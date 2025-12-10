# -*- coding: utf-8 -*-
{
    'name': 'Construction Visits',
    'version': '18.0.1.0.0',
    'category': 'Construction/Site Management',
    'summary': 'Site Visit management for Construction',
    'description': """
Construction Visits Module
==========================
Handles site visits, reports, and calendar integration.
Separated from Base to follow Microservices architecture.

Features:
- **Visit Scheduling**: Plan and track visits.
- **Reports**: Generate visit reports.
- **Chantier Integration**: Adds visit tabs and logic to Core Chantier.
    """,
    'author': 'Antigravity (Google DeepMind) for BLG Groupe',
    'website': 'https://www.blggroupe.com',
    'license': 'LGPL-3',
    'depends': [
        'construction_core',
    ],
    'data': [
        'security/ir.model.access.csv',
        'reports/visit_report.xml',
        'views/visit_views.xml',
        'views/chantier_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
