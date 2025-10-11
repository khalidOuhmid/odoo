# -*- coding: utf-8 -*-
"""Assistant intelligent pour la création de devis construction."""

import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ConstructionQuoteWizard(models.TransientModel):
    """Assistant intelligent pour la création de devis construction.
    
    Cet assistant permet de :
    - Sélectionner des lots du chantier
    - Rechercher et ajouter des produits au devis
    - Créer des produits personnalisés
    - Gérer les unités de mesure (m², ml, lots, etc.)
    - Organiser automatiquement le devis par sections de lots
    """
    
    _name = 'construction.quote.wizard'
    _description = 'Assistant de création de devis intelligent'

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Devis',
        required=True,
        readonly=True
    )
    
    chantier_id = fields.Many2one(
        'construction.chantier',
        string='Chantier',
        required=True,
        readonly=True
    )
    
    lot_ids = fields.Many2many(
        'construction.lot',
        string='Lots à traiter',
        domain="[('id', 'in', available_lot_ids if available_lot_ids else [0])]",
        help="Sélectionnez les lots du chantier pour lesquels créer des lignes de devis"
    )
    
    available_lot_ids = fields.Many2many(
        'construction.lot',
        compute='_compute_available_lots',
        string='Lots disponibles'
    )

    search_term = fields.Char(
        string='Rechercher un produit',
        placeholder="Nom, référence, description..."
    )
    
    category_filter_id = fields.Many2one(
        'product.category',
        string='Filtrer par catégorie'
    )
    
    show_lot_products_only = fields.Boolean(
        string='Produits spécifiques aux lots',
        default=True,
        help="Afficher uniquement les produits liés aux lots sélectionnés"
    )
    
    default_margin_percent = fields.Float(
        string='Marge par défaut (%)',
        default=50.0,
        help="Marge commerciale par défaut à appliquer aux nouveaux produits"
    )

    available_product_ids = fields.Many2many(
        'product.product',
        compute='_compute_available_products',
        string='Produits disponibles'
    )
    
    selected_line_ids = fields.One2many(
        'construction.quote.line',
        'wizard_id',
        string='Lignes sélectionnées'
    )

    total_amount = fields.Monetary(
        string='Montant total',
        compute='_compute_totals',
        currency_field='currency_id'
    )
    
    total_quantity = fields.Float(
        string='Quantité totale',
        compute='_compute_totals'
    )
    
    line_count = fields.Integer(
        string='Nombre de lignes',
        compute='_compute_totals'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        compute='_compute_currency',
        readonly=True
    )

    @api.depends('sale_order_id.currency_id')
    def _compute_currency(self):
        """Calcule la devise du wizard depuis le devis."""
        for wizard in self:
            if wizard.sale_order_id and wizard.sale_order_id.currency_id:
                wizard.currency_id = wizard.sale_order_id.currency_id
            else:
                wizard.currency_id = self.env.company.currency_id

    @api.model
    def default_get(self, fields_list):
        """Initialise les valeurs par défaut du wizard."""
        res = super().default_get(fields_list)
        
        if 'lot_ids' in fields_list and self.env.context.get('default_lot_ids'):
            res['lot_ids'] = self.env.context['default_lot_ids']
        
        return res

    @api.depends('chantier_id.lots_ids')
    def _compute_available_lots(self):
        """Calcule les lots disponibles depuis le chantier uniquement."""
        for wizard in self:
            if wizard.chantier_id and wizard.chantier_id.lots_ids:
                wizard.available_lot_ids = wizard.chantier_id.lots_ids
            else:
                wizard.available_lot_ids = self.env['construction.lot']

    @api.depends('search_term', 'category_filter_id', 'lot_ids', 'show_lot_products_only')
    def _compute_available_products(self):
        """Calcule les produits disponibles selon les filtres."""
        for wizard in self:
            domain = [
                ('sale_ok', '=', True),
                ('active', '=', True)
            ]
            
            if wizard.search_term:
                search_domain = [
                    '|', '|', '|',
                    ('name', 'ilike', wizard.search_term),
                    ('default_code', 'ilike', wizard.search_term),
                    ('description_sale', 'ilike', wizard.search_term),
                    ('barcode', 'ilike', wizard.search_term)
                ]
                domain.extend(search_domain)
            
            if wizard.category_filter_id:
                domain.append(('categ_id', 'child_of', wizard.category_filter_id.id))
            
            if wizard.show_lot_products_only and wizard.lot_ids:
                if hasattr(self.env['product.product'], 'lot_ids'):
                    domain.append(('lot_ids', 'in', wizard.lot_ids.ids))
            
            products = self.env['product.product'].search(
                domain, 
                limit=100, 
                order='name'
            )
            
            wizard.available_product_ids = products

    @api.depends('selected_line_ids.quantity', 'selected_line_ids.price_unit')
    def _compute_totals(self):
        """Calcule les totaux de la sélection."""
        for wizard in self:
            lines = wizard.selected_line_ids.filtered('quantity') if wizard.selected_line_ids else self.env['construction.quote.line']
            
            wizard.total_amount = sum(
                (line.quantity or 0.0) * (line.price_unit or 0.0) for line in lines
            ) if lines else 0.0
            
            wizard.total_quantity = sum(
                line.quantity or 0.0 for line in lines
            ) if lines else 0.0
            
            wizard.line_count = len(lines) if lines else 0

    def action_add_product(self):
        """Ouvrir le popup d'ajout de produit."""
        product_id = self.env.context.get('product_id')
        if not product_id:
            return self._reload_wizard()
        
        if not self.lot_ids:
            raise ValidationError(_(
                "Veuillez d'abord sélectionner au moins un lot "
                "avant d'ajouter des produits."
            ))
        
        dialog = self.env['construction.product.dialog'].create({
            'quote_wizard_id': self.id,
            'product_id': product_id,
            'margin_percent': self.default_margin_percent,
        })
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Ajouter : %s') % dialog.product_name,
            'res_model': 'construction.product.dialog',
            'res_id': dialog.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_create_quick_product(self):
        """Ouvrir le popup de création rapide de produit."""
        default_category = self.category_filter_id
        if not default_category:
            default_category = self.env['product.category'].search([
                '|', 
                ('name', 'ilike', 'construction'),
                ('name', 'ilike', 'matériau')
            ], limit=1)
            if not default_category:
                default_category = self.env['product.category'].search([], limit=1)
        
        dialog = self.env['construction.product.creator'].create({
            'quote_wizard_id': self.id,
            'categ_id': default_category.id if default_category else False,
            'lot_ids': [(6, 0, self.lot_ids.ids)] if self.lot_ids else False,
            'name': '',
        })
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Créer un nouveau produit personnalisé'),
            'res_model': 'construction.product.creator',
            'res_id': dialog.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_confirm_selection(self):
        """Confirmer et ajouter les produits au devis."""
        if not self.selected_line_ids.filtered('quantity'):
            raise ValidationError(_("Veuillez sélectionner au moins un produit."))
        
        if not self.lot_ids:
            self.lot_ids = self.chantier_id.lots_ids
        
        self._add_products_to_order()
        
        if self.lot_ids:
            self.sale_order_id.write({
                'lot_ids': [(6, 0, self.lot_ids.ids)]
            })
        
        self.selected_line_ids.unlink()
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Assistant de création de devis - %s') % self.chantier_id.name,
            'res_model': 'construction.quote.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_chantier_id': self.chantier_id.id,
                'default_sale_order_id': self.sale_order_id.id,
            }
        }

    def action_finalize_quote(self):
        """Finaliser le devis et retourner au devis."""
        # Ajouter les produits sélectionnés s'il y en a
        if self.selected_line_ids.filtered('quantity'):
            self.action_confirm_selection()
        
        # Retourner vers le devis créé
        return {
            'type': 'ir.actions.act_window',
            'name': _('Devis %s') % self.sale_order_id.name,
            'res_model': 'sale.order',
            'res_id': self.sale_order_id.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_chantier_id': self.chantier_id.id,
                'form_view_initial_mode': 'edit',
            }
        }

    def action_cancel_wizard(self):
        """Annuler le wizard avec confirmation si nécessaire."""
        if self.selected_line_ids:
            # Il y a des produits sélectionnés, demander confirmation
            return {
                'type': 'ir.actions.act_window',
                'name': _('Attention - Progression en cours'),
                'res_model': 'construction.wizard.cancel.confirm',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_wizard_id': self.id,
                }
            }
        else:
            # Pas de progression, fermer directement
            return {'type': 'ir.actions.act_window_close'}

    def action_safe_close(self):
        """Fermeture sécurisée avec vérification de progression."""
        return self.action_cancel_wizard()

    def _return_to_sale_order(self):
        """Retourne vers le devis de vente."""
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': self.sale_order_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_selection(self):
        """Afficher la sélection dans un popup"""
        if not self.selected_line_ids:
            raise ValidationError(_("Aucun produit sélectionné à afficher."))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Ma sélection - %s') % self.chantier_id.name,
            'res_model': 'construction.quote.line',
            'view_mode': 'list,form',
            'domain': [('wizard_id', '=', self.id)],
            'target': 'new',
            'context': {
                'default_wizard_id': self.id,
            }
        }

    def action_clear_selection(self):
        """Vider la sélection"""
        self.selected_line_ids.unlink()
        return self._reload_wizard()

    def action_refresh_products(self):
        """Actualiser la liste des produits"""
        self._compute_available_products()
        return self._reload_wizard()

    def _add_products_to_order(self):
        """Ajoute les produits sélectionnés au devis organisés par lots."""
        self._add_products_by_lots()

    def _add_products_by_lots(self):
        """Ajouter les produits organisés par sections de lots."""
        order = self.sale_order_id
        
        lots_with_products = self.selected_line_ids.mapped('lot_id')
        for lot in self.lot_ids:
            if lot in lots_with_products:
                lot_lines = self.selected_line_ids.filtered(lambda l: l.lot_id == lot)
                section_line = order.order_line.filtered(lambda l: l.display_type == 'line_section' and l.name.strip() == f"📋 {lot.name}")
                
                if section_line:
                    section = section_line[0]
                    section_seq = section.sequence
                    lot_product_lines = order.order_line.filtered(lambda l: l.lot_id == lot and not l.display_type and l.sequence > section_seq)
                    if lot_product_lines:
                        next_seq = max(lot_product_lines.mapped('sequence')) + 10
                    else:
                        next_seq = section_seq + 10
                else:
                    section = self._create_lot_section(lot, self._get_next_sequence())
                    next_seq = section.sequence + 10 if hasattr(section, 'sequence') else self._get_next_sequence() + 10
                
                sorted_lines = sorted(lot_lines, key=lambda l: l.product_id.name or '')
                for line in sorted_lines:
                    self._create_order_line(line, next_seq)
                    next_seq += 10

    def _create_lot_section(self, lot, sequence):
        """Crée une section pour un lot."""
        return self.env['sale.order.line'].create({
            'order_id': self.sale_order_id.id,
            'display_type': 'line_section',
            'name': f"📋 {lot.name}",
            'sequence': sequence,
        })

    def _create_order_line(self, quote_line, sequence):
        """Crée une ligne de commande à partir d'une ligne du wizard."""
        values = {
            'order_id': self.sale_order_id.id,
            'product_id': quote_line.product_id.id,
            'product_uom_qty': quote_line.quantity,
            'product_uom': quote_line.uom_id.id,
            'price_unit': quote_line.price_unit,
            'sequence': sequence,
        }
        
        # Ajouter le lot de construction
        if quote_line.lot_id:
            values['lot_id'] = quote_line.lot_id.id
        
        # Informations de localisation
        if quote_line.room_location:
            values['room_location'] = quote_line.room_location
        if quote_line.room_number:
            room_info = f"[{quote_line.room_number}]"
            if quote_line.room_location:
                room_info += f" {quote_line.room_location}"
            values['room_location'] = room_info
        if quote_line.floor_level:
            values['floor_level'] = quote_line.floor_level
        if quote_line.construction_notes:
            values['construction_notes'] = quote_line.construction_notes
        
        # Nom du produit avec informations de localisation
        product_name = quote_line.product_id.name
        name_parts = [product_name]
        
        if quote_line.room_number or quote_line.room_location:
            location_info = []
            if quote_line.room_location:
                location_info.append(quote_line.room_location)
            if quote_line.room_number:
                location_info.append(f"Salle {quote_line.room_number}")
            name_parts.append(f"({' - '.join(location_info)})")
        
        if quote_line.construction_notes:
            name_parts.append(f"\nNotes: {quote_line.construction_notes}")
        
        values['name'] = ' '.join(name_parts)
        
        self.env['sale.order.line'].create(values)

    def _get_next_sequence(self):
        """Retourne la prochaine séquence disponible dans le devis"""
        last_line = self.sale_order_id.order_line.sorted('sequence', reverse=True)
        return (last_line[0].sequence + 10) if last_line else 10

    def unlink(self):
        """Suppression sécurisée du wizard avec nettoyage des enregistrements liés"""
        # Supprimer toutes les lignes liées avant de supprimer le wizard
        for wizard in self:
            if wizard.selected_line_ids:
                wizard.selected_line_ids.unlink()
        
        # Supprimer le wizard lui-même
        return super().unlink()

    def _reload_wizard(self):
        """Recharge le wizard"""
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }


class ProductAddDialog(models.TransientModel):
    """Popup d'ajout de produit avec unité de mesure configurable."""
    
    _name = 'construction.product.dialog'
    _description = 'Popup d\'ajout de produit'

    quote_wizard_id = fields.Many2one(
        'construction.quote.wizard',
        required=True,
        ondelete='cascade'
    )
    
    product_id = fields.Many2one(
        'product.product',
        string='Produit',
        required=True,
        readonly=True
    )
    
    product_name = fields.Char(
        related='product_id.display_name',
        readonly=True
    )
    
    base_price = fields.Float(
        related='product_id.standard_price',
        readonly=True
    )

    quantity = fields.Float(
        string='Quantité',
        default=1.0,
        required=True
    )
    
    uom_id = fields.Many2one(
        'uom.uom',
        string='Unité de mesure',
        required=True,
        help="Unité de mesure pour ce produit (m², ml, lots, etc.)"
    )
    
    margin_percent = fields.Float(
        string='Marge (%)',
        default=20.0,
        help="Marge commerciale à appliquer"
    )
    
    unit_price = fields.Float(
        string='Prix unitaire final',
        compute='_compute_unit_price'
    )
    
    total_price = fields.Float(
        string='Total',
        compute='_compute_total_price'
    )
    
    room_number = fields.Char(
        string='N° Salle',
        placeholder="Ex: S01, C12..."
    )
    
    room_location = fields.Char(
        string='Localisation',
        placeholder="Ex: Salon, Cuisine..."
    )
    
    description = fields.Text(
        string='Description/Notes',
        placeholder="Notes techniques..."
    )
    
    lot_id = fields.Many2one(
        'construction.lot',
        string='Lot',
        required=True,
        help="Lot de construction pour ce produit"
    )
    
    available_lot_ids = fields.Many2many(
        'construction.lot',
        compute='_compute_available_lots_for_dialog',
        string='Lots disponibles'
    )

    @api.depends('quote_wizard_id.lot_ids')
    def _compute_available_lots_for_dialog(self):
        """Calcule les lots disponibles depuis le wizard parent."""
        for dialog in self:
            if dialog.quote_wizard_id and dialog.quote_wizard_id.lot_ids:
                dialog.available_lot_ids = dialog.quote_wizard_id.lot_ids
            else:
                dialog.available_lot_ids = self.env['construction.lot']
    
    @api.depends('base_price', 'margin_percent')
    def _compute_unit_price(self):
        """Calcule le prix unitaire final = coût * (1 + marge)."""
        for dialog in self:
            cost = dialog.base_price or 0.0
            margin = dialog.margin_percent or 0.0
            dialog.unit_price = cost * (1 + margin / 100.0)
    
    @api.depends('unit_price', 'quantity')
    def _compute_total_price(self):
        """Calcule le prix total."""
        for dialog in self:
            dialog.total_price = dialog.unit_price * dialog.quantity

    @api.model
    def create(self, vals):
        """Créer le dialog avec initialisation correcte."""
        dialog = super().create(vals)
        
        if dialog.quote_wizard_id:
            dialog._compute_available_lots_for_dialog()
            # Auto-assigner le lot unique ou le premier disponible
            if len(dialog.available_lot_ids) == 1:
                dialog.lot_id = dialog.available_lot_ids[0]
            elif not dialog.lot_id and dialog.available_lot_ids:
                dialog.lot_id = dialog.available_lot_ids[0]
        
        # Initialiser l'unité de mesure du produit
        if dialog.product_id and dialog.product_id.uom_id:
            dialog.uom_id = dialog.product_id.uom_id
        elif not dialog.uom_id:
            # Unité par défaut
            default_uom = self.env['uom.uom'].search([('name', '=', 'Units')], limit=1)
            if default_uom:
                dialog.uom_id = default_uom
        
        return dialog
    
    def action_confirm_add(self):
        """Confirmer l'ajout du produit."""
        if self.quantity <= 0:
            raise ValidationError(_("La quantité doit être positive."))
        
        if not self.lot_id:
            raise ValidationError(_("Veuillez sélectionner un lot pour ce produit."))
        
        if not self.uom_id:
            raise ValidationError(_("Veuillez sélectionner une unité de mesure."))
        
        # Créer la ligne dans le wizard principal
        line_vals = {
            'wizard_id': self.quote_wizard_id.id,
            'product_id': self.product_id.id,
            'quantity': self.quantity,
            'price_unit': self.unit_price,
            'lot_id': self.lot_id.id,
            'uom_id': self.uom_id.id,
            'room_number': self.room_number,
            'room_location': self.room_location,
            'construction_notes': self.description,
            'margin_percent': self.margin_percent,
        }
        
        self.env['construction.quote.line'].create(line_vals)
        
        return self._return_to_wizard()

    def action_cancel(self):
        """Annuler l'ajout et retourner au wizard principal."""
        return self._return_to_wizard()

    def _return_to_wizard(self):
        """Retourne vers le wizard principal."""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Assistant de création de devis - %s') % self.quote_wizard_id.chantier_id.name,
            'res_model': 'construction.quote.wizard',
            'res_id': self.quote_wizard_id.id,
            'view_mode': 'form',
            'target': 'new',
        }


class ConstructionQuoteLine(models.TransientModel):
    """Ligne de produit dans le wizard de devis."""
    
    _name = 'construction.quote.line'
    _description = 'Ligne de produit pour devis construction'
    _order = 'sequence, id'

    wizard_id = fields.Many2one(
        'construction.quote.wizard',
        required=True,
        ondelete='cascade'
    )
    
    product_id = fields.Many2one(
        'product.product',
        string='Produit',
        required=True
    )
    
    lot_id = fields.Many2one(
        'construction.lot',
        string='Lot',
        required=True,
        help="Lot de construction pour ce produit"
    )

    sequence = fields.Integer(
        string='Séquence',
        default=10
    )
    
    quantity = fields.Float(
        string='Quantité',
        default=1.0,
        required=True
    )
    
    uom_id = fields.Many2one(
        'uom.uom',
        string='Unité',
        required=True,
        help="Unité de mesure (m², ml, lots, etc.)"
    )
    
    price_unit = fields.Float(
        string='Prix unitaire',
        default=0.0
    )
    
    margin_percent = fields.Float(
        string='Marge (%)',
        default=0.0
    )
    
    subtotal = fields.Float(
        string='Sous-total',
        compute='_compute_subtotal',
        store=True
    )
    
    product_code = fields.Char(
        related='product_id.default_code',
        readonly=True
    )
    
    room_number = fields.Char(
        string='N° Salle'
    )
    
    room_location = fields.Char(
        string='Localisation'
    )
    
    floor_level = fields.Char(
        string='Étage'
    )
    
    construction_notes = fields.Text(
        string='Notes'
    )

    @api.depends('quantity', 'price_unit')
    def _compute_subtotal(self):
        """Calcule le sous-total de la ligne."""
        for line in self:
            line.subtotal = line.quantity * line.price_unit

    @api.model
    def create(self, vals):
        """Créer la ligne avec unité par défaut si non spécifiée."""
        if 'uom_id' not in vals and vals.get('product_id'):
            product = self.env['product.product'].browse(vals['product_id'])
            if product.uom_id:
                vals['uom_id'] = product.uom_id.id
            else:
                # Unité par défaut
                default_uom = self.env['uom.uom'].search([('name', '=', 'Units')], limit=1)
                if default_uom:
                    vals['uom_id'] = default_uom.id
        return super().create(vals)

    def action_edit_line(self):
        """Ouvrir l'édition de la ligne."""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Modifier : %s') % self.product_id.name,
            'res_model': 'construction.line.editor',
            'res_id': False,
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_quote_line_id': self.id,
                'default_product_id': self.product_id.id,
                'default_quantity': self.quantity,
                'default_price_unit': self.price_unit,
                'default_uom_id': self.uom_id.id,
                'default_lot_id': self.lot_id.id,
                'default_room_number': self.room_number,
                'default_room_location': self.room_location,
                'default_construction_notes': self.construction_notes,
                'default_margin_percent': self.margin_percent,
            }
        }

    def action_remove_line(self):
        """Supprimer cette ligne de devis."""
        self.ensure_one()
        wizard = self.wizard_id
        self.unlink()
        
        # Retourner vers le wizard avec un message de confirmation
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'construction.quote.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'current',
        }


class ConstructionLineEditor(models.TransientModel):
    """Éditeur de ligne de produit."""
    
    _name = 'construction.line.editor'
    _description = 'Éditeur de ligne de produit'

    quote_line_id = fields.Many2one(
        'construction.quote.line',
        required=True,
        ondelete='cascade'
    )
    
    product_id = fields.Many2one(
        'product.product',
        string='Produit',
        required=True
    )
    
    product_name = fields.Char(
        related='product_id.display_name',
        readonly=True
    )
    
    quantity = fields.Float(
        string='Quantité',
        required=True
    )
    
    uom_id = fields.Many2one(
        'uom.uom',
        string='Unité de mesure',
        required=True
    )
    
    price_unit = fields.Float(
        string='Prix unitaire'
    )
    
    margin_percent = fields.Float(
        string='Marge (%)'
    )
    
    lot_id = fields.Many2one(
        'construction.lot',
        string='Lot',
        required=True
    )
    
    room_number = fields.Char(
        string='N° Salle'
    )
    
    room_location = fields.Char(
        string='Localisation'
    )
    
    construction_notes = fields.Text(
        string='Notes'
    )
    
    available_lot_ids = fields.Many2many(
        'construction.lot',
        compute='_compute_available_lots'
    )

    @api.depends('quote_line_id.wizard_id.lot_ids')
    def _compute_available_lots(self):
        """Calcule les lots disponibles."""
        for editor in self:
            if editor.quote_line_id and editor.quote_line_id.wizard_id:
                editor.available_lot_ids = editor.quote_line_id.wizard_id.lot_ids
            else:
                editor.available_lot_ids = self.env['construction.lot']

    def action_save_changes(self):
        """Sauvegarder les modifications."""
        if self.quantity <= 0:
            raise ValidationError(_("La quantité doit être positive."))
        
        if not self.lot_id:
            raise ValidationError(_("Veuillez sélectionner un lot."))
        
        if not self.uom_id:
            raise ValidationError(_("Veuillez sélectionner une unité de mesure."))
        
        # Mettre à jour la ligne
        self.quote_line_id.write({
            'product_id': self.product_id.id,
            'quantity': self.quantity,
            'uom_id': self.uom_id.id,
            'price_unit': self.price_unit,
            'margin_percent': self.margin_percent,
            'lot_id': self.lot_id.id,
            'room_number': self.room_number,
            'room_location': self.room_location,
            'construction_notes': self.construction_notes,
        })
        
        return self._return_to_wizard()

    def action_cancel(self):
        """Annuler les modifications."""
        return self._return_to_wizard()

    def _return_to_wizard(self):
        """Retourne vers le wizard principal."""
        wizard = self.quote_line_id.wizard_id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Assistant de création de devis - %s') % wizard.chantier_id.name,
            'res_model': 'construction.quote.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }


class ProductCreator(models.TransientModel):
    """Popup pour créer rapidement un nouveau produit."""
    
    _name = 'construction.product.creator'
    _description = 'Créateur de produit rapide'

    quote_wizard_id = fields.Many2one(
        'construction.quote.wizard',
        required=True,
        ondelete='cascade'
    )
    
    name = fields.Char(
        string='Nom du produit',
        required=True,
        placeholder="Ex: Peinture satinée blanche..."
    )
    
    default_code = fields.Char(
        string='Référence',
        placeholder="Ex: PEIN-SAT-BL"
    )
    
    categ_id = fields.Many2one(
        'product.category',
        string='Catégorie',
        required=True,
        default=lambda self: self._get_default_category_id()
    )
    
    uom_id = fields.Many2one(
        'uom.uom',
        string='Unité de mesure',
        required=True,
        default=lambda self: self._get_default_uom_id(),
        help="Unité de mesure (m², ml, lots, etc.)"
    )
    
    list_price = fields.Float(
        string='Prix de vente',
        default=0.0
    )
    
    standard_price = fields.Float(
        string='Coût',
        default=0.0
    )

    computed_sale_price = fields.Float(
        string='Prix de vente (calculé)',
        compute='_compute_computed_sale_price'
    )
    
    description_sale = fields.Text(
        string='Description',
        placeholder="Description pour les devis..."
    )
    
    lot_ids = fields.Many2many(
        'construction.lot',
        string='Lots associés',
        help="Lots pour lesquels ce produit est utilisé"
    )

    @api.model
    def create(self, vals):
        """Créer le créateur avec lot prédéfini."""
        creator = super().create(vals)
        
        # Auto-assigner les lots du wizard parent si non spécifiés
        if creator.quote_wizard_id and not creator.lot_ids:
            creator.lot_ids = [(6, 0, creator.quote_wizard_id.lot_ids.ids)]
        
        return creator

    @api.depends('standard_price', 'quote_wizard_id.default_margin_percent')
    def _compute_computed_sale_price(self):
        """Calcule le prix de vente = coût × (1 + marge)."""
        for rec in self:
            margin = rec.quote_wizard_id.default_margin_percent or 0.0
            cost = rec.standard_price or 0.0
            rec.computed_sale_price = cost * (1 + margin / 100.0)
    
    def action_create_product(self):
        """Créer le produit."""
        if not self.name:
            raise ValidationError(_("Le nom du produit est obligatoire."))
        
        if not self.categ_id:
            raise ValidationError(_("Veuillez sélectionner une catégorie."))
        
        if not self.uom_id:
            raise ValidationError(_("Veuillez sélectionner une unité de mesure."))
        
        # Code produit automatique si non renseigné
        generated_code = self.default_code or self._generate_default_code_from_lot()

        # Prix de vente calculé si non fourni
        computed_list_price = self.list_price
        if (not computed_list_price or computed_list_price <= 0) and self.standard_price:
            default_margin = self.quote_wizard_id.default_margin_percent or 0.0
            computed_list_price = self.standard_price * (1 + default_margin / 100.0)

        product_vals = {
            'name': self.name,
            'default_code': generated_code,
            'categ_id': self.categ_id.id,
            'uom_id': self.uom_id.id,
            'list_price': computed_list_price or 0.0,
            'standard_price': self.standard_price,
            'description_sale': self.description_sale,
            'sale_ok': True,
            'purchase_ok': False,
            'type': 'consu',
        }
        
        self.env['product.product'].create(product_vals)
        self.quote_wizard_id.action_refresh_products()
        
        return self._return_to_wizard()
    
    def action_cancel(self):
        """Annuler et retourner au wizard."""
        return self._return_to_wizard()

    def _return_to_wizard(self):
        """Retourne vers le wizard principal."""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Assistant de création de devis - %s') % self.quote_wizard_id.chantier_id.name,
            'res_model': 'construction.quote.wizard',
            'res_id': self.quote_wizard_id.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _generate_default_code_from_lot(self):
        """Génère un code produit basé sur le lot."""
        lot = self.lot_ids[:1]
        if not lot and self.quote_wizard_id:
            lot = self.quote_wizard_id.lot_ids[:1]
        
        if not lot:
            return None

        import re
        base = (lot.name or '').upper().strip()
        base = re.sub(r'\s+', '-', base)
        base = re.sub(r'[^A-Z0-9\-]', '', base)
        prefix = base or 'PROD'

        index = 1
        while True:
            candidate = f"{prefix}-{index:03d}"
            exists = self.env['product.product'].search_count([('default_code', '=', candidate)])
            if not exists:
                return candidate
            index += 1

    def _get_default_uom_id(self):
        """Retourne l'unité de mesure par défaut."""
        default_uom = self.env['uom.uom'].search([('name', '=', 'm²')], limit=1)
        if default_uom:
            return default_uom.id
        return self.env['uom.uom'].search([('name', '=', 'Units')], limit=1).id

    def _get_default_category_id(self):
        """Retourne la catégorie par défaut."""
        construction_category = self.env['product.category'].search([
            ('name', 'ilike', 'construction')
        ], limit=1)
        if construction_category:
            return construction_category.id
        return self.env['product.category'].search([], limit=1).id


class WizardCancelConfirm(models.TransientModel):
    """Popup de confirmation pour l'annulation du wizard."""
    
    _name = 'construction.wizard.cancel.confirm'
    _description = 'Confirmation d\'annulation du wizard'

    wizard_id = fields.Many2one(
        'construction.quote.wizard',
        required=True,
        ondelete='cascade'
    )
    
    line_count = fields.Integer(
        related='wizard_id.line_count',
        readonly=True
    )

    def action_confirm_cancel(self):
        """Confirmer l'annulation et perdre la progression."""
        # Vider la sélection et fermer
        if self.wizard_id.selected_line_ids:
            self.wizard_id.selected_line_ids.unlink()
        return {'type': 'ir.actions.act_window_close'}

    def action_continue_wizard(self):
        """Continuer avec le wizard."""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Assistant de création de devis - %s') % self.wizard_id.chantier_id.name,
            'res_model': 'construction.quote.wizard',
            'res_id': self.wizard_id.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_save_and_close(self):
        """Sauvegarder la progression et fermer."""
        if self.wizard_id.selected_line_ids.filtered('quantity'):
            self.wizard_id.action_confirm_selection()
        return self.wizard_id._return_to_sale_order()


