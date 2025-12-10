# -*- coding: utf-8 -*-
{
    'name': 'Construction Contact Extension',
    'version': '18.0.1.0.0',
    'category': 'Construction/Contacts',
    'summary': 'Extension des contacts pour données légales (SIREN)',
    'description': """
Construction Contact Extension
==============================
Extension des modèles Partner et Company pour données légales françaises.

Fonctionnalités:
- Champ SIREN (Partner/Company)
- Validation SIREN (9 chiffres)
    """,
    'author': 'Antigravity (Google DeepMind) for BLG Groupe',
    'website': 'https://www.blggroupe.com',
    'license': 'LGPL-3',
    'depends': [
        'contacts',
    ],
    'data': [
        'views/partner_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
