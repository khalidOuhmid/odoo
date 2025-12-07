# -*- coding: utf-8 -*-
{
    'name': 'Construction Templates',
    'version': '18.0.1.0.0',
    'category': 'Construction',
    'summary': 'Centralized document template management for construction contracts',
    'description': """
        Construction Templates
        ======================

        Centralized management of document templates for BTPVision ERP.

        Features:
        ---------
        * Unified template management for contracts, invoices, quotes, and purchase orders
        * GrapesJS visual editor integration with BLG Groupe styling blocks
        * Signature zone configuration with drag-and-drop positioning
        * Template versioning with full history
        * Active/default template management per company
        * Pre-configured BLG Groupe templates
    """,
    'author': 'BLG Groupe',
    'website': 'https://www.blggroupe.com',
    'license': 'LGPL-3',

    'depends': [
        'base',
        'web',
        'mail',
        'construction_contract',
        'account',
        'sale',
        'purchase',
    ],

    'data': [
        # Security
        'security/templates_security.xml',
        'security/ir.model.access.csv',

        # Views
        'views/document_template_views.xml',
        'views/template_editor_templates.xml',
        'views/menus.xml',

        # Reports
        'reports/contract_blg_template.xml',
        'reports/invoice_blg_template.xml',
        'reports/quote_blg_template.xml',
        'reports/purchase_order_blg_template.xml',

        # Data
        'data/default_templates.xml',
    ],

    'assets': {
        'web.assets_backend': [
            'construction_templates/static/src/scss/templates.scss',
        ],
    },

    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}
