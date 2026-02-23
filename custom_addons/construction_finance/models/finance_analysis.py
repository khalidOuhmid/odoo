# -*- coding: utf-8 -*-
from odoo import tools
from odoo import models, fields, api

class ConstructionFinanceAnalysisReport(models.Model):
    """
    SQL View for Construction Finance Analysis.
    
    This model aggregates financial data across sales orders, purchase orders,
    and invoices to provide a comprehensive view of planned vs. actual revenue,
    costs, and margins per chantier.
    """
    _name = "construction.finance.analysis.report"
    _description = "Construction Finance Analysis"
    _auto = False
    _order = 'date desc'

    # ============= DIMENSIONS ============= #
    date = fields.Date('Date', readonly=True)
    chantier_id = fields.Many2one('construction.chantier', 'Chantier', readonly=True)
    partner_id = fields.Many2one('res.partner', 'Partenaire', readonly=True)
    company_id = fields.Many2one('res.company', 'Société', readonly=True)
    
    # ============= MEASURES ============= #
    planned_revenue = fields.Monetary('CA Prévisionnel (Devis)', readonly=True)
    invoiced_revenue = fields.Monetary('CA Facturé (Réalisé)', readonly=True)
    
    committed_cost = fields.Monetary('Coût Engagé (Commandes)', readonly=True)
    invoiced_cost = fields.Monetary('Coût Réel (Factures Frs)', readonly=True)
    
    commission_cost = fields.Monetary('Commissions Apporteurs', readonly=True)
    
    margin = fields.Monetary('Marge', readonly=True)
    margin_percent = fields.Float('Marge %', readonly=True, group_operator='avg')
    currency_id = fields.Many2one('res.currency', 'Devise', readonly=True)

    def init(self):
        """
        Initializes the SQL view for the report.
        Calculates planned/invoiced revenue, committed/invoiced costs,
        commission costs, margin, and margin percentage.
        """
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    MIN(id) as id,
                    date,
                    chantier_id,
                    partner_id,
                    company_id,
                    currency_id,
                    SUM(planned_revenue) as planned_revenue,
                    SUM(invoiced_revenue) as invoiced_revenue,
                    SUM(committed_cost) as committed_cost,
                    SUM(invoiced_cost) as invoiced_cost,
                    SUM(commission_cost) as commission_cost,
                    SUM(invoiced_revenue) - SUM(invoiced_cost) - SUM(commission_cost) as margin,
                    CASE 
                        WHEN SUM(invoiced_revenue) > 0 
                        THEN ROUND(((SUM(invoiced_revenue) - SUM(invoiced_cost) - SUM(commission_cost)) / SUM(invoiced_revenue) * 100)::numeric, 1)
                        ELSE 0 
                    END as margin_percent
                FROM (
                    -- 1. REVENUE PLANNED (Sales Orders)
                    SELECT
                        so.id * 100000 + 1 as id,
                        so.date_order::date as date,
                        so.chantier_id,
                        so.partner_id,
                        so.company_id,
                        so.currency_id,
                        so.amount_untaxed as planned_revenue,
                        0 as invoiced_revenue,
                        0 as committed_cost,
                        0 as invoiced_cost,
                        0 as commission_cost
                    FROM sale_order so
                    WHERE so.state IN ('sale', 'done') AND so.chantier_id IS NOT NULL

                    UNION ALL

                    -- 2. REVENUE REALIZED (Customer Invoices) + PROVISIONED COMMISSION
                    SELECT
                        am.id * 100000 + 2 as id,
                        am.invoice_date as date,
                        am.chantier_id,
                        am.partner_id,
                        am.company_id,
                        am.currency_id,
                        0 as planned_revenue,
                        am.amount_untaxed_signed as invoiced_revenue,
                        0 as committed_cost,
                        0 as invoiced_cost,
                        -- Calculate Commission Provision: IF Percentage, Apply Rate to Invoice Amount
                        CASE 
                            WHEN c.commission_type = 'percentage' AND c.business_provider_id IS NOT NULL 
                            THEN am.amount_untaxed_signed * (c.commission_value / 100.0)
                            ELSE 0 
                        END as commission_cost
                    FROM account_move am
                    JOIN construction_chantier c ON am.chantier_id = c.id
                    WHERE am.move_type IN ('out_invoice', 'out_refund')
                      AND am.state = 'posted'
                      AND am.chantier_id IS NOT NULL

                    UNION ALL

                    -- 3. COST COMMITTED (Purchase Order Lines linked to Lots)
                    SELECT
                        pol.id * 100000 + 3 as id,
                        po.date_order::date as date,
                        lot.chantier_id,
                        po.partner_id,
                        po.company_id,
                        po.currency_id,
                        0 as planned_revenue,
                        0 as invoiced_revenue,
                        pol.price_subtotal as committed_cost,
                        0 as invoiced_cost,
                        0 as commission_cost
                    FROM purchase_order_line pol
                    JOIN purchase_order po ON pol.order_id = po.id
                    JOIN construction_lot lot ON pol.lot_id = lot.id
                    WHERE po.state IN ('purchase', 'done')
                    
                    UNION ALL

                    -- 4. COST REALIZED (Vendor Bills)
                    -- Exclude Business Provider Bills to avoid double counting with Provision?
                    -- Strategy: We use Provision for Commission (Anticipation). 
                    -- Realized Bills from Provider should NOT duplicate Margine Impact.
                    SELECT
                        am.id * 100000 + 4 as id,
                        am.invoice_date as date,
                        am.chantier_id,
                        am.partner_id,
                        am.company_id,
                        am.currency_id,
                        0 as planned_revenue,
                        0 as invoiced_revenue,
                        0 as committed_cost,
                        -- Logic: Bill (+), Refund (-)
                        CASE 
                             WHEN am.move_type = 'in_invoice' THEN am.amount_untaxed 
                             WHEN am.move_type = 'in_refund' THEN -am.amount_untaxed 
                             ELSE 0 
                        END as invoiced_cost,
                        0 as commission_cost
                    FROM account_move am
                    JOIN construction_chantier c ON am.chantier_id = c.id
                    WHERE am.move_type IN ('in_invoice', 'in_refund')
                      AND am.state = 'posted'
                      AND am.chantier_id IS NOT NULL
                      -- EXCLUDE Business Provider Bills
                      AND (c.business_provider_id IS NULL OR am.partner_id != c.business_provider_id)

                ) as analysis
                GROUP BY
                    date,
                    chantier_id,
                    partner_id,
                    company_id,
                    currency_id
            )
        """ % (self._table,))
