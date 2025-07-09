# -*- coding: utf-8 -*-
"""
Document Service

This service provides high-level document management operations
including validation, preview, and lifecycle management.
"""

from odoo import models, api
from odoo.exceptions import ValidationError, AccessError
import logging
from ..document_config import DOCUMENT_TYPES

_logger = logging.getLogger(__name__)


class DocumentService(models.AbstractModel):
    """
    Service class for document management operations.
    
    This service encapsulates document business logic including:
    - Document validation and approval workflows
    - Preview and download operations
    - Document lifecycle management
    - Integration with archive system
    """
    _name = 'document.service'
    _description = 'Document Management Service'

    @api.model
    def validate_document(self, partner_id, doc_type_key, reset=False):
        """
        Validate or reset validation status for a document.
        
        Args:
            partner_id (int): Partner record ID
            doc_type_key (str): Document type key
            reset (bool): If True, reset status to 'to_check'
            
        Returns:
            dict: Result with success status and message
        """
        try:
            partner = self.env['res.partner'].browse(partner_id)
            if not partner.exists():
                return {'success': False, 'message': 'Partner not found'}

            # Validate access rights
            partner._validate_document_access_rights()
            
            # Get document configuration
            config = partner._get_document_config_by_key(doc_type_key)
            if not config:
                return {'success': False, 'message': 'Invalid document type'}

            # Check if document exists
            content = getattr(partner, config['content_field'])
            if not content:
                return {'success': False, 'message': 'No document uploaded'}

            # Update manual status
            manual_status_field = config['manual_status_field']
            new_status = 'to_check' if reset else 'valid'
            
            partner.write({manual_status_field: new_status})

            # Archive previous version if validating
            if not reset:
                self._archive_document_version(partner, config, 'validation')

            action_msg = 'reset to check' if reset else 'validated'
            return {
                'success': True,
                'message': f'Document {action_msg} successfully',
                'notification_type': 'info' if reset else 'success'
            }

        except (AccessError, ValidationError) as e:
            return {'success': False, 'message': str(e)}
        except Exception as e:
            _logger.error("Error validating document: %s", str(e), exc_info=True)
            return {'success': False, 'message': 'Internal error occurred'}

    @api.model
    def reject_document(self, partner_id, doc_type_key, rejection_reason=None):
        """
        Reject a document and send notification.
        
        Args:
            partner_id (int): Partner record ID
            doc_type_key (str): Document type key
            rejection_reason (str, optional): Reason for rejection
            
        Returns:
            dict: Result with success status and message
        """
        try:
            partner = self.env['res.partner'].browse(partner_id)
            if not partner.exists():
                return {'success': False, 'message': 'Partner not found'}

            # Validate access rights
            partner._validate_document_access_rights()
            
            # Get document configuration
            config = partner._get_document_config_by_key(doc_type_key)
            if not config:
                return {'success': False, 'message': 'Invalid document type'}

            # Check if document exists
            content = getattr(partner, config['content_field'])
            if not content:
                return {'success': False, 'message': 'No document to reject'}

            # Update manual status
            manual_status_field = config['manual_status_field']
            partner.write({manual_status_field: 'rejected'})

            # Archive rejected version
            self._archive_document_version(partner, config, 'rejection')

            # Send rejection notification
            reason = rejection_reason or "Document incorrect or incomplete"
            notification_sent = partner.send_document_rejection_notification(
                config['display_name'], reason
            )

            message = f"Document rejected successfully"
            if notification_sent:
                message += " and notification email sent"

            return {
                'success': True,
                'message': message,
                'notification_type': 'warning'
            }

        except (AccessError, ValidationError) as e:
            return {'success': False, 'message': str(e)}
        except Exception as e:
            _logger.error("Error rejecting document: %s", str(e), exc_info=True)
            return {'success': False, 'message': 'Internal error occurred'}

    @api.model
    def preview_document(self, partner_id, doc_type_key):
        """
        Generate document preview URL.
        
        Args:
            partner_id (int): Partner record ID
            doc_type_key (str): Document type key
            
        Returns:
            dict: Action dictionary for document preview
        """
        try:
            partner = self.env['res.partner'].browse(partner_id)
            if not partner.exists():
                return False

            # Validate access rights
            partner._validate_document_access_rights()
            
            # Get document configuration
            config = partner._get_document_config_by_key(doc_type_key)
            if not config:
                return False

            # Check if document exists
            content = getattr(partner, config['content_field'])
            if not content:
                return False

            # Generate preview URL
            field_name = config['content_field']
            filename_field = config['filename_field']
            filename = getattr(partner, filename_field) or f'{doc_type_key}.pdf'

            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content?model=res.partner&field={field_name}&id={partner_id}&filename={filename}',
                'target': 'new',
            }

        except (AccessError, ValidationError) as e:
            _logger.warning("Document preview access denied: %s", str(e))
            return False
        except Exception as e:
            _logger.error("Error generating document preview: %s", str(e), exc_info=True)
            return False

    @api.model
    def send_missing_documents_request(self, partner_id):
        """
        Send email requesting missing or rejected documents.
        
        Args:
            partner_id (int): Partner record ID
            
        Returns:
            dict: Result with success status and message
        """
        try:
            partner = self.env['res.partner'].browse(partner_id)
            if not partner.exists():
                return {'success': False, 'message': 'Partner not found'}

            if not partner.email:
                return {
                    'success': False,
                    'message': 'Partner has no email address configured'
                }

            # Find missing or rejected documents
            missing_documents = []
            for doc_type, config in DOCUMENT_TYPES.items():
                status = getattr(partner, config['status_field'])
                manual_status = getattr(partner, config['manual_status_field'])
                
                if status == 'missing' or manual_status == 'rejected':
                    missing_documents.append(config['display_name'])

            if not missing_documents:
                return {
                    'success': False,
                    'message': 'No missing or rejected documents to request'
                }

            # Send request email
            success = partner.send_missing_documents_request(missing_documents)
            
            if success:
                return {
                    'success': True,
                    'message': f"Request sent for: {', '.join(missing_documents)}",
                    'notification_type': 'success'
                }
            else:
                return {
                    'success': False,
                    'message': 'Failed to send email request'
                }

        except Exception as e:
            _logger.error("Error sending missing documents request: %s", str(e), exc_info=True)
            return {'success': False, 'message': 'Internal error occurred'}

    def _archive_document_version(self, partner, config, action_type):
        """
        Archive a document version when status changes.
        
        Args:
            partner (recordset): Partner record
            config (dict): Document configuration
            action_type (str): Type of action ('validation', 'rejection', 'upload')
        """
        try:
            content = getattr(partner, config['content_field'])
            filename = getattr(partner, config['filename_field'])
            
            if content and filename:
                archive_service = self.env['archive.service']
                archive_service.archive_document_version(
                    partner.id,
                    config['key'],
                    content,
                    filename,
                    action_type
                )
        except Exception as e:
            _logger.warning(
                "Failed to archive document version for partner %s: %s",
                partner.id, str(e)
            )

    @api.model
    def get_document_status_summary(self, partner_id):
        """
        Get comprehensive document status summary for a partner.
        
        Args:
            partner_id (int): Partner record ID
            
        Returns:
            dict: Document status summary
        """
        try:
            partner = self.env['res.partner'].browse(partner_id)
            if not partner.exists():
                return {}

            summary = {
                'total_documents': 0,
                'valid_documents': 0,
                'expired_documents': 0,
                'expiring_documents': 0,
                'missing_documents': 0,
                'rejected_documents': 0,
                'to_check_documents': 0,
                'documents': []
            }

            for doc_type, config in DOCUMENT_TYPES.items():
                status = getattr(partner, config['status_field'])
                content = getattr(partner, config['content_field'])
                expiry_field = config.get('expiry_field')
                expiry_date = getattr(partner, expiry_field) if expiry_field else None

                doc_info = {
                    'type': doc_type,
                    'display_name': config['display_name'],
                    'status': status,
                    'has_content': bool(content),
                    'expiry_date': expiry_date.isoformat() if expiry_date else None,
                }

                summary['documents'].append(doc_info)
                summary['total_documents'] += 1

                # Count by status
                if status == 'valid':
                    summary['valid_documents'] += 1
                elif status == 'expired':
                    summary['expired_documents'] += 1
                elif status == 'expiring':
                    summary['expiring_documents'] += 1
                elif status == 'missing':
                    summary['missing_documents'] += 1
                elif status == 'rejected':
                    summary['rejected_documents'] += 1
                elif status == 'to_check':
                    summary['to_check_documents'] += 1

            # Calculate compliance percentage
            compliant_docs = summary['valid_documents']
            total_with_content = summary['total_documents'] - summary['missing_documents']
            
            if total_with_content > 0:
                summary['compliance_percentage'] = round(
                    (compliant_docs / total_with_content) * 100, 1
                )
            else:
                summary['compliance_percentage'] = 0.0

            return summary

        except Exception as e:
            _logger.error(
                "Error getting document status summary for partner %s: %s",
                partner_id, str(e), exc_info=True
            )
            return {} 