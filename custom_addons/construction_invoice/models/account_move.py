# -*- coding: utf-8 -*-

from odoo import models, fields

class AccountMove(models.Model):
    _inherit = 'account.move'

    chantier_id = fields.Many2one('construction.chantier', string='Chantier')
