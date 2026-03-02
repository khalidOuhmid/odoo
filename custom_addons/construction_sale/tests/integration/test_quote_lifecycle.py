# construction_sale/tests/integration/test_quote_lifecycle.py
# -*- coding: utf-8 -*-
"""
Integration Tests — Quote Lifecycle
=====================================
Tests the full lifecycle of a construction quote:
  draft → confirm → revision flow.
Traverses sale.order + sale.order.line + construction.lot.
"""

from odoo.tests import tagged

from ..common import TestCommon


@tagged('post_install', '-at_install', 'construction_sale', 'integration')
class TestQuoteLifecycle(TestCommon):
    """Integration tests for the full quote lifecycle."""

    def _create_sample_order(self):
        """Create a complete order with 2 lines for lifecycle tests."""
        order = self._create_order()
        self._create_line(
            order,
            product=self.product_brique,
            lot=self.lot_go,
            price_unit=10.0,
            price_buy=5.0,
            product_uom_qty=100.0,
        )
        self._create_line(
            order,
            product=self.product_porte,
            lot=self.lot_menu,
            price_unit=225.0,
            price_buy=150.0,
            product_uom_qty=2.0,
        )
        return order

    # =========================================================================
    # Draft → Confirmed
    # =========================================================================

    def test_lifecycle_draft_to_confirmed(self):
        """Confirming a draft order sets state to 'sale'."""
        # Arrange
        order = self._create_sample_order()
        self.assertEqual(order.state, 'draft')

        # Act
        order.action_confirm()

        # Assert
        self.assertEqual(order.state, 'sale')

    def test_lifecycle_confirmed_preserves_line_data(self):
        """After confirmation, all line fields are preserved."""
        # Arrange
        EXPECTED_MARGIN = 50.0
        order = self._create_sample_order()
        line = order.order_line.filtered(lambda l: not l.display_type)[0]
        original_price_buy = line.price_buy
        original_price_unit = line.price_unit

        # Act
        order.action_confirm()

        # Assert
        self.assertEqual(line.price_buy, original_price_buy)
        self.assertEqual(line.price_unit, original_price_unit)

    def test_lifecycle_confirmed_order_amount_positive(self):
        """Confirmed order has positive amount_total."""
        # Arrange
        order = self._create_sample_order()

        # Act
        order.action_confirm()

        # Assert
        self.assertGreater(order.amount_total, 0)

    # =========================================================================
    # Lot price update after confirmation
    # =========================================================================

    def test_lifecycle_lot_price_updated_after_confirmation(self):
        """Confirming the order updates linked lot prices."""
        # Arrange
        BRIQUE_UNIT_PRICE = 10.0
        BRIQUE_QTY = 100.0
        order = self._create_order()
        self._create_line(
            order,
            product=self.product_brique,
            lot=self.lot_go,
            price_unit=BRIQUE_UNIT_PRICE,
            product_uom_qty=BRIQUE_QTY,
        )

        # Act
        order.action_confirm()
        self.lot_go.invalidate_recordset(['price'])

        # Assert
        EXPECTED = BRIQUE_UNIT_PRICE * BRIQUE_QTY
        self.assertAlmostEqual(self.lot_go.price, EXPECTED, places=2)

    # =========================================================================
    # Margin verification post-confirm
    # =========================================================================

    def test_lifecycle_margin_preserved_after_confirm(self):
        """Margin calculations remain correct after confirmation."""
        # Arrange
        COST = 5.0
        PRICE = 10.0
        QTY = 10.0
        order = self._create_order()
        line = self._create_line(
            order,
            price_buy=COST,
            price_unit=PRICE,
            product_uom_qty=QTY,
        )
        expected_margin = (PRICE - COST) * QTY

        # Act
        order.action_confirm()

        # Assert
        self.assertAlmostEqual(line.margin, expected_margin, places=2)

    # =========================================================================
    # Sections integrity
    # =========================================================================

    def test_lifecycle_sections_preserved_after_confirm(self):
        """Section lines are not lost during confirmation."""
        # Arrange
        order = self._create_sample_order()
        order._resequence_lines_by_lot()
        sections_before = len(order.order_line.filtered(lambda l: l.display_type == 'line_section'))

        # Act
        order.action_confirm()

        # Assert
        sections_after = len(order.order_line.filtered(lambda l: l.display_type == 'line_section'))
        self.assertEqual(sections_before, sections_after)

    # =========================================================================
    # Multi-order on same chantier
    # =========================================================================

    def test_lifecycle_multiple_orders_on_same_chantier(self):
        """Multiple orders can be created and confirmed for one chantier."""
        # Arrange
        order_1 = self._create_sample_order()
        order_2 = self._create_sample_order()

        # Act
        order_1.action_confirm()
        order_2.action_confirm()

        # Assert
        self.assertEqual(order_1.state, 'sale')
        self.assertEqual(order_2.state, 'sale')
        self.assertNotEqual(order_1.id, order_2.id)

    def test_lifecycle_lot_price_sums_across_orders(self):
        """Lot price sums line subtotals from all confirmed orders."""
        # Arrange
        PRICE_1 = 10.0
        QTY_1 = 50.0
        PRICE_2 = 20.0
        QTY_2 = 25.0

        order_1 = self._create_order()
        self._create_line(order_1, lot=self.lot_go, price_unit=PRICE_1, product_uom_qty=QTY_1)

        order_2 = self._create_order()
        self._create_line(order_2, lot=self.lot_go, price_unit=PRICE_2, product_uom_qty=QTY_2)

        # Act
        order_1.action_confirm()
        order_2.action_confirm()
        self.lot_go.invalidate_recordset(['price'])

        # Assert
        EXPECTED = (PRICE_1 * QTY_1) + (PRICE_2 * QTY_2)
        self.assertAlmostEqual(self.lot_go.price, EXPECTED, places=2)
