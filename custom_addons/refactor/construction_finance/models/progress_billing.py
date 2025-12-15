# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class ConstructionProgressBilling(models.Model):
    """
    Progress Billing (Situation de Travaux).
    
    Allows billing based on cumulative progress percentage.
    Handles 'Retenue de Garantie' (Retention) logic.
    """
    _name = 'construction.progress.billing'
    _description = 'Situation de Travaux'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(string='Référence', required=True, copy=False, default=lambda self: _('Brouillon'))
    date = fields.Date(string='Date', default=fields.Date.context_today, required=True, tracking=True)
    
    chantier_id = fields.Many2one(
        'construction.chantier',
        string='Chantier',
        required=True,
        tracking=True
    )
    
    partner_id = fields.Many2one(related='chantier_id.partner_id', string='Client', store=True)

    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('confirmed', 'Confirmé'),
        ('invoiced', 'Facturé'),
        ('cancel', 'Annulé')
    ], string='État', default='draft', tracking=True)

    # ==============================================================================================
    #                                      BILLING DETAILS
    # ==============================================================================================
    
    currency_id = fields.Many2one(related='chantier_id.currency_id')
    
    total_market_amount = fields.Monetary(string='Marché Initial', help="Montant total du marché")
    previous_progress = fields.Float(string='Avancement Précédent (%)', readonly=True)
    current_progress = fields.Float(string='Avancement Cumulé (%)', required=True)
    
    amount_cumulative = fields.Monetary(string='Montant Cumulé', compute='_compute_amounts', store=True)
    amount_previous = fields.Monetary(string='Déjà Facturé', readonly=True)
    amount_this_bill = fields.Monetary(string='Montant Situation', compute='_compute_amounts', store=True)
    
    # Retention (RG)
    apply_retention = fields.Boolean(string='Appliquer Retenue de Garantie (5%)', default=True)
    retention_amount = fields.Monetary(string='Retenue de Garantie', compute='_compute_amounts', store=True)
    net_to_pay = fields.Monetary(string='Net à Payer', compute='_compute_amounts', store=True)

    invoice_id = fields.Many2one('account.move', string='Facture', readonly=True)

    @api.depends('total_market_amount', 'current_progress', 'amount_previous', 'apply_retention')
    def _compute_amounts(self):
        for rec in self:
            # 1. Calculate Cumulative Amount based on Progress
            rec.amount_cumulative = rec.total_market_amount * (rec.current_progress / 100.0)
            
            # 2. Calculate Amount for THIS bill
            raw_amount = rec.amount_cumulative - rec.amount_previous
            
            # 3. Calculate Retention
            if rec.apply_retention:
                rec.retention_amount = raw_amount * 0.05
            else:
                rec.retention_amount = 0.0
            
            # 4. Net
            rec.amount_this_bill = raw_amount
            rec.net_to_pay = raw_amount - rec.retention_amount

    @api.constrains('current_progress')
    def _check_progress(self):
        for rec in self:
            if rec.current_progress < rec.previous_progress:
                raise ValidationError(_("L'avancement cumulé ne peut pas être inférieur à l'avancement précédent."))
            if rec.current_progress > 100:
                raise ValidationError(_("L'avancement ne peut pas dépasser 100%."))

    def action_confirm(self):
        self.state = 'confirmed'
        if self.name == _('Brouillon'):
            self.name = self.env['ir.sequence'].next_by_code('construction.progress.billing') or _('SIT/0000')

    def action_create_invoice(self):
        """Generates standard Odoo invoice from this billing situation."""
        self.ensure_one()
        if self.invoice_id:
            return
            
        invoice_vals = {
            'move_type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'invoice_date': self.date,
            'ref': f"{self.name} - {self.chantier_id.name}",
            'invoice_line_ids': [
                (0, 0, {
                    'name': f"Situation n° {self.name} - Avancement {self.current_progress}%",
                    'quantity': 1,
                    'price_unit': self.net_to_pay, # Simplified for now, should handle RG accounting properly
                })
            ]
        }
        invoice = self.env['account.move'].create(invoice_vals)
        self.invoice_id = invoice.id
        self.state = 'invoiced'
