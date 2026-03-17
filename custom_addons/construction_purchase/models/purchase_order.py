# -*- coding: utf-8 -*-
"""
Extension du modèle purchase.order pour la gestion d'achats construction.
Philosophie SAP/Salesforce - Enterprise-grade.
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


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
            _logger.error(f"Erreur mise à jour chantier: {e}")


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
