# -*- coding: utf-8 -*-
{
    'name': 'Construction Portal',
    'version': '18.0.1.0.0',
    'category': 'Construction/Portal',
    'summary': 'Subcontractor Portal & Signature',
    'description': """
        Construction Portal Features
        ============================
        
        Frontend logic for:
        * Contract Electronic Signature (Page-by-page validation)
        * Subcontractor Document Upload (Secure Token)
        
        Split from backend logic to keep 'construction_subcontractor' clean.
    """,
    'author': 'BLG Groupe',
    'license': 'LGPL-3',
    'depends': [
        'construction_subcontractor',
        'portal',
        'web',
    ],
    'data': [
        'views/portal_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'construction_portal/static/src/scss/portal.scss',
            'construction_portal/static/src/js/signature_pad.js',
        ],
    },
    'application': False,
    'installable': True,
}
