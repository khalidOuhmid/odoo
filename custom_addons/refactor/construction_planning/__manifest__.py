# -*- coding: utf-8 -*-
{
    'name': 'Construction Planning (Gantt)',
    'version': '18.0.1.0.0',
    'category': 'Construction/Planning',
    'summary': 'High-performance Gantt & Scheduling for Construction',
    'description': """
Construction Planning Module
============================

Implements a specialized scheduling engine for construction sites.

Key Features
------------
- **Lightweight Task Model**: Optimized for 1000+ items per project.
- **Dependencies**: Finish-to-Start (FS) constraints logic.
- **OWL Gantt**: "Archireport"-like visual interface.

Models
------
- `construction.planning.task`
    """,
    'author': 'BLG Groupe / Antigravity',
    'website': 'https://www.blggroupe.com',
    'depends': [
        'construction_core',
        'web',             # For the JS framework
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/planning_menus.xml',
        'views/planning_task_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
             'construction_planning/static/src/owl/gantt_view.xml',
             'construction_planning/static/src/owl/gantt_arch_parser.js',
             'construction_planning/static/src/owl/gantt_model.js',
             'construction_planning/static/src/owl/gantt_controller.js',
             'construction_planning/static/src/owl/gantt_renderer.js',
             'construction_planning/static/src/owl/gantt_view.js',
        ],
    },
    'application': False,
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
