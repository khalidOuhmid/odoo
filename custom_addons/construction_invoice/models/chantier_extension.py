# -*- coding: utf-8 -*-
"""
Chantier Extension for Invoice Module

Adds invoice scheduling capabilities to chantiers.
"""

from odoo import models, fields, api, _


class Chantier(models.Model):
    """Extend chantier with invoice scheduling."""
    _inherit = 'construction.chantier'

    invoice_type_id = fields.Many2one(
        'construction.invoice_type',
        string='Cycle de facturation',
        help="Pattern de facturation à appliquer"
    )
    main_quote_id = fields.Many2one(
        'sale.order',
        string='Devis principal',
        help="Devis servant de référence pour la facturation"
    )
    invoice_schedule_ids = fields.One2many(
        'construction.invoice.schedule',
        'chantier_id',
        string='Planning de facturation'
    )
    invoice_schedule_count = fields.Integer(
        compute='_compute_invoice_schedule_count'
    )
    
    # ============= COMPUTED ============= #
    
    def _compute_invoice_schedule_count(self):
        for record in self:
            record.invoice_schedule_count = len(record.invoice_schedule_ids)
    
    # ============= ACTIONS ============= #
    
    def action_view_invoice_schedules(self):
        """View invoice schedules for this chantier."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Planning facturation - %s') % self.name,
            'res_model': 'construction.invoice.schedule',
            'view_mode': 'list,form',
            'domain': [('chantier_id', '=', self.id)],
            'context': {'default_chantier_id': self.id},
        }
    
    def action_generate_invoice_schedule(self):
        """Generate invoice schedule from the selected invoice type."""
        self.ensure_one()
        
        if not self.invoice_type_id:
            raise UserError(_("Veuillez d'abord sélectionner un cycle de facturation."))
        
        # Delete existing draft schedules
        self.invoice_schedule_ids.filtered(
            lambda s: s.state == 'draft'
        ).unlink()
        
        # Create new schedules from type lines
        for line in self.invoice_type_id.line_ids:
            self.env['construction.invoice.schedule'].create({
                'chantier_id': self.id,
                'invoice_type_line_id': line.id,
                'name': line.name,
                'sequence': line.sequence,
                'trigger_percentage': line.trigger_percentage,
                'amount_percentage': line.percentage,
                'is_advance_payment': line.is_advance_payment,
                'lot_ids': [(6, 0, self.lots_ids.ids)],
                'state': 'planned',
            })
        
        self.message_post(
            body=_("📅 Planning de facturation généré: %s") % self.invoice_type_id.name,
            message_type='notification'
        )
        
        return self.action_view_invoice_schedules()
