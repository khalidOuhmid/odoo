"""
Document Email Utilities for BLG Groupe.

This module provides centralized email utility functions for document management,
handling notifications for expiration, rejection, and requests.

Author: BLG IT Team
"""

import logging
from odoo import fields
from datetime import date

_logger = logging.getLogger(__name__)

def send_document_notification(partner, notification_type, **kwargs):
    """
    Unified method to send document-related email notifications.
    
    Args:
        partner: The res.partner record to send notification to
        notification_type: Type of notification ('expiry', 'rejection', 'request', 'rib_request')
        **kwargs: Additional parameters depending on notification type
    
    Returns:
        bool: Success status of email sending
    """
    if not partner.email:
        _logger.warning(
            f"Partner {partner.name} ({partner.id}) has no email. Cannot send {notification_type} notification.")
        return False

    if partner.disable_document_emails and notification_type not in ['request', 'rib_request']:
        # Allow manual requests and RIB requests even if automatic notifications are disabled
        return False

    # Get the appropriate email template
    template_xml_id = {
        'expiry': 'blg_contacts_extension.email_template_document_expiry',
        'rejection': 'blg_contacts_extension.email_template_document_rejection',
        'request': 'blg_contacts_extension.email_template_document_request',
        'rib_request': 'blg_contacts_extension.email_template_rib_request',
        'documents_expiring': 'blg_contacts_extension.email_template_documents_expiring',
        'documents_expired': 'blg_contacts_extension.email_template_documents_expired'
    }.get(notification_type)
    
    if not template_xml_id:
        _logger.error(f"Unknown notification type: {notification_type}")
        return False
        
    email_template = partner.env.ref(template_xml_id, raise_if_not_found=False)
    if not email_template:
        _logger.error(
            f"Email template '{template_xml_id}' not found. "
            "Verify that the template is properly imported and the module is installed correctly.",
            exc_info=True
        )
        return False

    # Generate upload URL with appropriate context
    upload_context = {}
    if notification_type in ['rib_request', 'request']:
        upload_context['reminder' if notification_type == 'request' else 'rib_request'] = True
    
    try:
        # Prepare context data
        context = {
            'upload_url': partner.sudo().with_context(**upload_context)._generate_upload_token_details()
        }
        
        # Notification-specific context preparation
        if notification_type == 'expiry':
            doc_config = kwargs.get('doc_config')
            expiry_date = kwargs.get('expiry_date')
            status = kwargs.get('status')
            is_expired = kwargs.get('is_expired', False)
            
            formatted_expiry_date = expiry_date.strftime('%d/%m/%Y') if isinstance(expiry_date, date) else expiry_date
            context.update({
                'doc_name': doc_config.get('name', ''),
                'status': status,
                'expiry_date': formatted_expiry_date,
                'is_expired': is_expired
            })
            
            # Handle CC emails for expiry notifications
            Employee = partner.env['hr.employee']
            conductrice_travaux = Employee.search([('job_id.name', 'ilike', 'conductrice travaux')], limit=1)
            directeur_general = Employee.search([('job_id.name', 'ilike', 'directeur général')], limit=1)
            
            cc_emails = []
            if conductrice_travaux and conductrice_travaux.work_email:
                cc_emails.append(conductrice_travaux.work_email)
            if directeur_general and directeur_general.work_email:
                cc_emails.append(directeur_general.work_email)
                
        elif notification_type == 'rejection':
            context.update({
                'doc_name': kwargs.get('doc_name', ''),
                'rejection_reason': kwargs.get('rejection_reason', '')
            })
            
        elif notification_type == 'request':
            context.update({
                'documents_to_request': kwargs.get('documents_to_request', [])
            })

        # Prepare email values
        email_values = {'email_to': partner.email}
        
        # If we have CC emails and it's an expiry notification, add them
        if notification_type == 'expiry' and status == "sur le point d'expirer" and 'cc_emails' in locals() and cc_emails:
            email_values['email_cc'] = ','.join(cc_emails)
            
        # Send the email
        email_template.with_context(**context).send_mail(
            partner.id,
            email_values=email_values,
            force_send=True
        )
        
        # Update notification tracking date if applicable
        if notification_type == 'expiry' and status == "sur le point d'expirer" and not is_expired:
            partner.sudo().write({kwargs['doc_config']['last_notif_field']: fields.Date.today()})
        elif notification_type == 'rib_request':
            partner.sudo().write({'last_notif_rib': fields.Date.today()})
            
        return True
    except Exception as e:
        _logger.error(f"Failed to send {notification_type} email to {partner.name} ({partner.id}): {str(e)}",
                     exc_info=True)
        return False
