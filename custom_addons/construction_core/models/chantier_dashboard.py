# -*- coding: utf-8 -*-
"""
Construction Site (Chantier) Model - Dashboard Extensions
Additional computed fields for the advanced dashboard views.
"""

from odoo import models, fields, api

class ChantierDashboard(models.Model):
    _inherit = 'construction.chantier'

    # ============= Dashboard Computed Fields ============= #
    currency_id = fields.Many2one('res.currency', string='Devise', default=lambda self: self.env.company.currency_id)
    total_cost = fields.Monetary(string='Coût Total', currency_field='currency_id', compute='_compute_total_cost', store=True)
    
    days_remaining = fields.Integer(string='Jours Restants', compute='_compute_days_remaining', store=True)
    deadline_status = fields.Selection([
        ('on_time', 'À Temps'),
        ('warning', 'Attention'),
        ('critical', 'Critique'),
        ('overdue', 'En Retard')
    ], string='Statut Échéance', compute='_compute_deadline_status')
    deadline_color = fields.Integer(compute='_compute_deadline_status')

    # Visibility fields for contextual actions (legacy compatibility)
    show_schedule_visit = fields.Boolean(compute='_compute_action_visibility')
    show_create_quote = fields.Boolean(compute='_compute_action_visibility')
    show_assign_subcontractors = fields.Boolean(compute='_compute_action_visibility')
    show_mark_not_pursued = fields.Boolean(compute='_compute_action_visibility')

    # ============= Computes ============= #
    @api.depends('lots_ids.price')
    def _compute_total_cost(self):
        """Calculate total cost from lots."""
        for record in self:
            record.total_cost = sum(record.lots_ids.mapped('price'))

    @api.depends('date_end_contract', 'state')
    def _compute_days_remaining(self):
        """Calculate days remaining until contract end date."""
        today = fields.Date.today()
        for record in self:
            if record.date_end_contract and record.state == 'active':
                delta = record.date_end_contract - today
                record.days_remaining = delta.days
            else:
                record.days_remaining = 0

    @api.depends('days_remaining', 'date_end_contract')
    def _compute_deadline_status(self):
        """Compute deadline status and color for dashboard visualization."""
        for record in self:
            if not record.date_end_contract or record.state != 'active':
                record.deadline_status = 'on_time'
                record.deadline_color = 10  # Grey
            elif record.days_remaining < 0:
                record.deadline_status = 'overdue'
                record.deadline_color = 1  # Red
            elif record.days_remaining < 7:
                record.deadline_status = 'critical'
                record.deadline_color = 3  # Orange
            elif record.days_remaining < 14:
                record.deadline_status = 'warning'
                record.deadline_color = 2  # Yellow
            else:
                record.deadline_status = 'on_time'
                record.deadline_color = 10  # Green

    @api.depends('stage_id')
    def _compute_action_visibility(self):
        """Compute which contextual actions should be visible based on current stage."""
        for record in self:
            # These are legacy/placeholder fields for backward compatibility
            record.show_schedule_visit = True if record.stage_id else False
            record.show_create_quote = True if record.stage_id else False
            record.show_assign_subcontractors = True
            record.show_mark_not_pursued = True
