# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)

class ConstructionQuoteWizard(models.TransientModel):
    _name = 'construction.quote.wizard'
    _description = 'Assistant to add construction items by Lot'

    sale_order_id = fields.Many2one('sale.order', required=True)
    chantier_id = fields.Many2one('construction.chantier', readonly=True)
    
    # User selects which Lot they are working on RIGHT NOW
    target_lot_id = fields.Many2one(
        'construction.lot', 
        string='Target Lot',
        domain="[('chantier_id', '=', chantier_id)]",
        required=True
    )
    
    

    def action_add_lines(self):
        """ Add lines and close """
        self._add_lines_logic()
        return {'type': 'ir.actions.act_window_close'}
        
    def action_add_and_keep_open(self):
        """ Add lines, Save, and Keep Wizard Open (Prevent data loss) """
        self._add_lines_logic()
        
        # Clear lines after adding so user can add more or switch lot
        self.line_ids.unlink()
        
        # Notify user (Toast)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Items Added'),
                'message': _('Items have been added to the quote. You can continue.'),
                'type': 'success',
                'sticky': False,
            }
        }
        # We return a reload or just keep open. 
        # In Odoo wizard 'target=new', returning a notification USUALLY keeps it open unless we return act_window_close
        # But to be safe, we can return the action of the wizard itself again (re-open) if needed.
        # However, a simple notification usually allows staying in the modal if it doesn't return 'close'.
        # Let's try returning the action to reload the view, ensuring 'line_ids' is visually cleared.
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'construction.quote.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _add_lines_logic(self):
        self.ensure_one()
        _logger.info("Wizard: Adding %s lines to Quote %s for Lot %s", len(self.line_ids), self.sale_order_id.id, self.target_lot_id.name)
        
        SaleLine = self.env['sale.order.line']
        order = self.sale_order_id
        
        # 1. Find or Create Section for this Lot
        section_name = f"Lot: {self.target_lot_id.name}"
        section = order.order_line.filtered(lambda l: l.display_type == 'line_section' and l.name == section_name)
        
        sequence_start = 1000 # Default fallback
        
        if not section:
            # Create Config Section
            last_line = order.order_line[-1] if order.order_line else False
            new_seq = (last_line.sequence + 10) if last_line else 10
            
            section = SaleLine.create({
                'order_id': order.id,
                'display_type': 'line_section',
                'name': section_name,
                'sequence': new_seq
            })
            sequence_start = new_seq + 1
        else:
            sequence_start = section[0].sequence + 1
            
            # Find the next section to insert before it
            next_sections = order.order_line.filtered(lambda l: l.display_type == 'line_section' and l.sequence > section[0].sequence)
            
            # If we are inserting into an existing block, we might need to resequence, 
            # but for now we just append to the end of that block.
            # A simple heuristic: take the sequence of the last item in that block + 1
            
            block_lines = order.order_line.filtered(lambda l: l.sequence >= sequence_start and (not next_sections or l.sequence < min(next_sections.mapped('sequence'))))
            if block_lines:
                sequence_start = max(block_lines.mapped('sequence')) + 1

        # 2. Create Items
        current_seq = sequence_start
        for line in self.line_ids:
            # Calculate Qty on the fly if dimensions used
            qty = line.quantity
            if line.length or line.width:
                l = line.length or 1.0
                w = line.width or 1.0
                qty = l * w # Default to Area logic for wizard speed
            
            SaleLine.create({
                'order_id': order.id,
                'product_id': line.product_id.id,
                'name': line.description or line.product_id.get_product_multiline_description_sale(),
                'product_uom_qty': qty,
                'construction_lot_id': self.target_lot_id.id,
                'sequence': current_seq,
                'dimension_length': line.length,
                'dimension_width': line.width,
                'is_dimensional': True if (line.length or line.width) else False
            })
            current_seq += 1

class ConstructionQuoteWizardLine(models.TransientModel):
    _name = 'construction.quote.wizard.line'
    _description = 'Line for Construction Wizard'

    wizard_id = fields.Many2one('construction.quote.wizard')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    description = fields.Char(string='Description')
    
    # Simplified Dimension Inputs
    length = fields.Float(string='L (m)')
    width = fields.Float(string='W (m)')
    quantity = fields.Float(string='Qty', default=1.0)
