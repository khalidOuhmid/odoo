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
        'views/product_views.xml',
        'views/sale_order_views.xml',
        'views/chantier_views.xml',
        'views/sale_order_report.xml',
        'views/client_actions.xml',
        'reports/sale_order_report_blg.xml',
    ],
    'assets': {
        'web.assets_backend': [
            ('prepend', 'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap'),
            'construction_sale/static/lib/sortable/Sortable.min.js',
            'construction_sale/static/src/stub_widgets.xml',
            'construction_sale/static/src/stub_widgets.js',
            'construction_sale/static/src/hooks/useUndoRedo.js',
            'construction_sale/static/src/quote_builder/quote_builder.xml',
            'construction_sale/static/src/quote_builder/quote_builder.scss',
            'construction_sale/static/src/quote_builder/quote_builder.js',
            'construction_sale/static/src/quote_builder/quote_builder_dnd.js',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
