from odoo import models, fields, api, _

class LotExtension(models.Model):
    _inherit = 'lot'
    _name="lot"

    price = fields.Monetary('Prix', required=True)
    subcontractor_ids = fields.Many2one('res.partner', string='Subcontractor',)
    is_finished = fields.Boolean('Terminé', default=False)

