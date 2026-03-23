# -*- coding: utf-8 -*-
"""
Extension du modèle purchase.order pour la gestion d'achats construction.
Philosophie SAP/Salesforce - Enterprise-grade.
"""

from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

from odoo.addons.construction_core.utils.logger import get_logger

_logger = get_logger(__name__)


class PurchaseOrderConstruction(models.Model):
    """Extension du modèle purchase.order pour la construction."""
    
    _inherit = 'purchase.order'

    # =================== CHAMPS MÉTIER ===================
    
    chantier_id = fields.Many2one(
        'construction.chantier',
        string='Chantier',
        tracking=True,
        help="Projet de construction associé à cette commande"
    )
    
    lot_ids = fields.Many2many(
        'construction.lot',
        'purchase_order_lot_rel',
        'order_id',
        'lot_id',
        string='Lots concernés',
        help="Lots de construction pour cette commande"
    )
    
    # =================== CHAMPS CALCULÉS ===================
    
    order_line_count = fields.Integer(
        string='Nombre de lignes',
        compute='_compute_order_statistics',
        store=True,
        help="Nombre de lignes de produits (hors sections/notes)"
    )
    
    total_quantity = fields.Float(
        string='Quantité totale',
        compute='_compute_order_statistics',
        store=True,
        help="Quantité totale de tous les produits"
    )
    
    lots_count = fields.Integer(
        string='Nombre de lots',
        compute='_compute_lots_count'
    )
    
    margin_amount = fields.Monetary(
        string='Marge estimée',
        compute='_compute_margin',
        currency_field='currency_id',
        help="Différence entre prix de vente estimé et prix d'achat"
    )
    
    margin_percent = fields.Float(
        string='Marge (%)',
        compute='_compute_margin',
        help="Pourcentage de marge"
    )

    blg_name_generated = fields.Boolean(
        string='Référence BLG générée',
        copy=False,
        default=False,
        help="True une fois que la référence BLG a été appliquée à la première confirmation."
    )

    # =================== CONTRAINTES ===================
    
    @api.constrains('chantier_id', 'lot_ids')
    def _check_lot_coherence(self):
        """Vérifie que les lots sélectionnés appartiennent au chantier."""
        for record in self:
            if record.chantier_id and record.lot_ids:
                chantier_lots = record.chantier_id.lots_ids
                invalid_lots = record.lot_ids - chantier_lots
                if invalid_lots:
                    raise ValidationError(_(
                        "Les lots suivants n'appartiennent pas au chantier '%s' : %s"
                    ) % (record.chantier_id.name, ', '.join(invalid_lots.mapped('name'))))

    # =================== MÉTHODES CALCULÉES ===================

    @api.depends('order_line')
    def _compute_order_statistics(self):
        """Calcule les statistiques de la commande."""
        for record in self:
            product_lines = record.order_line.filtered(lambda l: not l.display_type)
            record.order_line_count = len(product_lines)
            record.total_quantity = sum(product_lines.mapped('product_qty'))

    def _compute_lots_count(self):
        """Compte les lots liés."""
        for record in self:
            record.lots_count = len(record.lot_ids)

    @api.depends('amount_total', 'order_line.price_subtotal')
    def _compute_margin(self):
        """Calcule la marge estimée basée sur les prix de vente des lots."""
        for record in self:
            if record.lot_ids and record.amount_total:
                # Somme des prix de vente des lots
                sale_price = sum(record.lot_ids.mapped('price'))
                purchase_price = record.amount_total
                record.margin_amount = sale_price - purchase_price
                record.margin_percent = ((sale_price - purchase_price) / purchase_price * 100) if purchase_price else 0
            else:
                record.margin_amount = 0
                record.margin_percent = 0

    # =================== CRUD ===================

    @api.model
    def create(self, vals):
        """Injecter le nom du chantier lors de la création."""
        if vals.get('chantier_id') and (not vals.get('name') or vals.get('name') == '/'):
            chantier = self.env['construction.chantier'].browse(vals['chantier_id'])
            if chantier.exists():
                # Le name sera généré par la séquence, mais on peut ajouter une note
                pass
        
        return super().create(vals)

    # =================== SYNCHRONISATION ===================

    @api.onchange('chantier_id')
    def _onchange_chantier_id(self):
        """Mise à jour automatique lors du changement de chantier."""
        if self.chantier_id:
            # Pré-sélectionner les lots du chantier
            if self.chantier_id.lots_ids:
                self.lot_ids = self.chantier_id.lots_ids
            
            # Mettre à jour l'adresse de livraison si disponible
            if self.chantier_id.address:
                self.notes = f"Livraison chantier: {self.chantier_id.address}"
                if self.chantier_id.city:
                    self.notes += f", {self.chantier_id.city}"

    @api.onchange('partner_id')
    def _onchange_partner_for_lots(self):
        """Filtrer les lots selon le sous-traitant sélectionné."""
        if self.partner_id and self.chantier_id:
            # Trouver les lots assignés à ce sous-traitant
            subcontractor_lots = self.chantier_id.lots_ids.filtered(
                lambda l: self.partner_id in l.subcontractor_ids
            )
            if subcontractor_lots:
                self.lot_ids = subcontractor_lots

    # =================== CONFIRMATION / NOMMAGE ===================

    def button_confirm(self):
        """Surcharge : génère la référence BLG à la première confirmation."""
        res = super().button_confirm()
        for record in self:
            if record.chantier_id and not record.blg_name_generated:
                blg_name = record._generate_blg_name()
                if blg_name:
                    record.write({'name': blg_name, 'blg_name_generated': True})
                    _logger.wizard_action('purchase_order', 'blg_name_generated', record)
        return res

    def _generate_blg_name(self):
        """Calcule le nom BLG au format [REF_CHANTIER]-[LOTS]-[INITIALES_ST]-[YYYYMMDD]."""
        self.ensure_one()
        chantier = self.chantier_id
        if not chantier:
            return False

        # Partie 1 : référence chantier (séquence si disponible, sinon nom)
        ref_chantier = (chantier.reference or chantier.name or 'CHANTIER').upper()
        # Normaliser : pas d'espaces ni de slashs dans la ref
        ref_chantier = ref_chantier.replace('/', '').replace(' ', '_').strip('_')

        # Partie 2 : codes lots (ex: ELEC+PLOM)
        if self.lot_ids:
            lot_codes = '+'.join(
                (lot.code or lot.name[:4]).upper()
                for lot in self.lot_ids.sorted('sequence')
            )
        else:
            lot_codes = 'SANS-LOT'

        # Partie 3 : initiales du sous-traitant (Prénom NOM → PN)
        initiales = self._compute_partner_initials(self.partner_id)

        # Partie 4 : date de confirmation
        today = date.today().strftime('%Y%m%d')

        return f"{ref_chantier}-{lot_codes}-{initiales}-{today}"

    @staticmethod
    def _compute_partner_initials(partner):
        """Retourne les initiales Prénom+Nom d'un partenaire (ex: 'BF' pour 'Baptiste Fontaine')."""
        if not partner:
            return 'XX'
        # Essayer d'abord prénom/nom séparés
        parts = []
        if partner.firstname:
            parts.append(partner.firstname[0])
        if partner.lastname:
            parts.append(partner.lastname[0])
        if parts:
            return ''.join(parts).upper()
        # Fallback : mots du name
        words = (partner.name or '').split()
        if len(words) >= 2:
            return (words[0][0] + words[-1][0]).upper()
        if words:
            return words[0][:2].upper()
        return 'XX'

    # =================== ACTIONS PRINCIPALES ===================

    def action_add_product_wizard(self):
        """Ouvrir l'assistant de sélection de produits."""
        self.ensure_one()
        
        if not self.chantier_id:
            raise UserError(_(
                "Veuillez d'abord sélectionner un chantier pour utiliser l'assistant."
            ))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Assistant de Création de Commande'),
            'res_model': 'construction.purchase.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_purchase_order_id': self.id,
                'default_chantier_id': self.chantier_id.id,
                'default_partner_id': self.partner_id.id,
            }
        }

    def action_organize_by_lots(self):
        """Organiser la commande par sections de lots."""
        self.ensure_one()
        
        if not self.lot_ids:
            raise UserError(_(
                "Veuillez sélectionner des lots pour organiser cette commande."
            ))
        
        self._create_lot_sections()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Commande Organisée'),
                'message': _('%d section(s) créée(s) pour les lots.') % len(self.lot_ids),
                'type': 'success'
            }
        }

    def action_validate_and_update_chantier(self):
        """Valider la commande et mettre à jour le chantier."""
        self.ensure_one()
        
        # Validation métier
        if not self.order_line.filtered(lambda l: not l.display_type):
            raise UserError(_(
                "Impossible de valider une commande sans ligne de produit."
            ))
        
        # Confirmer la commande
        self.button_confirm()
        
        # Mettre à jour le chantier
        if self.chantier_id:
            self._update_chantier_on_validation()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Commande Validée'),
                'message': _('La commande %s a été validée avec succès.') % self.name,
                'type': 'success'
            }
        }

    def action_view_lots(self):
        """Smart button: Voir les lots liés."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Lots - %s') % self.name,
            'res_model': 'construction.lot',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.lot_ids.ids)],
            'context': {'default_chantier_id': self.chantier_id.id if self.chantier_id else False},
        }

    def action_open_purchase_builder(self):
        """Ouvre le PurchaseBuilder Owl pour ce bon de commande."""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'construction_purchase.purchase_builder',
            'name': _('Purchase Builder — %s') % self.name,
            'context': {
                'active_id': self.id,
                'default_order_id': self.id,
            },
        }

    def action_view_chantier(self):
        """Smart button: Voir le chantier."""
        self.ensure_one()
        if not self.chantier_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'name': _('Chantier'),
            'res_model': 'construction.chantier',
            'res_id': self.chantier_id.id,
            'view_mode': 'form',
        }

    # =================== MÉTHODES PRIVÉES ===================

    def _create_lot_sections(self):
        """Créer des sections pour chaque lot dans la commande."""
        sequence = self._get_next_sequence()
        
        for lot in self.lot_ids:
            # Vérifier si la section existe déjà
            existing_section = self.order_line.filtered(
                lambda l: l.display_type == 'line_section' and lot.name in (l.name or '')
            )
            if not existing_section:
                self._create_section_for_lot(lot, sequence)
                sequence += 10

    def _create_section_for_lot(self, lot, sequence):
        """Créer une section pour un lot donné."""
        section_vals = {
            'order_id': self.id,
            'display_type': 'line_section',
            'name': _('📦 Lot : %s') % lot.name,
            'sequence': sequence,
            'product_qty': 0.0,
        }
        
        self.env['purchase.order.line'].create(section_vals)

    def _get_next_sequence(self):
        """Retourne la prochaine séquence disponible."""
        if self.order_line:
            return max(self.order_line.mapped('sequence')) + 10
        return 10

    # =================== PURCHASE BUILDER (API) ===================

    @api.model
    def search_products_for_builder(self, term='', lot_category_id=None, limit=100):
        """Catalogue produits pour le PurchaseBuilder Owl."""
        domain = [
            ('purchase_ok', '=', True),
            ('active', '=', True),
        ]
        if term:
            domain.append(('name', 'ilike', term))
        if lot_category_id:
            domain.append(('lot_category_ids', 'in', [lot_category_id]))
        products = self.env['product.template'].search(domain, limit=limit)
        return products.read(['id', 'name', 'display_name', 'uom_id', 'standard_price', 'list_price'])

    @api.model
    def get_builder_totals(self, order_id):
        """Retourne les totaux serveur du bon de commande pour le PurchaseBuilder."""
        order = self.browse(order_id)
        if not order.exists():
            return {}
        lot_totals = {}
        for line in order.order_line.filtered(lambda l: not l.display_type):
            lot_key = line.lot_id.id if line.lot_id else 0
            lot_name = line.lot_id.name if line.lot_id else _('Sans lot')
            if lot_key not in lot_totals:
                lot_totals[lot_key] = {'id': lot_key, 'name': lot_name, 'subtotal': 0.0}
            lot_totals[lot_key]['subtotal'] += line.price_subtotal
        return {
            'amount_untaxed': order.amount_untaxed,
            'amount_tax': order.amount_tax,
            'amount_total': order.amount_total,
            'currency_symbol': order.currency_id.symbol or '€',
            'lot_totals': list(lot_totals.values()),
        }

    @api.model
    def save_builder_lines(self, order_id, lines):
        """Sauvegarde les lignes depuis le PurchaseBuilder, retourne les totaux.

        `lines` est une liste de dicts:
          { id (optionnel), product_id, name, product_qty, price_unit,
            lot_id, room_location, floor_level, construction_notes }
        Les lignes absentes du payload et sans display_type sont supprimées.
        """
        self = self.browse(order_id)
        self.ensure_one()
        incoming_ids = {l['id'] for l in lines if l.get('id')}

        # Supprimer les lignes produit non présentes dans le payload
        lines_to_delete = self.order_line.filtered(
            lambda l: not l.display_type and l.id not in incoming_ids
        )
        lines_to_delete.unlink()

        for line_data in lines:
            vals = {
                'product_id': line_data.get('product_id'),
                'name': line_data.get('name', ''),
                'product_qty': line_data.get('product_qty', 1.0),
                'price_unit': line_data.get('price_unit', 0.0),
                'lot_id': line_data.get('lot_id') or False,
                'room_location': line_data.get('room_location', ''),
                'floor_level': line_data.get('floor_level') or False,
                'construction_notes': line_data.get('construction_notes', ''),
            }
            if line_data.get('id'):
                existing = self.order_line.filtered(lambda l: l.id == line_data['id'])
                if existing:
                    existing.write(vals)
            else:
                vals['order_id'] = self.id
                if vals['product_id']:
                    product = self.env['product.product'].browse(vals['product_id'])
                    if not vals['price_unit']:
                        vals['price_unit'] = product.standard_price
                    vals['product_uom'] = product.uom_po_id.id or product.uom_id.id
                self.env['purchase.order.line'].create(vals)

        return self.get_builder_totals(self.id)

    def message_post(self, **kwargs):
        """Duplique le message dans le thread du chantier parent."""
        result = super().message_post(**kwargs)
        if self.env.context.get('_posting_to_chantier'):
            return result
        chantier = getattr(self, 'chantier_id', False)
        if chantier and chantier.exists():
            prefix = f"[BdC — {self.name}]"
            original_body = kwargs.get('body', '')
            chantier.with_context(_posting_to_chantier=True).message_post(
                body=f"<b>{prefix}</b><br/>{original_body}",
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )
        return result

    def _update_chantier_on_validation(self):
        """Mettre à jour le chantier lors de la validation."""
        try:
            # Log de la validation
            self.chantier_id.message_post(
                body=_(
                    "📦 Commande fournisseur %s validée\n"
                    "Fournisseur: %s\n"
                    "Montant: %s %s\n"
                    "Lots: %s"
                ) % (
                    self.name,
                    self.partner_id.name,
                    f"{self.amount_total:,.2f}",
                    self.currency_id.symbol,
                    ', '.join(self.lot_ids.mapped('name')) if self.lot_ids else '-'
                ),
                message_type='notification'
            )
        except Exception as e:
            _logger.business_error(self, '_update_chantier_on_validation', e)


class PurchaseOrderGroupedCreation(models.TransientModel):
    """Wizard pour créer des commandes groupées par sous-traitant."""
    
    _name = 'construction.purchase.grouped.wizard'
    _description = 'Création groupée de commandes'

    chantier_id = fields.Many2one(
        'construction.chantier',
        string='Chantier',
        required=True
    )
    
    create_one_per_subcontractor = fields.Boolean(
        string='Une commande par sous-traitant',
        default=True,
        help="Créer une commande distincte pour chaque sous-traitant"
    )
    
    lot_ids = fields.Many2many(
        'construction.lot',
        string='Lots à commander',
        domain="[('chantier_id', '=', chantier_id)]"
    )

    @api.onchange('chantier_id')
    def _onchange_chantier_id(self):
        """Pré-remplir les lots du chantier."""
        if self.chantier_id:
            self.lot_ids = self.chantier_id.lots_ids

    def action_create_grouped_orders(self):
        """Créer les commandes groupées par sous-traitant."""
        self.ensure_one()
        
        if not self.lot_ids:
            raise UserError(_("Veuillez sélectionner au moins un lot."))
        
        created_orders = self.env['purchase.order']
        
        if self.create_one_per_subcontractor:
            # Grouper par sous-traitant
            subcontractor_lots = {}
            for lot in self.lot_ids:
                for subcontractor in lot.subcontractor_ids:
                    if subcontractor.id not in subcontractor_lots:
                        subcontractor_lots[subcontractor.id] = self.env['construction.lot']
                    subcontractor_lots[subcontractor.id] |= lot
            
            # Créer une commande par sous-traitant
            for subcontractor_id, lots in subcontractor_lots.items():
                order = self._create_order_for_subcontractor(subcontractor_id, lots)
                created_orders |= order
        else:
            # Créer une seule commande avec tous les lots
            if self.lot_ids.mapped('subcontractor_ids'):
                first_subcontractor = self.lot_ids.mapped('subcontractor_ids')[0]
                order = self._create_order_for_subcontractor(first_subcontractor.id, self.lot_ids)
                created_orders |= order
        
        # Retourner vers les commandes créées
        if len(created_orders) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Commande Créée'),
                'res_model': 'purchase.order',
                'res_id': created_orders.id,
                'view_mode': 'form',
            }
        else:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Commandes Créées'),
                'res_model': 'purchase.order',
                'view_mode': 'list,form',
                'domain': [('id', 'in', created_orders.ids)],
            }

    def _create_order_for_subcontractor(self, subcontractor_id, lots):
        """Créer une commande pour un sous-traitant avec les lots donnés."""
        order = self.env['purchase.order'].create({
            'partner_id': subcontractor_id,
            'chantier_id': self.chantier_id.id,
            'lot_ids': [(6, 0, lots.ids)],
        })
        
        # Créer les sections par lot
        order._create_lot_sections()
        
        return order
