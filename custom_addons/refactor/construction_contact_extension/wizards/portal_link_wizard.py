# -*- coding: utf-8 -*-
"""
Assistant pour la génération et gestion des liens portail
========================================================

Permet de générer, afficher et envoyer les liens d'accès au portail d'upload.
"""

from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.addons.construction_core.utils.helpers import (
    SecurityHelper, NotificationHelper, DateHelper, UrlHelper
)
from odoo.addons.construction_core.utils.validators import TextValidator
import logging

_logger = logging.getLogger(__name__)


class PortalLinkWizard(models.TransientModel):
    """Assistant pour la gestion des liens portail"""

    _name = 'portal.link.wizard'
    _description = 'Assistant Lien Portail'

    # =================== CHAMPS PRINCIPAUX ===================

    partner_id = fields.Many2one(
        'res.partner',
        string='Partenaire',
        required=True,
        readonly=True,
        help="Partenaire pour lequel générer le lien"
    )

    portal_url = fields.Char(
        string='URL du portail',
        readonly=True,
        help="URL complète d'accès au portail"
    )

    short_url = fields.Char(
        string='URL courte',
        readonly=True,
        help="Version courte de l'URL pour SMS"
    )

    token_expiry = fields.Datetime(
        string='Expiration du token',
        readonly=True,
        help="Date d'expiration du token"
    )

    qr_code = fields.Binary(
        string='QR Code',
        readonly=True,
        help="QR Code pour accès mobile"
    )

    # =================== CHAMPS DE CONFIGURATION ===================

    validity_days = fields.Integer(
        string='Validité (jours)',
        default=7,
        help="Nombre de jours de validité du token"
    )

    regenerate_if_exists = fields.Boolean(
        string='Régénérer si existant',
        default=False,
        help="Régénérer le token même s'il existe déjà"
    )

    include_instructions = fields.Boolean(
        string='Inclure les instructions',
        default=True,
        help="Inclure les instructions d'utilisation"
    )

    # =================== INFORMATIONS CONTEXTUELLES ===================

    missing_documents = fields.Text(
        string='Documents manquants',
        readonly=True,
        help="Liste des documents manquants"
    )

    partner_email = fields.Char(
        string='Email du partenaire',
        related='partner_id.email',
        readonly=True
    )

    partner_phone = fields.Char(
        string='Téléphone du partenaire',
        related='partner_id.phone',
        readonly=True
    )

    document_completion_rate = fields.Float(
        string='Taux de complétion (%)',
        related='partner_id.document_completion_rate',
        readonly=True
    )

    # =================== CHAMPS CALCULÉS ===================

    can_send_email = fields.Boolean(
        string='Peut envoyer par email',
        compute='_compute_send_capabilities'
    )

    can_send_sms = fields.Boolean(
        string='Peut envoyer par SMS',
        compute='_compute_send_capabilities'
    )

    token_status = fields.Selection([
        ('none', 'Aucun token'),
        ('valid', 'Token valide'),
        ('expired', 'Token expiré'),
        ('expiring', 'Expire bientôt')
    ], string='Statut du token',
        compute='_compute_token_status')

    days_until_expiry = fields.Integer(
        string='Jours avant expiration',
        compute='_compute_token_status'
    )

    # =================== MÉTHODES CALCULÉES ===================

    @api.depends('partner_id.email', 'partner_id.phone')
    def _compute_send_capabilities(self):
        """Calcule les capacités d'envoi"""
        for wizard in self:
            # Validation email
            if wizard.partner_email:
                email_validation = TextValidator.validate_email(wizard.partner_email)
                wizard.can_send_email = email_validation['valid']
            else:
                wizard.can_send_email = False

            # Validation téléphone
            if wizard.partner_phone:
                phone_validation = TextValidator.validate_phone(wizard.partner_phone, 'FR')
                wizard.can_send_sms = phone_validation['valid']
            else:
                wizard.can_send_sms = False

    @api.depends('partner_id.upload_token', 'partner_id.token_expiration')
    def _compute_token_status(self):
        """Calcule le statut du token"""
        for wizard in self:
            partner = wizard.partner_id

            if not partner.upload_token:
                wizard.token_status = 'none'
                wizard.days_until_expiry = 0
            elif not partner.token_expiration:
                wizard.token_status = 'valid'
                wizard.days_until_expiry = 0
            else:
                days_until = DateHelper.get_days_until(partner.token_expiration.date())
                wizard.days_until_expiry = days_until

                if days_until < 0:
                    wizard.token_status = 'expired'
                elif days_until <= 2:
                    wizard.token_status = 'expiring'
                else:
                    wizard.token_status = 'valid'

    # =================== MÉTHODES DE GÉNÉRATION ===================

    @api.model
    def default_get(self, fields_list):
        """Initialise le wizard avec les données du contexte"""
        res = super().default_get(fields_list)

        # Récupérer les informations du contexte
        partner_id = self.env.context.get('default_partner_id')
        if partner_id:
            partner = self.env['res.partner'].browse(partner_id)

            # Générer ou récupérer l'URL
            portal_url = self.env.context.get('default_portal_url')
            if not portal_url:
                portal_url = self._generate_portal_url(partner)

            res.update({
                'portal_url': portal_url,
                'token_expiry': partner.token_expiration,
                'missing_documents': '\n'.join(partner.get_missing_documents()),
            })

            # Générer le QR code
            if portal_url:
                res['qr_code'] = self._generate_qr_code(portal_url)

        return res

    def _generate_portal_url(self, partner):
        """Génère l'URL du portail pour le partenaire"""
        if not partner.is_token_valid() or self.regenerate_if_exists:
            partner.generate_upload_token(self.validity_days)

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return UrlHelper.build_portal_url(
            base_url,
            'documents/upload',
            partner.upload_token
        )

    def _generate_qr_code(self, url):
        """Génère un QR code pour l'URL"""
        try:
            import qrcode
            import io
            import base64

            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(url)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")

            # Convertir en base64
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            img_str = base64.b64encode(buffer.getvalue())

            return img_str

        except ImportError:
            _logger.warning("qrcode library not available, QR code generation skipped")
            return False
        except Exception as e:
            _logger.error(f"Error generating QR code: {str(e)}")
            return False

    # =================== ACTIONS DE COPIE ===================

    def action_copy_url(self):
        """Copie l'URL dans le presse-papier (simulation)"""
        self.ensure_one()

        # Note: La copie réelle se fait côté client via JavaScript
        return NotificationHelper.create_odoo_notification(
            "URL copiée dans le presse-papier",
            'success',
            title='Copié'
        )

    def action_copy_short_url(self):
        """Copie l'URL courte"""
        self.ensure_one()

        if not self.short_url:
            # Générer une URL courte (simulation)
            self.short_url = f"https://short.ly/{self.partner_id.upload_token[:8]}"

        return NotificationHelper.create_odoo_notification(
            "URL courte copiée dans le presse-papier",
            'success',
            title='Copié'
        )

    # =================== ACTIONS D'ENVOI ===================

    def action_send_by_email(self):
        """Envoie le lien par email"""
        self.ensure_one()

        if not self.can_send_email:
            return NotificationHelper.create_odoo_notification(
                "Impossible d'envoyer par email : adresse invalide",
                'warning'
            )

        # Utiliser le service de notification
        try:
            result = self.partner_id.action_send_document_request()

            # Log de l'action
            self.partner_id.message_post(
                body=f"📧 Lien portail envoyé par email à {self.partner_email}",
                message_type='notification'
            )

            return result

        except Exception as e:
            _logger.error(f"Error sending email: {str(e)}")
            return NotificationHelper.create_odoo_notification(
                "Erreur lors de l'envoi de l'email",
                'danger'
            )

    def action_send_by_sms(self):
        """Envoie le lien par SMS"""
        self.ensure_one()

        if not self.can_send_sms:
            return NotificationHelper.create_odoo_notification(
                "Impossible d'envoyer par SMS : numéro invalide",
                'warning'
            )

        # Préparer le message SMS
        message = f"Bonjour {self.partner_id.name}, voici votre lien pour téléverser vos documents: {self.portal_url}"

        if len(message) > 160:
            # Version courte pour SMS
            if not self.short_url:
                self.short_url = f"https://short.ly/{self.partner_id.upload_token[:8]}"
            message = f"Documents à téléverser: {self.short_url}"

        try:
            # Utiliser le service SMS (si disponible)
            sms_service = self.env.get('sms.api', False)
            if sms_service:
                sms_service.send_sms(self.partner_phone, message)

                # Log de l'action
                self.partner_id.message_post(
                    body=f"📱 Lien portail envoyé par SMS au {self.partner_phone}",
                    message_type='notification'
                )

                return NotificationHelper.create_odoo_notification(
                    "SMS envoyé avec succès",
                    'success'
                )
            else:
                return NotificationHelper.create_odoo_notification(
                    "Service SMS non disponible",
                    'warning'
                )

        except Exception as e:
            _logger.error(f"Error sending SMS: {str(e)}")
            return NotificationHelper.create_odoo_notification(
                "Erreur lors de l'envoi du SMS",
                'danger'
            )

    def action_print_instructions(self):
        """Imprime les instructions avec le lien"""
        self.ensure_one()

        return {
            'type': 'ir.actions.report',
            'report_name': 'construction_contact_extension.portal_instructions_report',
            'report_type': 'qweb-pdf',
            'data': {
                'partner_id': self.partner_id.id,
                'portal_url': self.portal_url,
                'missing_documents': self.missing_documents,
                'expiry_date': self.token_expiry,
                'include_qr_code': bool(self.qr_code)
            },
            'context': {
                'active_id': self.id,
                'active_model': self._name
            }
        }

    # =================== ACTIONS DE GESTION ===================

    def action_regenerate_token(self):
        """Régénère le token"""
        self.ensure_one()

        old_token = self.partner_id.upload_token
        new_token = self.partner_id.generate_upload_token(self.validity_days)

        # Mettre à jour l'URL
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        self.portal_url = UrlHelper.build_portal_url(
            base_url,
            'documents/upload',
            new_token
        )
        self.token_expiry = self.partner_id.token_expiration

        # Régénérer le QR code
        if self.portal_url:
            self.qr_code = self._generate_qr_code(self.portal_url)

        # Log de l'action
        self.partner_id.message_post(
            body=f"🔄 Token régénéré (ancien: {old_token[:8]}..., nouveau: {new_token[:8]}...)",
            message_type='notification'
        )

        return NotificationHelper.create_odoo_notification(
            "Token régénéré avec succès",
            'success'
        )

    def action_extend_validity(self):
        """Étend la validité du token"""
        self.ensure_one()

        if not self.partner_id.upload_token:
            return NotificationHelper.create_odoo_notification(
                "Aucun token à étendre",
                'warning'
            )

        # Étendre de X jours supplémentaires
        from datetime import timedelta
        current_expiry = self.partner_id.token_expiration or fields.Datetime.now()
        new_expiry = current_expiry + timedelta(days=self.validity_days)

        self.partner_id.write({'token_expiration': new_expiry})
        self.token_expiry = new_expiry

        # Log de l'action
        self.partner_id.message_post(
            body=f"⏰ Validité du token étendue jusqu'au {DateHelper.format_date_fr(new_expiry)}",
            message_type='notification'
        )

        return NotificationHelper.create_odoo_notification(
            f"Validité étendue jusqu'au {DateHelper.format_date_fr(new_expiry)}",
            'success'
        )

    def action_revoke_token(self):
        """Révoque le token"""
        self.ensure_one()

        self.partner_id.revoke_token()

        # Réinitialiser les champs
        self.portal_url = False
        self.token_expiry = False
        self.qr_code = False

        return NotificationHelper.create_odoo_notification(
            "Token révoqué avec succès",
            'success'
        )

    # =================== ACTIONS DE PRÉVISUALISATION ===================

    def action_preview_portal(self):
        """Prévisualise le portail (ouvre dans un nouvel onglet)"""
        self.ensure_one()

        if not self.portal_url:
            return NotificationHelper.create_odoo_notification(
                "Aucune URL disponible",
                'warning'
            )

        return {
            'type': 'ir.actions.act_url',
            'url': self.portal_url,
            'target': 'new'
        }

    def action_test_upload(self):
        """Ouvre un assistant de test d'upload"""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Test Upload Portal',
            'res_model': 'portal.upload.test.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_partner_id': self.partner_id.id,
                'default_portal_url': self.portal_url,
                'default_upload_token': self.partner_id.upload_token
            }
        }

    # =================== VALIDATION ===================

    @api.constrains('validity_days')
    def _check_validity_days(self):
        """Vérifie la validité des jours"""
        for wizard in self:
            if wizard.validity_days <= 0:
                raise ValidationError("La validité doit être positive")
            if wizard.validity_days > 365:
                raise ValidationError("La validité ne peut dépasser 365 jours")

    # =================== MÉTHODES UTILITAIRES ===================

    def get_portal_statistics(self):
        """Retourne les statistiques d'utilisation du portail"""
        self.ensure_one()

        # Compter les uploads récents via ce token
        recent_messages = self.partner_id.message_ids.filtered(
            lambda m: '📄' in (m.body or '') and 'uploadé' in (m.body or '') and
                      m.date >= (fields.Datetime.now() - timedelta(days=30))
        )

        return {
            'partner_name': self.partner_id.name,
            'completion_rate': self.document_completion_rate,
            'missing_count': len(self.missing_documents.split('\n')) if self.missing_documents else 0,
            'recent_uploads': len(recent_messages),
            'token_age_days': (fields.Datetime.now() - self.partner_id.create_date).days,
            'last_activity': self.partner_id.last_activity_date
        }
