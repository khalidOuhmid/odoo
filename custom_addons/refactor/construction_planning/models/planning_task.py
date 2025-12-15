# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class ConstructionPlanningTask(models.Model):
    """
    Planning Task - The atom of the Gantt Chart.
    
    Designed for high volume and speed. 
    Separate from project.task to avoid overhead.
    
    Inherits:
    - construction.date.mixin
    """
    _name = 'construction.planning.task'
    _description = 'Tâche de Planning'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'construction.date.mixin']
    _order = 'date_start, sequence, id'

    name = fields.Char(string='Libellé Tâche', required=True, translate=True)
    sequence = fields.Integer(default=10)
    
    # ==============================================================================================
    #                                      PARENTS & GROUPING
    # ==============================================================================================
    
    chantier_id = fields.Many2one(
        'construction.chantier',
        string='Chantier',
        required=True,
        ondelete='cascade',
        index=True
    )
    
    lot_id = fields.Many2one(
        'construction.lot',
        string='Lot',
        domain="[('chantier_id', '=', chantier_id)]",
        ondelete='restrict', # Don't delete planning if Lot is deleted, maybe? Or cascade?
        index=True
    )
    
    parent_id = fields.Many2one(
        'construction.planning.task',
        string='Tâche Parente',
        domain="[('chantier_id', '=', chantier_id), ('id', '!=', id)]",
        index=True,
        ondelete='cascade'
    )
    
    child_ids = fields.One2many('construction.planning.task', 'parent_id', string='Sous-tâches')

    # ==============================================================================================
    #                                      SCHEDULING LOGIC
    # ==============================================================================================
    
    color = fields.Integer(string='Couleur', default=0)
    
    subcontractor_id = fields.Many2one(
        'res.partner',
        string='Intervenant',
        tracking=True
    )

    constraint_type = fields.Selection([
        ('asap', 'Dès que possible'),
        ('alap', 'Le plus tard possible'),
        ('fixed', 'Date fixe')
    ], string='Contrainte', default='asap', required=True)

    # Dependencies (Predecessors)
    predecessor_ids = fields.Many2many(
        'construction.planning.task',
        'construction_planning_task_dependency_rel',
        'task_id', 'predecessor_id',
        string='Prédécesseurs',
        domain="[('chantier_id', '=', chantier_id), ('id', '!=', id)]"
    )

    # ==============================================================================================
    #                                      CONSTRAINTS & VALIDATION
    # ==============================================================================================

    @api.constrains('parent_id')
    def _check_hierarchy(self):
        if not self._check_recursion():
            raise ValidationError(_("Erreur : Boucle récursive détectée dans la hiérarchie des tâches (Parent/Enfant)."))

    @api.constrains('predecessor_ids')
    def _check_dependency_recursion(self):
        """Simple DFS to detect cycles in dependencies."""
        for task in self:
            visited = set()
            stack = [p.id for p in task.predecessor_ids]
            while stack:
                curr_id = stack.pop()
                if curr_id == task.id:
                    raise ValidationError(_("Erreur : Dépendance circulaire détectée (A dépend de B qui dépend de A)."))
                if curr_id not in visited:
                    visited.add(curr_id)
                    # Fetch predecessors of current predecessor
                    curr_task = self.browse(curr_id)
                    stack.extend([p.id for p in curr_task.predecessor_ids])

    # ==============================================================================================
    #                                      COMPUTED FIELDS FOR GANTT
    # ==============================================================================================
    
    progress = fields.Integer(string='Avancement (%)', default=0)
    
    @api.onchange('lot_id')
    def _onchange_lot_id(self):
        if self.lot_id and self.lot_id.subcontractor_id:
            self.subcontractor_id = self.lot_id.subcontractor_id
    # ==============================================================================================
    #                                      CONFLICT DETECTION (RESOURCE LOCKING)
    # ==============================================================================================

    conflict_ids = fields.Many2many(
        'construction.planning.task',
        'planning_task_conflict_rel',
        'task_id', 'conflict_id',
        string='Conflits de Ressources',
        compute='_compute_conflicts',
        store=True,
        help="Tâches en conflit pour le même sous-traitant sur la même période."
    )
    
    has_conflict = fields.Boolean(string='En Conflit', compute='_compute_conflicts', store=True)

    @api.depends('subcontractor_id', 'date_start', 'date_end')
    def _compute_conflicts(self):
        for task in self:
            if not task.subcontractor_id or not task.date_start or not task.date_end:
                task.conflict_ids = [(5, 0, 0)]
                task.has_conflict = False
                continue
                
            # Find overlapping tasks for same subcontractor
            domain = [
                ('subcontractor_id', '=', task.subcontractor_id.id),
                ('id', '!=', task.id),
                ('date_start', '<', task.date_end),
                ('date_end', '>', task.date_start),
                # Optional: Check if Chantier is different if we only care about cross-project conflicts
                # ('chantier_id', '!=', task.chantier_id.id) 
            ]
            conflicts = self.search(domain)
            task.conflict_ids = [(6, 0, conflicts.ids)]
            task.has_conflict = bool(conflicts)
