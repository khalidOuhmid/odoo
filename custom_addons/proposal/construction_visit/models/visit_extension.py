# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ConstructionChantier(models.Model):
    _inherit = 'construction.chantier'

    visit_ids = fields.One2many('construction.visit', 'chantier_id', string='Visits')
    visit_count = fields.Integer(compute='_compute_visit_count', string="Visit Count")

    @api.depends('visit_ids')
    def _compute_visit_count(self):
        for chantier in self:
            chantier.visit_count = len(chantier.visit_ids)

    def action_open_visits(self):
        self.ensure_one()
        return {
            'name': 'Visits',
            'type': 'ir.actions.act_window',
            'res_model': 'construction.visit',
            'view_mode': 'list,form',
            'domain': [('chantier_id', '=', self.id)],
            'context': {'default_chantier_id': self.id},
        }
