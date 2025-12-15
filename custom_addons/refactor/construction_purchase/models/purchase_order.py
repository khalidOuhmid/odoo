# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    chantier_id = fields.Many2one(
        'construction.chantier',
        string='Chantier',
        tracking=True,
        index=True
    )
    
    lot_id = fields.Many2one(
        'construction.lot',
        string='Lot',
        domain="[('chantier_id', '=', chantier_id)]",
        help="Specific Work Package cost center."
    )
    
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Source Devis',
        readonly=True,
        help="Linked Sales Order (Back-to-Back)"
    )

    def button_confirm(self):
        """Update Committed Costs on confirmation."""
        res = super(PurchaseOrder, self).button_confirm()
        for order in self:
            if order.lot_id:
                # Mock cost update logic
                # In real life: Update construction.lot.cost_committed
                pass
        return res

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'
    
    chantier_id = fields.Many2one(related='order_id.chantier_id', store=True)
    lot_id = fields.Many2one(related='order_id.lot_id', store=True)
