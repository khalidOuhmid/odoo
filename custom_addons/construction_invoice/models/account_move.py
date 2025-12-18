# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class AccountMove(models.Model):
    _inherit = 'account.move'

    chantier_id = fields.Many2one('construction.chantier', string="Chantier Linked")

    def action_post(self):
        """Override to trigger commission calculation on Client Invoice validation."""
        res = super(AccountMove, self).action_post()
        
        for move in self:
            if move.move_type in ['out_invoice', 'out_refund'] and move.chantier_id and move.chantier_id.business_provider_id:
                self._generate_business_provider_commission(move)
        
        return res

    def _generate_business_provider_commission(self, invoice):
        """Generate a Vendor Bill (Draft) or Refund for the Business Provider."""
        chantier = invoice.chantier_id
        provider = chantier.business_provider_id
        
        is_refund = invoice.move_type == 'out_refund'
        
        # Calculate Commission Amount
        commission_amount = 0.0
        if chantier.commission_type == 'percentage':
            commission_amount = invoice.amount_untaxed * (chantier.commission_value / 100.0)
        elif chantier.commission_type == 'fixed':
            # Pro-rata calculation
            total_sales = chantier.total_cost or 1.0 
            ratio = invoice.amount_untaxed / total_sales
            commission_amount = chantier.commission_value * ratio
            
        if commission_amount <= 0:
            return

        # Create Vendor Bill or Refund
        commission_vals = {
            'move_type': 'in_refund' if is_refund else 'in_invoice', # Reverse for provider
            'partner_id': provider.id,
            'invoice_date': fields.Date.today(),
            'ref': _("Commission %s sur %s") % ('(Avoir)' if is_refund else '', invoice.name),
            'invoice_origin': invoice.name,
            'chantier_id': chantier.id,
            'invoice_line_ids': [(0, 0, {
                'name': _("Commission - %s") % invoice.name,
                'quantity': 1,
                'price_unit': commission_amount,
                'tax_ids': [(6, 0, [])], 
            })]
        }
        
        self.env['account.move'].create(commission_vals)
