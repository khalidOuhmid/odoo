# -*- coding: utf-8 -*-
"""Extension du modèle construction.lot pour les achats."""

from odoo import api, fields, models, _


class LotPurchaseExtension(models.Model):
    """Extension pour ajouter les fonctionnalités d'achat aux lots."""
    
    _inherit = 'construction.lot'

    # =================== COMPUTED FIELDS ===================
    # Note: We do NOT use One2many here because the inverse field 'lot_id'
    # on 'purchase.order.line' is defined in the same module and may not be 
    # registered at the time Odoo sets up the One2many field.
    
    purchase_count = fields.Integer(
        string='Nombre de commandes',
        compute='_compute_purchase_stats'
    )
    
    purchase_total = fields.Monetary(
        string='Total Achats',
        compute='_compute_purchase_stats',
        currency_field='currency_id'
    )
    
    purchase_margin = fields.Monetary(
        string='Marge',
        compute='_compute_purchase_stats',
        currency_field='currency_id',
        help="Prix de vente - Achats"
    )
    
    purchase_margin_percent = fields.Float(
        string='Marge (%)',
        compute='_compute_purchase_stats'
    )

    def _compute_purchase_stats(self):
        """Calcule les statistiques d'achat du lot.
        
        Uses direct search to avoid dependency on One2many field.
        """
        PurchaseOrderLine = self.env['purchase.order.line']
        PurchaseOrder = self.env['purchase.order']
        
        for record in self:
            # Search for purchase order lines linked to this lot
            all_lines = PurchaseOrderLine.search([('lot_id', '=', record.id)])
            confirmed_lines = all_lines.filtered(
                lambda l: l.order_id.state in ['purchase', 'done']
            )
            
            # Search for purchase orders that have this lot in their lot_ids
            orders = PurchaseOrder.search([('lot_ids', 'in', [record.id])])
            
            record.purchase_count = len(orders)
            record.purchase_total = sum(confirmed_lines.mapped('price_subtotal'))
            
            # Marge = Prix vente - Achats
            if record.price:
                record.purchase_margin = record.price - record.purchase_total
                record.purchase_margin_percent = (
                    (record.purchase_margin / record.price * 100) if record.price else 0
                )
            else:
                record.purchase_margin = 0
                record.purchase_margin_percent = 0

    # =================== HELPER METHODS ===================

    def _get_purchase_lines(self):
        """Helper method to get purchase order lines for this lot."""
        self.ensure_one()
        return self.env['purchase.order.line'].search([('lot_id', '=', self.id)])

    def _get_purchase_orders(self):
        """Helper method to get purchase orders for this lot."""
        self.ensure_one()
        return self.env['purchase.order'].search([('lot_ids', 'in', [self.id])])

    # =================== ACTIONS ===================

    def action_view_purchase_orders(self):
        """Smart button: Voir les commandes fournisseur du lot."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Commandes - %s') % self.name,
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('lot_ids', 'in', [self.id])],
            'context': {
                'default_chantier_id': self.chantier_id.id if self.chantier_id else False,
                'default_lot_ids': [(6, 0, [self.id])],
            },
        }

    def action_create_purchase_order(self):
        """Créer une commande fournisseur pour ce lot."""
        self.ensure_one()
        
        if not self.subcontractor_ids:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Attention'),
                    'message': _('Aucun sous-traitant assigné à ce lot.'),
                    'type': 'warning'
                }
            }
        
        # Créer la commande avec le premier sous-traitant
        subcontractor = self.subcontractor_ids[0]
        order = self.env['purchase.order'].create({
            'partner_id': subcontractor.id,
            'chantier_id': self.chantier_id.id if self.chantier_id else False,
            'lot_ids': [(6, 0, [self.id])],
        })
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Commande Fournisseur'),
            'res_model': 'purchase.order',
            'res_id': order.id,
            'view_mode': 'form',
        }
