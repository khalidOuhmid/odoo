# -*- coding: utf-8 -*-
{
    'name': 'Construction Purchasing Pro',
    'version': '18.0.2.1.0',
    'category': 'Construction/Purchase',
    'summary': 'Gestion intelligente des achats pour chantiers de construction',
    'description': """
Construction Purchase Pro
=========================

Module professionnel de gestion des achats construction avec intégration 
SAP/Salesforce-style au module construction_core.

Fonctionnalités principales :
* Wizard intelligent de création de bons de commande par lots
* Groupement automatique par sous-traitant
* Intégration native avec les chantiers
* Organisation par sections de lots
* Calcul automatique des marges
* Interface premium et intuitive

Compatibilité : Odoo 18.0
    """,
    'author': 'Antigravity (Google DeepMind) for BLG Groupe',
    'website': 'https://www.blggroupe.com',
    'license': 'LGPL-3',
    'depends': [
        'construction_core',
        'purchase',
        'product',
        'sale',
        'account',
    ],
    'data': [
        # Security
        'security/ir.model.access.csv',

        # Wizards
        'wizard/purchase_wizard_views.xml',
        'wizard/purchase_create_wizard_views.xml',

        # Reports
        'reports/purchase_order_report.xml',
        'reports/invoice_report_blg.xml',

        # Views
        'views/purchase_order_views.xml',
        'views/chantier_views.xml',
        'views/lot_views.xml',
        'views/menus.xml',

        # PurchaseBuilder client action
        'views/purchase_builder_action.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'construction_purchase/static/src/scss/purchase_premium.scss',
            'construction_purchase/static/src/purchase_builder/purchase_builder.scss',
            'construction_purchase/static/src/purchase_builder/purchase_builder.js',
            'construction_purchase/static/src/purchase_builder/purchase_builder.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'sequence': 110,
    'test_dependencies': ['construction_core'],
}
