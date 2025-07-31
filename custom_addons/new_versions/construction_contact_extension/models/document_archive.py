# -*- coding: utf-8 -*-
"""
Archive des versions de documents
================================

Conserve un historique des anciennes versions de documents pour audit et traçabilité.
"""

from odoo import models, fields, api
from odoo.addons.construction_core.models.mixins.tracking_mixin import TrackingMixin
from odoo.addons.construction_core.utils.helpers import FileHelper, DateHelper
import logging

from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class DocumentArchive(models.Model):
    """Archive des versions de documents"""

    _name = 'document.archive'
    _inherit = ['mail.thread', 'tracking.mixin']
    _description = 'Archive Document'
    _order = 'archived_date desc'
    _rec_name = 'display_name'

    # =================== CHAMPS PRINCIPAUX ===================

    partner_id = fields.Many2one(
        'res.partner',
        string='Partenaire',
        required=True,
        ondelete='cascade',
        help="Partenaire propriétaire du document archivé"
    )

    document_type_id = fields.Many2one(
        'document.type',
        string='Type de document',
        required=True,
        help="Type du document archivé"
    )

    archived_content = fields.Binary(
        string='Contenu archivé',
        attachment=True,
        help="Contenu du document archivé"
    )

    archived_filename = fields.Char(
        string='Nom du fichier archivé',
        help="Nom original du fichier archivé"
    )

    file_hash = fields.Char(
        string='Hash du fichier',
        help="Hash SHA256 du fichier archivé"
    )

    file_size = fields.Integer(
        string='Taille du fichier',
        help="Taille en octets du fichier archivé"
    )

    # =================== INFORMATIONS D'ARCHIVAGE ===================

    archive_reason = fields.Selection([
        ('replaced', 'Remplacé par une nouvelle version'),
        ('expired', 'Document expiré'),
        ('rejected', 'Document rejeté'),
        ('deleted', 'Document supprimé'),
        ('migration', 'Migration de données'),
        ('manual', 'Archivage manuel')
    ], string='Raison de l\'archivage',
        required=True,
        help="Raison pour laquelle le document a été archivé")

    archived_date = fields.Datetime(
        string='Date d\'archivage',
        default=fields.Datetime.now,
        required=True,
        help="Date et heure d'archivage"
    )

    archived_by = fields.Many2one(
        'res.users',
        string='Archivé par',
        default=lambda self: self.env.user,
        help="Utilisateur ayant déclenché l'archivage"
    )

    archive_notes = fields.Text(
        string='Notes d\'archivage',
        help="Commentaires sur la raison de l'archivage"
    )

    # =================== DONNÉES ORIGINALES ===================

    original_upload_date = fields.Datetime(
        string='Date d\'upload originale',
        help="Date d'upload du document original"
    )

    original_expiry_date = fields.Date(
        string='Date d\'expiration originale',
        help="Date d'expiration du document original"
    )

    original_state = fields.Selection([
        ('missing', 'Manquant'),
        ('to_check', 'À vérifier'),
        ('valid', 'Valide'),
        ('expiring', 'Expire bientôt'),
        ('expired', 'Expiré'),
        ('rejected', 'Rejeté')
    ], string='État original',
        help="État du document au moment de l'archivage")

    original_validated_by = fields.Many2one(
        'res.users',
        string='Validé originalement par',
        help="Utilisateur ayant validé le document original"
    )

    original_validation_date = fields.Datetime(
        string='Date de validation originale',
        help="Date de validation du document original"
    )

    # =================== CHAMPS CALCULÉS ===================

    display_name = fields.Char(
        string='Nom d\'affichage',
        compute='_compute_display_name',
        store=True
    )

    file_size_human = fields.Char(
        string='Taille (lisible)',
        compute='_compute_file_info',
        store=True,
        help="Taille de fichier formatée"
    )

    days_since_archived = fields.Integer(
        string='Jours depuis archivage',
        compute='_compute_archive_info',
        store=True,
        help="Nombre de jours depuis l'archivage"
    )

    archive_reason_label = fields.Char(
        string='Raison (libellé)',
        compute='_compute_archive_info',
        help="Libellé de la raison d'archivage"
    )

    can_be_restored = fields.Boolean(
        string='Peut être restauré',
        compute='_compute_restore_capability',
        store=True,
        help="Indique si ce document peut être restauré"
    )

    # =================== MÉTHODES CALCULÉES ===================

    @api.depends('partner_id.name', 'document_type_id.name', 'archived_filename', 'archived_date')
    def _compute_display_name(self):
        """Calcule le nom d'affichage de l'archive"""
        for archive in self:
            parts = []
            if archive.partner_id:
                parts.append(archive.partner_id.name)
            if archive.document_type_id:
                parts.append(archive.document_type_id.name)
            if archive.archived_date:
                date_str = DateHelper.format_date_fr(archive.archived_date, include_time=True)
                parts.append(f"({date_str})")

            archive.display_name = ' - '.join(parts) or 'Archive sans nom'

    @api.depends('file_size')
    def _compute_file_info(self):
        """Calcule les informations du fichier"""
        for archive in self:
            if archive.file_size:
                archive.file_size_human = FileHelper.format_file_size(archive.file_size)
            else:
                archive.file_size_human = ""

    @api.depends('archived_date', 'archive_reason')
    def _compute_archive_info(self):
        """Calcule les informations d'archivage"""
        for archive in self:
            # Jours depuis archivage
            if archive.archived_date:
                from datetime import datetime
                days_since = (datetime.now() - archive.archived_date).days
                archive.days_since_archived = days_since
            else:
                archive.days_since_archived = 0

            # Libellé de la raison
            if archive.archive_reason:
                reason_labels = dict(archive._fields['archive_reason'].selection)
                archive.archive_reason_label = reason_labels.get(archive.archive_reason, archive.archive_reason)
            else:
                archive.archive_reason_label = ""

    @api.depends('archive_reason', 'partner_id', 'document_type_id')
    def _compute_restore_capability(self):
        """Détermine si le document peut être restauré"""
        for archive in self:
            # Ne peut pas restaurer si document supprimé ou migration
            if archive.archive_reason in ['deleted', 'migration']:
                archive.can_be_restored = False
                continue

            # Vérifier qu'il n'y a pas déjà un document actif du même type
            existing_doc = self.env['partner.document'].search([
                ('partner_id', '=', archive.partner_id.id),
                ('document_type_id', '=', archive.document_type_id.id)
            ], limit=1)

            archive.can_be_restored = not bool(existing_doc)

    # =================== MÉTHODES AUTOMATIQUES ===================

    @api.model_create_multi
    def create(self, vals_list):
        """Override create pour calculer les informations du fichier"""
        for vals in vals_list:
            if vals.get('archived_content'):
                # Calculer les informations du fichier
                import base64
                file_bytes = base64.b64decode(vals['archived_content'])
                vals['file_size'] = len(file_bytes)
                vals['file_hash'] = FileHelper.calculate_file_hash(file_bytes)

        return super().create(vals_list)

    # =================== ACTIONS ===================

    def action_download(self):
        """Télécharge le document archivé"""
        self.ensure_one()

        if not self.archived_content:
            from odoo.addons.construction_core.utils.helpers import NotificationHelper
            return NotificationHelper.create_odoo_notification(
                "Aucun contenu disponible pour ce document archivé",
                'warning'
            )

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/document.archive/{self.id}/archived_content/{self.archived_filename}?download=true',
            'target': 'self',
        }

    def action_restore(self):
        """Restaure le document archivé"""
        self.ensure_one()

        if not self.can_be_restored:
            from odoo.addons.construction_core.utils.helpers import NotificationHelper
            return NotificationHelper.create_odoo_notification(
                "Ce document ne peut pas être restauré",
                'warning'
            )

        return {
            'type': 'ir.actions.act_window',
            'name': f'Restaurer - {self.display_name}',
            'res_model': 'document.restore.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_archive_id': self.id,
                'default_partner_id': self.partner_id.id,
                'default_document_type_id': self.document_type_id.id,
                'default_original_filename': self.archived_filename,
                'default_original_expiry_date': self.original_expiry_date
            }
        }

    def action_view_replacement(self):
        """Affiche le document qui a remplacé celui-ci"""
        self.ensure_one()

        replacement_doc = self.env['partner.document'].search([
            ('partner_id', '=', self.partner_id.id),
            ('document_type_id', '=', self.document_type_id.id)
        ], limit=1)

        if not replacement_doc:
            from odoo.addons.construction_core.utils.helpers import NotificationHelper
            return NotificationHelper.create_odoo_notification(
                "Aucun document de remplacement trouvé",
                'info'
            )

        return {
            'type': 'ir.actions.act_window',
            'name': f'Document actuel - {self.document_type_id.name}',
            'res_model': 'partner.document',
            'res_id': replacement_doc.id,
            'view_mode': 'form',
            'target': 'current'
        }

    def action_permanent_delete(self):
        """Supprime définitivement l'archive"""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': f'Supprimer définitivement - {self.display_name}',
            'res_model': 'archive.permanent.delete.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_archive_id': self.id,
                'default_archive_name': self.display_name,
                'default_warning_message': 'Cette action est irréversible. Le document sera définitivement supprimé.'
            }
        }

    # =================== MÉTHODES DE RECHERCHE ===================

    @api.model
    def search_by_partner(self, partner_id):
        """Recherche les archives d'un partenaire"""
        return self.search([('partner_id', '=', partner_id)])

    @api.model
    def search_by_document_type(self, document_type_id):
        """Recherche les archives d'un type de document"""
        return self.search([('document_type_id', '=', document_type_id)])

    @api.model
    def search_by_reason(self, reason):
        """Recherche les archives par raison"""
        return self.search([('archive_reason', '=', reason)])

    @api.model
    def search_restorable(self):
        """Recherche les archives qui peuvent être restaurées"""
        return self.search([('can_be_restored', '=', True)])

    @api.model
    def search_recent(self, days=30):
        """Recherche les archives récentes"""
        from datetime import timedelta
        cutoff_date = fields.Datetime.now() - timedelta(days=days)
        return self.search([('archived_date', '>=', cutoff_date)])

    # =================== MÉTHODES D'ADMINISTRATION ===================

    @api.model
    def cleanup_old_archives(self, retention_days=365):
        """Nettoie les anciennes archives selon la politique de rétention"""
        from datetime import timedelta

        cutoff_date = fields.Datetime.now() - timedelta(days=retention_days)

        # Archives anciennes non critiques
        old_archives = self.search([
            ('archived_date', '<', cutoff_date),
            ('archive_reason', 'in', ['replaced', 'expired', 'rejected'])
        ])

        deleted_count = len(old_archives)

        # Log avant suppression
        for archive in old_archives:
            _logger.info(
                f"Cleaning up archive: {archive.display_name} (archived {archive.days_since_archived} days ago)")

        old_archives.unlink()

        _logger.info(f"Cleaned up {deleted_count} old archives (older than {retention_days} days)")
        return deleted_count

    @api.model
    def get_storage_statistics(self):
        """Retourne les statistiques de stockage des archives"""
        archives = self.search([])

        total_size = sum(archives.mapped('file_size'))
        total_count = len(archives)

        # Répartition par raison
        reason_stats = {}
        for reason_value, reason_label in self._fields['archive_reason'].selection:
            reason_archives = archives.filtered(lambda a: a.archive_reason == reason_value)
            reason_stats[reason_label] = {
                'count': len(reason_archives),
                'size': sum(reason_archives.mapped('file_size')),
                'size_human': FileHelper.format_file_size(sum(reason_archives.mapped('file_size')))
            }

        # Répartition par type de document
        type_stats = {}
        for doc_type in self.env['document.type'].search([]):
            type_archives = archives.filtered(lambda a: a.document_type_id == doc_type)
            if type_archives:
                type_stats[doc_type.name] = {
                    'count': len(type_archives),
                    'size': sum(type_archives.mapped('file_size')),
                    'size_human': FileHelper.format_file_size(sum(type_archives.mapped('file_size')))
                }

        return {
            'total_count': total_count,
            'total_size': total_size,
            'total_size_human': FileHelper.format_file_size(total_size),
            'by_reason': reason_stats,
            'by_type': type_stats,
            'oldest_archive': min(archives.mapped('archived_date')) if archives else None,
            'newest_archive': max(archives.mapped('archived_date')) if archives else None
        }

    @api.model
    def export_archive_report(self, partner_ids=None, date_from=None, date_to=None):
        """Exporte un rapport des archives"""
        domain = []

        if partner_ids:
            domain.append(('partner_id', 'in', partner_ids))

        if date_from:
            domain.append(('archived_date', '>=', date_from))

        if date_to:
            domain.append(('archived_date', '<=', date_to))

        archives = self.search(domain)

        report_data = []
        for archive in archives:
            report_data.append({
                'partner_name': archive.partner_id.name,
                'document_type': archive.document_type_id.name,
                'filename': archive.archived_filename,
                'archive_reason': archive.archive_reason_label,
                'archived_date': archive.archived_date,
                'archived_by': archive.archived_by.name,
                'file_size': archive.file_size_human,
                'original_upload_date': archive.original_upload_date,
                'original_expiry_date': archive.original_expiry_date,
                'days_since_archived': archive.days_since_archived,
                'can_be_restored': archive.can_be_restored
            })

        return report_data

    # =================== MÉTHODES CRON ===================

    @api.model
    def cron_cleanup_old_archives(self):
        """Tâche planifiée de nettoyage des anciennes archives"""
        # Récupérer la politique de rétention depuis les paramètres système
        retention_days = int(self.env['ir.config_parameter'].sudo().get_param(
            'construction_contact_extension.archive_retention_days',
            default='365'
        ))

        return self.cleanup_old_archives(retention_days)

    # =================== CONTRAINTES ===================

    @api.constrains('archived_content')
    def _check_archived_content(self):
        """Vérifie que le contenu archivé n'est pas vide"""
        for archive in self:
            if not archive.archived_content:
                raise ValidationError("Le contenu archivé ne peut pas être vide")

    @api.constrains('original_expiry_date', 'original_upload_date')
    def _check_original_dates(self):
        """Vérifie la cohérence des dates originales"""
        for archive in self:
            if (archive.original_expiry_date and archive.original_upload_date and
                    archive.original_expiry_date <= archive.original_upload_date.date()):
                raise ValidationError(
                    "La date d'expiration originale doit être postérieure à la date d'upload originale"
                )

    # =================== HOOKS ===================

    def _get_trackable_fields(self):
        """Champs à suivre pour le TrackingMixin"""
        return ['archive_reason', 'archive_notes']

    def unlink(self):
        """Override unlink pour logger la suppression définitive"""
        for archive in self:
            _logger.warning(f"Permanent deletion of archive: {archive.display_name}")

        return super().unlink()
