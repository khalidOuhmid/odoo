# -*- coding: utf-8 -*-
{
    'name': 'Construction Subcontractor Management',
    'version': '18.0.1.0.0',
    'category': 'Construction/Subcontracting',
    'summary': 'Sous-traitants: conformité documentaire, contrats, portail',
    'description': """
Construction Subcontractor Management
=====================================

Gestion complète des sous-traitants pour les chantiers de construction.

**Fonctionnalités:**
* Profil sous-traitant et qualification
* Documents de conformité (KBIS, URSSAF, Assurances) avec suivi d'expiration
* Gestion des contrats (signature numérique, avenants)
* Portail d'upload sécurisé pour les sous-traitants
* Notifications automatiques (chatter, activités)
* Rapport de conformité

**Philosophie PLM:**
Les actions sont liées aux étapes du chantier:
- Stage DA: Contrats signés requis
- Stage FD: Tous documents valides requis
""",
    'author': 'BLG Groupe',
    'website': 'https://www.blggroupe.com',
    'license': 'LGPL-3',
    'depends': [
        'construction_core',
        'contacts',
        'mail',
        'portal',
    ],
    'data': [
        # Security
        'security/ir.model.access.csv',
        
        # Data
        'data/mail_templates.xml',
        'data/email_templates_enterprise.xml',
        'data/cron_jobs.xml',
        
        # Views
        'views/res_partner_views.xml',
        'views/construction_contract_views.xml',
        'views/menus.xml',
        'wizard/subcontractor_assignment_wizard_views.xml',
        'views/lot_integration_views.xml',
        
        # Portal
        'views/portal_templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'construction_subcontractor/static/src/scss/subcontractor.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
