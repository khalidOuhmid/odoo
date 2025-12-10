# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError

class InvoiceScheduleWizard(models.TransientModel):
    _name = 'construction.invoice.schedule.wizard'
    _description = 'Assistant Planning Facturation'

    chantier_id = fields.Many2one('construction.chantier', required=True)
    invoice_type_id = fields.Many2one('construction.invoice_type', string="Cycle de Facturation", required=True)
    quote_id = fields.Many2one('sale.order', string="Devis de Référence")
    lot_ids = fields.Many2many('construction.lot', string="Lots Concernés")
    margin_percentage = fields.Float(string="Marge (%)", default=0.0)

    @api.onchange('chantier_id')
    def _onchange_chantier_id(self):
        if self.chantier_id:
            # Try to pre-fill quote if only one accepted quote exists
            quotes = self.chantier_id.quotation_ids.filtered(lambda q: q.state in ['sale', 'done'])
            if len(quotes) == 1:
                self.quote_id = quotes.id

    def action_generate_schedule(self):
        self.ensure_one()
        if not self.invoice_type_id.line_ids:
            raise UserError(_("Le cycle sélectionné n'a pas d'étapes."))

        schedule_model = self.env['construction.invoice.schedule']
        service = self.env['construction.invoice.service']

        # Determine reference amount calculation base
        # If quote_id and lot_ids are set, the specific calculation logic is handled inside the Service/Schedule compute method
        # Here we just create the records.

        created_schedules = []
        for line in self.invoice_type_id.line_ids:
            vals = {
                'chantier_id': self.chantier_id.id,
                'name': line.name,
                'sequence': line.sequence,
                'trigger_percentage': line.trigger_percentage,
                'amount_percentage': line.percentage,
                'quote_id': self.quote_id.id if self.quote_id else False,
                'lot_ids': [(6, 0, self.lot_ids.ids)] if self.lot_ids else False,
                'margin_percentage': self.margin_percentage,
                'state': 'planned'
            }
            schedule = schedule_model.create(vals)
            # Force compute of amount
            # schedule._compute_amount() # already triggered by store=True? Better force explicit compute call or just let Odoo handle it.
            # Explicit call via service to be safe if desired, but depends defaults handle it.
            created_schedules.append(schedule.id)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Planning Créé',
                'message': f"{len(created_schedules)} lignes de facturation ont été créées.",
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'}
            }
        }
