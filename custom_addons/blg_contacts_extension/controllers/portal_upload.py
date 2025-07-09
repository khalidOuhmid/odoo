"""
Secure Public Portal for Document Uploads by BLG Partners.

This module provides a secure way for subcontractors to upload required
legal documents through a token-authenticated portal interface.

Author: BLG IT Team
Last updated: 2023-12-11

Odoo 18 Compatible
"""

from odoo import http, fields, _
from odoo.http import request
import base64
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import logging
import urllib.parse
from typing import Dict, List, Optional, Tuple, Any
from odoo.exceptions import AccessError, ValidationError
from ..models import document_config

_logger = logging.getLogger(__name__)

class PortalDocumentUpload(http.Controller):
    """
    Controller handling secure document uploads through a public portal interface.
    """

    @http.route(['/documents/upload/<string:token>'], type='http', auth="public", website=True)
    def portal_document_upload(self, token, **kw):
        """
        Main entry point for the document upload portal.
        
        Args:
            token: Authentication token for identifying the partner
            kw: Additional request parameters
            
        Returns:
            Rendered template for document upload or appropriate status page
        """
        partner = self._validate_token(token)
        if not partner:
            return request.render('blg_contacts_extension.document_upload_error', {
                'datetime': datetime,
            })

        # Get document configurations and determine which ones need to be uploaded
        doc_configs = document_config.DOCUMENT_TYPES
        today = fields.Date.today()
        
        # Parse special request flags
        is_rib_request = kw.get('rib_request') == '1'
        is_reminder = kw.get('reminder') == '1'

        # Get all document statuses for the partner
        document_context = self._prepare_document_context(partner, doc_configs, today, is_rib_request, is_reminder)
        
        # If no documents need uploading, show the appropriate template
        if not document_context['document_types']:
            return request.render('blg_contacts_extension.document_upload_no_documents', {
                'partner': partner,
                'datetime': datetime,
            })

        # Process form submission
        if request.httprequest.method == 'POST':
            processed_docs, errors = self._process_document_uploads(
                partner, 
                document_context['document_types'], 
                document_context['doc_has_expiry'],
                document_context['critical_documents'],
                document_context['doc_expired'],
                doc_configs,
                kw,
                today
            )
            
            # If documents were successfully processed with no errors
            if processed_docs and not errors:
                # Calculate if all critical documents were processed
                critical_docs_count = sum(1 for doc_type in document_context['document_types'] 
                                        if document_context['critical_documents'].get(doc_type, False))
                critical_docs_processed = sum(1 for doc_type in processed_docs 
                                            if document_context['critical_documents'].get(doc_type, False))
                
                # Invalidate token if all required documents are now provided
                if critical_docs_count > 0 and critical_docs_processed >= critical_docs_count:
                    partner.sudo().write({
                        'upload_token': False,
                        'token_expiration': False
                    })
                    _logger.info(f"All {critical_docs_count} critical documents processed for partner {partner.id}. Token invalidated.")
                
                # Render success template
                return request.render('blg_contacts_extension.document_upload_success', {
                    'uploaded_docs': [document_context['document_types'].get(dt) for dt in processed_docs],
                    'all_documents_processed': critical_docs_count == 0 or critical_docs_processed >= critical_docs_count,
                    'datetime': datetime,
                })
            
            # Update context with any errors and processed documents for re-rendering the form
            document_context['error'] = errors
            document_context['uploaded_docs'] = processed_docs

        # Add necessary template variables
        document_context.update({
            'partner': partner,
            'datetime': datetime,
            'today': today,
        })
        
        return request.render('blg_contacts_extension.document_upload_form', document_context)

    def _validate_token(self, token: str) -> Optional[Any]:
        """
        Validate the upload token and return the associated partner if valid.
        
        Args:
            token: The token to validate
            
        Returns:
            The partner if token is valid, None otherwise
        """
        try:
            # Try both decoded and raw token
            decoded_token = urllib.parse.unquote(token)
            partner = request.env['res.partner'].sudo().search([
                '|',
                ('upload_token', '=', decoded_token),
                ('upload_token', '=', token)
            ], limit=1)
            
            # Check token expiration
            if not partner or not partner.token_expiration or partner.token_expiration < fields.Datetime.now():
                _logger.warning(f"Invalid or expired token: {token}")
                return None
                
            return partner
                
        except Exception as e:
            _logger.error(f"Error validating token: {str(e)}")
            return None

    def _prepare_document_context(self, partner, doc_configs, today, is_rib_request, is_reminder) -> Dict[str, Any]:
        """
        Prepare context dictionaries for document statuses.
        
        Args:
            partner: The partner for which to prepare the document context
            doc_configs: Document configuration dictionary
            today: Current date
            is_rib_request: Flag indicating if RIB document is specifically requested
            is_reminder: Flag indicating if this is a reminder request
            
        Returns:
            Dictionary containing document status information
        """
        document_types = {}
        doc_expired = {}
        doc_expiring = {}
        doc_expiry_dates = {}
        doc_days_to_expiry = {}
        doc_has_expiry = {}
        critical_documents = {}

        for doc_type, config in doc_configs.items():
            # Get document attributes
            doc_name = config['display_name_fr']
            status = getattr(partner, config['status_field'])
            manual_status = getattr(partner, config['manual_status_field'])
            expiry_field = config.get('expiry_field')
            expiry_date = getattr(partner, expiry_field) if expiry_field else None
            has_expiry = bool(expiry_field)
            
            # Determine if document should be included
            include_document = self._should_include_document(
                doc_type, status, manual_status, is_rib_request, is_reminder
            )
            
            if include_document:
                document_types[doc_type] = doc_name
                doc_has_expiry[doc_type] = has_expiry
                
                # Mark documents as critical based on status
                critical_documents[doc_type] = (
                    doc_type == 'rib' or 
                    status in ['missing', 'rejected', 'expired'] or 
                    manual_status == 'rejected'
                )
                
                # Set expiry information for documents with expiration dates
                if has_expiry and expiry_date:
                    is_expired = expiry_date < today
                    is_expiring = not is_expired and expiry_date < (today + timedelta(days=30))
                    doc_expired[doc_type] = is_expired
                    doc_expiring[doc_type] = is_expiring
                    doc_expiry_dates[doc_type] = expiry_date.strftime('%d/%m/%Y')
                    if not is_expired and expiry_date > today:
                        doc_days_to_expiry[doc_type] = (expiry_date - today).days

        return {
            'document_types': document_types,
            'doc_expired': doc_expired,
            'doc_expiring': doc_expiring,
            'doc_expiry_dates': doc_expiry_dates,
            'doc_days_to_expiry': doc_days_to_expiry,
            'doc_has_expiry': doc_has_expiry,
            'critical_documents': critical_documents,
            'error': {},
            'uploaded_docs': [],
        }
        
    def _should_include_document(self, doc_type, status, manual_status, is_rib_request, is_reminder) -> bool:
        """
        Determine if a document should be included in the upload form.
        
        Args:
            doc_type: Document type identifier
            status: Current document status
            manual_status: Manual override status
            is_rib_request: Flag indicating if RIB document is specifically requested
            is_reminder: Flag indicating if this is a reminder request
            
        Returns:
            True if document should be included, False otherwise
        """
        # Special case for RIB
        if doc_type == 'rib':
            if is_rib_request:
                return True
            if status in ['missing', 'rejected'] or manual_status == 'rejected':
                return True
            return False
            
        # For other documents
        if status in ['missing', 'rejected', 'expired']:
            return True
        if manual_status == 'rejected':
            return True
        if status == 'expiring' and is_reminder:
            return True
            
        return False

    def _process_document_uploads(self, partner, document_types, doc_has_expiry, 
                                 critical_documents, doc_expired, doc_configs, 
                                 form_data, today) -> Tuple[List[str], Dict[str, str]]:
        """
        Process uploaded documents.
        
        Args:
            partner: Partner for whom documents are being uploaded
            document_types: Dictionary of document types to process
            doc_has_expiry: Dictionary indicating which documents have expiration dates
            critical_documents: Dictionary indicating which documents are critical
            doc_expired: Dictionary indicating which documents are expired
            doc_configs: Document configuration dictionary
            form_data: Form data from request
            today: Current date
            
        Returns:
            Tuple containing list of processed document types and dictionary of errors
        """
        processed_docs = []
        errors = {}
        
        for doc_type, doc_name in document_types.items():
            config = doc_configs[doc_type]
            doc_file = request.httprequest.files.get(f'document_{doc_type}')
            
            if not doc_file:
                continue
                
            _logger.info(f"Processing upload for {doc_type} by partner ID {partner.id} ({partner.name})")
            
            try:
                # Read file content once and reuse it to avoid file pointer issues
                doc_file.seek(0)  # Make sure we're at the beginning of the file
                file_content_bytes = doc_file.read()
                if not file_content_bytes:
                    errors[doc_type] = f"Le fichier {doc_name} semble vide."
                    continue
                
                # Check file format
                original_filename = doc_file.filename
                if not original_filename.lower().endswith('.pdf'):
                    errors[doc_type] = f"Le document {doc_name} doit être un fichier PDF. Format détecté: {original_filename.split('.')[-1]}"
                    continue
                
                # Encode file content once
                file_content_b64 = base64.b64encode(file_content_bytes)
                
                # Validate expiry date if needed
                expiry_result = self._validate_expiry_date(
                    doc_type, 
                    doc_name,
                    form_data.get(f'expiry_{doc_type}'),
                    doc_has_expiry.get(doc_type, False),
                    critical_documents.get(doc_type, False),
                    doc_expired.get(doc_type, False),
                    today
                )
                
                if not expiry_result['valid']:
                    errors[doc_type] = expiry_result['error']
                    continue
                
                # Prepare and save document with proper error handling
                document_values = self._prepare_document_values(
                    partner, 
                    doc_type, 
                    doc_name,
                    file_content_b64,  # Pass encoded content instead of file object
                    config, 
                    expiry_result['expiry_date'], 
                    today
                )
                
                try:
                    # Save the document with more verbose error handling
                    partner.sudo().write(document_values)
                    processed_docs.append(doc_type)
                    _logger.info(f"Document {doc_type} successfully uploaded for partner ID {partner.id}")
                    
                except Exception as e:
                    _logger.error(f"Error writing {doc_type} to partner {partner.id}: {str(e)}", exc_info=True)
                    error_message = str(e) if str(e) else f"Erreur lors de l'enregistrement de {doc_name}"
                    errors[doc_type] = f"Erreur: {error_message}"
                    
            except Exception as e:
                _logger.error(f"Unexpected error processing {doc_type} for partner {partner.id}: {str(e)}", exc_info=True)
                errors[doc_type] = f"Une erreur inattendue s'est produite: {str(e)}"
                
        return processed_docs, errors

    def _validate_expiry_date(self, doc_type, doc_name, expiry_date_str,
                             has_expiry, is_critical, is_expired, today) -> Dict[str, Any]:
        """
        Validate document expiry date.
        
        Args:
            doc_type: Document type identifier
            doc_name: Human-readable document name
            expiry_date_str: Expiration date string from form
            has_expiry: Whether document has an expiration date
            is_critical: Whether document is critical
            is_expired: Whether document is expired
            today: Current date
            
        Returns:
            Dictionary containing validation result
        """
        result = {'valid': True, 'expiry_date': None, 'error': None}
        
        # Skip expiry validation for documents that don't need it
        if not has_expiry or doc_type in ['urssaf', 'kbis', 'rib']:
            return result
            
        # Validate date presence if required
        if (is_critical or is_expired) and not expiry_date_str:
            result['valid'] = False
            result['error'] = f"La date d'expiration est requise pour {doc_name}."
            return result
            
        # Process expiry date if provided
        if expiry_date_str:
            try:
                expiry_date = fields.Date.to_date(expiry_date_str)
                if expiry_date < today:
                    result['valid'] = False
                    result['error'] = f"La date d'expiration pour {doc_name} ne peut pas être dans le passé."
                    return result
                result['expiry_date'] = expiry_date
            except Exception as e:
                result['valid'] = False
                result['error'] = f"Format de date invalide pour {doc_name}. Format attendu: AAAA-MM-JJ."
                return result
                
        return result
        
    def _prepare_document_values(self, partner, doc_type, doc_name, file_content_b64,
                                config, expiry_date, today) -> Dict[str, Any]:
        """
        Prepare document values for saving.
        
        Args:
            partner: Partner for whom document is being saved
            doc_type: Document type identifier
            doc_name: Human-readable document name
            file_content_b64: Base64 encoded file content
            config: Document configuration
            expiry_date: Document expiration date
            today: Current date
            
        Returns:
            Dictionary of values to save
        """
        # Generate a simple, consistent filename
        partner_name_cleaned = partner.name.strip()
        
        # Fix: Don't use doc_name (which may be capitalized) for filename
        # Instead use the type identifier from configuration
        new_filename = f"{config['filename_prefix']} - {partner_name_cleaned}.pdf"
        
        # Prepare values dictionary
        values = {
            config['content_field']: file_content_b64,
            config['filename_field']: new_filename,
            config['manual_status_field']: 'to_check'
        }
        
        # Set expiry date based on document type
        expiry_field = config.get('expiry_field')
        if not expiry_field:
            return values
            
        if doc_type in ['urssaf', 'kbis']:
            values[expiry_field] = fields.Date.today() + relativedelta(months=3)
        elif doc_type != 'rib' and expiry_date:
            values[expiry_field] = expiry_date
            
        # Special handling for RIB documents (no expiry date needed)
        if doc_type == 'rib' and expiry_field and expiry_field in values:
            del values[expiry_field]
            
        return values