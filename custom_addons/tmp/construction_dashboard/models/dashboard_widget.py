# -*- coding: utf-8 -*-

import json
from odoo import models, fields, api
from odoo.tools.safe_eval import safe_eval


class ConstructionDashboardWidget(models.Model):
    _name = 'construction.dashboard.widget'
    _description = 'Dashboard Widget'
    _order = 'position_y, position_x'

    dashboard_id = fields.Many2one(
        'construction.dashboard',
        string='Dashboard',
        required=True,
        ondelete='cascade'
    )

    name = fields.Char(string='Nom', required=True)

    widget_type = fields.Selection([
        ('kpi', 'KPI Card'),
        ('chart', 'Graphique'),
        ('list', 'Liste'),
        ('calendar', 'Calendrier'),
        ('alert', 'Panneau d\'alertes'),
        ('quick_action', 'Actions rapides'),
    ], string='Type', required=True, default='kpi')

    # Data source
    model_name = fields.Char(string='Modèle')
    domain = fields.Text(string='Domaine', default='[]')
    measure_field = fields.Char(string='Champ de mesure')
    group_by = fields.Char(string='Grouper par')

    # Display
    title = fields.Char(string='Titre')
    icon = fields.Char(string='Icône', default='fa-chart-bar')
    color = fields.Selection([
        ('primary', 'Terre cuite'),
        ('success', 'Vert'),
        ('warning', 'Orange'),
        ('danger', 'Rouge'),
        ('info', 'Bleu'),
        ('secondary', 'Gris'),
    ], string='Couleur', default='primary')

    # Grid position
    position_x = fields.Integer(string='Position X', default=0)
    position_y = fields.Integer(string='Position Y', default=0)
    width = fields.Integer(string='Largeur (colonnes)', default=3)
    height = fields.Integer(string='Hauteur (lignes)', default=2)

    # Refresh
    refresh_interval = fields.Integer(
        string='Intervalle de rafraîchissement (s)',
        default=60,
        help='0 = pas de rafraîchissement automatique'
    )

    # Quick actions config (JSON)
    action_config = fields.Text(
        string='Configuration actions',
        help='JSON configuration for quick action buttons'
    )

    def get_widget_data(self):
        """Get computed data for this widget."""
        self.ensure_one()
        data = {
            'id': self.id,
            'name': self.name,
            'type': self.widget_type,
            'title': self.title or self.name,
            'icon': self.icon,
            'color': self.color,
            'position': {
                'x': self.position_x,
                'y': self.position_y,
                'width': self.width,
                'height': self.height,
            },
            'refresh_interval': self.refresh_interval,
        }

        # Compute value based on widget type
        if self.widget_type == 'kpi':
            data['value'] = self._compute_kpi_value()
        elif self.widget_type == 'list':
            data['items'] = self._compute_list_items()
        elif self.widget_type == 'alert':
            data['alerts'] = self._compute_alerts()
        elif self.widget_type == 'quick_action':
            data['actions'] = self._get_quick_actions()

        return data

    def _compute_kpi_value(self):
        """Compute KPI value from model and domain."""
        if not self.model_name:
            return 0

        try:
            domain = safe_eval(self.domain or '[]')
            Model = self.env[self.model_name]

            if self.measure_field:
                records = Model.search(domain)
                return sum(records.mapped(self.measure_field))
            else:
                return Model.search_count(domain)
        except Exception:
            return 0

    def _compute_list_items(self, limit=10):
        """Get list items from model."""
        if not self.model_name:
            return []

        try:
            domain = safe_eval(self.domain or '[]')
            Model = self.env[self.model_name]
            records = Model.search(domain, limit=limit)
            return [{
                'id': r.id,
                'name': r.display_name,
            } for r in records]
        except Exception:
            return []

    def _compute_alerts(self):
        """Compute alert items."""
        # Override in specific implementations
        return []

    def _get_quick_actions(self):
        """Get quick action buttons configuration."""
        if not self.action_config:
            return []
        try:
            return json.loads(self.action_config)
        except json.JSONDecodeError:
            return []
