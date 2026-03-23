# -*- coding: utf-8 -*-
"""
GED : Gestion Électronique de Documents centralisée sur construction.chantier.

construction.document est un enregistrement de métadonnées pointant vers
un ir.attachment. Le binaire n'est JAMAIS stocké en double.
"""
from odoo import models, fields, api

from odoo.addons.construction_core.utils.logger import get_logger

_logger = get_logger(__name__)


class DocumentTag(models.Model):
    """Tag libre pour classer les documents (Contrat, Rapport, CCTP…)."""

    _name = 'construction.document.tag'
    _description = 'Tag de Document Chantier'
    _order = 'name'

    name = fields.Char(string='Nom', required=True, translate=True)
    color = fields.Integer(string='Couleur', default=0)

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Le nom du tag doit être unique.'),
    ]


class Document(models.Model):
    """
    Enregistrement de métadonnées GED lié à un ir.attachment.

    Règle absolue : ne jamais copier le champ 'datas' d'un attachment
    dans ce modèle. Ce modèle pointe uniquement vers l'attachment existant.
    """

    _name = 'construction.document'
    _description = 'Document Chantier (GED)'
    _order = 'upload_date desc, id desc'
    _rec_name = 'name'

    # ============= Relations principales ============= #
    chantier_id = fields.Many2one(
        'construction.chantier',
        string='Chantier',
        required=True,
        ondelete='cascade',
        index=True,
    )
    attachment_id = fields.Many2one(
        'ir.attachment',
        string='Pièce jointe',
        required=True,
        ondelete='cascade',
    )

    # ============= Métadonnées (related depuis attachment) ============= #
    name = fields.Char(
        string='Nom',
        related='attachment_id.name',
        store=True,
        readonly=False,
    )
    mimetype = fields.Char(
        string='Type MIME',
        related='attachment_id.mimetype',
        store=True,
    )
    file_size = fields.Integer(
        string='Taille (octets)',
        related='attachment_id.file_size',
        store=True,
    )

    # ============= Taxonomie ============= #
    tag_ids = fields.Many2many(
        'construction.document.tag',
        string='Tags',
    )
    lot_id = fields.Many2one(
        'construction.lot',
        string='Lot associé',
        ondelete='set null',
    )

    # ============= Traçabilité source ============= #
    source_model = fields.Char(
        string='Modèle source',
        help="Modèle Odoo ayant généré ce document (ex: construction.contract)",
    )
    source_id = fields.Integer(
        string='ID source',
        help="ID de l'enregistrement source",
    )
    upload_date = fields.Datetime(
        string="Date d'upload",
        default=fields.Datetime.now,
        readonly=True,
    )
    uploaded_by_id = fields.Many2one(
        'res.users',
        string='Uploadé par',
        default=lambda self: self.env.user,
        readonly=True,
    )

    # ============= Calculés ============= #
    file_size_human = fields.Char(
        string='Taille',
        compute='_compute_file_size_human',
    )
    url = fields.Char(
        string='URL',
        compute='_compute_url',
    )

    @api.depends('file_size')
    def _compute_file_size_human(self):
        for rec in self:
            size = rec.file_size or 0
            if size < 1024:
                rec.file_size_human = '%d o' % size
            elif size < 1024 * 1024:
                rec.file_size_human = '%.1f Ko' % (size / 1024)
            else:
                rec.file_size_human = '%.1f Mo' % (size / (1024 * 1024))

    @api.depends('attachment_id')
    def _compute_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for rec in self:
            if rec.attachment_id:
                rec.url = '%s/web/content/%d?download=true' % (base_url, rec.attachment_id.id)
            else:
                rec.url = False

    # ============= Actions ============= #
    def action_download(self):
        """Ouvre l'attachment pour téléchargement/prévisualisation."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': self.url,
            'target': 'new',
        }

    # ============= Helpers ============= #
    @api.model
    def _get_or_create_tag(self, tag_name):
        """
        Récupère ou crée un tag de document par son nom.
        Utilisé par les modules tiers pour tagger automatiquement leurs PDF.
        """
        tag = self.env['construction.document.tag'].search(
            [('name', '=', tag_name)], limit=1
        )
        if not tag:
            tag = self.env['construction.document.tag'].sudo().create(
                {'name': tag_name}
            )
            _logger.email_event('ged_tag_created', 'Tag GED créé : %s' % tag_name)
        return tag
