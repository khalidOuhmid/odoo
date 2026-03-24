# -*- coding: utf-8 -*-
"""
Contract Regeneration Wizard
Forces the user to supply a mandatory reason before regenerating a contract.
Prevents accidental regenerations and guarantees full traceability.
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ContractRegenerateWizard(models.TransientModel):
    _name = 'contract.regenerate.wizard'
    _description = 'Wizard de régénération du contrat'

    contract_id = fields.Many2one(
        'construction.contract',
        string='Contrat',
        required=True,
        readonly=True,
    )

    contract_name = fields.Char(
        related='contract_id.name',
        readonly=True,
    )

    contract_state = fields.Selection(
        related='contract_id.state',
        readonly=True,
    )

    reason = fields.Text(
        string='Motif de régénération',
        required=True,
        help="Expliquez pourquoi ce contrat doit être régénéré. "
             "Ce motif sera enregistré dans l'historique des révisions et le chatter.",
    )

    notify_subcontractor = fields.Boolean(
        string='Notifier le sous-traitant',
        default=True,
        help="Envoie un email au sous-traitant pour l'informer qu'une nouvelle version "
             "du contrat est disponible (recommandé si le contrat avait déjà été envoyé).",
    )

    revision_count = fields.Integer(
        string='Révisions existantes',
        compute='_compute_revision_count',
    )

    @api.depends('contract_id')
    def _compute_revision_count(self):
        for wiz in self:
            wiz.revision_count = len(wiz.contract_id.revision_ids) if wiz.contract_id else 0

    def action_confirm(self):
        """Lance la régénération sécurisée et archive l'ancienne version."""
        self.ensure_one()
        if not self.reason or not self.reason.strip():
            raise UserError(_("Le motif de régénération est obligatoire."))
        self.contract_id._do_regenerate_contract(
            reason=self.reason.strip(),
            notify=self.notify_subcontractor,
        )
        return {'type': 'ir.actions.act_window_close'}
