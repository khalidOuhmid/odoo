"""
Stage model for managing construction stages within chapters.

Each stage represents a step in a construction project phase.
Stages are ordered by sequence within their chapter.

Classes:
    Stage: Model for construction stages
"""

from odoo import models, fields, api


class Stage(models.Model):
    """
    Model for managing construction stages within chapters.

    Each stage represents a step in a construction project phase.
    Stages are ordered by sequence within their chapter.

    Attributes:
        name (str): Name of the stage (required, translatable)
        code (str): Unique code of the stage within the chapter (max 10 characters)
        description (str): Detailed description (translatable)
        sequence (int): Order within the chapter (default: 10)
        color (int): Color index for kanban styling (0-11)
        chapter_id (Many2one): Reference to the parent chapter
        chantier_ids (One2many): Projects in this stage
        chantier_count (int): Computed number of projects
        full_name (str): Computed full name combining chapter and stage
        fold (bool): Whether to fold this stage in kanban view
        active (bool): Active status
    """

    _name = 'construction.stage'
    _description = 'Construction Stage'
    _order = 'chapter_id, sequence, name'

    # ============= Basic Fields ============= #
    name = fields.Char('Name', required=True, translate=True)
    code = fields.Char('Code', required=True, size=10)
    description = fields.Text('Description', translate=True)
    sequence = fields.Integer('Sequence', default=10)
    color = fields.Integer(
        'Color Index', default=0, help="Color for kanban styling (0-11)"
    )
    chantier_ids = fields.One2many('construction.chantier', 'stage_id', string='Chantiers')

    @api.depends('chantier_ids')
    def _compute_chantier_count(self):
        for record in self:
            record.chantier_count = len(record.chantier_ids)

    # ============= Relations ============= #
    chapter_id = fields.Many2one('construction.chapter', 'Chapter', required=True, ondelete='cascade')

    # ============= Computed Fields ============= #
    chantier_count = fields.Integer('Number of Projects', compute='_compute_chantier_count', store=True)
    full_name = fields.Char('Full Name', compute='_compute_full_name', store=True)

    # ============= Workflow Properties ============= #
    fold = fields.Boolean('Fold in Kanban', default=False, help="Fold this stage in kanban view")
    validation_info = fields.Text('Information de validation ',
                                  help="Informations sur les conditions pour passer à l'étape suivante"
                                  )
    # ============= Status ============= #
    active = fields.Boolean('Active', default=True)

    _sql_constraints = [
        ('code_chapter_uniq', 'unique(code, chapter_id)', 'Stage code must be unique within a chapter!'),
        ('sequence_positive', 'check(sequence >= 0)', 'Sequence must be positive!'),
    ]

    @api.depends('name', 'chapter_id.name')
    def _compute_full_name(self):
        """
        Compute the full name combining chapter and stage names.
        """
        for record in self:
            if record.chapter_id:
                record.full_name = f"{record.chapter_id.name} - {record.name}"
            else:
                record.full_name = record.name

    def get_next_stage(self):
        """
        Return the next stage in the same chapter.
        """
        return self.search([
            ('chapter_id', '=', self.chapter_id.id),
            ('sequence', '>', self.sequence),
            ('active', '=', True)
        ], limit=1, order='sequence')

    def get_previous_stage(self):
        """
        Return the previous stage in the same chapter.
        """
        return self.search([
            ('chapter_id', '=', self.chapter_id.id),
            ('sequence', '<', self.sequence),
            ('active', '=', True)
        ], limit=1, order='sequence desc')

    def action_view_chantiers(self):
        """
        Action to view projects in this stage.
        """
        return {
            'type': 'ir.actions.act_window',
            'name': f'Projects - {self.full_name}',
            'res_model': 'construction.chantier',
            'view_mode': 'kanban,list,form',
            'domain': [('stage_id', '=', self.id)],
            'context': {'default_stage_id': self.id}
        }

    @api.model
    def _read_group_stage_ids(self, stages, domain, order):
        all_stages = self.search([])
        return all_stages
