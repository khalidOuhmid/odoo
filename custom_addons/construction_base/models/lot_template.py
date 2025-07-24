from odoo import models, fields, api


class ConstructionLotTemplate(models.Model):
    _name = 'construction.lot.template'
    _description = 'Template de lot de construction'
    _order = 'name'

    name = fields.Char(
        string='Nom du lot',
        required=True
    )
    
    code = fields.Char(
        string='Code',
        required=True
    )
    
    color = fields.Integer(
        string='Couleur',
        default=0
    )
    
    description = fields.Text(
        string='Description'
    )
    
    active = fields.Boolean(
        string='Actif',
        default=True
    )
    
    def create_lot_for_chantier(self, chantier_id):
        """
        Crée un lot spécifique pour un chantier basé sur ce template
        """
        self.ensure_one()
        
        return self.env['construction.lot'].create({
            'name': self.name,
            'code': self.code,
            'color': self.color,
            'description': self.description,
            'chantier_id': chantier_id,
            'price': 0.0,
        })
