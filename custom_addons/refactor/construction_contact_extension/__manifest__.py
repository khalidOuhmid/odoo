# -*- coding: utf-8 -*-
{
    'name': 'BLG Groupe - Extension Contacts Sous-traitants',
    'version': '18.0.1.0.0',
    'category': 'Construction/Contacts',
    'sequence': 100,
    'summary': 'Gestion avancée des sous-traitants et de leurs documents administratifs',
    'description': '''

                                      Extension complète pour la gestion des sous-traitants dans le secteur du bâtiment
                                      ================================================================================

                                      Fonctionnalités principales :
                                      ============================

                                      📋 **Gestion des Documents**
                     • Upload et validation de documents administratifs
                     • Suivi automatique des dates d'expiration
                     • Archivage et historique complet
                     • Notifications automatiques de renouvellement
                     • Portail sécurisé pour les sous-traitants
                   
                   🏗️ **Gestion des Sous-traitants**
                     • Profils détaillés avec spécialités
                     • Scores de fiabilité et santé documentaire
                     • Statistiques avancées et tableaux de bord
                     • Opérations en lot pour gains de productivité
                   
                   
                   🔐 **Portail Sécurisé**
                     • Accès par token temporaire
                     • Interface moderne et responsive
                     • Upload par drag & drop
                     • Progression en temps réel
                   
                   📊 **Analyses et Reporting**
                     • Tableaux de bord interactifs
                     • Statistiques détaillées par partenaire
                     • Exports Excel et PDF
                     • Alertes intelligentes
                   
                   🔔 **Notifications Intelligentes**
                     • Emails automatiques personnalisés
                     • Rappels d'expiration configurables
                     • Préférences utilisateur avancées
                     • Templates modernes et responsive
                   
                   🛡️ **Sécurité et Conformité**
                     • Archivage sécurisé des documents
                     • Audit trail complet
                     • Gestion des droits granulaire
                     • Conformité RGPD
                   
                   Ce module étend construction_core pour offrir une solution complète
                   de gestion des partenaires sous-traitants dans le secteur du BTP.
''',

    # Informations sur l'auteur et la société
    'author': 'BLG Groupe',
    'website': 'https://www.blggroupe.com',
    'maintainer': 'BLG Groupe Development Team',
    'support': 'support@blggroupe.com',

    # Dépendances
    'depends': [
        # Modules Odoo de base
        'base',
        'mail',
        'portal',
        'web',
        'attachment_indexation',
        # Module principal construction
        'construction_core',
        'construction_base',
        'construction_lots',
        'website',
        'sms',
    ],

    # Fichiers de données et configuration
    'data': [
        # === SÉCURITÉ ===
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'security/record_rules.xml',

        # === DONNÉES DE BASE ===
        'data/document_types_data.xml',
        'data/email_templates.xml',
        'data/notification_templates.xml',
        'data/cron_jobs.xml',
        'data/ir_sequence.xml',
        'data/mail_template.xml',

        # === VUES PRINCIPALES ===
        # Modèles de base
        'views/res_partner_views.xml',
        'views/partner_document_views.xml',
        'views/document_type_views.xml',
        'views/document_archive_views.xml',

        # === VUES DES WIZARDS ===
        'views/wizards/portal_link_wizard_views.xml',
        'views/wizards/partner_document_stats_wizard_views.xml',
        'views/wizards/bulk_operations_wizard_views.xml',
        'views/wizards/document_rejection_wizard_views.xml',
        'views/wizards/document_restore_wizard_views.xml',
        'views/wizards/archive_permanent_delete_wizard_views.xml',

        # === TEMPLATES PORTAIL ===
        'templates/portal_templates.xml',
        'templates/email_templates.xml',
        'templates/assets_templates.xml',

        # === RAPPORTS ===
        'reports/partner_document_reports.xml',
        'reports/statistics_reports.xml',
        'reports/portal_instructions_report.xml',

        # === ACTIONS ET MENUS ===
        'views/actions.xml',
        'views/menus.xml',

        # === CONFIGURATION ===
        'data/res_config_settings_data.xml',
        'data/ir_config_parameter.xml',
    ],

    # Configuration du module
    'installable': True,
    'auto_install': False,
    'application': True,  # Module principal
    'license': 'LGPL-3',
}
