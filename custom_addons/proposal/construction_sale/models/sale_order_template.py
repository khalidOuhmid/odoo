# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class SaleOrderTemplate(models.Model):
    _inherit = 'sale.order.template'

    # We might want to define default lots for a template?
    # Or just generic "Attributes" that get mapped.
    # For simplicity, we just allow lines to have construction attributes.
    pass

class SaleOrderTemplateLine(models.Model):
    _inherit = 'sale.order.template.line'

    # Support for Construction attributes in Templates
    construction_lot_id = fields.Many2one('construction.lot', string='Default Lot')
    # Note: Linking to a specific lot ID in a template is risky because Lot IDs are per-chantier or generic?
    # Actually, legacy system had "Lot Categories" or "Generic Lots". 
    # In our new Core, 'construction.lot' is linked to 'chantier'. 
    # So a template cannot link to a specific 'construction.lot' because that lot belongs to a specific project.
    
    # SOLUTION: Use a Char field for "Lot Name" or a separate "Lot Category" model if we want loose coupling.
    # Or, creating a "Template Lot" concept.
    # The user manual input "Lot: Electricité" in the wizard created a section.
    # Let's add a Char field `lot_name` to the template line. When instantiating the quote, we find/create the lot/section.
    
    construction_lot_name = fields.Char(
        string="Lot Name", 
        help="Name of the Lot/Section this line belongs to (e.g. 'Electricity')"
    )
    
    dimension_length = fields.Float(string='Length (m)')
    dimension_width = fields.Float(string='Width (m)')
    is_dimensional = fields.Boolean(string="Use Dimensions")

    def _get_sale_order_line_multiline_description_sale(self, product):
        return product.get_product_multiline_description_sale()
