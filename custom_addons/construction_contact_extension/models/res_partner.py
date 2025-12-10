# -*- coding: utf-8 -*-
"""
Extension Partner - Données Légales Françaises
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re

class Partner(models.Model):
    _inherit = 'res.partner'

    siren = fields.Char(string='SIREN', size=9, help="Numéro SIREN à 9 chiffres")

    @api.constrains('siren')
    def _check_siren(self):
        """Validate SIREN format (9 digits)."""
        for partner in self:
            if partner.siren:
                # Remove spaces and check if 9 digits
                siren_clean = partner.siren.replace(' ', '')
                if not re.match(r'^\d{9}$', siren_clean):
                    raise ValidationError(_("Le SIREN doit contenir exactement 9 chiffres."))
                # Update with cleaned version
                if siren_clean != partner.siren:
                    partner.siren = siren_clean
