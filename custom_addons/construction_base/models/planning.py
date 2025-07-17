# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class ConstructionPlanningTask(models.Model):
    _name = 'construction.planning.task'
    _description = 'Tâche de planning chantier'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start, date_stop, chantier_id, lot_id'

    name = fields.Char('Nom de la tâche', required=True, tracking=True)
    chantier_id = fields.Many2one('construction.chantier', string='Chantier', required=True, ondelete='cascade', tracking=True)
    lot_id = fields.Many2one('construction.lot', string='Lot', ondelete='set null', tracking=True)
    subcontractor_id = fields.Many2one('res.partner', string='Sous-traitant', domain="[('supplier_rank', '>', 0)]", tracking=True)
    date_start = fields.Datetime('Date de début', required=True, tracking=True)
    date_stop = fields.Datetime('Date de fin', required=True, tracking=True)
    color = fields.Integer('Couleur', default=0)
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('planned', 'Planifiée'),
        ('in_progress', 'En cours'),
        ('done', 'Terminée'),
        ('cancelled', 'Annulée')
    ], string='Statut', default='planned', tracking=True)
    description = fields.Text('Description')
    notes = fields.Text('Notes internes')

    _sql_constraints = [
        ('date_check', 'CHECK(date_stop >= date_start)', 'La date de fin doit être postérieure à la date de début !'),
    ]

    @api.depends('name', 'chantier_id', 'lot_id')
    def _compute_display_name(self):
        for rec in self:
            parts = [rec.name]
            if rec.lot_id:
                parts.append(rec.lot_id.name)
            if rec.chantier_id:
                parts.append(rec.chantier_id.name)
            rec.display_name = ' - '.join(parts)
