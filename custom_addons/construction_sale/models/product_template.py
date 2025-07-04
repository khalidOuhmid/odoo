# models/product_template.py
from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    lot_ids = fields.Many2many(
        'lot',
        'product_lot_rel',
        'product_id',
        'lot_id',
        string='Lots de construction',
        help="Lots de construction où ce produit/service peut être utilisé"
    )

    construction_specialty = fields.Selection([
        ('general', 'Général'),
        ('demolition', 'Démolition'),
        ('maconnerie', 'Maçonnerie'),
        ('platrerie', 'Plâtrerie'),
        ('plomberie_cvc', 'Plomberie CVC'),
        ('electricite', 'Électricité'),
        ('menuiserie_ext', 'Menuiserie extérieure'),
        ('menuiserie_int', 'Menuiserie intérieure'),
        ('peinture', 'Peinture & finition'),
        ('sol', 'Sol souple et parquet'),
        ('carrelage', 'Carrelage & faïence'),
    ], string='Spécialité construction')


class ProductProduct(models.Model):
    _inherit = 'product.product'

    lot_ids = fields.Many2many(related='product_tmpl_id.lot_ids', readonly=False)
    construction_specialty = fields.Selection(related='product_tmpl_id.construction_specialty', readonly=False)
