# -*- coding: utf-8 -*-
"""
Document Fields Mixin

This mixin provides document field definitions and related computed fields
for subcontractor document management. It separates field definition concerns
from business logic.
"""

from odoo import models, fields, api
from datetime import date, timedelta
from ..document_config import DOCUMENT_TYPES


class DocumentFieldsMixin(models.AbstractModel):
    """
    Abstract mixin providing document field definitions.
    
    This mixin is responsible for defining all document-related fields
    including binary content, filenames, expiry dates, and computed statuses.
    """
    _name = 'document.fields.mixin'
    _description = 'Document Fields Mixin'

    # Document type for validation purposes
    document_type = fields.Char(
        string='Document Type',
        compute='_compute_document_type', 
        store=False,
        help="Technical field for view validation"
    )

    # Global document status flags
    has_expired_documents = fields.Boolean(
        string='Has Expired Documents',
        compute='_compute_document_status_flags', 
        store=False,
        help="True if partner has any expired documents"
    )
    
    has_expiring_documents = fields.Boolean(
        string='Has Expiring Documents',
        compute='_compute_document_status_flags', 
        store=False,
        help="True if partner has documents expiring within 30 days"
    )

    # Notification settings
    disable_document_emails = fields.Boolean(
        string="Disable Document Email Notifications",
        default=False,
        help="Check to disable email notifications for document status changes"
    )

    # Document archive relationship
    document_archive_ids = fields.One2many(
        'document.archive',
        'partner_id',
        string='Document Archives',
        help="History of all document versions"
    )

    # Upload token for secure portal access
    upload_token = fields.Char(
        string="Upload Token",
        copy=False,
        help="Secure token for document upload portal access"
    )
    
    token_expiration = fields.Datetime(
        string="Token Expiration",
        copy=False,
        help="Expiration date/time for upload token"
    )

    # Last notification tracking fields
    last_notif_expiry_identity_card = fields.Date(
        string="Last ID Card Notification",
        copy=False,
        help="Date of last expiration notification for ID card"
    )
    
    last_notif_expiry_urssaf = fields.Date(
        string="Last URSSAF Notification", 
        copy=False,
        help="Date of last expiration notification for URSSAF"
    )
    
    last_notif_expiry_kbis = fields.Date(
        string="Last KBIS Notification",
        copy=False,
        help="Date of last expiration notification for KBIS"
    )
    
    last_notif_expiry_insurance = fields.Date(
        string="Last Insurance Notification",
        copy=False,
        help="Date of last expiration notification for insurance"
    )
    
    last_notif_rib = fields.Date(
        string="Last RIB Request Notification",
        copy=False,
        help="Date of last RIB request notification"
    )

    # Dynamic document fields generation based on configuration
    def _setup_document_fields(self):
        """
        Dynamically setup document fields based on DOCUMENT_TYPES configuration.
        
        This method is called during model initialization to create all necessary
        document fields (binary, filename, expiry, status, manual_status) for
        each document type defined in the configuration.
        """
        for doc_type, config in DOCUMENT_TYPES.items():
            # Binary content field
            setattr(self.__class__, config['content_field'], fields.Binary(
                string=config['display_name'],
                attachment=True,
                help=f"{config['display_name']} document file"
            ))
            
            # Filename field  
            setattr(self.__class__, config['filename_field'], fields.Char(
                string=f"{config['display_name']} Filename",
                help=f"Filename for {config['display_name']} document"
            ))
            
            # Expiry date field (if applicable)
            if 'expiry_field' in config:
                setattr(self.__class__, config['expiry_field'], fields.Date(
                    string=f"{config['display_name']} Expiry Date",
                    help=f"Expiration date for {config['display_name']}"
                ))
            
            # Computed status field
            setattr(self.__class__, config['status_field'], fields.Selection(
                selection=[
                    ('valid', 'Valid'),
                    ('expiring', 'Expiring Soon'), 
                    ('expired', 'Expired'),
                    ('to_check', 'To Check'),
                    ('missing', 'Missing'),
                    ('rejected', 'Rejected'),
                ],
                string=f"{config['display_name']} Status",
                compute='_compute_document_statuses',
                store=False,
                help=f"Current status of {config['display_name']} document"
            ))
            
            # Manual validation status field
            setattr(self.__class__, config['manual_status_field'], fields.Selection(
                selection=[
                    ('to_check', 'To Check'),
                    ('valid', 'Valid'),
                    ('rejected', 'Rejected'),
                ],
                string=f"{config['display_name']} Manual Status",
                default='to_check',
                help=f"Manual validation status for {config['display_name']}"
            ))

    @api.depends('contact_type')
    def _compute_document_type(self):
        """Compute document type field for view validation."""
        for record in self:
            record.document_type = False

    @api.depends(*[f'document_{doc_type}_status' for doc_type in DOCUMENT_TYPES.keys()])
    def _compute_document_status_flags(self):
        """
        Compute global document status flags.
        
        Sets has_expired_documents and has_expiring_documents flags based on
        individual document statuses for efficient filtering and UI indicators.
        """
        for record in self:
            has_expired = False
            has_expiring = False
            
            for doc_type, config in DOCUMENT_TYPES.items():
                status = getattr(record, config['status_field'])
                if status == 'expired':
                    has_expired = True
                elif status == 'expiring':
                    has_expiring = True
                    
            record.has_expired_documents = has_expired
            record.has_expiring_documents = has_expiring

    @api.model
    def _init_dynamic_fields(self):
        """Initialize dynamic document fields when model is loaded."""
        self._setup_document_fields()

    def init(self):
        """Initialize the model with dynamic document fields."""
        self._init_dynamic_fields() 