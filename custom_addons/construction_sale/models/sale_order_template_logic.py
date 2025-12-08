# -*- coding: utf-8 -*-
from odoo import models, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _compute_line_data_for_template_change(self, line):
        """
        Override to inject construction data from template line to order line.
        """
        data = super()._compute_line_data_for_template_change(line)
        
        # 1. Dimensions
        if line.is_dimensional:
            data.update({
                'dimension_length': line.dimension_length,
                'dimension_width': line.dimension_width,
                'is_dimensional': True,
                # Recalculate Qty
                'product_uom_qty': (line.dimension_length or 1) * (line.dimension_width or 1)
            })
            
        # 2. Lot / Section Logic
        # If the template line specifies a "Lot Name", we needs to find/create that section
        # and link the line to it. 
        # However, standard Odoo template expansion is linear.
        # If we want to group by Lot, we might need to intercept the creation.
        
        # For now, we simply pass the data. The "Grouping" action can be run later.
        # But we don't have a 'lot_name' field on sale.order.line, we have 'construction_lot_id'.
        # We need to find a construction.lot that matches 'chantier_id' + 'lot_name'.
        
        if line.construction_lot_name and self.chantier_id:
            # Try to find a lot with this name in the current chantier
            found_lot = self.env['construction.lot'].search([
                ('chantier_id', '=', self.chantier_id.id),
                ('name', 'ilike', line.construction_lot_name)
            ], limit=1)
            
            if found_lot:
                data['construction_lot_id'] = found_lot.id
            else:
                # Optional: Auto-create lot? 
                # Maybe safer to just log warning or leave empty.
                pass
                
        return data
