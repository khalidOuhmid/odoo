# models/mixins/state_manager_mixin.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class StateManagerMixin(models.AbstractModel):
    """
    Mixin pour la gestion avancée des états avec validation des transitions.
    Fournit un système flexible de gestion d'états pour tous les modèles.
    """
    _name = 'state.manager.mixin'
    _description = 'State Management Mixin'

    # =================== CHAMPS D'ÉTAT ===================

    state = fields.Selection(
        selection=[],  # À définir dans les modèles filles
        string='État',
        default='draft',
        tracking=True,
        help="État actuel de l'enregistrement"
    )

    previous_state = fields.Selection(
        selection=[],  # Même sélection que state
        string='État précédent',
        readonly=True,
        help="État précédent avant la dernière transition"
    )

    state_changed_date = fields.Datetime(
        string='Changement d\'état',
        readonly=True,
        help="Date du dernier changement d'état"
    )

    state_changed_by = fields.Many2one(
        'res.users',
        string='État changé par',
        readonly=True,
        help="Utilisateur ayant effectué le dernier changement d'état"
    )

    can_be_cancelled = fields.Boolean(
        string='Peut être annulé',
        compute='_compute_transition_flags',
        help="True si l'enregistrement peut être annulé"
    )

    can_go_back = fields.Boolean(
        string='Peut revenir en arrière',
        compute='_compute_transition_flags',
        help="True si on peut revenir à l'état précédent"
    )

    # =================== MÉTHODES ABSTRAITES ===================

    def _get_state_config(self):
        """
        Configuration des états à définir dans les modèles filles.

        Returns:
            dict: Configuration des états avec transitions autorisées

        Example:
            {
                'draft': {
                    'label': 'Brouillon',
                    'next_states': ['confirmed', 'cancelled'],
                    'requirements': []
                },
                'confirmed': {
                    'label': 'Confirmé',
                    'next_states': ['progress', 'cancelled'],
                    'requirements': ['_check_required_fields']
                }
            }
        """
        return {}

    def _get_state_requirements(self, new_state):
        """
        Méthodes de validation à exécuter pour un état donné.

        Args:
            new_state (str): Nouvel état

        Returns:
            list: Liste des méthodes de validation
        """
        config = self._get_state_config()
        return config.get(new_state, {}).get('requirements', [])

    # =================== MÉTHODES DE CALCUL ===================

    @api.depends('state', 'previous_state')
    def _compute_transition_flags(self):
        """Calcule les flags de transition possibles"""
        for record in self:
            config = record._get_state_config()
            current_config = config.get(record.state, {})

            # Peut être annulé si 'cancelled' est dans les états suivants possibles
            next_states = current_config.get('next_states', [])
            record.can_be_cancelled = 'cancelled' in next_states

            # Peut revenir en arrière si état précédent défini et transition autorisée
            record.can_go_back = (
                    record.previous_state and
                    record.previous_state in next_states
            )

    # =================== VALIDATION DES TRANSITIONS ===================

    def _validate_state_transition(self, new_state):
        """
        Valide qu'une transition d'état est autorisée.

        Args:
            new_state (str): Nouvel état souhaité

        Returns:
            dict: Résultat de la validation
        """
        self.ensure_one()

        config = self._get_state_config()
        current_config = config.get(self.state, {})

        # Vérifier que la transition est autorisée
        allowed_next_states = current_config.get('next_states', [])
        if new_state not in allowed_next_states:
            return {
                'valid': False,
                'message': f"Transition de '{self.state}' vers '{new_state}' non autorisée"
            }

        # Exécuter les validations spécifiques
        requirements = self._get_state_requirements(new_state)
        for requirement in requirements:
            if hasattr(self, requirement):
                validation_method = getattr(self, requirement)
                result = validation_method()
                if not result.get('valid', True):
                    return result

        return {'valid': True, 'message': 'Transition autorisée'}

    # =================== ACTIONS D'ÉTAT ===================

    def action_change_state(self, new_state, force=False):
        """
        Change l'état de l'enregistrement avec validation.

        Args:
            new_state (str): Nouvel état
            force (bool): Force le changement sans validation

        Returns:
            dict: Résultat de l'action
        """
        self.ensure_one()

        if new_state == self.state:
            return self._create_info_response("L'enregistrement est déjà dans cet état")

        # Validation (sauf si forcé)
        if not force:
            validation = self._validate_state_transition(new_state)
            if not validation['valid']:
                return self._create_error_response(validation['message'])

        # Sauvegarder l'état précédent
        old_state = self.state

        # Effectuer le changement
        try:
            self.write({
                'previous_state': old_state,
                'state': new_state,
                'state_changed_date': fields.Datetime.now(),
                'state_changed_by': self.env.user.id
            })

            # Exécuter les actions post-transition
            self._post_state_change_actions(old_state, new_state)

            # Message de succès
            config = self._get_state_config()
            new_state_label = config.get(new_state, {}).get('label', new_state)

            return self._create_success_response(
                f"État changé vers '{new_state_label}'"
            )

        except Exception as e:
            _logger.error(f"Error changing state for {self._name} {self.id}: {str(e)}")
            return self._create_error_response("Erreur lors du changement d'état")

    def action_cancel(self):
        """Annule l'enregistrement"""
        return self.action_change_state('cancelled')

    def action_go_back(self):
        """Revient à l'état précédent"""
        if not self.previous_state:
            return self._create_error_response("Aucun état précédent disponible")

        return self.action_change_state(self.previous_state)

    def action_reset_to_draft(self):
        """Remet en brouillon (avec confirmation)"""
        return self.action_change_state('draft', force=True)

    # =================== HOOKS POST-TRANSITION ===================

    def _post_state_change_actions(self, old_state, new_state):
        """
        Actions à exécuter après un changement d'état.
        À override dans les modèles filles si nécessaire.

        Args:
            old_state (str): Ancien état
            new_state (str): Nouvel état
        """
        # Log du changement
        if hasattr(self, 'message_post'):
            config = self._get_state_config()
            old_label = config.get(old_state, {}).get('label', old_state)
            new_label = config.get(new_state, {}).get('label', new_state)

            self.message_post(
                body=f"🔄 État changé: {old_label} → {new_label}",
                message_type='notification'
            )

    # =================== MÉTHODES UTILITAIRES ===================

    def get_available_transitions(self):
        """
        Retourne les transitions disponibles depuis l'état actuel.

        Returns:
            list: Liste des états accessibles
        """
        self.ensure_one()
        config = self._get_state_config()
        current_config = config.get(self.state, {})
        return current_config.get('next_states', [])

    def get_state_history(self):
        """
        Retourne l'historique des changements d'état.

        Returns:
            list: Historique des changements
        """
        self.ensure_one()

        if not hasattr(self, 'message_ids'):
            return []

        # Rechercher les messages de changement d'état
        state_messages = self.message_ids.filtered(
            lambda m: '🔄 État changé:' in (m.body or '')
        )

        return [{
            'date': msg.date,
            'user': msg.author_id.name,
            'change': msg.body
        } for msg in state_messages.sorted('date', reverse=True)]

    def _create_success_response(self, message):
        """Crée une réponse de succès"""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': message,
                'type': 'success'
            }
        }

    def _create_error_response(self, message):
        """Crée une réponse d'erreur"""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': message,
                'type': 'danger',
                'sticky': True
            }
        }

    def _create_info_response(self, message):
        """Crée une réponse d'information"""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': message,
                'type': 'info'
            }
        }

    # =================== CONTRAINTES ===================

    @api.constrains('state')
    def _check_state_validity(self):
        """Vérifie que l'état est valide"""
        for record in self:
            config = record._get_state_config()
            if record.state and record.state not in config:
                raise ValidationError(f"État '{record.state}' non valide pour ce type d'enregistrement")
