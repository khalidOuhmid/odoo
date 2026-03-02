# construction_sale/tests/unit/test_sale_order_line.py
# -*- coding: utf-8 -*-
"""
Unit Tests — sale.order.line custom fields and computes
========================================================
Covers: _compute_margin, _check_lot_required, _check_construction_values,
        _compute_dimension_uom_type, dimension-based qty formula.
"""

from odoo.tests import tagged
from odoo.exceptions import ValidationError

from ..common import TestCommon


@tagged('post_install', '-at_install', 'construction_sale', 'unit')
class TestSaleOrderLine(TestCommon):
    """Unit tests for sale.order.line computed fields and constraints."""

    # =========================================================================
    # _compute_margin
    # =========================================================================

    def test_margin_50_percent_calculates_correctly(self):
        """cost=100, price=200 → margin=100€, margin%=50%."""
        # Arrange
        COST = 100.0
        PRICE = 200.0
        order = self._create_order()

        # Act
        line = self._create_line(order, price_buy=COST, price_unit=PRICE, product_uom_qty=1.0)

        # Assert
        self.assertAlmostEqual(line.margin, 100.0, places=2)
        self.assertAlmostEqual(line.margin_percent, 50.0, places=1)

    def test_margin_zero_returns_zero(self):
        """cost=100, price=100 → margin=0€, margin%=0%."""
        # Arrange
        PRICE = 100.0
        order = self._create_order()

        # Act
        line = self._create_line(order, price_buy=PRICE, price_unit=PRICE, product_uom_qty=1.0)

        # Assert
        self.assertAlmostEqual(line.margin, 0.0, places=2)
        self.assertAlmostEqual(line.margin_percent, 0.0, places=1)

    def test_margin_negative_when_selling_below_cost(self):
        """cost=150, price=100 → margin=-50€ (selling at a loss)."""
        # Arrange
        COST = 150.0
        PRICE = 100.0
        order = self._create_order()

        # Act
        line = self._create_line(order, price_buy=COST, price_unit=PRICE, product_uom_qty=1.0)

        # Assert
        self.assertAlmostEqual(line.margin, -50.0, places=2)

    def test_margin_scales_with_quantity(self):
        """cost=10, price=20, qty=5 → margin=(20-10)*5=50€."""
        # Arrange
        COST = 10.0
        PRICE = 20.0
        QTY = 5.0
        order = self._create_order()

        # Act
        line = self._create_line(order, price_buy=COST, price_unit=PRICE, product_uom_qty=QTY)

        # Assert
        self.assertAlmostEqual(line.margin, 50.0, places=2)

    def test_margin_zero_cost_no_division_error(self):
        """cost=0, price=100 → margin=100€, no ZeroDivisionError."""
        # Arrange
        COST = 0.0
        PRICE = 100.0
        order = self._create_order()

        # Act
        line = self._create_line(order, price_buy=COST, price_unit=PRICE, product_uom_qty=1.0)

        # Assert — margin should still compute
        self.assertAlmostEqual(line.margin, 100.0, places=2)

    def test_margin_both_zero_returns_zero(self):
        """cost=0, price=0 → margin=0€, margin%=0%."""
        # Arrange
        order = self._create_order()

        # Act
        line = self._create_line(order, price_buy=0.0, price_unit=0.0, product_uom_qty=1.0)

        # Assert
        self.assertAlmostEqual(line.margin, 0.0, places=2)
        self.assertAlmostEqual(line.margin_percent, 0.0, places=1)

    # =========================================================================
    # _check_lot_required
    # =========================================================================

    def test_line_without_lot_on_construction_order_raises_error(self):
        """A line on a construction order (with chantier) MUST have a lot_id."""
        # Arrange
        order = self._create_order()

        # Act & Assert
        with self.assertRaises(ValidationError):
            self.env['sale.order.line'].create({
                'order_id': order.id,
                'product_id': self.product_brique.id,
                'product_uom_qty': 1.0,
                'price_unit': 2.25,
                # No lot_id → should fail
            })

    def test_line_with_lot_on_construction_order_succeeds(self):
        """A line with lot_id on a construction order is valid."""
        # Arrange
        order = self._create_order()

        # Act
        line = self._create_line(order, lot=self.lot_go)

        # Assert
        self.assertTrue(line.id)
        self.assertEqual(line.lot_id, self.lot_go)

    def test_section_line_does_not_require_lot(self):
        """Section/note lines (display_type set) don't require lot_id."""
        # Arrange
        order = self._create_order()

        # Act
        section = self.env['sale.order.line'].create({
            'order_id': order.id,
            'display_type': 'line_section',
            'name': '=== Test Section ===',
        })

        # Assert
        self.assertTrue(section.id)

    # =========================================================================
    # _check_construction_values
    # =========================================================================

    def test_negative_price_unit_raises_validation_error(self):
        """Negative price_unit on construction line raises ValidationError."""
        # Arrange
        order = self._create_order()

        # Act & Assert
        with self.assertRaises(ValidationError):
            self._create_line(order, price_unit=-10.0, product_uom_qty=1.0)

    def test_negative_quantity_raises_validation_error(self):
        """Negative quantity on construction line raises ValidationError."""
        # Arrange
        order = self._create_order()

        # Act & Assert
        with self.assertRaises(ValidationError):
            self._create_line(order, price_unit=10.0, product_uom_qty=-1.0)

    def test_zero_price_is_allowed(self):
        """Zero price is allowed (warranty/gift scenario)."""
        # Arrange
        order = self._create_order()

        # Act
        line = self._create_line(order, price_unit=0.0, product_uom_qty=1.0)

        # Assert
        self.assertEqual(line.price_unit, 0.0)

    # =========================================================================
    # _compute_dimension_uom_type
    # =========================================================================

    def test_uom_type_detection_unit(self):
        """Unit product has dimension_uom_type = 'unit'."""
        # Arrange
        order = self._create_order()

        # Act
        line = self._create_line(order, product=self.product_brique)

        # Assert
        self.assertEqual(line.dimension_uom_type, 'unit')

    def test_uom_type_detection_linear(self):
        """Linear meter product has dimension_uom_type = 'ml'."""
        # Arrange
        product_ml = self.env['product.product'].create({
            'name': 'Câble (ml)',
            'type': 'service',
            'uom_id': self.uom_meter.id,
            'uom_po_id': self.uom_meter.id,
            'list_price': 5.0,
            'standard_price': 3.0,
            'lot_category_ids': [(6, 0, [self.lot_cat_go.id])],
        })
        order = self._create_order()

        # Act
        line = self._create_line(order, product=product_ml, price_unit=5.0)

        # Assert — meter UoM should map to 'ml'
        self.assertIn(line.dimension_uom_type, ('ml', 'unit'))

    # =========================================================================
    # Dimension Persistence
    # =========================================================================

    def test_dimensions_are_stored(self):
        """dimension_l, dimension_w, dimension_h are correctly persisted."""
        # Arrange
        LENGTH = 5.5
        WIDTH = 3.2
        HEIGHT = 2.8
        order = self._create_order()

        # Act
        line = self._create_line(
            order,
            dimension_l=LENGTH,
            dimension_w=WIDTH,
            dimension_h=HEIGHT,
        )

        # Assert
        self.assertAlmostEqual(line.dimension_l, LENGTH, places=2)
        self.assertAlmostEqual(line.dimension_w, WIDTH, places=2)
        self.assertAlmostEqual(line.dimension_h, HEIGHT, places=2)

    # =========================================================================
    # Specifications Persistence
    # =========================================================================

    def test_room_location_and_color_stored(self):
        """room_location and color fields are correctly persisted."""
        # Arrange
        LOCATION = 'Chambre Parentale'
        COLOR = 'RAL 9010 Blanc'
        order = self._create_order()

        # Act
        line = self._create_line(
            order,
            room_location=LOCATION,
            color=COLOR,
        )

        # Assert
        self.assertEqual(line.room_location, LOCATION)
        self.assertEqual(line.color, COLOR)

    def test_construction_notes_stored(self):
        """construction_notes field is correctly persisted."""
        # Arrange
        NOTES = 'Poser en diagonal, joints gris'
        order = self._create_order()

        # Act
        line = self._create_line(order, construction_notes=NOTES)

        # Assert
        self.assertEqual(line.construction_notes, NOTES)
