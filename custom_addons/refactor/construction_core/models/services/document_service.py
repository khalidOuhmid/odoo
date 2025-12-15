# models/services/document_service.py
from odoo import models, api
from .base_service import BaseService
from ...config.document_types import DOCUMENT_TYPES
from ...config.notification_templates import format_message
from datetime import date, timedelta
import logging

_logger = logging.getLogger(__name__)


class DocumentService(models.Model, BaseService):
    """Service centralisé pour la gestion des documents"""
    _name = 'document.service'
    _description = 'Document Management Service'

    # =================== VALIDATION DE DOCUMENTS ===================

    @api.model
    def validate_document_upload(self, file_data, doc_type, partner=None):
        """
        Valide un document avant upload.

        Args:
            file_data (dict): Données du fichier
            doc_type (str): Type de document
            partner: Partenaire (optionnel)

        Returns:
            dict: Résultat de la validation
        """
        try:
            # Vérifier que le type de document existe
            if doc_type not in DOCUMENT_TYPES:
                return {
                    'valid': False,
                    'error': format_message('invalid_data', 'error',
                                            details=f"Type de document '{doc_type}' non supporté")
                }

            config = DOCUMENT_TYPES[doc_type]

            # Validation de la taille
            max_size_bytes = config.get('max_size_mb', 10) * 1024 * 1024
            if file_data.get('size', 0) > max_size_bytes:
                return {
                    'valid': False,
                    'error': format_message('file_too_large', 'error',
                                            max_size=config.get('max_size_mb', 10))
                }

            # Validation du type MIME
            allowed_types = config.get('mime_types', ['application/pdf'])
            file_type = file_data.get('mime_type', '')

            if file_type not in allowed_types:
                return {
                    'valid': False,
                    'error': format_message('invalid_file_type', 'error')
                }

            # Validations spécifiques selon le type
            specific_validation = self._validate_document_specific(doc_type, file_data, partner)
            if not specific_validation['valid']:
                return specific_validation

            return {'valid': True, 'message': 'Document valide'}

        except Exception as e:
            _logger.error(f"Error validating document: {str(e)}")
            return {
                'valid': False,
                'error': "Erreur lors de la validation du document"
            }

    def _validate_document_specific(self, doc_type, file_data, partner):
        """Validations spécifiques selon le type de document"""

        # Validation spéciale pour KBIS (doit être récent)
        if doc_type == 'kbis':
            return self._validate_kbis_freshness(file_data)

        # Validation pour cartes d'identité (lecture OCR optionnelle)
        elif doc_type == 'identity_card':
            return self._validate_identity_card(file_data, partner)

        # Validation pour RIB (format IBAN)
        elif doc_type == 'rib':
            return self._validate_rib_format(file_data)

        return {'valid': True}

    def _validate_kbis_freshness(self, file_data):
        """Valide que le KBIS est récent (moins de 3 mois)"""
        # Ici on pourrait implémenter une lecture OCR pour extraire la date
        # Pour l'instant, on fait confiance à l'utilisateur
        return {'valid': True, 'warning': 'Vérifiez que le KBIS date de moins de 3 mois'}

    def _validate_identity_card(self, file_data, partner):
        """Valide une carte d'identité"""
        # Validation basique de la qualité de l'image
        if file_data.get('size', 0) < 50000:  # Moins de 50KB
            return {
                'valid': False,
                'error': 'La qualité de l\'image semble insuffisante (fichier trop petit)'
            }

        return {'valid': True}

    def _validate_rib_format(self, file_data):
        """Valide un RIB"""
        # Ici on pourrait implémenter une validation du format IBAN
        return {'valid': True}

    # =================== GESTION DES STATUTS ===================

    @api.model
    def update_document_status(self, partner, doc_type, new_status, comment=None):
        """
        Met à jour le statut d'un document.

        Args:
            partner: Enregistrement partenaire
            doc_type (str): Type de document
            new_status (str): Nouveau statut
            comment (str): Commentaire optionnel

        Returns:
            dict: Résultat de l'opération
        """
        try:
            if doc_type not in DOCUMENT_TYPES:
                return self._error_response(f"Type de document '{doc_type}' inconnu")

            config = DOCUMENT_TYPES[doc_type]
            manual_status_field = config['manual_status_field']

            # Vérifier que le statut est valide
            valid_statuses = ['to_check', 'valid', 'rejected']
            if new_status not in valid_statuses:
                return self._error_response(f"Statut '{new_status}' invalide")

            # Mettre à jour le statut
            partner.sudo().write({
                manual_status_field: new_status
            })

            # Logger l'action
            status_labels = {
                'to_check': 'à vérifier',
                'valid': 'validé',
                'rejected': 'rejeté'
            }

            message = f"📄 Document {config['label']} {status_labels[new_status]}"
            if comment:
                message += f" - {comment}"

            partner.message_post(
                body=message,
                message_type='notification'
            )

            return self._success_response(
                format_message('validation_passed', 'success')
            )

        except Exception as e:
            _logger.error(f"Error updating document status: {str(e)}")
            return self._error_response("Erreur lors de la mise à jour du statut")

    # =================== SURVEILLANCE DES EXPIRATIONS ===================

    @api.model
    def check_document_expiries(self, days_ahead=30):
        """
        Vérifie les documents qui expirent bientôt.

        Args:
            days_ahead (int): Nombre de jours à vérifier en avance

        Returns:
            dict: Résultats de la vérification
        """
        try:
            cutoff_date = date.today() + timedelta(days=days_ahead)
            expiring_partners = []

            # Rechercher tous les partenaires avec documents
            partners = self.env['res.partner'].search([
                ('is_subcontractor', '=', True)
            ])

            for partner in partners:
                expiring_docs = {}

                # Vérifier chaque type de document
                for doc_type, config in DOCUMENT_TYPES.items():
                    if not config.get('has_expiry'):
                        continue

                    expiry_field = config.get('expiry_field')
                    if not expiry_field or not hasattr(partner, expiry_field):
                        continue

                    expiry_date = getattr(partner, expiry_field)
                    if expiry_date and expiry_date <= cutoff_date:
                        days_until_expiry = (expiry_date - date.today()).days
                        expiring_docs[config['label']] = days_until_expiry

                if expiring_docs:
                    expiring_partners.append({
                        'partner': partner,
                        'documents': expiring_docs
                    })

            return {
                'success': True,
                'expiring_partners': expiring_partners,
                'count': len(expiring_partners)
            }

        except Exception as e:
            _logger.error(f"Error checking document expiries: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    @api.model
    def send_expiry_reminders(self, days_ahead=30):
        """
        Envoie des rappels d'expiration par email.

        Args:
            days_ahead (int): Nombre de jours d'avance pour les rappels

        Returns:
            dict: Résultats de l'envoi
        """
        try:
            # Récupérer les documents expirants
            check_result = self.check_document_expiries(days_ahead)
            if not check_result['success']:
                return self._error_response("Erreur lors de la vérification des expirations")

            sent_count = 0
            errors = []

            # Envoyer les rappels
            notification_service = self.env['document.notification.service']

            for item in check_result['expiring_partners']:
                partner = item['partner']
                expiring_docs = item['documents']

                try:
                    # Éviter les doublons de notification
                    if self._should_send_reminder(partner, expiring_docs):
                        result = notification_service.send_expiry_reminder(partner, expiring_docs)
                        if result.get('params', {}).get('type') == 'success':
                            sent_count += 1
                            self._update_reminder_tracking(partner, expiring_docs)
                        else:
                            errors.append(f"{partner.name}: Échec d'envoi")

                except Exception as e:
                    errors.append(f"{partner.name}: {str(e)}")

            # Résultat final
            if sent_count > 0:
                message = f"{sent_count} rappel(s) d'expiration envoyé(s)"
                if errors:
                    message += f" ({len(errors)} erreur(s))"
                return self._success_response(message)
            else:
                return self._info_response("Aucun rappel à envoyer")

        except Exception as e:
            _logger.error(f"Error sending expiry reminders: {str(e)}")
            return self._error_response("Erreur lors de l'envoi des rappels")

    def _should_send_reminder(self, partner, expiring_docs):
        """Détermine si un rappel doit être envoyé"""
        # Éviter de spammer : max 1 rappel par semaine par document
        for doc_type, days_left in expiring_docs.items():
            last_reminder_field = f'last_notif_expiry_{doc_type.lower()}'
            if hasattr(partner, last_reminder_field):
                last_reminder = getattr(partner, last_reminder_field)
                if last_reminder:
                    days_since_reminder = (date.today() - last_reminder).days
                    if days_since_reminder < 7:  # Moins d'une semaine
                        return False
        return True

    def _update_reminder_tracking(self, partner, expiring_docs):
        """Met à jour le tracking des rappels envoyés"""
        update_vals = {}
        for doc_type in expiring_docs:
            field_name = f'last_notif_expiry_{doc_type.lower()}'
            if hasattr(partner, field_name):
                update_vals[field_name] = date.today()

        if update_vals:
            partner.sudo().write(update_vals)

    # =================== RAPPORTS ET STATISTIQUES ===================

    @api.model
    def get_document_statistics(self, partner_domain=None):
        """
        Génère des statistiques sur les documents.

        Args:
            partner_domain (list): Domaine pour filtrer les partenaires

        Returns:
            dict: Statistiques des documents
        """
        try:
            if partner_domain is None:
                partner_domain = [('is_subcontractor', '=', True)]

            partners = self.env['res.partner'].search(partner_domain)
            stats = {
                'total_partners': len(partners),
                'document_stats': {},
                'global_completion': 0
            }

            # Statistiques par type de document
            for doc_type, config in DOCUMENT_TYPES.items():
                status_field = config['status_field']
                doc_stats = {
                    'valid': 0,
                    'missing': 0,
                    'expired': 0,
                    'expiring': 0,
                    'to_check': 0,
                    'rejected': 0
                }

                for partner in partners:
                    if hasattr(partner, status_field):
                        status = getattr(partner, status_field, 'missing')
                        doc_stats[status] = doc_stats.get(status, 0) + 1

                stats['document_stats'][doc_type] = {
                    'label': config['label'],
                    'stats': doc_stats,
                    'completion_rate': (doc_stats['valid'] / len(partners) * 100) if partners else 0
                }

            # Taux de complétion global
            total_valid = sum(
                doc_data['stats']['valid']
                for doc_data in stats['document_stats'].values()
            )
            total_documents = len(partners) * len(DOCUMENT_TYPES)
            stats['global_completion'] = (total_valid / total_documents * 100) if total_documents else 0

            return stats

        except Exception as e:
            _logger.error(f"Error generating document statistics: {str(e)}")
            return {'error': str(e)}
