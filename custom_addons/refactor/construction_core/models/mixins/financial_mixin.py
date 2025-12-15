# models/mixins/financial_mixin.py
from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class FinancialMixin(models.AbstractModel):
    """
    Mixin pour la gestion financière avec calculs automatiques.
    Fournit des fonctionnalités financières standardisées.
    """
    _name = 'financial.mixin'
    _description = 'Financial Management Mixin'

    # =================== CHAMPS FINANCIERS DE BASE ===================

    currency_id = fields.Many2one(
        'res.currency',
        string='Devise',
        default=lambda self: self.env.company.currency_id,
        required=True,
        help="Devise utilisée pour les montants"
    )

    amount_untaxed = fields.Monetary(
        string='Montant HT',
        currency_field='currency_id',
        tracking=True,
        help="Montant hors taxes"
    )

    amount_tax = fields.Monetary(
        string='Montant des taxes',
        currency_field='currency_id',
        compute='_compute_amounts',
        store=True,
        help="Montant total des taxes"
    )

    amount_total = fields.Monetary(
        string='Montant TTC',
        currency_field='currency_id',
        compute='_compute_amounts',
        store=True,
        help="Montant toutes taxes comprises"
    )

    # =================== CHAMPS DE COÛT ===================

    cost_estimated = fields.Monetary(
        string='Coût estimé',
        currency_field='currency_id',
        help="Coût estimé du projet/lot"
    )

    cost_actual = fields.Monetary(
        string='Coût réel',
        currency_field='currency_id',
        compute='_compute_cost_actual',
        store=True,
        help="Coût réel basé sur les dépenses"
    )

    cost_variance = fields.Monetary(
        string='Écart de coût',
        currency_field='currency_id',
        compute='_compute_financial_indicators',
        store=True,
        help="Différence entre coût estimé et réel"
    )

    cost_variance_percent = fields.Float(
        string='Écart de coût (%)',
        compute='_compute_financial_indicators',
        store=True,
        help="Pourcentage d'écart de coût"
    )

    # =================== CHAMPS DE MARGE ===================

    margin_amount = fields.Monetary(
        string='Marge',
        currency_field='currency_id',
        compute='_compute_financial_indicators',
        store=True,
        help="Marge en valeur absolue"
    )

    margin_percent = fields.Float(
        string='Marge (%)',
        compute='_compute_financial_indicators',
        store=True,
        help="Pourcentage de marge"
    )

    margin_target_percent = fields.Float(
        string='Marge cible (%)',
        default=10.0,
        help="Objectif de marge en pourcentage"
    )

    # =================== INDICATEURS FINANCIERS ===================

    profitability_index = fields.Float(
        string='Indice de rentabilité',
        compute='_compute_financial_indicators',
        store=True,
        help="Ratio revenus / coûts"
    )

    roi_percent = fields.Float(
        string='ROI (%)',
        compute='_compute_financial_indicators',
        store=True,
        help="Retour sur investissement"
    )

    financial_health = fields.Selection([
        ('excellent', 'Excellent'),
        ('good', 'Bon'),
        ('average', 'Moyen'),
        ('poor', 'Mauvais'),
        ('critical', 'Critique')
    ], string='Santé financière',
        compute='_compute_financial_health',
        store=True,
        help="Évaluation de la santé financière")

    # =================== CHAMPS DE PAIEMENT ===================

    payment_terms = fields.Selection([
        ('immediate', 'Immédiat'),
        ('30_days', '30 jours'),
        ('60_days', '60 jours'),
        ('90_days', '90 jours'),
        ('custom', 'Personnalisé')
    ], string='Conditions de paiement', default='30_days')

    payment_received = fields.Monetary(
        string='Paiements reçus',
        currency_field='currency_id',
        compute='_compute_payment_status',
        store=True,
        help="Montant total des paiements reçus"
    )

    payment_pending = fields.Monetary(
        string='Paiements en attente',
        currency_field='currency_id',
        compute='_compute_payment_status',
        store=True,
        help="Montant en attente de paiement"
    )

    payment_completion_rate = fields.Float(
        string='Taux de paiement (%)',
        compute='_compute_payment_status',
        store=True,
        help="Pourcentage de paiements reçus"
    )

    # =================== MÉTHODES DE CALCUL ===================

    @api.depends('amount_untaxed')
    def _compute_amounts(self):
        """Calcule les montants avec taxes"""
        for record in self:
            # Si le modèle a des lignes avec taxes, les utiliser
            if hasattr(record, '_get_tax_amount'):
                record.amount_tax = record._get_tax_amount()
            else:
                # Sinon, calculer un taux de TVA par défaut (à override si nécessaire)
                tax_rate = record._get_default_tax_rate()
                record.amount_tax = record.amount_untaxed * (tax_rate / 100)

            record.amount_total = record.amount_untaxed + record.amount_tax

    @api.depends()  # Dépendances à définir dans les modèles filles
    def _compute_cost_actual(self):
        """Calcule le coût réel - à override dans les modèles filles"""
        for record in self:
            record.cost_actual = record._calculate_actual_cost()

    @api.depends('amount_total', 'cost_actual', 'cost_estimated', 'margin_target_percent')
    def _compute_financial_indicators(self):
        """Calcule tous les indicateurs financiers"""
        for record in self:
            # Écart de coût
            if record.cost_estimated and record.cost_actual:
                record.cost_variance = record.cost_actual - record.cost_estimated
                record.cost_variance_percent = (
                    (record.cost_variance / record.cost_estimated) * 100
                    if record.cost_estimated else 0
                )
            else:
                record.cost_variance = 0
                record.cost_variance_percent = 0

            # Marge
            cost_for_margin = record.cost_actual or record.cost_estimated or 0
            record.margin_amount = record.amount_total - cost_for_margin

            if record.amount_total:
                record.margin_percent = (record.margin_amount / record.amount_total) * 100
            else:
                record.margin_percent = 0

            # Indice de rentabilité
            if cost_for_margin:
                record.profitability_index = record.amount_total / cost_for_margin
            else:
                record.profitability_index = 0

            # ROI
            if cost_for_margin:
                record.roi_percent = (record.margin_amount / cost_for_margin) * 100
            else:
                record.roi_percent = 0

    @api.depends('margin_percent', 'cost_variance_percent', 'payment_completion_rate')
    def _compute_financial_health(self):
        """Évalue la santé financière globale"""
        for record in self:
            score = 0

            # Critère 1: Marge par rapport à l'objectif
            if record.margin_percent >= record.margin_target_percent:
                score += 2
            elif record.margin_percent >= record.margin_target_percent * 0.8:
                score += 1
            elif record.margin_percent < 0:
                score -= 2

            # Critère 2: Écart de coût
            if abs(record.cost_variance_percent) <= 5:
                score += 2
            elif abs(record.cost_variance_percent) <= 15:
                score += 1
            elif record.cost_variance_percent > 25:
                score -= 2

            # Critère 3: Paiements
            if record.payment_completion_rate >= 90:
                score += 1
            elif record.payment_completion_rate < 50:
                score -= 1

            # Attribution de la santé financière
            if score >= 4:
                record.financial_health = 'excellent'
            elif score >= 2:
                record.financial_health = 'good'
            elif score >= 0:
                record.financial_health = 'average'
            elif score >= -2:
                record.financial_health = 'poor'
            else:
                record.financial_health = 'critical'

    @api.depends()  # Dépendances à définir dans les modèles filles
    def _compute_payment_status(self):
        """Calcule le statut des paiements - à override dans les modèles filles"""
        for record in self:
            payment_data = record._get_payment_data()
            record.payment_received = payment_data.get('received', 0)
            record.payment_pending = record.amount_total - record.payment_received

            if record.amount_total:
                record.payment_completion_rate = (
                                                         record.payment_received / record.amount_total
                                                 ) * 100
            else:
                record.payment_completion_rate = 0

    # =================== MÉTHODES UTILITAIRES ===================

    def _get_default_tax_rate(self):
        """Retourne le taux de TVA par défaut"""
        # À override dans les modèles filles si nécessaire
        return 20.0  # 20% par défaut

    def _calculate_actual_cost(self):
        """Calcule le coût réel - à override dans les modèles filles"""
        # Méthode par défaut, à spécialiser selon le contexte
        return self.cost_estimated or 0

    def _get_payment_data(self):
        """Récupère les données de paiement - à override dans les modèles filles"""
        return {'received': 0, 'pending': self.amount_total}

    # =================== ACTIONS PUBLIQUES ===================

    def action_recalculate_financial_data(self):
        """Recalcule toutes les données financières"""
        self.ensure_one()

        try:
            # Forcer le recalcul des champs calculés
            self._compute_amounts()
            self._compute_cost_actual()
            self._compute_financial_indicators()
            self._compute_payment_status()
            self._compute_financial_health()

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': 'Données financières recalculées',
                    'type': 'success'
                }
            }
        except Exception as e:
            _logger.error(f"Error recalculating financial data: {str(e)}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': 'Erreur lors du recalcul',
                    'type': 'danger'
                }
            }

    def action_view_financial_analysis(self):
        """Affiche une analyse financière détaillée"""
        self.ensure_one()

        analysis = self._prepare_financial_analysis()

        return {
            'name': f'Analyse financière - {self.display_name}',
            'type': 'ir.actions.act_window',
            'res_model': 'financial.analysis.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_analysis_data': analysis,
                'default_record_id': self.id,
                'default_model': self._name
            }
        }

    def _prepare_financial_analysis(self):
        """Prépare les données d'analyse financière"""
        self.ensure_one()

        return {
            'revenue': self.amount_total,
            'cost_estimated': self.cost_estimated,
            'cost_actual': self.cost_actual,
            'margin_amount': self.margin_amount,
            'margin_percent': self.margin_percent,
            'margin_target': self.margin_target_percent,
            'cost_variance': self.cost_variance,
            'cost_variance_percent': self.cost_variance_percent,
            'profitability_index': self.profitability_index,
            'roi_percent': self.roi_percent,
            'financial_health': self.financial_health,
            'payment_received': self.payment_received,
            'payment_pending': self.payment_pending,
            'payment_rate': self.payment_completion_rate
        }

    # =================== CONTRAINTES ===================

    @api.constrains('amount_untaxed', 'cost_estimated')
    def _check_positive_amounts(self):
        """Vérifie que les montants sont positifs"""
        for record in self:
            if record.amount_untaxed < 0:
                raise ValidationError("Le montant HT ne peut pas être négatif")
            if record.cost_estimated < 0:
                raise ValidationError("Le coût estimé ne peut pas être négatif")

    @api.constrains('margin_target_percent')
    def _check_margin_target(self):
        """Vérifie que l'objectif de marge est raisonnable"""
        for record in self:
            if record.margin_target_percent < -100 or record.margin_target_percent > 100:
                raise ValidationError("L'objectif de marge doit être entre -100% et 100%")
