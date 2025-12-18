# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.tools import float_round

class BillingStep(models.Model):
    _name = 'construction.billing.step'
    _description = 'Construction Billing Step'
    _order = 'sequence, id'

    cycle_id = fields.Many2one('construction.billing.cycle', string="Cycle", required=True, ondelete='cascade')
    name = fields.Char(string="Description", required=True)
    sequence = fields.Integer(default=10)
    
    percentage = fields.Float(string="Percentage (%)", digits=(16, 2))
    amount = fields.Monetary(string="Amount", currency_field='currency_id', compute='_compute_amount', store=True, readonly=False)
    
    currency_id = fields.Many2one(related='cycle_id.currency_id')
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('invoiced', 'Invoiced'),
        ('paid', 'Paid')
    ], default='draft', string="Status")
    
    invoice_id = fields.Many2one('account.move', string="Invoice", readonly=True)

    @api.model
    def create(self, vals):
        step = super(BillingStep, self).create(vals)
        # Audit Requirement: Strict Blocking Error if > 100%
        # We check the cycle total after adding this step
        if step.cycle_id:
             # Recompute total
             total_pct = sum(step.cycle_id.step_ids.mapped('percentage'))
             if total_pct > 100.001: # Small float tolerance
                 raise ValidationError(_("BLOCKING ERROR: The billing cycle cannot exceed 100% (Current: %.2f%%)") % total_pct)
        return step
    def _compute_amount(self):
        for step in self:
            if step.percentage:
                amount = step.cycle_id.total_amount_confirmed * (step.percentage / 100.0)
                step.amount = float_round(amount, precision_digits=2)
            # If percentage is 0, we allow manual amount entry, so we don't overwrite if not computed

    def action_create_invoice(self):
        """Generate a draft invoice for this billing step."""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_("This step is already invoiced."))
        
        chantier = self.cycle_id.chantier_id
        if not chantier.client:
            raise UserError(_("No client defined on the project."))
            
        # SMART ROUNDING LOGIC (Audit Requirement)
        # If this is the LAST step (by sequence), we must bill the REMAINING balance
        # to ensure we match the total confirmed amount exactly (no penny errors).
        
        # Check if last step
        other_draft_steps = self.cycle_id.step_ids.filtered(lambda s: s.state == 'draft' and s.id != self.id)
        is_last_step = len(other_draft_steps) == 0
        
        amount_to_invoice = self.amount
        
        if is_last_step:
            total_confirmed = self.cycle_id.total_amount_confirmed
            total_invoiced = sum(self.cycle_id.step_ids.mapped('invoice_id.amount_untaxed'))
            remaining = total_confirmed - total_invoiced
            
            # If the calculated amount is close to remaining (within rounding), use remaining
            # Or always use remaining if it's the last step?
            # Safer: Use remaining, but warn if deviation is huge.
            # Audit Requirement: "Reste à facturer sur la dernière facture pour tomber juste"
            amount_to_invoice = remaining
        
        # Create Invoice
        invoice_vals = {
            'move_type': 'out_invoice',
            'partner_id': chantier.client.id,
            'invoice_date': fields.Date.today(),
            'chantier_id': chantier.id,
            'invoice_origin': _("Cycle %s - %s") % (self.cycle_id.name, self.name),
            'narration': _("Facturation Étape: %s") % self.name,
            'invoice_line_ids': [(0, 0, {
                'name': _("Avancement Chantier - %s") % self.name,
                'quantity': 1,
                'price_unit': amount_to_invoice,
                'tax_ids': [(6, 0, [])], 
            })]
        }
        
        invoice = self.env['account.move'].create(invoice_vals)
        
        self.write({
            'state': 'invoiced',
            'invoice_id': invoice.id
        })
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Facture Brouillon'),
            'res_model': 'account.move',
            'res_id': invoice.id,
            'view_mode': 'form',
            'target': 'current',
        }
