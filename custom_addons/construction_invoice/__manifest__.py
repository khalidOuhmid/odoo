{
    'name': 'Construction Invoicing & Progress Billing',
    'version': '18.0.1.0.0',
    'category': 'Construction/Accounting',
    'summary': 'Manage progress billing (situations) and invoicing schedules',
    'description': """
Construction Invoicing Module
=============================
Handles the complex billing cycles of construction projects.
Features:
- Define Invoice Types (Billing Cycles) like "30/30/40".
- Create Billing Schedules linked to Construction Progress.
- Generate "Situation Invoices" referencing the original Quote.
- Deduct previous payments/advances automatically.
- Validates billing against Project Stage.
    """,
    'author': 'Antigravity',
    'depends': [
        'construction_core',
        'construction_sale',
        'account',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/invoice_type_data.xml',
        'views/invoice_schedule_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
