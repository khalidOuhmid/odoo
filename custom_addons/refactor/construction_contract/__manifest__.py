# -*- coding: utf-8 -*-
{
    'name': 'Construction Contracts (Subcontractors)',
    'version': '18.0.1.0.0',
    'category': 'Construction/Legal',
    'summary': 'Subcontractor Contracts & Document Compliance',
    'description': """
Construction Contracts Module
=============================

Manages legal agreements with subcontractors.

Key Features
------------
- **Contract Generation**: Create PDF contracts from templates.
- **Document Compliance**: Track Kbis, Insurance, URSSAF.
- **Signature Tracking**: Monitor signature status.
    """,
    'author': 'BLG Groupe / Antigravity',
    'website': 'https://www.blggroupe.com',
    'depends': [
        'construction_core',
        # 'document',  # Removed to allow Local Community Testing (Attachments are handled by base/mail)
        'portal', 
        'website',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/contract_menus.xml',
        'views/contract_views.xml',
        'views/portal_templates.xml',
        'views/report_templates.xml',
        'data/email_templates.xml',
    ],
    'application': False,
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
