# -*- coding: utf-8 -*-
from odoo import models, fields, api
from . import models

class new_project(models.Model):
     _name = 'new_project.new_project'
     _description = 'Nouveau Projet'

     name = fields.Char(string="Nom du projet", required=True)
     value = fields.Integer()
     value2 = fields.Float(compute="_value_pc", store=True)
     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100

