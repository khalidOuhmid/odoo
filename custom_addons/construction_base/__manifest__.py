# -*- coding: utf-8 -*-
{
    'name': 'BLG Groupe - Construction Base',
    'version': '1.0.1',
    'summary': 'Gestion des chantiers de construction',
    'description': """
                           Module pour la gestion des chantiers de construction,
                           incluant la gestion des lots, sous-traitants, devis,
                           planning et contrats pour les projets BLG Groupe.
                       """,
    'category': 'Construction',
    'author': 'BLG Groupe',
    'website': 'https://www.blggroupe.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'contacts',
        'construction_lots',
        'blg_contacts_extension',
        'sale',
        'mail',
        'account',
        'web_gantt',
        'purchase'
    ],
    'data': [
        # Sécurité
        'security/security.xml',
        'security/construction_security.xml',
        'security/ir.model.access.csv',

        # Rapports (templates d'abord, puis actions)
        'reports/contract_header_footer.xml',
        'reports/subcontractor_contract_template.xml',
        'reports/reports.xml',
        'reports/planning_report.xml',
        'reports/report_actions.xml',

        # Données
        'data/construction_data.xml',
        'data/construction_lot_data.xml',
        'data/construction_lot_template_data.xml',
        'data/suppliers_data.xml',
        'data/invoice_type_cycles.xml',
        'data/sequence_data.xml',
        'data/email_templates.xml',
        
        # Wizards
        'wizard/views/document_upload_wizard_views.xml',
        'wizard/views/lot_subquote_wizard_views.xml',
        'wizard/views/lot_subcontractor_assign_wizard_views.xml',
        'wizard/views/create_task_planning_views.xml',
        'wizard/views/quote_selection_wizard_views.xml',
        'wizard/views/force_stage_wizard_view.xml',
        'wizard/views/invoice_schedule_wizard_views.xml',
        'wizard/views/lot_document_wizard_views.xml',
        'wizard/views/contract_wizzard_views.xml',
        'wizard/views/invoice_setup_wizard_views.xml',

        # Vues principales
        'views/chantier_views.xml',
        'views/lot_views.xml',
        'views/lot_template_views.xml',
        'views/visit_views.xml',
        'views/planning_views.xml',
        'views/invoice_type_views.xml',
        'views/sale_order_line_orders_views.xml',
        'views/subcontractor_contract_views.xml',
        'views/subcontractor_contract_upload.xml',
        'views/templates.xml',
        'views/main_views.xml',
        'views/menu.xml',

        # Assets
        'views/assets.xml',

    ],
    'assets': {
        'web.assets_backend': [
            # SCSS/CSS Files
            'construction_base/static/src/scss/kanban_clean.scss',
            'construction_base/static/src/scss/chantier_views.scss',
            # JavaScript Files
            'construction_base/static/src/js/construction_kanban.js',
            'construction_base/static/src/js/planning_gantt.js',
        ],
    },
    'demo': [],
    'test': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'sequence': 1,
}
