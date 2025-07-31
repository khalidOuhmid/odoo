from odoo import models, fields, api

class lot(models.Model):
    _name = 'lot'
    _description = 'Construction lot'

    name = fields.Char('Name', required=True)
    code = fields.Char('Code' , required=True)
    color = fields.Integer(
        string='Color Index',
        default=0,
        help="Color index for tag styling (0-11)"
    )
    # Contrainte d'unicité supprimée pour permettre les codes uniques par chantier
    # _sql_constraints = [
    #     ('code_unique', 'unique(code)', 'Le code doit être unique'),
    # ]