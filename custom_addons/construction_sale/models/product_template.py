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
    # LOT CATEGORY ASSIGNMENT (US-SAL-002)
    # ============================================================
    
    # REFACTORED: Changed from Many2one to Many2many to support multiple categories
    lot_category_ids = fields.Many2many(
        'construction.lot.category',
        'product_template_lot_category_rel',
        'product_id',
        'category_id',
        string='Catégories de Lot',
        help="Catégories de lot construction (ex: Plomberie, Électricité). Un produit peut appartenir à plusieurs catégories."
    )
    
    # Keep old field for backwards compatibility (computed from new field)
    lot_category_id = fields.Many2one(
        'construction.lot.category',
        string='Catégorie de Lot (legacy)',
        compute='_compute_lot_category_id',
        store=True,
        help="Première catégorie de lot (pour compatibilité)"
    )
    
    @api.depends('lot_category_ids')
    def _compute_lot_category_id(self):
        for product in self:
            product.lot_category_id = product.lot_category_ids[:1] if product.lot_category_ids else False
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Auto-generate default_code from lot codes + name (US-SAL-002)
            lot_ids = vals.get('lot_category_ids')
            if lot_ids and vals.get('name') and not vals.get('default_code'):
                # Handle both list of IDs and Odoo command format [(6, 0, [ids])]
                if isinstance(lot_ids, list) and lot_ids:
                    if isinstance(lot_ids[0], (list, tuple)) and lot_ids[0][0] == 6:
                        category_ids = lot_ids[0][2]
                    else:
                        category_ids = lot_ids
                    
                    if category_ids:
                        # Get lot codes (max 2 to keep reference short)
                        lots = self.env['construction.lot.category'].browse(category_ids[:2])
                        lot_codes = [lot.code for lot in lots if lot.code]
                        
                        if lot_codes:
                            # Format: LOT1-LOT2-PRODUCTNAME or LOT1-PRODUCTNAME
                            codes_prefix = '-'.join(lot_codes)
                            product_name = vals['name'].replace(' ', '-')[:15].upper()
                            vals['default_code'] = f"{codes_prefix}-{product_name}"
        return super().create(vals_list)

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
