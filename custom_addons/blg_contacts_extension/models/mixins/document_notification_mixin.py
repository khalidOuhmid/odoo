# -*- coding: utf-8 -*-
"""
Document Notification Mixin

This mixin provides document notification functionality including email
notifications for expiring documents, rejection notifications, and
automated reminders.
"""

from odoo import models, fields, api
from datetime import date, timedelta
import base64
import os
import urllib.parse
import logging
from ..document_config import DOCUMENT_TYPES

_logger = logging.getLogger(__name__)


class DocumentNotificationMixin(models.AbstractModel):
    """
    Abstract mixin providing document notification functionality.
    
    This mixin handles all notification-related concerns including:
    - Expiry notification management
    - Email template processing
    - Secure upload token generation
    - Notification frequency control
    """
    _name = 'document.notification.mixin'
    _description = 'Document Notification Mixin'

    def generate_secure_upload_token(self, context_params=None):
        """
        Generate a secure upload token and URL for document uploads.
        
        Args:
            context_params (dict): Optional context parameters to append to URL
            
        Returns:
            str: The generated upload URL with token
        """
        self.ensure_one()
        
        # Generate cryptographically secure token
        token = base64.b64encode(os.urandom(32)).decode('utf-8').replace('/', '_').replace('+', '-')
        token_expiration = fields.Datetime.now() + timedelta(days=7)
        
        # Update record with new token
        self.sudo().write({
            'upload_token': token,
            'token_expiration': token_expiration
        })

        # Build upload URL
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url').rstrip('/')
        safe_token = urllib.parse.quote(token, safe='')
        upload_url = f"{base_url}/documents/upload/{safe_token}"

        # Add context parameters if provided
        if context_params:
            params = []
            for key, value in context_params.items():
                if value:  # Only add truthy values
                    params.append(f"{key}={value}")
            
            if params:
                upload_url += "?" + "&".join(params)
                
        return upload_url

    def send_document_expiry_notification(self, doc_config, expiry_date, is_expired=False):
        """
        Send email notification about expiring or expired document.
        
        Args:
            doc_config (dict): Document configuration dictionary
            expiry_date (date): Document expiration date
            is_expired (bool): Whether document is already expired
        """
        self.ensure_one()
        
        if not self.email or self.disable_document_emails:
            _logger.info(
                "Skipping expiry notification for partner %s: %s",
                self.id,
                "no email" if not self.email else "notifications disabled"
            )
            return False

        # Check notification frequency to avoid spam
        if not self._should_send_expiry_notification(doc_config['key'], is_expired):
            return False

        try:
            # Generate secure upload link
            upload_url = self.generate_secure_upload_token({
                'reminder': '1',
                'doc_type': doc_config['key']
            })

            # Prepare email context
            email_context = {
                'partner_name': self.name,
                'document_name': doc_config['display_name'],
                'expiry_date': expiry_date,
                'days_until_expiry': (expiry_date - date.today()).days if not is_expired else 0,
                'is_expired': is_expired,
                'upload_url': upload_url,
                'company_name': self.env.company.name,
            }

            # Select appropriate email template
            template_ref = (
                'blg_contacts_extension.email_template_document_expired' if is_expired
                else 'blg_contacts_extension.email_template_document_expiring'
            )
            
            template = self.env.ref(template_ref, raise_if_not_found=False)
            if not template:
                _logger.error("Email template %s not found", template_ref)
                return False

            # Send email
            template.with_context(**email_context).send_mail(self.id, force_send=True)
            
            # Update last notification date
            self._update_last_notification_date(doc_config['key'], 'expiry')
            
            _logger.info(
                "Sent %s notification for %s to partner %s (%s)",
                "expiry" if is_expired else "expiring",
                doc_config['display_name'],
                self.name,
                self.email
            )
            
            return True
            
        except Exception as e:
            _logger.error(
                "Failed to send expiry notification for partner %s: %s",
                self.id, str(e), exc_info=True
            )
            return False

    def send_document_rejection_notification(self, doc_name, rejection_reason):
        """
        Send email notification about document rejection.
        
        Args:
            doc_name (str): Name of rejected document
            rejection_reason (str): Reason for rejection
        """
        self.ensure_one()
        
        if not self.email or self.disable_document_emails:
            return False

        try:
            # Generate secure upload link
            upload_url = self.generate_secure_upload_token({
                'rejection': '1',
                'doc_type': doc_name.lower().replace(' ', '_')
            })

            # Prepare email context
            email_context = {
                'partner_name': self.name,
                'document_name': doc_name,
                'rejection_reason': rejection_reason,
                'upload_url': upload_url,
                'company_name': self.env.company.name,
            }

            # Send rejection email
            template = self.env.ref(
                'blg_contacts_extension.email_template_document_rejected',
                raise_if_not_found=False
            )
            
            if template:
                template.with_context(**email_context).send_mail(self.id, force_send=True)
                
                _logger.info(
                    "Sent rejection notification for %s to partner %s (%s)",
                    doc_name, self.name, self.email
                )
                return True
            else:
                _logger.error("Document rejection email template not found")
                return False
                
        except Exception as e:
            _logger.error(
                "Failed to send rejection notification for partner %s: %s",
                self.id, str(e), exc_info=True
            )
            return False

    def send_missing_documents_request(self, missing_documents):
        """
        Send email requesting missing or rejected documents.
        
        Args:
            missing_documents (list): List of document display names
            
        Returns:
            bool: True if email was sent successfully
        """
        self.ensure_one()
        
        if not self.email or self.disable_document_emails:
            return False

        if not missing_documents:
            return False

        try:
            # Generate secure upload link
            upload_url = self.generate_secure_upload_token({'request': '1'})

            # Prepare email context
            email_context = {
                'partner_name': self.name,
                'missing_documents': missing_documents,
                'document_count': len(missing_documents),
                'upload_url': upload_url,
                'company_name': self.env.company.name,
            }

            # Send request email
            template = self.env.ref(
                'blg_contacts_extension.email_template_missing_documents_request',
                raise_if_not_found=False
            )
            
            if template:
                template.with_context(**email_context).send_mail(self.id, force_send=True)
                
                _logger.info(
                    "Sent missing documents request to partner %s (%s) for: %s",
                    self.name, self.email, ', '.join(missing_documents)
                )
                return True
            else:
                _logger.error("Missing documents request email template not found")
                return False
                
        except Exception as e:
            _logger.error(
                "Failed to send missing documents request for partner %s: %s",
                self.id, str(e), exc_info=True
            )
            return False

    def _should_send_expiry_notification(self, doc_type_key, is_expired):
        """
        Check if expiry notification should be sent based on frequency rules.
        
        Args:
            doc_type_key (str): Document type key
            is_expired (bool): Whether document is expired
            
        Returns:
            bool: True if notification should be sent
        """
        last_notif_field = f'last_notif_expiry_{doc_type_key}'
        
        if not hasattr(self, last_notif_field):
            return True
            
        last_notification = getattr(self, last_notif_field)
        
        if not last_notification:
            return True
        
        # For expired documents, send weekly reminders
        if is_expired:
            return (date.today() - last_notification).days >= 7
        
        # For expiring documents, send notification only once per month
        return (date.today() - last_notification).days >= 30

    def _update_last_notification_date(self, doc_type_key, notification_type):
        """
        Update last notification date for tracking purposes.
        
        Args:
            doc_type_key (str): Document type key
            notification_type (str): Type of notification ('expiry', 'rib')
        """
        if notification_type == 'expiry':
            field_name = f'last_notif_expiry_{doc_type_key}'
        elif notification_type == 'rib':
            field_name = 'last_notif_rib'
        else:
            return
            
        if hasattr(self, field_name):
            self.sudo().write({field_name: date.today()})

    @api.model
    def process_document_expiry_notifications(self):
        """
        Process expiry notifications for all subcontractors (typically called by cron).
        
        This method scans all subcontractors and sends appropriate notifications
        for expired or expiring documents.
        """
        today = date.today()
        warning_threshold = today + timedelta(days=30)
        
        # Find subcontractors with notifications enabled
        subcontractors = self.search([
            ('contact_type', '=', 'sous_traitant'),
            ('disable_document_emails', '=', False),
            ('email', '!=', False)
        ])
        
        _logger.info(
            'Processing document expiry notifications for %s subcontractors',
            len(subcontractors)
        )

        # Process in batches for memory efficiency
        batch_size = 100
        total_sent = 0
        
        for i in range(0, len(subcontractors), batch_size):
            batch = subcontractors[i:i + batch_size]
            
            try:
                batch_sent = self._process_expiry_notification_batch(
                    batch, today, warning_threshold
                )
                total_sent += batch_sent
                self.env.cr.commit()
                
            except Exception as e:
                _logger.error(
                    'Error processing expiry notification batch %s-%s: %s',
                    i, i + batch_size, str(e), exc_info=True
                )
                self.env.cr.rollback()

        _logger.info(
            'Completed document expiry notification processing. Sent %s notifications.',
            total_sent
        )
        
        return total_sent

    def _process_expiry_notification_batch(self, partners, today, warning_threshold):
        """
        Process a batch of partners for expiry notifications.
        
        Args:
            partners (recordset): Batch of partners to process
            today (date): Current date
            warning_threshold (date): Threshold for "expiring soon"
            
        Returns:
            int: Number of notifications sent
        """
        sent_count = 0
        
        for partner in partners:
            for doc_type, config in DOCUMENT_TYPES.items():
                # Skip documents without expiry dates
                if 'expiry_field' not in config:
                    continue
                    
                expiry_date = getattr(partner, config['expiry_field'])
                content = getattr(partner, config['content_field'])
                
                # Skip if no document or no expiry date
                if not content or not expiry_date:
                    continue
                
                # Check if notification is needed
                is_expired = expiry_date <= today
                is_expiring = not is_expired and expiry_date <= warning_threshold
                
                if is_expired or is_expiring:
                    if partner._should_send_expiry_notification(doc_type, is_expired):
                        success = partner.send_document_expiry_notification(
                            config, expiry_date, is_expired
                        )
                        if success:
                            sent_count += 1
        
        return sent_count 