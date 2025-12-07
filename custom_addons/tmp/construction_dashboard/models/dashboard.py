# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ConstructionDashboard(models.Model):
    _name = 'construction.dashboard'
    _description = 'Role-Based Dashboard'
    _order = 'sequence, name'

    name = fields.Char(string='Nom', required=True)
    sequence = fields.Integer(string='Séquence', default=10)

    role = fields.Selection([
        ('gestionnaire', 'Gestionnaire de Chantier'),
        ('administratif', 'Responsable Administratif'),
        ('directeur', 'Directeur de Travaux'),
    ], string='Rôle', required=True)

    widget_ids = fields.One2many(
        'construction.dashboard.widget',
        'dashboard_id',
        string='Widgets'
    )

    user_ids = fields.Many2many(
        'res.users',
        'dashboard_user_rel',
        'dashboard_id',
        'user_id',
        string='Utilisateurs assignés'
    )

    is_default = fields.Boolean(
        string='Par défaut',
        help='Dashboard par défaut pour ce rôle'
    )

    company_id = fields.Many2one(
        'res.company',
        string='Société',
        default=lambda self: self.env.company
    )

    active = fields.Boolean(string='Actif', default=True)

    @api.model
    def get_dashboard_for_user(self, user_id=None):
        """Get the appropriate dashboard for a user based on their role."""
        user = self.env['res.users'].browse(user_id) if user_id else self.env.user

        # First check if user has a specific dashboard assigned
        dashboard = self.search([
            ('user_ids', 'in', user.id),
            ('active', '=', True),
        ], limit=1)

        if dashboard:
            return dashboard

        # Otherwise, determine role from groups and get default dashboard
        role = self._get_user_role(user)
        if role:
            dashboard = self.search([
                ('role', '=', role),
                ('is_default', '=', True),
                ('active', '=', True),
                '|',
                ('company_id', '=', False),
                ('company_id', '=', user.company_id.id),
            ], limit=1)

        return dashboard or self.browse()

    def _get_user_role(self, user):
        """Determine user role based on security groups."""
        if user.has_group('construction_dashboard.group_btpvision_directeur'):
            return 'directeur'
        elif user.has_group('construction_dashboard.group_btpvision_administratif'):
            return 'administratif'
        elif user.has_group('construction_dashboard.group_btpvision_gestionnaire'):
            return 'gestionnaire'
        return None

    def get_dashboard_data(self):
        """Get all widget data for this dashboard."""
        self.ensure_one()
        return {
            'id': self.id,
            'name': self.name,
            'role': self.role,
            'widgets': [widget.get_widget_data() for widget in self.widget_ids],
        }
