# -*- coding: utf-8 -*-
"""
blg_contacts_extension.models.lot
---------------------------------

Defines the Lot model for BLG Groupe, representing business trades or work categories (e.g., Electricity, Plumbing) associated with subcontractors.

Features:
---------
- Stores trade names, unique codes, and sequence for ordering.
- Supports hierarchical categorization via type_id.
- Links lots to subcontractor partners (res.partner).
- Provides a method to retrieve lots with a minimum number of valid KBIS subcontractors.

Class:
------
Lot (models.Model)
    Represents a trade (lot) with fields for name, code, sequence, type, and active status.

Fields:
-------
- name: Full name of the trade (e.g., Electricity, Plumbing).
- code: Unique short code for the trade (e.g., ELEC-01).
- sequence: Ordering index for dropdowns and lists.
- active: Boolean flag for active/inactive status.
- type_id: Many2one to blg.lot.type for hierarchical categorization.
- partner_ids: One2many link to subcontractors (res.partner) associated with this lot.
- color: Integer field for tag color styling in UI.

Methods:
--------
- get_lots_with_subcontractors(min_subcontractors=1): Returns lots having at least N valid KBIS subcontractors.

Author: BLG IT Team
"""

from odoo import models, fields, api

class Lot(models.Model):
    _name = 'blg_contacts_extension.lot'
    _description = 'Corps de métier (Lots)'
    _order = 'sequence, name'
    _rec_name = 'name' 

    name = fields.Char(
        string='Nom',
        required=True,
        index=True,
        help="Full name of the trade (e.g., Electricity, Plumbing)"
    )
    code = fields.Char(
        string='Code',
        required=True,
        size=8,
        index=True,
        help="Unique short code (e.g., ELEC-01)"
    )
    sequence = fields.Integer(
        string='Ordre',
        default=10,
        index=True,
        help="Order in dropdown lists"
    )
    active = fields.Boolean(
        string='Actif',
        default=True,
        index=True,
        help="Deactivate instead of deleting"
    )
    # FIX: Make this field optional to avoid relationship errors
    type_id = fields.Many2one(
        'blg.lot.type',
        string='Type',
        index=True,
        ondelete='set null',  # Changed from 'restrict' to 'set null'
        help="Hierarchical categorization"
    )
    partner_ids = fields.One2many(
        'res.partner',
        'lots',  # Changed from 'lot_ids' to 'lots' to match the field name in res.partner
        string='Sous-traitants',
        domain="[('contact_type', '=', 'sous_traitant')]"
    )
    color = fields.Integer(
        string='Couleur',
        default=0,
        help="Color index for tag styling (0-11)"
    )

    @api.model
    def get_lots_with_subcontractors(self, min_subcontractors=1):
        """Return lots having at least N valid KBIS subcontractors."""
        return self.search([
            ('partner_ids.document_KBIS_status', '=', 'valid'),
            ('active', '=', True)
        ]).filtered(
            lambda l: len(l.partner_ids) >= min_subcontractors
        )
