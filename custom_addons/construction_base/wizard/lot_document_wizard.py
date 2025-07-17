from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class LotDocumentWizard(models.TransientModel):
    _name = 'lot.document.wizard'
    _description = 'Gestion des documents du lot'

    lot_id = fields.Many2one('construction.lot', string='Lot', required=True, readonly=True)
    chantier_id = fields.Many2one('construction.chantier', string='Chantier', required=True, readonly=True)
    subcontractor_id = fields.Many2one('res.partner', string='Sous-traitant', required=True, readonly=True)

    document_cctp = fields.Binary(string="CCTP", attachment=True)
    document_subcontractor_contract = fields.Binary(string="Contrat de sous-traitance", attachment=True)

    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        lot = self.env['construction.lot'].browse(self.env.context.get('active_id'))
        if lot:
            res['lot_id'] = lot.id
            # Récupérer le chantier via la relation inverse
            chantier = self.env['construction.chantier'].search([
                ('lots_ids', 'in', lot.id)
            ], limit=1)
            res['chantier_id'] = chantier.id if chantier else False
            if lot.subcontractor_ids:
                res['subcontractor_id'] = lot.subcontractor_ids[0].id
            # Pré-remplir les documents si présents
            res['document_cctp'] = lot.document_cctp
            res['document_subcontractor_contract'] = lot.document_subcontractor_contract
        return res

    def action_save_documents(self):
        self.ensure_one()
        lot = self.lot_id
        vals = {}
        if self.document_cctp:
            vals['document_cctp'] = self.document_cctp
        if self.document_subcontractor_contract:
            vals['document_subcontractor_contract'] = self.document_subcontractor_contract
        if vals:
            lot.write(vals)
        return {'type': 'ir.actions.act_window_close'}

    def action_send_contract_email(self):
        self.ensure_one()
        # On suppose que le lot a un sous-traitant principal
        partner = self.subcontractor_id
        chantier = self.chantier_id
        if not partner:
            raise ValidationError("Aucun sous-traitant assigné à ce lot.")
        # On utilise l'action du chantier pour envoyer l'email
        chantier.action_send_contract_to_subcontractor()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Email envoyé',
                'message': 'L\'email de dépôt a été envoyé au sous-traitant.',
                'type': 'success',
            }
        }