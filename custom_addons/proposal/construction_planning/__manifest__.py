{
    'name': 'Construction Planning & Gantt',
    'version': '18.0.1.0.0',
    'category': 'Construction/Project Management',
    'summary': 'Advanced Gantt Planning and Resource Management',
    'description': """
    Construction Planning Module
    ============================
    - Advanced Gantt Chart for Construction Sites (Client-Lourd style)
    - Resource Capacity Planning (Internal vs Subcontractors)
    - Auto-sync with Lots and Contracts
    - PDF Export of Planning
    
    Features:
    - Global Gantt (All Sites)
    - Site Gantt (Lots & Tasks)
    - Resource Gantt (Availability)
    """,
    'author': 'Antigravity',
    'depends': ['construction_core', 'construction_subcontractor', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'views/planning_views.xml',
        'views/planning_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # Placeholder for Custom Gantt JS/CSS
            # 'construction_planning/static/src/**/*', 
        ],
    },
    'application': True,
    'installable': True,
    'license': 'LGPL-3',
}
