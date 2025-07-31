# -*- coding: utf-8 -*-
"""
Service de notifications spécialisé pour les partenaires
=======================================================

Étend le service de notification du core avec des fonctionnalités spécifiques
aux partenaires sous-traitants et à leurs documents.
"""

from odoo import models, api, fields
from odoo.addons.construction_core.models.services.base_service import BaseService
from odoo.addons.construction_core.utils.helpers import NotificationHelper, DateHelper, UrlHelper
from odoo.addons.construction_core.config.notification_templates import prepare_email_context
import logging

_logger = logging.getLogger(__name__)


class PartnerNotificationService(models.Model, BaseService):
    """Service de notifications pour les partenaires sous-traitants"""

    _name = 'partner.notification.service'
    _inherit = 'document.notification.service'  # Du construction_core
    _description = 'Service Notifications Partenaires'

    # =================== NOTIFICATIONS DE DOCUMENTS ===================

    def send_document_request_with_portal(self, partner, missing_docs):
        """Envoie une demande de documents avec lien portail personnalisé"""
        try:
            # Générer le token si nécessaire
            if not partner.is_token_valid():
                partner.generate_upload_token()

            # Construire l'URL du portail
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            upload_url = UrlHelper.build_portal_url(
                base_url,
                'documents/upload',
                partner.upload_token
            )

            # Préparer le contexte
            context = prepare_email_context(
                'document_missing',
                partner_name=partner.name,
                company_name=self.env.company.name,
                missing_documents=missing_docs,
                upload_link=upload_url,
                token_expiry=partner.token_expiration
            )

            # Envoyer l'email
            template = self.env.ref('construction_contact_extension.email_template_partner_document_request')
            template.with_context(**context).send_mail(partner.id, force_send=True)

            # Mettre à jour la date de dernière notification
            partner.write({'last_notification_date': fields.Datetime.now()})

            return NotificationHelper.create_odoo_notification(
                f"Demande de documents envoyée à {partner.name}",
                'success'
            )

        except Exception as e:
            _logger.error(f"Error sending document request to partner {partner.id}: {str(e)}")
            return NotificationHelper.create_odoo_notification(
                f"Erreur lors de l'envoi : {str(e)}",
                'danger'
            )

    def send_document_rejection_notification(self, partner, rejection_data):
        """Envoie une notification de rejet de document"""
        try:
            # Préparer le contexte spécifique au rejet
            context = prepare_email_context(
                'document_rejection',
                partner_name=partner.name,
                company_name=self.env.company.name,
                document_type=rejection_data['document_type'],
                rejection_reason=rejection_data['rejection_reason'],
                rejection_details=rejection_data['rejection_details'],
                required_actions=rejection_data.get('required_actions', ''),
                upload_link=rejection_data.get('upload_link', ''),
                rejection_count=rejection_data.get('rejection_count', 1)
            )

            # Template email spécialisé pour les rejets
            template = self.env.ref('construction_contact_extension.email_template_document_rejection')
            template.with_context(**context).send_mail(partner.id, force_send=True)

            return self._success_response(f"Notification de rejet envoyée à {partner.name}")

        except Exception as e:
            _logger.error(f"Error sending rejection notification: {str(e)}")
            return self._error_response(f"Erreur d'envoi : {str(e)}")

    def send_document_expiry_reminder(self, document):
        """Envoie un rappel d'expiration pour un document spécifique"""
        try:
            partner = document.partner_id

            if not partner.email or partner.notification_preferences == 'none':
                return self._info_response("Notifications désactivées pour ce partenaire")

            days_until_expiry = document.days_until_expiry

            context = prepare_email_context(
                'document_expiry',
                partner_name=partner.name,
                company_name=self.env.company.name,
                document_type=document.document_type_id.name,
                expiry_date=DateHelper.format_date_fr(document.expiry_date),
                days_until_expiry=days_until_expiry,
                urgency_level='high' if days_until_expiry <= 7 else 'medium'
            )

            template = self.env.ref('construction_contact_extension.email_template_document_expiry')
            template.with_context(**context).send_mail(partner.id, force_send=True)

            return self._success_response(f"Rappel d'expiration envoyé pour {document.document_type_id.name}")

        except Exception as e:
            _logger.error(f"Error sending expiry reminder: {str(e)}")
            return self._error_response(f"Erreur d'envoi : {str(e)}")

    # =================== NOTIFICATIONS EN LOT ===================

    def send_bulk_reminders(self, partner_ids, reminder_type='missing_documents'):
        """Envoie des rappels en lot"""
        try:
            partners = self.env['res.partner'].browse(partner_ids)
            success_count = 0
            error_count = 0

            for partner in partners:
                try:
                    if reminder_type == 'missing_documents':
                        missing_docs = partner.get_missing_documents()
                        if missing_docs:
                            result = self.send_document_request_with_portal(partner, missing_docs)
                            if result.get('params', {}).get('type') == 'success':
                                success_count += 1
                            else:
                                error_count += 1

                except Exception as e:
                    error_count += 1
                    _logger.error(f"Error sending bulk reminder to partner {partner.id}: {str(e)}")

            return NotificationHelper.create_bulk_notification(
                success_count, error_count, "Envoi de rappels"
            )

        except Exception as e:
            _logger.error(f"Error in bulk reminders: {str(e)}")
            return self._error_response(f"Erreur dans l'envoi en lot : {str(e)}")


    # =================== NOTIFICATIONS SYSTÈME ===================

    def send_archive_deletion_notification(self, partner, deletion_data):
        """Notifie la suppression définitive d'une archive"""
        try:
            context = prepare_email_context(
                'archive_deletion',
                partner_name=partner.name,
                company_name=self.env.company.name,
                archive_name=deletion_data['archive_name'],
                document_type=deletion_data['document_type'],
                deletion_reason=deletion_data['deletion_reason'],
                deletion_date=deletion_data['deletion_date'],
                reference_number=deletion_data.get('reference_number', ''),
                contact_email=deletion_data.get('contact_email', '')
            )

            template = self.env.ref('construction_contact_extension.email_template_archive_deletion')
            template.with_context(**context).send_mail(partner.id, force_send=True)

            return self._success_response("Notification de suppression envoyée")

        except Exception as e:
            _logger.error(f"Error sending deletion notification: {str(e)}")
            return self._error_response(f"Erreur d'envoi : {str(e)}")

    def send_token_expiry_warning(self, partner):
        """Avertit qu'un token va expirer"""
        try:
            if not partner.upload_token or not partner.token_expiration:
                return self._info_response("Aucun token à surveiller")

            days_until_expiry = DateHelper.get_days_until(partner.token_expiration.date())

            if days_until_expiry > 2:  # Pas d'alerte si plus de 2 jours
                return self._info_response("Token pas encore proche de l'expiration")

            context = prepare_email_context(
                'token_expiry_warning',
                partner_name=partner.name,
                company_name=self.env.company.name,
                expiry_date=DateHelper.format_date_fr(partner.token_expiration),
                days_until_expiry=days_until_expiry,
                contact_email=self.env.user.email
            )

            template = self.env.ref('construction_contact_extension.email_template_token_expiry')
            template.with_context(**context).send_mail(partner.id, force_send=True)

            return self._success_response("Avertissement d'expiration de token envoyé")

        except Exception as e:
            _logger.error(f"Error sending token expiry warning: {str(e)}")
            return self._error_response(f"Erreur d'envoi : {str(e)}")

    # =================== NOTIFICATIONS PERSONNALISÉES ===================

    def send_custom_notification(self, partner, template_key, custom_data):
        """Envoie une notification personnalisée"""
        try:
            # Fusionner les données par défaut avec les données personnalisées
            base_context = {
                'partner_name': partner.name,
                'company_name': self.env.company.name,
                'current_date': DateHelper.format_date_fr(fields.Date.today())
            }
            base_context.update(custom_data)

            context = prepare_email_context(template_key, **base_context)

            # Utiliser un template générique ou spécialisé
            template_ref = f'construction_contact_extension.email_template_{template_key}'
            try:
                template = self.env.ref(template_ref)
            except ValueError:
                # Fallback vers un template générique
                template = self.env.ref('construction_contact_extension.email_template_generic')

            template.with_context(**context).send_mail(partner.id, force_send=True)

            return self._success_response(f"Notification personnalisée envoyée à {partner.name}")

        except Exception as e:
            _logger.error(f"Error sending custom notification: {str(e)}")
            return self._error_response(f"Erreur d'envoi : {str(e)}")

    # =================== MÉTHODES DE CONFIGURATION ===================

    @api.model
    def get_notification_preferences(self, partner):
        """Retourne les préférences de notification d'un partenaire"""
        return {
            'email_enabled': bool(partner.email),
            'notification_level': partner.notification_preferences,
            'preferred_method': partner.preferred_contact_method,
            'last_notification': partner.last_notification_date,
            'can_send_now': partner._should_send_notification('general')
        }

    @api.model
    def update_notification_frequency(self, partner_ids, frequency_days):
        """Met à jour la fréquence minimale de notification"""
        try:
            # Mettre à jour un paramètre de configuration par partenaire
            # (implémentation simplifiée)
            for partner_id in partner_ids:
                partner = self.env['res.partner'].browse(partner_id)
                # Ici on pourrait stocker des préférences spécifiques
                partner.message_post(
                    body=f"Fréquence de notification mise à jour : {frequency_days} jours",
                    message_type='notification'
                )

            return self._success_response(f"Fréquence mise à jour pour {len(partner_ids)} partenaire(s)")

        except Exception as e:
            return self._error_response(f"Erreur de mise à jour : {str(e)}")

    # =================== STATISTIQUES ET REPORTING ===================

    @api.model
    def get_notification_statistics(self, date_from=None, date_to=None):
        """Retourne des statistiques sur les notifications envoyées"""
        try:
            # Rechercher dans les messages mail
            domain = [
                ('model', '=', 'res.partner'),
                ('message_type', '=', 'email')
            ]

            if date_from:
                domain.append(('date', '>=', date_from))
            if date_to:
                domain.append(('date', '<=', date_to))

            messages = self.env['mail.message'].search(domain)

            # Statistiques de base
            stats = {
                'total_sent': len(messages),
                'unique_partners': len(messages.mapped('res_id')),
                'by_type': {},
                'success_rate': 0.0,
                'average_per_day': 0.0
            }

            # Répartition par type (basée sur l'objet)
            for message in messages:
                subject = message.subject or 'Sans objet'
                if 'Documents manquants' in subject:
                    stats['by_type']['missing_docs'] = stats['by_type'].get('missing_docs', 0) + 1
                elif 'rejeté' in subject.lower():
                    stats['by_type']['rejection'] = stats['by_type'].get('rejection', 0) + 1
                elif 'expir' in subject.lower():
                    stats['by_type']['expiry'] = stats['by_type'].get('expiry', 0) + 1
                else:
                    stats['by_type']['other'] = stats['by_type'].get('other', 0) + 1

            # Calcul du taux de succès (simplifié)
            failed_messages = messages.filtered(
                lambda m: m.notification_ids.filtered(lambda n: n.notification_status == 'exception'))
            stats['success_rate'] = ((len(messages) - len(failed_messages)) / len(messages) * 100) if messages else 100

            # Moyenne par jour
            if date_from and date_to:
                days = (date_to - date_from).days + 1
                stats['average_per_day'] = len(messages) / days if days > 0 else 0

            return stats

        except Exception as e:
            _logger.error(f"Error getting notification statistics: {str(e)}")
            return {'error': str(e)}

    # =================== MÉTHODES UTILITAIRES ===================

    def _should_send_notification_to_partner(self, partner, notification_type):
        """Détermine si on peut envoyer une notification à un partenaire"""
        # Vérifications de base
        if not partner.email or partner.notification_preferences == 'none':
            return False

        # Vérifications spécifiques par type
        if notification_type == 'document_reminder':
            return partner.is_subcontractor and partner.get_missing_documents()

        elif notification_type == 'expiry_warning':
            return partner.has_expiring_documents

        elif notification_type == 'validation_result':
            return True  # Toujours notifier les résultats de validation

        return True

    def _get_partner_notification_template(self, partner, template_type):
        """Retourne le template approprié selon le partenaire et le type"""
        # Templates par défaut
        template_map = {
            'document_request': 'construction_contact_extension.email_template_partner_document_request',
            'document_rejection': 'construction_contact_extension.email_template_document_rejection',
            'document_expiry': 'construction_contact_extension.email_template_document_expiry',
        }

        # Possibilité de personnaliser selon le partenaire
        # (par exemple, templates différents selon la spécialité)

        return template_map.get(template_type, 'construction_contact_extension.email_template_generic')
