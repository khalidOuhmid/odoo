# -*- coding: utf-8 -*-

from odoo import models, api, _
from odoo.exceptions import UserError
from odoo.tools import float_round

class InvoiceService(models.AbstractModel):
    _name = 'construction.invoice.service'
    _description = 'Service de Facturation Construction'

    def compute_schedule_amount(self, schedule) -> float:
        """
        Compute the amount for a schedule with strict rounding.
        Bulwark against monetary errors.
        """
        if not schedule.quote_id and not schedule.chantier_id.total_cost:
            return 0.0

        base_amount = 0.0
        
        if schedule.quote_id and schedule.lot_ids:
            # Calculate based on specific lots in quote
            # Note: Logic simplified for robustness - sum matching lines
            # In a real scenario, we might need the complex line matching from legacy
            # but here we prioritize correctness over implicit string matching if possible.
            # Using the simplified fallback logic from legacy as primary for now:
            
            # 1. Try to find lines linked to these lots (if explicit link exists)
            # Need strict float handling
            total_lot_price = 0.0
             # Implementation choice: If lot.price_from_quote is populated, use it.
            for lot in schedule.lot_ids:
                 total_lot_price += lot.price_from_quote or 0.0
            
            if total_lot_price > 0:
                 base_amount = total_lot_price
            else:
                 # Fallback: Proportional
                 base_amount = schedule.quote_id.amount_total
        
        elif schedule.quote_id:
             base_amount = schedule.quote_id.amount_total
        else:
             base_amount = schedule.chantier_id.total_cost

        # Apply Margin
        if schedule.margin_percentage:
            factor = 1.0 - (schedule.margin_percentage / 100.0)
            base_amount = base_amount * factor

        # Apply Schedule Percentage
        amount = base_amount * (schedule.amount_percentage / 100.0)
        
        # Strict Rounding
        return float_round(amount, precision_digits=2)

    def create_invoice(self, schedule) -> dict:
        """
        Create Invoice from Schedule.
        """
        if not schedule.chantier_id.client:
             raise UserError(_("Le chantier n'a pas de client."))
             
        invoice_vals = {
            'move_type': 'out_invoice',
            'partner_id': schedule.chantier_id.client.id,
            'invoice_date': fields.Date.today(),
            'chantier_id': schedule.chantier_id.id, # Link back to Chantier if field exists on move
            'invoice_line_ids': [
                (0, 0, {
                    'name': f"{schedule.name} - {schedule.chantier_id.name}",
                    'quantity': 1,
                    'price_unit': schedule.amount_fixed,
                })
            ]
        }
        
        move = self.env['account.move'].create(invoice_vals)
        schedule.write({'state': 'invoiced', 'invoice_id': move.id})
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': move.id,
            'view_mode': 'form',
        }
