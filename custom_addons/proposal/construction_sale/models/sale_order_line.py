# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # Link each line to a specific lot (for financial analysis later)
    construction_lot_id = fields.Many2one(
        'construction.lot', 
        string='Work Package',
        domain="[('chantier_id', '=', parent.chantier_id)]"
    )

    # ==========================
    # DIMENSIONS & PRICING
    # ==========================
    # We port the "Dimensions" logic for m2/ml calculations
    # This allows typing "Length: 5, Width: 4" -> Qty: 20
    
    dimension_length = fields.Float(string='Length (m)', default=0.0)
    dimension_width = fields.Float(string='Width (m)', default=0.0)
    dimension_height = fields.Float(string='Height/Depth (m)', default=0.0)
    
    # Helper to calculate quantity automatically
    is_dimensional = fields.Boolean(string="Use Dimensions", default=False)

    @api.onchange('dimension_length', 'dimension_width', 'dimension_height', 'is_dimensional')
    def _onchange_dimensions(self):
        if not self.is_dimensional:
            return
            
        qty = 0.0
        # Logic: 
        # If just Length -> Linear Meters
        # If Length * Width -> Area (m2)
        # If Length * Width * Height -> Volume (m3)
        
        l = self.dimension_length or 1.0
        w = self.dimension_width or 1.0
        h = self.dimension_height or 1.0
        
        if self.dimension_length and not self.dimension_width and not self.dimension_height:
             qty = self.dimension_length
        elif self.dimension_length and self.dimension_width and not self.dimension_height:
             qty = self.dimension_length * self.dimension_width
        elif self.dimension_length and self.dimension_width and self.dimension_height:
             qty = self.dimension_length * self.dimension_width * self.dimension_height
             
        if qty > 0:
            self.product_uom_qty = qty
