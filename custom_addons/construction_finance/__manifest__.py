# -*- coding: utf-8 -*-
{
    'name': 'Construction Finance — Tour de Contrôle',
    'version': '2.0',
    'category': 'Construction/Finance',
    'summary': 'Tour de contrôle financière pour dirigeants BTP — 5 vues opérationnelles',
    'description': """
Tour de Contrôle Financière BLG Groupe
=======================================

Vue globale de tous vos chantiers en temps réel.

Fonctionnalités :
- Tour de Contrôle : 100 chantiers en un coup d'œil (vert/orange/rouge)
- Analyse des Marges : classement automatique du plus au moins rentable
- Facturation : ce qui est prêt à encaisser, les retards, le pipeline 30j
- Prévisions M+1/M+2/M+3 : combien va-t-on encaisser ?
- Sous-Traitants : qui travaille le plus, qui coûte le plus ?
- Alertes automatiques : marge faible, budget dépassé, facture en retard
    """,
    'author': 'Antigravity (Google DeepMind) for BLG Groupe',
    'website': 'https://www.blggroupe.com',
    'license': 'LGPL-3',
    'depends': [
        'construction_core',
        'construction_sale',
        'construction_invoice',
        'construction_purchase',
        'sale',
        'account',
        'purchase',
    ],
    'data': [
        # Security
        'security/ir.model.access.csv',
        # Data (cron + thresholds defaults)
        'data/finance_cron.xml',
        # Views Sprint 1
        'views/finance_dashboard.xml',
        'views/finance_alerts.xml',
        # Views Sprint 2
        'views/view_facturation.xml',
        'views/view_sous_traitants.xml',
        # Views Sprint 3
        'views/view_previsions.xml',
        # Menus (last, after all actions are defined)
        'views/finance_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'construction_finance/static/src/scss/finance_dashboard.scss',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
    'sequence': 200,
}
