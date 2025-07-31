# models/mixins/document_manager_mixin.py
from odoo import models, fields, api
from datetime import date, timedelta
from ...config.document_types import DOCUMENT_TYPES, DOCUMENT_STATUSES
import logging

_logger = logging.getLogger(__name__)


class DocumentManagerMixin(models.AbstractModel):
    """
    Mixin pour la gestion des documents avec validation automatique.
    Fournit une interface standardisée pour tous les modèles ayant des documents.
    """
    _name = 'document.manager.mixin'
    _description = 'Document Management Mixin'

    # =================== CHAMPS GLOBAUX ===================

    has_expired_documents = fields.Boolean(
        string='A des documents expirés',
        compute='_compute_document_status_flags',
        store=False,
        help="True si au moins un document est expiré"
    )

    has_expiring_documents = fields.Boolean(
        string='A des documents qui expirent bientôt',
        compute='_compute_document_status_flags',
        store=False,
        help="True si au moins un document expire dans les 30 jours"
    )

    document_completion_rate = fields.Float(
        string='Taux de complétion des documents (%)',
        compute='_compute_document_completion',
        store=False,
        help="Pourcentage de documents valides"
    )

    # =================== MÉTHODES ABSTRAITES ===================

    def _get_document_config(self):
        """
        Méthode à override dans les classes filles pour définir
        quels documents sont gérés par ce modèle.

        Returns:
            dict: Configuration des documents pour ce modèle
        """
        return {}

    def _get_required_documents_for_role(self, role):
        """
        Retourne les documents requis pour un rôle donné.

        Args:
            role (str): Rôle à vérifier (ex: 'subcontractor')

        Returns:
            list: Liste des types de documents requis
        """
        config = self._get_document_config()
        return [
            doc_type for doc_type, doc_config in config.items()
            if role in doc_config.get('required_roles', [])
        ]

    # =================== MÉTHODES DE CALCUL ===================

    @api.depends()  # Les dépendances seront ajoutées dynamiquement
    def _compute_document_status_flags(self):
        """Calcule les flags globaux de statut des documents"""
        for record in self:
            has_expired = False
            has_expiring = False

            config = record._get_document_config()
            for doc_type in config.keys():
                status_field = f'document_{doc_type}_status'
                if hasattr(record, status_field):
                    status = getattr(record, status_field, 'missing')
                    if status == 'expired':
                        has_expired = True
                    elif status == 'expiring':
                        has_expiring = True

            record.has_expired_documents = has_expired
            record.has_expiring_documents = has_expiring

    @api.depends()
    def _compute_document_completion(self):
        """Calcule le taux de complétion des documents"""
        for record in self:
            config = record._get_document_config()
            if not config:
                record.document_completion_rate = 100.0
                continue

            total_docs = len(config)
            valid_docs = 0

            for doc_type in config.keys():
                status_field = f'document_{doc_type}_status'
                if hasattr(record, status_field):
                    status = getattr(record, status_field, 'missing')
                    if status == 'valid':
                        valid_docs += 1

            record.document_completion_rate = (valid_docs / total_docs) * 100 if total_docs > 0 else 0.0

    # =================== MÉTHODES UTILITAIRES ===================

    def get_missing_documents(self):
        """
        Retourne la liste des documents manquants ou expirés.

        Returns:
            list: Liste des labels des documents manquants
        """
        self.ensure_one()
        missing = []
        config = self._get_document_config()

        for doc_type, doc_config in config.items():
            status_field = f'document_{doc_type}_status'
            if hasattr(self, status_field):
                status = getattr(self, status_field, 'missing')
                if status in ['missing', 'expired', 'rejected']:
                    missing.append(doc_config['label'])
            else:
                missing.append(doc_config['label'])

        return missing

    def get_expiring_documents(self, days=30):
        """
        Retourne les documents qui expirent dans X jours.

        Args:
            days (int): Nombre de jours pour considérer un document comme "expirant"

        Returns:
            dict: Dictionnaire {doc_type: days_until_expiry}
        """
        self.ensure_one()
        expiring = {}
        config = self._get_document_config()

        for doc_type, doc_config in config.items():
            if doc_config.get('has_expiry'):
                expiry_field = f'document_{doc_type}_expiry'
                if hasattr(self, expiry_field):
                    expiry_date = getattr(self, expiry_field)
                    if expiry_date:
                        days_until_expiry = (expiry_date - date.today()).days
                        if 0 <= days_until_expiry <= days:
                            expiring[doc_type] = days_until_expiry

        return expiring

    def validate_document(self, doc_type, status='valid'):
        """
        Valide manuellement un document.

        Args:
            doc_type (str): Type de document
            status (str): Nouveau statut ('valid', 'rejected', 'to_check')
        """
        self.ensure_one()
        manual_status_field = f'document_{doc_type}_manual_status'

        if hasattr(self, manual_status_field):
            setattr(self, manual_status_field, status)

            # Log de l'action
            action = "validé" if status == 'valid' else "rejeté" if status == 'rejected' else "marqué à vérifier"
            self.message_post(
                body=f"📄 Document {doc_type} {action} par {self.env.user.name}",
                message_type='notification'
            )

    def check_documents_before_action(self, required_docs=None):
        """
        Vérifie que tous les documents requis sont valides avant une action.

        Args:
            required_docs (list): Liste des types de documents requis

        Returns:
            dict: Résultat de la vérification
        """
        self.ensure_one()

        if required_docs is None:
            config = self._get_document_config()
            required_docs = list(config.keys())

        missing = []
        expired = []

        for doc_type in required_docs:
            status_field = f'document_{doc_type}_status'
            if hasattr(self, status_field):
                status = getattr(self, status_field, 'missing')
                if status == 'missing':
                    missing.append(doc_type)
                elif status == 'expired':
                    expired.append(doc_type)

        is_valid = len(missing) == 0 and len(expired) == 0

        return {
            'is_valid': is_valid,
            'missing': missing,
            'expired': expired,
            'message': self._build_validation_message(missing, expired)
        }

    def _build_validation_message(self, missing, expired):
        """Construit le message de validation des documents"""
        messages = []

        if missing:
            config = self._get_document_config()
            missing_labels = [config[doc]['label'] for doc in missing if doc in config]
            messages.append(f"Documents manquants : {', '.join(missing_labels)}")

        if expired:
            config = self._get_document_config()
            expired_labels = [config[doc]['label'] for doc in expired if doc in config]
            messages.append(f"Documents expirés : {', '.join(expired_labels)}")

        return " | ".join(messages) if messages else "Tous les documents sont valides"

    # =================== ACTIONS PUBLIQUES ===================

    def action_send_document_reminder(self):
        """Action pour envoyer un rappel de documents manquants"""
        self.ensure_one()

        if not hasattr(self, 'email') or not self.email:
            return self._create_notification('error', "Aucune adresse email configurée")

        missing_docs = self.get_missing_documents()
        if not missing_docs:
            return self._create_notification('info', "Aucun document manquant")

        # Utiliser le service de notification
        notification_service = self.env['document.notification.service']
        result = notification_service.send_missing_documents_email(self, missing_docs)

        return result

    def action_bulk_validate_documents(self):
        """Action pour valider tous les documents en lot"""
        self.ensure_one()

        config = self._get_document_config()
        validated_count = 0

        for doc_type in config.keys():
            content_field = f'document_{doc_type}'
            if hasattr(self, content_field) and getattr(self, content_field):
                self.validate_document(doc_type, 'valid')
                validated_count += 1

        if validated_count > 0:
            message = f"{validated_count} document(s) validé(s)"
            return self._create_notification('success', message)
        else:
            return self._create_notification('warning', "Aucun document à valider")

    # =================== MÉTHODES UTILITAIRES ===================

    def _create_notification(self, notification_type, message, title=None):
        """Crée une notification standardisée"""
        type_mapping = {
            'success': 'success',
            'warning': 'warning',
            'error': 'danger',
            'info': 'info'
        }

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title or notification_type.title(),
                'message': message,
                'type': type_mapping.get(notification_type, 'info'),
                'sticky': notification_type == 'error'
            }
        }
