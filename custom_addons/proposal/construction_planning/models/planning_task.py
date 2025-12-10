# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class ConstructionPlanningTask(models.Model):
    _name = 'construction.planning.task'
    _description = 'Task for Gantt Planning'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start asc, id desc'

    # ==========================
    # IDENTIFICATION
    # ==========================
    name = fields.Char(string='Tâche', required=True, tracking=True)
    chantier_id = fields.Many2one('construction.chantier', string='Chantier', required=True, ondelete='cascade', tracking=True)
    lot_id = fields.Many2one('construction.lot', string='Lot', domain="[('chantier_id', '=', chantier_id)]", tracking=True)
    
    # ==========================
    # RESOURCES
    # ==========================
    partner_id = fields.Many2one(
        'res.partner', 
        string='Intervenant', 
        tracking=True,
        help="Sous-traitant ou Employé Interne"
    )
    
    resource_type = fields.Selection(
        [('internal', 'Interne'), ('external', 'Sous-traitant')], 
        string="Type de Ressource",
        compute='_compute_resource_type',
        store=True
    )
    
    @api.depends('partner_id')
    def _compute_resource_type(self):
        for task in self:
            if not task.partner_id:
                task.resource_type = False
            elif task.partner_id.is_subcontractor:
                task.resource_type = 'external'
            else:
                task.resource_type = 'internal'

    # ==========================
    # SCHEDULE (Gantt)
    # ==========================
    date_start = fields.Datetime(string='Début', required=True, tracking=True, default=fields.Datetime.now)
    date_end = fields.Datetime(string='Fin', required=True, tracking=True)
    duration_days = fields.Float(string='Durée (Jours)', compute='_compute_duration', store=True, readonly=False)
    
    progress = fields.Float(string='Avancement (%)', default=0.0, tracking=True)
    color = fields.Integer(string='Couleur', default=1) # Mapping standard Odoo (1-11)
    
    predecessor_ids = fields.Many2many(
        'construction.planning.task', 
        'construction_planning_task_rel', 
        'task_id', 'predecessor_id',
        string='Prédécesseurs',
        domain="[('chantier_id', '=', chantier_id), ('id', '!=', id)]"
    )

    # ==========================
    # LOGIC
    # ==========================
    @api.depends('date_start', 'date_end')
    def _compute_duration(self):
        for task in self:
            if task.date_start and task.date_end:
                delta = task.date_end - task.date_start
                task.duration_days = delta.days + (delta.seconds / 86400)
            else:
                task.duration_days = 0.0

    @api.onchange('duration_days', 'date_start')
    def _on_change_duration(self):
        """ Update End Date if Duration changes """
        if self.date_start and self.duration_days:
            self.date_end = self.date_start + fields.Timedelta(days=self.duration_days)

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for task in self:
            if task.date_start > task.date_end:
                raise ValidationError("La date de fin doit être postérieure à la date de début.")

    # ==========================
    # CONTRACT SYNC
    # ==========================
    # Feature Link: Assigning a Subcontractor here could suggest adding to Contract?
    # Keeping it decoupled for now.
