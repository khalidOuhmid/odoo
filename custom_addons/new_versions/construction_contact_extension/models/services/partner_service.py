from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.addons.construction_core.models.mixins.document_manager_mixin import DocumentManagerMixin
from odoo.addons.construction_core.models.mixins.tracking_mixin import TrackingMixin
from odoo.addons.construction_core.models.services.base_service import BaseService
from odoo.addons.construction_core.utils.helpers import (
    SecurityHelper, NotificationHelper, DataHelper, DateHelper
)
from odoo.addons.construction_core.utils.validators import TextValidator, BusinessValidator
from odoo.addons.construction_core.config.document_types import DOCUMENT_TYPES
from datetime import timedelta
import logging
_logger = logging.getLogger(__name__)

class PartnerService(BaseService):
    """Service métier pour la gestion des partenaires sous-traitants."""

    def create_subcontractor(self, partner_data, speciality_ids=None):
        """Crée un sous-traitant avec validation complète."""
        try:
            # Validation des données
            required_fields = ['name', 'email']
            missing = self._validate_required_fields(partner_data, required_fields)
            if missing:
                return self._error_response(f"Champs manquants : {', '.join(missing)}")

            # Validation email
            email_validation = TextValidator.validate_email(partner_data['email'])
            if not email_validation['valid']:
                return self._error_response(f"Email invalide : {email_validation['message']}")

            # Nettoyer les données
            clean_data = {
                'name': DataHelper.clean_text(partner_data['name']),
                'email': partner_data['email'].lower().strip(),
                'phone': DataHelper.clean_text(partner_data.get('phone', '')),
                'is_subcontractor': True,
                'notification_preferences': partner_data.get('notification_preferences', 'all'),
                'preferred_contact_method': partner_data.get('preferred_contact_method', 'email')
            }

            # Créer le partenaire
            partner = self.env['res.partner'].create(clean_data)

            # Ajouter les spécialités si fournies
            if speciality_ids:
                partner.speciality_ids = [(6, 0, speciality_ids)]

            # Générer un token d'upload
            partner.generate_upload_token()

            # Log de l'opération
            from odoo.addons.construction_core.utils.helpers import LogHelper
            LogHelper.log_operation(
                'create_subcontractor',
                True,
                details={'partner_id': partner.id, 'name': partner.name},
                user_id=self.env.user.id
            )

            return self._success_response(
                f"Sous-traitant {partner.name} créé avec succès",
                data={'partner_id': partner.id, 'upload_token': partner.upload_token}
            )

        except Exception as e:
            _logger.error(f"Error creating subcontractor: {str(e)}")
            return self._error_response("Erreur lors de la création du sous-traitant")

    def bulk_update_notification_preferences(self, partner_ids, preferences):
        """Met à jour les préférences de notification en lot."""
        try:
            partners = self.env['res.partner'].browse(partner_ids)
            partners = partners.filtered('is_subcontractor')

            if not partners:
                return self._warning_response("Aucun sous-traitant trouvé")

            partners.write({'notification_preferences': preferences})

            return self._success_response(
                f"Préférences mises à jour pour {len(partners)} sous-traitant(s)"
            )

        except Exception as e:
            return self._error_response(f"Erreur : {str(e)}")