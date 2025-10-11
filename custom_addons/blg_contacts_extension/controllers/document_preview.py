# -*- coding: utf-8 -*-
"""
Document Preview Controller

Ce contrôleur gère la prévisualisation et le téléchargement sécurisé des documents
pour le module BLG Contacts Extension.

Author: BLG IT Team
Odoo 18 Compatible
"""

from odoo import http, fields, _
from odoo.http import request, Response
from odoo.exceptions import AccessError, ValidationError
import base64
import logging
import mimetypes
from ..models.document_config import DOCUMENT_TYPES

_logger = logging.getLogger(__name__)


class DocumentPreviewController(http.Controller):
    """
    Contrôleur pour la prévisualisation et le téléchargement de documents.
    """

    def _check_document_access(self, partner_id, doc_type):
        """
        Vérifie l'accès au document.
        
        Args:
            partner_id (int): ID du partenaire
            doc_type (str): Type de document
            
        Returns:
            tuple: (partner, document_content, filename) ou (False, False, False) si accès refusé
        """
        try:
            # Vérifier que l'utilisateur est connecté
            if not request.env.user or request.env.user._is_public():
                return False, False, False
            
            # Vérifier que le type de document est valide
            if doc_type not in DOCUMENT_TYPES:
                _logger.warning(f"Type de document invalide demandé: {doc_type}")
                return False, False, False
            
            # Récupérer le partenaire
            partner = request.env['res.partner'].browse(partner_id)
            if not partner.exists():
                _logger.warning(f"Partenaire inexistant: {partner_id}")
                return False, False, False
            
            # Vérifier les droits d'accès au partenaire
            try:
                partner.check_access_rights('read')
                partner.check_access_rule('read')
            except AccessError:
                _logger.warning(f"Accès refusé au partenaire {partner_id} pour l'utilisateur {request.env.user.id}")
                return False, False, False
            
            # Récupérer les informations du document
            config = DOCUMENT_TYPES[doc_type]
            content_field = config['content_field']
            filename_field = config['filename_field']
            
            document_content = getattr(partner, content_field, False)
            document_filename = getattr(partner, filename_field, False)
            
            if not document_content:
                _logger.warning(f"Document {doc_type} non trouvé pour le partenaire {partner_id}")
                return False, False, False
            
            # Générer un nom de fichier par défaut si nécessaire
            if not document_filename:
                extension = 'pdf'  # Extension par défaut
                document_filename = f"{config['display_name_fr']}_{partner.name}.{extension}"
            
            return partner, document_content, document_filename
            
        except Exception as e:
            _logger.error(f"Erreur lors de la vérification d'accès au document: {e}")
            return False, False, False

    @http.route(['/blg_contacts/document/preview/<int:partner_id>/<string:doc_type>'], 
                type='http', auth="user", website=True)
    def preview_document(self, partner_id, doc_type, **kwargs):
        """
        Affiche la prévisualisation d'un document dans le navigateur.
        
        Args:
            partner_id (int): ID du partenaire
            doc_type (str): Type de document
            
        Returns:
            Response: Page de prévisualisation ou document direct selon le type
        """
        partner, document_content, document_filename = self._check_document_access(partner_id, doc_type)
        
        if not partner:
            return request.render('blg_contacts_extension.document_preview_error', {
                'error_message': 'Document non trouvé ou accès refusé.'
            })
        
        try:
            # Pour les requêtes directes (ex: iframe), servir le document directement
            if kwargs.get('direct'):
                return self._serve_document_direct(document_content, document_filename)
            
            # Sinon, afficher la page de prévisualisation
            config = DOCUMENT_TYPES[doc_type]
            
            # Déterminer le type de fichier
            mimetype, _ = mimetypes.guess_type(document_filename)
            is_pdf = mimetype == 'application/pdf' or document_filename.lower().endswith('.pdf')
            is_image = mimetype and mimetype.startswith('image/')
            
            # URLs pour les actions
            preview_direct_url = f'/blg_contacts/document/preview/{partner_id}/{doc_type}?direct=1'
            download_url = f'/blg_contacts/document/download/{partner_id}/{doc_type}'
            
            return request.render('blg_contacts_extension.document_preview_template', {
                'partner_name': partner.name,
                'document_title': config['display_name_fr'],
                'filename': document_filename,
                'is_pdf': is_pdf,
                'is_image': is_image,
                'preview_url': preview_direct_url,
                'download_url': download_url,
            })
            
        except Exception as e:
            _logger.error(f"Erreur lors de la prévisualisation du document: {e}")
            return request.render('blg_contacts_extension.document_preview_error', {
                'error_message': 'Erreur lors du chargement du document.'
            })

    def _serve_document_direct(self, document_content, document_filename):
        """
        Sert le document directement (pour iframe ou téléchargement direct).
        
        Args:
            document_content (str): Contenu base64 du document
            document_filename (str): Nom du fichier
            
        Returns:
            Response: Document binaire
        """
        # Décoder le contenu base64
        document_binary = base64.b64decode(document_content)
        
        # Déterminer le type MIME
        mimetype, _ = mimetypes.guess_type(document_filename)
        if not mimetype:
            mimetype = 'application/pdf'  # Défaut pour les documents
        
        # Créer la réponse HTTP
        headers = [
            ('Content-Type', mimetype),
            ('Content-Length', str(len(document_binary))),
            ('Content-Disposition', f'inline; filename="{document_filename}"'),
            ('Cache-Control', 'no-cache, no-store, must-revalidate'),
            ('Pragma', 'no-cache'),
            ('Expires', '0'),
        ]
        
        return Response(document_binary, headers=headers)

    @http.route(['/blg_contacts/document/download/<int:partner_id>/<string:doc_type>'], 
                type='http', auth="user", website=False)
    def download_document(self, partner_id, doc_type, **kwargs):
        """
        Télécharge un document.
        
        Args:
            partner_id (int): ID du partenaire
            doc_type (str): Type de document
            
        Returns:
            Response: Document à télécharger ou page d'erreur
        """
        partner, document_content, document_filename = self._check_document_access(partner_id, doc_type)
        
        if not partner:
            return request.render('http_routing.404', {})
        
        try:
            # Décoder le contenu base64
            document_binary = base64.b64decode(document_content)
            
            # Déterminer le type MIME
            mimetype, _ = mimetypes.guess_type(document_filename)
            if not mimetype:
                mimetype = 'application/octet-stream'  # Défaut pour le téléchargement
            
            # Créer la réponse HTTP pour téléchargement
            headers = [
                ('Content-Type', mimetype),
                ('Content-Length', str(len(document_binary))),
                ('Content-Disposition', f'attachment; filename="{document_filename}"'),
                ('Cache-Control', 'no-cache, no-store, must-revalidate'),
                ('Pragma', 'no-cache'),
                ('Expires', '0'),
            ]
            
            return Response(document_binary, headers=headers)
            
        except Exception as e:
            _logger.error(f"Erreur lors du téléchargement du document: {e}")
            return request.render('http_routing.404', {})

    @http.route(['/blg_contacts/document/info/<int:partner_id>/<string:doc_type>'], 
                type='json', auth="user", website=False)
    def get_document_info(self, partner_id, doc_type, **kwargs):
        """
        Récupère les informations sur un document (pour AJAX).
        
        Args:
            partner_id (int): ID du partenaire
            doc_type (str): Type de document
            
        Returns:
            dict: Informations sur le document ou erreur
        """
        partner, document_content, document_filename = self._check_document_access(partner_id, doc_type)
        
        if not partner:
            return {'error': 'Document non trouvé ou accès refusé'}
        
        try:
            # Calculer la taille du document
            document_binary = base64.b64decode(document_content)
            file_size = len(document_binary)
            
            # Déterminer le type MIME
            mimetype, _ = mimetypes.guess_type(document_filename)
            
            config = DOCUMENT_TYPES[doc_type]
            
            return {
                'success': True,
                'filename': document_filename,
                'size': file_size,
                'size_human': self._human_size(file_size),
                'mimetype': mimetype,
                'document_type': config['display_name_fr'],
                'preview_url': f'/blg_contacts/document/preview/{partner_id}/{doc_type}',
                'download_url': f'/blg_contacts/document/download/{partner_id}/{doc_type}',
            }
            
        except Exception as e:
            _logger.error(f"Erreur lors de la récupération des infos du document: {e}")
            return {'error': 'Erreur lors du traitement du document'}

    def _human_size(self, size_bytes):
        """
        Convertit une taille en bytes en format lisible.
        
        Args:
            size_bytes (int): Taille en bytes
            
        Returns:
            str: Taille formatée (ex: "1.2 MB")
        """
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.1f} {size_names[i]}"
