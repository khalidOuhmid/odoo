# -*- coding: utf-8 -*-
"""
This module defines the BlgChantier model representing construction projects in BLG Groupe.

Features:
---------
- Manages project lifecycle from initial call to archiving.
- Tracks project details, client information, dates, and financials.
- Supports workflow progression through chapters and stages.
- Links to work sections (lots), technical visits, documents, and subcontractors.
- Provides methods for assigning subcontractors, scheduling visits, and managing documents.

Author: BLG IT Team
"""
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta


class BlgChantier(models.Model):
    """
    Simplified Chantier model for initial testing
    """
    _name = 'blg.chantier'
    _description = 'Chantier BTP'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    # Basic Information only
    name = fields.Char('Project Name', required=True, tracking=True)
    client_id = fields.Many2one('res.partner', string='Client', required=True)
    address = fields.Text('Site Address')
    description = fields.Html('Project Description')
    
    # Simplified workflow
    stage_id = fields.Many2one('blg.stage', string='Current Stage', tracking=True)
    chapter_id = fields.Many2one('blg.chapter', string='Chapter', tracking=True)
    progress = fields.Float('Progress (%)', default=0)
    
    # Basic dates
    date_start_contract = fields.Date('Start Date')
    date_end_contract = fields.Date('End Date')
    
    # Financial
    total_cost = fields.Monetary('Total Cost', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    
    # Team
    user_ids = fields.Many2many('res.users', string='Team')
    
    # Computed fields - simplified
    days_remaining = fields.Integer('Days Remaining', compute='_compute_days_remaining')
    
    @api.depends('date_end_contract')
    def _compute_days_remaining(self):
        """Compute days until deadline"""
        today = fields.Date.today()
        for record in self:
            if record.date_end_contract:
                delta = record.date_end_contract - today
                record.days_remaining = delta.days
            else:
                record.days_remaining = 0

    def get_lots_with_sent_quotes(self):
        """Retourne les lots avec des devis envoyés."""
        self.ensure_one()
        return self.lot_ids.filtered(lambda l: l.quote_state == 'sent')

    @api.model
    def create(self, vals):
        """Set default stage"""
        if not vals.get('stage_id'):
            first_stage = self.env['blg.stage'].search([], limit=1)
            if first_stage:
                vals['stage_id'] = first_stage.id
                vals['chapter_id'] = first_stage.chapter_id.id
        return super().create(vals)
