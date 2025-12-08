# -*- coding: utf-8 -*-
{
    'name': 'Construction Subcontractor',
    'version': '18.0.1.0.0',
    'category': 'Construction/Subcontracting',
    'summary': 'Partner Compliance, Contracts & Documents',
    'description': """
        Construction Subcontractor Management
        =====================================
        
        Consolidates logic from 'blg_contacts_extension' and 'construction_contract'.
        
        Features:
        * Subcontractor Profile & Qualification
        * Compliance Documents (KBIS, URSSAF, Insurance) with Expiry Tracking
        * Contract Management (Digital Signature, Provisions)
        
        Depends on `construction_core` for foundational mixins.
    """,
    'author': 'BLG Groupe',
    'website': 'https://www.blggroupe.com',
    'license': 'LGPL-3',
    'depends': [
        'construction_core',
        'contacts',
        'portal', # For contract signature
        'mail',
        'purchase',
        'sale',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/mail_template_data.xml',
        'views/res_partner_views.xml',
        'views/construction_contract_views.xml',
        'reports/contract_report.xml',
    ],
    'application': False,
    'installable': True,
    'auto_install': False,
}
