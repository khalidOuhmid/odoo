# -*- coding: utf-8 -*-
"""
Assistant pour la restauration de documents archivés
===================================================

Permet de restaurer un document depuis les archives.
"""

from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.addons.construction_core.utils.helpers import NotificationHelper, DateHelper
import logging

_logger = logging.getLogger(__name__)


class DocumentRestoreWizard(models.TransientModel):
    """Assistant pour restaurer un document archivé"""

    _name = 'document.restore.wizard'
    _description = 'Assistant Restauration Document'

    # =================== CHAMPS PRINCIPAUX ===================

    archive_id = fields.Many2one(
        'document.archive',
        string='Archive',
        required=True,
        readonly=True,
        help="Archive à restaurer"
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Partenaire',
        related='archive_id.partner_id',
        readonly=True
    )

    document_type_id = fields.Many2one(
        'document.type',
        string='Type de document',
        related='archive_id.document_type_id',
        readonly=True
    )

    original_filename = fields.Char(
        string='Nom de fichier original',
        related='archive_id.archived_filename',
        readonly=True
    )

    original_expiry_date = fields.Date(
        string='Date d\'expiration originale',
        help="Date d'expiration du document restauré"
    )

    # =================== OPTIONS DE RESTAURATION ===================

    restore_mode = fields.Selection([
        ('as_draft', 'Restaurer comme brouillon'),
        ('as_to_check', 'Restaurer à vérifier'),
        ('keep_original_state', 'Conserver l\'état original')
    ], string='Mode de restauration',
        default='as_to_check',
        required=True,
        help="État du document après restauration")

    update_filename = fields.Boolean(
        string='Mettre à jour le nom de fichier',
        default=False,
        help="Ajouter un suffixe au nom de fichier"
    )

    new_filename = fields.Char(
        string='Nouveau nom de fichier',
        help="Nouveau nom pour le fichier restauré"
    )

    update_expiry_date = fields.Boolean(
        string='Mettre à jour la date d\'expiration',
        default=False,
        help="Calculer une nouvelle date d'expiration"
    )

    new_expiry_date = fields.Date(
        string='Nouvelle date d\'expiration',
        help="Nouvelle date d'expiration"
    )

    # =================== INFORMATIONS CONTEXTUELLES ===================

    archive_reason = fields.Selection(
        related='archive_id.archive_reason',
        readonly=True
    )

    archived_date = fields.Datetime(
        related='archive_id.archived_date',
        readonly=True
    )

    days_since_archived = fields.Integer(
        related='archive_id.days_since_archived',
        readonly=True
    )

    file_size_human = fields.Char(
        related='archive_id.file_size_human',
        readonly=True
    )

    # =================== VÉRIFICATIONS ===================

    existing_document_id = fields.Many2one(
        'partner.document',
        string='Document existant',
        compute='_compute_existing_document',
        help="Document actuel du même type s'il existe"
    )

    has_existing_document = fields.Boolean(
        string='Document existant trouvé',
        compute='_compute_existing_document'
    )

    can_restore = fields.Boolean(
        string='Peut être restauré',
        compute='_compute_restore_capability'
    )

    restore_warnings = fields.Html(
        string='Avertissements',
        compute='_compute_restore_capability'
    )

    # =================== MÉTHODES CALCULÉES ===================

    @api.depends('partner_id', 'document_type_id')
    def _compute_existing_document(self):
        """Vérifie s'il existe déjà un document du même type"""
        for wizard in self:
            if wizard.partner_id and wizard.document_type_id:
                existing = wizard.env['partner.document'].search([
                    ('partner_id', '=', wizard.partner_id.id),
                    ('document_type_id', '=', wizard.document_type_id.id)
                ], limit=1)

                wizard.existing_document_id = existing.id if existing else False
                wizard.has_existing_document = bool(existing)
            else:
                wizard.existing_document_id = False
                wizard.has_existing_document = False

    @api.depends('has_existing_document', 'archive_id')
    def _compute_restore_capability(self):
        """Détermine si la restauration est possible et les avertissements"""
        for wizard in self:
            warnings = []
            can_restore = True

            # Vérifier s'il y a un document existant
            if wizard.has_existing_document:
                warnings.append(
                    "⚠️ Un document du même type existe déjà. "
                    "La restauration remplacera le document actuel."
                )

            # Vérifier l'âge de l'archive
            if wizard.days_since_archived > 365:
                warnings.append(
                    f"⚠️ Cette archive date de {wizard.days_since_archived} jours. "
                    "Les informations peuvent être obsolètes."
                )

            # Vérifier la raison d'archivage
            if wizard.archive_reason == 'deleted':
                warnings.append(
                    "⚠️ Ce document avait été supprimé. "
                    "Vérifiez la pertinence de la restauration."
                )
            elif wizard.archive_reason == 'rejected':
                warnings.append(
                    "⚠️ Ce document avait été rejeté. "
                    "Assurez-vous qu'il est maintenant acceptable."
                )

            # Vérifier la date d'expiration
            if wizard.original_expiry_date and wizard.original_expiry_date < fields.Date.today():
                warnings.append(
                    f"⚠️ Ce document était expiré ({DateHelper.format_date_fr(wizard.original_expiry_date)}). "
                    "Considérez mettre à jour la date d'expiration."
                )

            wizard.can_restore = can_restore
            wizard.restore_warnings = "<br/>".join(warnings) if warnings else "Aucun avertissement"

    # =================== MÉTHODES UTILITAIRES ===================

    @api.onchange('update_filename')
    def _onchange_update_filename(self):
        """Génère automatiquement un nouveau nom de fichier"""
        if self.update_filename and self.original_filename:
            # Ajouter un suffixe avec la date
            from datetime import datetime
            suffix = f"_restored_{datetime.now().strftime('%Y%m%d')}"

            if '.' in self.original_filename:
                name, ext = self.original_filename.rsplit('.', 1)
                self.new_filename = f"{name}{suffix}.{ext}"
            else:
                self.new_filename = f"{self.original_filename}{suffix}"
        else:
            self.new_filename = self.original_filename

    @api.onchange('update_expiry_date', 'document_type_id')
    def _onchange_update_expiry_date(self):
        """Calcule automatiquement une nouvelle date d'expiration"""
        if self.update_expiry_date and self.document_type_id:
            self.new_expiry_date = self.document_type_id.get_default_expiry_date()
        else:
            self.new_expiry_date = self.original_expiry_date

    # =================== ACTION PRINCIPALE ===================

    def action_restore_document(self):
        """Effectue la restauration du document"""
        self.ensure_one()

        if not self.can_restore:
            raise ValidationError("Cette archive ne peut pas être restaurée")

        try:
            # 1. Archiver le document existant s'il y en a un
            if self.has_existing_document:
                existing_doc = self.existing_document_id
                if existing_doc.file_content:
                    existing_doc._archive_current_version('replaced')
                existing_doc.unlink()

            # 2. Préparer les données du nouveau document
            restore_data = {
                'partner_id': self.partner_id.id,
                'document_type_id': self.document_type_id.id,
                'file_content': self.archive_id.archived_content,
                'filename': self.new_filename or self.original_filename,
                'expiry_date': self.new_expiry_date,
                'upload_date': fields.Datetime.now(),
                'state': self._get_restore_state()
            }

            # 3. Créer le document restauré
            restored_doc = self.env['partner.document'].create(restore_data)

            # 4. Ajouter une note de restauration
            restore_note = f"""
                Document restauré depuis les archives le {fields.Datetime.now().strftime('%d/%m/%Y à %H:%M')}

                Archive originale du {DateHelper.format_date_fr(self.archived_date, include_time=True)}
                Raison d'archivage : {dict(self.archive_id._fields['archive_reason'].selection)[self.archive_reason]}
                Restauré par : {self.env.user.name}
            """

            restored_doc.message_post(
                body=f"🔄 {restore_note}",
                message_type='notification'
            )

            # 5. Log de la restauration sur l'archive
            self.archive_id.message_post(
                body=f"📤 Document restauré par {self.env.user.name}",
                message_type='notification'
            )

            return {
                'type': 'ir.actions.act_window',
                'name': 'Document restauré',
                'res_model': 'partner.document',
                'res_id': restored_doc.id,
                'view_mode': 'form',
                'target': 'current'
            }

        except Exception as e:
            _logger.error(f"Error restoring document from archive {self.archive_id.id}: {str(e)}")
            return NotificationHelper.create_odoo_notification(
                f"Erreur lors de la restauration : {str(e)}",
                'danger'
            )

    def _get_restore_state(self):
        """Détermine l'état du document restauré"""
        state_map = {
            'as_draft': 'missing',
            'as_to_check': 'to_check',
            'keep_original_state': self.archive_id.original_state or 'to_check'
        }
        return state_map.get(self.restore_mode, 'to_check')

    # =================== ACTIONS SECONDAIRES ===================

    def action_preview_restored_document(self):
        """Prévisualise le document qui sera restauré"""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Prévisualisation document restauré',
            'res_model': 'document.preview.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_file_content': self.archive_id.archived_content,
                'default_filename': self.new_filename or self.original_filename,
                'default_preview_mode': 'restore'
            }
        }

    def action_view_existing_document(self):
        """Affiche le document existant qui sera remplacé"""
        self.ensure_one()

        if not self.has_existing_document:
            return NotificationHelper.create_odoo_notification(
                "Aucun document existant à afficher",
                'info'
            )

        return {
            'type': 'ir.actions.act_window',
            'name': 'Document actuel',
            'res_model': 'partner.document',
            'res_id': self.existing_document_id.id,
            'view_mode': 'form',
            'target': 'new'
        }

    def action_cancel_restore(self):
        """Annule la restauration"""
        return {'type': 'ir.actions.act_window_close'}

    # =================== CONTRAINTES ===================

    @api.constrains('new_expiry_date')
    def _check_new_expiry_date(self):
        """Vérifie que la nouvelle date d'expiration est valide"""
        for wizard in self:
            if wizard.new_expiry_date and wizard.new_expiry_date <= fields.Date.today():
                raise ValidationError("La nouvelle date d'expiration doit être dans le futur")

    @api.constrains('new_filename')
    def _check_new_filename(self):
        """Vérifie que le nouveau nom de fichier est valide"""
        for wizard in self:
            if wizard.new_filename:
                if len(wizard.new_filename) > 255:
                    raise ValidationError("Le nom de fichier ne peut dépasser 255 caractères")

                # Caractères interdits
                forbidden_chars = ['<', '>', ':', '"', '|', '?', '*']
                if any(char in wizard.new_filename for char in forbidden_chars):
                    raise ValidationError(
                        f"Le nom de fichier contient des caractères interdits : {', '.join(forbidden_chars)}")
