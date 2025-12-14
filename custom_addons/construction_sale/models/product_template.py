# -*- coding: utf-8 -*-
"""
Product Template Construction Extension
========================================
Adds construction-specific pricing and specification fields.
"""

from odoo import models, fields, api
from typing import Any


class ProductTemplate(models.Model):
    """Extended Product Template with Construction pricing models.
    
    Supports multiple pricing strategies:
    - Standard (per unit)
    - Per square meter (m²)
    - Per linear meter (ml)
    - Per weight (kg)
    """
    _inherit = 'product.template'

    # ============================================================
    # CONSTRUCTION PRICING
    # ============================================================

    price_type = fields.Selection(
        [
            ('standard', 'Standard (Unit)'),
            ('m2', 'Per Square Meter (m²)'),
            ('ml', 'Per Linear Meter (ml)'),
            ('weight', 'Per Kilogram (kg)'),
        ],
        string='Pricing Type',
        default='standard',
        help="Determines how this product is priced in construction quotes"
    )

    # Field required by some Odoo views - prevents OWL crash
    service_to_purchase = fields.Boolean(
        string='Subcontracting Service',
        default=False,
        help="If checked, this service will trigger a purchase order for subcontracting"
    )

    price_type_label = fields.Char(
        string='Pricing Label',
        compute='_compute_price_type_label',
        store=True,
        help="Human-readable pricing type for display"
    )

    construction_specialty = fields.Char(
        string='Construction Specialty',
        compute='_compute_construction_specialty',
        help="Categorization for construction workflows (e.g., 'Flooring', 'Plumbing')"
    )

    # ============================================================
    # MEASUREMENT VALUES
    # ============================================================

    surface_required = fields.Boolean(
        string='Surface Input Required',
        compute='_compute_required_fields',
        help="True if pricing requires surface area"
    )

    length_required = fields.Boolean(
        string='Length Input Required',
        compute='_compute_required_fields',
        help="True if pricing requires length"
    )

    weight_required = fields.Boolean(
        string='Weight Input Required',
        compute='_compute_required_fields',
        help="True if pricing requires weight"
    )

    surface_value = fields.Float(
        string='Reference Surface (m²)',
        help="Default surface area for calculations"
    )

    length_value = fields.Float(
        string='Reference Length (m)',
        help="Default length for calculations"
    )

    weight_value = fields.Float(
        string='Reference Weight (kg)',
        help="Default weight for calculations"
    )

    # ============================================================
    # COMPUTED FIELDS
    # ============================================================

    @api.depends('price_type')
    def _compute_price_type_label(self) -> None:
        """Generate human-readable label for pricing type.
        
        Returns:
            None (updates field in-place)
        """
        labels = {
            'standard': 'Unit',
            'm2': 'm²',
            'ml': 'ml',
            'weight': 'kg',
        }
        for product in self:
            product.price_type_label = labels.get(product.price_type, 'Unit')

    @api.depends('price_type')
    def _compute_required_fields(self) -> None:
        """Determine which input fields are required based on pricing type.
        
        Returns:
            None (updates fields in-place)
        """
        for product in self:
            product.surface_required = product.price_type == 'm2'
            product.length_required = product.price_type == 'ml'
            product.weight_required = product.price_type == 'weight'

    @api.depends('categ_id', 'price_type')
    def _compute_construction_specialty(self) -> None:
        """Derive construction specialty from category and pricing.
        
        Returns:
            None (updates field in-place)
        """
        for product in self:
            specialty = product.categ_id.name if product.categ_id else 'General'
            if product.price_type == 'm2':
                specialty += ' (Surface)'
            elif product.price_type == 'ml':
                specialty += ' (Linear)'
            product.construction_specialty = specialty
