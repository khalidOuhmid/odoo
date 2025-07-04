from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Relations avec les chantiers de construction
    chantier_ids = fields.One2many(
        'construction.chantier',
        'client',
        string='Chantiers',
        help='Chantiers dont ce partenaire est le client'
    )

    def action_view_chantiers(self):
        """Action pour voir les chantiers associés au partenaire"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'Chantiers - {self.name}',
            'res_model': 'construction.chantier',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.chantier_ids.ids)],
            'context': {
                'default_client': self.id if self.is_company else False,
            },
            'target': 'current',
        } 