# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class ConstructionInvoiceSchedule(models.Model):
    """
    Invoice Schedule (Echéancier de Facturation).
    
    Compatible with Onaya/SAP billing plans.
    Allows defining a payment schedule (e.g. 30% Order, 30% Start, 40% Delivery).
    """
    _name = 'construction.invoice.schedule'
    _description = 'Echéancier Facturation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, date_planned'

    name = fields.Char(string='Libellé', required=True)
    sequence = fields.Integer(default=10)
    
    chantier_id = fields.Many2one(
        'construction.chantier',
        string='Chantier',
        required=True,
        ondelete='cascade'
    )
    
    percentage = fields.Float(string='Pourcentage (%)', required=True)
    amount_to_invoice = fields.Monetary(string='Montant à Facturer', compute='_compute_amount', store=True)
    
    date_planned = fields.Date(string='Date Prévue')
    
    state = fields.Selection([
        ('draft', 'Prévu'),
        ('ready', 'A Facturer'),
        ('invoiced', 'Facturé')
    ], default='draft', string='État', tracking=True)
    
    invoice_id = fields.Many2one('account.move', string='Facture Générée', readonly=True)
    currency_id = fields.Many2one(related='chantier_id.currency_id')

    @api.depends('chantier_id.budget_total', 'percentage')
    def _compute_amount(self):
        for rec in self:
            rec.amount_to_invoice = rec.chantier_id.budget_total * (rec.percentage / 100.0)

    def action_create_invoice(self):
        """Create invoice from schedule line."""
        self.ensure_one()
        # Similar logic to progress billing but for fixed percentage
        pass
