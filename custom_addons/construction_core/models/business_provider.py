# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ConstructionBusinessProvider(models.Model):
    """
    Gestion des Apporteurs d'Affaires (Business Providers).
    Permet de suivre les commissions et l'impact sur la marge nette du chantier.
    """
    _name = 'construction.business.provider'
    _description = 'Business Provider Commission'
    _inherit = ['construction.financial.mixin'] # Pour le suivi financier propre à l'apporteur si besoin

    name = fields.Char(related='partner_id.name', store=True)

    # ==========================
    # RELATIONS
    # ==========================
    partner_id = fields.Many2one(
        'res.partner', 
        string="Apporteur d'Affaires", 
        required=True,
        domain="[('is_company', '=', False)]" # Souvent des individus, à adapter
    )
    
    chantier_id = fields.Many2one(
        'construction.chantier', 
        string="Chantier", 
        required=True,
        ondelete='cascade'
    )

    # ==========================
    # CONDITIONS
    # ==========================
    commission_type = fields.Selection([
        ('percentage_turnover', '% sur CA HT'),
        ('percentage_margin', '% sur Marge Brute'),
        ('fixed', 'Montant Fixe')
    ], string="Type de Commission", default='percentage_turnover', required=True)

    commission_rate = fields.Float(string="Taux Comm. (%)")
    fixed_amount = fields.Monetary(string="Montant Fixe", currency_field='currency_id')
    cap_amount = fields.Monetary(
        string="Plafond", 
        help="Montant maximum de la commission",
        currency_field='currency_id'
    )

    # ==========================
    # INDICATORS (FinOps)
    # ==========================
    generated_revenue = fields.Monetary(
        string="CA Généré",
        help="Montant des ventes apportées (liées au chantier)",
        currency_field='currency_id'
    )
    
    theoretical_commission = fields.Monetary(
        string="Comm. Théorique",
        compute='_compute_commission',
        store=True,
        currency_field='currency_id'
    )
    
    # Suivi Facturation Apporteur (Reverse Factoring ou Facture Fournisseur)
    invoiced_commission = fields.Monetary(
        string="Comm. Facturée",
        help="Montant des factures reçues de l'apporteur",
        currency_field='currency_id'
    )
    
    paid_commission = fields.Monetary(
        string="Comm. Payée",
        currency_field='currency_id'
    )

    @api.depends('commission_type', 'commission_rate', 'fixed_amount', 'generated_revenue', 'chantier_id.gross_margin', 'cap_amount')
    def _compute_commission(self):
        for record in self:
            amount = 0.0
            if record.commission_type == 'fixed':
                amount = record.fixed_amount
            elif record.commission_type == 'percentage_turnover':
                amount = record.generated_revenue * (record.commission_rate / 100.0)
            elif record.commission_type == 'percentage_margin':
                # Note: gross_margin comes from the mixin on the chantier
                margin = record.chantier_id.gross_margin if record.chantier_id else 0.0
                amount = margin * (record.commission_rate / 100.0)
            
            # Apply Cap
            if record.cap_amount > 0 and amount > record.cap_amount:
                amount = record.cap_amount
                
            record.theoretical_commission = amount
