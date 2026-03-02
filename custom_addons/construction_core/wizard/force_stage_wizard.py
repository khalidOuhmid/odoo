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
        """Load default values from current chantier context."""
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
        if not self.env.user.has_group('construction_core.group_construction_admin'):
            raise UserError(_("Seuls les Directeurs et Administrateurs peuvent forcer un changement d'étape."))

        # Log the forced change with proper HTML (using f-string to avoid % formatting issues)
        from markupsafe import Markup, escape
        
        # Escape user input to prevent XSS
        from_stage = escape(self.current_stage_id.name or '')
        to_stage = escape(self.new_stage_id.name or '')
        user_name = escape(self.env.user.name or '')
        reason_text = escape(self.reason or '')
        
        message = Markup(f"""<div style="padding: 12px; background: linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%); 
                        border-radius: 8px; border-left: 4px solid #ed8936;">
                <p style="margin: 0 0 8px 0; font-weight: 600; color: #c05621;">
                    ⚠️ Changement d'étape forcé
                </p>
                <table style="width: 100%; font-size: 13px;">
                    <tr>
                        <td style="color: #718096; width: 80px;">De:</td>
                        <td style="font-weight: 500;">{from_stage}</td>
                    </tr>
                    <tr>
                        <td style="color: #718096;">Vers:</td>
                        <td style="font-weight: 500;">{to_stage}</td>
                    </tr>
                    <tr>
                        <td style="color: #718096;">Par:</td>
                        <td>{user_name}</td>
                    </tr>
                    <tr>
                        <td style="color: #718096; vertical-align: top;">Raison:</td>
                        <td style="font-style: italic;">{reason_text}</td>
                    </tr>
                </table>
            </div>""")
        
        self.chantier_id.message_post(
            body=message,
            message_type='comment',
            subtype_xmlid='mail.mt_note'
        )

        # Force change with bypass context
        self.chantier_id.with_context(bypass_stage_validation=True).write({
            'stage_id': self.new_stage_id.id
        })

        return {'type': 'ir.actions.act_window_close'}
