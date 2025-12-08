# -*- coding: utf-8 -*-
"""
Document Validation Mixin

This mixin provides document validation logic including status computation,
constraints validation, and business rules enforcement.
"""

from odoo import models, fields, api
from odoo.exceptions import ValidationError, AccessError
from datetime import date, timedelta
import logging
from ..document_config import DOCUMENT_TYPES

_logger = logging.getLogger(__name__)


class DocumentValidationMixin(models.AbstractModel):
    """
    Abstract mixin providing document validation functionality.
    
    This mixin handles all document validation concerns including:
    - Status computation based on expiry dates and manual validation
    - File format validation
    - Business rules enforcement
    - Access control validation
    """
    _name = 'document.validation.mixin'
    _description = 'Document Validation Mixin'

    @api.depends(*[config['content_field'] for config in DOCUMENT_TYPES.values()] +
                 [config['expiry_field'] for config in DOCUMENT_TYPES.values() if 'expiry_field' in config] +
                 [config['manual_status_field'] for config in DOCUMENT_TYPES.values()])
    def _compute_document_statuses(self):
        """
        Compute document statuses based on content, expiry dates, and manual validation.
        
        This method calculates the current status for each document type considering:
        - Document presence (missing if no content)
        - Manual validation status (rejected, to_check, valid)
        - Expiry date status (expired, expiring soon)
        """
        today = date.today()
        warning_threshold = today + timedelta(days=30)
        
        for record in self:
            for doc_type, config in DOCUMENT_TYPES.items():
                content = getattr(record, config['content_field'])
                expiry_field = config.get('expiry_field')
                expiry_date = getattr(record, expiry_field) if expiry_field else None
                manual_status = getattr(record, config['manual_status_field'])

                status = self._calculate_document_status(
                    content, expiry_date, manual_status, today, warning_threshold
                )
                setattr(record, config['status_field'], status)

    def _calculate_document_status(self, content, expiry_date, manual_status, today, warning_threshold):
        """
        Calculate document status based on business rules.
        
        Args:
            content: Binary document content
            expiry_date: Document expiration date
            manual_status: Manual validation status
            today: Current date
            warning_threshold: Date threshold for "expiring soon" status
            
        Returns:
            str: Document status ('missing', 'rejected', 'to_check', 'expired', 'expiring', 'valid')
        """
        if not content:
            return 'missing'
            
        if manual_status == 'rejected':
            return 'rejected'
            
        if manual_status == 'to_check':
            return 'to_check'
            
        # If no expiry date or manual status is valid, check expiry
        if not expiry_date:
            return 'valid'
            
        if expiry_date <= today:
            return 'expired'
            
        if expiry_date <= warning_threshold:
            return 'expiring'
            
        return 'valid'

    @api.constrains(*[config['filename_field'] for config in DOCUMENT_TYPES.values()])
    def _check_document_file_format(self):
        """
        Validate that uploaded documents are in PDF format.
        
        Raises:
            ValidationError: If any document is not a PDF file
        """
        for record in self:
            for config in DOCUMENT_TYPES.values():
                filename = getattr(record, config['filename_field'])
                if filename and not filename.lower().endswith('.pdf'):
                    raise ValidationError(
                        f"Only PDF files are allowed for {config['display_name']} documents. "
                        f"Please convert your file to PDF format before uploading."
                    )

    @api.constrains(*[config['content_field'] for config in DOCUMENT_TYPES.values()], 'contact_type')
    def _check_documents_only_for_subcontractors(self):
        """
        Ensure documents can only be uploaded for subcontractor contacts.
        
        Raises:
            ValidationError: If documents are uploaded for non-subcontractor contacts
        """
        for record in self:
            if record.contact_type != 'sous_traitant':
                has_documents = any(
                    getattr(record, config['content_field']) 
                    for config in DOCUMENT_TYPES.values()
                )
                if has_documents:
                    raise ValidationError(
                        "Documents can only be uploaded for contacts with type 'Subcontractor'. "
                        "Please change the contact type or remove the documents."
                    )

    def _validate_document_access_rights(self):
        """
        Validate user access rights for document management operations.
        
        Returns:
            bool: True if access is granted
            
        Raises:
            AccessError: If user doesn't have appropriate access rights
        """
        user = self.env.user
        
        # Check if user has required groups for document access
        required_groups = [
            'base.group_system',
            'blg_contacts_extension.group_conductrice_travaux',
            'blg_contacts_extension.group_directeur_general'
        ]
        
        has_access = any(user.has_group(group) for group in required_groups)
        
        if not has_access:
            raise AccessError(
                "You don't have sufficient rights to access document management features. "
                "Please contact your system administrator."
            )
        
        return True

    def _get_document_config_by_key(self, doc_type_key):
        """
        Get document configuration by document type key.
        
        Args:
            doc_type_key (str): Document type key
            
        Returns:
            dict: Document configuration or None if not found
        """
        return DOCUMENT_TYPES.get(doc_type_key)

    def _validate_document_expiry_date(self, doc_type_key, expiry_date):
        """
        Validate document expiry date business rules.
        
        Args:
            doc_type_key (str): Document type key
            expiry_date (date): Proposed expiry date
            
        Returns:
            bool: True if valid
            
        Raises:
            ValidationError: If expiry date violates business rules
        """
        if not expiry_date:
            return True
            
        today = date.today()
        
        # Don't allow expiry dates in the past for new documents
        if expiry_date < today:
            config = self._get_document_config_by_key(doc_type_key)
            doc_name = config['display_name'] if config else doc_type_key
            raise ValidationError(
                f"The expiry date for {doc_name} cannot be in the past. "
                f"Please select a future date."
            )
        
        # Warn about very short validity periods (less than 30 days)
        min_validity_days = 30
        min_date = today + timedelta(days=min_validity_days)
        
        if expiry_date < min_date:
            _logger.warning(
                "Document %s has a very short validity period (expires in %s days)",
                doc_type_key, (expiry_date - today).days
            )
        
        return True 