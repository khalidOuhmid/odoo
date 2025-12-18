# -*- coding: utf-8 -*-
{
    'name': 'Construction Finance BI',
    'version': '1.0',
    'category': 'Construction/Finance',
    'summary': 'Business Intelligence for Construction Sites',
    'description': """
        Military-Grade Financial Analysis for Construction Projects.
        
        Features:
        - Real-time SQL Analysis View
        - God Mode Dashboard (Revenue vs Cost)
        - Margin Analysis
        - Traffic Lights Indicators
    """,
    'author': 'Task Force Elite',
    'depends': ['construction_core', 'construction_sale', 'construction_invoice', 'sale', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'views/finance_dashboard.xml',
        'views/finance_menus.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
