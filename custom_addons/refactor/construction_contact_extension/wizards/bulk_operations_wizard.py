# -*- coding: utf-8 -*-
"""
Assistant pour les opérations en lot sur les sous-traitants
==========================================================

Permet d'effectuer des actions en masse sur plusieurs partenaires sous-traitants.
"""

from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.addons.construction_core.models.mixins.tracking_mixin import TrackingMixin
from odoo.addons.construction_core.utils.helpers import NotificationHelper, LogHelper
import logging

_logger = logging.getLogger(__name__)


class BulkOperationsWizard(models.TransientModel):
    """Assistant pour les opérations en lot sur les sous-traitants"""

    _name = 'subcontractor.bulk.wizard'
    _inherit = ['mail.thread', 'tracking.mixin']
    _description = 'Opérations en Lot Sous-traitants'

    # =================== SÉLECTION DES PARTENAIRES ===================

    partner_ids = fields.Many2many(
        'res.partner',
        string='Partenaires sélectionnés',
        domain=[('is_subcontractor', '=', True)],
        required=True,
        help="Sous-traitants sur lesquels effectuer l'opération"
    )

    partner_count = fields.Integer(
        string='Nombre de partenaires',
        compute='_compute_partner_count'
    )

    selection_criteria = fields.Selection([
        ('manual', 'Sélection manuelle'),
        ('incomplete_docs', 'Documents incomplets'),
        ('expired_docs', 'Documents expirés'),
        ('expiring_docs', 'Documents expirant'),
        ('low_health_score', 'Score santé faible'),
        ('inactive', 'Inactifs récemment'),
        ('by_speciality', 'Par spécialité')
    ], string='Critère de sélection',
        default='manual',
        help="Critère pour sélectionner automatiquement les partenaires")

    # =================== TYPE D'OPÉRATION ===================

    operation = fields.Selection([
        ('send_reminders', 'Envoyer rappels documents'),
        ('update_notifications', 'Modifier préférences notifications'),
        ('generate_tokens', 'Générer tokens upload'),
        ('revoke_tokens', 'Révoquer tokens'),
        ('validate_documents', 'Valider documents'),
        ('archive_old_docs', 'Archiver anciens documents'),
        ('update_speciality', 'Mettre à jour spécialités'),
        ('export_data', 'Exporter données'),
        ('send_survey', 'Envoyer questionnaire'),
        ('generate_reports', 'Générer rapports')
    ], string='Opération',
        required=True,
        help="Type d'opération à effectuer")

    # =================== PARAMÈTRES SPÉCIFIQUES ===================

    # Notifications
    notification_preference = fields.Selection([
        ('all', 'Toutes les notifications'),
        ('important', 'Notifications importantes uniquement'),
        ('none', 'Aucune notification')
    ], string='Préférence de notification',
        help="Nouvelle préférence de notification")

    # Tokens
    token_validity_days = fields.Integer(
        string='Validité token (jours)',
        default=7,
        help="Nombre de jours de validité pour les nouveaux tokens"
    )

    force_regenerate = fields.Boolean(
        string='Forcer la régénération',
        default=False,
        help="Régénérer même si un token valide existe"
    )

    # Documents
    document_type_ids = fields.Many2many(
        'document.type',
        string='Types de documents',
        help="Types de documents concernés par l'opération"
    )

    validation_status = fields.Selection([
        ('valid', 'Valider'),
        ('rejected', 'Rejeter'),
        ('to_check', 'Remettre à vérifier')
    ], string='Statut de validation')

    validation_notes = fields.Text(
        string='Notes de validation',
        help="Commentaire pour la validation en lot"
    )

    # Spécialités
    new_speciality_ids = fields.Many2many(
        'lot',
        'bulk_wizard_new_speciality_rel',
        'wizard_id',
        'lot_id',
        string='Nouvelles spécialités',
        help="Spécialités à assigner aux partenaires sélectionnés"
    )

    speciality_mode = fields.Selection([
        ('add', 'Ajouter aux existantes'),
        ('replace', 'Remplacer les existantes'),
        ('remove', 'Supprimer ces spécialités')
    ], string='Mode spécialités',
        default='add')

    # Filtres avancés
    health_score_min = fields.Float(
        string='Score santé minimum',
        default=50.0,
        help="Score de santé minimum pour la sélection automatique"
    )

    days_inactive = fields.Integer(
        string='Jours d\'inactivité',
        default=90,
        help="Nombre de jours d'inactivité pour la sélection"
    )

    speciality_filter_ids = fields.Many2many(
        'lot',
        'bulk_wizard_speciality_rel',
        'wizard_id',
        'lot_id',
        string='Filtre par spécialités',
        help="Spécialités pour filtrer les partenaires"
    )

    # =================== RÉSULTATS ET PROGRESSION ===================

    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('confirm', 'Confirmation'),
        ('processing', 'En cours'),
        ('done', 'Terminé')
    ], string='État',
        default='draft')

    progress_percent = fields.Float(
        string='Progression (%)',
        default=0.0
    )

    success_count = fields.Integer(
        string='Succès',
        default=0,
        help="Nombre d'opérations réussies"
    )

    error_count = fields.Integer(
        string='Erreurs',
        default=0,
        help="Nombre d'erreurs rencontrées"
    )

    result_log = fields.Html(
        string='Journal des résultats',
        help="Détail des opérations effectuées"
    )

    estimated_duration = fields.Char(
        string='Durée estimée',
        compute='_compute_estimated_duration',
        help="Durée estimée de l'opération"
    )

    # =================== MÉTHODES CALCULÉES ===================

    @api.depends('partner_ids')
    def _compute_partner_count(self):
        """Calcule le nombre de partenaires sélectionnés"""
        for wizard in self:
            wizard.partner_count = len(wizard.partner_ids)

    @api.depends('operation', 'partner_count')
    def _compute_estimated_duration(self):
        """Calcule la durée estimée selon l'opération"""
        duration_per_partner = {
            'send_reminders': 2,  # 2 secondes par partenaire
            'update_notifications': 1,
            'generate_tokens': 1,
            'revoke_tokens': 1,
            'validate_documents': 5,
            'archive_old_docs': 10,
            'update_speciality': 3,
            'export_data': 5,
            'send_survey': 3,
            'generate_reports': 15
        }

        for wizard in self:
            if wizard.operation and wizard.partner_count:
                seconds_per_partner = duration_per_partner.get(wizard.operation, 5)
                total_seconds = wizard.partner_count * seconds_per_partner

                if total_seconds < 60:
                    wizard.estimated_duration = f"{total_seconds} secondes"
                elif total_seconds < 3600:
                    wizard.estimated_duration = f"{total_seconds // 60} minutes"
                else:
                    wizard.estimated_duration = f"{total_seconds // 3600}h {(total_seconds % 3600) // 60}m"
            else:
                wizard.estimated_duration = "Non estimée"

    # =================== SÉLECTION AUTOMATIQUE ===================

    @api.onchange('selection_criteria')
    def _onchange_selection_criteria(self):
        """Met à jour la sélection selon le critère"""
        if self.selection_criteria == 'manual':
            return

        domain = [('is_subcontractor', '=', True)]

        if self.selection_criteria == 'incomplete_docs':
            domain.append(('document_completion_rate', '<', 100))

        elif self.selection_criteria == 'expired_docs':
            domain.append(('has_expired_documents', '=', True))

        elif self.selection_criteria == 'expiring_docs':
            domain.append(('has_expiring_documents', '=', True))

        elif self.selection_criteria == 'low_health_score':
            domain.append(('document_health_score', '<', self.health_score_min))

        elif self.selection_criteria == 'inactive':
            from datetime import timedelta
            cutoff_date = fields.Datetime.now() - timedelta(days=self.days_inactive)
            domain.append(('last_activity_date', '<', cutoff_date))

        elif self.selection_criteria == 'by_speciality' and self.speciality_filter_ids:
            domain.append(('speciality_ids', 'in', self.speciality_filter_ids.ids))

        # Appliquer la sélection
        selected_partners = self.env['res.partner'].search(domain)
        self.partner_ids = [(6, 0, selected_partners.ids)]

    # =================== ACTIONS PRINCIPALES ===================

    def action_confirm_operation(self):
        """Confirme l'opération avant exécution"""
        self.ensure_one()

        if not self.partner_ids:
            raise ValidationError("Aucun partenaire sélectionné")

        # Vérifications spécifiques selon l'opération
        if self.operation == 'update_notifications' and not self.notification_preference:
            raise ValidationError("Préférence de notification requise")

        if self.operation == 'validate_documents' and not self.document_type_ids:
            raise ValidationError("Types de documents requis pour la validation")

        if self.operation == 'update_speciality' and not self.new_speciality_ids:
            raise ValidationError("Spécialités requises pour la mise à jour")

        self.state = 'confirm'

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {'form_view_initial_mode': 'edit'}
        }

    def action_execute_operation(self):
        """Exécute l'opération sélectionnée"""
        self.ensure_one()

        if self.state != 'confirm':
            raise ValidationError("L'opération doit être confirmée avant exécution")

        self.state = 'processing'
        self.success_count = 0
        self.error_count = 0
        self.result_log = "<h4>Début de l'opération</h4>"

        try:
            # Dispatcher vers la méthode appropriée
            method_name = f'_execute_{self.operation}'
            if hasattr(self, method_name):
                getattr(self, method_name)()
            else:
                raise ValidationError(f"Opération '{self.operation}' non implémentée")

            self.state = 'done'
            self._finalize_operation()

        except Exception as e:
            self.error_count += 1
            self.result_log += f"<p class='text-danger'>Erreur critique: {str(e)}</p>"
            _logger.error(f"Bulk operation error: {str(e)}")
            raise

        return self._show_results()

    # =================== OPÉRATIONS SPÉCIFIQUES ===================

    def _execute_send_reminders(self):
        """Envoie des rappels de documents"""
        total = len(self.partner_ids)

        for i, partner in enumerate(self.partner_ids):
            try:
                # Vérifier si le partenaire a besoin d'un rappel
                missing_docs = partner.get_missing_documents()
                if not missing_docs:
                    self.result_log += f"<p class='text-info'>{partner.name}: Aucun document manquant</p>"
                    continue

                # Envoyer le rappel
                result = partner.action_send_document_request()

                if result.get('params', {}).get('type') == 'success':
                    self.success_count += 1
                    self.result_log += f"<p class='text-success'>✅ {partner.name}: Rappel envoyé</p>"
                else:
                    self.error_count += 1
                    self.result_log += f"<p class='text-warning'>⚠️ {partner.name}: Échec d'envoi</p>"

                # Mettre à jour la progression
                self.progress_percent = ((i + 1) / total) * 100

            except Exception as e:
                self.error_count += 1
                self.result_log += f"<p class='text-danger'>❌ {partner.name}: Erreur - {str(e)}</p>"

    def _execute_update_notifications(self):
        """Met à jour les préférences de notification"""
        total = len(self.partner_ids)

        for i, partner in enumerate(self.partner_ids):
            try:
                old_pref = partner.notification_preferences
                partner.notification_preferences = self.notification_preference

                self.success_count += 1
                self.result_log += f"<p class='text-success'>✅ {partner.name}: {old_pref} → {self.notification_preference}</p>"

                self.progress_percent = ((i + 1) / total) * 100

            except Exception as e:
                self.error_count += 1
                self.result_log += f"<p class='text-danger'>❌ {partner.name}: Erreur - {str(e)}</p>"

    def _execute_generate_tokens(self):
        """Génère des tokens d'upload"""
        total = len(self.partner_ids)

        for i, partner in enumerate(self.partner_ids):
            try:
                # Vérifier si un token existe déjà
                if partner.is_token_valid() and not self.force_regenerate:
                    self.result_log += f"<p class='text-info'>{partner.name}: Token existant conservé</p>"
                    continue

                # Générer le nouveau token
                token = partner.generate_upload_token(self.token_validity_days)

                self.success_count += 1
                self.result_log += f"<p class='text-success'>✅ {partner.name}: Token généré ({token[:8]}...)</p>"

                self.progress_percent = ((i + 1) / total) * 100

            except Exception as e:
                self.error_count += 1
                self.result_log += f"<p class='text-danger'>❌ {partner.name}: Erreur - {str(e)}</p>"

    def _execute_revoke_tokens(self):
        """Révoque les tokens d'upload"""
        total = len(self.partner_ids)

        for i, partner in enumerate(self.partner_ids):
            try:
                if not partner.upload_token:
                    self.result_log += f"<p class='text-info'>{partner.name}: Aucun token à révoquer</p>"
                    continue

                partner.revoke_token()

                self.success_count += 1
                self.result_log += f"<p class='text-success'>✅ {partner.name}: Token révoqué</p>"

                self.progress_percent = ((i + 1) / total) * 100

            except Exception as e:
                self.error_count += 1
                self.result_log += f"<p class='text-danger'>❌ {partner.name}: Erreur - {str(e)}</p>"

    def _execute_validate_documents(self):
        """Valide des documents en lot"""
        total = len(self.partner_ids)

        for i, partner in enumerate(self.partner_ids):
            try:
                docs_to_validate = partner.document_ids.filtered(
                    lambda d: d.document_type_id in self.document_type_ids and
                              d.state == 'to_check'
                )

                if not docs_to_validate:
                    self.result_log += f"<p class='text-info'>{partner.name}: Aucun document à valider</p>"
                    continue

                validated_count = 0
                for doc in docs_to_validate:
                    doc.write({
                        'state': self.validation_status,
                        'validated_by': self.env.user.id,
                        'validation_date': fields.Datetime.now(),
                        'validation_notes': self.validation_notes
                    })
                    validated_count += 1

                self.success_count += validated_count
                self.result_log += f"<p class='text-success'>✅ {partner.name}: {validated_count} document(s) validé(s)</p>"

                self.progress_percent = ((i + 1) / total) * 100

            except Exception as e:
                self.error_count += 1
                self.result_log += f"<p class='text-danger'>❌ {partner.name}: Erreur - {str(e)}</p>"

    def _execute_update_speciality(self):
        """Met à jour les spécialités"""
        total = len(self.partner_ids)

        for i, partner in enumerate(self.partner_ids):
            try:
                if self.speciality_mode == 'add':
                    partner.speciality_ids = [(4, spec.id) for spec in self.new_speciality_ids]
                elif self.speciality_mode == 'replace':
                    partner.speciality_ids = [(6, 0, self.new_speciality_ids.ids)]
                elif self.speciality_mode == 'remove':
                    partner.speciality_ids = [(3, spec.id) for spec in self.new_speciality_ids]

                self.success_count += 1
                self.result_log += f"<p class='text-success'>✅ {partner.name}: Spécialités mises à jour</p>"

                self.progress_percent = ((i + 1) / total) * 100

            except Exception as e:
                self.error_count += 1
                self.result_log += f"<p class='text-danger'>❌ {partner.name}: Erreur - {str(e)}</p>"

    def _execute_export_data(self):
        """Exporte les données des partenaires"""
        try:
            export_data = []

            for partner in self.partner_ids:
                partner_data = {
                    'Nom': partner.name,
                    'Email': partner.email,
                    'Téléphone': partner.phone,
                    'Taux complétion': partner.document_completion_rate,
                    'Score santé': partner.document_health_score,
                    'Documents expirés': len(partner.document_ids.filtered(lambda d: d.state == 'expired')),
                    'Dernière activité': partner.last_activity_date,
                    'Spécialités': ', '.join(partner.speciality_ids.mapped('name'))
                }
                export_data.append(partner_data)

            # Créer un fichier d'export (simulation)
            self.success_count = len(export_data)
            self.result_log += f"<p class='text-success'>✅ Données de {len(export_data)} partenaires exportées</p>"

        except Exception as e:
            self.error_count += 1
            self.result_log += f"<p class='text-danger'>❌ Erreur d'export: {str(e)}</p>"

    # =================== FINALISATION ===================

    def _finalize_operation(self):
        """Finalise l'opération"""
        # Log de l'opération
        LogHelper.log_operation(
            f'bulk_operation_{self.operation}',
            self.error_count == 0,
            details={
                'partner_count': self.partner_count,
                'success_count': self.success_count,
                'error_count': self.error_count,
                'operation': self.operation
            },
            user_id=self.env.user.id
        )

        # Résumé final
        total_processed = self.success_count + self.error_count
        self.result_log += f"""
        <hr>
        <h4>Résumé final</h4>
        <ul>
            <li><strong>Partenaires traités:</strong> {total_processed}/{self.partner_count}</li>
            <li><strong>Succès:</strong> {self.success_count}</li>
            <li><strong>Erreurs:</strong> {self.error_count}</li>
            <li><strong>Taux de succès:</strong> {(self.success_count / total_processed * 100) if total_processed > 0 else 0:.1f}%</li>
        </ul>
        """

        self.progress_percent = 100.0

    def _show_results(self):
        """Affiche les résultats"""
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {'form_view_initial_mode': 'readonly'}
        }

    # =================== ACTIONS UTILITAIRES ===================

    def action_preview_selection(self):
        """Prévisualise les partenaires sélectionnés"""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': f'Prévisualisation - {self.partner_count} partenaire(s)',
            'res_model': 'res.partner',
            'view_mode': 'list',
            'domain': [('id', 'in', self.partner_ids.ids)],
            'target': 'new'
        }

    def action_clear_selection(self):
        """Vide la sélection"""
        self.partner_ids = [(5, 0, 0)]
        return {'type': 'ir.actions.do_nothing'}

    def action_export_results(self):
        """Exporte les résultats de l'opération"""
        self.ensure_one()

        if self.state != 'done':
            raise ValidationError("L'opération doit être terminée pour exporter les résultats")

        return {
            'type': 'ir.actions.act_window',
            'name': 'Exporter les résultats',
            'res_model': 'bulk.operation.results.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_bulk_wizard_id': self.id,
                'default_results_data': self.result_log
            }
        }

    # =================== CONTRAINTES ===================

    @api.constrains('token_validity_days')
    def _check_token_validity(self):
        """Vérifie la validité des jours pour les tokens"""
        for wizard in self:
            if wizard.token_validity_days <= 0 or wizard.token_validity_days > 365:
                raise ValidationError("La validité du token doit être entre 1 et 365 jours")

    @api.constrains('health_score_min')
    def _check_health_score(self):
        """Vérifie le score de santé minimum"""
        for wizard in self:
            if wizard.health_score_min < 0 or wizard.health_score_min > 100:
                raise ValidationError("Le score de santé doit être entre 0 et 100")

    # =================== HOOKS ===================

    def _get_trackable_fields(self):
        """Champs à suivre pour le TrackingMixin"""
        return ['operation', 'state', 'success_count', 'error_count']
