# models/mixins/tracking_mixin.py
from odoo import models, fields, api
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)


class TrackingMixin(models.AbstractModel):
    """
    Mixin pour le suivi automatique des modifications et de l'activité.
    Fournit des fonctionnalités de traçabilité pour tous les modèles.
    """
    _name = 'tracking.mixin'
    _description = 'Tracking and Activity Mixin'

    # =================== CHAMPS DE SUIVI ===================

    created_date = fields.Datetime(
        string='Date de création',
        default=fields.Datetime.now,
        readonly=True,
        help="Date de création automatique de l'enregistrement"
    )

    created_by = fields.Many2one(
        'res.users',
        string='Créé par',
        default=lambda self: self.env.user,
        readonly=True,
        help="Utilisateur ayant créé l'enregistrement"
    )

    last_modified_date = fields.Datetime(
        string='Dernière modification',
        readonly=True,
        help="Date de la dernière modification"
    )

    last_modified_by = fields.Many2one(
        'res.users',
        string='Modifié par',
        readonly=True,
        help="Utilisateur ayant effectué la dernière modification"
    )

    last_activity_date = fields.Datetime(
        string='Dernière activité',
        compute='_compute_last_activity',
        store=True,
        help="Date de la dernière activité (modification, message, etc.)"
    )

    activity_count = fields.Integer(
        string='Nombre d\'activités',
        compute='_compute_activity_stats',
        help="Nombre total d'activités sur cet enregistrement"
    )

    days_since_creation = fields.Integer(
        string='Jours depuis création',
        compute='_compute_time_stats',
        help="Nombre de jours depuis la création"
    )

    days_since_last_activity = fields.Integer(
        string='Jours depuis dernière activité',
        compute='_compute_time_stats',
        help="Nombre de jours depuis la dernière activité"
    )

    # =================== MÉTHODES DE CALCUL ===================

    @api.depends('message_ids.date', 'write_date')
    def _compute_last_activity(self):
        """Calcule la date de la dernière activité"""
        for record in self:
            dates = []

            # Date de dernière modification
            if record.write_date:
                dates.append(record.write_date)

            # Date du dernier message (si le modèle hérite de mail.thread)
            if hasattr(record, 'message_ids') and record.message_ids:
                last_message_date = max(record.message_ids.mapped('date'))
                dates.append(last_message_date)

            record.last_activity_date = max(dates) if dates else record.created_date

    @api.depends('message_ids')
    def _compute_activity_stats(self):
        """Calcule les statistiques d'activité"""
        for record in self:
            if hasattr(record, 'message_ids'):
                record.activity_count = len(record.message_ids)
            else:
                record.activity_count = 0

    @api.depends('created_date', 'last_activity_date')
    def _compute_time_stats(self):
        """Calcule les statistiques temporelles"""
        for record in self:
            now = datetime.now()

            # Jours depuis création
            if record.created_date:
                record.days_since_creation = (now - record.created_date).days
            else:
                record.days_since_creation = 0

            # Jours depuis dernière activité
            if record.last_activity_date:
                record.days_since_last_activity = (now - record.last_activity_date).days
            else:
                record.days_since_last_activity = record.days_since_creation

    # =================== MÉTHODES DE SUIVI ===================

    @api.model_create_multi
    def create(self, vals_list):
        """Override create pour enregistrer les informations de création"""
        records = super().create(vals_list)
        for record in records:
            record._log_creation()
        return records

    def write(self, vals):
        """Override write pour enregistrer les modifications"""
        # Sauvegarder les valeurs avant modification pour comparaison
        old_values = {}
        if self._should_track_changes():
            old_values = {record.id: self._get_trackable_values(record) for record in self}

        # Mettre à jour les champs de modification
        vals.update({
            'last_modified_date': fields.Datetime.now(),
            'last_modified_by': self.env.user.id,
        })

        result = super().write(vals)

        # Logger les changements si nécessaire
        if self._should_track_changes():
            for record in self:
                record._log_changes(old_values.get(record.id, {}), vals)

        return result

    def _log_creation(self):
        """Log la création de l'enregistrement"""
        if hasattr(self, 'message_post'):
            self.message_post(
                body=f"📝 Enregistrement créé par {self.env.user.name}",
                message_type='notification'
            )

    def _log_changes(self, old_values, new_values):
        """Log les changements importants"""
        if not hasattr(self, 'message_post'):
            return

        changes = []
        trackable_fields = self._get_trackable_fields()

        for field_name, new_value in new_values.items():
            if field_name in trackable_fields:
                old_value = old_values.get(field_name)
                if old_value != new_value:
                    field_label = self._fields[field_name].string
                    changes.append(f"{field_label}: {old_value} → {new_value}")

        if changes:
            body = "📋 <strong>Modifications:</strong><br/>" + "<br/>".join(changes)
            self.message_post(
                body=body,
                message_type='notification'
            )

    def _should_track_changes(self):
        """Détermine si les changements doivent être suivis"""
        # Override dans les modèles filles si nécessaire
        return hasattr(self, 'message_post')

    def _get_trackable_fields(self):
        """Retourne la liste des champs à suivre"""
        # Override dans les modèles filles pour définir les champs à suivre
        return ['name', 'state', 'active']

    def _get_trackable_values(self, record):
        """Récupère les valeurs des champs suivis"""
        values = {}
        for field_name in self._get_trackable_fields():
            if hasattr(record, field_name):
                values[field_name] = getattr(record, field_name)
        return values

    # =================== ACTIONS PUBLIQUES ===================

    def action_view_activity_history(self):
        """Affiche l'historique d'activité"""
        self.ensure_one()

        if not hasattr(self, 'message_ids'):
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': 'Historique non disponible pour ce type d\'enregistrement',
                    'type': 'warning'
                }
            }

        return {
            'name': f'Historique - {self.display_name}',
            'type': 'ir.actions.act_window',
            'res_model': 'mail.message',
            'view_mode': 'list,form',
            'domain': [('res_id', '=', self.id), ('model', '=', self._name)],
            'context': {'default_model': self._name, 'default_res_id': self.id}
        }
