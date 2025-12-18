# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class BillingCycleWizard(models.TransientModel):
    _name = 'construction.billing.cycle.wizard'
    _description = 'Wizard to configure Billing Cycle'

    chantier_id = fields.Many2one('construction.chantier', string="Chantier", required=True)
    cycle_type = fields.Selection([
        ('standard', 'Standard (30/30/40)'),
        ('progress', 'Avancement (Progress)'),
        ('custom', 'Custom')
    ], string="Cycle Type", default='standard', required=True)
    
    currency_id = fields.Many2one(related='chantier_id.currency_id')
    total_amount = fields.Monetary(related='chantier_id.total_cost', string="Total Chantier Estimation")

    def action_apply_cycle(self):
        self.ensure_one()
        
        # Create Cycle
        cycle_vals = {
            'chantier_id': self.chantier_id.id,
            'name': dict(self._fields['cycle_type'].selection).get(self.cycle_type),
        }
        cycle = self.env['construction.billing.cycle'].create(cycle_vals)
        
        # Link cycle to chantier
        self.chantier_id.billing_cycle_id = cycle.id
        
        # Generate Steps
        if self.cycle_type == 'standard':
            self._create_standard_steps(cycle)
        elif self.cycle_type == 'progress':
            self._create_progress_steps(cycle)
        
        # Return action to view the cycle or chantier
        return {
            'type': 'ir.actions.act_window_close', 
            # Ideally verify triggers a reload
        }

    def _create_standard_steps(self, cycle):
        """30% Order, 30% Intermediate, 40% Final"""
        steps = [
            (1, _("Acompte Commande"), 30.0),
            (2, _("Situation Intermédiaire"), 30.0),
            (3, _("Solde Réception"), 40.0),
        ]
        
        for sequence, name, pct in steps:
            self.env['construction.billing.step'].create({
                'cycle_id': cycle.id,
                'name': name,
                'sequence': sequence,
                'percentage': pct,
            })

    def _create_progress_steps(self, cycle):
        """Create empty steps for monthly progress billing, initial setup"""
        # For progress, we might just create one open step or just set the mode
        # Let's create a starting step
        self.env['construction.billing.step'].create({
            'cycle_id': cycle.id,
            'name': _("Première Situation"),
            'sequence': 1,
            'percentage': 0.0, # Manual
        })
