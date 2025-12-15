# -*- coding: utf-8 -*-
"""
Types de documents pour les partenaires sous-traitants
=====================================================

Définit les différents types de documents requis avec leurs règles de validation.
"""

from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.addons.construction_core.utils.validators import TextValidator
import logging

_logger = logging.getLogger(__name__)


class DocumentType(models.Model):
    """Type de document requis pour les sous-traitants"""

    _name = 'document.type'
    _description = 'Type de Document'
    _order = 'sequence, name'
    _rec_name = 'name'

    # =================== CHAMPS PRINCIPAUX ===================

    name = fields.Char(
        string='Nom',
        required=True,
        translate=True,
        help="Nom du type de document (ex: KBIS, Assurance)"
    )

    code = fields.Char(
        string='Code',
        required=True,
        help="Code technique unique (ex: kbis, insurance)"
    )

    description = fields.Text(
        string='Description',
        translate=True,
        help="Description détaillée du document"
    )

    sequence = fields.Integer(
        string='Séquence',
        default=10,
        help="Ordre d'affichage"
    )

    # =================== CONFIGURATION ===================

    active = fields.Boolean(
        string='Actif',
        default=True,
        help="Décocher pour désactiver ce type de document"
    )

    is_mandatory = fields.Boolean(
        string='Obligatoire',
        default=True,
        help="Document requis pour tous les sous-traitants"
    )

    has_expiry = fields.Boolean(
        string='A une expiration',
        default=True,
        help="Ce document a une date d'expiration"
    )

    validity_period_months = fields.Integer(
        string='Période de validité (mois)',
        default=12,
        help="Durée de validité par défaut en mois"
    )

    expiry_warning_days = fields.Integer(
        string='Alerte expiration (jours)',
        default=30,
        help="Nombre de jours avant expiration pour déclencher l'alerte"
    )

    # =================== VALIDATION FICHIERS ===================

    allowed_file_types = fields.Char(
        string='Types de fichiers autorisés',
        default='.pdf',
        help="Extensions autorisées séparées par des virgules (ex: .pdf,.jpg,.png)"
    )

    max_file_size_mb = fields.Float(
        string='Taille maximum (MB)',
        default=10.0,
        help="Taille maximum du fichier en mégaoctets"
    )

    require_expiry_date = fields.Boolean(
        string='Date d\'expiration requise',
        default=True,
        help="La date d'expiration est obligatoire lors de l'upload"
    )

    # =================== RÈGLES MÉTIER ===================

    auto_renewal_possible = fields.Boolean(
        string='Renouvellement automatique possible',
        default=False,
        help="Ce document peut être renouvelé automatiquement"
    )

    renewal_reminder_months = fields.Integer(
        string='Rappel renouvellement (mois)',
        default=2,
        help="Mois avant expiration pour envoyer le rappel de renouvellement"
    )

    required_for_specialities = fields.Many2many(
        'lot',
        'document_type_lot_rel',
        'document_type_id',
        'lot_id',
        string='Spécialités requises',
        help="Spécialités pour lesquelles ce type de document est obligatoire"
    )

    # =================== TEMPLATES ===================

    upload_instructions = fields.Html(
        string='Instructions d\'upload',
        translate=True,
        help="Instructions spécifiques pour ce type de document"
    )

    validation_checklist = fields.Html(
        string='Checklist de validation',
        help="Points à vérifier lors de la validation"
    )

    # =================== CHAMPS CALCULÉS ===================

    document_count = fields.Integer(
        string='Nombre de documents',
        compute='_compute_document_count',
        help="Nombre de documents de ce type dans le système"
    )

    valid_document_count = fields.Integer(
        string='Documents valides',
        compute='_compute_document_count',
        help="Nombre de documents valides de ce type"
    )

    expired_document_count = fields.Integer(
        string='Documents expirés',
        compute='_compute_document_count',
        help="Nombre de documents expirés de ce type"
    )

    compliance_rate = fields.Float(
        string='Taux de conformité (%)',
        compute='_compute_document_count',
        help="Pourcentage de documents valides"
    )

    # =================== MÉTHODES CALCULÉES ===================

    @api.depends()
    def _compute_document_count(self):
        """Calcule les statistiques de documents"""
        for doc_type in self:
            # Rechercher tous les documents de ce type
            documents = self.env['partner.document'].search([
                ('document_type_id', '=', doc_type.id)
            ])

            doc_type.document_count = len(documents)
            doc_type.valid_document_count = len(documents.filtered(lambda d: d.state == 'valid'))
            doc_type.expired_document_count = len(documents.filtered(lambda d: d.state == 'expired'))

            # Taux de conformité
            if doc_type.document_count > 0:
                doc_type.compliance_rate = (doc_type.valid_document_count / doc_type.document_count) * 100
            else:
                doc_type.compliance_rate = 0.0

    # =================== MÉTHODES UTILITAIRES ===================

    def get_allowed_extensions_list(self):
        """Retourne la liste des extensions autorisées"""
        self.ensure_one()
        if not self.allowed_file_types:
            return ['.pdf']

        return [ext.strip() for ext in self.allowed_file_types.split(',') if ext.strip()]

    def is_file_type_allowed(self, filename):
        """Vérifie si le type de fichier est autorisé"""
        self.ensure_one()
        allowed_extensions = self.get_allowed_extensions_list()

        file_ext = '.' + filename.split('.')[-1].lower() if '.' in filename else ''
        return file_ext in [ext.lower() for ext in allowed_extensions]

    def get_default_expiry_date(self, issue_date=None):
        """Calcule la date d'expiration par défaut"""
        self.ensure_one()

        if not self.has_expiry:
            return False

        from datetime import date
        from dateutil.relativedelta import relativedelta

        base_date = issue_date or date.today()
        return base_date + relativedelta(months=self.validity_period_months)

    def get_upload_context(self, partner=None):
        """Retourne le contexte pour l'upload de ce type de document"""
        self.ensure_one()

        context = {
            'document_type': self,
            'allowed_extensions': self.get_allowed_extensions_list(),
            'max_size_mb': self.max_file_size_mb,
            'require_expiry': self.require_expiry_date,
            'instructions': self.upload_instructions,
            'has_expiry': self.has_expiry
        }

        if partner:
            context['default_expiry'] = self.get_default_expiry_date()

        return context

    # =================== ACTIONS ===================

    def action_view_documents(self):
        """Affiche tous les documents de ce type"""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': f'Documents - {self.name}',
            'res_model': 'partner.document',
            'view_mode': 'list,form',
            'domain': [('document_type_id', '=', self.id)],
            'context': {
                'default_document_type_id': self.id,
                'search_default_group_by_state': 1
            }
        }

    def action_view_statistics(self):
        """Affiche les statistiques de ce type de document"""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': f'Statistiques - {self.name}',
            'res_model': 'document.type.stats.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_document_type_id': self.id,
                'default_total_count': self.document_count,
                'default_valid_count': self.valid_document_count,
                'default_expired_count': self.expired_document_count,
                'default_compliance_rate': self.compliance_rate
            }
        }

    def action_send_renewal_reminders(self):
        """Envoie des rappels de renouvellement pour ce type de document"""
        self.ensure_one()

        if not self.has_expiry:
            from odoo.addons.construction_core.utils.helpers import NotificationHelper
            return NotificationHelper.create_odoo_notification(
                "Ce type de document n'a pas d'expiration",
                'warning'
            )

        # Trouver les documents expirant bientôt
        from datetime import timedelta
        cutoff_date = fields.Date.today() + timedelta(days=self.expiry_warning_days)

        expiring_documents = self.env['partner.document'].search([
            ('document_type_id', '=', self.id),
            ('expiry_date', '<=', cutoff_date),
            ('expiry_date', '>=', fields.Date.today()),
            ('state', '=', 'valid')
        ])

        if not expiring_documents:
            return NotificationHelper.create_odoo_notification(
                "Aucun document expirant bientôt pour ce type",
                'info'
            )

        # Envoyer les rappels
        notification_service = self.env['partner.notification.service']
        sent_count = 0

        for doc in expiring_documents:
            try:
                if doc.partner_id.notification_preferences != 'none':
                    notification_service.send_document_expiry_reminder(doc)
                    sent_count += 1
            except Exception as e:
                _logger.error(f"Error sending reminder for document {doc.id}: {str(e)}")

        return NotificationHelper.create_odoo_notification(
            f"{sent_count} rappel(s) envoyé(s)",
            'success'
        )

    # =================== MÉTHODES DE VALIDATION ===================

    def validate_document_data(self, file_content, filename, expiry_date=None):
        """Valide les données d'un document de ce type"""
        self.ensure_one()

        errors = []

        # Validation du fichier
        if not self.is_file_type_allowed(filename):
            allowed = ', '.join(self.get_allowed_extensions_list())
            errors.append(f"Type de fichier non autorisé. Types acceptés : {allowed}")

        # Validation de la taille
        if file_content:
            import base64
            file_size = len(base64.b64decode(file_content))
            max_size_bytes = self.max_file_size_mb * 1024 * 1024

            if file_size > max_size_bytes:
                errors.append(
                    f"Fichier trop volumineux ({file_size / 1024 / 1024:.1f}MB). Maximum : {self.max_file_size_mb}MB")

        # Validation de la date d'expiration
        if self.require_expiry_date and not expiry_date:
            errors.append("Date d'expiration requise pour ce type de document")

        if expiry_date and expiry_date <= fields.Date.today():
            errors.append("La date d'expiration doit être dans le futur")

        return {
            'valid': len(errors) == 0,
            'errors': errors
        }

    # =================== CONTRAINTES ===================

    @api.constrains('code')
    def _check_code_unique(self):
        """Vérifie l'unicité du code"""
        for doc_type in self:
            if self.search_count([('code', '=', doc_type.code), ('id', '!=', doc_type.id)]) > 0:
                raise ValidationError(f"Le code '{doc_type.code}' est déjà utilisé")

    @api.constrains('code')
    def _check_code_format(self):
        """Vérifie le format du code"""
        for doc_type in self:
            if doc_type.code:
                validation = TextValidator.validate_required_text(doc_type.code, "Code")
                if not validation['valid']:
                    raise ValidationError(validation['message'])

                # Code doit être alphanumérique et underscore uniquement
                import re
                if not re.match(r'^[a-zA-Z0-9_]+$', doc_type.code):
                    raise ValidationError("Le code ne peut contenir que des lettres, chiffres et underscores")

    @api.constrains('validity_period_months')
    def _check_validity_period(self):
        """Vérifie la période de validité"""
        for doc_type in self:
            if doc_type.has_expiry and doc_type.validity_period_months <= 0:
                raise ValidationError("La période de validité doit être positive")

    @api.constrains('max_file_size_mb')
    def _check_file_size(self):
        """Vérifie la taille maximum"""
        for doc_type in self:
            if doc_type.max_file_size_mb <= 0:
                raise ValidationError("La taille maximum doit être positive")
            if doc_type.max_file_size_mb > 100:
                raise ValidationError("La taille maximum ne peut dépasser 100MB")

    # =================== MÉTHODES DE RECHERCHE ===================

    @api.model
    def search_mandatory(self):
        """Recherche les types de documents obligatoires"""
        return self.search([('is_mandatory', '=', True), ('active', '=', True)])

    @api.model
    def search_with_expiry(self):
        """Recherche les types de documents avec expiration"""
        return self.search([('has_expiry', '=', True), ('active', '=', True)])

    @api.model
    def search_for_speciality(self, speciality_id):
        """Recherche les types requis pour une spécialité"""
        return self.search([
            ('active', '=', True),
            '|',
            ('is_mandatory', '=', True),
            ('required_for_specialities', 'in', [speciality_id])
        ])

    # =================== MÉTHODES D'ADMINISTRATION ===================

    @api.model
    def create_default_types(self):
        """Crée les types de documents par défaut"""
        default_types = [
            {
                'name': 'Carte d\'identité',
                'code': 'identity_card',
                'description': 'Pièce d\'identité officielle',
                'validity_period_months': 120,  # 10 ans
                'allowed_file_types': '.pdf,.jpg,.jpeg,.png',
                'sequence': 10
            },
            {
                'name': 'URSSAF',
                'code': 'urssaf',
                'description': 'Attestation de régularité URSSAF',
                'validity_period_months': 3,
                'expiry_warning_days': 15,
                'sequence': 20
            },
            {
                'name': 'KBIS',
                'code': 'kbis',
                'description': 'Extrait KBIS de moins de 3 mois',
                'validity_period_months': 3,
                'expiry_warning_days': 15,
                'sequence': 30
            },
            {
                'name': 'Assurance',
                'code': 'insurance',
                'description': 'Attestation d\'assurance responsabilité civile',
                'validity_period_months': 12,
                'sequence': 40
            },
            {
                'name': 'RIB',
                'code': 'rib',
                'description': 'Relevé d\'identité bancaire',
                'has_expiry': False,
                'require_expiry_date': False,
                'sequence': 50
            }
        ]

        created_count = 0
        for type_data in default_types:
            if not self.search([('code', '=', type_data['code'])]):
                self.create(type_data)
                created_count += 1

        return created_count

    @api.model
    def cleanup_unused_types(self):
        """Nettoie les types de documents non utilisés"""
        unused_types = self.search([
            ('active', '=', False),
            ('document_count', '=', 0)
        ])

        count = len(unused_types)
        unused_types.unlink()

        return count

    # =================== MÉTHODES D'EXPORT ===================

    def export_statistics(self):
        """Exporte les statistiques de ce type de document"""
        self.ensure_one()

        return {
            'name': self.name,
            'code': self.code,
            'is_mandatory': self.is_mandatory,
            'has_expiry': self.has_expiry,
            'total_documents': self.document_count,
            'valid_documents': self.valid_document_count,
            'expired_documents': self.expired_document_count,
            'compliance_rate': self.compliance_rate,
            'validity_period_months': self.validity_period_months,
            'max_file_size_mb': self.max_file_size_mb
        }

    # =================== GESTION DES HOOKS ===================

    def write(self, vals):
        """Override write pour gérer les changements critiques"""
        # Si on change le code, vérifier l'impact
        if 'code' in vals:
            for doc_type in self:
                if doc_type.document_count > 0:
                    _logger.warning(
                        f"Changing code for document type {doc_type.name} with {doc_type.document_count} existing documents")

        # Si on désactive un type obligatoire, avertir
        if 'active' in vals and not vals['active']:
            for doc_type in self:
                if doc_type.is_mandatory and doc_type.document_count > 0:
                    _logger.warning(
                        f"Deactivating mandatory document type {doc_type.name} with {doc_type.document_count} existing documents")

        return super().write(vals)
