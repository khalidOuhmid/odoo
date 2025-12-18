# -*- coding: utf-8 -*-
{
    'name': 'Construction Invoicing & Progress Billing',
    'version': '18.0.1.0.0',
    'category': 'Construction/Accounting',
    'summary': 'Facturation progressive et situations de travaux',
    'description': """
Construction Invoicing Module
=============================

Gestion de la facturation progressive des chantiers de construction.

**Fonctionnalités:**
* Cycles de facturation ("30/30/40", etc.)
* Planning de facturation lié aux étapes
* Déclenchement automatique selon progression
* Génération de factures "situation"

**Philosophie PLM:**
Les factures sont déclenchées par les étapes:
- Stage DA: Acompte signature possible
- Stages TRAV: Déclenchement par % progression
- Stage LR: Solde final
""",
    'author': 'BLG Groupe',
    'website': 'https://www.blggroupe.com',
    'license': 'LGPL-3',
    'depends': [
        'construction_core',
        'account',
        'sale',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/invoice_type_data.xml',
        'views/invoice_type_views.xml',
        'views/invoice_schedule_views.xml',
        'views/chantier_views.xml',
        'views/menus.xml',
        'wizards/billing_cycle_wizard_view.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
