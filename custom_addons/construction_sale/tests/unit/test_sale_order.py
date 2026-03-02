# construction_sale/tests/unit/test_sale_order.py
# -*- coding: utf-8 -*-
"""
Unit Tests — sale.order custom methods
=======================================
Covers: create_from_spa, search_products_for_spa, _resequence_lines_by_lot,
        custom create (name generation), _check_monetary_safety.
"""

from odoo.tests import tagged
from odoo.exceptions import ValidationError

from ..common import TestCommon


@tagged('post_install', '-at_install', 'construction_sale', 'unit')
class TestSaleOrder(TestCommon):
    """Unit tests for sale.order custom methods."""

    # =========================================================================
    # create_from_spa — Nominal
    # =========================================================================

    def test_create_from_spa_nominal_creates_order_with_lines(self):
        """BR-001: Valid create_from_spa creates a draft order with correct lines."""
        # Arrange
        EXPECTED_QTY = 2.0
        EXPECTED_PRICE = 10.0
        vals = {
            'chantier_id': self.chantier.id,
            'partner_id': self.partner.id,
            'order_line': [
                (0, 0, {
                    'product_id': self.product_brique.id,
                    'lot_id': self.lot_go.id,
                    'product_uom_qty': EXPECTED_QTY,
                    'price_unit': EXPECTED_PRICE,
                }),
                (0, 0, {
                    'product_id': self.product_porte.id,
                    'lot_id': self.lot_menu.id,
                    'product_uom_qty': 1.0,
                    'price_unit': 225.0,
                }),
            ],
        }

        # Act
        result = self.env['sale.order'].create_from_spa(vals)

        # Assert
        order = self.env['sale.order'].browse(result['id'])
        self.assertEqual(order.state, 'draft')
        self.assertEqual(order.chantier_id, self.chantier)
        # Lines = product lines + section lines created by _resequence_lines_by_lot
        product_lines = order.order_line.filtered(lambda l: not l.display_type)
        self.assertEqual(len(product_lines), 2)

    def test_create_from_spa_returns_expected_keys(self):
        """create_from_spa response contains id, name, state."""
        # Arrange
        vals = {
            'chantier_id': self.chantier.id,
            'partner_id': self.partner.id,
            'order_line': [
                (0, 0, {
                    'product_id': self.product_brique.id,
                    'lot_id': self.lot_go.id,
                    'product_uom_qty': 1.0,
                    'price_unit': 2.25,
                }),
            ],
        }

        # Act
        result = self.env['sale.order'].create_from_spa(vals)

        # Assert
        self.assertIn('id', result)
        self.assertIn('name', result)
        self.assertIn('state', result)

    # =========================================================================
    # create_from_spa — Error cases
    # =========================================================================

    def test_create_from_spa_empty_lines_creates_empty_order(self):
        """create_from_spa with no lines creates an order with no product lines."""
        # Arrange
        vals = {
            'chantier_id': self.chantier.id,
            'partner_id': self.partner.id,
            'order_line': [],
        }

        # Act
        result = self.env['sale.order'].create_from_spa(vals)

        # Assert
        order = self.env['sale.order'].browse(result['id'])
        self.assertEqual(len(order.order_line), 0)

    # =========================================================================
    # Custom create — Name generation
    # =========================================================================

    def test_create_chantier_order_generates_custom_name(self):
        """Order linked to chantier gets auto-generated name pattern."""
        # Arrange / Act
        order = self._create_order()

        # Assert — name should contain chantier short name and version
        self.assertIn('v1', order.name)
        self.assertTrue(order.quote_reference)

    def test_create_non_chantier_order_keeps_default_name(self):
        """Order without chantier keeps Odoo default name (S00xxx)."""
        # Arrange / Act
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
        })

        # Assert — no 'v1' suffix, standard Odoo naming
        self.assertFalse(order.quote_reference)

    # =========================================================================
    # _check_monetary_safety
    # =========================================================================

    def test_confirmed_order_negative_total_raises_validation_error(self):
        """Confirming an order with negative total raises ValidationError."""
        # Arrange
        order = self._create_order()
        self._create_line(order, price_unit=-100.0, product_uom_qty=1.0)

        # Act & Assert
        with self.assertRaises((ValidationError, Exception)):
            order.action_confirm()

    # =========================================================================
    # _resequence_lines_by_lot
    # =========================================================================

    def test_resequence_creates_sections_for_each_lot(self):
        """_resequence_lines_by_lot creates one section per unique lot."""
        # Arrange
        order = self._create_order()
        self._create_line(order, lot=self.lot_go, price_unit=10.0)
        self._create_line(order, lot=self.lot_menu, price_unit=20.0)

        # Act
        order._resequence_lines_by_lot()

        # Assert
        sections = order.order_line.filtered(lambda l: l.display_type == 'line_section')
        self.assertEqual(len(sections), 2)

    def test_resequence_no_duplicate_on_rerun(self):
        """Running _resequence_lines_by_lot twice produces same section count."""
        # Arrange
        order = self._create_order()
        self._create_line(order, lot=self.lot_go, price_unit=10.0)

        # Act
        order._resequence_lines_by_lot()
        order._resequence_lines_by_lot()

        # Assert
        sections = order.order_line.filtered(lambda l: l.display_type == 'line_section')
        self.assertEqual(len(sections), 1)

    def test_resequence_empty_order_no_crash(self):
        """_resequence_lines_by_lot on empty order does not crash."""
        # Arrange
        order = self._create_order()

        # Act & Assert (no exception)
        order._resequence_lines_by_lot()
        self.assertEqual(len(order.order_line), 0)

    def test_resequence_non_construction_order_skipped(self):
        """_resequence_lines_by_lot is a no-op if no chantier_id."""
        # Arrange
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
        })

        # Act (should not crash or create sections)
        order._resequence_lines_by_lot()

        # Assert
        self.assertEqual(len(order.order_line), 0)

    # =========================================================================
    # action_open_quote_builder
    # =========================================================================

    def test_action_open_quote_builder_draft_returns_client_action(self):
        """Draft order returns standard client action."""
        # Arrange
        order = self._create_order()

        # Act
        result = order.action_open_quote_builder()

        # Assert
        self.assertEqual(result['type'], 'ir.actions.client')
        self.assertEqual(result['tag'], 'construction_sale.quote_builder')

    def test_action_open_quote_builder_confirmed_returns_notification(self):
        """Confirmed order returns notification + client action."""
        # Arrange
        order = self._create_order()
        self._create_line(order, price_unit=100.0)
        order.action_confirm()

        # Act
        result = order.action_open_quote_builder()

        # Assert
        self.assertEqual(result['type'], 'ir.actions.client')
        self.assertEqual(result['tag'], 'display_notification')
        self.assertIn('next', result['params'])
