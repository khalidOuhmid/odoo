# -*- coding: utf-8 -*-
"""
Notification Service
Handles email and SMS notifications for contract workflow
Single Responsibility: Send notifications and track delivery
"""

from odoo import models, fields, api, _
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
    def send_contract_invitation(self, contract, channel=None):
        """
        Send contract invitation via email and/or SMS based on channel preference

        Args:
            contract: construction.contract record
            channel: 'email', 'sms', or 'both' (defaults to contract.communication_channel)

        Returns:
            dict: Sending status with email_sent, sms_sent, and errors
        """
        results = {
            'email_sent': False,
            'sms_sent': False,
            'errors': [],
        }

        # Validate contract has necessary data
        if not contract.subcontractor_id:
            _logger.error(f"✗ Cannot send invitation for contract {contract.name}: no subcontractor")
            raise UserError(_(
                "❌ Sous-traitant manquant\n\n"
                "Impossible d'envoyer l'invitation : aucun sous-traitant n'est associé au contrat.\n\n"
                "Veuillez sélectionner un sous-traitant avant d'envoyer l'invitation."
            ))
        
        # Determine channel to use
        channel = channel or contract.communication_channel or 'both'
        
        # Validate channel requirements
        if channel in ('email', 'both') and not contract.subcontractor_id.email:
            _logger.error(
                f"✗ Cannot send email for contract {contract.name}: "
                f"subcontractor {contract.subcontractor_id.name} has no email"
            )
            results['errors'].append(_(
                "Le sous-traitant '%s' n'a pas d'adresse email."
            ) % contract.subcontractor_id.name)
        
        if channel in ('sms', 'both') and not contract.subcontractor_id.mobile:
            _logger.warning(
                f"Cannot send SMS for contract {contract.name}: "
                f"subcontractor {contract.subcontractor_id.name} has no mobile"
            )
            results['errors'].append(_(
                "Le sous-traitant '%s' n'a pas de numéro de mobile."
            ) % contract.subcontractor_id.name)
        
        # Send email if requested
        if channel in ('email', 'both'):
            try:
                self._send_email_invitation(contract)
                results['email_sent'] = True
                contract.email_sent = True
                _logger.info(f"✓ Email invitation sent for contract {contract.name}")
            except Exception as e:
                _logger.error(
                    f"✗ Failed to send email for contract {contract.name}: {e}",
                    exc_info=True
                )
                results['errors'].append(_(
                    "Erreur d'envoi d'email : %s"
                ) % str(e))

        # Send SMS if requested
        if channel in ('sms', 'both'):
            try:
                self._send_sms_invitation(contract)
                results['sms_sent'] = True
                contract.sms_sent = True
                _logger.info(f"✓ SMS invitation sent for contract {contract.name}")
            except Exception as e:
                _logger.error(
                    f"✗ Failed to send SMS for contract {contract.name}: {e}",
                    exc_info=True
                )
                results['errors'].append(_(
                    "Erreur d'envoi de SMS : %s"
                ) % str(e))

        # Check if at least one channel succeeded
        if not results['email_sent'] and not results['sms_sent']:
            error_msg = _(
                "❌ Échec d'envoi des notifications\n\n"
                "Aucune notification n'a pu être envoyée au sous-traitant.\n\n"
                "Erreurs rencontrées :\n%s\n\n"
                "Actions recommandées :\n"
                "1. Vérifiez que le sous-traitant a une adresse email valide\n"
                "2. Vérifiez la configuration du serveur email\n"
                "3. Contactez l'administrateur si le problème persiste"
            ) % '\n'.join(results['errors'])
            raise UserError(error_msg)

        return results

    def _send_email_invitation(self, contract):
        """
        Send email invitation with portal link

        Args:
            contract: construction.contract record
        """
        # Validate email address
        if not contract.subcontractor_id.email:
            _logger.error(
                f"✗ Cannot send email invitation: subcontractor {contract.subcontractor_id.name} has no email"
            )
            raise UserError(_(
                "❌ Adresse email manquante\n\n"
                "Le sous-traitant '%s' n'a pas d'adresse email.\n\n"
                "Actions recommandées :\n"
                "1. Ajoutez une adresse email dans la fiche du sous-traitant\n"
                "2. Vérifiez que l'adresse email est valide\n"
                "3. Réessayez d'envoyer l'invitation"
            ) % contract.subcontractor_id.name)
        
        # Get email template
        template = self.env.ref(
            'construction_contract.mail_template_contract_invitation',
            raise_if_not_found=False
        )

        if not template:
            _logger.error("✗ Email template 'contract_invitation' not found")
            raise UserError(_(
                "❌ Modèle d'email manquant\n\n"
                "Le modèle d'email 'contract_invitation' est introuvable.\n\n"
                "Contactez l'administrateur système pour réinstaller le module."
            ))

        # Prepare context
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        portal_url = f"{base_url}/my/contract/{contract.id}/sign?access_token={contract.access_token}"

        # Send email with retry logic
        for attempt in range(EMAIL_RETRY_ATTEMPTS):
            try:
                template.send_mail(
                    contract.id,
                    force_send=True,
                    raise_exception=True,
                    email_values={
                        'email_to': contract.subcontractor_id.email,
                    },
                    email_layout_xmlid=False,
                    notif_layout='mail.mail_notification_light',
                )

                _logger.info(
                    f"✓ Email sent successfully for contract {contract.name} "
                    f"to {contract.subcontractor_id.email}"
                )
                return

            except Exception as e:
                if attempt == EMAIL_RETRY_ATTEMPTS - 1:
                    _logger.error(
                        f"✗ All email send attempts failed for contract {contract.name}: {e}",
                        exc_info=True
                    )
                    raise UserError(_(
                        "❌ Échec d'envoi d'email\n\n"
                        "Impossible d'envoyer l'email d'invitation après %d tentatives.\n\n"
                        "Destinataire : %s\n"
                        "Erreur : %s\n\n"
                        "Actions recommandées :\n"
                        "1. Vérifiez que l'adresse email est valide\n"
                        "2. Vérifiez la configuration du serveur email dans Paramètres > Technique > Email\n"
                        "3. Contactez l'administrateur système si le problème persiste"
                    ) % (EMAIL_RETRY_ATTEMPTS, contract.subcontractor_id.email, str(e)))
                _logger.warning(
                    f"⚠️ Email send attempt {attempt + 1}/{EMAIL_RETRY_ATTEMPTS} failed "
                    f"for contract {contract.name}: {e}"
                )

    def _send_sms_invitation(self, contract):
        """
        Send SMS invitation with portal link

        Args:
            contract: construction.contract record
        """
        # Check if subcontractor has mobile number
        if not contract.subcontractor_id.mobile:
            _logger.warning(
                f"Cannot send SMS for contract {contract.name}: "
                f"subcontractor {contract.subcontractor_id.name} has no mobile"
            )
            raise UserError(_(
                "❌ Numéro de mobile manquant\n\n"
                "Le sous-traitant '%s' n'a pas de numéro de mobile.\n\n"
                "Actions recommandées :\n"
                "1. Ajoutez un numéro de mobile dans la fiche du sous-traitant\n"
                "2. Vérifiez que le numéro est au format international (+33...)\n"
                "3. Réessayez d'envoyer l'invitation\n\n"
                "Note : L'email sera envoyé même si le SMS échoue."
            ) % contract.subcontractor_id.name)

        # Get SMS template
        template = self.env.ref(
            'construction_contract.sms_template_contract_invitation',
            raise_if_not_found=False
        )

        if not template:
            _logger.warning(
                f"SMS template 'sms_template_contract_invitation' not found, "
                f"skipping SMS for contract {contract.name}"
            )
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

                _logger.info(
                    f"✓ SMS sent successfully for contract {contract.name} "
                    f"to {contract.subcontractor_id.mobile}"
                )
                return

            except Exception as e:
                if attempt == SMS_RETRY_ATTEMPTS - 1:
                    _logger.error(
                        f"✗ All SMS send attempts failed for contract {contract.name}: {e}",
                        exc_info=True
                    )
                    raise UserError(_(
                        "❌ Échec d'envoi de SMS\n\n"
                        "Impossible d'envoyer le SMS d'invitation après %d tentatives.\n\n"
                        "Destinataire : %s\n"
                        "Erreur : %s\n\n"
                        "Actions recommandées :\n"
                        "1. Vérifiez que le numéro de mobile est valide\n"
                        "2. Vérifiez la configuration SMS dans Paramètres > Technique > SMS\n"
                        "3. Vérifiez que vous avez des crédits SMS disponibles\n"
                        "4. Contactez l'administrateur système si le problème persiste\n\n"
                        "Note : L'email a peut-être été envoyé avec succès."
                    ) % (SMS_RETRY_ATTEMPTS, contract.subcontractor_id.mobile, str(e)))
                _logger.warning(
                    f"⚠️ SMS send attempt {attempt + 1}/{SMS_RETRY_ATTEMPTS} failed "
                    f"for contract {contract.name}: {e}"
                )

    # ============================================================
    # REMINDER NOTIFICATIONS
    # ============================================================

    @api.model
    def send_reminder(self, contract, reminder_number=None, channel=None):
        """
        Send reminder for pending signature with customizable templates

        Args:
            contract: construction.contract record
            reminder_number: 1, 2, or 3 for J+7, J+14, J+21 reminders
            channel: 'email', 'sms', or 'both' (defaults to contract.communication_channel)

        Returns:
            dict: Sending status with email_sent, sms_sent, and errors
        """
        results = {
            'email_sent': False,
            'sms_sent': False,
            'errors': [],
        }
        
        # Validate contract state
        if contract.state not in ['sent', 'in_progress']:
            _logger.warning(
                f"Cannot send reminder for contract {contract.name}: "
                f"invalid state '{contract.state}'"
            )
            raise UserError(_(
                "❌ État du contrat invalide\n\n"
                "Les rappels ne peuvent être envoyés que pour les contrats "
                "dans l'état 'Envoyé' ou 'En cours'.\n\n"
                "État actuel : %s\n\n"
                "Veuillez d'abord envoyer le contrat au sous-traitant."
            ) % dict(contract._fields['state'].selection).get(contract.state, contract.state))

        # Determine channel to use
        channel = channel or contract.communication_channel or 'both'
        
        # Determine which reminder template to use
        if reminder_number == 1:
            template_suffix = '_j7'
        elif reminder_number == 2:
            template_suffix = '_j14'
        elif reminder_number == 3:
            template_suffix = '_j21'
        else:
            template_suffix = ''
        
        # Send reminder email
        if channel in ('email', 'both'):
            try:
                # Try specific reminder template first, fall back to generic
                template_xmlid = f'construction_contract.mail_template_contract_reminder{template_suffix}'
                template = self.env.ref(template_xmlid, raise_if_not_found=False)
                
                if not template:
                    # Fall back to generic reminder template
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
                        reminder_number=reminder_number,
                    ).send_mail(contract.id, force_send=True)
                    
                    results['email_sent'] = True
                    _logger.info(f"✓ Reminder email sent for contract {contract.name}")
                else:
                    _logger.warning(f"No reminder email template found for contract {contract.name}")
                    results['errors'].append(_("Modèle d'email de relance introuvable"))
                    
            except Exception as e:
                _logger.error(f"✗ Failed to send reminder email: {e}", exc_info=True)
                results['errors'].append(_(
                    "Erreur d'envoi d'email de relance : %s"
                ) % str(e))

        # Send reminder SMS
        if channel in ('sms', 'both') and contract.subcontractor_id.mobile:
            try:
                # Try specific SMS template first
                template_xmlid = f'construction_contract.sms_template_contract_reminder{template_suffix}'
                sms_template = self.env.ref(template_xmlid, raise_if_not_found=False)
                
                if not sms_template:
                    # Fall back to generic SMS reminder
                    sms_template = self.env.ref(
                        'construction_contract.sms_template_contract_reminder',
                        raise_if_not_found=False
                    )
                
                if sms_template:
                    base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                    portal_url = f"{base_url}/my/contract/{contract.id}/sign?access_token={contract.access_token}"
                    
                    # Render SMS template
                    message = sms_template._render_field(
                        'body',
                        contract.ids,
                        compute_lang=True,
                        post_process=True,
                        options={'portal_url': portal_url}
                    )[contract.id]
                else:
                    # Default SMS message
                    expiry_date = contract.token_expiry_date.strftime('%d/%m/%Y') if contract.token_expiry_date else 'N/A'
                    message = _(
                        "Rappel: Contrat '%s' en attente de signature. "
                        "Expire le %s. Signez: %s"
                    ) % (contract.name, expiry_date, portal_url)

                contract.subcontractor_id._message_sms(
                    body=message,
                    partner_ids=contract.subcontractor_id.ids,
                )
                
                results['sms_sent'] = True
                _logger.info(f"✓ Reminder SMS sent for contract {contract.name}")
                
            except Exception as e:
                _logger.warning(f"Failed to send reminder SMS: {e}")
                results['errors'].append(_(
                    "Erreur d'envoi de SMS de relance : %s"
                ) % str(e))

        # Update last reminder date
        if results['email_sent'] or results['sms_sent']:
            contract.write({
                'last_reminder_date': fields.Datetime.now(),
            })
            _logger.info(f"✓ Reminder sent for contract {contract.name}")
        
        return results

    # ============================================================
    # CONFIRMATION NOTIFICATIONS
    # ============================================================

    @api.model
    def send_signature_confirmation(self, contract, channel=None):
        """
        Send confirmation notification after contract is signed
        Notifies both the subcontractor and the gestionnaire

        Args:
            contract: construction.contract record
            channel: 'email', 'sms', or 'both' (defaults to contract.communication_channel)

        Returns:
            dict: Sending status with email_sent, sms_sent, and errors
        """
        results = {
            'email_sent': False,
            'sms_sent': False,
            'errors': [],
        }
        
        # Determine channel to use
        channel = channel or contract.communication_channel or 'email'
        
        # Send confirmation email to subcontractor
        if channel in ('email', 'both'):
            try:
                template = self.env.ref(
                    'construction_contract.mail_template_contract_signed',
                    raise_if_not_found=False
                )

                if template:
                    template.send_mail(contract.id, force_send=True)
                    results['email_sent'] = True
                    _logger.info(f"✓ Signature confirmation email sent to subcontractor for contract {contract.name}")
                else:
                    _logger.warning(f"Signature confirmation email template not found")
                    results['errors'].append(_("Modèle d'email de confirmation introuvable"))
                    
            except Exception as e:
                _logger.error(f"✗ Failed to send confirmation email: {e}", exc_info=True)
                results['errors'].append(_(
                    "Erreur d'envoi d'email de confirmation : %s"
                ) % str(e))

        # Send confirmation SMS to subcontractor
        if channel in ('sms', 'both') and contract.subcontractor_id.mobile:
            try:
                sms_template = self.env.ref(
                    'construction_contract.sms_template_contract_signed',
                    raise_if_not_found=False
                )
                
                if sms_template:
                    # Render SMS template
                    message = sms_template._render_field(
                        'body',
                        contract.ids,
                        compute_lang=True,
                        post_process=True
                    )[contract.id]
                else:
                    # Default SMS message
                    signature_date = contract.signature_date.strftime('%d/%m/%Y %H:%M') if contract.signature_date else 'N/A'
                    message = _(
                        "Contrat '%s' signé avec succès le %s. "
                        "Vous recevrez le PDF signé par email."
                    ) % (contract.name, signature_date)

                contract.subcontractor_id._message_sms(
                    body=message,
                    partner_ids=contract.subcontractor_id.ids,
                )
                
                results['sms_sent'] = True
                _logger.info(f"✓ Signature confirmation SMS sent to subcontractor for contract {contract.name}")
                
            except Exception as e:
                _logger.warning(f"Failed to send confirmation SMS: {e}")
                results['errors'].append(_(
                    "Erreur d'envoi de SMS de confirmation : %s"
                ) % str(e))

        # Internal notification to contract manager (chatter)
        try:
            signature_date_str = contract.signature_date.strftime('%d/%m/%Y %H:%M') if contract.signature_date else 'N/A'
            signer_name = contract.signature_id.signer_name if contract.signature_id else contract.subcontractor_id.name
            
            contract.message_post(
                body=_(
                    "✅ <strong>Contrat signé</strong><br/>"
                    "Signataire : %s<br/>"
                    "Date : %s<br/>"
                    "Méthode : %s"
                ) % (
                    signer_name,
                    signature_date_str,
                    dict(contract.signature_id._fields['signature_method'].selection).get(
                        contract.signature_id.signature_method, 'N/A'
                    ) if contract.signature_id else 'N/A'
                ),
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )
        except Exception as e:
            _logger.warning(f"Failed to post internal notification: {e}")

        # Notify chantier manager (gestionnaire)
        if contract.chantier_id and contract.chantier_id.user_id:
            try:
                # Send email notification to gestionnaire
                gestionnaire_template = self.env.ref(
                    'construction_contract.mail_template_contract_signed_gestionnaire',
                    raise_if_not_found=False
                )
                
                if gestionnaire_template:
                    gestionnaire_template.with_context(
                        email_to=contract.chantier_id.user_id.email,
                    ).send_mail(contract.id, force_send=True)
                    _logger.info(f"✓ Gestionnaire notification sent for contract {contract.name}")
                else:
                    # Fall back to chatter notification
                    contract.chantier_id.message_post(
                        body=_(
                            "✅ <strong>Contrat sous-traitant signé</strong><br/>"
                            "Contrat : %s<br/>"
                            "Sous-traitant : %s<br/>"
                            "Date : %s"
                        ) % (
                            contract.name,
                            contract.subcontractor_id.name,
                            signature_date_str
                        ),
                        partner_ids=[contract.chantier_id.user_id.partner_id.id],
                        message_type='notification',
                    )
                    _logger.info(f"✓ Gestionnaire chatter notification sent for contract {contract.name}")
                    
            except Exception as e:
                _logger.warning(f"Failed to notify gestionnaire: {e}")

        _logger.info(f"✓ Signature confirmation process completed for contract {contract.name}")
        return results
