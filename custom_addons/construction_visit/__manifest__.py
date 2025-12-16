# -*- coding: utf-8 -*-
{
    'name': 'Construction Visits',
    'version': '18.0.2.0.0',
    'category': 'Construction/Site Management',
    'summary': 'Site Visit management with BLG Groupe workflow',
    'description': """
Construction Visits Module - BLG Groupe
========================================
Handles site visits, reports, and calendar integration.

Features:
- **Visit Scheduling**: Plan and track visits with unified participants.
- **Workflow**: 3-step process (Notification → Report Generation → Report Sending).
- **BLG Charte**: Professional email templates and PDF reports.
- **Chantier Integration**: Visit tabs and logic integrated with Core Chantier.
    """,
    'author': 'Antigravity (Google DeepMind) for BLG Groupe',
    'website': 'https://www.blggroupe.com',
    'license': 'LGPL-3',
    'depends': [
        'construction_core',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/mail_template_visit.xml',
        'reports/visit_report.xml',
        'views/visit_views.xml',
        'views/chantier_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
