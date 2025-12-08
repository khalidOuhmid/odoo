{
    'name': 'Construction Sales & Estimates',
    'version': '18.0.1.0.0',
    'category': 'Construction/Sales',
    'summary': 'Advanced construction quotes, estimation, and site integration',
    'description': """
Construction Sales Module
=========================
Links Sales Orders to Construction Sites (Chantiers) and Work Packages (Lots).
Features:
- Link Quotes to Chantier and Lots.
- Organizing lines by Lot (Sections).
- Advanced Pricing logic (m², ml, etc.).
- "Smart Add" Wizard for fast quoting.
- Integration with Quotation Templates.
    """,
    'author': 'Antigravity',
    'depends': [
        'sale_management',
        'construction_core',
    ],
    'data': [
        'security/ir.model.access.csv',
        'wizards/construction_quote_wizard_views.xml',
        'views/sale_order_views.xml',
        'views/sale_order_template_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
