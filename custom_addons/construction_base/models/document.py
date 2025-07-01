from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class Document(models.Model):
    _name = 'construction.document'
    _description = 'Construction Document'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char('Document Name', required=True, tracking=True)
    chantier_id = fields.Many2one('construction.chantier', string='Project',
                                  required=True, tracking=True)
    chapter_id = fields.Many2one('construction.chapter', string='Chapter')
    stage_id = fields.Many2one('construction.stage', string='Stage')

    document_type = fields.Selection([
        ('quote', 'Quote'),
        ('contract', 'Contract'),
        ('subcontract', 'Subcontract'),
        ('specs', 'Technical Specifications'),
        ('plan', 'Plan'),
        ('schedule', 'Schedule'),
        ('permit', 'Permit'),
        ('other', 'Other')
    ], string='Document Type', required=True, tracking=True)

    # Approche simplifiée avec champ Binary
    file_data = fields.Binary('File', required=True, attachment=True)
    filename = fields.Char('Filename', required=True)
    file_size = fields.Integer('File Size', readonly=True)

    description = fields.Text('Description')
    partner_id = fields.Many2one('res.partner', string='Related Partner')
    expiry_date = fields.Date('Expiry Date')
    amount = fields.Monetary('Amount', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  default=lambda self: self.env.company.currency_id)
