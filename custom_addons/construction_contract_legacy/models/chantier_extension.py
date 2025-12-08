# -*- coding: utf-8 -*-
"""
Chantier Extension
Extends construction.chantier model to add contract management
"""

from odoo import models, fields, api, _


class ChantierExtension(models.Model):
    """
    Extension of construction.chantier

    Adds contract management capabilities to construction sites
    """

    _inherit = 'construction.chantier'

    # ============================================================
    # CONTRACT RELATIONS
    # ============================================================

    contract_ids = fields.One2many(
        'construction.contract',
        'chantier_id',
        string='Subcontractor Contracts',
        help="Contracts signed with subcontractors for this site"
    )

    contract_count = fields.Integer(
        string='Contract Count',
        compute='_compute_contract_count',
        help="Number of contracts for this construction site"
    )

    # Contract statistics
    signed_contract_count = fields.Integer(
        string='Signed Contracts',
        compute='_compute_contract_statistics',
        help="Number of signed contracts"
    )

    pending_contract_count = fields.Integer(
        string='Pending Contracts',
        compute='_compute_contract_statistics',
        help="Number of contracts awaiting signature"
    )

    total_contract_amount = fields.Monetary(
        string='Total Contract Amount',
        compute='_compute_contract_statistics',
        currency_field='currency_id',
        help="Total amount of all contracts"
    )

    # ============================================================
    # COMPUTED FIELDS
    # ============================================================

    @api.depends('contract_ids')
    def _compute_contract_count(self):
        """Count total contracts"""
        for chantier in self:
            chantier.contract_count = len(chantier.contract_ids)

    @api.depends('contract_ids', 'contract_ids.state', 'contract_ids.total_amount_ttc')
    def _compute_contract_statistics(self):
        """Compute contract statistics"""
        for chantier in self:
            contracts = chantier.contract_ids

            chantier.signed_contract_count = len(contracts.filtered(lambda c: c.state == 'signed'))
            chantier.pending_contract_count = len(contracts.filtered(lambda c: c.state in ['sent', 'in_progress']))
            chantier.total_contract_amount = sum(contracts.mapped('total_amount_ttc'))

    # ============================================================
    # ACTION METHODS
    # ============================================================

    def action_view_contracts(self):
        """
        Open contracts view for this construction site
        Smart button action
        """
        self.ensure_one()

        action = self.env.ref('construction_contract.action_construction_contract').read()[0]
        action.update({
            'domain': [('chantier_id', '=', self.id)],
            'context': {
                'default_chantier_id': self.id,
                'search_default_chantier_id': self.id,
            },
        })

        # If only one contract, open it directly
        if self.contract_count == 1:
            action.update({
                'views': [(False, 'form')],
                'res_id': self.contract_ids[0].id,
            })

        return action

    def action_create_contract(self):
        """
        Quick action to create a new contract for this site
        Opens wizard with chantier pre-filled
        """
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': _('Create Contract'),
            'res_model': 'contract.creation.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_chantier_id': self.id,
            },
        }

    def action_open_contract_builder(self):
        """Open the live contract builder for this chantier."""
        self.ensure_one()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        url = f"{base_url}/contract/live-builder?chantier_id={self.id}"
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }