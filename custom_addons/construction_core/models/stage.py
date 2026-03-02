# -*- coding: utf-8 -*-

from odoo import models, fields, api

class Stage(models.Model):
    """
    Model for managing construction stages within chapters.

    Each stage represents a step in a construction project phase.
    Stages are ordered by sequence within their chapter.
    """
    _name = 'construction.stage'
    _description = 'Construction Stage'
    _order = 'chapter_id, sequence, name'

    # ============= Basic Fields ============= #
    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code', required=True, size=10)
    description = fields.Text(string='Description', translate=True)
    sequence = fields.Integer(string='Sequence', default=10)
    color = fields.Integer(string='Color Index', default=0, help="Color for kanban styling (0-11)")
    
    # ============= Relations ============= #
    chapter_id = fields.Many2one('construction.chapter', string='Chapter', required=True, ondelete='cascade')
    chantier_ids = fields.One2many('construction.chantier', 'stage_id', string='Chantiers')

    # ============= Computed Fields ============= #
    chantier_count = fields.Integer(string='Number of Projects', compute='_compute_chantier_count', store=True)
    full_name = fields.Char(string='Full Name', compute='_compute_full_name', store=True)

    # ============= Workflow Properties ============= #
    fold = fields.Boolean(string='Fold in Kanban', default=False, help="Fold this stage in kanban view")
    validation_info = fields.Text(string='Validation Info', help="Information about conditions to move to next stage")
    
    # ============= Status ============= #
    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        ('code_chapter_uniq', 'unique(code, chapter_id)', 'Stage code must be unique within a chapter!'),
        ('sequence_positive', 'check(sequence >= 0)', 'Sequence must be positive!'),
    ]

    @api.depends('chantier_ids')
    def _compute_chantier_count(self):
        """Count the number of linked chantiers for this stage."""
        for record in self:
            record.chantier_count = len(record.chantier_ids)

    @api.depends('name', 'chapter_id.name')
    def _compute_full_name(self):
        """Compute the full name combining chapter and stage names."""
        for record in self:
            if record.chapter_id:
                record.full_name = f"{record.chapter_id.name} - {record.name}"
            else:
                record.full_name = record.name

    def get_next_stage(self) -> models.Model:
        """Return the next stage in the same chapter."""
        self.ensure_one()
        return self.search([
            ('chapter_id', '=', self.chapter_id.id),
            ('sequence', '>', self.sequence),
            ('active', '=', True)
        ], limit=1, order='sequence')

    def get_previous_stage(self) -> models.Model:
        """Return the previous stage in the same chapter."""
        self.ensure_one()
        return self.search([
            ('chapter_id', '=', self.chapter_id.id),
            ('sequence', '<', self.sequence),
            ('active', '=', True)
        ], limit=1, order='sequence desc')

    def action_view_chantiers(self) -> dict:
        """Action to view projects in this stage."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Projects - {self.full_name}',
            'res_model': 'construction.chantier',
            'view_mode': 'kanban,list,form',
            'domain': [('stage_id', '=', self.id)],
            'context': {'default_stage_id': self.id}
        }

    @api.model
    def _read_group_stage_id(self, stages, domain, order) -> models.Model:
        """Expand stages to show empty ones in Kanban."""
        return self.search([])
