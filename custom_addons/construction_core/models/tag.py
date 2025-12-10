# -*- coding: utf-8 -*-
from odoo import models, fields

class ConstructionTag(models.Model):
    _name = "construction.tag"
    _description = "Étiquette de Chantier"
    
    name = fields.Char('Nom', required=True)
    color = fields.Integer('Couleur')

    _sql_constraints = [
        ('name_uniq', 'unique (name)', "Le nom de l'étiquette doit être unique !"),
    ]
