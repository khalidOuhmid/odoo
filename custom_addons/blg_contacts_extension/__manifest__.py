# -*- coding: utf-8 -*-

{
    'name': 'BLG Contacts Extension - Subcontractor Management',
    'version': '18.0.1.0.0',
    'summary': 'Advanced subcontractor document management and integration with construction projects',
    'description': """
        This module provides comprehensive subcontractor management capabilities including:
        - Document lifecycle management with expiration tracking
        - Automated notification system for document status changes
        - Secure portal upload functionality for subcontractors
        - Integration with construction projects and lot management
        - Advanced reporting and filtering capabilities
        
        Designed for BLG construction workflow with SOLID principles and clean architecture.
    """,
    'category': 'Human Resources/Subcontractors',
    'author': 'BLG IT Team',
    'website': 'https://www.blggroupe.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'contacts',
        'mail',
        'hr',
        'construction_lots',  # Integration with standardized lot management
        'website',            # Needed for portal controller (website=True)
    ],
    'data': [
        # Security - Load first
        'security/security.xml',
        'security/ir.model.access.csv',
        
        # Data files
        'data/email_templates.xml',
        'data/cron_jobs.xml',
        
        # Views
        'views/document_archive_views.xml',
        'views/res_partner_views.xml',
        'views/portal/document_upload_form.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'blg_contacts_extension/static/src/css/portal_document_upload.css',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
    'post_init_hook': '_post_init_migrate_lots',
}
