# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class ConstructionDateMixin(models.AbstractModel):
    """
    Abstract Mixin for entities managing execution or contractual dates.

    Principles:
    - Encapsulates start/end/duration logic.
    - Enforces coherence (start <= end).
    - Provides utility computations (days remaining).
    """
    _name = 'construction.date.mixin'
    _description = 'Construction Date Mixin'

    date_start = fields.Date(string='Start Date', tracking=True)
    date_end = fields.Date(string='End Date', tracking=True)
    
    duration = fields.Integer(
        string='Duration (Days)',
        compute='_compute_duration',
        store=True,
        readonly=False,
        help="Duration in days. Modifying this updates the End Date."
    )
    
    days_remaining = fields.Integer(
        string='Days Remaining',
        compute='_compute_days_remaining',
        help="Working days remaining until End Date."
    )

    is_late = fields.Boolean(
        string='Is Late',
        compute='_compute_is_late',
        store=True,
        help="True if End Date < Today and State is not closed."
    )

    @api.depends('date_start', 'date_end')
    def _compute_duration(self):
        """Compute duration from dates."""
        for record in self:
            if record.date_start and record.date_end:
                delta = record.date_end - record.date_start
                record.duration = delta.days + 1
            elif not record.duration: # Only if not set manually
                record.duration = 0

    @api.onchange('duration', 'date_start')
    def _onchange_duration(self):
        """Update date_end when duration changes."""
        for record in self:
            if record.date_start and record.duration:
                from datetime import timedelta
                record.date_end = record.date_start + timedelta(days=record.duration - 1)

    @api.depends('date_end')
    def _compute_days_remaining(self):
        """Compute delta between today and date_end."""
        today = fields.Date.context_today(self)
        for record in self:
            if record.date_end:
                record.days_remaining = (record.date_end - today).days
            else:
                record.days_remaining = 0

    @api.depends('date_end')
    def _compute_is_late(self):
        """Check if today is past date_end."""
        today = fields.Date.context_today(self)
        for record in self:
            # Note: This abstract mixin doesn't know about 'state'.
            # Consuming models should override or use a separate mixin for state-based logic.
            if record.date_end and record.date_end < today:
                record.is_late = True
            else:
                record.is_late = False

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        """Invariant: Start Date must be before End Date."""
        for record in self:
            if record.date_start and record.date_end:
                if record.date_start > record.date_end:
                    raise ValidationError(_("End Date cannot be earlier than Start Date."))
