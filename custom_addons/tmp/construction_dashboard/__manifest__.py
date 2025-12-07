# -*- coding: utf-8 -*-
{
    'name': 'Construction Dashboard',
    'version': '18.0.1.0.0',
    'category': 'Construction',
    'summary': 'Role-based dashboards for construction management',
    'description': """
        Construction Dashboard
        ======================

        Role-based dashboards for BTPVision ERP with SAP Fiori-inspired design.

        Features:
        ---------
        * Role-based dashboards (Gestionnaire, Administratif, Directeur)
        * Configurable KPI widgets
        * Real-time data refresh
        * Alert panels and quick actions
        * Responsive grid layout
        * BLG Groupe visual identity
    """,
    'author': 'BLG Groupe',
    'website': 'https://www.blggroupe.com',
    'license': 'LGPL-3',

    'depends': [
        'base',
        'web',
        'mail',
        'construction_base',
    ],

    'data': [
        # Security
        'security/dashboard_security.xml',
        'security/ir.model.access.csv',

        # Views
        'views/dashboard_views.xml',
        'views/menus.xml',

        # Data
        'data/default_dashboards.xml',
    ],

    'assets': {
        'web.assets_backend': [
            # BLG Groupe Theme - Variables first
            'construction_dashboard/static/src/scss/_variables.scss',
            'construction_dashboard/static/src/scss/btpvision_theme.scss',
            'construction_dashboard/static/src/scss/dashboard.scss',
            # JavaScript - Components
            'construction_dashboard/static/src/js/kpi_card.js',
            'construction_dashboard/static/src/js/alert_panel.js',
            'construction_dashboard/static/src/js/quick_actions.js',
            'construction_dashboard/static/src/js/dashboard_action.js',
            # XML Templates
            'construction_dashboard/static/src/xml/kpi_card.xml',
            'construction_dashboard/static/src/xml/alert_panel.xml',
            'construction_dashboard/static/src/xml/quick_actions.xml',
            'construction_dashboard/static/src/xml/dashboard_templates.xml',
        ],
    },

    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}
