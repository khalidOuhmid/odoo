# -*- coding: utf-8 -*-
{
    'name': 'Construction Core',
    'version': '18.0.1.1.0',
    'category': 'Construction/Project Management',
    'summary': 'Core module for Construction Sites and Lots management',
    'description': """
Construction Core Module
========================
The foundational module for the Construction Suite. 

Features:
- **Chantier (Site) Management**: Centralized project management.
- **Lot Management**: Breakdown of works into specific lots.
- **Chapter & Stage Workflow**: Strict state machine for project progress.

Enterprise Standards:
- Strict Typing
- SOLID Principles
- "Governor Limits" ready
    """,
    'author': 'Antigravity (Google DeepMind) for BLG Groupe',
    'website': 'https://www.blggroupe.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'contacts',
        'sale',
        'mail',
        'purchase',
        # 'web_gantt', # Optional: Check if enterprise is available, otherwise remove
    ],
    'data': [
        'security/construction_security.xml',
        'security/ir.model.access.csv',
        'data/core_data.xml',
        'data/lot_data.xml',
        'data/email_templates.xml',
        'data/mail_config.xml',
        'data/cron_jobs.xml',
        'wizard/force_stage_wizard_views.xml',
        'wizard/lot_subcontractor_assign_wizard_views.xml',
        'wizard/lot_management_wizard_views.xml',
        'wizard/multi_lot_wizard_views.xml',
        'wizard/sans_suite_wizard_views.xml',
        'views/main_views.xml',
        'views/document_views.xml',
        'views/chantier_views.xml',
        'views/lot_views.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            ('prepend', 'construction_core/static/src/scss/_blg_variables.scss'),
            'construction_core/static/src/scss/construction_kanban.scss',
            'construction_core/static/src/scss/construction_lot.scss',
            'construction_core/static/src/scss/construction_form.scss',
            'construction_core/static/src/widgets/lot_progress/lot_progress_widget.js',
            'construction_core/static/src/widgets/lot_progress/lot_progress_widget.xml',
            'construction_core/static/src/widgets/lot_progress/lot_progress_widget.scss',
        ],
    },
    'external_dependencies': {'python': [], 'bin': []},
    'installable': True,
    'application': True,
    'auto_install': False,
}
