{
    'name': 'Construction Sale Extension',
    'version': '18.0.1.0.0',
    'summary': 'Extension intelligente pour la création de devis construction',
    'description': """
Construction Sale Extension
===========================

Module d'extension pour la création de devis intelligents dans le contexte 
de projets de construction avec intégration complète au module construction_base.

Fonctionnalités principales :
* Wizard intelligent de création de devis par lots
* Intégration native avec les chantiers de construction 
* Gestion automatisée des produits par lots
* Interface moderne et intuitive

Compatibilité : Odoo 18.0
    """,
    'category': 'Construction',
    'author': 'BLG Groupe',
    'website': 'https://www.blggroupe.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'sale',
        'product',
        'construction_base',
    ],
    'data': [
        # Sécurité
        'security/ir.model.access.csv',
        
        # Données de base
        'data/product_category_data.xml',
        'data/product_sequence_data.xml',
        'data/construction_uom_data.xml',
        'data/construction_product_categories.xml',
        'data/construction_products_data.xml',
        
        # Wizards (popup d'abord pour définir les actions)
        'wizards/popup_views.xml',
        'wizards/quote_wizard_views.xml',
        
        # Vues principales
        'views/sale_order_views.xml',
        'views/modern_wizards.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'construction_sale/static/src/scss/quote_builder.scss',
            'construction_sale/static/src/js/quote_builder.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'sequence': 100,
}
