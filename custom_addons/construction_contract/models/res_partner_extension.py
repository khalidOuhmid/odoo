# -*- coding: utf-8 -*-
"""
Partner Extension
Extends res.partner to add contract tracking for subcontractors
"""

from odoo import models, fields, api, _


class ResPartnerExtension(models.Model):
    """
    Extension of res.partner

    Adds contract tracking for subcontractors
    """

    _inherit = 'res.partner'

    # ============================================================
    # CONTRACT RELATIONS
    # ============================================================

    subcontractor_contract_ids = fields.One2many(
        'construction.contract',
        'subcontractor_id',
        string='Subcontractor Contracts',
        domain="[('subcontractor_id', '=', id)]",
        help="Contracts where this partner is the subcontractor"
    )

    subcontractor_contract_count = fields.Integer(
        string='Contract Count',
        compute='_compute_subcontractor_contract_count',
        help="Number of contracts as subcontractor"
    )

    # ============================================================
    # COMPUTED FIELDS
    # ============================================================

    @api.depends('subcontractor_contract_ids')
    def _compute_subcontractor_contract_count(self):
        """Count contracts as subcontractor"""
        for partner in self:
            partner.subcontractor_contract_count = len(partner.subcontractor_contract_ids)

    # ============================================================
    # ACTION METHODS
    # ============================================================

    def action_view_subcontractor_contracts(self):
        """View contracts where this partner is subcontractor"""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': _('Subcontractor Contracts'),
            'res_model': 'construction.contract',
            'view_mode': 'tree,form',
            'domain': [('subcontractor_id', '=', self.id)],
            'context': {'default_subcontractor_id': self.id},
        }
