# -*- coding: utf-8 -*-
{
    'name': 'Construction Contract Management',
    'version': '18.0.1.1.0',
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
        'construction_core',  # Core chantier and lot models
        'contacts',  # Provides partner model for subcontractors
        'purchase',
        'construction_purchase',
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
        'data/default_contract_template_data.xml',
        'data/urssaf_codes.xml',

        # Views (template views first - defines actions referenced by contract_views)
        'views/contract_template_views.xml',  # Defines actions
        'views/contract_views.xml',           # References template actions
        'views/chantier_views.xml',
        'views/urssaf_code_views.xml',
        'views/menus.xml',
        'views/purchase_order_views.xml',
        'views/lot_extension_views.xml',

        # Wizards
        'wizards/views/contract_creation_wizard_views.xml',
        'wizards/views/deliverable_selector_wizard_views.xml',
        'wizards/views/contract_send_wizard_views.xml',
        'wizards/views/lot_grouping_wizard_views.xml',
        'wizards/views/contract_validation_wizard_views.xml',
        'wizards/views/compliance_warning_wizard_views.xml',
        'wizards/views/compliance_override_wizard_views.xml',

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
        'web.assets_frontend': [
            'construction_contract/static/src/components/portal_signature/portal_signature.js',
            'construction_contract/static/src/components/portal_signature/portal_signature.xml',
        ],
        'web.assets_backend': [
            'construction_contract/static/src/js/urssaf_code_selector.js',
            'construction_contract/static/src/xml/urssaf_code_selector.xml',
            'construction_contract/static/src/css/urssaf_code_selector.css',
            'construction_contract/static/src/components/contract_editor/contract_editor.js',
            'construction_contract/static/src/components/contract_editor/contract_editor.xml',
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
            'construction_contract/static/src/scss/contract_builder.scss',
        ],
    },

    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}
