# -*- coding: utf-8 -*-
"""
Wizard intelligent pour la création de commandes d'achat construction.
Philosophie SAP/Salesforce inspirée de construction_sale.
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class ConstructionPurchaseWizard(models.TransientModel):
    """Assistant intelligent pour la création de commandes d'achat construction.
    
    Permet de :
    - Sélectionner des lots du chantier
    - Rechercher et ajouter des produits
    - Gérer les sous-traitants par lot
    - Créer des commandes groupées par fournisseur
    """
    
    _name = 'construction.purchase.wizard'
    _description = 'Assistant de création de commande d\'achat'

    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Commande',
        readonly=True
    )
    
    chantier_id = fields.Many2one(
        'construction.chantier',
        string='Chantier',
        required=True
    )
    
    partner_id = fields.Many2one(
        'res.partner',
        string='Fournisseur',
        domain="[('supplier_rank', '>', 0)]"
    )
    
    lot_ids = fields.Many2many(
        'construction.lot',
        string='Lots à traiter',
        domain="[('id', 'in', available_lot_ids)]"
    )
    
    available_lot_ids = fields.Many2many(
        'construction.lot',
        compute='_compute_available_lots',
        string='Lots disponibles'
    )

    # =================== FILTRES ===================
    
    search_term = fields.Char(
        string='Rechercher un produit',
    )
    
    category_filter_id = fields.Many2one(
        'product.category',
        string='Filtrer par catégorie'
    )
    
    available_product_ids = fields.Many2many(
        'product.product',
        compute='_compute_available_products',
        string='Produits disponibles'
    )
    
    # =================== LIGNES SÉLECTIONNÉES ===================
    
    selected_line_ids = fields.One2many(
        'construction.purchase.line',
        'wizard_id',
        string='Lignes sélectionnées'
    )
    
    # =================== TOTAUX ===================
    
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
        default=lambda self: self.env.company.currency_id
    )

    # =================== COMPUTED ===================

    @api.depends('chantier_id.lots_ids', 'partner_id')
    def _compute_available_lots(self):
        """Calcule les lots disponibles."""
        for wizard in self:
            if wizard.chantier_id:
                lots = wizard.chantier_id.lots_ids
                # Si un fournisseur est sélectionné, filtrer par sous-traitant
                if wizard.partner_id:
                    lots = lots.filtered(
                        lambda l: wizard.partner_id in l.subcontractor_ids
                    )
                wizard.available_lot_ids = lots
            else:
                wizard.available_lot_ids = self.env['construction.lot']

    @api.depends('search_term', 'category_filter_id')
    def _compute_available_products(self):
        """Calcule les produits disponibles selon les filtres."""
        for wizard in self:
            domain = [
                ('purchase_ok', '=', True),
                ('active', '=', True)
            ]
            
            if wizard.search_term:
                domain.extend([
                    '|', '|', '|',
                    ('name', 'ilike', wizard.search_term),
                    ('default_code', 'ilike', wizard.search_term),
                    ('description_purchase', 'ilike', wizard.search_term),
                    ('barcode', 'ilike', wizard.search_term)
                ])
            
            if wizard.category_filter_id:
                domain.append(('categ_id', 'child_of', wizard.category_filter_id.id))
            
            products = self.env['product.product'].search(domain, limit=100, order='name')
            wizard.available_product_ids = products

    @api.depends('selected_line_ids.quantity', 'selected_line_ids.price_unit')
    def _compute_totals(self):
        """Calcule les totaux de la sélection."""
        for wizard in self:
            lines = wizard.selected_line_ids.filtered('quantity')
            wizard.total_amount = sum(l.quantity * l.price_unit for l in lines)
            wizard.total_quantity = sum(l.quantity for l in lines)
            wizard.line_count = len(lines)

    # =================== ONCHANGE ===================

    @api.onchange('chantier_id')
    def _onchange_chantier_id(self):
        """Pré-remplir les lots du chantier."""
        if self.chantier_id:
            self.lot_ids = self.chantier_id.lots_ids

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        """Filtrer les lots selon le fournisseur."""
        if self.partner_id and self.chantier_id:
            subcontractor_lots = self.chantier_id.lots_ids.filtered(
                lambda l: self.partner_id in l.subcontractor_ids
            )
            if subcontractor_lots:
                self.lot_ids = subcontractor_lots

    # =================== ACTIONS ===================

    def action_add_product(self):
        """Ajouter un produit à la sélection."""
        product_id = self.env.context.get('product_id')
        if not product_id:
            return self._reload_wizard()
        
        if not self.lot_ids:
            raise UserError(_("Veuillez sélectionner au moins un lot."))
        
        product = self.env['product.product'].browse(product_id)
        
        # Créer la ligne
        self.env['construction.purchase.line'].create({
            'wizard_id': self.id,
            'product_id': product_id,
            'lot_id': self.lot_ids[0].id,
            'quantity': 1.0,
            'price_unit': product.standard_price or 0.0,
            'uom_id': product.uom_po_id.id or product.uom_id.id,
        })
        
        return self._reload_wizard()

    def action_confirm_selection(self):
        """Confirmer et ajouter les produits à la commande."""
        if not self.selected_line_ids.filtered('quantity'):
            raise ValidationError(_("Veuillez sélectionner au moins un produit."))
        
        if not self.purchase_order_id:
            # Créer la commande si elle n'existe pas
            if not self.partner_id:
                raise UserError(_("Veuillez sélectionner un fournisseur."))
            
            self.purchase_order_id = self.env['purchase.order'].create({
                'partner_id': self.partner_id.id,
                'chantier_id': self.chantier_id.id,
                'lot_ids': [(6, 0, self.lot_ids.ids)],
            })
        
        # Ajouter les lignes à la commande
        self._add_products_to_order()
        
        # Nettoyer
        self.selected_line_ids.unlink()
        
        return self._reload_wizard()

    def action_finalize_purchase(self):
        """Finaliser et retourner à la commande."""
        if self.selected_line_ids.filtered('quantity'):
            self.action_confirm_selection()
        
        if self.purchase_order_id:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Commande %s') % self.purchase_order_id.name,
                'res_model': 'purchase.order',
                'res_id': self.purchase_order_id.id,
                'view_mode': 'form',
            }
        else:
            return {'type': 'ir.actions.act_window_close'}

    def action_clear_selection(self):
        """Vider la sélection."""
        self.selected_line_ids.unlink()
        return self._reload_wizard()

    # =================== PRIVATE ===================

    def _add_products_to_order(self):
        """Ajouter les produits sélectionnés à la commande."""
        order = self.purchase_order_id
        sequence = self._get_next_sequence()
        
        # Organiser par lots
        lots_with_products = self.selected_line_ids.mapped('lot_id')
        for lot in lots_with_products:
            lot_lines = self.selected_line_ids.filtered(lambda l: l.lot_id == lot)
            
            # Vérifier/créer la section
            section = order.order_line.filtered(
                lambda l: l.display_type == 'line_section' and lot.name in (l.name or '')
            )
            if not section:
                self.env['purchase.order.line'].create({
                    'order_id': order.id,
                    'display_type': 'line_section',
                    'name': f"📦 {lot.name}",
                    'sequence': sequence,
                })
                sequence += 10
            
            # Ajouter les lignes
            for line in lot_lines:
                self.env['purchase.order.line'].create({
                    'order_id': order.id,
                    'product_id': line.product_id.id,
                    'product_qty': line.quantity,
                    'product_uom': line.uom_id.id,
                    'price_unit': line.price_unit,
                    'lot_id': line.lot_id.id,
                    'sequence': sequence,
                })
                sequence += 10

    def _get_next_sequence(self):
        """Retourne la prochaine séquence."""
        if self.purchase_order_id and self.purchase_order_id.order_line:
            return max(self.purchase_order_id.order_line.mapped('sequence')) + 10
        return 10

    def _reload_wizard(self):
        """Recharger le wizard."""
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }


class ConstructionPurchaseLine(models.TransientModel):
    """Ligne de produit dans le wizard d'achat."""
    
    _name = 'construction.purchase.line'
    _description = 'Ligne de produit pour commande achat'
    _order = 'sequence, id'

    wizard_id = fields.Many2one(
        'construction.purchase.wizard',
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
        required=True
    )
    
    sequence = fields.Integer(default=10)
    
    quantity = fields.Float(
        string='Quantité',
        default=1.0,
        required=True
    )
    
    uom_id = fields.Many2one(
        'uom.uom',
        string='Unité',
        required=True
    )
    
    price_unit = fields.Float(
        string='Prix unitaire',
        default=0.0
    )
    
    subtotal = fields.Float(
        string='Sous-total',
        compute='_compute_subtotal',
        store=True
    )
    
    room_location = fields.Char(string='Localisation')
    construction_notes = fields.Text(string='Notes techniques')

    @api.depends('quantity', 'price_unit')
    def _compute_subtotal(self):
        """Calcule le sous-total."""
        for line in self:
            line.subtotal = line.quantity * line.price_unit

    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Auto-remplir le prix et l'unité."""
        if self.product_id:
            self.price_unit = self.product_id.standard_price or 0.0
            self.uom_id = self.product_id.uom_po_id or self.product_id.uom_id
