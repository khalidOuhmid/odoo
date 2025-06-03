"""
blg_contacts_extension.models.res_partner
========================================

This module extends Odoo's `res.partner` model to provide a comprehensive document management
system for subcontractors (sous-traitants) within the BLG Groupe context.

Features:
---------
- Tracks and manages key legal and administrative documents (ID card, URSSAF, KBIS, Insurance, RIB).
- Handles document validation workflows, expiration tracking, and automated notifications.
- Provides secure upload links and archives previous document versions.
- Integrates with email utilities for automated partner notifications.
- Supports filtering and querying subcontractors by document status, lot, and other criteria.

Classes:
--------
ResPartner (models.Model)
    Extends `res.partner` with document management fields and methods.

Key Methods:
------------
- _compute_document_statuses: Computes the status of each document (valid, expiring, expired, etc.).
- _compute_document_status_flags: Sets global flags for expired/expiring documents.
- _check_file_type: Ensures only PDF files are uploaded.
- _check_documents_for_sous_traitant: Restricts document upload to subcontractors.
- preview_document: Generates a preview URL for a document.
- validate_document / reject_document: Handles document validation and rejection, with notifications.
- _generate_upload_token_details: Creates secure upload tokens and URLs.
- action_send_missing_documents_email: Sends email requests for missing/rejected documents.
- check_document_expiry: Scheduled check for expiring/expired documents, sends notifications.
- _archive_document: Archives old document versions.
- write: Overrides write to handle archiving, auto-expiry, and filename management.
- filter_subcontractors: Flexible filtering of subcontractors by document status, lot, etc.

Author: BLG IT Team
Last updated: 2023-07-12
"""

from odoo import models, fields, api
from odoo.exceptions import ValidationError, AccessError
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
import base64
import os
import logging
import urllib.parse
from . import document_config
from . import document_email_utils

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    """
    Extension of res.partner model that adds document management capabilities.
    
    This class implements a comprehensive document management system for tracking
    legal documents required for subcontractors, including validation workflows,
    expiration tracking, and automated notifications.
    """
    _inherit = 'res.partner'

    # Use document configurations from document_config.py
    _doc_config = document_config.DOCUMENT_CONFIGS

    contact_type = fields.Selection([
        ('customer', 'Client'),
        ('supplier', 'Fournisseur'),
        ('sous_traitant', 'Sous-traitant'),
        ('employee', 'Employé'),
        ('other', 'Autre')
    ], string="Type de Contact", default='other', help="Type de contact")

    # FIX: Ensure the field name matches what's expected by the inverse relationship
    lots = fields.Many2many(
        'blg_contacts_extension.lot', 
        'res_partner_lot_rel',  # Explicit relation table name
        'partner_id', 
        'lot_id',
        string='Corps de métier',
        help="Corps de métier dans lesquels ce sous-traitant intervient"
    )

    document_type = fields.Char(compute='_compute_document_type', store=False)

    has_expired_documents = fields.Boolean(
    compute='_compute_document_status_flags',
    store=True,  # Permettre la recherche
    help="Documents expirés"
    )
    has_expiring_documents = fields.Boolean(
        compute='_compute_document_status_flags',
        store=True,  # Permettre la recherche
        help="Documents à échéance"
    )

    #########################################################################################
    #                                       IDENTITY_CARD                                   #
    #########################################################################################
    document_identity_card = fields.Binary(string="Carte d'identité", attachment=True)
    document_identity_card_filename = fields.Char(string="Nom Carte d'identité")
    document_identity_card_expiry = fields.Date(string="Expiration Carte d'identité")
    document_identity_card_status = fields.Selection([
        ('valid', 'Valide'), ('expiring', 'Expire bientôt'), ('expired', 'Expiré'),
        ('to_check', 'À vérifier'), ('missing', 'Manquant'), ('rejected', 'Rejeté'),
    ], compute='_compute_document_statuses', string="Statut CNI", store=False)

    #########################################################################################
    #                                       URSSAF                                          #
    #########################################################################################
    document_URSSAF = fields.Binary(string="URSSAF", attachment=True)
    document_URSSAF_filename = fields.Char(string="Nom URSSAF")
    document_URSSAF_expiry = fields.Date(string="Expiration URSSAF")
    document_URSSAF_status = fields.Selection([
        ('valid', 'Valide'), ('expiring', 'Expire bientôt'), ('expired', 'Expiré'),
        ('to_check', 'À vérifier'), ('missing', 'Manquant'), ('rejected', 'Rejeté'),
    ], compute='_compute_document_statuses', string="Statut URSSAF", store=False)

    #########################################################################################
    #                                       KBIS                                            #
    #########################################################################################
    document_KBIS = fields.Binary(string="KBIS", attachment=True)
    document_KBIS_filename = fields.Char(string="Nom KBIS")
    document_KBIS_expiry = fields.Date(string="Expiration KBIS")
    document_KBIS_status = fields.Selection([
        ('valid', 'Valide'), ('expiring', 'Expire bientôt'), ('expired', 'Expiré'),
        ('to_check', 'À vérifier'), ('missing', 'Manquant'), ('rejected', 'Rejeté'),
    ], compute='_compute_document_statuses', string="Statut KBIS", store=False)

    #########################################################################################
    #                                       Insurance                                       #
    #########################################################################################
    document_insurance = fields.Binary(string="Assurance", attachment=True)
    document_insurance_filename = fields.Char(string="Nom Assurance")
    document_insurance_expiry = fields.Date(string="Expiration Assurance")
    document_insurance_status = fields.Selection([
        ('valid', 'Valide'), ('expiring', 'Expire bientôt'), ('expired', 'Expiré'),
        ('to_check', 'À vérifier'), ('missing', 'Manquant'), ('rejected', 'Rejeté'),
    ], compute='_compute_document_statuses', string="Statut Assurance", store=False)

    #########################################################################################
    #                                       RIB                                             #
    #########################################################################################
    document_RIB = fields.Binary(string="RIB", attachment=True)
    document_RIB_filename = fields.Char(string="Nom RIB")
    document_RIB_status = fields.Selection([
        ('valid', 'Valide'),
        ('to_check', 'À vérifier'), ('missing', 'Manquant'), ('rejected', 'Rejeté'),
    ], compute='_compute_document_statuses', string="Statut RIB", store=False)

    document_identity_card_manual_status = fields.Selection([
        ('to_check', 'À vérifier'), ('valid', 'Valide'), ('rejected', 'Rejeté'),
    ], string="Statut manuel Carte d'identité", default='to_check')
    document_URSSAF_manual_status = fields.Selection([
        ('to_check', 'À vérifier'), ('valid', 'Valide'), ('rejected', 'Rejeté'),
    ], string="Statut manuel URSSAF", default='to_check')
    document_KBIS_manual_status = fields.Selection([
        ('to_check', 'À vérifier'), ('valid', 'Valide'), ('rejected', 'Rejeté'),
    ], string="Statut manuel KBIS", default='to_check')
    document_insurance_manual_status = fields.Selection([
        ('to_check', 'À vérifier'), ('valid', 'Valide'), ('rejected', 'Rejeté'),
    ], string="Statut manuel Assurance", default='to_check')
    document_RIB_manual_status = fields.Selection([
        ('to_check', 'À vérifier'), ('valid', 'Valide'), ('rejected', 'Rejeté'),
    ], string="Statut manuel RIB", default='to_check')

    upload_token = fields.Char(string="Token d'upload", copy=False)
    token_expiration = fields.Datetime(string="Expiration du token", copy=False)
    document_archive_ids = fields.One2many('document.archive', 'partner_id', string='Archives de documents')
    disable_document_emails = fields.Boolean(
        string="Désactiver les emails de documents", default=False,
        help="Cocher pour désactiver les notifications par email concernant les documents")

    last_notif_expiry_identity_card = fields.Date(string="Dernière notif. expiration CNI", copy=False)
    last_notif_expiry_urssaf = fields.Date(string="Dernière notif. expiration URSSAF", copy=False)
    last_notif_expiry_kbis = fields.Date(string="Dernière notif. expiration KBIS", copy=False)
    last_notif_expiry_insurance = fields.Date(string="Dernière notif. expiration Assurance", copy=False)
    last_notif_rib = fields.Date(string="Dernière notif. demande RIB", copy=False)

    def _get_document_computed_status(self, content, expiry_date, manual_status, today, warning_threshold):
        """Calculate the document status based on content, expiry date, and manual status."""
        if not content:
            return 'missing'
        if manual_status == 'rejected':
            return 'rejected'
        if manual_status == 'to_check':
            return 'to_check'
        if not expiry_date: # This applies to documents like RIB that don't expire but are validated
            return 'valid'
        if expiry_date <= today:
            return 'expired'
        if expiry_date <= warning_threshold:
            return 'expiring'
        return 'valid'

    @api.depends(lambda self: [config['content_field'] for config in self._doc_config.values()] +
             [config['expiry_field'] for config in self._doc_config.values() if 'expiry_field' in config] +
             [config['manual_status_field'] for config in self._doc_config.values()])
    def _compute_document_statuses(self):
        """
        Compute the status for all documents based on content, expiry date, and manual validation.
        """
        today = date.today()
        warning_threshold = today + timedelta(days=30)
        for record in self:
            for doc_key, config in self._doc_config.items():
                content = getattr(record, config['content_field'])
                expiry_field = config.get('expiry_field')
                expiry_date = getattr(record, expiry_field) if expiry_field else None
                manual_status = getattr(record, config['manual_status_field'])

                status = record._get_document_computed_status(
                    content, expiry_date, manual_status, today, warning_threshold
                )
                setattr(record, config['status_field'], status)


    @api.depends(lambda self: [config['status_field'] for config in self._doc_config.values()])
    def _compute_document_status_flags(self):
        """
        Compute global document status flags based on individual document statuses.

        Sets the has_expired_documents and has_expiring_documents flags that are used
        for filtering and UI indicators.
        """
        for record in self:
            has_expired = False
            has_expiring = False
            for config in self._doc_config.values():
                status = getattr(record, config['status_field'])
                if status == 'expired':
                    has_expired = True
                elif status == 'expiring':
                    has_expiring = True
            record.has_expired_documents = has_expired
            record.has_expiring_documents = has_expiring

    @api.depends('contact_type')
    def _compute_document_type(self):
        """Technical field for view validation purposes."""
        for record in self:
            record.document_type = False

    @api.constrains(lambda self: [config['filename_field'] for config in self._doc_config.values()])
    def _check_file_type(self):
        """
        Validate that all document files are PDF format.
        
        Raises:
            ValidationError: If a document is not a PDF file
        """
        for record in self:
            for config in self._doc_config.values():
                filename = getattr(record, config['filename_field'])
                if filename and not filename.lower().endswith('.pdf'):
                    raise ValidationError("Seuls les fichiers PDF sont autorisés pour les documents.")

    @api.constrains(lambda self: [config['content_field'] for config in self._doc_config.values()] + ['contact_type'])
    def _check_documents_for_sous_traitant(self):
        """
        Ensure documents can only be uploaded for subcontractor contacts.
        
        Raises:
            ValidationError: If documents are uploaded for non-subcontractor contacts
        """
        for record in self:
            if record.contact_type != 'sous_traitant':
                if any(getattr(record, config['content_field']) for config in self._doc_config.values()):
                    raise ValidationError(
                        "Les documents ne peuvent être uploadés que pour les contacts de type Sous-traitant.")

    def _check_document_access(self):
        """
        Check if the current user has permission to access and manage documents.
        
        Returns:
            bool: True if access is granted
        
        Raises:
            AccessError: If the user doesn't have appropriate access rights
        """
        user = self.env.user
        if not (user.has_group('base.group_system') or \
                user.has_group('blg_contacts_extension.group_conductrice_travaux') or \
                user.has_group('blg_contacts_extension.group_directeur_general')):
            raise AccessError("Vous n'avez pas les droits pour accéder à ces documents.")
        return True

    def preview_document(self):
        """
        Generate a URL to preview a specific document in a new browser tab.
        
        Returns:
            dict: Action dictionary with URL for document preview
            
        Raises:
            AccessError: If user doesn't have document access rights
        """
        self._check_document_access()
        doc_type_key = self.env.context.get('doc_type')
        if not doc_type_key or doc_type_key not in self._doc_config:
            return False

        config = self._doc_config[doc_type_key]
        field_name = config['content_field']
        filename = getattr(self, config['filename_field']) or f'{doc_type_key}.pdf'

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content?model={self._name}&field={field_name}&id={self.id}&filename={filename}',
            'target': 'new',
        }

    def _perform_document_action(self, doc_type_key, action_type, reset=False):
        """
        Execute a document action (validate or reject) with appropriate notifications.
        
        This is a helper method used by validate_document and reject_document to perform
        the actual action and generate appropriate UI notifications.
        
        Args:
            doc_type_key (str): Document type key from _doc_config
            action_type (str): Action to perform ('validate' or 'reject')
            reset (bool): If True, will reset validation status to 'to_check'
            
        Returns:
            dict: UI notification action
        """
        self._check_document_access()
        if not doc_type_key or doc_type_key not in self._doc_config:
            return False

        config = self._doc_config[doc_type_key]
        manual_status_field = config['manual_status_field']

        if action_type == 'validate':
            new_status = 'to_check' if reset else 'valid'
            self.write({manual_status_field: new_status})
            message = 'Le statut du document a été réinitialisé à "À vérifier".' if reset else 'Le document a été validé avec succès.'
            title = 'Statut réinitialisé' if reset else 'Succès'
            msg_type = 'info' if reset else 'success'
        elif action_type == 'reject':
            self.write({manual_status_field: 'rejected'})
            rejection_reason = self.env.context.get('rejection_reason', "Document incorrect ou incomplet")
            self._generate_and_send_rejection_email(config['name'], rejection_reason)
            message = f'Le document a été rejeté{" et un email a été envoyé au partenaire" if self.email else ""}.'
            title = 'Information'
            msg_type = 'warning'
        else:
            return False

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': title, 'message': message, 'sticky': False, 'type': msg_type}
        }

    def validate_document(self):
        """
        Validate a document or reset its status to 'to_check'.
        
        This action is typically triggered by a button in the UI.
        The doc_type and reset parameters are expected in the context.
        
        Returns:
            dict: UI notification action
        """
        doc_type_key = self.env.context.get('doc_type')
        reset = self.env.context.get('reset', False)
        return self._perform_document_action(doc_type_key, 'validate', reset=reset)

    def reject_document(self):
        """
        Reject a document and notify partner.
        
        This action is typically triggered by a button in the UI.
        The doc_type parameter is expected in the context.
        
        Returns:
            dict: UI notification action
        """
        doc_type_key = self.env.context.get('doc_type')
        return self._perform_document_action(doc_type_key, 'reject')

    def _generate_upload_token_details(self):
        """
        Generate a secure upload token and URL for document uploads.
        
        This method creates a cryptographically secure token, sets its expiration,
        and generates a URL that can be used in notification emails.
        It now appends context-specific parameters like 'rib_request' or 'reminder'.
        
        Returns:
            str: The generated upload URL
        """
        self.ensure_one()
        token = base64.b64encode(os.urandom(32)).decode('utf-8').replace('/', '_').replace('+', '-')
        token_expiration = fields.Datetime.now() + timedelta(days=7)
        self.sudo().write({'upload_token': token, 'token_expiration': token_expiration})

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url').rstrip('/')
        safe_token = urllib.parse.quote(token, safe='')
        upload_url = f"{base_url}/documents/upload/{safe_token}"

        params = []
        if self.env.context.get('rib_request'):
            params.append("rib_request=1")
        if self.env.context.get('reminder'):
            params.append("reminder=1")
        
        if params:
            upload_url += "?" + "&".join(params)
            
        return upload_url

    def _generate_and_send_rejection_email(self, doc_name, rejection_reason):
        """
        Send a document rejection email with a secure upload link.
        
        Args:
            doc_name (str): Name of the rejected document
            rejection_reason (str): Reason for rejection
        """
        self.ensure_one()
        document_email_utils.send_document_notification(
            self,
            'rejection',
            doc_name=doc_name,
            rejection_reason=rejection_reason
        )

    def _send_expiry_email(self, doc_config, expiry_date, status, is_expired_doc=False):
        """
        Send an email notification about an expiring or expired document.
        
        This method creates a secure upload link and sends an email notification
        regarding a document that is expired or about to expire. For documents
        that are "about to expire", it tracks the last notification date to prevent
        sending notifications too frequently.
        
        Args:
            doc_config (dict): Document configuration dictionary
            expiry_date (date): Document's expiration date
            status (str): Status message ('expiré' or 'sur le point d'expirer')
            is_expired_doc (bool): Whether the document is already expired
        """
        self.ensure_one()
        document_email_utils.send_document_notification(
            self, 
            'expiry', 
            doc_config=doc_config, 
            expiry_date=expiry_date, 
            status=status,
            is_expired=is_expired_doc
        )

    def action_send_missing_documents_email(self):
        """
        Send an email requesting missing or rejected documents.
        
        This action creates a secure upload token and sends an email listing
        all documents that are missing or have been rejected.
        
        Returns:
            dict: UI notification action
        """
        self.ensure_one()
        if not self.email:
            return {'type': 'ir.actions.client', 'tag': 'display_notification',
                    'params': {'title': 'Erreur', 'message': 'Ce partenaire n\'a pas d\'adresse email configurée.',
                               'sticky': False, 'type': 'danger'}}

        documents_to_request = []
        for config in self._doc_config.values():
            auto_status = getattr(self, config['status_field'])
            manual_status = getattr(self, config['manual_status_field'])
            if auto_status == 'missing' or manual_status == 'rejected':
                documents_to_request.append(config['name'])

        if not documents_to_request:
            return {'type': 'ir.actions.client', 'tag': 'display_notification',
                    'params': {'title': 'Information', 'message': 'Aucun document manquant ou rejeté à demander.',
                               'sticky': False, 'type': 'info'}}

        success = document_email_utils.send_document_notification(
            self,
            'request',
            documents_to_request=documents_to_request
        )
        
        if success:
            message = f"Email de demande pour les documents ({', '.join(documents_to_request)}) envoyé à {self.email}."
            msg_params = {'title': 'Email Envoyé', 'message': message, 'sticky': False, 'type': 'success'}
        else:
            msg_params = {'title': 'Erreur', 'message': "Erreur lors de l'envoi de l'email.",
                          'sticky': False, 'type': 'danger'}
        
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': msg_params}

    def check_document_expiry(self):
        """
        Scan all subcontractors for expiring or expired documents and send notifications.
        
        This method is typically called by a scheduled cron job and processes partners
        in batches for memory efficiency. It identifies documents that are expired or
        expiring soon and sends appropriate notifications.
        """
        today = date.today()
        warning_threshold = today + timedelta(days=30)
        sous_traitants = self.search([('contact_type', '=', 'sous_traitant'), ('disable_document_emails', '=', False)])
        _logger.info('Started document expiry check for %s sous-traitants (notifications enabled)', len(sous_traitants))
        batch_size = 100
        for i in range(0, len(sous_traitants), batch_size):
            batch = sous_traitants[i:i + batch_size]
            try:
                self._process_document_expiry_batch(batch, today, warning_threshold)
                self.env.cr.commit()
            except Exception as e:
                _logger.error('Error processing document expiry batch %s-%s: %s', i, i + batch_size, str(e),
                              exc_info=True)
                self.env.cr.rollback()
        _logger.info('Completed document expiry check')

    def _process_document_expiry_batch(self, partners, today, warning_threshold):
        """
        Process a batch of partners for document expiration checks.
        
        This is a helper method for check_document_expiry that processes
        a subset of partners for memory efficiency.
        
        Args:
            partners (recordset): Batch of res.partner records to process
            today (date): Current date for comparison
            warning_threshold (date): Date threshold for "expiring soon" status
        """
        for partner in partners:
            try:
                for doc_key, config in self._doc_config.items():
                    content = getattr(partner, config['content_field'])
                    expiry_date = getattr(partner, config['expiry_field'])

                    if not (content and expiry_date):
                        continue

                    status_to_send = None
                    is_expired_doc_check = False

                    if expiry_date <= today:
                        status_to_send = "expiré"
                        is_expired_doc_check = True
                    elif expiry_date <= warning_threshold:
                        last_notif_date = getattr(partner, config['last_notif_field'])
                        if not last_notif_date or (today - last_notif_date).days >= 7:
                            status_to_send = "sur le point d'expirer"

                    if status_to_send:
                        partner._send_expiry_email(config, expiry_date, status_to_send, is_expired_doc_check)

            except Exception as e:
                _logger.error('Error processing partner %s (%s) for document expiry: %s', partner.name, partner.id,
                              str(e), exc_info=True)

    def _archive_document(self, doc_config, old_document_content, old_filename):
        """
        Archive an old document when a new version is uploaded.
        
        This method stores the old document in the document.archive model
        for historical tracking purposes.
        
        Args:
            doc_config (dict): Document configuration dictionary
            old_document_content (binary): Content of the document to archive
            old_filename (str): Filename of the document to archive
        """
        self.ensure_one()
        if not old_document_content:
            return

        # Map document types to match exactly the values in document_archive.document_type selection field
        content_field = doc_config['content_field']
        
        # Map directly to the selection field options to avoid any case mismatches
        document_type_mapping = {
            'document_identity_card': 'identity_card',
            'document_URSSAF': 'urssaf',
            'document_KBIS': 'kbis',
            'document_insurance': 'insurance',
            'document_RIB': 'rib'
        }
        
        # Use the mapping to get the correct value
        document_type = document_type_mapping.get(content_field, 'identity_card')  # Default to identity_card if not found
        
        _logger.info(f"Archiving document of type {document_type} for partner {self.name} (ID: {self.id})")
        
        try:
            self.env['document.archive'].create({
                'name': old_filename or f"{doc_config['name']} - {self.name}",
                'document': old_document_content,
                'document_type': document_type,
                'partner_id': self.id,
            })
            _logger.info(f"Document archived successfully: {doc_config['name']}")
        except Exception as e:
            _logger.error(f"Error archiving document for partner {self.id}: {e}")

    def write(self, vals):
        """
        Override write to handle document archiving, auto-expiry, and filename management.
        
        This method extends the standard write method to:
        1. Archive old documents when new ones are uploaded
        2. Automatically set expiration dates for URSSAF and KBIS documents
        3. Reset notification dates when documents are updated
        4. Standardize document filenames based on document type and partner name
        
        Args:
            vals (dict): Values to write
            
        Returns:
            bool: Result of super().write()
        """
        archival_actions = []
        if any(vals.get(config['content_field']) for config in self._doc_config.values()):
            for record in self:
                for doc_key, config in self._doc_config.items():
                    if vals.get(config['content_field']) and getattr(record, config['content_field']):
                        archival_actions.append({
                            'record_id': record.id,
                            'config': config,
                            'old_content': getattr(record, config['content_field']),
                            'old_filename': getattr(record, config['filename_field'])
                        })

        today = fields.Date.today()
        for doc_key, config in self._doc_config.items():
            content_field = config['content_field']
            if vals.get(content_field):
                vals[config['last_notif_field']] = False
                expiry_field = config.get('expiry_field')
                if config.get('auto_expiry_months') and expiry_field:
                    vals[expiry_field] = today + relativedelta(months=config['auto_expiry_months'])

        res = super(ResPartner, self).write(vals)

        for action in archival_actions:
            record = self.browse(action['record_id'])
            record._archive_document(action['config'], action['old_content'], action['old_filename'])

        if any(vals.get(config['content_field']) for config in self._doc_config.values()):
            for record in self:
                record_specific_filename_updates = {}
                for doc_key, config in self._doc_config.items():
                    if vals.get(config['content_field']):
                        new_filename = f"{config['filename_prefix']} - {record.name}.pdf"
                        if getattr(record, config['filename_field']) != new_filename:
                            record_specific_filename_updates[config['filename_field']] = new_filename

                if record_specific_filename_updates:
                    super(ResPartner, record).write(record_specific_filename_updates)

        return res

    def action_view_document(self):
        """
        View an archived document.
        
        This method is typically called from the document archives list view
        and generates a URL to view the selected document.
        
        Returns:
            dict: Action URL to view the document
            
        Raises:
            AccessError: If attempting to view another partner's document
        """
        self.ensure_one()
        active_id = self.env.context.get('active_id')
        if not active_id:
            return False
        archive = self.env['document.archive'].browse(active_id)
        if archive.partner_id != self:
            raise AccessError("Vous ne pouvez pas voir un document archivé d'un autre partenaire.")

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content?model=document.archive&field=document&id={archive.id}&filename={archive.name}',
            'target': 'new',
        }

    def action_send_rib_request_email(self):
        """Send an email requesting the RIB document."""
        self.ensure_one()
        if not self.email:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Erreur',
                    'message': 'Ce partenaire n\'a pas d\'adresse email configurée.',
                    'sticky': False,
                    'type': 'danger'
                }
            }

        # Correction : toujours générer un nouveau token et lien pour la demande RIB
        success = document_email_utils.send_document_notification(self, 'rib_request')

        if success:
            message = f"Email de demande de RIB envoyé à {self.email}."
            msg_params = {'title': 'Email Envoyé', 'message': message, 'sticky': False, 'type': 'success'}
        else:
            msg_params = {
                'title': 'Erreur',
                'message': "Erreur lors de l'envoi de l'email.",
                'sticky': False,
                'type': 'danger'
            }
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': msg_params}

    @api.model
    def get_all_subcontractors(self):
        """Récupère tous les partenaires marqués comme sous-traitants"""
        return self.search([('contact_type', '=', 'sous_traitant')])

    @api.model
    def get_subcontractors_by_document_status(self, status=None):
        """
        Récupère les sous-traitants selon l'état de leurs documents

        Args:
            status (str): État des documents ('valid', 'expired', 'expiring', 'missing', 'rejected', 'to_check')
        """
        domain = [('contact_type', '=', 'sous_traitant')]

        if status:
            if status == 'expired':
                domain.append(('has_expired_documents', '=', True))
            elif status == 'expiring':
                domain.append(('has_expiring_documents', '=', True))
            elif status in ['missing', 'rejected', 'to_check', 'valid']:
                # Pour filtrer par statut spécifique (manquant, rejeté, à vérifier, valide)
                status_domains = []
                for doc_key, config in self._doc_config.items():
                    status_domains.append((config['status_field'], '=', status))
                if status_domains:
                    domain.append('|' * (len(status_domains) - 1))
                    domain.extend(status_domains)

        return self.search(domain)

    @api.model
    def get_subcontractors_by_lot(self, lot_id=None):
        """
        Récupère les sous-traitants associés à un lot spécifique

        Args:
            lot_id (int): ID du lot (corps de métier)
        """
        domain = [('contact_type', '=', 'sous_traitant')]

        if lot_id:
            domain.append(('lots', 'in', [lot_id]))

        return self.search(domain)

    @api.model
    def filter_subcontractors(self, status=None, lot_id=None, document_type=None):
        """
        Méthode flexible pour filtrer les sous-traitants avec plusieurs critères

        Args:
            status (str): État des documents ('valid', 'expired', 'expiring', etc.)
            lot_id (int): ID du lot (corps de métier)
            document_type (str): Type de document spécifique à vérifier (une clé de _doc_config)

        Returns:
            recordset: Sous-traitants correspondant aux critères
        """
        domain = [('contact_type', '=', 'sous_traitant')]

        # Filtrage par lot
        if lot_id:
            domain.append(('lots', 'in', [lot_id]))

        # Filtrage par statut global
        if status and not document_type:
            if status == 'expired':
                domain.append(('has_expired_documents', '=', True))
            elif status == 'expiring':
                domain.append(('has_expiring_documents', '=', True))
            elif status in ['missing', 'rejected', 'to_check', 'valid']:
                status_domains = []
                for doc_key, config in self._doc_config.items():
                    status_domains.append((config['status_field'], '=', status))
                if status_domains:
                    domain.append('|' * (len(status_domains) - 1))
                    domain.extend(status_domains)

        # Filtrage par type de document spécifique et son statut
        if document_type and status and document_type in self._doc_config:
            config = self._doc_config[document_type]
            domain.append((config['status_field'], '=', status))

        return self.search(domain)

    def get_subcontractors_with_valid_docs(self):
        """Return subcontractors that have valid KBIS documents."""
        return self.filter_subcontractors(
            status='valid',
            document_type='document_KBIS'
        ).sorted('travaux_count', reverse=True)
