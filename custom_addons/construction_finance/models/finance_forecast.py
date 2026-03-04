# -*- coding: utf-8 -*-
"""
Finance Forecast Model — SQL View
====================================
Vue SQL de prévision financière sur M+1 / M+2 / M+3.

Basée sur les `construction.invoice.schedule` planifiés (state = planned / ready).
Réponse à : "Combien vais-je encaisser dans les 3 prochains mois ?"
"""
from odoo import tools, models, fields, api
from dateutil.relativedelta import relativedelta


class ConstructionFinanceForecast(models.Model):
    """
    Prévision mensuelle de facturation.

    Chaque ligne représente un mois de prévision (M+1, M+2, M+3)
    avec le CA prévu, la marge estimée, et le nombre de chantiers actifs.
    """
    _name = 'construction.finance.forecast'
    _description = 'Prévisions Financières (M+1/M+2/M+3)'
    _auto = False
    _order = 'forecast_month ASC'

    # ============= DIMENSIONS ============= #
    forecast_month = fields.Date('Mois', readonly=True)
    currency_id = fields.Many2one('res.currency', 'Devise', readonly=True)

    # ============= MESURES ============= #
    forecast_revenue = fields.Monetary(
        'CA Prévu (€)', readonly=True,
        help="Montant total des factures planifiées pour ce mois"
    )
    forecast_margin = fields.Monetary(
        'Marge Prévue (€)', readonly=True,
        help="Marge estimée après déduction de la marge configurée sur chaque échéance"
    )
    forecast_margin_pct = fields.Float(
        'Marge Prévue (%)', readonly=True, group_operator='avg'
    )
    active_chantiers = fields.Integer(
        'Chantiers Actifs', readonly=True,
        help="Nombre de chantiers distincts avec une facturation planifiée ce mois"
    )
    schedules_count = fields.Integer(
        'Nb Échéances', readonly=True,
        help="Nombre d'échéances de facturation planifiées pour ce mois"
    )

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    ROW_NUMBER() OVER (ORDER BY date_trunc('month', s.planned_date)) AS id,
                    date_trunc('month', s.planned_date)::date AS forecast_month,
                    -- Utilise la devise de la société courante (défaut company_id=1)
                    (SELECT id FROM res_currency WHERE name = 'EUR' LIMIT 1) AS currency_id,
                    SUM(s.amount_fixed) AS forecast_revenue,
                    -- Marge = montant * (1 - margin_pct/100)
                    SUM(s.amount_fixed * (1.0 - COALESCE(s.margin_percentage, 0) / 100.0)) AS forecast_margin,
                    CASE
                        WHEN SUM(s.amount_fixed) > 0
                        THEN ROUND(
                            (SUM(s.amount_fixed * (1.0 - COALESCE(s.margin_percentage, 0) / 100.0))
                             / SUM(s.amount_fixed) * 100)::numeric, 1)
                        ELSE 0
                    END AS forecast_margin_pct,
                    COUNT(DISTINCT s.chantier_id) AS active_chantiers,
                    COUNT(s.id) AS schedules_count
                FROM construction_invoice_schedule s
                WHERE s.state IN ('planned','ready')
                  AND s.planned_date BETWEEN CURRENT_DATE
                                         AND (CURRENT_DATE + INTERVAL '3 months')
                GROUP BY date_trunc('month', s.planned_date)
            )
        """ % (self._table,))

    # ============= COMPUTED (Santé du carnet) ============= #
    carnet_health = fields.Selection([
        ('green',  '✅ Bon — Pipeline solide'),
        ('orange', '⚠️ Attention — Pipeline moyen'),
        ('red',    '🔴 Critique — Pipeline insuffisant'),
    ], string="Santé du carnet", compute='_compute_carnet_health')

    @api.depends('forecast_revenue', 'active_chantiers')
    def _compute_carnet_health(self):
        """
        Règle feux tricolores :
          🟢 > 3 mois de CA moyen  → Bon
          🟠 entre 1 et 3 mois     → Attention
          🔴 < 1 mois              → Critique
        """
        # CA moyen mensuel facturé (3 derniers mois)
        self.env.cr.execute("""
            SELECT COALESCE(AVG(monthly), 0)
            FROM (
                SELECT date_trunc('month', invoice_date) AS m,
                       SUM(amount_untaxed_signed) AS monthly
                FROM account_move
                WHERE move_type = 'out_invoice'
                  AND state = 'posted'
                  AND invoice_date >= CURRENT_DATE - INTERVAL '3 months'
                GROUP BY m
            ) sub
        """)
        avg_monthly = self.env.cr.fetchone()[0] or 0

        # Total du pipeline 3 mois
        pipeline_total = sum(self.mapped('forecast_revenue'))

        for rec in self:
            if avg_monthly <= 0:
                rec.carnet_health = 'green'  # Pas encore de données = neutre
            elif pipeline_total >= avg_monthly * 3:
                rec.carnet_health = 'green'
            elif pipeline_total >= avg_monthly:
                rec.carnet_health = 'orange'
            else:
                rec.carnet_health = 'red'
