"""
blg_contacts_extension.controllers.portal_upload
================================================

This module provides a secure public portal for BLG Groupe partners (subcontractors)
to upload required legal documents using a token-authenticated interface.

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

    # Configuration des types de fichiers autorisés
    ALLOWED_MIMETYPES = {
        'application/pdf': '.pdf',
        'image/jpeg': '.jpg',
        'image/png': '.png',
    }
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

    @http.route(['/documents/upload/<string:token>'], type='http', auth="public", website=True, csrf=False)
    def portal_document_upload(self, token, **kw):
        """
        Main entry point for the document upload portal.
        """
        _logger.info("Tentative d'accès à l'upload avec token: %s", token[:10] + "...")
        
        try:
            partner = self._validate_token(token)
            if not partner:
                return request.render('blg_contacts_extension.document_upload_error', {
                    'error': _("Token invalide ou expiré"),
                })

            # Get document configurations and determine which ones need to be uploaded
            doc_configs = document_config.DOCUMENT_CONFIGS
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
                })

            # Process form submission
            if request.httprequest.method == 'POST':
                return self._handle_document_submission(partner, document_context, doc_configs, kw, today)

            # Add necessary template variables
            document_context.update({
                'partner': partner,
                'today': today,
                'max_file_size_mb': self.MAX_FILE_SIZE // 1024 // 1024,
                'allowed_extensions': list(self.ALLOWED_MIMETYPES.values())
            })
            
            return request.render('blg_contacts_extension.document_upload_form', document_context)

        except Exception as e:
            _logger.error("Erreur inattendue upload: %s", e, exc_info=True)
            return request.render('blg_contacts_extension.document_upload_error', {
                'error': _("Une erreur inattendue s'est produite")
            })

    def _validate_token(self, token: str) -> Optional[Any]:
        """
        Validate the upload token and return the associated partner if valid.
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
            doc_name = config['name']
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

    def _handle_document_submission(self, partner, document_context, doc_configs, form_data, today):
        """
        Handle form submission and process documents.
        """
        processed_docs, errors = self._process_document_uploads(
            partner, 
            document_context['document_types'], 
            document_context['doc_has_expiry'],
            document_context['critical_documents'],
            document_context['doc_expired'],
            doc_configs,
            form_data,
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
                'uploaded_docs': {dt: document_context['document_types'].get(dt) for dt in processed_docs},
                'total_uploaded': len(processed_docs),
                'partner': partner,
                'all_documents_processed': critical_docs_count == 0 or critical_docs_processed >= critical_docs_count,
            })
        
        # Update context with any errors and processed documents for re-rendering the form
        document_context['error'] = errors
        document_context['uploaded_docs'] = processed_docs
        document_context.update({
            'partner': partner,
            'today': today,
            'max_file_size_mb': self.MAX_FILE_SIZE // 1024 // 1024,
            'allowed_extensions': list(self.ALLOWED_MIMETYPES.values())
        })
        
        return request.render('blg_contacts_extension.document_upload_form', document_context)

    def _process_document_uploads(self, partner, document_types, doc_has_expiry, 
                                 critical_documents, doc_expired, doc_configs, 
                                 form_data, today) -> Tuple[List[str], Dict[str, str]]:
        """
        Process uploaded documents with enhanced validation.
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
                # Validate file
                self._validate_uploaded_file(doc_file, doc_name)
                
                # Read file content
                doc_file.seek(0)
                file_content_bytes = doc_file.read()
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
                
                # Prepare and save document
                document_values = self._prepare_document_values(
                    partner, 
                    doc_type, 
                    doc_name,
                    file_content_b64,
                    config, 
                    expiry_result['expiry_date'], 
                    today
                )
                
                # Save the document
                partner.sudo().write(document_values)
                processed_docs.append(doc_type)
                _logger.info(f"Document {doc_type} successfully uploaded for partner ID {partner.id}")
                    
            except ValidationError as e:
                errors[doc_type] = str(e)
            except Exception as e:
                _logger.error(f"Unexpected error processing {doc_type} for partner {partner.id}: {str(e)}", exc_info=True)
                errors[doc_type] = f"Une erreur inattendue s'est produite: {str(e)}"
                
        return processed_docs, errors

    def _validate_uploaded_file(self, file, doc_name):
        """
        Validate an uploaded file.
        """
        # Check file size
        file.seek(0, 2)
        file_size = file.tell()
        file.seek(0)

        if file_size > self.MAX_FILE_SIZE:
            raise ValidationError(_("Fichier trop volumineux pour %s (max %sMB)") % (doc_name, self.MAX_FILE_SIZE // 1024 // 1024))

        if file_size == 0:
            raise ValidationError(_("Fichier vide pour %s") % doc_name)

        # Check MIME type
        content_type = file.content_type or 'application/octet-stream'
        if content_type not in self.ALLOWED_MIMETYPES:
            allowed_extensions = ', '.join(self.ALLOWED_MIMETYPES.values())
            raise ValidationError(_("Type de fichier non autorisé pour %s. Extensions autorisées: %s") % (doc_name, allowed_extensions))

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