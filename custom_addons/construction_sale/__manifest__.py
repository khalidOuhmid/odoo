# -*- coding: utf-8 -*-
{
    'name': 'Construction Sales',
    'version': '18.0.1.0.0',
    'category': 'Construction/Sales',
    'summary': 'Smart Quotes for Construction (Lots, Estimation)',
    'description': """
Construction Sales Integration
==============================

Bridges the gap between Sales and Construction Projects (SAP PS style).

Key Features
------------
- **Quote -> Project**: Auto-create or link projects from quotes.
- **Smart Sections**: Organize quotes by 'Lots' automatically.
- **Estimation**: Advanced costing per lot in the quote.
    """,
    'author': 'BLG Groupe / Antigravity',
    'website': 'https://www.blggroupe.com',
    'depends': [
        'construction_core',
        'sale_management',
    ],
    'data': [
        'views/sale_order_views.xml',
    ],
    'application': False,
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
