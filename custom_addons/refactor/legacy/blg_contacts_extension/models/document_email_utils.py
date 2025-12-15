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

    if partner.disable_document_emails and notification_type != 'request':
        # Still allow manual requests even if automatic notifications are disabled
        return False

    # Generate upload URL with appropriate context for rib_request or reminder
    upload_context = {}
    if notification_type == 'rib_request':
        upload_context['rib_request'] = True
    elif notification_type == 'request': # This is for general missing docs reminder
        upload_context['reminder'] = True
    
    upload_url = partner.sudo().with_context(**upload_context)._generate_upload_token_details()

    # Select appropriate template
    template_xml_id = {
        'expiry': 'blg_contacts_extension.email_template_document_expiry',
        'rejection': 'blg_contacts_extension.email_template_document_rejection',
        'request': 'blg_contacts_extension.email_template_manual_document_request',
        'rib_request': 'blg_contacts_extension.email_template_rib_request'
    }.get(notification_type)
    
    if not template_xml_id:
        _logger.error(f"Unknown notification type: {notification_type}")
        return False
        
    email_template = partner.env.ref(template_xml_id, raise_if_not_found=False)
    if not email_template:
        _logger.error(f"Email template '{template_xml_id}' not found.")
        return False
    
    # Prepare context and email values
    context = {'upload_url': upload_url}
    email_values = {'email_to': partner.email}
    
    # Add notification-specific values
    if notification_type == 'expiry':
        doc_config = kwargs.get('doc_config')
        expiry_date = kwargs.get('expiry_date')
        status = kwargs.get('status')
        is_expired = kwargs.get('is_expired', False)
        
        formatted_expiry_date = expiry_date.strftime('%d/%m/%Y') if isinstance(expiry_date, date) else expiry_date
        context.update({
            'doc_name': doc_config['name'],
            'status': status,
            'expiry_date': formatted_expiry_date
        })
        
        # Add CCs for expiry notifications
        Employee = partner.env['hr.employee']
        conductrice_travaux = Employee.search([('job_id.name', 'ilike', 'conductrice travaux')], limit=1)
        directeur_general = Employee.search([('job_id.name', 'ilike', 'directeur général')], limit=1)
        
        cc_emails = []
        if conductrice_travaux and conductrice_travaux.work_email:
            cc_emails.append(conductrice_travaux.work_email)
        if directeur_general and directeur_general.work_email:
            cc_emails.append(directeur_general.work_email)
            
        if cc_emails:
            email_values['email_cc'] = ','.join(cc_emails)
            
    elif notification_type == 'rejection':
        context.update({
            'doc_name': kwargs.get('doc_name', ''),
            'rejection_reason': kwargs.get('rejection_reason', '')
        })
        
    elif notification_type == 'request':
        context.update({
            'documents_to_request': kwargs.get('documents_to_request', [])
        })
    elif notification_type == 'rib_request':
        context.update({})
        # Met à jour la date de notification
        partner.sudo().write({'last_notif_rib': fields.Date.today()})

    # Send email
    try:
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
