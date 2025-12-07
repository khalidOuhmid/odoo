# -*- coding: utf-8 -*-
{
    'name': 'Construction Procurement',
    'version': '18.0.1.0.0',
    'category': 'Construction/Purchase',
    'summary': 'Project Procurement & Back-to-Back Orders',
    'description': """
Construction Purchase
=====================

Link Procurement to Construction Projects.

Key Features
------------
- **Project Tracking**: POs linked to Chantier/Lots.
- **Back-to-Back**: Create POs directly from Sales Quotes.
- **Cost Tracking**: Automated commitment tracking.
    """,
    'author': 'BLG Groupe / Antigravity',
    'website': 'https://www.blggroupe.com',
    'depends': [
        'construction_core',
        'construction_sale', # For back-to-back flow
        'purchase',
    ],
    'data': [
        'views/purchase_views.xml',
    ],
    'application': False,
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
