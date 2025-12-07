# -*- coding: utf-8 -*-
{
    'name': 'Construction Core',
    'version': '18.0.1.0.0',
    'category': 'Construction/Project Management',
    'summary': 'Core module for Construction Management System (BTP)',
    'description': """
Construction Core Module
========================

This is the kernel of the Construction Management System.
It defines the fundamental data models and business logic without UI clutter.

Architecture
------------
- **SOLID Principles**: Usage of Abstract Mixins and specialized models.
- **Fat Models**: Business logic is encapsulated in models.
- **Performance**: Optimized SQL queries and computed fields.

Key Features
------------
- **Chantier (Project site)**: The aggregate root entity managing the lifecycle.
- **Lot (Work Package)**: The budgetary and operational unit.
- **Partner Extension**: Managing subcontractors and supplier ranks.
    """,
    'author': 'BLG Groupe / Antigravity',
    'website': 'https://www.blggroupe.com',
    'depends': [
        'base',
        'mail',
        'contacts',
        'product',  # For material/service definitions
        'analytic', # For budget tracking
    ],
    'data': [
        'security/construction_security.xml',
        'security/ir.model.access.csv',
        'data/construction_sequence_data.xml',
        'views/construction_menus.xml',
        'views/construction_chantier_views.xml',
        'views/construction_lot_views.xml',
    ],
    'application': True,
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
