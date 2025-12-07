# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ConstructionSignatureZone(models.Model):
    _name = 'construction.signature.zone'
    _description = 'Signature Zone Configuration'
    _order = 'page_number, sequence'

    template_id = fields.Many2one(
        'construction.document.template',
        string='Template',
        required=True,
        ondelete='cascade'
    )
    sequence = fields.Integer(string='Séquence', default=10)

    zone_type = fields.Selection([
        ('company', 'Signature entreprise'),
        ('subcontractor', 'Signature sous-traitant'),
        ('witness', 'Signature témoin'),
    ], string='Type', required=True, default='subcontractor')

    # Position (percentage from top-left)
    position_x = fields.Float(string='Position X (%)', default=10.0)
    position_y = fields.Float(string='Position Y (%)', default=80.0)
    width = fields.Float(string='Largeur (px)', default=200.0)
    height = fields.Float(string='Hauteur (px)', default=80.0)

    # Labels
    label = fields.Char(string='Libellé', default='Signature')
    sublabel = fields.Char(string='Sous-libellé', default='Date et lieu')

    # Page placement
    page_number = fields.Integer(
        string='Page',
        default=-1,
        help='-1 = dernière page'
    )

    @api.constrains('position_x', 'position_y')
    def _check_position_bounds(self):
        """Validate position is within 0-100% bounds."""
        for record in self:
            if not (0 <= record.position_x <= 100):
                raise ValidationError(
                    "La position X doit être entre 0 et 100%."
                )
            if not (0 <= record.position_y <= 100):
                raise ValidationError(
                    "La position Y doit être entre 0 et 100%."
                )

    @api.constrains('width', 'height')
    def _check_dimensions(self):
        """Validate dimensions are positive."""
        for record in self:
            if record.width <= 0 or record.height <= 0:
                raise ValidationError(
                    "Les dimensions doivent être positives."
                )
