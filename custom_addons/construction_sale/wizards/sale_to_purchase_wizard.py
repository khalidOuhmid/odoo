# -*- coding: utf-8 -*-
"""
Sale to Purchase Wizard
========================
Automated Purchase Order generation from Sales Quotes.
Groups products by Technical Lot and assigns to Subcontractors.
Uses line-level price_buy (cost) for PO pricing.
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from typing import Any
import logging

_logger = logging.getLogger(__name__)


class SaleToPurchaseWizard(models.TransientModel):
    """Wizard to automate PO creation from Sales Quotes.
    
    Business Logic:
    1. Groups sale order lines by their assigned Technical Lot
    2. For each lot, creates a Purchase Order assigned to the lot's subcontractor
    3. Uses line-level price_buy (cost) for PO pricing - NOT selling price
    4. Preserves traceability via origin field
    """
    _name = 'construction.sale.to.purchase.wizard'
    _description = 'Generate Purchase Orders from Quote'

    sale_order_id = fields.Many2one(
        'sale.order', 
        string="Source Quote", 
        required=True, 
        readonly=True
    )
    
    lot_id = fields.Many2one(
        'construction.lot',
        string="Lot to Process",
        help="Optional: Select a specific lot. Leave empty to process all lots."
    )
    
    vendor_id = fields.Many2one(
        'res.partner',
        string="Override Vendor",
        domain="[('supplier_rank', '>', 0)]",
        help="Optional: Override the lot's default subcontractor with a specific vendor."
    )

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        if self.env.context.get('active_id'):
            res['sale_order_id'] = self.env.context.get('active_id')
        return res
    
    @api.onchange('sale_order_id')
    def _onchange_sale_order_id(self):
        """Filter lot_id domain to only lots present in the quote."""
        if self.sale_order_id:
            lot_ids = self.sale_order_id.order_line.filtered(lambda l: l.lot_id).mapped('lot_id').ids
            return {'domain': {'lot_id': [('id', 'in', lot_ids)]}}
        return {}

    def action_generate_orders(self) -> dict:
        """Generate Purchase Orders grouped by Technical Lot.
        
        Business Logic:
        1. Validates that quote is linked to a construction site
        2. Groups all product lines by their assigned lot (or single lot if specified)
        3. For each lot, creates a PO with the vendor (override or lot's subcontractor)
        4. CRITICAL: Uses line.price_buy (cost) for PO price, NOT selling price
        5. Returns action to display generated POs
        
        Returns:
            Action dictionary to open tree view of generated POs
            
        Raises:
            UserError: If quote not linked to site or no lots assigned
        """
        self.ensure_one()
        order = self.sale_order_id
        
        if not order.chantier_id:
            raise UserError(_("This quote is not linked to a Construction Site (Chantier)."))

        generated_orders = self.env['purchase.order']
        lines_by_lot = {}

        # 1. Filter and Group Lines
        product_lines = order.order_line.filtered(
            lambda l: not l.display_type and l.lot_id and l.product_id.type != 'service'
        )
        
        # If specific lot selected, filter further
        if self.lot_id:
            product_lines = product_lines.filtered(lambda l: l.lot_id == self.lot_id)
        
        for line in product_lines:
            if line.lot_id not in lines_by_lot:
                lines_by_lot[line.lot_id] = self.env['sale.order.line']
            lines_by_lot[line.lot_id] |= line
            
        if not lines_by_lot:
            raise UserError(_("No products found with assigned Lots. Please ensure lines have a 'Technical Lot' set."))

        # 2. Create POs
        for lot, lines in lines_by_lot.items():
            # Vendor priority: Wizard override > Lot's subcontractor
            vendor = self.vendor_id or lot.subcontractor_ids[:1]
            
            if not vendor:
                _logger.warning(f"Lot {lot.name} has no subcontractor and no override vendor. Skipping PO generation.")
                continue

            # Create Header
            po_vals = {
                'partner_id': vendor.id,
                'chantier_id': order.chantier_id.id,
                'origin': f"{order.name} (Lot {lot.code})",
                'lot_ids': [(4, lot.id)],
                'date_order': fields.Datetime.now(),
            }
            po = self.env['purchase.order'].create(po_vals)
            generated_orders |= po

            # Create Lines - CRITICAL: Use price_buy (cost), not price_unit (selling)
            for sale_line in lines:
                # Get cost from line-level price_buy, fallback to product standard_price
                cost_price = sale_line.price_buy or sale_line.product_id.standard_price or 0.0
                
                line_vals = {
                    'order_id': po.id,
                    'product_id': sale_line.product_id.id,
                    'name': sale_line.name + (f"\nLocation: {sale_line.room_location}" if sale_line.room_location else ""),
                    'product_qty': sale_line.product_uom_qty or 1.0,  # FIX: Mandatory field
                    'price_unit': cost_price,  # COST, not selling price!
                    'date_planned': fields.Datetime.now(),
                    'product_uom': sale_line.product_uom.id,
                }
                self.env['purchase.order.line'].create(line_vals)

        if not generated_orders:
            raise UserError(_("No Purchase Orders were created. Check if Lots have Subcontractors assigned or specify an override vendor."))

        # 3. Success notification
        po_names = ', '.join(generated_orders.mapped('name'))
        
        # 4. Open Result
        return {
            'name': _('Generated Purchase Orders'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', generated_orders.ids)],
            'context': {'create': False},
        }
