# -*- coding: utf-8 -*-

from odoo import models, fields, api

class Chapter(models.Model):
    """
    Chapter model for managing construction chapters.
    
    A chapter represents a major phase of a construction project.
    Projects are linked to chapters through stages.
    """
    _name = 'construction.chapter'
    _description = 'Construction Chapter'
    _order = 'sequence, name'

    # =========== Basic Fields ============
    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code', required=True, size=10)
    description = fields.Text(string='Description', translate=True)
    sequence = fields.Integer(string='Sequence', default=10)
    color = fields.Integer(string='Color Index', default=0, help="Color index for kanban display (0-11)")

    # =========== Relations ============
    stage_ids = fields.One2many('construction.stage', 'chapter_id', string='Stages')

    # =========== Computed Fields ============
    stage_count = fields.Integer(string='Number of Stages', compute='_compute_counts', store=True)
    chantier_count = fields.Integer(string='Number of Projects', compute='_compute_chantier_count', store=True)

    # =========== Status ============
    active = fields.Boolean(string='Active', default=True)
    is_default = fields.Boolean(string='Default Chapter', help="Use this chapter as default for new projects")

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'Chapter code must be unique!'),
        ('name_uniq', 'unique(name)', 'Chapter name must be unique!'),
        ('sequence_positive', 'check(sequence >= 0)', 'Sequence must be positive!'),
    ]

    @api.depends('stage_ids')
    def _compute_counts(self):
        """Compute the number of stages in this chapter."""
        for record in self:
            record.stage_count = len(record.stage_ids)

    @api.depends('stage_ids.chantier_ids')
    def _compute_chantier_count(self):
        """Compute the number of projects in this chapter via stages."""
        for record in self:
            # Efficiently count unique projects
            record.chantier_count = len(record.stage_ids.mapped('chantier_ids'))

    def get_chantiers(self) -> models.Model:
        """
        Get all projects in this chapter through stages.

        Returns:
            recordset: All chantiers in this chapter
        """
        return self.stage_ids.mapped('chantier_ids')

    def action_view_chantiers(self) -> dict:
        """Action to view projects in this chapter."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Projects - {self.name}',
            'res_model': 'construction.chantier',
            'view_mode': 'kanban,list,form',
            'domain': [('stage_id.chapter_id', '=', self.id)],
            'context': {'default_chapter_id': self.id}
        }
