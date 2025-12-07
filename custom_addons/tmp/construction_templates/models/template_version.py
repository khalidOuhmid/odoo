# -*- coding: utf-8 -*-

from odoo import models, fields


class ConstructionTemplateVersion(models.Model):
    _name = 'construction.template.version'
    _description = 'Template Version History'
    _order = 'create_date desc'

    template_id = fields.Many2one(
        'construction.document.template',
        string='Template',
        required=True,
        ondelete='cascade'
    )
    version_number = fields.Integer(string='Numéro de version', required=True)

    # Snapshots
    html_snapshot = fields.Html(string='HTML', sanitize=False)
    css_snapshot = fields.Text(string='CSS')
    grapesjs_snapshot = fields.Text(string='Données GrapesJS')

    # Metadata
    description = fields.Char(string='Description')
    created_by = fields.Many2one(
        'res.users',
        string='Créé par',
        default=lambda self: self.env.user,
        readonly=True
    )

    def action_restore(self):
        """Restore template to this version."""
        self.ensure_one()
        self.template_id.write({
            'html_content': self.html_snapshot,
            'css_content': self.css_snapshot,
            'grapesjs_data': self.grapesjs_snapshot,
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Version restaurée',
                'message': f'Template restauré à la version {self.version_number}',
                'type': 'success',
            }
        }

    def action_preview(self):
        """Preview this version's content."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Aperçu - Version {self.version_number}',
            'res_model': 'construction.template.version',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
