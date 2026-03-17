# -*- coding: utf-8 -*-
"""
Construction Finance Analysis Report (Enriched)
================================================
SQL View enrichi pour la Tour de Contrôle Financière.

Nouveaux champs vs version originale :
  - health_score       : green / orange / red (calculé auto)
  - days_since_last_invoice : Jours depuis la dernière facture émise
  - invoice_pipeline_30d    : Montant planifié à facturer dans 30j
  - budget_drift_percent    : Dérive coût réel vs coût planifié (%)
"""
from odoo import tools, models, fields, api
import logging
_logger = logging.getLogger(__name__)


class ConstructionFinanceAnalysisReport(models.Model):
    """
    Vue SQL complète pour l'analyse financière chantier.

    Agrège : devis, factures client, commandes fournisseur, factures fournisseur.
    Calcule la marge nette, le score de santé et les indicateurs d'alerte.
    """
    _name = "construction.finance.analysis.report"
    _description = "Analyse Financière Chantier"
    _auto = False
    _order = 'health_score ASC, margin_percent ASC'

    # ============= DIMENSIONS ============= #
    date = fields.Date('Date', readonly=True)
    chantier_id = fields.Many2one('construction.chantier', 'Chantier', readonly=True)
    partner_id = fields.Many2one('res.partner', 'Partenaire', readonly=True)
    company_id = fields.Many2one('res.company', 'Société', readonly=True)

    # ============= MESURES FINANCIÈRES ============= #
    planned_revenue = fields.Monetary('CA Prévisionnel', readonly=True)
    invoiced_revenue = fields.Monetary('CA Facturé', readonly=True)
    committed_cost = fields.Monetary('Coût Engagé', readonly=True)
    invoiced_cost = fields.Monetary('Coût Réel', readonly=True)
    commission_cost = fields.Monetary('Commissions', readonly=True)
    margin = fields.Monetary('Marge Brute (€)', readonly=True)
    margin_percent = fields.Float('Marge (%)', readonly=True, aggregator='avg')
    currency_id = fields.Many2one('res.currency', 'Devise', readonly=True)

    # ============= NOUVEAUX INDICATEURS ============= #
    days_since_last_invoice = fields.Integer(
        'Jours sans facture', readonly=True,
        help="Nombre de jours depuis la dernière facture client émise pour ce chantier"
    )
    invoice_pipeline_30d = fields.Monetary(
        'Pipeline 30 jours (€)', readonly=True,
        help="Montant total planifié à facturer dans les 30 prochains jours"
    )
    budget_drift_percent = fields.Float(
        'Dérive Budget (%)', readonly=True,
        help="Écart entre coût engagé et coût réel — positif = dépassement"
    )
    health_score = fields.Selection([
        ('green', '✅ Sain'),
        ('orange', '⚠️ À surveiller'),
        ('red', '🔴 En danger'),
    ], string='État', readonly=True,
       help="Calculé automatiquement selon marge, retard facturation et dépassement budget"
    )

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        query = """
            CREATE OR REPLACE VIEW {table} AS (
                WITH
                -- ================================================================
                -- CTE 1 : Agrégation financière de base par chantier + date
                -- ================================================================
                base AS (
                    SELECT
                        MIN(id) as id,
                        date,
                        chantier_id,
                        partner_id,
                        company_id,
                        currency_id,
                        SUM(planned_revenue)  AS planned_revenue,
                        SUM(invoiced_revenue) AS invoiced_revenue,
                        SUM(committed_cost)   AS committed_cost,
                        SUM(invoiced_cost)    AS invoiced_cost,
                        SUM(commission_cost)  AS commission_cost,
                        SUM(invoiced_revenue) - SUM(invoiced_cost) - SUM(commission_cost) AS margin,
                        CASE
                            WHEN SUM(invoiced_revenue) > 0
                            THEN ROUND(
                                ((SUM(invoiced_revenue) - SUM(invoiced_cost) - SUM(commission_cost))
                                 / SUM(invoiced_revenue) * 100)::numeric, 1)
                            ELSE 0
                        END AS margin_percent
                    FROM (
                        -- 1. Devis acceptés → CA Prévisionnel
                        SELECT
                            so.id * 100000 + 1 AS id,
                            so.date_order::date AS date,
                            so.chantier_id, so.partner_id, so.company_id, so.currency_id,
                            so.amount_untaxed AS planned_revenue,
                            0 AS invoiced_revenue, 0 AS committed_cost,
                            0 AS invoiced_cost, 0 AS commission_cost
                        FROM sale_order so
                        WHERE so.state IN ('sale','done') AND so.chantier_id IS NOT NULL

                        UNION ALL

                        -- 2. Factures client → CA Réalisé + Commission
                        SELECT
                            am.id * 100000 + 2 AS id,
                            am.invoice_date AS date,
                            am.chantier_id, am.partner_id, am.company_id, am.currency_id,
                            0 AS planned_revenue,
                            am.amount_untaxed_signed AS invoiced_revenue,
                            0 AS committed_cost, 0 AS invoiced_cost,
                            CASE
                                WHEN c.commission_type = 'percentage' AND c.business_provider_id IS NOT NULL
                                THEN am.amount_untaxed_signed * (c.commission_value / 100.0)
                                ELSE 0
                            END AS commission_cost
                        FROM account_move am
                        JOIN construction_chantier c ON am.chantier_id = c.id
                        WHERE am.move_type IN ('out_invoice','out_refund')
                          AND am.state = 'posted' AND am.chantier_id IS NOT NULL

                        UNION ALL

                        -- 3. Commandes fournisseur → Coût Engagé
                        SELECT
                            pol.id * 100000 + 3 AS id,
                            po.date_order::date AS date,
                            lot.chantier_id, po.partner_id, po.company_id, po.currency_id,
                            0, 0, pol.price_subtotal AS committed_cost, 0, 0
                        FROM purchase_order_line pol
                        JOIN purchase_order po ON pol.order_id = po.id
                        JOIN construction_lot lot ON pol.lot_id = lot.id
                        WHERE po.state IN ('purchase','done')

                        UNION ALL

                        -- 4. Factures fournisseur → Coût Réel
                        SELECT
                            am.id * 100000 + 4 AS id,
                            am.invoice_date AS date,
                            am.chantier_id, am.partner_id, am.company_id, am.currency_id,
                            0, 0, 0,
                            CASE
                                WHEN am.move_type = 'in_invoice' THEN am.amount_untaxed
                                WHEN am.move_type = 'in_refund'  THEN -am.amount_untaxed
                                ELSE 0
                            END AS invoiced_cost,
                            0
                        FROM account_move am
                        JOIN construction_chantier c ON am.chantier_id = c.id
                        WHERE am.move_type IN ('in_invoice','in_refund')
                          AND am.state = 'posted' AND am.chantier_id IS NOT NULL
                          AND (c.business_provider_id IS NULL OR am.partner_id != c.business_provider_id)

                    ) AS analysis
                    GROUP BY date, chantier_id, partner_id, company_id, currency_id
                ),

                -- ================================================================
                -- CTE 2 : Dernière date de facture par chantier
                -- ================================================================
                last_invoice AS (
                    SELECT
                        chantier_id,
                        MAX(invoice_date) AS last_invoice_date
                    FROM account_move
                    WHERE move_type = 'out_invoice'
                      AND state = 'posted'
                      AND chantier_id IS NOT NULL
                    GROUP BY chantier_id
                ),

                -- ================================================================
                -- CTE 3 : Pipeline de facturation 30 jours par chantier
                -- ================================================================
                pipeline AS (
                    SELECT
                        chantier_id,
                        SUM(amount_fixed) AS pipeline_30d
                    FROM construction_invoice_schedule
                    WHERE state IN ('planned','ready')
                      AND planned_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '30 days'
                    GROUP BY chantier_id
                )

                -- ================================================================
                -- Requête finale : jointure + calcul health_score
                -- ================================================================
                SELECT
                    b.id, b.date, b.chantier_id, b.partner_id, b.company_id, b.currency_id,
                    b.planned_revenue, b.invoiced_revenue,
                    b.committed_cost, b.invoiced_cost, b.commission_cost,
                    b.margin, b.margin_percent,

                    -- Jours sans facture (0 = aucune facture connue → alerte)
                    COALESCE(
                        CURRENT_DATE - li.last_invoice_date, 999
                    ) AS days_since_last_invoice,

                    -- Pipeline 30j
                    COALESCE(p.pipeline_30d, 0) AS invoice_pipeline_30d,

                    -- Dérive budget : (coût_réel - coût_engagé) / coût_engagé * 100
                    CASE
                        WHEN b.committed_cost > 0
                        THEN ROUND(((b.invoiced_cost - b.committed_cost) / b.committed_cost * 100)::numeric, 1)
                        ELSE 0
                    END AS budget_drift_percent,

                    -- Health Score : red > orange > green
                    CASE
                        WHEN b.margin_percent < 5
                          OR b.invoiced_cost > b.committed_cost * 1.10
                          OR COALESCE(CURRENT_DATE - li.last_invoice_date, 999) > 60
                        THEN 'red'
                        WHEN b.margin_percent < 15
                          OR COALESCE(CURRENT_DATE - li.last_invoice_date, 999) > 30
                        THEN 'orange'
                        ELSE 'green'
                    END AS health_score

                FROM base b
                LEFT JOIN last_invoice li ON li.chantier_id = b.chantier_id
                LEFT JOIN pipeline p      ON p.chantier_id  = b.chantier_id
            )
        """.format(table=self._table)
        try:
            self.env.cr.execute(query)
        except Exception as e:
            _logger.error("Error in finance_analysis.init: %s", e)
            _logger.error("Query was: %s", query)
            raise

    # ============= ACTIONS SMART BUTTONS ============= #

    def action_view_chantier(self):
        """Navigation one-click vers la fiche chantier."""
        self.ensure_one()
        if not self.chantier_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'name': self.chantier_id.name,
            'res_model': 'construction.chantier',
            'res_id': self.chantier_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_create_invoice(self):
        """One-click : créer la facture d'avancement depuis le dashboard."""
        self.ensure_one()
        if not self.chantier_id:
            return
        # Trouver le premier schedule prêt
        ready_schedule = self.env['construction.invoice.schedule'].search([
            ('chantier_id', '=', self.chantier_id.id),
            ('state', '=', 'ready'),
        ], limit=1)
        if ready_schedule:
            return ready_schedule.action_create_invoice()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Aucune facturation prête',
                'message': 'Ce chantier n\'a pas d\'échéance prête à facturer.',
                'type': 'warning',
            }
        }
