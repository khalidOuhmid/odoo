# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)

class ConstructionFinancialMixin(models.AbstractModel):
    """
    Mixin for FinOps tracking (Budget vs Realized vs Forecast).
    Intended to be inherited by Chantier, Lot, and Contracts.
    """
    _name = 'construction.financial.mixin'
    _description = 'Financial Tracking Mixin'

    # ==========================================
    # 1. BUDGET (Estimated / Plan)
    # ==========================================
    budget_amount = fields.Monetary(
        string="Budget Initial",
        currency_field='currency_id',
        tracking=True,
        help="Montant initialement prévu (devisé ou alloué)."
    )
    
    # ==========================================
    # 2. COMMITTED (Signed Contracts / POs)
    # ==========================================
    committed_amount = fields.Monetary(
        string="Montant Engagé",
        compute='_compute_financial_status',
        store=True,
        currency_field='currency_id',
        help="Total des commandes/contrats signés (Devis acceptés, POs confirmés)."
    )

    # ==========================================
    # 3. REALIZED (Invoiced / Timesheets)
    # ==========================================
    realized_amount = fields.Monetary(
        string="Coût Réalisé",
        compute='_compute_financial_status',
        store=True,
        currency_field='currency_id',
        help="Total des factures fournisseurs comptabilisées + Coût Main d'oeuvre."
    )

    # ==========================================
    # 4. MARGINS & VARIANCE
    # ==========================================
    gross_margin = fields.Monetary(
        string="Marge Brute",
        compute='_compute_financial_kpi',
        currency_field='currency_id',
        help="Revenus (Vente) - Coûts Réalisés"
    )
    
    margin_rate = fields.Float(
        string="Taux de Marge (%)",
        compute='_compute_financial_kpi',
        group_operator="avg"
    )

    budget_variance = fields.Monetary(
        string="Écart Budget",
        compute='_compute_financial_kpi',
        currency_field='currency_id',
        help="Budget - Engagé (Positif = Sous budget, Négatif = Dépassement)"
    )

    # ==========================================
    # TECHNICAL
    # ==========================================
    currency_id = fields.Many2one(
        'res.currency', 
        default=lambda self: self.env.company.currency_id
    )

    def _compute_financial_status(self):
        """
        To be implemented by the concrete class (Chantier, Lot, etc.)
        Must set: committed_amount, realized_amount
        """
        for record in self:
            record.committed_amount = 0.0
            record.realized_amount = 0.0

    @api.depends('budget_amount', 'committed_amount', 'realized_amount')
    def _compute_financial_kpi(self):
        for record in self:
            # Variance logic
            record.budget_variance = record.budget_amount - record.committed_amount
            
            # Margin logic (safely handle missing revenue_amount)
            revenue = 0.0
            if hasattr(record, 'revenue_amount'):
                revenue = record.revenue_amount
            
            record.gross_margin = revenue - record.realized_amount
            
            if revenue and revenue != 0.0:
                record.margin_rate = (record.gross_margin / revenue) * 100
            else:
                record.margin_rate = 0.0
