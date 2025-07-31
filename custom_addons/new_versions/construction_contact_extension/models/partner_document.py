# -*- coding: utf-8 -*-
"""
Modèle pour les documents des partenaires sous-traitants
======================================================

Gère les documents individuels avec validation, archivage et suivi automatique.
"""

from odoo import models, fields, api
from odoo.exceptions import ValidationError, AccessError
from odoo.addons.construction_core.models.mixins.tracking_mixin import TrackingMixin
from odoo.addons.construction_core.utils.helpers import FileHelper, DateHelper
from odoo.addons.construction_core.utils.validators import FileValidator, DateValidator
from datetime import date, timedelta
import logging

_logger = logging.getLogger(__name__)


class PartnerDocument(models.Model):
    """Document d'un partenaire sous-traitant"""

    _name = 'partner.document'
    _inherit = ['mail.thread', 'tracking.mixin']
    _description = 'Document Partenaire'
    _order = 'document_type_id, expiry_date'
    _rec_name = 'display_name'

    # =================== CHAMPS PRINCIPAUX ===================

    partner_id = fields.Many2one(
        'res.partner',
        string='Partenaire',
        required=True,
        ondelete='cascade',
        help="Partenaire propriétaire du document"
    )

    document_type_id = fields.Many2one(
        'document.type',
        string='Type de document',
        required=True,
        help="Type de document (KBIS, Assurance, etc.)"
    )

    file_content = fields.Binary(
        string='Fichier',
        attachment=True,
        help="Contenu du fichier document"
    )

    filename = fields.Char(
        string='Nom du fichier',
        help="Nom original du fichier"
    )

    file_size = fields.Integer(
        string='Taille du fichier',
        help="Taille en octets"
    )

    file_hash = fields.Char(
        string='Hash du fichier',
        help="Hash SHA256 pour détecter les doublons"
    )

    # =================== CHAMPS DE VALIDITÉ ===================

    expiry_date = fields.Date(
        string='Date d\'expiration',
        help="Date d'expiration du document"
    )

    issue_date = fields.Date(
        string='Date d\'émission',
        help="Date d'émission du document"
    )

    upload_date = fields.Datetime(
        string='Date d\'upload',
        default=fields.Datetime.now,
        help="Date de téléversement"
    )

    # =================== ÉTAT ET VALIDATION ===================

    state = fields.Selection([
        ('missing', 'Manquant'),
        ('to_check', 'À vérifier'),
        ('valid', 'Valide'),
        ('expiring', 'Expire bientôt'),
        ('expired', 'Expiré'),
        ('rejected', 'Rejeté')
    ], string='État',
        default='missing',
        tracking=True,
        help="État de validation du document")

    validation_notes = fields.Text(
        string='Notes de validation',
        help="Commentaires du validateur"
    )

    validated_by = fields.Many2one(
        'res.users',
        string='Validé par',
        help="Utilisateur ayant validé le document"
    )

    validation_date = fields.Datetime(
        string='Date de validation',
        help="Date de validation du document"
    )

    # =================== CHAMPS CALCULÉS ===================

    display_name = fields.Char(
        string='Nom d\'affichage',
        compute='_compute_display_name',
        store=True
    )

    days_until_expiry = fields.Integer(
        string='Jours avant expiration',
        compute='_compute_expiry_info',
        help="Nombre de jours avant expiration"
    )

    is_expired = fields.Boolean(
        string='Expiré',
        compute='_compute_expiry_info'
    )

    is_expiring_soon = fields.Boolean(
        string='Expire bientôt',
        compute='_compute_expiry_info'
    )

    file_size_human = fields.Char(
        string='Taille (lisible)',
        compute='_compute_file_info',
        help="Taille de fichier formatée"
    )

    can_be_validated = fields.Boolean(
        string='Peut être validé',
        compute='_compute_validation_flags'
    )

    can_be_rejected = fields.Boolean(
        string='Peut être rejeté',
        compute='_compute_validation_flags'
    )

    # =================== MÉTHODES CALCULÉES ===================

    @api.depends('partner_id.name', 'document_type_id.name', 'filename')
    def _compute_display_name(self):
        """Calcule le nom d'affichage du document"""
        for doc in self:
            if doc.partner_id and doc.document_type_id:
                doc.display_name = f"{doc.partner_id.name} - {doc.document_type_id.name}"
            else:
                doc.display_name = doc.filename or "Nouveau document"

    @api.depends('expiry_date')
    def _compute_expiry_info(self):
        """Calcule les informations d'expiration"""
        for doc in self:
            if doc.expiry_date:
                days_until = DateHelper.get_days_until(doc.expiry_date)
                doc.days_until_expiry = days_until
                doc.is_expired = days_until < 0
                doc.is_expiring_soon = 0 <= days_until <= 30
            else:
                doc.days_until_expiry = 0
                doc.is_expired = False
                doc.is_expiring_soon = False

    @api.depends('file_content', 'file_size')
    def _compute_file_info(self):
        """Calcule les informations du fichier"""
        for doc in self:
            if doc.file_size:
                doc.file_size_human = FileHelper.format_file_size(doc.file_size)
            else:
                doc.file_size_human = ""

    @api.depends('state', 'file_content')
    def _compute_validation_flags(self):
        """Calcule les flags de validation"""
        for doc in self:
            doc.can_be_validated = doc.state in ['to_check'] and bool(doc.file_content)
            doc.can_be_rejected = doc.state in ['to_check', 'valid']

    # =================== MÉTHODES AUTOMATIQUES ===================

    @api.model_create_multi
    def create(self, vals_list):
        """Override create pour traiter les fichiers"""
        for vals in vals_list:
            if vals.get('file_content'):
                # Calculer les informations du fichier
                file_content = vals['file_content']
                if isinstance(file_content, str):
                    import base64
                    file_bytes = base64.b64decode(file_content)
                    vals['file_size'] = len(file_bytes)
                    vals['file_hash'] = FileHelper.calculate_file_hash(file_bytes)

        documents = super().create(vals_list)

        # Post-traitement
        for doc in documents:
            doc._auto_compute_state()
            doc._create_archive_if_replacing()

        return documents

    def write(self, vals):
        """Surcharge de write pour gérer les fichiers et recalculer l'état"""
        
        # Si on modifie déjà le state, ne pas recalculer automatiquement
        if 'state' in vals:
            # Éviter la récursion en ne recalculant pas l'état
            result = super().write(vals)
            return result
        
        # Gestion du fichier uploadé
        if 'file_content' in vals and vals['file_content']:
            import base64
            file_bytes = base64.b64decode(vals['file_content'])
            vals['file_size'] = len(file_bytes)
            vals['file_hash'] = FileHelper.calculate_file_hash(file_bytes)

        result = super().write(vals)

        # Recalculer l'état après modification (sauf si on a déjà modifié le state)
        for doc in self:
            doc._auto_compute_state()

        return result

    # =================== MÉTHODES MÉTIER ===================

    def _auto_compute_state(self):
        """Calcule automatiquement l'état du document"""
        self.ensure_one()

        new_state = None

        if not self.file_content:
            new_state = 'missing'
        elif not self.expiry_date:
            # Si pas de date d'expiration, laisser en 'to_check' sauf si déjà 'missing'
            if self.state == 'missing':
                new_state = 'to_check'
        else:
            # Vérifier l'expiration
            if self.is_expired:
                new_state = 'expired'
            elif self.is_expiring_soon and self.state == 'valid':
                new_state = 'expiring'

        # Utiliser super().write() pour éviter la récursion
        if new_state and new_state != self.state:
            super(PartnerDocument, self).write({'state': new_state})

    def _archive_current_version(self, reason):
        """Archive la version actuelle du document"""
        self.ensure_one()

        if not self.file_content:
            return

        archive_vals = {
            'partner_id': self.partner_id.id,
            'document_type_id': self.document_type_id.id,
            'archived_content': self.file_content,
            'archived_filename': self.filename,
            'archive_reason': reason,
            'archived_date': fields.Datetime.now(),
            'original_upload_date': self.upload_date,
            'original_expiry_date': self.expiry_date
        }

        self.env['document.archive'].create(archive_vals)

    def _create_archive_if_replacing(self):
        """Crée une archive si ce document remplace un existant"""
        self.ensure_one()

        # Chercher un document existant du même type
        existing_doc = self.search([
            ('partner_id', '=', self.partner_id.id),
            ('document_type_id', '=', self.document_type_id.id),
            ('id', '!=', self.id)
        ], limit=1)

        if existing_doc and existing_doc.file_content:
            existing_doc._archive_current_version('replaced')
            existing_doc.unlink()

    # =================== ACTIONS PUBLIQUES ===================

    def action_validate(self):
        """Valide le document"""
        self.ensure_one()

        if not self.can_be_validated:
            from odoo.addons.construction_core.utils.helpers import NotificationHelper
            return NotificationHelper.create_odoo_notification(
                "Ce document ne peut pas être validé dans son état actuel",
                'warning'
            )

        self.write({
            'state': 'valid',
            'validated_by': self.env.user.id,
            'validation_date': fields.Datetime.now()
        })

        # Message de validation
        self.message_post(
            body=f"✅ Document validé par {self.env.user.name}",
            message_type='notification'
        )

        return NotificationHelper.create_odoo_notification(
            f"Document {self.document_type_id.name} validé",
            'success'
        )

    def action_reject(self):
        """Rejette le document"""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Rejeter le document',
            'res_model': 'document.rejection.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_document_id': self.id,
                'default_document_name': self.display_name
            }
        }

    def action_download(self):
        """Télécharge le document"""
        self.ensure_one()

        if not self.file_content:
            from odoo.addons.construction_core.utils.helpers import NotificationHelper
            return NotificationHelper.create_odoo_notification(
                "Aucun fichier disponible pour ce document",
                'warning'
            )

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/partner.document/{self.id}/file_content/{self.filename}?download=true',
            'target': 'self',
        }

    def action_view_archives(self):
        """Affiche les archives de ce document"""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': f'Archives - {self.display_name}',
            'res_model': 'document.archive',
            'view_mode': 'list,form',
            'domain': [
                ('partner_id', '=', self.partner_id.id),
                ('document_type_id', '=', self.document_type_id.id)
            ],
            'context': {
                'default_partner_id': self.partner_id.id,
                'default_document_type_id': self.document_type_id.id
            }
        }

    # =================== MÉTHODES DE VALIDATION ===================

    def _validate_file_upload(self, file_content, filename):
        """Valide un fichier avant upload"""
        if not file_content or not filename:
            raise ValidationError("Fichier et nom de fichier requis")

        # Validation de l'extension
        file_validation = FileValidator.validate_file_type(
            filename,
            self.document_type_id.allowed_file_types.split(',')
        )
        if not file_validation['valid']:
            raise ValidationError(file_validation['message'])

        # Validation de la taille
        file_size = len(base64.b64decode(file_content))
        size_validation = FileValidator.validate_file_size(
            file_size,
            self.document_type_id.max_file_size_mb
        )
        if not size_validation['valid']:
            raise ValidationError(size_validation['message'])

        return True

    # =================== CONTRAINTES ===================

    @api.constrains('partner_id', 'document_type_id')
    def _check_unique_document_type(self):
        """Vérifie l'unicité du type de document par partenaire"""
        for doc in self:
            duplicate = self.search([
                ('partner_id', '=', doc.partner_id.id),
                ('document_type_id', '=', doc.document_type_id.id),
                ('id', '!=', doc.id)
            ])
            if duplicate:
                raise ValidationError(
                    f"Un document de type '{doc.document_type_id.name}' "
                    f"existe déjà pour ce partenaire"
                )

    @api.constrains('expiry_date', 'issue_date')
    def _check_dates_coherence(self):
        """Vérifie la cohérence des dates"""
        for doc in self:
            if doc.expiry_date and doc.issue_date:
                if doc.expiry_date <= doc.issue_date:
                    raise ValidationError(
                        "La date d'expiration doit être postérieure à la date d'émission"
                    )

    # =================== MÉTHODES CRON ===================

    @api.model
    def cron_update_document_states(self):
        """Met à jour les états des documents (tâche planifiée)"""
        # Documents à vérifier pour expiration
        documents_to_check = self.search([
            ('expiry_date', '!=', False),
            ('state', 'in', ['valid', 'expiring'])
        ])

        updated_count = 0
        for doc in documents_to_check:
            old_state = doc.state
            doc._auto_compute_state()
            if doc.state != old_state:
                updated_count += 1

        _logger.info(f"Updated {updated_count} document states")
        return updated_count

    @api.model
    def cron_check_document_expiry(self):
        """Vérifie les documents qui expirent et envoie des notifications"""
        # Documents expirant dans les 30 jours
        expiring_docs = self.search([
            ('expiry_date', '>=', fields.Date.today()),
            ('expiry_date', '<=', fields.Date.today() + timedelta(days=30)),
            ('state', '=', 'valid')
        ])

        # Grouper par partenaire
        partners_with_expiring = {}
        for doc in expiring_docs:
            partner = doc.partner_id
            if partner not in partners_with_expiring:
                partners_with_expiring[partner] = []
            partners_with_expiring[partner].append(doc)

        # Envoyer les notifications
        notification_service = self.env['partner.notification.service']
        sent_count = 0

        for partner, docs in partners_with_expiring.items():
            try:
                if partner.notification_preferences != 'none':
                    notification_service.send_expiry_notification(partner, docs)
                    sent_count += 1
            except Exception as e:
                _logger.error(f"Error sending expiry notification to {partner.name}: {str(e)}")

        _logger.info(f"Sent {sent_count} expiry notifications")
        return sent_count

    # =================== MÉTHODES DE RECHERCHE ===================

    @api.model
    def search_by_state(self, state):
        """Recherche par état"""
        return self.search([('state', '=', state)])

    @api.model
    def search_expiring_soon(self, days=30):
        """Recherche les documents expirant bientôt"""
        cutoff_date = fields.Date.today() + timedelta(days=days)
        return self.search([
            ('expiry_date', '<=', cutoff_date),
            ('expiry_date', '>=', fields.Date.today()),
            ('state', 'in', ['valid'])
        ])

    @api.model
    def search_by_partner_and_type(self, partner_id, document_type_code):
        """Recherche par partenaire et type de document"""
        return self.search([
            ('partner_id', '=', partner_id),
            ('document_type_id.code', '=', document_type_code)
        ])

    # =================== MÉTHODES D'EXPORT ===================

    def export_document_data(self):
        """Exporte les données du document pour reporting"""
        self.ensure_one()

        return {
            'partner_name': self.partner_id.name,
            'document_type': self.document_type_id.name,
            'state': dict(self._fields['state'].selection)[self.state],
            'upload_date': self.upload_date,
            'expiry_date': self.expiry_date,
            'days_until_expiry': self.days_until_expiry,
            'file_size': self.file_size_human,
            'validated_by': self.validated_by.name if self.validated_by else None,
            'validation_date': self.validation_date
        }

    # =================== GESTION DES HOOKS ===================

    def _get_trackable_fields(self):
        """Champs à suivre pour le TrackingMixin"""
        return ['state', 'expiry_date', 'validated_by', 'validation_notes']

    def unlink(self):
        """Override unlink pour archiver avant suppression"""
        for doc in self:
            if doc.file_content:
                doc._archive_current_version('deleted')

        return super().unlink()
