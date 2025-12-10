# -*- coding: utf-8 -*-
from odoo import models, fields


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    chantier_id = fields.Many2one(
        'construction.chantier',
        string='Chantier',
        help="Chantier lié à ce devis",
        tracking=True
    )


class Chantier(models.Model):
    """
    Extension to add quotation_ids after sale.order is fully set up.
    
    This MUST be in a file that loads after chantier.py (alphabetically).
    Since 's' > 'c', this works.
    """
    _inherit = 'construction.chantier'

    quotation_ids = fields.One2many(
        'sale.order', 'chantier_id',
        string='Devis'
    )
