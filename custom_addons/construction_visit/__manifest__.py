# -*- coding: utf-8 -*-
{
    'name': 'Construction Site Visits',
    'version': '18.0.1.0.0',
    'category': 'Construction/Operations',
    'summary': 'Site Visit Reports, Photos & Calendar',
    'description': """
Construction Site Visits
========================

Manage daily/weekly site visits with ease.

Key Features
------------
- **Visit Reports**: Rich text reports (Quill/HTML).
- **Photo Gallery**: Specialized attachment handling.
- **PDF Generation**: Auto-generate beautiful reports for clients.
- **Calendar**: Integrated view of all visits.
    """,
    'author': 'BLG Groupe / Antigravity',
    'website': 'https://www.blggroupe.com',
    'depends': [
        'construction_core',
        'calendar',
    ],
    'data': [
        'security/ir.model.access.csv',
        'report/visit_report_template.xml',
        'report/visit_report_action.xml',
        'views/visit_menus.xml',
        'views/visit_views.xml',
    ],
    'application': False,
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
