from odoo import models, fields, api, _

class LotExtension(models.Model):
    _inherit = 'lot'
    _name="lot"
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
        required=True
    )
    price = fields.Monetary('Prix', required=True)
    subcontractor_ids = fields.Many2many('res.partner', string='Sous-traitants')
    is_finished = fields.Boolean('Terminé', default=False)
    quote_state = fields.Selection([
        ('draft', 'No Quote'),
        ('sent', 'Quote Sent'),
        ('accepted', 'Quote Accepted'),
        ('rejected', 'Quote Rejected')
    ], string='Quote Status', default='draft')

