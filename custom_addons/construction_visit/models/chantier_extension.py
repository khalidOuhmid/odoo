# -*- coding: utf-8 -*-

from odoo import models, fields, api

class Chantier(models.Model):
    _inherit = 'construction.chantier'

    visit_ids = fields.One2many('construction.visit', 'chantier_id', string='Visites')
    visit_count = fields.Integer(compute='_compute_visit_count', string='Nombre de Visites')

    @api.depends('visit_ids')
    def _compute_visit_count(self):
        for record in self:
            record.visit_count = len(record.visit_ids)

    # ============= Interaction Methods ============= #
    def action_view_visits(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Visites',
            'res_model': 'construction.visit',
            'view_mode': 'list,form,calendar',
            'domain': [('chantier_id', '=', self.id)],
            'context': {'default_chantier_id': self.id}
        }

    # ============= Validation Hooks ============= #
    def check_visit_stage(self):
        """
        Validation to ensure visits are done before specific stages.
        Overrides/Implements the hook in Core.
        """
        # Logic from legacy: check if at least one completed visit exists
        # NOTE: This assumes 'check_visit_stage' is called dynamically by Core's validator
        if not self.visit_ids:
            return False, "Aucune visite technique réalisée"
        
        completed_visits = self.visit_ids.filtered(lambda v: v.state == 'completed')
        if not completed_visits:
            return False, "Visite technique non terminée"
            
        return True, "OK"
