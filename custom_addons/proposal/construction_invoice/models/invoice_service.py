# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ConstructionInvoiceService(models.AbstractModel):
    _name = "construction.invoice.service"
    _description = "Service for generating Situation Invoices"

    def create_situation_invoice(self, schedule_item):
        """
        Creates a Customer Invoice (account.move) based on the Schedule Item.
        """
        quote = schedule_item.quote_id
        if not quote:
            raise UserError(_("No Quote linked to this billing schedule."))

        # 1. Prepare Invoice Lines
        # We create a single line description for the progress billing "Situation N..."
        # Or detailed lines? Usually sitution invoices are "Situation No X: 30% of Quote Ref..."
        
        product = self.env.ref('construction_invoice.product_situation', raise_if_not_found=False)
        if not product:
            # Create a default service product for billing if not exists
            product = self.env['product.product'].create({
                'name': 'Situation / Avancement',
                'type': 'service',
                'taxes_id': [(5, 0, 0)], # No tax by default, will copy from quote? No, complex taxes. 
                # Better to copy tax from quote lines? 
                # Simplified approach: Apply main tax from quote representative line
            })
            # Self-reference for future
            self.env['ir.model.data'].create({
                'module': 'construction_invoice',
                'name': 'product_situation',
                'model': 'product.product',
                'res_id': product.id
            })

        # Calculate taxes (taking first tax from order line for simplicity - Refinement needed for multi-tax)
        tax_ids = quote.order_line[0].tax_id.ids if quote.order_line else []
        
        invoice_lines = [{
            'name': f"{schedule_item.name} - Ref: {quote.name}",
            'product_id': product.id,
            'quantity': 1,
            'price_unit': schedule_item.amount_to_bill,
            'tax_ids': [(6, 0, tax_ids)],
        }]

        # 2. Create Invoice
        journal = self.env['account.journal'].search([('type', '=', 'sale'), ('company_id', '=', quote.company_id.id)], limit=1)
        if not journal:
             raise UserError(_("No Sales Journal found for this company."))

        invoice_vals = {
            'move_type': 'out_invoice',
            'partner_id': quote.partner_id.id,
            'partner_shipping_id': quote.partner_shipping_id.id,
            'currency_id': quote.currency_id.id,
            'invoice_origin': f"{quote.name} - {schedule_item.name}",
            'invoice_user_id': quote.user_id.id,
            'journal_id': journal.id,
            'invoice_line_ids': [(0, 0, line) for line in invoice_lines],
            'chantier_id': schedule_item.chantier_id.id, # Link invoice to Chantier if field exists on Move
        }
        
        # Check if account.move has chantier_id (it should if we extend it, let's assume we do or will)
        # For now, just create
        invoice = self.env['account.move'].create(invoice_vals)
        
        return invoice
