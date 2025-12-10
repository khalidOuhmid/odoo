# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ConstructionForceStageWizard(models.TransientModel):
    _name = 'construction.force.stage.wizard'
    _description = 'Wizard to force chantier stage'

    chantier_id = fields.Many2one('construction.chantier', required=True, readonly=True)
    target_stage_id = fields.Many2one('construction.stage', string="Nouvelle Étape", required=True)
    reason = fields.Text(string="Motif (Audit)", required=True)

    def action_confirm(self):
        self.ensure_one()
        # Bypass workflow checks by writing directly (if we had guards)
        # We log the forcing
        self.chantier_id.message_post(
            body=f"⚠️ Étape forcée vers {self.target_stage_id.name} par {self.env.user.name}.<br/>Motif : {self.reason}",
            message_type='comment',
            subtype_xmlid='mail.mt_note'
        )
        self.chantier_id.write({'stage_id': self.target_stage_id.id})
        return {'type': 'ir.actions.act_window_close'}
