# models/services/base_service.py
from odoo import models, api
import logging

_logger = logging.getLogger(__name__)


class BaseService:
    """
    Classe de base pour tous les services métier.
    Fournit des méthodes communes et une interface standardisée.
    """

    def __init__(self, env):
        """
        Initialise le service avec l'environnement Odoo.

        Args:
            env: Environnement Odoo
        """
        self.env = env
        self.user = env.user
        self.company = env.company

    # =================== GESTION DES RÉPONSES ===================

    def _success_response(self, message, title="Succès", data=None):
        """Crée une réponse de succès standardisée"""
        response = {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': message,
                'type': 'success',
                'sticky': False
            }
        }

        if data:
            response['data'] = data

        return response

    def _error_response(self, message, title="Erreur", exception=None):
        """Crée une réponse d'erreur standardisée"""
        if exception:
            _logger.error(f"Service error: {message} - Exception: {str(exception)}")

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': message,
                'type': 'danger',
                'sticky': True
            }
        }

    def _warning_response(self, message, title="Attention"):
        """Crée une réponse d'avertissement standardisée"""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': message,
                'type': 'warning',
                'sticky': False
            }
        }

    def _info_response(self, message, title="Information"):
        """Crée une réponse d'information standardisée"""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': message,
                'type': 'info',
                'sticky': False
            }
        }

    # =================== ACTIONS ODOO ===================

    def _action_open_record(self, model, record_id, view_mode='form'):
        """Ouvre un enregistrement en vue formulaire"""
        return {
            'type': 'ir.actions.act_window',
            'res_model': model,
            'res_id': record_id,
            'view_mode': view_mode,
            'target': 'current'
        }

    def _action_open_list(self, model, domain=None, context=None, name=None):
        """Ouvre une vue liste avec domaine"""
        return {
            'type': 'ir.actions.act_window',
            'name': name or f'Liste {model}',
            'res_model': model,
            'view_mode': 'list,form',
            'domain': domain or [],
            'context': context or {},
            'target': 'current'
        }

    def _action_open_wizard(self, wizard_model, context=None, name=None):
        """Ouvre un wizard"""
        return {
            'type': 'ir.actions.act_window',
            'name': name or 'Assistant',
            'res_model': wizard_model,
            'view_mode': 'form',
            'target': 'new',
            'context': context or {}
        }

    # =================== UTILITAIRES ===================

    def _check_access_rights(self, model, operation='read'):
        """Vérifie les droits d'accès sur un modèle"""
        try:
            self.env[model].check_access_rights(operation)
            return True
        except Exception as e:
            _logger.warning(f"Access denied for {model}.{operation}: {str(e)}")
            return False

    def _safe_execute(self, operation, *args, **kwargs):
        """Exécute une opération de manière sécurisée"""
        try:
            return operation(*args, **kwargs)
        except Exception as e:
            _logger.error(f"Error in safe_execute: {str(e)}")
            return None

    def _validate_required_fields(self, record, required_fields):
        """Valide que tous les champs requis sont remplis"""
        missing_fields = []

        for field in required_fields:
            if not getattr(record, field, None):
                missing_fields.append(field)

        return missing_fields

    def _get_model_label(self, model_name):
        """Récupère le label d'un modèle"""
        try:
            model = self.env[model_name]
            return model._description
        except:
            return model_name
