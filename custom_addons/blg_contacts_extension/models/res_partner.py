# -*- coding: utf-8 -*-
"""
Enhanced Partner Model for Subcontractor Document Management

This module extends the res.partner model with comprehensive document management
capabilities specifically designed for subcontractor workflow in construction projects.
It follows SOLID principles and clean architecture patterns.
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, AccessError
from odoo.osv import expression
import logging
from datetime import date, timedelta
from .document_config import DOCUMENT_TYPES
from . import document_email_utils
import urllib.parse

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    """
    Enhanced partner model with document management and subcontractor functionality.
    
    This model provides comprehensive document management for subcontractors
    including document validation, notifications, and integration with construction projects.
    """
    _inherit = 'res.partner'

    # =================== CORE SUBCONTRACTOR FIELDS ===================
    
    # Contact type field with proper selection options
    contact_type = fields.Selection([
        ('customer', 'Customer'),
        ('supplier', 'Supplier'),
        ('sous_traitant', 'Subcontractor'),
        ('employee', 'Employee'),
        ('other', 'Other')
    ], string="Contact Type", default='other', help="Type of contact relationship")

    # Integration with construction lots (using standardized lot model)
    lot_ids = fields.Many2many(
        'lot',  # Reference to lot model from construction_lots module
        'partner_lot_rel',
        'partner_id',
        'lot_id',
        string="Trade Specializations",
        help="Construction trades/lots this subcontractor specializes in"
    )

    urssaf_code = fields.Char(
        string="Code URSSAF",
        compute='_compute_urssaf_code',
        store=True,
        help="Codes URSSAF agrégés depuis les spécialités (lots) liées"
    )

    # Computed fields for better UX
    is_subcontractor = fields.Boolean(
        string='Is Subcontractor',
        compute='_compute_is_subcontractor',
        store=True,
        help="True if contact type is subcontractor"
    )

    lot_names = fields.Char(
        string='Specializations',
        compute='_compute_lot_names',
        store=False,
        help="Comma-separated list of trade specializations"
    )

    # Performance optimization: count related records
    chantier_count = fields.Integer(
        string='Active Projects Count',
        compute='_compute_related_counts',
        store=False,
        help="Number of active construction projects"
    )

    # Document archive relationship
    document_archive_ids = fields.One2many(
        'document.archive',
        'partner_id',
        string='Document Archives',
        help="History of all document versions"
    )

    # Notification settings
    disable_document_emails = fields.Boolean(
        string="Disable Document Email Notifications",
        default=False,
        help="Check to disable email notifications for document status changes"
    )

    # =================== DOCUMENT FIELDS ===================
    
    # Identity Card Document
    document_identity_card = fields.Binary(
        string="Carte d'identité",
        attachment=True,
        help="Identity card document file"
    )
    document_identity_card_filename = fields.Char(
        string="Nom du fichier - Carte d'identité",
        help="Filename for identity card document"
    )
    document_identity_card_expiry = fields.Date(
        string="Date d'expiration - Carte d'identité",
        help="Expiration date for identity card"
    )
    document_identity_card_status = fields.Selection([
        ('valid', 'Valide'),
        ('expiring', 'Expire bientôt'), 
        ('expired', 'Expiré'),
        ('to_check', 'À vérifier'),
        ('missing', 'Manquant'),
        ('rejected', 'Rejeté'),
    ], string="Statut - Carte d'identité", compute='_compute_document_statuses', store=False)
    document_identity_card_manual_status = fields.Selection([
        ('to_check', 'À vérifier'),
        ('valid', 'Valide'),
        ('rejected', 'Rejeté'),
    ], string="Validation manuelle - Carte d'identité", default='to_check')

    # URSSAF Document
    document_URSSAF = fields.Binary(
        string="URSSAF",
        attachment=True,
        help="URSSAF certificate document file"
    )
    document_URSSAF_filename = fields.Char(
        string="Nom du fichier - URSSAF",
        help="Filename for URSSAF document"
    )
    document_URSSAF_expiry = fields.Date(
        string="Date d'expiration - URSSAF",
        help="Expiration date for URSSAF certificate"
    )
    document_URSSAF_status = fields.Selection([
        ('valid', 'Valide'),
        ('expiring', 'Expire bientôt'), 
        ('expired', 'Expiré'),
        ('to_check', 'À vérifier'),
        ('missing', 'Manquant'),
        ('rejected', 'Rejeté'),
    ], string="Statut - URSSAF", compute='_compute_document_statuses', store=False)
    document_URSSAF_manual_status = fields.Selection([
        ('to_check', 'À vérifier'),
        ('valid', 'Valide'),
        ('rejected', 'Rejeté'),
    ], string="Validation manuelle - URSSAF", default='to_check')

    # KBIS Document
    document_KBIS = fields.Binary(
        string="KBIS",
        attachment=True,
        help="KBIS extract document file"
    )
    document_KBIS_filename = fields.Char(
        string="Nom du fichier - KBIS",
        help="Filename for KBIS document"
    )
    document_KBIS_expiry = fields.Date(
        string="Date d'expiration - KBIS",
        help="Expiration date for KBIS extract"
    )
    document_KBIS_status = fields.Selection([
        ('valid', 'Valide'),
        ('expiring', 'Expire bientôt'), 
        ('expired', 'Expiré'),
        ('to_check', 'À vérifier'),
        ('missing', 'Manquant'),
        ('rejected', 'Rejeté'),
    ], string="Statut - KBIS", compute='_compute_document_statuses', store=False)
    document_KBIS_manual_status = fields.Selection([
        ('to_check', 'À vérifier'),
        ('valid', 'Valide'),
        ('rejected', 'Rejeté'),
    ], string="Validation manuelle - KBIS", default='to_check')

    # Insurance Document
    document_insurance = fields.Binary(
        string="Assurance",
        attachment=True,
        help="Insurance certificate document file"
    )
    document_insurance_filename = fields.Char(
        string="Nom du fichier - Assurance",
        help="Filename for insurance document"
    )
    document_insurance_expiry = fields.Date(
        string="Date d'expiration - Assurance",
        help="Expiration date for insurance certificate"
    )
    document_insurance_status = fields.Selection([
        ('valid', 'Valide'),
        ('expiring', 'Expire bientôt'), 
        ('expired', 'Expiré'),
        ('to_check', 'À vérifier'),
        ('missing', 'Manquant'),
        ('rejected', 'Rejeté'),
    ], string="Statut - Assurance", compute='_compute_document_statuses', store=False)
    document_insurance_manual_status = fields.Selection([
        ('to_check', 'À vérifier'),
        ('valid', 'Valide'),
        ('rejected', 'Rejeté'),
    ], string="Validation manuelle - Assurance", default='to_check')

    # RIB Document (no expiry)
    document_RIB = fields.Binary(
        string="RIB",
        attachment=True,
        help="Bank details (RIB) document file"
    )
    document_RIB_filename = fields.Char(
        string="Nom du fichier - RIB",
        help="Filename for RIB document"
    )
    document_RIB_status = fields.Selection([
        ('valid', 'Valide'),
        ('to_check', 'À vérifier'),
        ('missing', 'Manquant'),
        ('rejected', 'Rejeté'),
    ], string="Statut - RIB", compute='_compute_document_statuses', store=False)
    document_RIB_manual_status = fields.Selection([
        ('to_check', 'À vérifier'),
        ('valid', 'Valide'),
        ('rejected', 'Rejeté'),
    ], string="Validation manuelle - RIB", default='to_check')

    # Notification tracking fields
    last_notif_expiry_identity_card = fields.Date(
        string="Dernière notification - Carte d'identité",
        copy=False
    )
    last_notif_expiry_urssaf = fields.Date(
        string="Dernière notification - URSSAF", 
        copy=False
    )
    last_notif_expiry_kbis = fields.Date(
        string="Dernière notification - KBIS",
        copy=False
    )
    last_notif_expiry_insurance = fields.Date(
        string="Dernière notification - Assurance",
        copy=False
    )
    last_notif_rib = fields.Date(
        string="Dernière notification - RIB",
        copy=False
    )

    # Global document status flags
    has_expired_documents = fields.Boolean(
        string='Has Expired Documents',
        compute='_compute_document_status_flags', 
        store=False,
        help="True if partner has any expired documents"
    )
    
    has_expiring_documents = fields.Boolean(
        string='Has Expiring Documents',
        compute='_compute_document_status_flags', 
        store=False,
        help="True if partner has documents expiring within 30 days"
    )

    # Upload token for secure portal access
    upload_token = fields.Char(
        string="Upload Token",
        copy=False,
        help="Secure token for document upload portal access"
    )
    
    token_expiration = fields.Datetime(
        string="Token Expiration",
        copy=False,
        help="Expiration date/time for upload token"
    )



    # =================== COMPUTED METHODS ===================

    @api.depends('contact_type')
    def _compute_is_subcontractor(self):
        """Compute if partner is a subcontractor for easy filtering."""
        for record in self:
            record.is_subcontractor = record.contact_type == 'sous_traitant'

    @api.depends('lot_ids.name')
    def _compute_lot_names(self):
        """Compute comma-separated lot names for display purposes."""
        for record in self:
            if record.lot_ids:
                record.lot_names = ', '.join(record.lot_ids.mapped('name'))
            else:
                record.lot_names = ''

    @api.depends('lot_ids.urssaf_code')
    def _compute_urssaf_code(self):
        """Agrège les codes URSSAF provenant des lots liés."""
        for record in self:
            codes = [code.strip() for code in record.lot_ids.mapped('urssaf_code') if code]
            unique_codes = []
            for code in codes:
                if code and code not in unique_codes:
                    unique_codes.append(code)
            record.urssaf_code = ', '.join(unique_codes) if unique_codes else False

    def _compute_related_counts(self):
        """Compute counts of related construction records for performance."""
        for record in self:
            if record.is_subcontractor:
                try:
                    chantier_count = self.env['construction.chantier'].search_count([
                        ('subcontractors', 'in', record.id)
                    ])
                    record.chantier_count = chantier_count
                except Exception:
                    record.chantier_count = 0
            else:
                record.chantier_count = 0

    @api.depends(
        'contact_type',
        'document_identity_card', 'document_identity_card_expiry', 'document_identity_card_manual_status',
        'document_URSSAF', 'document_URSSAF_expiry', 'document_URSSAF_manual_status',
        'document_KBIS', 'document_KBIS_expiry', 'document_KBIS_manual_status',
        'document_insurance', 'document_insurance_expiry', 'document_insurance_manual_status',
        'document_RIB', 'document_RIB_manual_status'
    )
    def _compute_document_statuses(self):
        """
        Compute document statuses based on content, expiry dates, and manual validation.
        """
        for record in self:
            # Pour les contacts internes, ignorer la gestion documentaire partenaire
            # (les exigences restent au niveau chantier: planning, CCTP, etc.)
            if getattr(record, 'contact_type', False) == 'employee':
                for doc_type, config in DOCUMENT_TYPES.items():
                    status_field = config['status_field']
                    setattr(record, status_field, 'valid')
                continue
            for doc_type, config in DOCUMENT_TYPES.items():
                content_field = config['content_field']
                manual_status_field = config['manual_status_field']
                status_field = config['status_field']
                
                # Get field values
                has_content = bool(getattr(record, content_field, False))
                manual_status = getattr(record, manual_status_field, 'to_check')
                
                # Calculate status
                if not has_content:
                    status = 'missing'
                elif manual_status == 'rejected':
                    status = 'rejected'
                elif manual_status == 'to_check':
                    status = 'to_check'
                elif manual_status == 'valid':
                    # La validation manuelle doit toujours prévaloir
                    status = 'valid'
                elif config.get('has_expiry'):
                    # Check expiry for documents that have expiry dates
                    expiry_field = config['expiry_field']
                    expiry_date = getattr(record, expiry_field, False)
                    
                    if not expiry_date:
                        status = 'to_check'  # No expiry date set
                    elif expiry_date < date.today():
                        status = 'expired'
                    elif expiry_date <= date.today() + timedelta(days=30):
                        status = 'expiring'
                    else:
                        status = 'valid'
                else:
                    # Documents without expiry (like RIB)
                    status = 'valid'
                
                setattr(record, status_field, status)

    @api.depends(
        'contact_type',
        'document_identity_card_status', 'document_URSSAF_status',
        'document_KBIS_status', 'document_insurance_status', 'document_RIB_status'
    )
    def _compute_document_status_flags(self):
        """
        Compute global document status flags.
        """
        for record in self:
            # Les contacts internes ne doivent pas bloquer par documents partenaires
            if getattr(record, 'contact_type', False) == 'employee':
                record.has_expired_documents = False
                record.has_expiring_documents = False
                continue
            has_expired = False
            has_expiring = False
            
            for doc_type, config in DOCUMENT_TYPES.items():
                status_field = config['status_field']
                if hasattr(record, status_field):
                    status = getattr(record, status_field)
                    if status == 'expired':
                        has_expired = True
                    elif status == 'expiring':
                        has_expiring = True
                    
            record.has_expired_documents = has_expired
            record.has_expiring_documents = has_expiring

    # =================== CONSTRAINTS ===================

    @api.constrains('lot_ids', 'contact_type')
    def _check_lot_assignment_rules(self):
        """Validate lot assignment business rules."""
        for record in self:
            # Autoriser l'affectation d'une spécialité aux employés internes
            if record.lot_ids and record.contact_type not in ('sous_traitant', 'employee'):
                raise ValidationError(
                    "Trade specializations (lots) can only be assigned to subcontractor contacts. "
                    "Please change the contact type to 'Subcontractor' or remove the lot assignments."
                )

    @api.onchange('contact_type')
    def _onchange_contact_type(self):
        """Clear lots when contact type changes from subcontractor."""
        if self.contact_type != 'sous_traitant' and self.lot_ids:
            self.lot_ids = [(5, 0, 0)]  # Clear all lot assignments

    # =================== BUSINESS METHODS ===================

    def action_view_related_chantiers(self):
        """Open view of construction projects involving this subcontractor."""
        self.ensure_one()
        
        if not self.is_subcontractor:
            return False

        try:
            chantiers = self.env['construction.chantier'].search([
                ('subcontractors', 'in', self.id)
            ])
            
            return {
                'type': 'ir.actions.act_window',
                'name': f'Projects - {self.name}',
                'res_model': 'construction.chantier',
                'view_mode': 'kanban,list,form',
                'domain': [('id', 'in', chantiers.ids)],
                'context': {
                    'default_subcontractors': [(6, 0, [self.id])],
                    'search_default_subcontractor_filter': 1,
                },
                'target': 'current',
            }
        except Exception as e:
            _logger.warning(
                "Could not open chantiers view for subcontractor %s: %s",
                self.id, str(e)
            )
            return False

    def _create_notification(self, notification_type, message, title=None, reload=False):
        """
        Create a standardized UI notification.
        """
        type_mapping = {
            'success': 'success',
            'warning': 'warning', 
            'danger': 'danger',
            'error': 'danger',
            'info': 'info'
        }
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title or notification_type.title(),
                'message': message,
                'sticky': False,
                'type': type_mapping.get(notification_type, 'info'),
                **({'next': {'type': 'ir.actions.client', 'tag': 'reload'}} if reload else {}),
            },
        }

    def _send_missing_documents_email(self):
        """
        Envoie un email listant tous les documents manquants ou expirés.
        Utilise la file d'envoi native d'Odoo 18 pour éviter les blocages.
        """
        self.ensure_one()
        
        # Ne pas envoyer d'email de documents aux contacts internes
        if getattr(self, 'contact_type', False) == 'employee':
            return self._create_notification('info', "Contact interne: aucun document partenaire requis.")

        if not self.email:
            return self._create_notification(
                'danger', 
                'Ce partenaire n\'a pas d\'adresse email configurée.'
            )

        try:
            # Construire la liste des documents manquants/expirés
            missing_docs = []
            for doc_type, config in DOCUMENT_TYPES.items():
                status = getattr(self, config['status_field'])
                manual_status = getattr(self, config['manual_status_field'])
                
                if status in ['missing', 'expired'] or manual_status == 'rejected':
                    missing_docs.append(config['display_name_fr'])

            if not missing_docs:
                return self._create_notification('info', 'Aucun document manquant trouvé.')

            # 1) Récupérer le modèle d’e-mail s’il existe
            template = self.env.ref(
                'blg_contacts_extension.email_template_documents_missing',
                raise_if_not_found=False
            )

            if template:
                # Utilise la file native d'Odoo 18 (force_send=False)
                template.with_context(missing_documents=missing_docs).send_mail(
                    self.id,
                    force_send=False,
                    raise_exception=False,
                )
            else:
                # Fallback : envoyer via message_post pour qu'il apparaisse dans le Chatter
                body_html = (
                    f"<p>Bonjour {self.name},</p>"
                    f"<p>Merci de nous transmettre les documents suivants : {', '.join(missing_docs)}</p>"
                    f"<p>Cordialement,<br/>L’équipe BLG Groupe</p>"
                )

                self.message_post(
                    subject=f"BLG Groupe : Documents manquants pour {self.name}",
                    body=body_html,
                    message_type='email',
                    subtype_xmlid='mail.mt_comment',
                    email_from=self.env.user.email_formatted or self.env.company.email,
                    email_to=self.email,
                )

            # Notifier l’utilisateur : mail placé dans la file d’envoi
            message = (
                f"E-mail de rappel créé pour {self.email} (documents : {', '.join(missing_docs)}). "
                "Il sera envoyé par le service natif d'Odoo."
            )
            return self._create_notification('success', message)

        except Exception as e:
            _logger.error("Error sending missing documents email for partner %s: %s", self.id, str(e))
            return self._create_notification('danger', "Erreur lors de l'envoi de l'email.")

    def _generate_upload_token(self):
        """
        Génère un token unique pour l'upload de documents via le portail.
        """
        import secrets
        import string
        from datetime import datetime, timedelta
        
        # Générer un token sécurisé
        alphabet = string.ascii_letters + string.digits
        token = ''.join(secrets.choice(alphabet) for _ in range(32))
        
        # Définir l'expiration à 7 jours
        expiration = datetime.now() + timedelta(days=7)
        
        self.write({
            'upload_token': token,
            'token_expiration': expiration
        })
        
        return token

    def _get_portal_upload_url(self, rib_request=False, reminder=False, extra_params=None):
        """
        Build the public upload URL associated with the partner token.
        """
        self.ensure_one()
        now = fields.Datetime.now()
        if not self.upload_token or not self.token_expiration or self.token_expiration < now:
            self._generate_upload_token()
            
        base_url = (self.env['ir.config_parameter']
                    .sudo()
                    .get_param('web.base.url', '')
                    .rstrip('/'))
        params = {'token': self.upload_token}
        
        if rib_request:
            params['rib_request'] = '1'
        if reminder:
            params['reminder'] = '1'
        if extra_params:
            params.update(extra_params)
            
        query_string = '&'.join([f'{k}={v}' for k, v in params.items()])
        safe_token = urllib.parse.quote(self.upload_token, safe='')
        return f"{base_url}/documents/upload/{safe_token}?{query_string}"

    def _generate_upload_token_details(self):
        """
        Return the upload URL used inside mail templates and notifications.
        """
        extra_params = {}
        if self.env.context.get('request'):
            extra_params['request'] = '1'
        return self._get_portal_upload_url(
            rib_request=bool(self.env.context.get('rib_request')),
            reminder=bool(self.env.context.get('reminder')),
            extra_params=extra_params or None,
        )

    def send_document_rejection_notification(self, doc_name, rejection_reason):
        """
        Send the rejection email with a secure upload link.
        """
        self.ensure_one()
        if not self.email:
            return False
        return document_email_utils.send_document_notification(
            self,
            'rejection',
            doc_name=doc_name,
            rejection_reason=rejection_reason or _('Document not compliant'),
        )

    def send_missing_documents_request(self, missing_documents):
        """
        Send the reminder email that lists all missing or rejected documents.
        """
        self.ensure_one()
        if not self.email or not missing_documents:
            return False
        return document_email_utils.send_document_notification(
            self,
            'request',
            documents_to_request=missing_documents,
        )

    def _validate_document_access_rights(self):
        """
        Ensure the current user has the right groups to manipulate documents.
        """
        required_groups = [
            'base.group_system',
            'blg_contacts_extension.group_conductrice_travaux',
            'blg_contacts_extension.group_directeur_general',
        ]
        if not any(self.env.user.has_group(xml_id) for xml_id in required_groups):
            raise AccessError(
                _("You don't have sufficient rights to manage subcontractor documents.")
            )
        return True

    def _get_document_config_by_key(self, doc_type_key):
        """
        Helper returning the configuration dictionary for a document key.
        """
        return DOCUMENT_TYPES.get(doc_type_key)

    def action_validate_document(self):
        """
        Valide un document spécifique.
        """
        self.ensure_one()
        
        # Récupérer le type de document depuis le contexte
        doc_type = self.env.context.get('doc_type')
        if not doc_type:
            return self._create_notification('danger', 'Type de document non spécifié')
        
        config = DOCUMENT_TYPES.get(doc_type)
        if not config:
            return self._create_notification('danger', 'Type de document invalide')
            
        # Mettre à jour le statut manuel à 'valid'
        manual_status_field = config['manual_status_field']
        self.write({manual_status_field: 'valid'})
        
        # Log dans le chatter
        self.message_post(
            body=f"Document {config['display_name_fr']} validé par {self.env.user.name}",
            subtype_xmlid='mail.mt_note',
        )
        
        return self._create_notification(
            'success',
            _("Document %s validé avec succès") % config['display_name_fr'],
            reload=True,
        )

    def action_reject_document(self):
        """
        Rejette un document et envoie un email avec lien de téléversement.
        """
        self.ensure_one()
        
        if not self.email:
            return self._create_notification('danger', 'Ce partenaire n\'a pas d\'adresse email')
        
        # Récupérer le type de document depuis le contexte
        doc_type = self.env.context.get('doc_type')
        if not doc_type:
            return self._create_notification('danger', 'Type de document non spécifié')
             
        config = DOCUMENT_TYPES.get(doc_type)
        if not config:
            return self._create_notification('danger', 'Type de document invalide')
            
        # TODO: Ajouter un wizard pour demander le motif du rejet
        reason = ''
        
        # Mettre à jour le statut manuel à 'rejected'
        manual_status_field = config['manual_status_field']
        self.write({manual_status_field: 'rejected'})
        
        # Générer le lien de téléversement
        upload_url = self._get_portal_upload_url()
        
        # Envoyer l'email de rejet
        template = self.env.ref(
            'blg_contacts_extension.email_template_document_rejection',
            raise_if_not_found=False
        )
        
        if template:
            template.with_context(
                doc_name=config['display_name_fr'],
                rejection_reason=reason or 'Document non conforme aux exigences',
                upload_url=upload_url
            ).send_mail(self.id, force_send=False)
        else:
            # Fallback
            body = f"""
            <p>Bonjour {self.name},</p>
            <p>Votre document <strong>{config['display_name_fr']}</strong> a été rejeté.</p>
            <p>Motif : {reason or 'Document non conforme'}</p>
            <p><a href="{upload_url}" style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Soumettre un nouveau document</a></p>
            <p>Cordialement,<br/>L'équipe BLG Groupe</p>
            """
            
            self.message_post(
                subject=f"Document rejeté : {config['display_name_fr']}",
                body=body,
                message_type='email',
                subtype_xmlid='mail.mt_comment',
                email_to=self.email,
            )
        
        # Log dans le chatter
        self.message_post(
            body=f"Document {config['display_name_fr']} rejeté par {self.env.user.name}. Motif : {reason or 'Non spécifié'}",
            subtype_xmlid='mail.mt_note',
        )
        
        return self._create_notification(
            'info',
            _("Document rejeté et email envoyé à %s") % self.email,
            reload=True,
        )

    def action_send_all_missing_documents_email(self):
        """
        Version améliorée qui envoie un email avec lien unique pour tous les documents manquants.
        """
        self.ensure_one()
        
        # Ne pas envoyer d'email de documents aux contacts internes
        if getattr(self, 'contact_type', False) == 'employee':
            return self._create_notification('info', "Contact interne: aucun document partenaire requis.")

        if not self.email:
            return self._create_notification(
                'danger', 
                'Ce partenaire n\'a pas d\'adresse email configurée.'
            )

        try:
            # Construire la liste des documents manquants/expirés
            missing_docs = []
            for doc_type, config in DOCUMENT_TYPES.items():
                status = getattr(self, config['status_field'])
                manual_status = getattr(self, config['manual_status_field'])
                
                if status in ['missing', 'expired'] or manual_status == 'rejected':
                    missing_docs.append(config['display_name_fr'])

            if not missing_docs:
                return self._create_notification('info', 'Aucun document manquant trouvé.')

            # Générer le lien unique
            upload_url = self._get_portal_upload_url()

            # Utiliser le template ou fallback
            template = self.env.ref(
                'blg_contacts_extension.email_template_documents_missing',
                raise_if_not_found=False
            )

            if template:
                template.with_context(
                    missing_documents=missing_docs,
                    upload_url=upload_url
                ).send_mail(self.id, force_send=False)
            else:
                # Fallback avec lien
                body_html = f"""
                <p>Bonjour {self.name},</p>
                <p>Merci de nous transmettre les documents suivants :</p>
                <ul>{''.join([f'<li>{doc}</li>' for doc in missing_docs])}</ul>
                <p style="margin: 20px 0;">
                    <a href="{upload_url}" style="background-color: #007bff; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; display: inline-block;">
                        Téléverser les documents
                    </a>
                </p>
                <p>Ce lien est valable 7 jours.</p>
                <p>Cordialement,<br/>L'équipe BLG Groupe</p>
                """

                self.message_post(
                    subject=f"BLG Groupe : Documents manquants pour {self.name}",
                    body=body_html,
                    message_type='email',
                    subtype_xmlid='mail.mt_comment',
                    email_from=self.env.user.email_formatted or self.env.company.email,
                    email_to=self.email,
                )

            # Notifier l'utilisateur
            message = f"E-mail envoyé à {self.email} avec lien de téléversement pour : {', '.join(missing_docs)}"
            return self._create_notification('success', message)

        except Exception as e:
            import traceback
            _logger.error(
                "Erreur détaillée lors de l'envoi de l'e-mail pour les documents manquants au partenaire %s: %s\n%s",
                self.id, str(e), traceback.format_exc()
            )
            return self._create_notification(
                'danger', 
                f"Erreur lors de l'envoi de l'e-mail : {str(e)}. Consultez les logs du serveur pour plus de détails."
            )

    # Remplacer l'ancienne méthode par la nouvelle
    action_send_missing_documents_email = action_send_all_missing_documents_email

    def action_send_rib_request_email(self):
        """
        Send a dedicated email requesting the partner's bank details (RIB).
        """
        self.ensure_one()
        if not self.email:
            return self._create_notification(
                'danger',
                _("This partner does not have an email address.")
            )
        success = document_email_utils.send_document_notification(self, 'rib_request')
        if success:
            return self._create_notification(
                'success',
                _("RIB request email sent to %s.") % self.email
            )
        return self._create_notification(
            'danger',
            _("An error occurred while sending the RIB request email.")
        )

    def write(self, vals):
        """
        Override write pour gérer automatiquement le statut des documents.
        """
        # Vérifier si des documents sont ajoutés/modifiés
        for doc_type, config in DOCUMENT_TYPES.items():
            content_field = config['content_field']
            manual_status_field = config['manual_status_field']
            
            # Si un nouveau document est ajouté, mettre le statut à 'to_check'
            if content_field in vals and vals[content_field]:
                # Vérifier si c'est un nouveau document ou une mise à jour
                old_value = getattr(self, content_field, False)
                if not old_value or old_value != vals[content_field]:
                    vals[manual_status_field] = 'to_check'
                    
                    # Archiver l'ancien document si présent
                    if old_value:
                        self._archive_document(doc_type, 'replacement')
        
        return super().write(vals)

    def _archive_document(self, doc_type, reason='replacement'):
        """
        Archive un document avant son remplacement.
        """
        config = DOCUMENT_TYPES.get(doc_type)
        if not config:
            return
            
        content = getattr(self, config['content_field'], False)
        filename = getattr(self, config['filename_field'], False)
        expiry_date = getattr(self, config.get('expiry_field', ''), False) if config.get('expiry_field') else False
        status = getattr(self, config['status_field'], False)
        
        if content:
            self.env['document.archive'].create({
                'name': filename or f"{config['display_name_fr']} - {self.name}",
                'document': content,
                'document_type': doc_type.replace('_', ''),  # Adapter au format attendu
                'partner_id': self.id,
                'archive_reason': reason,
                'original_expiry_date': expiry_date,
                'original_status': status,
            })

    def _send_expiry_email(self, doc_config, expiry_date, status, is_expired_doc=False):
        """
        Send an expiry notification for the given document configuration.
        """
        self.ensure_one()
        success = document_email_utils.send_document_notification(
            self,
            'expiry',
            doc_config=doc_config,
            expiry_date=expiry_date,
            status=status,
            is_expired=is_expired_doc,
        )
        if success and doc_config.get('last_notif_field'):
            self.sudo().write({doc_config['last_notif_field']: fields.Date.today()})
        return success

    @api.model
    def check_document_expiry(self):
        """
        Cron entry point: scans subcontractors and sends expiry reminders.
        """
        today = date.today()
        warning_threshold = today + timedelta(days=30)
        domain = [
            ('contact_type', '=', 'sous_traitant'),
            ('disable_document_emails', '=', False),
            ('email', '!=', False),
        ]
        partners = self.search(domain)
        batch_size = 100
        total_sent = 0
        _logger.info(
            "Starting subcontractor document expiry check for %s partners",
            len(partners),
        )
        for start in range(0, len(partners), batch_size):
            batch = partners[start:start + batch_size]
            try:
                total_sent += self._process_document_expiry_batch(
                    batch, today, warning_threshold
                )
                self.env.cr.commit()
            except Exception as exc:
                _logger.error(
                    "Error while processing document expiry batch %s-%s: %s",
                    start,
                    start + batch_size,
                    exc,
                    exc_info=True,
                )
                self.env.cr.rollback()
        _logger.info("Document expiry check completed. Notifications sent: %s", total_sent)
        return total_sent

    def _process_document_expiry_batch(self, partners, today, warning_threshold):
        """
        Scan a batch of partners and send expiry or expiring notifications.
        """
        notifications = 0
        for partner in partners:
            if partner.disable_document_emails:
                continue
            for doc_key, config in DOCUMENT_TYPES.items():
                expiry_field = config.get('expiry_field')
                if not expiry_field:
                    continue
                content = getattr(partner, config['content_field'])
                expiry_date = getattr(partner, expiry_field)
                if not (content and expiry_date):
                    continue
                last_notif_field = config.get('last_notif_field')
                last_notif = getattr(partner, last_notif_field) if last_notif_field else False
                if expiry_date <= today:
                    if last_notif and (today - last_notif).days < 7:
                        continue
                    if partner._send_expiry_email(config, expiry_date, 'expiré', True):
                        notifications += 1
                    continue
                if expiry_date <= warning_threshold:
                    if last_notif and (today - last_notif).days < 30:
                        continue
                    if partner._send_expiry_email(
                        config, expiry_date, "sur le point d'expirer", False
                    ):
                        notifications += 1
        return notifications

    def action_view_document(self):
        """
        View document archive for this partner.
        """
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'Document Archive - {self.name}',
            'res_model': 'document.archive',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {
                'default_partner_id': self.id,
                'search_default_partner_id': self.id,
            },
            'target': 'current',
        }

    # =================== DOCUMENT PREVIEW METHODS ===================

    def action_preview_document(self):
        """
        Ouvre la prévisualisation du document dans une nouvelle fenêtre/onglet.
        Le type de document est récupéré du contexte via 'doc_type'.
        
        Returns:
            dict: Action pour ouvrir la prévisualisation
        """
        self.ensure_one()
        
        # Récupérer le type de document depuis le contexte
        doc_type = self.env.context.get('doc_type')
        if not doc_type:
            return self._create_notification('error', 'Type de document non spécifié dans le contexte.')
        
        # Vérifier que le type de document est valide
        if doc_type not in DOCUMENT_TYPES:
            return self._create_notification('error', f'Type de document invalide: {doc_type}')
        
        config = DOCUMENT_TYPES[doc_type]
        content_field = config['content_field']
        
        # Vérifier que le document existe
        document_content = getattr(self, content_field, False)
        if not document_content:
            return self._create_notification('warning', f'Aucun document {config["display_name_fr"]} disponible pour prévisualisation.')
        
        # Générer l'URL de prévisualisation sécurisée
        preview_url = f'/blg_contacts/document/preview/{self.id}/{doc_type}'
        
        # Retourner l'action pour ouvrir dans une nouvelle fenêtre
        return {
            'type': 'ir.actions.act_url',
            'url': preview_url,
            'target': 'new',
        }

    def action_download_document(self):
        """
        Télécharge un document. Le type de document est récupéré du contexte.
        
        Returns:
            dict: Action pour télécharger le document
        """
        self.ensure_one()
        
        # Récupérer le type de document depuis le contexte
        doc_type = self.env.context.get('doc_type')
        if not doc_type:
            return self._create_notification('error', 'Type de document non spécifié dans le contexte.')
        
        # Vérifier que le type de document est valide
        if doc_type not in DOCUMENT_TYPES:
            return self._create_notification('error', f'Type de document invalide: {doc_type}')
        
        config = DOCUMENT_TYPES[doc_type]
        content_field = config['content_field']
        
        # Vérifier que le document existe
        document_content = getattr(self, content_field, False)
        if not document_content:
            return self._create_notification('warning', f'Aucun document {config["display_name_fr"]} disponible pour téléchargement.')
        
        # Générer l'URL de téléchargement sécurisée
        download_url = f'/blg_contacts/document/download/{self.id}/{doc_type}'
        
        # Retourner l'action pour ouvrir l'URL de téléchargement
        return {
            'type': 'ir.actions.act_url',
            'url': download_url,
            'target': 'new',
        }

    def get_document_preview_url(self, doc_type):
        """
        Génère une URL sécurisée pour la prévisualisation d'un document.
        
        Args:
            doc_type (str): Type de document
            
        Returns:
            str: URL de prévisualisation ou False si le document n'existe pas
        """
        self.ensure_one()
        
        if doc_type not in DOCUMENT_TYPES:
            return False
            
        config = DOCUMENT_TYPES[doc_type]
        content_field = config['content_field']
        
        # Vérifier que le document existe
        if not getattr(self, content_field, False):
            return False
            
        return f'/blg_contacts/document/preview/{self.id}/{doc_type}'

    def get_document_download_url(self, doc_type):
        """
        Génère une URL sécurisée pour le téléchargement d'un document.
        
        Args:
            doc_type (str): Type de document
            
        Returns:
            str: URL de téléchargement ou False si le document n'existe pas
        """
        self.ensure_one()
        
        if doc_type not in DOCUMENT_TYPES:
            return False
            
        config = DOCUMENT_TYPES[doc_type]
        content_field = config['content_field']
        
        # Vérifier que le document existe
        if not getattr(self, content_field, False):
            return False
            
        return f'/blg_contacts/document/download/{self.id}/{doc_type}'

    def has_document(self, doc_type):
        """
        Vérifie si un document spécifique existe pour ce partenaire.
        
        Args:
            doc_type (str): Type de document à vérifier
            
        Returns:
            bool: True si le document existe, False sinon
        """
        self.ensure_one()
        
        if doc_type not in DOCUMENT_TYPES:
            return False
            
        config = DOCUMENT_TYPES[doc_type]
        content_field = config['content_field']
        
        return bool(getattr(self, content_field, False))

    # =================== API methods for external integration ===================
    @api.model
    def _build_status_domain(self, status):
        """
        Build an OR-domain that matches subcontractors based on a single status.
        """
        domain_parts = [[(config['status_field'], '=', status)] for config in DOCUMENT_TYPES.values()]
        return expression.OR(domain_parts) if domain_parts else []

    @api.model
    def get_all_subcontractors(self):
        """
        Return every partner flagged as subcontractor.
        """
        return self.search([('contact_type', '=', 'sous_traitant')])

    @api.model
    def get_subcontractors_by_document_status(self, status=None):
        """
        Filter subcontractors by aggregated document status.
        """
        domain = [('contact_type', '=', 'sous_traitant')]
        if status == 'expired':
            domain.append(('has_expired_documents', '=', True))
            return self.search(domain)
        if status == 'expiring':
            domain.append(('has_expiring_documents', '=', True))
            return self.search(domain)
        if status in {'missing', 'rejected', 'to_check', 'valid'}:
            status_domain = self._build_status_domain(status)
            if status_domain:
                domain = expression.AND([domain, status_domain])
        return self.search(domain)

    @api.model
    def get_subcontractors_by_lot(self, lot_id=None):
        """
        Return subcontractors linked to a specific trade lot.
        """
        domain = [('contact_type', '=', 'sous_traitant')]
        if lot_id:
            domain.append(('lot_ids', 'in', [lot_id]))
        return self.search(domain)

    @api.model
    def filter_subcontractors(self, status=None, lot_id=None, document_type=None):
        """
        Flexible helper that combines lot and document filters.
        """
        domain = [('contact_type', '=', 'sous_traitant')]
        if lot_id:
            domain.append(('lot_ids', 'in', [lot_id]))
        if status and not document_type:
            if status == 'expired':
                domain.append(('has_expired_documents', '=', True))
            elif status == 'expiring':
                domain.append(('has_expiring_documents', '=', True))
            elif status in {'missing', 'rejected', 'to_check', 'valid'}:
                status_domain = self._build_status_domain(status)
                if status_domain:
                    domain = expression.AND([domain, status_domain])
        if document_type and status and document_type in DOCUMENT_TYPES:
            config = DOCUMENT_TYPES[document_type]
            domain.append((config['status_field'], '=', status))
        return self.search(domain)

    def get_subcontractors_with_valid_docs(self):
        """
        Return subcontractors that present a valid KBIS document.
        """
        return self.filter_subcontractors(
            status='valid',
            document_type='kbis'
        ).sorted('chantier_count', reverse=True)

    @api.model
    def get_subcontractors_with_expired_documents(self):
        """Get subcontractors with expired documents."""
        return self.search([
            ('contact_type', '=', 'sous_traitant'),
            ('has_expired_documents', '=', True)
        ])

    @api.model
    def get_subcontractors_with_expiring_documents(self):
        """Get subcontractors with expiring documents."""
        return self.search([
            ('contact_type', '=', 'sous_traitant'),
            ('has_expiring_documents', '=', True)
        ])

    def get_related_chantiers(self):
        """Get construction projects related to this subcontractor."""
        self.ensure_one()
        
        if not self.is_subcontractor:
            return self.env['construction.chantier']
            
        try:
            return self.env['construction.chantier'].search([
                ('subcontractors', 'in', self.id)
            ])
        except Exception:
            # Module might not be installed
            return self.env['construction.chantier'] if 'construction.chantier' in self.env else False

