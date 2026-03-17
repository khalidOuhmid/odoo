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
import logging
_logger = logging.getLogger(__name__)


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
    carnet_health = fields.Selection([
        ('green',  '✅ Bon — Pipeline solide'),
        ('orange', '⚠️ Attention — Pipeline moyen'),
        ('red',    '🔴 Critique — Pipeline insuffisant'),
    ], string="Santé du carnet", readonly=True)

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
        'Marge Prévue (%)', readonly=True, aggregator='avg'
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
        query = """
            CREATE OR REPLACE VIEW {table} AS (
                WITH
                -- Moyenne mensuelle facturée (3 derniers mois)
                historical_avg AS (
                    SELECT COALESCE(AVG(monthly), 0) as avg_monthly
                    FROM (
                        SELECT date_trunc('month', invoice_date) AS m,
                               SUM(amount_untaxed_signed) AS monthly
                        FROM account_move
                        WHERE move_type = 'out_invoice'
                          AND state = 'posted'
                          AND invoice_date >= CURRENT_DATE - INTERVAL '3 months'
                        GROUP BY m
                    ) sub
                ),
                -- Pipeline total sur 3 mois
                pipeline_total AS (
                    SELECT SUM(amount_fixed) as total
                    FROM construction_invoice_schedule
                    WHERE state IN ('planned','ready')
                      AND planned_date BETWEEN CURRENT_DATE AND (CURRENT_DATE + INTERVAL '3 months')
                ),
                -- Agrégation mensuelle
                agg AS (
                    SELECT
                        date_trunc('month', s.planned_date)::date AS forecast_month,
                        SUM(s.amount_fixed) AS forecast_revenue,
                        SUM(s.amount_fixed * (1.0 - COALESCE(s.margin_percentage, 0) / 100.0)) AS forecast_margin,
                        COUNT(DISTINCT s.chantier_id) AS active_chantiers,
                        COUNT(s.id) AS schedules_count
                    FROM construction_invoice_schedule s
                    WHERE s.state IN ('planned','ready')
                      AND s.planned_date BETWEEN CURRENT_DATE AND (CURRENT_DATE + INTERVAL '3 months')
                    GROUP BY date_trunc('month', s.planned_date)
                )
                SELECT
                    ROW_NUMBER() OVER (ORDER BY a.forecast_month) AS id,
                    a.forecast_month,
                    (SELECT id FROM res_currency WHERE name = 'EUR' LIMIT 1) AS currency_id,
                    a.forecast_revenue,
                    a.forecast_margin,
                    CASE
                        WHEN a.forecast_revenue > 0
                        THEN ROUND((a.forecast_margin / a.forecast_revenue * 100)::numeric, 1)
                        ELSE 0
                    END AS forecast_margin_pct,
                    a.active_chantiers,
                    a.schedules_count,
                    -- Calcul de la santé
                    CASE
                        WHEN (SELECT avg_monthly FROM historical_avg) <= 0 THEN 'green'
                        WHEN (SELECT total FROM pipeline_total) >= (SELECT avg_monthly FROM historical_avg) * 3 THEN 'green'
                        WHEN (SELECT total FROM pipeline_total) >= (SELECT avg_monthly FROM historical_avg) THEN 'orange'
                        ELSE 'red'
                    END AS carnet_health
                FROM agg a
            )
        """.format(table=self._table)
        try:
            self.env.cr.execute(query)
        except Exception as e:
            _logger.error("Error in finance_forecast.init: %s", e)
            _logger.error("Query was: %s", query)
            raise
