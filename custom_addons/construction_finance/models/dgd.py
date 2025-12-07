# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class ConstructionDGD(models.Model):
    """
    DGD - Décompte Général Définitif.
    
    Final settlement of the contract.
    Releases the retention amount and applies final penalties.
    """
    _name = 'construction.dgd'
    _description = 'Décompte Général Définitif'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Référence', default="DGD", required=True)
    chantier_id = fields.Many2one('construction.chantier', required=True)
    partner_id = fields.Many2one(related='chantier_id.partner_id', string='Client')
    
    date = fields.Date(default=fields.Date.context_today)
    
    # Amounts
    total_works_amount = fields.Monetary(string='Montant Travaux Total (HT)')
    total_paid_advances = fields.Monetary(string='Total Acomptes Versés')
    
    penalties_amount = fields.Monetary(string='Pénalités de Retard')
    prorata_account = fields.Monetary(string='Compte Prorata')
    
    final_balance = fields.Monetary(string='Solde à Payer', compute='_compute_balance')
    
    currency_id = fields.Many2one(related='chantier_id.currency_id')

    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('confirmed', 'Validé'),
        ('paid', 'Payé')
    ], default='draft')

    @api.depends('total_works_amount', 'total_paid_advances', 'penalties_amount', 'prorata_account')
    def _compute_balance(self):
        for rec in self:
            rec.final_balance = (rec.total_works_amount 
                               - rec.total_paid_advances 
                               - rec.penalties_amount 
                               - rec.prorata_account)
                               
    def action_approve(self):
        self.state = 'confirmed'
