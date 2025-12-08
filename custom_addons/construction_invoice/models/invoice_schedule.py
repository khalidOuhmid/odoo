# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class ConstructionInvoiceType(models.Model):
    _name = "construction.invoice.type"
    _description = "Billing Cycle Template"
    _order = "sequence, name"

    name = fields.Char(string="Nom", required=True)
    code = fields.Char(string="Code", required=True)
    sequence = fields.Integer(string="Séquence", default=10)
    line_ids = fields.One2many('construction.invoice.type.line', 'type_id', string="Étapes")

class ConstructionInvoiceTypeLine(models.Model):
    _name = "construction.invoice.type.line"
    _description = "Billing Cycle Step"
    _order = "sequence"

    type_id = fields.Many2one('construction.invoice.type', string="Type de Facturation", required=True, ondelete='cascade')
    name = fields.Char(string="Libellé", required=True)
    sequence = fields.Integer(string="Séquence", default=10)
    trigger_percentage = fields.Float(string="Déclenchement (%)", required=True, help="Avancement % qui déclenche cette facture")
    bill_percentage = fields.Float(string="Facturation (%)", required=True, help="% du Devis Total à facturer")
    is_advance = fields.Boolean(string="Acompte", help="Facture à la signature")

class ConstructionInvoiceSchedule(models.Model):
    _name = "construction.invoice.schedule"
    _description = "Planning de Facturation"
    _order = "chantier_id, sequence"

    chantier_id = fields.Many2one('construction.chantier', string="Chantier", required=True, ondelete='cascade')
    quote_id = fields.Many2one('sale.order', string="Devis Réf.", domain="[('chantier_id', '=', chantier_id), ('state', 'in', ['sale', 'done'])]")
    
    name = fields.Char(string="Libellé", required=True)
    sequence = fields.Integer(string="Séquence", default=10)
    
    trigger_percentage = fields.Float(string="Déclenchement (%)", required=True)
    amount_percentage = fields.Float(string="Facturation (%)", required=True)
    
    amount_to_bill = fields.Monetary(string="Montant à Facturer", currency_field='currency_id', compute='_compute_amount_to_bill')
    currency_id = fields.Many2one(related='chantier_id.currency_id')
    
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('ready', 'Prêt à facturer'),
        ('invoiced', 'Facturé'),
        ('paid', 'Payé')
    ], string="État", default='draft', tracking=True)
    
    invoice_id = fields.Many2one('account.move', string="Facture", readonly=True)
    
    @api.depends('quote_id', 'amount_percentage', 'chantier_id')
    def _compute_amount_to_bill(self):
        for record in self:
            base_amount = record.quote_id.amount_total if record.quote_id else 0.0
            record.amount_to_bill = base_amount * (record.amount_percentage / 100.0)

    def check_trigger(self):
        """ Checks if Chantier/Lot progress triggers this bill """
        for record in self:
            if record.state != 'draft':
                continue
            
            # Simple Logic: Check Chantier global progress (or aggregated Lot progress)
            # For now, let's assume we use the Chantier's main progress field if it exists, 
            # or calculate it from Lots.
            
            current_progress = record._get_current_progress()
            
            if current_progress >= record.trigger_percentage:
                record.write({'state': 'ready'})
                # Notify User
                record.chantier_id.message_post(
                    body=f"Billing Schedule '{record.name}' is READY (Progress {current_progress}% >= {record.trigger_percentage}%)",
                    message_type='notification'
                )

    def _get_current_progress(self):
        self.ensure_one()
        # Calculate weighted average progress of lots
        lots = self.chantier_id.lot_ids
        if not lots:
            return 0.0
        
        # Simple average for now, better would be weighted by cost
        total_progress = sum(lots.mapped('progress'))
        return total_progress / len(lots)

    def action_create_invoice(self):
        self.ensure_one()
        if self.state != 'ready':
            raise ValidationError(_("Schedule item is not ready to be billed."))
            
        service = self.env['construction.invoice.service']
        invoice = service.create_situation_invoice(self)
        
        self.write({
            'state': 'invoiced', 
            'invoice_id': invoice.id
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': invoice.id,
            'view_mode': 'form',
            'target': 'current',
        }
