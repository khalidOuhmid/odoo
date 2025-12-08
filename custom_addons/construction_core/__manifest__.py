# -*- coding: utf-8 -*-
{
    'name': 'Construction Core',
    'version': '18.0.1.0.0',
    'category': 'Construction/Technical',
    'summary': 'Core foundations and FinOps mixins for Construction modules',
    'description': """
        Construction Core Module
        ========================
        
        This module provides the technical foundations for the modular Construction architecture.
        It contains:
        * Abstract models for financial tracking (FinOps)
        * Mixins for document management
        * Base enums and utilities
        
        This module does NOT contain end-user views or actions.
    """,
    'author': 'BLG Groupe',
    'website': 'https://www.blggroupe.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'analytic',  # Fundamental for FinOps
        'uom',
    ],
    'data': [
        'security/construction_security.xml',
        'security/ir.model.access.csv',
        'data/construction_stage_data.xml',
        'wizards/force_stage_wizard_views.xml',
        'views/project_chantier_views.xml',
        'views/project_lot_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
