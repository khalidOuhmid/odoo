# -*- coding: utf-8 -*-
"""
Assistant pour le rejet de documents avec raison
===============================================

Permet de rejeter un document en spécifiant une raison détaillée.
"""

from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.addons.construction_core.utils.helpers import NotificationHelper
import logging

_logger = logging.getLogger(__name__)


class DocumentRejectionWizard(models.TransientModel):
    """Assistant pour rejeter un document avec raison"""

    _name = 'document.rejection.wizard'
    _description = 'Assistant Rejet Document'

    # =================== CHAMPS PRINCIPAUX ===================

    document_id = fields.Many2one(
        'partner.document',
        string='Document',
        required=True,
        readonly=True,
        help="Document à rejeter"
    )

    document_name = fields.Char(
        string='Nom du document',
        related='document_id.display_name',
        readonly=True
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Partenaire',
        related='document_id.partner_id',
        readonly=True
    )

    # =================== RAISON DU REJET ===================

    rejection_reason = fields.Selection([
        ('poor_quality', 'Qualité insuffisante'),
        ('illegible', 'Document illisible'),
        ('expired', 'Document expiré'),
        ('wrong_type', 'Mauvais type de document'),
        ('incomplete', 'Document incomplet'),
        ('corrupted', 'Fichier corrompu'),
        ('invalid_format', 'Format non valide'),
        ('missing_info', 'Informations manquantes'),
        ('wrong_person', 'Document d\'une autre personne'),
        ('other', 'Autre raison')
    ], string='Raison du rejet',
        required=True,
        help="Raison principale du rejet")

    rejection_details = fields.Text(
        string='Détails du rejet',
        required=True,
        help="Explication détaillée du rejet"
    )

    required_actions = fields.Html(
        string='Actions requises',
        help="Actions que le partenaire doit effectuer"
    )

    # =================== OPTIONS DE NOTIFICATION ===================

    notify_partner = fields.Boolean(
        string='Notifier le partenaire',
        default=True,
        help="Envoyer une notification au partenaire"
    )

    send_email = fields.Boolean(
        string='Envoyer par email',
        default=True,
        help="Envoyer un email de notification"
    )

    include_instructions = fields.Boolean(
        string='Inclure les instructions',
        default=True,
        help="Inclure les instructions de correction"
    )

    # =================== GESTION DE L'ARCHIVAGE ===================

    archive_document = fields.Boolean(
        string='Archiver le document rejeté',
        default=True,
        help="Archiver l'ancienne version"
    )

    allow_resubmission = fields.Boolean(
        string='Autoriser une nouvelle soumission',
        default=True,
        help="Le partenaire peut soumettre une nouvelle version"
    )

    # =================== CHAMPS CALCULÉS ===================

    can_send_email = fields.Boolean(
        string='Peut envoyer email',
        compute='_compute_notification_capabilities'
    )

    rejection_count = fields.Integer(
        string='Nombre de rejets',
        compute='_compute_document_history',
        help="Nombre de fois que ce type de document a été rejeté"
    )

    # =================== MÉTHODES CALCULÉES ===================

    @api.depends('partner_id.email')
    def _compute_notification_capabilities(self):
        """Calcule les capacités de notification"""
        for wizard in self:
            if wizard.partner_id and wizard.partner_id.email:
                from odoo.addons.construction_core.utils.validators import TextValidator
                email_validation = TextValidator.validate_email(wizard.partner_id.email)
                wizard.can_send_email = email_validation['valid']
            else:
                wizard.can_send_email = False

    @api.depends('document_id', 'partner_id')
    def _compute_document_history(self):
        """Calcule l'historique de rejets"""
        for wizard in self:
            if wizard.document_id and wizard.partner_id:
                # Compter les rejets précédents pour ce type de document
                rejection_count = wizard.env['document.archive'].search_count([
                    ('partner_id', '=', wizard.partner_id.id),
                    ('document_type_id', '=', wizard.document_id.document_type_id.id),
                    ('archive_reason', '=', 'rejected')
                ])
                wizard.rejection_count = rejection_count
            else:
                wizard.rejection_count = 0

    # =================== MÉTHODES DE PRÉPARATION ===================

    @api.model
    def default_get(self, fields_list):
        """Initialise le wizard avec les données par défaut"""
        res = super().default_get(fields_list)

        document_id = self.env.context.get('default_document_id')
        if document_id:
            document = self.env['partner.document'].browse(document_id)

            # Préparer les instructions selon le type de document
            instructions = self._prepare_rejection_instructions(document)
            res['required_actions'] = instructions

        return res

    def _prepare_rejection_instructions(self, document):
        """Prépare les instructions de correction selon le type de document"""
        doc_type = document.document_type_id.code

        instructions_map = {
            'identity_card': """
                <h4>Pour corriger votre carte d'identité :</h4>
                <ul>
                    <li>Scannez ou photographez les deux faces</li>
                    <li>Assurez-vous que le texte soit parfaitement lisible</li>
                    <li>Format accepté : PDF, JPG, PNG</li>
                    <li>Résolution minimum : 300 DPI</li>
                </ul>
            """,
            'kbis': """
                <h4>Pour corriger votre KBIS :</h4>
                <ul>
                    <li>Le document doit dater de moins de 3 mois</li>
                    <li>Scannez l'original en couleur</li>
                    <li>Vérifiez que toutes les informations soient visibles</li>
                    <li>Format requis : PDF uniquement</li>
                </ul>
            """,
            'urssaf': """
                <h4>Pour corriger votre attestation URSSAF :</h4>
                <ul>
                    <li>Document officiel avec cachet URSSAF</li>
                    <li>Doit être en cours de validité</li>
                    <li>Scan de qualité professionnelle</li>
                    <li>Toutes les pages si document multi-pages</li>
                </ul>
            """,
            'insurance': """
                <h4>Pour corriger votre assurance :</h4>
                <ul>
                    <li>Attestation en cours de validité</li>
                    <li>Montants de garantie visibles</li>
                    <li>Activités couvertes correspondant à vos spécialités</li>
                    <li>Signature et cachet de l'assureur</li>
                </ul>
            """,
            'rib': """
                <h4>Pour corriger votre RIB :</h4>
                <ul>
                    <li>RIB original de la banque</li>
                    <li>IBAN parfaitement lisible</li>
                    <li>Nom du titulaire correspondant</li>
                    <li>Pas de photocopie de photocopie</li>
                </ul>
            """
        }

        return instructions_map.get(doc_type, """
            <h4>Instructions générales :</h4>
            <ul>
                <li>Document original et lisible</li>
                <li>Format PDF de préférence</li>
                <li>Bonne résolution</li>
                <li>Informations complètes et visibles</li>
            </ul>
        """)

    # =================== ACTION PRINCIPALE ===================

    def action_reject_document(self):
        """Effectue le rejet du document"""
        self.ensure_one()

        if not self.rejection_details:
            raise ValidationError("Les détails du rejet sont obligatoires")

        try:
            # 1. Archiver le document actuel si demandé
            if self.archive_document and self.document_id.file_content:
                self.document_id._archive_current_version('rejected')

            # 2. Mettre à jour le document
            rejection_note = f"""
                REJET - {dict(self._fields['rejection_reason'].selection)[self.rejection_reason]}

                Détails: {self.rejection_details}

                Rejeté le {fields.Datetime.now().strftime('%d/%m/%Y à %H:%M')} par {self.env.user.name}
            """

            self.document_id.write({
                'state': 'rejected',
                'validation_notes': rejection_note,
                'validated_by': self.env.user.id,
                'validation_date': fields.Datetime.now()
            })

            # 3. Message sur le document
            self.document_id.message_post(
                body=f"❌ Document rejeté : {self.rejection_reason}<br/>{self.rejection_details}",
                message_type='notification'
            )

            # 4. Notification au partenaire si demandée
            if self.notify_partner:
                self._send_rejection_notification()

            # 5. Créer un nouveau document vide si résoumission autorisée
            if self.allow_resubmission:
                self._create_new_document_placeholder()

            return NotificationHelper.create_odoo_notification(
                f"Document rejeté : {self.rejection_reason}",
                'success',
                title='Document rejeté'
            )

        except Exception as e:
            _logger.error(f"Error rejecting document {self.document_id.id}: {str(e)}")
            return NotificationHelper.create_odoo_notification(
                f"Erreur lors du rejet : {str(e)}",
                'danger'
            )

    # =================== MÉTHODES DE NOTIFICATION ===================

    def _send_rejection_notification(self):
        """Envoie la notification de rejet"""
        if not self.can_send_email or not self.send_email:
            return

        try:
            # Utiliser le service de notification
            notification_service = self.env['partner.notification.service']

            rejection_data = {
                'document_type': self.document_id.document_type_id.name,
                'rejection_reason': dict(self._fields['rejection_reason'].selection)[self.rejection_reason],
                'rejection_details': self.rejection_details,
                'required_actions': self.required_actions if self.include_instructions else '',
                'rejection_count': self.rejection_count + 1,
                'upload_link': self._get_upload_link()
            }

            notification_service.send_document_rejection_notification(
                self.partner_id,
                rejection_data
            )

        except Exception as e:
            _logger.error(f"Error sending rejection notification: {str(e)}")

    def _get_upload_link(self):
        """Génère le lien d'upload pour le partenaire"""
        if not self.allow_resubmission:
            return ""

        # Générer un token si nécessaire
        if not self.partner_id.is_token_valid():
            self.partner_id.generate_upload_token()

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return f"{base_url}/documents/upload/{self.partner_id.upload_token}"

    def _create_new_document_placeholder(self):
        """Crée un nouveau document vide pour la résoumission"""
        self.env['partner.document'].create({
            'partner_id': self.partner_id.id,
            'document_type_id': self.document_id.document_type_id.id,
            'state': 'missing'
        })

    # =================== ACTIONS SECONDAIRES ===================

    def action_preview_notification(self):
        """Prévisualise la notification qui sera envoyée"""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Prévisualisation notification',
            'res_model': 'notification.preview.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_notification_type': 'document_rejection',
                'default_partner_id': self.partner_id.id,
                'default_data': {
                    'rejection_reason': self.rejection_reason,
                    'rejection_details': self.rejection_details,
                    'document_type': self.document_id.document_type_id.name
                }
            }
        }

    def action_view_document_history(self):
        """Affiche l'historique des documents de ce type"""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': f'Historique - {self.document_id.document_type_id.name}',
            'res_model': 'document.archive',
            'view_mode': 'list,form',
            'domain': [
                ('partner_id', '=', self.partner_id.id),
                ('document_type_id', '=', self.document_id.document_type_id.id)
            ]
        }

    # =================== CONTRAINTES ===================

    @api.constrains('rejection_details')
    def _check_rejection_details(self):
        """Vérifie que les détails du rejet sont suffisants"""
        for wizard in self:
            if wizard.rejection_details and len(wizard.rejection_details.strip()) < 10:
                raise ValidationError("Les détails du rejet doivent contenir au moins 10 caractères")
