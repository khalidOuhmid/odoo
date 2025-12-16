# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class Lot(models.Model):
    _inherit = 'construction.lot'

    def action_generate_contract_wizard(self):
        """Open the contract creation wizard with defaults from this lot."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Générer Contrat'),
            'res_model': 'contract.creation.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_chantier_id': self.chantier_id.id,
                'default_subcontractor_id': self.subcontractor_id.id if self.execution_type == 'external' else False,
                'default_lot_ids': [(6, 0, [self.id])],
                'default_start_date': self.date_start_planned,
                'default_end_date': self.date_end_planned,
            }
        }
