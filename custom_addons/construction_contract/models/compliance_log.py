# -*- coding: utf-8 -*-
"""
Log permanent des dérogations à la conformité documentaire.
Chaque dérogation accordée via construction.compliance.override.wizard
crée un enregistrement immuable dans ce modèle.
"""

from odoo import fields, models, _

from odoo.addons.construction_core.utils.logger import get_logger

_logger = get_logger(__name__)


class ComplianceOverrideLog(models.Model):
    """
    Journal permanent des dérogations de conformité.
    Immuable : aucune suppression autorisée (pas de unlink).
    """

    _name = 'construction.compliance.override.log'
    _description = 'Journal de Dérogation Conformité'
    _order = 'override_date desc, id desc'
    _rec_name = 'partner_id'

    contract_id = fields.Many2one(
        'construction.contract',
        string='Contrat',
        ondelete='set null',
    )

    chantier_id = fields.Many2one(
        'construction.chantier',
        string='Chantier',
        ondelete='set null',
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Sous-traitant',
        ondelete='set null',
    )

    non_compliant_docs = fields.Text(
        string='Documents non conformes',
        readonly=True,
    )

    override_reason = fields.Text(
        string='Raison de la dérogation',
        readonly=True,
        required=True,
    )

    override_by_id = fields.Many2one(
        'res.users',
        string='Accordé par',
        readonly=True,
        ondelete='set null',
    )

    override_date = fields.Datetime(
        string='Date de dérogation',
        readonly=True,
        required=True,
        default=lambda self: fields.Datetime.now(),
    )

    def unlink(self):
        _logger.compliance_check(self, 'unlink_attempt', passed=False)
        raise models.AccessError(_(
            "Les journaux de dérogation de conformité ne peuvent pas être supprimés "
            "pour des raisons de traçabilité réglementaire."
        ))
