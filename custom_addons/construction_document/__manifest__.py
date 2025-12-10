# -*- coding: utf-8 -*-
{
    'name': 'Construction Documents',
    'version': '18.0.1.0.0',
    'category': 'Construction/Document',
    'summary': 'Document Management for Construction Sites',
    'description': """
Construction Document Module
============================
Separated module for managing documents on construction sites.
    """,
    'author': 'Antigravity (Google DeepMind) for BLG Groupe',
    'website': 'https://www.blggroupe.com',
    'license': 'LGPL-3',
    'depends': [
        'construction_core',
        # 'documents',  # Odoo Enterprise - Optional, add in production if available
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/document_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
