# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class BlgLotType(models.Model):
    """
    Model for defining work section types (categories)
    """
    _name = 'blg.lot.type'
    _description = 'Work Section Type'
    _parent_name = "parent_id"
    _parent_store = True
    _rec_name = 'complete_name'
    _order = 'complete_name'
    
    name = fields.Char('Name', required=True, translate=True)
    complete_name = fields.Char('Complete Name', compute='_compute_complete_name', store=True)
    parent_id = fields.Many2one('blg.lot.type', 'Parent Category', index=True, ondelete='cascade')
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many('blg.lot.type', 'parent_id', 'Child Categories')
    
    # Link to products and lots
    product_ids = fields.Many2many('product.product', 'product_lot_type_rel', 'lot_type_id', 'product_id', 
                                  string='Recommended Products')
    lot_ids = fields.One2many('blg_contacts_extension.lot', 'type_id', string='Trade Categories')
    
    # Additional fields
    active = fields.Boolean(default=True)
    code = fields.Char('Code')
    
    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for category in self:
            if category.parent_id:
                category.complete_name = '%s / %s' % (category.parent_id.complete_name, category.name)
            else:
                category.complete_name = category.name
