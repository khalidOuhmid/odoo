from odoo import models, fields, api, _

class BlgAssignSubcontractorWizard(models.TransientModel):
    _name = 'blg.assign.subcontractor.wizard'
    _description = 'Assign Subcontractors to Project'

    chantier_id = fields.Many2one('blg.chantier', string='Chantier', required=True)
    lot_id = fields.Many2one('blg_contacts_extension.lot', string='Corps de métier')
    subcontractor_ids = fields.Many2many(
        'res.partner',
        string='Sous-traitants',
        domain="[('contact_type', '=', 'sous_traitant')]",
        required=True
    )

    def action_confirm(self):
        self.ensure_one()
        return self.chantier_id.action_assign_subcontractors(
            subcontractor_ids=self.subcontractor_ids.ids,
            lot_id=self.lot_id.id if self.lot_id else None
        )
