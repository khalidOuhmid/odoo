# -*- coding: utf-8 -*-
"""
Document Preview Wizard

Ce wizard permet d'afficher une prévisualisation de document dans une modal Odoo native
avec des fonctionnalités avancées de navigation et de validation.
"""

from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class DocumentPreviewWizard(models.TransientModel):
    """
    Wizard pour afficher la prévisualisation de documents dans une modal.
    """
    _name = 'document.preview.wizard'
    _description = 'Document Preview Wizard'

    partner_id = fields.Many2one(
        'res.partner',
        string='Partenaire',
        required=True,
        readonly=True
    )
    
    partner_name = fields.Char(
        string='Nom du partenaire',
        readonly=True
    )
    
    doc_type = fields.Char(
        string='Type de document',
        required=True,
        readonly=True
    )
    
    document_title = fields.Char(
        string='Titre du document',
        readonly=True
    )
    
    preview_url = fields.Char(
        string='URL de prévisualisation',
        readonly=True
    )
    
    download_url = fields.Char(
        string='URL de téléchargement',
        readonly=True,
        compute='_compute_download_url'
    )
    
    filename = fields.Char(
        string='Nom du fichier',
        readonly=True,
        compute='_compute_filename'
    )
    
    file_size = fields.Char(
        string='Taille du fichier',
        readonly=True,
        compute='_compute_file_info'
    )
    
    is_pdf = fields.Boolean(
        string='Est un PDF',
        readonly=True,
        compute='_compute_file_info'
    )
    
    is_image = fields.Boolean(
        string='Est une image',
        readonly=True,
        compute='_compute_file_info'
    )
    
    document_status = fields.Selection(
        string='Statut du document',
        readonly=True,
        compute='_compute_document_status',
        selection=[
            ('valid', 'Valide'),
            ('expiring', 'Expire bientôt'),
            ('expired', 'Expiré'),
            ('to_check', 'À vérifier'),
            ('rejected', 'Rejeté'),
            ('missing', 'Manquant')
        ]
    )
    
    can_validate = fields.Boolean(
        string='Peut valider',
        compute='_compute_permissions'
    )
    
    show_validation_buttons = fields.Boolean(
        string='Afficher boutons validation',
        compute='_compute_permissions'
    )

    @api.depends('partner_id', 'doc_type')
    def _compute_download_url(self):
        """Calcule l'URL de téléchargement."""
        for wizard in self:
            if wizard.partner_id and wizard.doc_type:
                wizard.download_url = f'/blg_contacts/document/download/{wizard.partner_id.id}/{wizard.doc_type}'
            else:
                wizard.download_url = False

    @api.depends('partner_id', 'doc_type')
    def _compute_filename(self):
        """Récupère le nom du fichier."""
        for wizard in self:
            if wizard.partner_id and wizard.doc_type:
                from ..models.document_config import DOCUMENT_TYPES
                if wizard.doc_type in DOCUMENT_TYPES:
                    config = DOCUMENT_TYPES[wizard.doc_type]
                    filename_field = config['filename_field']
                    wizard.filename = getattr(wizard.partner_id, filename_field, False) or f"{wizard.document_title}.pdf"
                else:
                    wizard.filename = f"{wizard.document_title}.pdf"
            else:
                wizard.filename = False

    @api.depends('partner_id', 'doc_type')
    def _compute_file_info(self):
        """Calcule les informations du fichier."""
        for wizard in self:
            if wizard.partner_id and wizard.doc_type:
                try:
                    info = wizard.partner_id.get_document_info_json(wizard.doc_type)
                    if 'error' not in info:
                        wizard.is_pdf = info.get('is_pdf', False)
                        wizard.is_image = info.get('is_image', False)
                        
                        # Formatage de la taille
                        size_bytes = info.get('size', 0)
                        if size_bytes > 1024 * 1024:
                            wizard.file_size = f"{size_bytes / (1024 * 1024):.1f} MB"
                        elif size_bytes > 1024:
                            wizard.file_size = f"{size_bytes / 1024:.1f} KB"
                        else:
                            wizard.file_size = f"{size_bytes} bytes"
                    else:
                        wizard.is_pdf = False
                        wizard.is_image = False
                        wizard.file_size = "Inconnu"
                except:
                    wizard.is_pdf = False
                    wizard.is_image = False
                    wizard.file_size = "Erreur"
            else:
                wizard.is_pdf = False
                wizard.is_image = False
                wizard.file_size = False

    @api.depends('partner_id', 'doc_type')
    def _compute_document_status(self):
        """Calcule le statut du document."""
        for wizard in self:
            if wizard.partner_id and wizard.doc_type:
                from ..models.document_config import DOCUMENT_TYPES
                if wizard.doc_type in DOCUMENT_TYPES:
                    config = DOCUMENT_TYPES[wizard.doc_type]
                    status_field = config['status_field']
                    wizard.document_status = getattr(wizard.partner_id, status_field, 'missing')
                else:
                    wizard.document_status = 'missing'
            else:
                wizard.document_status = 'missing'

    @api.depends('partner_id')
    def _compute_permissions(self):
        """Calcule les permissions de l'utilisateur."""
        for wizard in self:
            # Vérifier si l'utilisateur peut valider des documents
            wizard.can_validate = self.env.user.has_group('base.group_system') or \
                                 self.env.user.has_group('blg_contacts_extension.group_conductrice_travaux') or \
                                 self.env.user.has_group('blg_contacts_extension.group_directeur_general')
            
            # Afficher les boutons seulement si le document est à vérifier et que l'utilisateur a les droits
            wizard.show_validation_buttons = wizard.can_validate and wizard.document_status == 'to_check'

    def action_download_document(self):
        """Télécharge le document."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': self.download_url,
            'target': 'new',
        }

    def action_validate_document(self):
        """Valide le document."""
        self.ensure_one()
        result = self.partner_id.with_context(doc_type=self.doc_type).action_validate_document()
        
        # Recharger les informations
        self._compute_document_status()
        self._compute_permissions()
        
        # Message de confirmation
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Document validé',
                'message': f'Le document {self.document_title} a été validé avec succès.',
                'type': 'success',
                'sticky': False,
            }
        }

    def action_reject_document(self):
        """Rejette le document."""
        self.ensure_one()
        result = self.partner_id.with_context(doc_type=self.doc_type).action_reject_document()
        
        # Recharger les informations
        self._compute_document_status()
        self._compute_permissions()
        
        # Message de confirmation
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Document rejeté',
                'message': f'Le document {self.document_title} a été rejeté.',
                'type': 'warning',
                'sticky': False,
            }
        }

    def action_open_partner(self):
        """Ouvre la fiche du partenaire."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'res_id': self.partner_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_refresh_preview(self):
        """Actualise la prévisualisation."""
        self.ensure_one()
        
        # Recharger toutes les informations
        self._compute_download_url()
        self._compute_filename()
        self._compute_file_info()
        self._compute_document_status()
        self._compute_permissions()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Actualisé',
                'message': 'La prévisualisation a été actualisée.',
                'type': 'info',
                'sticky': False,
            }
        }
