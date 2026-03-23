# -*- coding: utf-8 -*-
{
    'name': 'Construction Visits',
    'version': '18.0.2.2.0',
    'category': 'Construction/Site Management',
    'summary': 'Site Visit management with ICS calendar integration - BLG Groupe',
    'description': """
Construction Visits Module - BLG Groupe
========================================
Production-grade site visit management with calendar integration.

Features:
- **Visit Scheduling**: Plan and track visits with unified participants.
- **24h Validation Buffer**: Ensure adequate preparation time.
- **ICS Calendar Integration**: RFC 5545 compliant calendar files (Outlook/Gmail/Apple).
- **Workflow**: 3-step process (Notification with ICS -> Report Generation -> Report Sending).
- **BLG Charte**: Professional email templates and PDF reports.
- **Chantier Integration**: Visit tabs and logic integrated with Core Chantier.
- **Maps/Waze Deep Links**: Native navigation app integration.

Audit & Compliance:
- All actions logged to chatter
- Comprehensive unit test coverage
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
        'data/cron.xml',
        'reports/visit_report.xml',
        'views/visit_views.xml',
        'views/chantier_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
