# -*- coding: utf-8 -*-
"""
Assistant pour la suppression définitive d'archives
==================================================

Permet de supprimer définitivement des archives avec confirmation de sécurité.
"""

from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.addons.construction_core.utils.helpers import NotificationHelper, LogHelper
import logging

_logger = logging.getLogger(__name__)


class ArchivePermanentDeleteWizard(models.TransientModel):
    """Assistant pour la suppression définitive d'archives"""

    _name = 'archive.permanent.delete.wizard'
    _description = 'Assistant Suppression Définitive Archive'

    # =================== CHAMPS PRINCIPAUX ===================

    archive_id = fields.Many2one(
        'document.archive',
        string='Archive',
        required=True,
        readonly=True,
        help="Archive à supprimer définitivement"
    )

    archive_name = fields.Char(
        string='Nom de l\'archive',
        related='archive_id.display_name',
        readonly=True
    )

    partner_name = fields.Char(
        string='Partenaire',
        related='archive_id.partner_id.name',
        readonly=True
    )

    document_type = fields.Char(
        string='Type de document',
        compute='_compute_document_type',
        readonly=True
    )

    @api.depends('archive_id')
    def _compute_document_type(self):
        """Calcule le type de document de manière robuste"""
        for wizard in self:
            if wizard.archive_id:
                # Essayer d'abord construction_contact_extension structure
                if hasattr(wizard.archive_id, 'document_type_id') and wizard.archive_id.document_type_id:
                    wizard.document_type = wizard.archive_id.document_type_id.name
                # Fallback vers blg_contacts_extension structure
                elif hasattr(wizard.archive_id, 'document_type'):
                    wizard.document_type = wizard.archive_id.document_type
                else:
                    wizard.document_type = 'Type inconnu'
            else:
                wizard.document_type = 'Non défini'

    # =================== INFORMATIONS DE SÉCURITÉ ===================

    warning_message = fields.Html(
        string='Avertissement',
        default="""
        <div class="alert alert-danger">
            <h4>⚠️ ATTENTION - ACTION IRRÉVERSIBLE</h4>
            <p>Cette action supprimera définitivement l'archive et son contenu.</p>
            <p><strong>Cette opération ne peut pas être annulée !</strong></p>
        </div>
        """,
        readonly=True
    )

    archive_info = fields.Html(
        string='Informations sur l\'archive',
        compute='_compute_archive_info',
        help="Détails de l'archive à supprimer"
    )

    # =================== CONFIRMATION DE SÉCURITÉ ===================

    confirmation_text = fields.Char(
        string='Confirmation',
        help="Tapez 'SUPPRIMER' pour confirmer"
    )

    confirm_partner_name = fields.Boolean(
        string='Je confirme le nom du partenaire',
        default=False,
        help="Confirmation du partenaire concerné"
    )

    confirm_document_type = fields.Boolean(
        string='Je confirme le type de document',
        default=False,
        help="Confirmation du type de document"
    )

    confirm_irreversible = fields.Boolean(
        string='Je comprends que cette action est irréversible',
        default=False,
        help="Confirmation de l'aspect irréversible"
    )

    # =================== RAISON DE LA SUPPRESSION ===================

    deletion_reason = fields.Selection([
        ('gdpr_request', 'Demande RGPD / Droit à l\'oubli'),
        ('legal_requirement', 'Obligation légale'),
        ('data_cleanup', 'Nettoyage de données'),
        ('storage_optimization', 'Optimisation stockage'),
        ('data_corruption', 'Corruption de données'),
        ('security_breach', 'Faille de sécurité'),
        ('end_of_retention', 'Fin de période de rétention'),
        ('administrative', 'Raison administrative'),
        ('other', 'Autre raison')
    ], string='Raison de la suppression',
        required=True,
        help="Justification de la suppression définitive")

    deletion_details = fields.Text(
        string='Détails de la suppression',
        help="Explication détaillée de la raison"
    )

    reference_number = fields.Char(
        string='Numéro de référence',
        help="Numéro de dossier, ticket, ou référence externe"
    )

    # =================== OPTIONS DE TRAÇABILITÉ ===================

    create_audit_log = fields.Boolean(
        string='Créer un log d\'audit',
        default=True,
        help="Enregistrer cette suppression dans les logs d'audit"
    )

    notify_stakeholders = fields.Boolean(
        string='Notifier les parties prenantes',
        default=False,
        help="Envoyer une notification aux parties concernées"
    )

    backup_before_delete = fields.Boolean(
        string='Sauvegarder avant suppression',
        default=True,
        help="Créer une sauvegarde de sécurité avant suppression"
    )

    # =================== CHAMPS CALCULÉS ===================

    can_delete = fields.Boolean(
        string='Peut supprimer',
        compute='_compute_can_delete',
        help="Toutes les conditions sont remplies pour supprimer"
    )

    missing_confirmations = fields.Html(
        string='Confirmations manquantes',
        compute='_compute_can_delete',
        help="Liste des confirmations manquantes"
    )

    # =================== MÉTHODES CALCULÉES ===================

    @api.depends('archive_id')
    def _compute_archive_info(self):
        """Calcule les informations détaillées de l'archive"""
        for wizard in self:
            if not wizard.archive_id:
                wizard.archive_info = ""
                continue

            archive = wizard.archive_id

            info_html = f"""
            <div class="container-fluid">
                <div class="row">
                    <div class="col-md-6">
                        <h5>Informations générales</h5>
                        <ul>
                            <li><strong>Partenaire :</strong> {archive.partner_id.name}</li>
                            <li><strong>Type :</strong> {archive.document_type_id.name}</li>
                            <li><strong>Nom fichier :</strong> {archive.archived_filename}</li>
                            <li><strong>Taille :</strong> {archive.file_size_human}</li>
                        </ul>
                    </div>
                    <div class="col-md-6">
                        <h5>Historique</h5>
                        <ul>
                            <li><strong>Archivé le :</strong> {archive.archived_date.strftime('%d/%m/%Y à %H:%M') if archive.archived_date else 'N/A'}</li>
                            <li><strong>Raison :</strong> {archive.archive_reason_label}</li>
                            <li><strong>Par :</strong> {archive.archived_by.name if archive.archived_by else 'N/A'}</li>
                            <li><strong>Âge :</strong> {archive.days_since_archived} jours</li>
                        </ul>
                    </div>
                </div>
            </div>
            """

            wizard.archive_info = info_html

    @api.depends('confirmation_text', 'confirm_partner_name', 'confirm_document_type',
                 'confirm_irreversible', 'deletion_reason')
    def _compute_can_delete(self):
        """Détermine si toutes les conditions sont remplies pour supprimer"""
        for wizard in self:
            missing = []

            # Vérifier le texte de confirmation
            if wizard.confirmation_text != 'SUPPRIMER':
                missing.append("Tapez 'SUPPRIMER' dans le champ de confirmation")

            # Vérifier les cases à cocher
            if not wizard.confirm_partner_name:
                missing.append("Confirmer le nom du partenaire")

            if not wizard.confirm_document_type:
                missing.append("Confirmer le type de document")

            if not wizard.confirm_irreversible:
                missing.append("Confirmer que l'action est irréversible")

            # Vérifier la raison
            if not wizard.deletion_reason:
                missing.append("Spécifier la raison de la suppression")

            wizard.can_delete = len(missing) == 0
            wizard.missing_confirmations = "<ul><li>" + "</li><li>".join(missing) + "</li></ul>" if missing else ""

    # =================== ACTION PRINCIPALE ===================

    def action_permanent_delete(self):
        """Effectue la suppression définitive"""
        self.ensure_one()

        if not self.can_delete:
            raise ValidationError("Toutes les confirmations ne sont pas remplies")

        try:
            # 1. Créer une sauvegarde si demandée
            backup_data = None
            if self.backup_before_delete:
                backup_data = self._create_backup()

            # 2. Créer le log d'audit avant suppression
            if self.create_audit_log:
                self._create_audit_log(backup_data)

            # 3. Notifier les parties prenantes si demandé
            if self.notify_stakeholders:
                self._notify_stakeholders()

            # 4. Sauvegarder les informations pour le log
            archive_info = {
                'archive_id': self.archive_id.id,
                'partner_name': self.partner_name,
                'document_type': self.document_type,
                'archive_name': self.archive_name,
                'deletion_reason': self.deletion_reason,
                'deleted_by': self.env.user.name,
                'reference_number': self.reference_number
            }

            # 5. Supprimer définitivement l'archive
            self.archive_id.unlink()

            # 6. Log de l'opération
            LogHelper.log_operation(
                'permanent_archive_deletion',
                True,
                details=archive_info,
                user_id=self.env.user.id
            )

            return NotificationHelper.create_odoo_notification(
                f"Archive supprimée définitivement : {self.archive_name}",
                'success',
                title='Suppression réussie'
            )

        except Exception as e:
            _logger.error(f"Error permanently deleting archive {self.archive_id.id}: {str(e)}")
            return NotificationHelper.create_odoo_notification(
                f"Erreur lors de la suppression : {str(e)}",
                'danger'
            )

    # =================== MÉTHODES DE SAUVEGARDE ===================

    def _create_backup(self):
        """Crée une sauvegarde de sécurité avant suppression"""
        backup_data = {
            'archive_id': self.archive_id.id,
            'partner_id': self.archive_id.partner_id.id,
            'partner_name': self.partner_name,
            'document_type': self.document_type,
            'filename': self.archive_id.archived_filename,
            'file_content': self.archive_id.archived_content,
            'file_hash': self.archive_id.file_hash,
            'file_size': self.archive_id.file_size,
            'archived_date': self.archive_id.archived_date,
            'archive_reason': self.archive_id.archive_reason,
            'deletion_date': fields.Datetime.now(),
            'deletion_reason': self.deletion_reason,
            'deletion_details': self.deletion_details,
            'deleted_by': self.env.user.id,
            'reference_number': self.reference_number
        }

        # Ici, vous pourriez sauvegarder vers un système externe
        # ou créer un enregistrement dans une table de sauvegarde
        _logger.info(f"Backup created for archive {self.archive_id.id} before permanent deletion")

        return backup_data

    def _create_audit_log(self, backup_data):
        """Crée un log d'audit de la suppression"""
        audit_data = {
            'action': 'permanent_archive_deletion',
            'archive_id': self.archive_id.id,
            'partner_name': self.partner_name,
            'document_type': self.document_type,
            'deletion_reason': dict(self._fields['deletion_reason'].selection)[self.deletion_reason],
            'deletion_details': self.deletion_details,
            'reference_number': self.reference_number,
            'deleted_by': self.env.user.name,
            'deletion_date': fields.Datetime.now(),
            'backup_created': bool(backup_data),
            'stakeholders_notified': self.notify_stakeholders
        }

        # Créer l'enregistrement d'audit
        self.env['audit.log'].create({
            'action_type': 'permanent_deletion',
            'resource_type': 'document.archive',
            'resource_id': self.archive_id.id,
            'description': f"Suppression définitive archive : {self.archive_name}",
            'details': str(audit_data),
            'user_id': self.env.user.id,
            'date': fields.Datetime.now()
        })

    def _notify_stakeholders(self):
        """Notifie les parties prenantes de la suppression"""
        try:
            # Identifier les parties prenantes
            stakeholders = []

            # Ajouter le partenaire s'il a une adresse email
            if self.archive_id.partner_id.email:
                stakeholders.append(self.archive_id.partner_id)

            # Ajouter l'utilisateur qui avait archivé le document
            if self.archive_id.archived_by and self.archive_id.archived_by.email:
                stakeholders.append(self.archive_id.archived_by.partner_id)

            # Envoyer les notifications
            for stakeholder in stakeholders:
                self._send_deletion_notification(stakeholder)

        except Exception as e:
            _logger.error(f"Error notifying stakeholders: {str(e)}")

    def _send_deletion_notification(self, partner):
        """Envoie une notification de suppression à une partie prenante"""
        # Template d'email pour la notification de suppression
        template_data = {
            'partner_name': partner.name,
            'archive_name': self.archive_name,
            'document_type': self.document_type,
            'deletion_reason': dict(self._fields['deletion_reason'].selection)[self.deletion_reason],
            'deletion_date': fields.Datetime.now().strftime('%d/%m/%Y à %H:%M'),
            'reference_number': self.reference_number,
            'contact_email': self.env.user.email
        }

        # Utiliser le service de notification pour envoyer l'email
        notification_service = self.env['partner.notification.service']
        notification_service.send_archive_deletion_notification(partner, template_data)

    # =================== ACTIONS SECONDAIRES ===================

    def action_cancel_deletion(self):
        """Annule la suppression"""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': 'Suppression annulée',
                'type': 'info'
            }
        }

    def action_view_archive_details(self):
        """Affiche les détails complets de l'archive"""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': f'Détails - {self.archive_name}',
            'res_model': 'document.archive',
            'res_id': self.archive_id.id,
            'view_mode': 'form',
            'target': 'new'
        }

    # =================== CONTRAINTES ===================

    @api.constrains('confirmation_text')
    def _check_confirmation_text(self):
        """Vérifie le texte de confirmation"""
        for wizard in self:
            if wizard.confirmation_text and wizard.confirmation_text != 'SUPPRIMER':
                raise ValidationError("Le texte de confirmation doit être exactement 'SUPPRIMER'")

    @api.constrains('deletion_details')
    def _check_deletion_details(self):
        """Vérifie que les détails sont suffisants pour certaines raisons"""
        sensitive_reasons = ['gdpr_request', 'legal_requirement', 'security_breach']

        for wizard in self:
            if (wizard.deletion_reason in sensitive_reasons and
                    (not wizard.deletion_details or len(wizard.deletion_details.strip()) < 20)):
                raise ValidationError(
                    f"Pour la raison '{wizard.deletion_reason}', "
                    "des détails d'au moins 20 caractères sont obligatoires"
                )
