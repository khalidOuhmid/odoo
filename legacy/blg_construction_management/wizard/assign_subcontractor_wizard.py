# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class AssignSubcontractorWizard(models.TransientModel):
    """Assistant pour assigner des sous-traitants à un chantier"""
    _name = 'blg.assign.subcontractor.wizard'
    _description = 'Assistant Attribution Sous-traitants'

    chantier_id = fields.Many2one('blg.chantier', string='Chantier', required=True, readonly=True)
    lot_ids = fields.Many2many('blg_contacts_extension.lot', string='Lots de travaux')
    subcontractor_ids = fields.Many2many(
        'res.partner', 
        string='Sous-traitants',
        domain="[('contact_type', '=', 'sous_traitant')]"
    )

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        if 'chantier_id' in self.env.context:
            chantier_id = self.env.context['chantier_id']
            chantier = self.env['blg.chantier'].browse(chantier_id)
            if chantier.exists():
                res['chantier_id'] = chantier_id
                # Get lots from chantier
                if chantier.lot_ids:
                    res['lot_ids'] = [(6, 0, chantier.lot_ids.mapped('lot_id').ids)]
        return res

    def action_assign_subcontractors(self):
        """Assigner les sous-traitants sélectionnés au chantier"""
        self.ensure_one()
        
        # Add subcontractors to the chantier
        if self.subcontractor_ids:
            self.chantier_id.write({
                'subcontractor_ids': [(6, 0, self.subcontractor_ids.ids)]
            })
        
        return {
            'type': 'ir.actions.act_window_close'
        }
