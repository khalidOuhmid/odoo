# -*- coding: utf-8 -*-
"""
Invoice Schedule Model

Represents planned invoices for a construction project.
Triggers based on stage progression (PLM philosophy).
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class InvoiceSchedule(models.Model):
    """
    Invoice Schedule (Planned Invoice).
    
    Each schedule represents a planned invoice that will be triggered
    when the chantier reaches a specific stage/progress.
    """
    _name = 'construction.invoice.schedule'
    _description = 'Planning de facturation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'chantier_id, sequence, trigger_percentage'

    # ============= RELATIONS ============= #
    chantier_id = fields.Many2one(
        'construction.chantier',
        string='Chantier',
        required=True,
        ondelete='cascade',
        tracking=True
    )
    invoice_type_line_id = fields.Many2one(
        'construction.invoice_type.line',
        string='Étape du cycle',
        help="Ligne du cycle de facturation source"
    )
    quote_id = fields.Many2one(
        'sale.order',
        string='Devis de référence',
        domain="[('chantier_id', '=', chantier_id), ('state', 'in', ['sale', 'done'])]"
    )
    lot_ids = fields.Many2many(
        'construction.lot',
        'invoice_schedule_lot_rel',
        'schedule_id', 'lot_id',
        string='Lots concernés',
        domain="[('chantier_id', '=', chantier_id)]"
    )
    
    # ============= IDENTIFICATION ============= #
    name = fields.Char(string='Description', required=True)
    sequence = fields.Integer(string='Séquence', default=10)
    
    # ============= TRIGGER & AMOUNT ============= #
    trigger_percentage = fields.Float(
        string='Déclenchement (%)',
        required=True,
        help="Pourcentage d'avancement qui déclenche cette facture"
    )
    trigger_stage_id = fields.Many2one(
        'construction.stage',
        string='Étape de déclenchement',
        help="Alternative: déclencher quand le chantier atteint cette étape"
    )
    amount_percentage = fields.Float(
        string='Montant (%)',
        required=True
    )
    amount_fixed = fields.Monetary(
        string='Montant calculé',
        compute='_compute_amount_fixed',
        store=True,
        currency_field='currency_id'
    )
    margin_percentage = fields.Float(
        string='Marge (%)',
        default=0.0,
        help="Marge à déduire du montant"
    )
    
    # ============= DATES ============= #
    planned_date = fields.Date(string='Date prévue')
    invoice_date = fields.Date(string='Date facture', readonly=True)
    payment_date = fields.Date(string='Date paiement', readonly=True)
    
    # ============= STATE ============= #
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('planned', 'Planifié'),
        ('ready', 'Prêt à facturer'),
        ('invoiced', 'Facturé'),
        ('paid', 'Payé'),
        ('cancelled', 'Annulé'),
    ], string='État', default='draft', required=True, tracking=True)
    
    is_advance_payment = fields.Boolean(
        string='Acompte signature',
        help="Facture à émettre à la signature"
    )
    is_triggered = fields.Boolean(
        string='Déclenchée',
        help="Seuil d'avancement atteint"
    )
    
    # ============= INVOICE LINK ============= #
    invoice_id = fields.Many2one(
        'account.move',
        string='Facture',
        readonly=True
    )
    
    # ============= CURRENCY ============= #
    currency_id = fields.Many2one(
        related='chantier_id.currency_id',
        store=True
    )
    
    notes = fields.Text(string='Notes')
    
    # ============= COMPUTED ============= #
    
    @api.depends('chantier_id.total_cost', 'amount_percentage', 'margin_percentage', 'lot_ids')
    def _compute_amount_fixed(self):
        """Calculate fixed amount from percentage and margin."""
        for record in self:
            base_amount = 0.0
            
            if record.lot_ids:
                # Amount based on selected lots
                base_amount = sum(record.lot_ids.mapped('price'))
            elif record.chantier_id:
                # Fallback to total chantier cost
                base_amount = record.chantier_id.total_cost or 0.0
            
            # Apply margin
            net_amount = base_amount * (1 - record.margin_percentage / 100)
            
            # Apply percentage
            record.amount_fixed = net_amount * (record.amount_percentage / 100)
    
    # ============= ACTIONS ============= #
    
    def action_mark_planned(self):
        """Mark as planned (ready to be triggered)."""
        self.ensure_one()
        self.state = 'planned'
        return True
    
    def action_mark_ready(self):
        """Mark as ready to invoice (triggered)."""
        self.ensure_one()
        
        if not self.is_advance_payment:
            current_progress = self.chantier_id.progress
            if current_progress < self.trigger_percentage:
                raise UserError(_(
                    "Le chantier n'a pas atteint %.0f%% (actuellement %.1f%%)"
                ) % (self.trigger_percentage, current_progress))
        
        self.write({
            'state': 'ready',
            'is_triggered': True,
        })
        
        # Post notification in chantier
        self.chantier_id.message_post(
            body=_("📊 Facturation disponible: %s (%.0f%% - %.2f €)") % (
                self.name, self.amount_percentage, self.amount_fixed
            ),
            message_type='notification'
        )
        
        return True
    
    def action_create_invoice(self):
        """Create the invoice for this schedule."""
        self.ensure_one()
        
        if self.state != 'ready':
            raise UserError(_("Cette échéance n'est pas prête à être facturée."))
        
        if not self.chantier_id.client:
            raise UserError(_("Le chantier n'a pas de client défini."))
        
        # Create invoice
        invoice_vals = {
            'move_type': 'out_invoice',
            'partner_id': self.chantier_id.client.id,
            'invoice_date': fields.Date.today(),
            'invoice_origin': self.chantier_id.reference,
            'narration': _("Facturation %s - %s") % (self.name, self.chantier_id.name),
            'invoice_line_ids': [(0, 0, {
                'name': _("%s - %s") % (self.chantier_id.name, self.name),
                'quantity': 1,
                'price_unit': self.amount_fixed,
            })],
        }
        
        invoice = self.env['account.move'].create(invoice_vals)
        
        self.write({
            'state': 'invoiced',
            'invoice_id': invoice.id,
            'invoice_date': fields.Date.today(),
        })
        
        self.chantier_id.message_post(
            body=_("🧾 Facture %s créée: %.2f €") % (invoice.name, self.amount_fixed),
            message_type='notification'
        )
        
        return {
            'type': 'ir.actions.act_window',
            'name': invoice.name,
            'res_model': 'account.move',
            'res_id': invoice.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_cancel(self):
        """Cancel the schedule."""
        self.ensure_one()
        if self.state == 'invoiced' and self.invoice_id:
            raise UserError(_("Impossible d'annuler une échéance facturée."))
        self.state = 'cancelled'
        return True
    
    # ============= STAGE TRIGGER CHECK ============= #
    
    def check_stage_trigger(self, new_stage):
        """
        Check if this schedule should be triggered by a stage change.
        Called by the chantier when stage changes.
        
        Args:
            new_stage: The new stage record
        """
        self.ensure_one()
        
        if self.state != 'planned':
            return
        
        # Check stage-based trigger
        if self.trigger_stage_id and self.trigger_stage_id == new_stage:
            self.action_mark_ready()
            return
        
        # Check progress-based trigger
        current_progress = self.chantier_id.progress
        if current_progress >= self.trigger_percentage:
            self.action_mark_ready()
    
    # ============= CRON ============= #
    
    @api.model
    def cron_check_triggers(self):
        """Scheduled action to check if any schedules should be triggered."""
        schedules = self.search([
            ('state', '=', 'planned'),
            ('is_triggered', '=', False),
        ])
        
        for schedule in schedules:
            try:
                current_progress = schedule.chantier_id.progress
                
                # Skip advance payments (manual trigger)
                if schedule.is_advance_payment:
                    continue
                
                if current_progress >= schedule.trigger_percentage:
                    schedule.action_mark_ready()
                    
            except Exception as e:
                _logger.error("Error checking invoice schedule %s: %s", schedule.id, e)
        
        return True
