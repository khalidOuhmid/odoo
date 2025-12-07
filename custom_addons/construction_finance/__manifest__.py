# -*- coding: utf-8 -*-
{
    'name': 'Construction Finance',
    'version': '18.0.1.0.0',
    'category': 'Construction/Accounting',
    'summary': 'Progress Billing, Retentions (Retenue de Garantie) & DGD',
    'description': """
Construction Finance Module
===========================

Handles the specifics of construction accounting.

Key Features
------------
- **Progress Billing (Situations)**: Bill clients based on % completion.
- **Retentions (Retenue de Garantie)**: Automatic 5% withholding management.
- **DGD**: General Final Settlement.
    """,
    'author': 'BLG Groupe / Antigravity',
    'website': 'https://www.blggroupe.com',
    'depends': [
        'construction_core',
        'account',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/finance_menus.xml',
        'views/progress_billing_views.xml',
        'views/dgd_views.xml',
        'views/invoice_schedule_views.xml',
    ],
    'application': False,
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
