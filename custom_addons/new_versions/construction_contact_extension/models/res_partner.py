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

class ResPartner(models.Model):
    _inherit = 'res.partner'

    # =================== CHAMPS MÉTIER ===================
    contact_type = fields.Selection([
        ('customer', 'Client'),
        ('supplier', 'Fournisseur'),
        ('sous_traitant', 'Sous-traitant'),
        ('employee', 'Employé'),
        ('other', 'Autre')
    ], string='Type de contact',
        default='customer',
        tracking=True,
        help="Type de contact pour la classification"
    )

    is_subcontractor = fields.Boolean(
        string="Sous-traitant",
        default=False,
        tracking=True,
        help="Indique si ce contact est un sous-traitant"
    )

    speciality_ids = fields.Many2many(
        'lot',
        'partner_speciality_rel',
        'partner_id',
        'lot_id',
        string='Spécialités',
        help="Corps de métier de ce sous-traitant"
    )

    upload_token = fields.Char(
        string="Token d'upload",
        copy=False,
        readonly=True,
        help="Token sécurisé pour l'upload de documents"
    )

    # =================== CHAMPS DE SÉCURITÉ ===================
    token_expiration = fields.Datetime(
        string="Expiration du token",
        copy=False,
        readonly=True,
        help="Date d'expiration du token"
    )

    # =================== CHAMPS DE NOTIFICATION ===================

    notification_preferences = fields.Selection([
        ('all', 'Toutes les notifications'),
        ('important', 'Notifications importantes uniquement'),
        ('none', 'Aucune notification')
    ], string='Préférences de notification',
        default='all',
        help="Type de notifications à recevoir")

    preferred_contact_method = fields.Selection([
        ('email', 'Email'),
        ('phone', 'Téléphone'),
        ('portal', 'Portail uniquement')
    ], string='Méthode de contact préférée',
        default='email')

    document_health_score = fields.Float(
        string="Score santé documentaire",
        compute='_compute_document_health',
        store=True,
        help="Score de 0 à 100 basé sur l'état des documents"
    )

    next_document_expiry = fields.Date(
        string="Prochaine expiration",
        compute='_compute_document_health',
        store=True,
        help="Date de la prochaine expiration de document"
    )

    active_projects_count = fields.Integer(
        string="Projets actifs",
        compute='_compute_project_stats',
        help="Nombre de projets en cours"
    )

    reliability_score = fields.Float(
        string="Score de fiabilité",
        compute='_compute_reliability_score',
        store=True,
        help="Score de fiabilité basé sur l'historique et les documents"
    )

    disable_notifications = fields.Boolean(
        string="Désactiver notifications",
        default=False,
        help="Désactive les notifications automatiques pour ce partenaire"
    )

    # =================== CHAMPS DES MIXINS (INTÉGRÉS DIRECTEMENT) ===================
    
    # Champs du DocumentManagerMixin
    document_ids = fields.One2many(
        'partner.document',
        'partner_id',
        string='Documents',
        help="Documents associés à ce partenaire"
    )

    # =================== CHAMPS D'ARCHIVES ===================
    
    document_archive_ids = fields.One2many(
        'document.archive',
        'partner_id',
        string='Archives de documents',
        help="Documents archivés du partenaire"
    )

    # =================== CHAMPS DE STATUT DES DOCUMENTS ===================
    
    # Champs de statut automatique des documents
    document_identity_card_status = fields.Selection([
        ('valid', 'Valide'),
        ('expiring', 'Expire bientôt'),
        ('expired', 'Expiré'),
        ('to_check', 'À vérifier'),
        ('missing', 'Manquant'),
        ('rejected', 'Rejeté'),
    ], string="Statut Carte d'identité",
        compute='_compute_document_statuses',
        store=False,
        help="Statut automatique de la carte d'identité"
    )

    document_URSSAF_status = fields.Selection([
        ('valid', 'Valide'),
        ('expiring', 'Expire bientôt'),
        ('expired', 'Expiré'),
        ('to_check', 'À vérifier'),
        ('missing', 'Manquant'),
        ('rejected', 'Rejeté'),
    ], string="Statut URSSAF",
        compute='_compute_document_statuses',
        store=False,
        help="Statut automatique du certificat URSSAF"
    )

    document_KBIS_status = fields.Selection([
        ('valid', 'Valide'),
        ('expiring', 'Expire bientôt'),
        ('expired', 'Expiré'),
        ('to_check', 'À vérifier'),
        ('missing', 'Manquant'),
        ('rejected', 'Rejeté'),
    ], string="Statut KBIS",
        compute='_compute_document_statuses',
        store=False,
        help="Statut automatique de l'extrait KBIS"
    )

    document_insurance_status = fields.Selection([
        ('valid', 'Valide'),
        ('expiring', 'Expire bientôt'),
        ('expired', 'Expiré'),
        ('to_check', 'À vérifier'),
        ('missing', 'Manquant'),
        ('rejected', 'Rejeté'),
    ], string="Statut Assurance",
        compute='_compute_document_statuses',
        store=False,
        help="Statut automatique du certificat d'assurance"
    )

    document_RIB_status = fields.Selection([
        ('valid', 'Valide'),
        ('expiring', 'Expire bientôt'),
        ('expired', 'Expiré'),
        ('to_check', 'À vérifier'),
        ('missing', 'Manquant'),
        ('rejected', 'Rejeté'),
    ], string="Statut RIB",
        compute='_compute_document_statuses',
        store=False,
        help="Statut automatique du RIB"
    )

    # Champs de statut manuel des documents
    document_identity_card_manual_status = fields.Selection([
        ('valid', 'Valide'),
        ('to_check', 'À vérifier'),
        ('rejected', 'Rejeté'),
    ], string="Statut manuel Carte d'identité",
        default='to_check',
        help="Statut manuel de validation de la carte d'identité"
    )

    document_URSSAF_manual_status = fields.Selection([
        ('valid', 'Valide'),
        ('to_check', 'À vérifier'),
        ('rejected', 'Rejeté'),
    ], string="Statut manuel URSSAF",
        default='to_check',
        help="Statut manuel de validation du certificat URSSAF"
    )

    document_KBIS_manual_status = fields.Selection([
        ('valid', 'Valide'),
        ('to_check', 'À vérifier'),
        ('rejected', 'Rejeté'),
    ], string="Statut manuel KBIS",
        default='to_check',
        help="Statut manuel de validation de l'extrait KBIS"
    )

    document_insurance_manual_status = fields.Selection([
        ('valid', 'Valide'),
        ('to_check', 'À vérifier'),
        ('rejected', 'Rejeté'),
    ], string="Statut manuel Assurance",
        default='to_check',
        help="Statut manuel de validation du certificat d'assurance"
    )

    document_RIB_manual_status = fields.Selection([
        ('valid', 'Valide'),
        ('to_check', 'À vérifier'),
        ('rejected', 'Rejeté'),
    ], string="Statut manuel RIB",
        default='to_check',
        help="Statut manuel de validation du RIB"
    )

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

    documents_complete_modern = fields.Boolean(
        string='Documents complets (moderne)',
        compute='_compute_documents_complete_modern',
        store=False,
        help="Indique si tous les documents sont complets (version moderne)"
    )

    # Champs du TrackingMixin
    created_date = fields.Datetime(
        string='Date de création',
        default=fields.Datetime.now,
        readonly=True,
        help="Date de création automatique de l'enregistrement"
    )

    created_by = fields.Many2one(
        'res.users',
        string='Créé par',
        default=lambda self: self.env.user,
        readonly=True,
        help="Utilisateur ayant créé l'enregistrement"
    )

    last_modified_date = fields.Datetime(
        string='Dernière modification',
        readonly=True,
        help="Date de la dernière modification"
    )

    last_modified_by = fields.Many2one(
        'res.users',
        string='Modifié par',
        readonly=True,
        help="Utilisateur ayant effectué la dernière modification"
    )

    last_activity_date = fields.Datetime(
        string='Dernière activité',
        compute='_compute_last_activity',
        store=True,
        help="Date de la dernière activité (modification, message, etc.)"
    )

    activity_count = fields.Integer(
        string='Nombre d\'activités',
        compute='_compute_activity_stats',
        help="Nombre total d'activités sur cet enregistrement"
    )

    days_since_creation = fields.Integer(
        string='Jours depuis création',
        compute='_compute_time_stats',
        help="Nombre de jours depuis la création"
    )

    days_since_last_activity = fields.Integer(
        string='Jours depuis dernière activité',
        compute='_compute_time_stats',
        help="Nombre de jours depuis la dernière activité"
    )

    # =================== CONFIGURATION DOCUMENTMANAGERMIXIN ===================
    def _get_document_config(self):
        """Configuration des documents pour ce type de partenaire."""
        if self.is_subcontractor:
            return DOCUMENT_TYPES
        return {}

    def _get_trackable_fields(self):
        """Champs à suivre pour le TrackingMixin."""
        return [
            'name', 'email', 'phone', 'is_subcontractor',
            'speciality_ids', 'notification_preferences'
        ]
    # =================== MÉTHODES CALCULÉES ===================
    
    # Méthodes du TrackingMixin
    @api.depends('message_ids.date', 'write_date')
    def _compute_last_activity(self):
        """Calcule la date de la dernière activité"""
        for record in self:
            dates = []

            # Date de dernière modification
            if record.write_date:
                dates.append(record.write_date)

            # Date du dernier message (si le modèle hérite de mail.thread)
            if hasattr(record, 'message_ids') and record.message_ids:
                last_message_date = max(record.message_ids.mapped('date'))
                dates.append(last_message_date)

            record.last_activity_date = max(dates) if dates else record.created_date

    @api.depends('message_ids')
    def _compute_activity_stats(self):
        """Calcule les statistiques d'activité"""
        for record in self:
            if hasattr(record, 'message_ids'):
                record.activity_count = len(record.message_ids)
            else:
                record.activity_count = 0

    @api.depends('created_date', 'last_activity_date')
    def _compute_time_stats(self):
        """Calcule les statistiques temporelles"""
        from datetime import datetime
        today = datetime.now()
        
        for record in self:
            if record.created_date:
                delta = today - record.created_date
                record.days_since_creation = delta.days
            else:
                record.days_since_creation = 0

            if record.last_activity_date:
                delta = today - record.last_activity_date
                record.days_since_last_activity = delta.days
            else:
                record.days_since_last_activity = 0

    # Méthodes du DocumentManagerMixin
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

            record.document_completion_rate = (valid_docs / total_docs * 100) if total_docs > 0 else 0.0

    @api.depends('document_completion_rate')
    def _compute_documents_complete_modern(self):
        """Calcule si les documents sont complets (version moderne)"""
        for record in self:
            if not record.is_subcontractor:
                record.documents_complete_modern = True
                continue
            
            record.documents_complete_modern = record.document_completion_rate == 100.0

    @api.depends('document_completion_rate', 'has_expired_documents', 'has_expiring_documents')
    def _compute_document_health(self):
        """Calcule le score de santé documentaire."""
        for partner in self:
            if not partner.is_subcontractor:
                partner.document_health_score = 100.0
                partner.next_document_expiry = False
                continue

            # Score de base = taux de complétion
            score = partner.document_completion_rate or 0

            # Pénalités
            if partner.has_expired_documents:
                score -= 30
            elif partner.has_expiring_documents:
                score -= 15

            # Bonus pour documents récents
            recent_uploads = self._count_recent_document_uploads()
            if recent_uploads > 0:
                score += min(10, recent_uploads * 2)

            partner.document_health_score = max(0, min(100, score))

            # Prochaine expiration
            partner.next_document_expiry = self._get_next_document_expiry()

    @api.depends('document_ids', 'document_ids.state', 'document_ids.expiry_date')
    def _compute_document_statuses(self):
        """Calcule les statuts automatiques des documents par type"""
        for partner in self:
            # Initialiser tous les statuts à 'missing'
            partner.document_identity_card_status = 'missing'
            partner.document_URSSAF_status = 'missing'
            partner.document_KBIS_status = 'missing'
            partner.document_insurance_status = 'missing'
            partner.document_RIB_status = 'missing'
            
            # Récupérer les documents du partenaire
            documents = partner.document_ids.filtered(lambda d: d.state != 'rejected')
            
            # Traiter chaque type de document
            for doc_type in ['identity_card', 'URSSAF', 'KBIS', 'insurance', 'RIB']:
                field_name = f'document_{doc_type}_status'
                
                # Trouver le document correspondant
                doc = documents.filtered(lambda d: d.document_type_id.code == doc_type)
                
                if not doc:
                    # Pas de document trouvé
                    setattr(partner, field_name, 'missing')
                    continue
                
                # Vérifier le statut du document
                if doc.state == 'valid':
                    if doc.expiry_date:
                        today = fields.Date.today()
                        days_until_expiry = (doc.expiry_date - today).days
                        
                        if days_until_expiry < 0:
                            setattr(partner, field_name, 'expired')
                        elif days_until_expiry <= 30:
                            setattr(partner, field_name, 'expiring')
                        else:
                            setattr(partner, field_name, 'valid')
                    else:
                        # Document sans date d'expiration
                        setattr(partner, field_name, 'valid')
                else:
                    # Statut autre que 'valid'
                    setattr(partner, field_name, doc.state)

    @api.depends('is_subcontractor')
    def _compute_project_stats(self):
        """Calcule les statistiques de projets."""
        for partner in self:
            if not partner.is_subcontractor:
                partner.active_projects_count = 0
                continue

            try:
                # Rechercher dans différents modèles de projets possibles
                count = 0

                if 'construction.chantier' in self.env:
                    active_chantiers = self.env['construction.chantier'].search([
                        ('subcontractor_ids', 'in', partner.id),
                        ('state', 'in', ['draft', 'confirmed', 'progress'])
                    ])
                    count = len(active_chantiers)

                partner.active_projects_count = count

            except Exception as e:
                _logger.warning(f"Error computing project stats for partner {partner.id}: {str(e)}")
                partner.active_projects_count = 0

    @api.depends('document_health_score', 'days_since_last_activity', 'activity_count')
    def _compute_reliability_score(self):
        """Calcule le score de fiabilité du partenaire."""
        for partner in self:
            if not partner.is_subcontractor:
                partner.reliability_score = 100.0
                continue

            # Score de base basé sur la santé documentaire
            base_score = partner.document_health_score or 0

            # Bonus pour activité récente
            if partner.days_since_last_activity <= 30:
                base_score += 10
            elif partner.days_since_last_activity <= 90:
                base_score += 5

            # Bonus pour activité régulière
            if partner.activity_count > 10:
                base_score += 5
            elif partner.activity_count > 5:
                base_score += 2

            # Pénalité pour inactivité
            if partner.days_since_last_activity > 365:
                base_score -= 20

            partner.reliability_score = max(0, min(100, base_score))

    # =================== SERVICES MÉTIER ===================

    @api.model_create_multi
    def create(self, vals_list):
        """Override pour ajouter le tracking de création."""
        for vals in vals_list:
            # Ajouter les champs de tracking
            vals.update({
                'created_date': fields.Datetime.now(),
                'created_by': self.env.user.id,
                'last_modified_date': fields.Datetime.now(),
                'last_modified_by': self.env.user.id,
            })

        records = super().create(vals_list)
        
        # Log de création
        for record in records:
            record._log_creation()
        
        return records

    @api.model
    def _get_partner_service(self):
        """Factory pour le service partenaire."""
        return PartnerService(self.env)

    @api.model
    def _get_notification_service(self):
        """Factory pour le service de notification."""
        return self.env['document.notification.service']

    def generate_upload_token(self, validity_days=7):
        """Génère un token d'upload sécurisé."""
        self.ensure_one()

        if not self.is_subcontractor:
            raise ValidationError("Seuls les sous-traitants peuvent avoir un token d'upload")

        # Utiliser SecurityHelper du core
        token_data = SecurityHelper.generate_upload_token(
            partner_id=self.id,
            validity_days=validity_days
        )

        self.write({
            'upload_token': token_data['token'],
            'token_expiration': token_data['expiration']
        })

        # Log de l'action
        self.message_post(
            body=f" Token d'upload généré (expire le {DateHelper.format_date_fr(token_data['expiration'])})",
            message_type='notification'
        )

        return token_data['token']

    def is_token_valid(self):
        """Vérifie si le token est valide."""
        self.ensure_one()

        if not self.upload_token or not self.token_expiration:
            return False

        return self.token_expiration >= fields.Datetime.now()

    def revoke_token(self):
        """Révoque le token d'upload."""
        self.ensure_one()

        self.write({
            'upload_token': False,
            'token_expiration': False
        })

        self.message_post(
            body=" Token d'upload révoqué",
            message_type='notification'
        )

    def action_send_document_request(self):
        """Envoie une demande de documents manquants."""
        self.ensure_one()

        # Validation avec les validators du core
        if not self.email:
            return NotificationHelper.create_odoo_notification(
                "Aucune adresse email configurée",
                'danger'
            )

        email_validation = TextValidator.validate_email(self.email)
        if not email_validation['valid']:
            return NotificationHelper.create_odoo_notification(
                f"Email invalide : {email_validation['message']}",
                'danger'
            )

        if not self.is_subcontractor:
            return NotificationHelper.create_odoo_notification(
                "Cette action est réservée aux sous-traitants",
                'warning'
            )

        # Vérifier les préférences de notification
        if self.notification_preferences == 'none':
            return NotificationHelper.create_odoo_notification(
                "Les notifications sont désactivées pour ce partenaire",
                'warning'
            )

        # Utiliser DocumentManagerMixin
        missing_docs = self.get_missing_documents()
        if not missing_docs:
            return NotificationHelper.create_odoo_notification(
                "Aucun document manquant",
                'info'
            )

        # Générer un token si nécessaire
        if not self.is_token_valid():
            self.generate_upload_token()

        # Envoyer via le service de notification
        try:
            result = self.action_send_document_reminder()
            return result
        except Exception as e:
            _logger.error(f"Error sending document request: {str(e)}")
            return NotificationHelper.create_odoo_notification(
                "Erreur lors de l'envoi de la demande",
                'danger'
            )

    def action_send_document_reminder(self):
        """Envoie un rappel de documents via email."""
        self.ensure_one()
        
        if not self.email:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Erreur',
                    'message': 'Aucune adresse email configurée pour ce partenaire',
                    'type': 'danger',
                }
            }

        # Récupérer les documents manquants
        missing_docs = self.get_missing_documents()
        
        # Préparer le contexte pour le template
        template_context = {
            'missing_documents': missing_docs,
            'upload_link': f"/documents/upload/{self.upload_token}" if self.is_token_valid() else None,
            'token_expiry': self.token_expiration,
        }

        # Envoyer l'email via le template
        try:
            template = self.env.ref('construction_contact_extension.email_template_partner_document_request')
            template.with_context(**template_context).send_mail(self.id, force_send=True)
            
            # Log de l'envoi
            self.message_post(
                body=f"📧 Rappel de documents envoyé à {self.email}",
                message_type='notification'
            )
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Succès',
                    'message': f'Rappel de documents envoyé à {self.email}',
                    'type': 'success',
                }
            }
            
        except Exception as e:
            _logger.error(f"Error sending document reminder email: {str(e)}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Erreur',
                    'message': f'Erreur lors de l\'envoi de l\'email : {str(e)}',
                    'type': 'danger',
                }
            }

    def action_validate_all_documents(self):
        """Valide tous les documents en attente."""
        self.ensure_one()

        # Vérifier les droits d'accès
        if not self.env.user.has_group('base.group_system'):
            return NotificationHelper.create_odoo_notification(
                "Droits insuffisants pour cette action",
                'danger'
            )

        # Utiliser DocumentManagerMixin
        return self.action_bulk_validate_documents()

    def action_generate_portal_link(self):
        """Génère un lien vers le portail d'upload."""
        self.ensure_one()

        if not self.is_subcontractor:
            return NotificationHelper.create_odoo_notification(
                "Cette action est réservée aux sous-traitants",
                'warning'
            )

        # Générer ou vérifier le token
        if not self.is_token_valid():
            self.generate_upload_token()

        # Construire l'URL du portail
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        portal_url = f"{base_url}/documents/upload/{self.upload_token}"

        return {
            'type': 'ir.actions.act_window',
            'name': f'Lien portail - {self.name}',
            'res_model': 'portal.link.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_partner_id': self.id,
                'default_portal_url': portal_url,
                'default_token_expiry': self.token_expiration,
                'default_missing_documents': self.get_missing_documents()
            }
        }

    def action_view_document_statistics(self):
            """Affiche les statistiques documentaires."""
            self.ensure_one()

            return {
                'type': 'ir.actions.act_window',
                'name': f'Statistiques documentaires - {self.name}',
                'res_model': 'partner.document.stats.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_partner_id': self.id,
                    'default_health_score': self.document_health_score,
                    'default_completion_rate': self.document_completion_rate,
                    'default_reliability_score': self.reliability_score
                }
            }

    def action_check_all_documents(self):
        """Vérifie tous les documents du partenaire."""
        self.ensure_one()

        if not self.is_subcontractor:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Information',
                    'message': 'Cette action est réservée aux sous-traitants',
                    'type': 'warning',
                }
            }

        # Vérifier les documents manquants
        missing_docs = self.get_missing_documents()
        expired_docs = []
        
        config = self._get_document_config()
        for doc_type in config.keys():
            status_field = f'document_{doc_type}_status'
            if hasattr(self, status_field):
                status = getattr(self, status_field, 'missing')
                if status == 'expired':
                    expired_docs.append(doc_type)

        # Construire le message de résultat
        message_parts = []
        if missing_docs:
            message_parts.append(f"Documents manquants : {', '.join(missing_docs)}")
        if expired_docs:
            message_parts.append(f"Documents expirés : {', '.join(expired_docs)}")
        
        if not message_parts:
            message = "✅ Tous les documents sont à jour"
            message_type = 'success'
        else:
            message = " | ".join(message_parts)
            message_type = 'warning'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Vérification des documents',
                'message': message,
                'type': message_type,
            }
        }

    def action_add_mandatory_documents(self):
        """Ajoute les documents obligatoires manquants pour ce sous-traitant."""
        self.ensure_one()

        if not self.is_subcontractor:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Information',
                    'message': 'Cette action est réservée aux sous-traitants',
                    'type': 'warning',
                }
            }

        # Récupérer la configuration des documents
        config = self._get_document_config()
        if not config:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Information',
                    'message': 'Aucun document obligatoire configuré',
                    'type': 'info',
                }
            }

        # Identifier les documents manquants
        missing_docs = self.get_missing_documents()
        if not missing_docs:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Information',
                    'message': 'Tous les documents obligatoires sont déjà présents',
                    'type': 'success',
                }
            }

        # Créer les documents manquants
        created_docs = []
        for doc_type in missing_docs:
            if doc_type in config:
                doc_config = config[doc_type]
                
                # Créer le document via le service
                try:
                    doc_vals = {
                        'partner_id': self.id,
                        'document_type': doc_type,
                        'name': f"{doc_config.get('name', doc_type)} - {self.name}",
                        'state': 'draft',
                        'is_mandatory': doc_config.get('mandatory', True),
                        'expiry_days': doc_config.get('expiry_days', 365),
                    }
                    
                    # Créer le document
                    document = self.env['partner.document'].create(doc_vals)
                    created_docs.append(doc_type)
                    
                    # Log de création
                    self.message_post(
                        body=f"📄 Document obligatoire ajouté : {doc_config.get('name', doc_type)}",
                        message_type='notification'
                    )
                    
                except Exception as e:
                    _logger.error(f"Error creating document {doc_type} for partner {self.id}: {str(e)}")

        if created_docs:
            message = f"✅ {len(created_docs)} document(s) obligatoire(s) ajouté(s) : {', '.join(created_docs)}"
            message_type = 'success'
        else:
            message = "❌ Aucun document n'a pu être ajouté"
            message_type = 'warning'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Ajout de documents obligatoires',
                'message': message,
                'type': message_type,
            }
        }

    # =================== ACTIONS DE DÉLÉGATION POUR DOCUMENTS ===================

    def action_validate(self):
        """Valide un document (délégué vers partner.document)"""
        self.ensure_one()
        # Cette action est appelée depuis la vue des documents
        # Elle sera gérée par le modèle partner.document
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Validation de document',
                'message': 'Cette action est gérée par le modèle document',
                'type': 'info',
            }
        }

    def action_reject(self):
        """Rejette un document (délégué vers partner.document)"""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Rejet de document',
                'message': 'Cette action est gérée par le modèle document',
                'type': 'info',
            }
        }

    def action_download(self):
        """Télécharge un document (délégué vers partner.document)"""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Téléchargement',
                'message': 'Cette action est gérée par le modèle document',
                'type': 'info',
            }
        }

    def action_view_archives(self):
        """Affiche les archives (délégué vers partner.document)"""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Archives',
                'message': 'Cette action est gérée par le modèle document',
                'type': 'info',
            }
        }



    def action_view_document_archives(self):
        """Affiche les archives de documents"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Archives de documents - {self.name}',
            'res_model': 'document.archive',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
            'target': 'current',
        }

    def action_restore(self):
        """Restaure un document archivé (délégué vers document.archive)"""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Restauration',
                'message': 'Cette action est gérée par le modèle document.archive',
                'type': 'info',
            }
        }

    # =================== MÉTHODES UTILITAIRES ===================

    def get_documents_by_type(self, document_type_id):
        """Récupère les documents d'un type spécifique pour ce partenaire."""
        self.ensure_one()
        return self.document_ids.filtered(
            lambda d: d.document_type_id.id == document_type_id
        )

    # Méthodes utilitaires du DocumentManagerMixin
    def get_missing_documents(self):
        """Retourne la liste des documents manquants"""
        missing = []
        config = self._get_document_config()
        
        for doc_type in config.keys():
            status_field = f'document_{doc_type}_status'
            if hasattr(self, status_field):
                status = getattr(self, status_field, 'missing')
                if status == 'missing':
                    missing.append(doc_type)
        
        return missing

    def get_expiring_documents(self, days=30):
        """Retourne la liste des documents qui expirent bientôt"""
        expiring = []
        config = self._get_document_config()
        
        for doc_type in config.keys():
            status_field = f'document_{doc_type}_status'
            if hasattr(self, status_field):
                status = getattr(self, status_field, 'missing')
                if status == 'expiring':
                    expiring.append(doc_type)
        
        return expiring

    def validate_document(self, doc_type, status='valid'):
        """Valide un document spécifique"""
        status_field = f'document_{doc_type}_status'
        if hasattr(self, status_field):
            self.write({status_field: status})
            return True
        return False

    def check_documents_before_action(self, required_docs=None):
        """Vérifie les documents avant une action"""
        if not self.is_subcontractor:
            return True, ""

        missing = self.get_missing_documents()
        expired = []
        
        config = self._get_document_config()
        for doc_type in config.keys():
            status_field = f'document_{doc_type}_status'
            if hasattr(self, status_field):
                status = getattr(self, status_field, 'missing')
                if status == 'expired':
                    expired.append(doc_type)

        if missing or expired:
            message = self._build_validation_message(missing, expired)
            return False, message

        return True, ""

    def _build_validation_message(self, missing, expired):
        """Construit le message de validation"""
        parts = []
        if missing:
            parts.append(f"Documents manquants : {', '.join(missing)}")
        if expired:
            parts.append(f"Documents expirés : {', '.join(expired)}")
        return " | ".join(parts)

    # Méthodes utilitaires du TrackingMixin
    def _log_creation(self):
        """Log la création d'un enregistrement"""
        _logger.info(f"Partner created: {self.name} (ID: {self.id})")

    def _log_changes(self, old_values, new_values):
        """Log les changements d'un enregistrement"""
        changed_fields = []
        for field, new_value in new_values.items():
            if field in old_values and old_values[field] != new_value:
                changed_fields.append(field)
        
        if changed_fields:
            _logger.info(f"Partner {self.name} (ID: {self.id}) updated: {', '.join(changed_fields)}")

    def _should_track_changes(self):
        """Détermine si les changements doivent être trackés"""
        return self._get_trackable_fields()

    def action_view_activity_history(self):
        """Action pour voir l'historique d'activité"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'Historique d\'activité - {self.name}',
            'res_model': 'mail.message',
            'view_mode': 'list,form',
            'domain': [('model', '=', 'res.partner'), ('res_id', '=', self.id)],
            'context': {'default_model': 'res.partner', 'default_res_id': self.id},
            'target': 'current',
        }

    def _count_recent_document_uploads(self, days=30):
            """Compte les uploads récents de documents."""
            cutoff_date = fields.Date.today() - timedelta(days=days)

            # Rechercher dans les messages de type upload
            recent_uploads = self.message_ids.filtered(
                lambda m: m.date >= fields.Datetime.to_datetime(cutoff_date) and
                          '📄' in (m.body or '') and 'uploadé' in (m.body or '')
            )

            return len(recent_uploads)

    def _get_next_document_expiry(self):
            """Retourne la date de la prochaine expiration."""
            expiring_docs = self.get_expiring_documents(days=365)  # Prochain an

            if expiring_docs:
                # Retourner la date la plus proche
                min_days = min(expiring_docs.values())
                return fields.Date.today() + timedelta(days=min_days)

            return False

    def get_portal_context(self):
            """Retourne le contexte pour le portail d'upload."""
            self.ensure_one()

            return {
                'partner': self,
                'missing_documents': self.get_missing_documents(),
                'expiring_documents': self.get_expiring_documents(),
                'completion_rate': self.document_completion_rate,
                'health_score': self.document_health_score,
                'token_valid': self.is_token_valid(),
                'preferred_contact': self.preferred_contact_method
            }

            # =================== API PUBLIQUE ===================

    @api.model
    def search_subcontractors(self, **criteria):
            """API de recherche avancée pour les sous-traitants."""
            domain = [('is_subcontractor', '=', True)]

            # Filtres par score
            if 'min_health_score' in criteria:
                domain.append(('document_health_score', '>=', criteria['min_health_score']))

            # Filtres par spécialité
            if 'speciality_ids' in criteria:
                domain.append(('speciality_ids', 'in', criteria['speciality_ids']))

            # Filtres par état des documents
            if criteria.get('documents_complete'):
                domain.append(('document_completion_rate', '=', 100))

            if criteria.get('no_expired_docs'):
                domain.append(('has_expired_documents', '=', False))

            # Filtre par activité récente
            if criteria.get('active_only'):
                cutoff_date = fields.Datetime.now() - timedelta(days=90)
                domain.append(('last_activity_date', '>=', cutoff_date))

            return self.search(domain)

    @api.model
    def get_subcontractor_statistics(self):
            """Retourne des statistiques globales sur les sous-traitants."""
            subcontractors = self.search([('is_subcontractor', '=', True)])

            if not subcontractors:
                return {
                    'total': 0,
                    'with_complete_docs': 0,
                    'avg_health_score': 0,
                }

            total = len(subcontractors)
            complete_docs = len(subcontractors.filtered(lambda s: s.document_completion_rate == 100))

            avg_health = sum(subcontractors.mapped('document_health_score')) / total

            return {
                'total': total,
                'with_complete_docs': complete_docs,
                'completion_percentage': (complete_docs / total) * 100,
                'avg_health_score': round(avg_health, 1),
                'with_expired_docs': len(subcontractors.filtered('has_expired_documents')),
                'with_expiring_docs': len(subcontractors.filtered('has_expiring_documents'))
            }

    @api.constrains('email')
    def _check_email_format(self):
            """Validation du format email."""
            for partner in self:
                if partner.email:
                    validation = TextValidator.validate_email(partner.email)
                    if not validation['valid']:
                        raise ValidationError(f"Format d'email invalide : {validation['message']}")

    @api.constrains('phone')
    def _check_phone_format(self):
            """Validation du format téléphone."""
            for partner in self:
                if partner.phone:
                    validation = TextValidator.validate_phone(partner.phone, 'FR')
                    if not validation['valid']:
                        raise ValidationError(f"Format de téléphone invalide : {validation['message']}")

    @api.onchange('contact_type')
    def _onchange_contact_type(self):
        """Synchronise le type de contact avec le statut de sous-traitant"""
        for record in self:
            if record.contact_type == 'sous_traitant':
                record.is_subcontractor = True
            elif record.contact_type != 'sous_traitant' and record.is_subcontractor:
                record.is_subcontractor = False

    @api.onchange('is_subcontractor')
    def _onchange_is_subcontractor(self):
        """Synchronise le statut de sous-traitant avec le type de contact"""
        for record in self:
            if record.is_subcontractor:
                record.contact_type = 'sous_traitant'
            elif not record.is_subcontractor and record.contact_type == 'sous_traitant':
                record.contact_type = 'customer'

    @api.constrains('is_subcontractor', 'speciality_ids')
    def _check_subcontractor_coherence(self):
            """Vérifie la cohérence des données sous-traitant."""
            for partner in self:
                if partner.speciality_ids and not partner.is_subcontractor:
                    raise ValidationError(
                        "Les spécialités ne peuvent être assignées qu'aux sous-traitants"
                    )

    def write(self, vals):
            """Override pour gérer les changements spéciaux et le tracking."""
            # Sauvegarder les anciennes valeurs pour le tracking
            old_values = {}
            if self._should_track_changes():
                trackable_fields = self._get_trackable_fields()
                for field in trackable_fields:
                    if field in self._fields and field in vals:
                        old_values[field] = getattr(self, field, False)

            # Si on désactive le statut sous-traitant, nettoyer les données liées
            if 'is_subcontractor' in vals and not vals['is_subcontractor']:
                vals.update({
                    'speciality_ids': [(5, 0, 0)],  # Supprimer toutes les spécialités
                    'upload_token': False,
                    'token_expiration': False
                })

            # Si on change l'email, révoquer le token existant
            if 'email' in vals and self.upload_token:
                vals.update({
                    'upload_token': False,
                    'token_expiration': False
                })

            # Mettre à jour les champs de tracking
            vals.update({
                'last_modified_date': fields.Datetime.now(),
                'last_modified_by': self.env.user.id,
            })

            result = super().write(vals)
            
            # Log des changements
            if old_values:
                self._log_changes(old_values, vals)
            
            return result

    @api.model
    def cron_cleanup_expired_tokens(self):
            """Nettoie les tokens expirés."""
            expired_partners = self.search([
                ('token_expiration', '<', fields.Datetime.now()),
                ('upload_token', '!=', False)
            ])

            if expired_partners:
                expired_partners.write({
                    'upload_token': False,
                    'token_expiration': False
                })

                _logger.info(f"Cleaned up {len(expired_partners)} expired tokens")

            return len(expired_partners)

    @api.model
    def cron_send_document_reminders(self):
            """Envoie des rappels automatiques pour les documents."""
            # Sous-traitants avec documents manquants ou expirés
            partners_to_notify = self.search([
                ('is_subcontractor', '=', True),
                ('notification_preferences', '!=', 'none'),
                '|',
                ('has_expired_documents', '=', True),
                ('has_expiring_documents', '=', True)
            ])

            sent_count = 0
            for partner in partners_to_notify:
                try:
                    # Vérifier si on peut envoyer (pas trop fréquent)
                    if partner._should_send_notification('document_reminder'):
                        result = partner.action_send_document_request()
                        if result.get('params', {}).get('type') == 'success':
                            sent_count += 1
                except Exception as e:
                    _logger.error(f"Error sending reminder to partner {partner.id}: {str(e)}")

            _logger.info(f"Sent {sent_count} document reminders")
            return sent_count

    def _should_send_notification(self, notification_type):
            """Détermine si une notification peut être envoyée."""
            if self.notification_preferences == 'none':
                return False

            # Limite de fréquence : max 1 rappel par semaine
            if self.last_notification_date:
                days_since = (fields.Datetime.now() - self.last_notification_date).days
                if days_since < 7:
                    return False

            return True



