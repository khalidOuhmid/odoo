# -*- coding: utf-8 -*-
{
    'name': 'Construction Purchasing Pro',
    'version': '18.0.2.0.0',
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
    ],
    'data': [
        # Security
        'security/ir.model.access.csv',
        
        # Wizards
        'wizard/purchase_wizard_views.xml',
        
        # Views
        'views/purchase_order_views.xml',
        'views/chantier_views.xml',
        'views/lot_views.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'construction_purchase/static/src/scss/purchase_premium.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'sequence': 110,
}
