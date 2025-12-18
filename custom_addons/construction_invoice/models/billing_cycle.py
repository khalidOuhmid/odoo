from odoo import models, fields, api, _
from odoo.tools import float_compare

class BillingCycle(models.Model):
    _name = 'construction.billing.cycle'
    _description = 'Construction Billing Cycle'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Reference", required=True, copy=False, default=lambda self: _('New'))
    chantier_id = fields.Many2one('construction.chantier', string="Construction Site", required=True, ondelete='cascade')
    
    step_ids = fields.One2many('construction.billing.step', 'cycle_id', string="Billing Steps")
    
    total_amount_confirmed = fields.Monetary(
        string="Total Confirmed Amount",
        compute='_compute_total_amount_confirmed',
        store=True,
        currency_field='currency_id',
        help="Total amount of all confirmed Sales Orders linked to this project"
    )
    
    currency_id = fields.Many2one(related='chantier_id.currency_id')
    
    billing_status = fields.Selection([
        ('under_billed', 'Under Billed'),
        ('balanced', 'Balanced (100%)'),
        ('over_billed', 'Over Billed')
    ], compute='_compute_billing_status', store=True, string="Billing Status")

    @api.depends('chantier_id.quotation_ids.state', 'chantier_id.quotation_ids.amount_total', 'chantier_id.total_cost')
    def _compute_total_amount_confirmed(self):
        """
        Compute total confirmed amount from validated sale orders.
        Falls back to chantier.total_cost if no confirmed orders.
        """
        for cycle in self:
            if cycle.chantier_id:
                confirmed_orders = cycle.chantier_id.quotation_ids.filtered(
                    lambda q: q.state in ['sale', 'done']
                )
                if confirmed_orders:
                    cycle.total_amount_confirmed = sum(confirmed_orders.mapped('amount_total'))
                else:
                    # Fallback to chantier total_cost
                    cycle.total_amount_confirmed = cycle.chantier_id.total_cost or 0.0
            else:
                cycle.total_amount_confirmed = 0.0

    @api.depends('step_ids.amount', 'total_amount_confirmed')
    def _compute_billing_status(self):
        for cycle in self:
            total_planned = sum(cycle.step_ids.mapped('amount'))
            if float_compare(total_planned, cycle.total_amount_confirmed, precision_digits=2) > 0:
                cycle.billing_status = 'over_billed'
            elif float_compare(total_planned, cycle.total_amount_confirmed, precision_digits=2) == 0:
                cycle.billing_status = 'balanced'
            else:
                cycle.billing_status = 'under_billed'

    @api.constrains('step_ids', 'total_amount_confirmed')
    def _check_over_billing(self):
        """Warn if over-billed (Non-blocking as per user request)."""
        for cycle in self:
            total_planned = sum(cycle.step_ids.mapped('amount'))
            if float_compare(total_planned, cycle.total_amount_confirmed, precision_digits=2) > 0:
                # We can't easily show a "Warning" dialog from a constraint in Odoo (it raises ValidationError).
                # But the user asked for a "Warning" and "Manual override".
                # A common pattern is to allow it but flag it big.
                # Since we have 'billing_status' = 'over_billed', the UI can show a banner.
                # We will Log a warning here instead of raising, or relying on the computed field to trigger UI alerts.
                # If we want to strictly WARN (user sees popup but can proceed), we need to do it in the wizard or on write/create,
                # but models constraints are usually strict.
                # Given "enable the facts that it can be manual changed but with bigs warnings",
                # I will rely on the `billing_status` field to show a BIG RED ALERT in the View.
                pass 

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('construction.billing.cycle') or _('New')
        return super(BillingCycle, self).create(vals)
