# -*- coding: utf-8 -*-
{
    'name': 'Construction Contract Management',
    'version': '18.0.1.0.0',
    'category': 'Construction',
    'summary': 'Complete subcontractor contract management with e-signature',
    'description': """
        Construction Contract Management
        =================================

        Features:
        ---------
        * Contract creation linked to construction sites (chantiers)
        * Editable templates with GrapesJS visual editor
        * PDF generation with Jinja2 templating
        * Electronic signature workflow
        * Signature portal for subcontractors
        * Page-by-page validation enforcement
        * Email/SMS notifications
        * Legal compliance (eIDAS)
        * Certificate of completion
        * Full integration with construction_base and blg_contacts_extension
    """,
    'author': 'BLG Groupe',
    'website': 'https://www.blggroupe.com',
    'license': 'LGPL-3',

    # Module dependencies - loaded in this order
    'depends': [
        'base',
        'web',
        'mail',
        'portal',
        'sms',
        'website',
        'construction_base',  # Provides chantier, lot, planning, purchase orders
        'blg_contacts_extension',  # Provides subcontractor data and documents
    ],

    # External Python dependencies
    'external_dependencies': {
        'python': [
            'jinja2',      # Template rendering engine (required)
            'PyPDF2',      # PDF manipulation (required)
            'weasyprint',  # HTML to PDF conversion - pure Python (required)
        ],
    },

    # Data files loaded in order
    'data': [
        # Security first
        'security/contract_security.xml',
        'security/ir.model.access.csv',

        # Master data
        'data/contract_sequences.xml',
        'data/contract_variables.xml',
        'data/email_templates.xml',
        'data/sms_templates.xml',
        'data/default_contract_template.xml',
        'data/urssaf_codes.xml',

        # Views
        'views/contract_views.xml',
        'views/contract_summary_view.xml',
        'views/contract_template_views.xml',
        'views/chantier_views.xml',
        'views/urssaf_code_views.xml',
        'views/menus.xml',

        # Wizards
        'wizards/views/contract_creation_wizard_views.xml',
        'wizards/views/deliverable_selector_wizard_views.xml',

        # Reports
        'reports/contract_report.xml',
        'reports/certificate_template.xml',

        # Portal templates
        'views/portal/signature_portal_templates.xml',
        'views/portal/contract_viewer_templates.xml',
        'views/portal/contract_live_builder_templates.xml',
    ],

    # Frontend assets
    'assets': {
        'web.assets_backend': [
            'construction_contract/static/src/js/urssaf_code_selector.js',
            'construction_contract/static/src/xml/urssaf_code_selector.xml',
            'construction_contract/static/src/css/urssaf_code_selector.css',
        ],
        'construction_contract.assets_template_editor': [
            'construction_contract/static/src/lib/grapesjs/grapes.min.js',
            'construction_contract/static/src/lib/grapesjs/grapes.min.css',
            'construction_contract/static/src/lib/grapesjs/grapesjs-preset-webpage.min.js',
            'construction_contract/static/src/js/template_editor.js',
            'construction_contract/static/src/scss/template_editor.scss',
        ],
        'construction_contract.assets_signature_portal': [
            # Note: JavaScript files are loaded directly in template to avoid AMD wrapping issues
            # Only CSS is loaded via assets
            'construction_contract/static/src/scss/signature_portal.scss',
        ],
        'construction_contract.assets_contract_builder': [
            'construction_contract/static/src/js/contract_builder.js',
            'construction_contract/static/src/js/contract_builder_debug.js',
            'construction_contract/static/src/scss/contract_builder.scss',
        ],
    },

    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}
