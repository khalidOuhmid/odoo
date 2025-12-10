# -*- coding: utf-8 -*-

from odoo import models, fields

class Chantier(models.Model):
    _inherit = "construction.chantier"

    document_ids = fields.One2many('construction.document', 'chantier_id', string="Documents")
    document_count = fields.Integer(compute='_compute_document_count', string="Nombre de documents")

    def _compute_document_count(self):
        for record in self:
            record.document_count = len(record.document_ids)

    def action_view_documents(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Documents',
            'res_model': 'construction.document',
            'view_mode': 'kanban,list,form',
            'domain': [('chantier_id', '=', self.id)],
            'context': {'default_chantier_id': self.id}
        }
