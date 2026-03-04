# -*- coding: utf-8 -*-
"""
Sale Order Line Construction Extension
======================================
Adds detailed construction specifications to order lines.
Includes:
- Dimension Calculator ("Métré")
- Cost & Margin Cockpit
- Lot assignment for workflow tracking
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SaleOrderLine(models.Model):
    """Extended Sale Order Line with Construction specifics.
    
    Includes:
    - Visual and technical specifications (color, dimensions, location)
    - Hard link to construction.lot
    - Dimension-based quantity calculation ("Métré")
    - Line-level cost (price_buy) with margin calculation
    - Constraint validation for lot assignment
    """
    _inherit = 'sale.order.line'

    # ============================================================
    # VISUAL & TECHNICAL SPECS
    # ============================================================

    room_location = fields.Char(
        string='Location',
        help="Specific location in the building (e.g., 'Kitchen', 'Master Bedroom')"
    )
    
    lot_id = fields.Many2one(
        'construction.lot', 
        string='Technical Lot',
        domain="[('chantier_id', '=', parent.chantier_id)]",
        help="The construction lot this item belongs to (e.g. Electricity)"
    )

    color = fields.Char(
        string='Color/Finish',
        help="Custom color or finish selected for this item"
    )

    dimensions = fields.Char(
        string='Dimensions (Text)',
        help="Specific measurements (e.g., '120x80cm') - legacy field"
    )

    construction_notes = fields.Text(
        string='Technical Notes',
        help="Notes for the construction team"
    )

    is_locked_for_construction = fields.Boolean(
        string='Locked',
        default=False,
        help="If true, this line details are locked by the construction manager"
    )

    # Field required by some Odoo views - prevents field undefined error
    product_document_ids = fields.Many2many(
        'ir.attachment',
        string='Product Documents',
        compute='_compute_product_documents',
        help="Technical documents associated with the product"
    )
    
    @api.depends('product_id')
    def _compute_product_documents(self):
        for line in self:
            line.product_document_ids = False

    # ============================================================
    # DIMENSION CALCULATOR ("Métré")
    # ============================================================

    dimension_l = fields.Float(
        string='Length (m)',
        digits='Product Unit of Measure',
        default=0.0,
        help="Length in meters for quantity calculation"
    )

    dimension_w = fields.Float(
        string='Width (m)',
        digits='Product Unit of Measure',
        default=0.0,
        help="Width in meters for quantity calculation"
    )

    dimension_h = fields.Float(
        string='Height (m)',
        digits='Product Unit of Measure',
        default=0.0,
        help="Height in meters for quantity calculation"
    )

    dimension_uom_type = fields.Char(
        string='UoM Category',
        compute='_compute_dimension_uom_type',
        store=False,
        help="UoM category name for dimension input visibility"
    )

    # ============================================================
    # COST & MARGIN COCKPIT (Manager-Only)
    # ============================================================

    price_buy = fields.Float(
        string='Cost Price',
        digits='Product Price',
        groups='construction_core.group_construction_user,construction_core.group_construction_admin',
        help="Purchase/cost price for this line. Defaults to product standard price."
    )

    target_margin_percent = fields.Float(
        string='Target Margin (%)',
        default=50.0,
        groups='construction_core.group_construction_user,construction_core.group_construction_admin',
        help="Target profit margin percentage. Price = Cost / (1 - Margin%)"
    )

    margin = fields.Monetary(
        string='Margin (€)',
        compute='_compute_margin',
        store=True,
        currency_field='currency_id',
        groups='construction_core.group_construction_user,construction_core.group_construction_admin',
        help="Profit margin in currency (Sale Price - Cost Price)"
    )

    margin_percent = fields.Float(
        string='Actual Margin (%)',
        compute='_compute_margin',
        store=True,
        groups='construction_core.group_construction_user,construction_core.group_construction_admin',
        help="Profit margin as percentage of sale price"
    )

    # ============================================================
    # COMPUTED FIELDS
    # ============================================================

    @api.depends('product_id', 'product_id.uom_id', 'product_id.uom_id.category_id')
    def _compute_dimension_uom_type(self) -> None:
        """Determine UoM category for dimension input visibility.
        
        Returns category name: 'Length' for ml, 'Surface' for m², 'Volume' for m³
        """
        for line in self:
            if line.product_id and line.product_id.uom_id:
                uom = line.product_id.uom_id
                # Check UoM name patterns for common construction units
                uom_name = uom.name.lower() if uom.name else ''
                if 'm²' in uom_name or 'm2' in uom_name or 'square' in uom_name:
                    line.dimension_uom_type = 'm2'
                elif 'm³' in uom_name or 'm3' in uom_name or 'cubic' in uom_name:
                    line.dimension_uom_type = 'm3'
                elif 'ml' in uom_name or 'linear' in uom_name or uom_name == 'm':
                    line.dimension_uom_type = 'ml'
                else:
                    line.dimension_uom_type = 'unit'
            else:
                line.dimension_uom_type = 'unit'

    @api.depends('price_unit', 'product_uom_qty', 'price_buy')
    def _compute_margin(self) -> None:
        """Calculate margin in both absolute and percentage terms.
        
        Formula:
        - Margin (€) = (Sale Price - Cost Price) * Quantity
        - Margin (%) = ((Sale Price - Cost Price) / Sale Price) * 100
        
        Uses line-level price_buy instead of product.standard_price.
        """
        for line in self:
            if line.price_unit and line.price_buy:
                cost = line.price_buy
                sale_price = line.price_unit
                
                # Absolute margin
                line.margin = (sale_price - cost) * line.product_uom_qty
                
                # Percentage margin (avoid division by zero)
                if sale_price > 0:
                    line.margin_percent = ((sale_price - cost) / sale_price) * 100
                else:
                    line.margin_percent = 0.0
            else:
                line.margin = 0.0
                line.margin_percent = 0.0

    # ============================================================
    # ONCHANGE & CONSTRAINTS
    # ============================================================

    @api.onchange('product_id')
    def _onchange_product_id_set_cost(self) -> None:
        """Initialize price_buy from product's standard_price when product changes."""
        if self.product_id:
            self.price_buy = self.product_id.standard_price or 0.0
            # Also compute initial price from margin if cost exists
            if self.price_buy > 0 and self.target_margin_percent < 100:
                margin_factor = 1 - (self.target_margin_percent / 100)
                if margin_factor > 0:
                    self.price_unit = self.price_buy / margin_factor

    @api.onchange('price_buy', 'target_margin_percent')
    def _onchange_margin_compute_price(self) -> None:
        """Compute selling price from cost and target margin.
        
        Formula: price_unit = price_buy / (1 - margin_percent/100)
        Example: 100€ cost, 50% margin → 100 / 0.5 = 200€
        """
        if self.price_buy > 0 and self.target_margin_percent < 100:
            margin_factor = 1 - (self.target_margin_percent / 100)
            if margin_factor > 0:
                self.price_unit = self.price_buy / margin_factor

    @api.onchange('dimension_l', 'dimension_w', 'dimension_h')
    def _onchange_dimensions_compute_qty(self) -> None:
        """Auto-calculate quantity from dimensions based on UoM.
        
        Rules:
        - m² (surface): qty = L × W
        - m³ (volume): qty = L × W × H
        - ml (linear): qty = L
        """
        if not self.product_id:
            return
            
        uom_type = self.dimension_uom_type
        
        if uom_type == 'm2' and self.dimension_l > 0 and self.dimension_w > 0:
            self.product_uom_qty = self.dimension_l * self.dimension_w
        elif uom_type == 'm3' and self.dimension_l > 0 and self.dimension_w > 0 and self.dimension_h > 0:
            self.product_uom_qty = self.dimension_l * self.dimension_w * self.dimension_h
        elif uom_type == 'ml' and self.dimension_l > 0:
            self.product_uom_qty = self.dimension_l

    @api.constrains('lot_id', 'order_id')
    def _check_lot_required(self):
        """Enforce lot assignment for construction order lines.
        
        Business Rule: Every non-section/note line in a construction quote
        must be assigned to a technical lot for proper workflow tracking.
        
        Raises:
            ValidationError: If construction line lacks lot assignment
        """
        for line in self:
            if (line.order_id.chantier_id and 
                not line.lot_id and 
                not line.display_type):
                raise ValidationError(
                    _("Line '%s' must be assigned to a Technical Lot since this is a construction order.") 
                    % (line.name or line.product_id.name)
                )

    @api.constrains('price_unit', 'discount')
    def _check_locked_prices(self):
        """
        Phase 2: Verrouillage des Lignes.
        Interdire la modification des montants si la commande est validée.
        """
        for line in self:
            if line.order_id.state in ['sale', 'done']:
                raise ValidationError(
                    _("Vous ne pouvez pas modifier le prix unitaire ou la remise d'une ligne sur un devis confirmé (%s).") 
                    % line.order_id.name
                )

    @api.constrains('price_unit', 'product_uom_qty')
    def _check_construction_values(self):
        """
        SAP-Level Validation: Ensure data integrity for construction lines.
        """
        for line in self:
            if line.order_id.chantier_id and not line.display_type:
                # 1. No negative prices (unless it's a discount product, but standard lines shouldn't)
                if line.price_unit < 0:
                    raise ValidationError(_("Line '%s': Unit price cannot be negative.") % line.name)
                
                # 2. No negative quantities
                if line.product_uom_qty < 0:
                    raise ValidationError(_("Line '%s': Quantity cannot be negative.") % line.name)

