# -*- coding: utf-8 -*-
"""
Extension du modèle construction.contract pour le module sous-traitant.

Ajoute deux champs de synthèse utiles dans la vue liste du menu Sous-traitants :
- lot_names : noms des lots (lecture seule, affichage)
- amount_total : total des prix de lot (différent du total_amount_ttc issu des BdC)
"""

from odoo import api, fields, models

from odoo.addons.construction_core.utils.logger import get_logger

_logger = get_logger(__name__)


class ConstructionContractSubcontractorExtension(models.Model):
    """
    Extension sous-traitant du contrat.
    Tous les champs métier (state, parties, signature, BdC) sont définis
    dans construction_contract. Ce modèle n'ajoute que des champs de synthèse.
    """
    _inherit = 'construction.contract'

    # ============= CHAMPS ADDITIFS SOUS-TRAITANT ============= #

    lot_names = fields.Char(
        string='Lots',
        compute='_compute_lot_names_sub',
        store=False,
    )

    amount_total = fields.Monetary(
        string='Montant lots',
        compute='_compute_amount_total_sub',
        store=True,
        currency_field='currency_id',
        help="Somme des prix des lots concernés (distinct du montant issu des BdC).",
    )

    # ============= COMPUTED ============= #

    @api.depends('lot_ids')
    def _compute_lot_names_sub(self):
        for contract in self:
            contract.lot_names = ', '.join(contract.lot_ids.mapped('name'))

    @api.depends('lot_ids.price')
    def _compute_amount_total_sub(self):
        for contract in self:
            contract.amount_total = sum(contract.lot_ids.mapped('price'))


class PurchaseOrderSubcontractorExtension(models.Model):
    """Lie un BdC à un contrat de sous-traitance."""
    _inherit = 'purchase.order'

    contract_id = fields.Many2one(
        'construction.contract',
        string='Contrat',
        ondelete='set null',
        help="Contrat de sous-traitance associé à ce bon de commande.",
    )
