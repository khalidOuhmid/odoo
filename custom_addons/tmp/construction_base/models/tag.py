# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ChantierTag(models.Model):
    """
    Tags pour catégoriser les chantiers
    """
    _name = 'construction.tag'
    _description = 'Étiquette de chantier'
    _order = 'name'

    name = fields.Char('Nom', required=True)
    color = fields.Integer('Couleur', default=0)
    active = fields.Boolean('Actif', default=True)
    
    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'Le nom de l\'étiquette doit être unique !'),
    ] 