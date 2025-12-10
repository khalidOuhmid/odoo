# -*- coding: utf-8 -*-
"""
Force Stage Wizard - Reserved for Directors/Admins
Allows forcing stage changes without validation constraints.
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ForceStageWizard(models.TransientModel):
    _name = 'construction.force.stage.wizard'
    _description = 'Forcer le Changement d\'Étape'

    chantier_id = fields.Many2one('construction.chantier', string='Chantier', required=True)
    current_stage_id = fields.Many2one('construction.stage', string='Étape Actuelle', readonly=True)
    new_stage_id = fields.Many2one('construction.stage', string='Nouvelle Étape', required=True)
    reason = fields.Text(string='Raison du Forçage', required=True,
                        help="Expliquez pourquoi vous forcez ce changement")

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        if self.env.context.get('active_model') == 'construction.chantier':
            chantier = self.env['construction.chantier'].browse(self.env.context.get('active_id'))
            res['chantier_id'] = chantier.id
            res['current_stage_id'] = chantier.stage_id.id
        return res

    def action_force_stage(self):
        """Force the stage change with bypass validation context."""
        self.ensure_one()
        
        # Security check - Only Directors/Admins
        if not self.env.user.has_group('construction_core.group_construction_director'):
            raise UserError(_("Seuls les Directeurs et Administrateurs peuvent forcer un changement d'étape."))

        # Log the forced change
        self.chantier_id.message_post(
            body=_(
                "<b>Changement d'étape forcé</b><br/>"
                "De: <b>%s</b> → <b>%s</b><br/>"
                "Par: <b>%s</b><br/>"
                "Raison: %s"
            ) % (
                self.current_stage_id.name,
                self.new_stage_id.name,
                self.env.user.name,
                self.reason
            ),
            subject="Forçage d'étape"
        )

        # Force change with bypass context
        self.chantier_id.with_context(bypass_stage_validation=True).write({
            'stage_id': self.new_stage_id.id
        })

        return {'type': 'ir.actions.act_window_close'}
