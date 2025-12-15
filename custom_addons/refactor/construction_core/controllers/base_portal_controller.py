# construction_core/controllers/base_portal_controller.py
from odoo import http, fields, _
from odoo.http import request
import base64
import logging
import urllib.parse
from datetime import datetime
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple, Any

_logger = logging.getLogger(__name__)


class BasePortalController(http.Controller, ABC):
    """Controller de base abstrait - ne doit pas être instancié directement"""
    
    def __new__(cls, *args, **kwargs):
        """Empêche l'instanciation directe de cette classe abstraite"""
        if cls == BasePortalController:
            raise TypeError("BasePortalController est une classe abstraite et ne peut pas être instanciée directement")
        return super().__new__(cls)
    
    # Empêcher l'instanciation automatique par Odoo
    def __init__(self, *args, **kwargs):
        if self.__class__ == BasePortalController:
            raise TypeError("BasePortalController est une classe abstraite et ne peut pas être instanciée directement")
        super().__init__(*args, **kwargs)
    
    # Empêcher l'instanciation automatique par Odoo lors du chargement des contrôleurs
    @classmethod
    def _is_abstract(cls):
        """Indique que cette classe est abstraite et ne doit pas être instanciée"""
        return True
    """
    Controller de base pour tous les portails publics avec authentification par token.
    Fournit les fonctionnalités communes et permet l'extension par injection de spécificités.
    """

    # =================== CONFIGURATION ABSTRAITE ===================

    @abstractmethod
    def _get_portal_config(self) -> Dict[str, Any]:
        """
        Configuration du portail à définir dans les classes filles.

        Returns:
            Dict contenant :
            - route_base: string - Base de la route (ex: '/documents/upload')
            - template_prefix: string - Préfixe des templates (ex: 'module_name')
            - allowed_file_types: list - Types de fichiers autorisés
            - max_file_size_mb: int - Taille max en MB
        """
        pass

    @abstractmethod
    def _prepare_upload_context(self, partner, **kw) -> Dict[str, Any]:
        """
        Prépare le contexte spécifique pour l'upload.

        Args:
            partner: Partenaire authentifié
            **kw: Paramètres de la requête

        Returns:
            Dict contenant le contexte pour le template
        """
        pass

    @abstractmethod
    def _process_file_upload(self, partner, file_data, context) -> Tuple[bool, Optional[str]]:
        """
        Traite l'upload d'un fichier spécifique.

        Args:
            partner: Partenaire authentifié
            file_data: Données du fichier uploadé
            context: Contexte préparé

        Returns:
            Tuple (success: bool, error_message: Optional[str])
        """
        pass

    # =================== MÉTHODES COMMUNES ===================

    def _validate_token(self, token: str) -> Optional[Any]:
        """Valide le token et retourne le partenaire associé"""
        try:
            decoded_token = urllib.parse.unquote(token)
            partner = request.env['res.partner'].sudo().search([
                '|',
                ('upload_token', '=', decoded_token),
                ('upload_token', '=', token)
            ], limit=1)

            if not partner or not partner.token_expiration or partner.token_expiration < fields.Datetime.now():
                _logger.warning(f"Invalid or expired token: {token}")
                return None

            return partner

        except Exception as e:
            _logger.error(f"Error validating token: {str(e)}")
            return None

    def _validate_file(self, file, config: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Valide un fichier uploadé selon la configuration.

        Args:
            file: Fichier uploadé
            config: Configuration du portail

        Returns:
            Tuple (is_valid: bool, error_message: Optional[str])
        """
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

    def _prepare_file_data(self, file) -> Dict[str, Any]:
        """Prépare les données du fichier pour traitement"""
        file.seek(0)
        content = file.read()

        return {
            'filename': file.filename,
            'content': content,
            'content_b64': base64.b64encode(content),
            'size': len(content)
        }

    def _render_template(self, template_name: str, context: Dict[str, Any]):
        """Rend un template avec le préfixe configuré"""
        config = self._get_portal_config()
        full_template_name = f"{config['template_prefix']}.{template_name}"

        # Ajouter les variables communes
        context.update({
            'datetime': datetime,
            'today': fields.Date.today(),
        })

        return request.render(full_template_name, context)

    # =================== ROUTE PRINCIPALE ===================

    def portal_main_route(self, token: str, **kw):
        """
        Route principale du portail - à mapper dans les classes filles.

        Args:
            token: Token d'authentification
            **kw: Paramètres de la requête
        """
        # Validation du token
        partner = self._validate_token(token)
        if not partner:
            return self._render_template('upload_error', {
                'error_message': "Token invalide ou expiré"
            })

        # Préparation du contexte
        try:
            context = self._prepare_upload_context(partner, **kw)
            context['partner'] = partner
        except Exception as e:
            _logger.error(f"Error preparing context: {str(e)}")
            return self._render_template('upload_error', {
                'error_message': "Erreur lors de la préparation du portail"
            })

        # Traitement POST
        if request.httprequest.method == 'POST':
            return self._handle_post_request(partner, context, **kw)

        # Affichage du formulaire
        return self._render_template('upload_form', context)

    def _handle_post_request(self, partner, context: Dict[str, Any], **kw):
        """Gère les requêtes POST"""
        config = self._get_portal_config()
        errors = []
        success_count = 0

        # Traiter tous les fichiers uploadés
        for field_name in request.httprequest.files:
            file = request.httprequest.files[field_name]

            # Validation du fichier
            is_valid, error_msg = self._validate_file(file, config)
            if not is_valid:
                errors.append(f"{field_name}: {error_msg}")
                continue

            # Préparation des données
            file_data = self._prepare_file_data(file)
            file_data['field_name'] = field_name

            # Traitement spécifique
            try:
                success, error_msg = self._process_file_upload(partner, file_data, context)
                if success:
                    success_count += 1
                else:
                    errors.append(f"{field_name}: {error_msg}")
            except Exception as e:
                _logger.error(f"Error processing file {field_name}: {str(e)}")
                errors.append(f"{field_name}: Erreur inattendue")

        # Résultat
        if success_count > 0 and not errors:
            return self._render_template('upload_success', {
                'partner': partner,
                'success_count': success_count,
                'context': context
            })
        else:
            context['errors'] = errors
            context['partial_success'] = success_count > 0
            return self._render_template('upload_form', context)
