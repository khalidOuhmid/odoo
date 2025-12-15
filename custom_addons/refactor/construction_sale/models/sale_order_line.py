# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # ==============================================================================================
    #                                      ESTIMATION DETAILS
    # ==============================================================================================
    
    construction_lot_id = fields.Many2one(
        'construction.lot',
        string='Lot Travaux',
        help="Technical link to a specific Work Package."
    )
    
    location = fields.Char(string='Localisation', help="Ex: Rez-de-chaussée, Cuisine...")
