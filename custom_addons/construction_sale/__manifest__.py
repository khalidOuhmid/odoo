{
    'name': 'Construction Sale',
    'version': '18.0.1.0.3',
    'category': 'Construction/Sales',
    'summary': 'Next-gen Construction Sales Interface (SPA)',
    'description': """
    Construction Sale Module
    ========================
    Advanced SPA-like interface for construction quotes using Odoo Owl framework.
    
    Features:
    - Owl-based Quote Builder
    - Real-time Draft Saving (LocalStorage)
    - Construction-specific line details (Location, Dimensions, Color)
    - Construction Site integration
    """,
    'author': 'Khalid Ouhmid',
    'depends': ['sale', 'construction_core', 'web', 'purchase'],
    'data': [
        'wizards/sale_to_purchase_views.xml',
        'views/sale_order_views.xml',
        'views/sale_order_report.xml',
        'views/client_actions.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'construction_sale/static/src/stub_widgets.xml',
            'construction_sale/static/src/stub_widgets.js',
            'construction_sale/static/src/quote_builder/quote_builder.xml',
            'construction_sale/static/src/quote_builder/quote_builder.scss',
            'construction_sale/static/src/quote_builder/quote_builder.js',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
