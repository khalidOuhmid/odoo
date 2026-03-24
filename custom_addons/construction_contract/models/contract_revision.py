# -*- coding: utf-8 -*-
"""
Contract Revision Model
Archives previous PDF versions each time a contract is regenerated.
Enables full revision history with download access for both backend users and portal signatories.
"""

from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class ConstructionContractRevision(models.Model):
    _name = 'construction.contract.revision'
    _description = 'Révision de contrat'
    _order = 'version_number desc'

    contract_id = fields.Many2one(
        'construction.contract',
        string='Contrat',
        required=True,
        ondelete='cascade',
        index=True,
    )

    version_number = fields.Integer(
        string='Version',
        required=True,
    )

    pdf_document = fields.Binary(
        string='PDF',
        attachment=True,
        help="PDF archivé de cette version du contrat",
    )

    pdf_filename = fields.Char(
        string='Nom du fichier',
        compute='_compute_pdf_filename',
        store=True,
    )

    pdf_hash = fields.Char(
        string='Empreinte SHA-256',
        readonly=True,
        help="Hash du PDF au moment de l'archivage — garantit l'intégrité",
    )

    generated_by = fields.Many2one(
        'res.users',
        string='Généré par',
        readonly=True,
    )

    generated_at = fields.Datetime(
        string='Généré le',
        default=fields.Datetime.now,
        readonly=True,
    )

    state_at_generation = fields.Char(
        string='État lors de la génération',
        readonly=True,
    )

    reason = fields.Text(
        string='Motif de régénération',
        help="Raison pour laquelle ce contrat a été régénéré (saisi par l'utilisateur)",
    )

    is_superseded = fields.Boolean(
        string='Archivée',
        default=False,
        help="True si cette révision a été remplacée par une version plus récente",
    )

    @api.depends('contract_id', 'version_number')
    def _compute_pdf_filename(self):
        for rev in self:
            if rev.contract_id and rev.version_number:
                name = (rev.contract_id.name or 'contrat').replace('/', '_')
                rev.pdf_filename = f"{name}_v{rev.version_number}.pdf"
            else:
                rev.pdf_filename = 'contrat.pdf'

    def action_download(self):
        """Télécharger le PDF de cette révision."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': (
                f'/web/content/construction.contract.revision'
                f'/{self.id}/pdf_document/{self.pdf_filename}?download=true'
            ),
            'target': 'self',
        }
