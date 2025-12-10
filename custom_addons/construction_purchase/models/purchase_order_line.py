# -*- coding: utf-8 -*-
"""
Extension du modèle purchase.order.line pour la construction.
"""

from odoo import api, fields, models, _


class PurchaseOrderLineConstruction(models.Model):
    """Extension des lignes de commande achat pour la construction."""
    
    _inherit = 'purchase.order.line'

    # =================== CHAMPS CONSTRUCTION ===================
    
    lot_id = fields.Many2one(
        'construction.lot',
        string='Lot',
        help="Lot de construction pour cette ligne"
    )
    
    room_location = fields.Char(
        string='Localisation',
        help="Ex: Salon, Cuisine, Chambre 1, etc."
    )
    
    floor_level = fields.Selection([
        ('basement', 'Sous-sol'),
        ('ground', 'Rez-de-chaussée'),
        ('floor_1', 'Étage 1'),
        ('floor_2', 'Étage 2'),
        ('floor_3', 'Étage 3'),
        ('attic', 'Combles'),
    ], string='Niveau')
    
    construction_notes = fields.Text(
        string='Notes techniques',
        help="Commentaires ou spécifications techniques"
    )
    
    # =================== CHAMPS CALCULÉS ===================
    
    chantier_id = fields.Many2one(
        related='order_id.chantier_id',
        store=True,
        string='Chantier'
    )
    
    sale_price = fields.Float(
        string='Prix de vente',
        compute='_compute_sale_price',
        help="Prix de vente estimé du lot (pour calcul marge)"
    )
    
    line_margin = fields.Float(
        string='Marge ligne',
        compute='_compute_line_margin',
        help="Marge estimée pour cette ligne"
    )

    @api.depends('lot_id', 'lot_id.price', 'product_qty')
    def _compute_sale_price(self):
        """Calcule le prix de vente estimé basé sur le lot."""
        for line in self:
            if line.lot_id and line.lot_id.price:
                # Répartir le prix du lot sur la quantité
                line.sale_price = line.lot_id.price
            else:
                line.sale_price = 0

    @api.depends('price_subtotal', 'sale_price')
    def _compute_line_margin(self):
        """Calcule la marge de la ligne."""
        for line in self:
            line.line_margin = line.sale_price - line.price_subtotal if line.sale_price else 0

    @api.onchange('lot_id')
    def _onchange_lot_id(self):
        """Auto-compléter les informations du lot."""
        if self.lot_id:
            # Si le produit n'est pas défini, suggérer un produit générique
            if not self.product_id:
                self.name = f"[{self.lot_id.code}] {self.lot_id.name}"
