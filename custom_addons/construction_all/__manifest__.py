# -*- coding: utf-8 -*-
{
    'name': 'Construction - Installation Complète',
    'version': '18.0.1.0.0',
    'category': 'Construction',
    'summary': 'Installe tous les modules Construction d\'un seul coup',
    'description': """
Construction Suite - Installation Complète
===========================================

Module méta qui installe automatiquement tous les modules de la suite Construction:

* **construction_core** - Module de base (chantiers, stages, lots)
* **construction_visit** - Gestion des visites techniques
* **construction_subcontractor** - Gestion des sous-traitants
* **construction_contract** - Contrats et signatures électroniques
* **construction_invoice** - Facturation et échelonnement
* **construction_purchase** - Achats et commandes fournisseurs

**Usage:**
Installez uniquement ce module pour activer toute la suite Construction.
""",
    'author': 'BLG Groupe',
    'website': 'https://www.blggroupe.com',
    'license': 'LGPL-3',
    'depends': [
        # Core module (required)
        'construction_core',
        
        # Business modules (all features)
        'construction_visit',
        'construction_subcontractor',
        'construction_contract',
        'construction_invoice',
        'construction_purchase',
    ],
    'data': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'sequence': 1,  # Show at top
}
