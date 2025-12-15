from odoo import models, fields

class BlgChantierTag(models.Model):
    """
    Tags/labels for categorizing construction projects.
    """
    _name = 'blg.chantier.tag'
    _description = 'Project Tag'

    name = fields.Char('Name', required=True)
    color = fields.Integer('Color Index')

    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'Tag name must be unique!')
    ]
