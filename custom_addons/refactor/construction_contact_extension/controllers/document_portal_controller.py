# -*- coding: utf-8 -*-
"""
Controller pour le portail d'upload de documents des partenaires
===============================================================

Permet aux sous-traitants d'accéder à un portail sécurisé pour téléverser
leurs documents via un lien avec token d'authentification.
"""

import json
import base64
import urllib.parse
from datetime import datetime
from werkzeug.exceptions import NotFound, Forbidden, BadRequest
from werkzeug.utils import redirect

from odoo import http, fields, _
from odoo.http import request
from odoo.exceptions import ValidationError, AccessError
from odoo.addons.portal.controllers.portal import CustomerPortal
# Import des utilitaires du core
from odoo.addons.construction_core.utils.helpers import FileHelper, SecurityHelper, NotificationHelper
from odoo.addons.construction_core.utils.validators import FileValidator
import logging

_logger = logging.getLogger(__name__)


class DocumentPortalController(http.Controller):
    """Controller pour le portail d'upload de documents"""

    # =================== CONFIGURATION DU PORTAIL ===================

    def _get_portal_config(self):
        """Configuration spécifique du portail de documents"""
        return {
            'route_base': '/documents/upload',
            'template_prefix': 'construction_contact_extension',
            'allowed_file_types': ['.pdf', '.jpg', '.jpeg', '.png', '.doc', '.docx'],
            'max_file_size_mb': 10.0,
            'require_authentication': True,
            'session_timeout_minutes': 60,
            'auto_redirect_after_upload': True
        }

    # =================== MÉTHODES COMMUNES ===================

    def _validate_file(self, file, config):
        """Valide un fichier uploadé selon la configuration"""
        if not file:
            return False, "Aucun fichier sélectionné"

        # Vérifier l'extension
        filename = file.filename.lower()
        allowed_extensions = config.get('allowed_file_types', ['.pdf'])

        if not any(filename.endswith(ext) for ext in allowed_extensions):
            allowed_str = ', '.join(allowed_extensions)
            return False, f"Format de fichier non autorisé. Formats acceptés : {allowed_str}"

        # Vérifier la taille
        file.seek(0, 2)  # Aller à la fin
        file_size = file.tell()
        file.seek(0)  # Revenir au début

        max_size_bytes = config.get('max_file_size_mb', 10) * 1024 * 1024
        if file_size > max_size_bytes:
            max_size_mb = config.get('max_file_size_mb', 10)
            return False, f"Fichier trop volumineux. Taille maximum : {max_size_mb}MB"

        # Vérifier que le fichier n'est pas vide
        if file_size == 0:
            return False, "Le fichier est vide"

        return True, None

    def _prepare_file_data(self, file):
        """Prépare les données du fichier pour traitement"""
        file.seek(0)
        content = file.read()

        return {
            'filename': file.filename,
            'content': content,
            'content_b64': base64.b64encode(content),
            'size': len(content)
        }

    def _render_template(self, template_name, context):
        """Rend un template avec le préfixe configuré"""
        config = self._get_portal_config()
        full_template_name = f"{config['template_prefix']}.{template_name}"

        # Ajouter les variables communes
        context.update({
            'datetime': datetime,
            'today': fields.Date.today(),
        })

        return request.render(full_template_name, context)

    # =================== ROUTES PRINCIPALES ===================

    @http.route([
        '/documents/upload/<string:token>',
        '/documents/upload/<string:token>/<path:subpath>'
    ], type='http', auth="public", website=True, csrf=False)
    def portal_document_upload(self, token, subpath=None, **kw):
        """Route principale du portail d'upload"""
        return self.portal_main_route(token, subpath=subpath, **kw)

    @http.route(['/documents/upload/<string:token>/ajax'],
                type='json', auth="public", methods=['POST'], csrf=False)
    def portal_upload_ajax(self, token, **kw):
        """Upload AJAX de fichiers"""
        try:
            # Validation du token
            partner = self._validate_token(token)
            if not partner:
                return {'success': False, 'error': 'Token invalide ou expiré'}

            # Traitement de l'upload
            result = self._process_ajax_upload(partner, kw)
            return result

        except Exception as e:
            _logger.error(f"AJAX upload error: {str(e)}")
            return {'success': False, 'error': 'Erreur lors de l\'upload'}

    @http.route(['/documents/upload/<string:token>/progress'],
                type='json', auth="public", methods=['GET'], csrf=False)
    def portal_upload_progress(self, token, **kw):
        """Récupère la progression des uploads"""
        try:
            partner = self._validate_token(token)
            if not partner:
                return {'error': 'Token invalide'}

            # Récupérer les statistiques de progression
            progress_data = self._get_upload_progress(partner)
            return {'success': True, 'data': progress_data}

        except Exception as e:
            _logger.error(f"Progress check error: {str(e)}")
            return {'success': False, 'error': str(e)}

    # =================== VALIDATION ET AUTHENTIFICATION ===================

    def _validate_token(self, token):
        """Valide le token d'accès et retourne le partenaire"""
        if not token:
            return None

        try:
            # Rechercher le partenaire avec ce token
            partner = request.env['res.partner'].sudo().search([
                ('upload_token', '=', token),
                ('is_subcontractor', '=', True)
            ], limit=1)

            if not partner:
                _logger.warning(f"Invalid token attempted: {token}")
                return None

            # Vérifier l'expiration
            if not partner.is_token_valid():
                _logger.warning(f"Expired token used by partner {partner.id}")
                return None

            return partner

        except Exception as e:
            _logger.error(f"Token validation error: {str(e)}")
            return None

    def _check_partner_access(self, partner):
        """Vérifie les droits d'accès du partenaire"""
        if not partner.is_subcontractor:
            raise Forbidden("Accès réservé aux sous-traitants")

        if partner.notification_preferences == 'none':
            raise Forbidden("Accès au portail désactivé")

        return True

    # =================== PRÉPARATION DU CONTEXTE ===================

    def _prepare_upload_context(self, partner, **kw):
        """Prépare le contexte pour le template d'upload"""
        try:
            # Contexte de base du partenaire
            context = partner.get_portal_context()

            # Informations sur les types de documents
            document_types = self._get_available_document_types(partner)

            # Statistiques et progression
            upload_stats = self._get_upload_statistics(partner)

            # Messages et alertes
            messages = self._get_portal_messages(partner, kw)

            # Configuration du portail
            portal_config = self._get_portal_config()

            # Fusionner tout le contexte
            context.update({
                'document_types': document_types,
                'upload_stats': upload_stats,
                'messages': messages,
                'portal_config': portal_config,
                'current_url': request.httprequest.url,
                'upload_ajax_url': f"/documents/upload/{partner.upload_token}/ajax",
                'progress_url': f"/documents/upload/{partner.upload_token}/progress",
                'max_file_size_bytes': int(portal_config['max_file_size_mb'] * 1024 * 1024),
                'allowed_extensions': portal_config['allowed_file_types'],
                'csrf_token': request.csrf_token(),
                'debug_mode': request.env.context.get('debug', False)
            })

            return context

        except Exception as e:
            _logger.error(f"Error preparing upload context: {str(e)}")
            return {'error': 'Erreur de préparation du contexte'}

    def _get_available_document_types(self, partner):
        """Récupère les types de documents disponibles pour ce partenaire"""
        try:
            # Documents obligatoires
            mandatory_types = request.env['document.type'].sudo().search([
                ('is_mandatory', '=', True),
                ('active', '=', True)
            ])

            # Documents par spécialité
            speciality_types = request.env['document.type'].sudo().search([
                ('required_for_specialities', 'in', partner.speciality_ids.ids),
                ('active', '=', True)
            ])

            # Fusionner et dédoublonner
            all_types = (mandatory_types | speciality_types).sorted('sequence')

            # Préparer les données pour le template
            types_data = []
            for doc_type in all_types:
                # Vérifier s'il existe déjà un document de ce type
                existing_doc = partner.document_ids.filtered(
                    lambda d: d.document_type_id == doc_type
                )

                type_data = {
                    'id': doc_type.id,
                    'name': doc_type.name,
                    'code': doc_type.code,
                    'description': doc_type.description,
                    'is_mandatory': doc_type.is_mandatory,
                    'has_expiry': doc_type.has_expiry,
                    'allowed_types': doc_type.get_allowed_extensions_list(),
                    'max_size_mb': doc_type.max_file_size_mb,
                    'upload_instructions': doc_type.upload_instructions,
                    'existing_document': existing_doc[0] if existing_doc else None,
                    'upload_context': doc_type.get_upload_context(partner)
                }
                types_data.append(type_data)

            return types_data

        except Exception as e:
            _logger.error(f"Error getting document types: {str(e)}")
            return []

    def _get_upload_statistics(self, partner):
        """Récupère les statistiques d'upload du partenaire"""
        try:
            documents = partner.document_ids

            return {
                'total_documents': len(documents),
                'uploaded_documents': len(documents.filtered('file_content')),
                'valid_documents': len(documents.filtered(lambda d: d.state == 'valid')),
                'pending_documents': len(documents.filtered(lambda d: d.state == 'to_check')),
                'rejected_documents': len(documents.filtered(lambda d: d.state == 'rejected')),
                'expired_documents': len(documents.filtered(lambda d: d.state == 'expired')),
                'completion_rate': partner.document_completion_rate,
                'health_score': partner.document_health_score
            }

        except Exception as e:
            _logger.error(f"Error getting upload statistics: {str(e)}")
            return {}

    def _get_portal_messages(self, partner, request_params):
        """Récupère les messages et alertes pour le portail"""
        messages = {
            'success': [],
            'warning': [],
            'error': [],
            'info': []
        }

        try:
            # Messages de paramètres URL
            if request_params.get('success'):
                messages['success'].append("Opération réussie !")

            if request_params.get('error'):
                messages['error'].append(request_params['error'])

            # Messages contextuels
            if partner.has_expired_documents:
                messages['warning'].append(
                    "Vous avez des documents expirés qui nécessitent un renouvellement."
                )

            if partner.has_expiring_documents:
                messages['warning'].append(
                    "Certains de vos documents expirent bientôt."
                )

            missing_docs = partner.get_missing_documents()
            if missing_docs:
                messages['info'].append(
                    f"Documents manquants : {', '.join(missing_docs)}"
                )

            # Message de bienvenue pour première visite
            if not partner.document_ids:
                messages['info'].append(
                    "Bienvenue ! Téléversez vos documents pour compléter votre dossier."
                )

            return messages

        except Exception as e:
            _logger.error(f"Error getting portal messages: {str(e)}")
            return messages

    # =================== TRAITEMENT DES UPLOADS ===================

    def _process_file_upload(self, partner, file_data, upload_context):
        """Traite l'upload d'un fichier (méthode héritée de BasePortalController)"""
        try:
            # Déterminer le type de document
            doc_type_code = file_data.get('doc_type') or upload_context.get('doc_type')
            if not doc_type_code:
                return False, "Type de document non spécifié"

            # Rechercher le type de document
            doc_type = request.env['document.type'].sudo().search([
                ('code', '=', doc_type_code)
            ], limit=1)

            if not doc_type:
                return False, f"Type de document '{doc_type_code}' non trouvé"

            # Validation spécifique
            validation_result = self._validate_document_upload(doc_type, file_data, partner)
            if not validation_result['valid']:
                return False, validation_result['error']

            # Traitement du fichier
            return self._save_partner_document(partner, doc_type, file_data, upload_context)

        except Exception as e:
            _logger.error(f"File upload processing error: {str(e)}")
            return False, f"Erreur de traitement : {str(e)}"

    def _validate_document_upload(self, doc_type, file_data, partner):
        """Valide un document avant upload"""
        try:
            filename = file_data.get('filename', '')
            file_content = file_data.get('content_b64', '')

            # Validation via le type de document
            validation = doc_type.validate_document_data(
                file_content,
                filename,
                file_data.get('expiry_date')
            )

            if not validation['valid']:
                return validation

            # Validations supplémentaires avec les validators du core
            file_size = len(base64.b64decode(file_content)) if file_content else 0

            # Validation de la taille
            size_validation = FileValidator.validate_file_size(
                file_size,
                doc_type.max_file_size_mb
            )
            if not size_validation['valid']:
                return size_validation

            # Validation du type de fichier
            type_validation = FileValidator.validate_file_type(
                filename,
                doc_type.get_allowed_extensions_list()
            )
            if not type_validation['valid']:
                return type_validation

            return {'valid': True}

        except Exception as e:
            _logger.error(f"Document validation error: {str(e)}")
            return {'valid': False, 'error': 'Erreur de validation'}

    def _save_partner_document(self, partner, doc_type, file_data, upload_context):
        """Sauvegarde le document du partenaire"""
        try:
            # Vérifier s'il existe déjà un document de ce type
            existing_doc = partner.document_ids.filtered(
                lambda d: d.document_type_id == doc_type
            )

            # Préparer les données du document
            document_data = {
                'partner_id': partner.id,
                'document_type_id': doc_type.id,
                'file_content': file_data['content_b64'],
                'filename': FileHelper.generate_safe_filename(
                    file_data['filename'],
                    prefix=partner.name.replace(' ', '_')
                ),
                'upload_date': fields.Datetime.now(),
                'state': 'to_check'
            }

            # Ajouter la date d'expiration si fournie
            if file_data.get('expiry_date'):
                document_data['expiry_date'] = file_data['expiry_date']
            elif doc_type.has_expiry:
                # Calculer une date d'expiration par défaut
                document_data['expiry_date'] = doc_type.get_default_expiry_date()

            # Créer ou mettre à jour le document
            if existing_doc:
                # Archiver l'ancien document et mettre à jour
                existing_doc._archive_current_version('replaced')
                existing_doc.write(document_data)
                document = existing_doc
            else:
                # Créer un nouveau document
                document = request.env['partner.document'].sudo().create(document_data)

            # Message de confirmation
            document.message_post(
                body=f"📄 Document téléversé via le portail par {partner.name}",
                message_type='notification'
            )

            return True, None

        except Exception as e:
            _logger.error(f"Error saving document: {str(e)}")
            return False, f"Erreur de sauvegarde : {str(e)}"

    def _process_ajax_upload(self, partner, upload_data):
        """Traite un upload AJAX"""
        try:
            # Récupérer les données du fichier depuis la requête AJAX
            files = request.httprequest.files
            if not files:
                return {'success': False, 'error': 'Aucun fichier reçu'}

            results = []

            for field_name, file_obj in files.items():
                if not file_obj.filename:
                    continue

                # Préparer les données du fichier
                file_content = file_obj.read()
                file_data = {
                    'filename': file_obj.filename,
                    'content_b64': base64.b64encode(file_content).decode('utf-8'),
                    'size': len(file_content),
                    'doc_type': upload_data.get(f'{field_name}_type'),
                    'expiry_date': upload_data.get(f'{field_name}_expiry')
                }

                # Traiter l'upload
                success, error = self._process_file_upload(partner, file_data, upload_data)

                results.append({
                    'filename': file_obj.filename,
                    'success': success,
                    'error': error,
                    'doc_type': file_data['doc_type']
                })

            # Calculer le résultat global
            success_count = sum(1 for r in results if r['success'])
            total_count = len(results)

            return {
                'success': success_count > 0,
                'results': results,
                'summary': f"{success_count}/{total_count} fichier(s) uploadé(s) avec succès",
                'partner_completion': partner.document_completion_rate
            }

        except Exception as e:
            _logger.error(f"AJAX upload processing error: {str(e)}")
            return {'success': False, 'error': str(e)}

    # =================== ACTIONS SPÉCIALISÉES ===================

    @http.route(['/documents/upload/<string:token>/delete/<int:doc_id>'],
                type='http', auth="public", methods=['POST'], csrf=False)
    def portal_delete_document(self, token, doc_id, **kw):
        """Supprime un document depuis le portail"""
        try:
            partner = self._validate_token(token)
            if not partner:
                return request.redirect(f'/documents/upload/{token}?error=Token invalide')

            # Rechercher le document
            document = request.env['partner.document'].sudo().search([
                ('id', '=', doc_id),
                ('partner_id', '=', partner.id)
            ])

            if not document:
                return request.redirect(f'/documents/upload/{token}?error=Document non trouvé')

            # Archiver et supprimer
            if document.file_content:
                document._archive_current_version('deleted')

            document_name = document.display_name
            document.unlink()

            return request.redirect(f'/documents/upload/{token}?success=Document {document_name} supprimé')

        except Exception as e:
            _logger.error(f"Document deletion error: {str(e)}")
            return request.redirect(f'/documents/upload/{token}?error=Erreur de suppression')

    @http.route(['/documents/upload/<string:token>/download/<int:doc_id>'],
                type='http', auth="public")
    def portal_download_document(self, token, doc_id, **kw):
        """Télécharge un document depuis le portail"""
        try:
            partner = self._validate_token(token)
            if not partner:
                raise Forbidden("Token invalide")

            # Rechercher le document
            document = request.env['partner.document'].sudo().search([
                ('id', '=', doc_id),
                ('partner_id', '=', partner.id)
            ])

            if not document or not document.file_content:
                raise NotFound("Document non trouvé")

            # Préparer la réponse de téléchargement
            file_content = base64.b64decode(document.file_content)

            return request.make_response(
                file_content,
                headers=[
                    ('Content-Type', 'application/octet-stream'),
                    ('Content-Disposition', f'attachment; filename="{document.filename}"'),
                    ('Content-Length', str(len(file_content)))
                ]
            )

        except Exception as e:
            _logger.error(f"Document download error: {str(e)}")
            raise NotFound("Document non disponible")

    @http.route(['/documents/upload/<string:token>/refresh'],
                type='http', auth="public", methods=['POST'], csrf=False)
    def portal_refresh_status(self, token, **kw):
        """Actualise le statut des documents"""
        try:
            partner = self._validate_token(token)
            if not partner:
                return request.redirect(f'/documents/upload/{token}?error=Token invalide')

            # Recalculer les statuts des documents
            for document in partner.document_ids:
                document._auto_compute_state()

            return request.redirect(f'/documents/upload/{token}?success=Statuts actualisés')

        except Exception as e:
            _logger.error(f"Status refresh error: {str(e)}")
            return request.redirect(f'/documents/upload/{token}?error=Erreur d\'actualisation')

    # =================== UTILITAIRES ===================

    def _get_upload_progress(self, partner):
        """Calcule la progression des uploads"""
        try:
            total_required = len(self._get_available_document_types(partner))
            uploaded_count = len(partner.document_ids.filtered('file_content'))

            return {
                'total_required': total_required,
                'uploaded_count': uploaded_count,
                'completion_percent': (uploaded_count / total_required * 100) if total_required > 0 else 100,
                'missing_documents': partner.get_missing_documents(),
                'last_upload': max(partner.document_ids.mapped('upload_date')) if partner.document_ids else None
            }

        except Exception as e:
            _logger.error(f"Progress calculation error: {str(e)}")
            return {}

    def _log_portal_access(self, partner, action, details=None):
        """Log les accès au portail pour audit"""
        try:
            log_message = f"Portal access: {action} by partner {partner.name} ({partner.id})"
            if details:
                log_message += f" - {details}"

            _logger.info(log_message)

            # Optionnel : enregistrer dans un modèle d'audit spécialisé
            if hasattr(request.env, 'portal.access.log'):
                request.env['portal.access.log'].sudo().create({
                    'partner_id': partner.id,
                    'action': action,
                    'details': details,
                    'access_date': fields.Datetime.now(),
                    'ip_address': request.httprequest.environ.get('REMOTE_ADDR'),
                    'user_agent': request.httprequest.environ.get('HTTP_USER_AGENT')
                })

        except Exception as e:
            _logger.error(f"Portal access logging error: {str(e)}")

    # =================== GESTION DES ERREURS ===================

    def _handle_portal_error(self, token, error_type, error_message):
        """Gestion centralisée des erreurs du portail"""
        try:
            # Logger l'erreur
            _logger.error(f"Portal error [{error_type}]: {error_message}")

            # Rediriger avec message d'erreur
            if token:
                return request.redirect(f'/documents/upload/{token}?error={error_message}')
            else:
                # Page d'erreur générique si pas de token
                return request.render('construction_contact_extension.portal_error', {
                    'error_type': error_type,
                    'error_message': error_message
                })

        except Exception as e:
            _logger.critical(f"Error handler failed: {str(e)}")
            return request.not_found()

    @http.route(['/documents/upload/error'], type='http', auth="public", website=True)
    def portal_error_page(self, **kw):
        """Page d'erreur générique du portail"""
        return request.render('construction_contact_extension.portal_error', {
            'error_type': kw.get('type', 'unknown'),
            'error_message': kw.get('message', 'Une erreur inattendue s\'est produite')
        })

    # =================== ROUTES DE DEBUG (DÉVELOPPEMENT UNIQUEMENT) ===================

    @http.route(['/documents/upload/<string:token>/debug'],
                type='http', auth="public", website=True)
    def portal_debug_info(self, token, **kw):
        """Informations de debug (développement uniquement)"""
        if not request.env.context.get('debug'):
            raise NotFound()

        try:
            partner = self._validate_token(token)
            if not partner:
                return "Token invalide"

            debug_info = {
                'partner': {
                    'id': partner.id,
                    'name': partner.name,
                    'token': partner.upload_token,
                    'token_expiry': partner.token_expiration,
                    'is_token_valid': partner.is_token_valid()
                },
                'documents': [
                    {
                        'id': doc.id,
                        'type': doc.document_type_id.name,
                        'state': doc.state,
                        'filename': doc.filename,
                        'upload_date': doc.upload_date
                    }
                    for doc in partner.document_ids
                ],
                'statistics': self._get_upload_statistics(partner),
                'config': self._get_portal_config()
            }

            return f"<pre>{json.dumps(debug_info, indent=2, default=str)}</pre>"

        except Exception as e:
            return f"Debug error: {str(e)}"


# =================== EXTENSIONS POUR L'HÉRITAGE ===================

class PortalAccount(CustomerPortal):
    """Extension du portail client pour les fonctionnalités documents"""

    @http.route()
    def account(self, **kw):
        """Étend la page de compte pour inclure les documents"""
        response = super().account(**kw)

        # Ajouter les informations de documents si c'est un sous-traitant
        if hasattr(request.env.user, 'partner_id') and request.env.user.partner_id.is_subcontractor:
            partner = request.env.user.partner_id

            # Vérifier si le partenaire a un token valide
            has_valid_token = partner.is_token_valid()

            # Ajouter au contexte
            if isinstance(response.qcontext, dict):
                response.qcontext.update({
                    'document_completion_rate': partner.document_completion_rate,
                    'has_expired_documents': partner.has_expired_documents,
                    'has_expiring_documents': partner.has_expiring_documents,
                    'has_valid_upload_token': has_valid_token,
                    'upload_portal_url': f"/documents/upload/{partner.upload_token}" if has_valid_token else None
                })

        return response
