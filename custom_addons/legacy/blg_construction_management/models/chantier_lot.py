# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class BlgChantierLot(models.Model):
    """
    Work sections (lots) attached to construction projects
    """
    _name = 'blg.chantier.lot'
    _description = 'Construction Project Work Section'
    _order = 'sequence, name'  # Using simple fields that don't rely on related models
    
    name = fields.Char(related='lot_id.name', store=True, readonly=True)
    sequence = fields.Integer(string='Sequence', default=10)
    chantier_id = fields.Many2one('blg.chantier', string='Project', required=True, ondelete='cascade')
    lot_id = fields.Many2one('blg_contacts_extension.lot', string='Trade Category')
    lot_type_id = fields.Many2one('blg.lot.type', string='Work Section Type', 
                                  related='lot_id.type_id', store=True, readonly=True)
    
    subcontractor_id = fields.Many2one('res.partner', string='Subcontractor', 
                                      domain="[('contact_type', '=', 'sous_traitant')]")
    eligible_subcontractor_ids = fields.Many2many('res.partner', compute='_compute_eligible_subcontractors')
    
    cost = fields.Float('Cost')
    progress = fields.Float('Progress (%)', default=0)
    
    # Dates
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    
    # Status
    quote_state = fields.Selection([
        ('draft', 'No Quote'),
        ('sent', 'Quote Sent'),
        ('accepted', 'Quote Accepted'),
        ('rejected', 'Quote Rejected')
    ], string='Quote Status', default='draft')
    
    notes = fields.Text('Notes')

    @api.depends('lot_id')
    def _compute_eligible_subcontractors(self):
        """Compute subcontractors eligible for this work section based on their trade categories"""
        for record in self:
            if record.lot_id:
                record.eligible_subcontractor_ids = self.env['res.partner'].search([
                    ('contact_type', '=', 'sous_traitant'),
                    ('lots', 'in', record.lot_id.id)
                ])
            else:
                record.eligible_subcontractor_ids = self.env['res.partner'].search([
                    ('contact_type', '=', 'sous_traitant')
                ])

    @api.onchange('lot_id')
    def _onchange_lot_id(self):
        if self.lot_id and self.lot_id.type_id:
            self.lot_type_id = self.lot_id.type_id

