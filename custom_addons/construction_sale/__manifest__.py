{
    'name': 'Construction Sale Extension',
    'version': '1.0.0',
    'summary': 'Extension intelligente du module Sale pour la construction',
    'description': """
        Module d'extension pour la création de devis intelligents
        dans le contexte de projets de construction.
    """,
    'category': 'Construction',
    'author': 'BLG Groupe',
    'website': 'https://www.blggroupe.com',
    'license': 'LGPL-3',
    'depends': ['construction_base', 'sale', 'product', 'blggroupe_lots'],
    'data': [
        'security/ir.model.access.csv',
        'data/product_category_data.xml',
        'data/product_sequence_data.xml',
        'views/modern_wizards.xml',
        'wizards/quote_builder_wizard.xml',
        'wizards/import_email_wizard.xml',
    ],
'assets': {
        'web.assets_backend': [
            'construction_sale/static/src/scss/quote_builder.scss',
            'construction_sale/static/src/scss/lot_product_selector.scss',
            'construction_sale/static/src/js/lot_product_selector.js',
            'construction_sale/static/src/xml/lot_product_selector.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'sequence': 100,
}
