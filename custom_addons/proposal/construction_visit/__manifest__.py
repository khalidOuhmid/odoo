{
    'name': 'Construction Site Visits',
    'version': '18.0.1.0.0',
    'category': 'Construction/Project Management',
    'summary': 'Manage site visits, reports and inspections',
    'description': """
    Construction Site Visits Module
    ===============================
    - Plan and track site visits (Initial, Progress, Quality, Reception)
    - Mobile-friendly interface for on-site usage
    - Generate PDF reports automatically
    - Integrate with Construction Core
    """,
    'author': 'Antigravity',
    'depends': ['construction_core', 'calendar', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/visit_views.xml',
        'views/visit_menus.xml',
        # 'reports/visit_report.xml', # To implementing later
    ],
    'application': True,
    'installable': True,
    'license': 'LGPL-3',
}
