# -*- coding: utf-8 -*-
{
    'name': 'BLG Groupe - Construction Base',
    'version': '1.0.0',
    'summary': 'Gestion des lots de construction',
    'description': """
                           Module pour la gestion des catégories et lots de construction
                           pour les projets BLG Groupe.
                       """,
    'category': 'Construction',
    'author': 'BLG Groupe',
    'website': 'https://www.blggroupe.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'contacts',
        'construction_lots',
        'blg_contacts_extension',
        'sale',
        'mail',
        'account',
        'web_gantt'
    ],
    'data': [
        # Security
        'security/security.xml',
        'security/ir.model.access.csv',
        'security/construction_security.xml',

        # Data
        'data/sequence_data.xml',
        'data/construction_data.xml',
        'data/construction_lot_data.xml',
        'data/invoice_type_cycles.xml',

        # Views
        'views/main_views.xml',
        'views/menu.xml',
        'views/invoice_type_views.xml',
        'views/chantier_views.xml',
        'views/visit_views.xml',
        'views/templates.xml',
        'views/planning_views.xml',
        'views/lot_document_wizard_view.xml',

        # Wizards
        'wizard/force_stage_wizard_view.xml',
        'wizard/lot_subquote_wizard_views.xml',

        # report
        'reports/planning_report.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # SCSS/CSS Files
            'construction_base/static/src/scss/kanban_clean.scss',
            'construction_base/static/src/scss/chantier_views.scss'
            # JavaScript Files
            'construction_base/static/src/js/construction_kanban.js',
        ],
    },

    'installable': True,
    'application': True,
    'auto_install': False,
}
