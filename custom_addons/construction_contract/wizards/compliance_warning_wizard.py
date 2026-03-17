# -*- coding: utf-8 -*-
from odoo import models, fields, _


class ContractComplianceWarningWizard(models.TransientModel):
    """
    Warning wizard shown when a subcontractor has non-compliant documents
    at contract creation time.

    Lets the user acknowledge the risk and proceed anyway instead of being
    blocked by a ValidationError.
    """
    _name = 'contract.compliance.warning.wizard'
    _description = 'Avertissement Conformité Sous-Traitant'

    creation_wizard_id = fields.Many2one(
        'contract.creation.wizard',
        string='Assistant Contrat',
        required=True,
        ondelete='cascade',
    )
    warning_message = fields.Text(
        string='Avertissement',
        readonly=True,
    )

    def action_force_proceed(self):
        """Force contract creation despite non-compliant documents."""
        self.ensure_one()
        self.creation_wizard_id.bypass_compliance_check = True
        return self.creation_wizard_id.action_create_contract()
