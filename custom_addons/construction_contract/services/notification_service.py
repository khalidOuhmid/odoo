# -*- coding: utf-8 -*-
"""
Notification Service
Handles email and SMS notifications for contract workflow
Single Responsibility: Send notifications and track delivery
"""

from odoo import models, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

# Import constants
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config.contract_constants import EMAIL_RETRY_ATTEMPTS, SMS_RETRY_ATTEMPTS


class ContractNotificationService(models.AbstractModel):
    """
    Notification Service

    Responsible for:
    - Sending contract invitation emails
    - Sending SMS notifications
    - Sending reminders
    - Tracking notification delivery
    """

    _name = 'construction.contract.notification'
    _description = 'Contract Notification Service'

    # ============================================================
    # EMAIL NOTIFICATIONS
    # ============================================================

    @api.model
    def send_contract_invitation(self, contract):
        """
        Send contract invitation via email and SMS

        Args:
            contract: construction.contract record

        Returns:
            dict: Sending status
        """
        results = {
            'email_sent': False,
            'sms_sent': False,
            'errors': [],
        }

        # Send email
        try:
            self._send_email_invitation(contract)
            results['email_sent'] = True
            contract.email_sent = True
        except Exception as e:
            _logger.error(f"Failed to send email for contract {contract.name}: {e}")
            results['errors'].append(f"Email error: {str(e)}")

        # Send SMS
        try:
            self._send_sms_invitation(contract)
            results['sms_sent'] = True
            contract.sms_sent = True
        except Exception as e:
            _logger.error(f"Failed to send SMS for contract {contract.name}: {e}")
            results['errors'].append(f"SMS error: {str(e)}")

        if not results['email_sent'] and not results['sms_sent']:
            raise UserError(_(
                "Failed to send any notification:\n%s"
            ) % '\n'.join(results['errors']))

        return results

    def _send_email_invitation(self, contract):
        """
        Send email invitation with portal link

        Args:
            contract: construction.contract record
        """
        # Get email template
        template = self.env.ref(
            'construction_contract.mail_template_contract_invitation',
            raise_if_not_found=False
        )

        if not template:
            raise UserError(_("Email template 'contract_invitation' not found."))

        # Prepare context
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        portal_url = f"{base_url}/my/contract/{contract.id}/sign?access_token={contract.access_token}"

        # Send email with retry logic
        for attempt in range(EMAIL_RETRY_ATTEMPTS):
            try:
                template.with_context(
                    portal_url=portal_url,
                    contract=contract,
                ).send_mail(
                    contract.id,
                    force_send=True,
                    raise_exception=True,
                )

                _logger.info(f"Email sent successfully for contract {contract.name}")
                return

            except Exception as e:
                if attempt == EMAIL_RETRY_ATTEMPTS - 1:
                    raise
                _logger.warning(
                    f"Email send attempt {attempt + 1}/{EMAIL_RETRY_ATTEMPTS} failed: {e}"
                )

    def _send_sms_invitation(self, contract):
        """
        Send SMS invitation with portal link

        Args:
            contract: construction.contract record
        """
        # Check if subcontractor has mobile number
        if not contract.subcontractor_id.mobile:
            raise UserError(_(
                "Subcontractor '%s' has no mobile number."
            ) % contract.subcontractor_id.name)

        # Get SMS template
        template = self.env.ref(
            'construction_contract.sms_template_contract_invitation',
            raise_if_not_found=False
        )

        if not template:
            _logger.warning("SMS template not found, skipping SMS")
            return

        # Prepare short URL (you may want to use a URL shortener service)
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        portal_url = f"{base_url}/my/contract/{contract.id}/sign?access_token={contract.access_token}"

        # Build SMS message
        message = _(
            "New contract to sign for project '%s'. "
            "Open: %s"
        ) % (contract.chantier_id.name, portal_url)

        # Send SMS with retry logic
        for attempt in range(SMS_RETRY_ATTEMPTS):
            try:
                # Use Odoo SMS sending
                contract.subcontractor_id._message_sms(
                    body=message,
                    partner_ids=contract.subcontractor_id.ids,
                )

                _logger.info(f"SMS sent successfully for contract {contract.name}")
                return

            except Exception as e:
                if attempt == SMS_RETRY_ATTEMPTS - 1:
                    raise
                _logger.warning(
                    f"SMS send attempt {attempt + 1}/{SMS_RETRY_ATTEMPTS} failed: {e}"
                )

    # ============================================================
    # REMINDER NOTIFICATIONS
    # ============================================================

    @api.model
    def send_reminder(self, contract):
        """
        Send reminder for pending signature

        Args:
            contract: construction.contract record

        Returns:
            bool: True if sent successfully
        """
        if contract.state not in ['sent', 'in_progress']:
            raise UserError(_(
                "Reminders can only be sent for contracts in 'Sent' or 'In Progress' state."
            ))

        # Send reminder email
        template = self.env.ref(
            'construction_contract.mail_template_contract_reminder',
            raise_if_not_found=False
        )

        if template:
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            portal_url = f"{base_url}/my/contract/{contract.id}/sign?access_token={contract.access_token}"

            template.with_context(
                portal_url=portal_url,
                contract=contract,
            ).send_mail(contract.id, force_send=True)

        # Optional: Send reminder SMS
        if contract.subcontractor_id.mobile:
            try:
                message = _(
                    "Reminder: Contract '%s' is waiting for your signature. "
                    "Please sign it before %s."
                ) % (contract.name, contract.token_expiry_date.strftime('%d/%m/%Y'))

                contract.subcontractor_id._message_sms(
                    body=message,
                    partner_ids=contract.subcontractor_id.ids,
                )
            except Exception as e:
                _logger.warning(f"Failed to send reminder SMS: {e}")

        _logger.info(f"Reminder sent for contract {contract.name}")
        return True

    # ============================================================
    # CONFIRMATION NOTIFICATIONS
    # ============================================================

    @api.model
    def send_signature_confirmation(self, contract):
        """
        Send confirmation email after contract is signed

        Args:
            contract: construction.contract record
        """
        # Email to subcontractor
        template = self.env.ref(
            'construction_contract.mail_template_contract_signed',
            raise_if_not_found=False
        )

        if template:
            template.send_mail(contract.id, force_send=True)

        # Email to contract manager (internal notification)
        contract.message_post(
            body=_(
                "Contract '%s' has been signed by %s on %s."
            ) % (
                     contract.name,
                     contract.subcontractor_id.name,
                     contract.signature_date.strftime('%d/%m/%Y %H:%M') if contract.signature_date else ''
                 ),
            message_type='notification',
            subtype_xmlid='mail.mt_note',
        )

        # Notify chantier manager
        if contract.chantier_id.user_id:
            contract.chantier_id.message_post(
                body=_(
                    "Subcontractor contract '%s' has been signed."
                ) % contract.name,
                partner_ids=[contract.chantier_id.user_id.partner_id.id],
                message_type='notification',
            )

        _logger.info(f"Signature confirmation sent for contract {contract.name}")
