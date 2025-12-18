# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class ContractValidationWizard(models.TransientModel):
    _name = 'construction.contract.validation.wizard'
    _description = 'Wizard de validation pré-contrat'

    lot_id = fields.Many2one('construction.lot', string="Lot", required=True, readonly=True)
    missing_items = fields.Html(string="Documents Manquants", readonly=True)
    
    def action_force_generate(self):
        """Forcer la génération malgré les manquants."""
        self.ensure_one()
        lot = self.lot_id
        
        # Log dans le chatter
        lot.chantier_id.message_post(
            body=_("⚠️ Contrat généré de force pour le lot <b>%s</b> malgré les documents manquants :<br/>%s") % (
                lot.name, self.missing_items
            ),
            message_type='comment',
            subtype_xmlid='mail.mt_note'
        )
        
        # Relancer la génération avec le flag pour ignorer la validation
        return lot.with_context(force_contract_validation=True).action_generate_contract_wizard()

    def action_cancel(self):
        """Annuler"""
        return {'type': 'ir.actions.act_window_close'}
