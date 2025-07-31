# models/services/notification_service.py
from odoo import models, api
from .base_service import BaseService
import logging

_logger = logging.getLogger(__name__)


class DocumentNotificationService(models.Model, BaseService):
    """Service de notification pour les documents"""
    _name = 'document.notification.service'
    _description = 'Document Notification Service'

    @api.model
    def send_missing_documents_email(self, partner, missing_docs):
        """
        Envoie un email de documents manquants.

        Args:
            partner: Enregistrement partner
            missing_docs: Liste des documents manquants

        Returns:
            dict: Réponse standardisée
        """
        if not partner.email:
            return self._error_response("Aucune adresse email configurée")

        try:
            # Récupérer le template d'email
            template = self.env.ref(
                'construction_core.email_template_missing_documents',
                raise_if_not_found=False
            )

            if template:
                # Préparer le contexte
                template_context = {
                    'missing_documents': missing_docs,
                    'partner_name': partner.name,
                    'company_name': self.env.company.name
                }

                # Envoyer l'email via la file d'attente
                template.with_context(**template_context).send_mail(
                    partner.id,
                    force_send=False,
                    raise_exception=False
                )

                return self._success_response(
                    f"Email de rappel envoyé à {partner.email}"
                )
            else:
                # Fallback : message dans le chatter
                return self._send_fallback_notification(partner, missing_docs)

        except Exception as e:
            _logger.error(f"Error sending document email: {str(e)}")
            return self._error_response("Erreur lors de l'envoi de l'email")

    def _send_fallback_notification(self, partner, missing_docs):
        """Notification de secours via le chatter"""
        try:
            body = f"""
            <p>Bonjour {partner.name},</p>
            <p>Nous avons besoin des documents suivants :</p>
            <ul>
                {''.join(f'<li>{doc}</li>' for doc in missing_docs)}
            </ul>
            <p>Merci de nous les transmettre dans les meilleurs délais.</p>
            <p>Cordialement,<br/>{self.env.company.name}</p>
            """

            partner.message_post(
                subject=f"Documents manquants - {partner.name}",
                body=body,
                message_type='email',
                email_to=partner.email
            )

            return self._success_response(
                f"Notification envoyée via le chatter à {partner.email}"
            )

        except Exception as e:
            _logger.error(f"Error in fallback notification: {str(e)}")
            return self._error_response("Erreur lors de l'envoi de la notification")

    @api.model
    def send_expiry_reminders(self, days_before=30):
        """
        Envoie des rappels pour les documents qui expirent bientôt.
        Méthode appelée par un cron job.

        Args:
            days_before (int): Nombre de jours avant expiration
        """
        try:
            # Rechercher tous les partenaires avec documents expirants
            partners = self.env['res.partner'].search([
                ('has_expiring_documents', '=', True)
            ])

            sent_count = 0

            for partner in partners:
                if hasattr(partner, 'get_expiring_documents'):
                    expiring = partner.get_expiring_documents(days_before)
                    if expiring:
                        result = self._send_expiry_reminder(partner, expiring)
                        if result.get('params', {}).get('type') == 'success':
                            sent_count += 1

            _logger.info(f"Sent {sent_count} expiry reminder emails")
            return sent_count

        except Exception as e:
            _logger.error(f"Error in send_expiry_reminders: {str(e)}")
            return 0

    def _send_expiry_reminder(self, partner, expiring_docs):
        """Envoie un rappel d'expiration"""
        try:
            template = self.env.ref(
                'construction_core.email_template_document_expiry',
                raise_if_not_found=False
            )

            if template:
                template.with_context(
                    expiring_documents=expiring_docs,
                    partner_name=partner.name
                ).send_mail(partner.id, force_send=False)

                return self._success_response(f"Rappel d'expiration envoyé à {partner.email}")

            return self._warning_response("Template d'email non trouvé")

        except Exception as e:
            return self._error_response(f"Erreur : {str(e)}")
