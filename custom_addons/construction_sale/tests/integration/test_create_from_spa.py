# construction_sale/tests/integration/test_create_from_spa.py
# -*- coding: utf-8 -*-
"""
Integration Tests — create_from_spa flow
==========================================
Full end-to-end simulation of the OWL QuoteBuilder creating quotes.
Traverses sale.order + sale.order.line + construction.lot.
"""

from odoo.tests import tagged

from ..common import TestCommon


@tagged('post_install', '-at_install', 'construction_sale', 'integration')
class TestCreateFromSpa(TestCommon):
    """Integration tests for the SPA quote creation flow."""

    def _make_spa_payload(self, lines_data, **kwargs):
        """Build a create_from_spa payload from simple line tuples.
        
        Args:
            lines_data: list of dicts with {product, lot, qty, price_unit, ...}
        """
        order_lines = []
        for data in lines_data:
            line_vals = {
                'product_id': data['product'].id,
                'lot_id': data['lot'].id,
                'product_uom_qty': data.get('qty', 1.0),
                'price_unit': data.get('price_unit', data['product'].list_price),
            }
            if 'price_buy' in data:
                line_vals['price_buy'] = data['price_buy']
            if 'room_location' in data:
                line_vals['room_location'] = data['room_location']
            if 'dimension_l' in data:
                line_vals['dimension_l'] = data['dimension_l']
            if 'dimension_w' in data:
                line_vals['dimension_w'] = data['dimension_w']
            order_lines.append((0, 0, line_vals))

        payload = {
            'chantier_id': self.chantier.id,
            'partner_id': self.partner.id,
            'order_line': order_lines,
        }
        payload.update(kwargs)
        return payload

    # =========================================================================
    # Full SPA create flow
    # =========================================================================

    def test_full_spa_create_quote_flow(self):
        """E2E: 3 lines across 2 lots → order with correct structure."""
        # Arrange
        BRIQUE_QTY = 500.0
        PORTE_QTY = 3.0
        BRIQUE_PRICE = 2.25
        PORTE_PRICE = 225.0
        lines = [
            {'product': self.product_brique, 'lot': self.lot_go,
             'qty': BRIQUE_QTY, 'price_unit': BRIQUE_PRICE, 'price_buy': 1.5},
            {'product': self.product_porte, 'lot': self.lot_menu,
             'qty': PORTE_QTY, 'price_unit': PORTE_PRICE, 'price_buy': 150.0},
            {'product': self.product_brique, 'lot': self.lot_go,
             'qty': 100.0, 'price_unit': BRIQUE_PRICE, 'price_buy': 1.5,
             'room_location': 'Cuisine'},
        ]
        payload = self._make_spa_payload(lines)

        # Act
        result = self.env['sale.order'].create_from_spa(payload)

        # Assert
        order = self.env['sale.order'].browse(result['id'])
        self.assertEqual(order.state, 'draft')
        self.assertEqual(order.chantier_id, self.chantier)
        self.assertEqual(order.partner_id, self.partner)

        product_lines = order.order_line.filtered(lambda l: not l.display_type)
        self.assertEqual(len(product_lines), 3)

        # Verify lots are correctly assigned
        go_lines = product_lines.filtered(lambda l: l.lot_id == self.lot_go)
        menu_lines = product_lines.filtered(lambda l: l.lot_id == self.lot_menu)
        self.assertEqual(len(go_lines), 2)
        self.assertEqual(len(menu_lines), 1)

        # Verify cost is persisted
        for line in product_lines:
            self.assertGreater(line.price_buy, 0)

    def test_spa_with_dimensions_persists_correctly(self):
        """Lines with dimension_l/w are correctly stored via SPA."""
        # Arrange
        LENGTH = 5.0
        WIDTH = 3.0
        lines = [
            {'product': self.product_brique, 'lot': self.lot_go,
             'qty': 15.0, 'price_unit': 2.25,
             'dimension_l': LENGTH, 'dimension_w': WIDTH},
        ]
        payload = self._make_spa_payload(lines)

        # Act
        result = self.env['sale.order'].create_from_spa(payload)

        # Assert
        order = self.env['sale.order'].browse(result['id'])
        line = order.order_line.filtered(lambda l: not l.display_type)
        self.assertAlmostEqual(line.dimension_l, LENGTH, places=2)
        self.assertAlmostEqual(line.dimension_w, WIDTH, places=2)

    def test_spa_creates_sections_automatically(self):
        """create_from_spa triggers _resequence_lines_by_lot after creation."""
        # Arrange
        lines = [
            {'product': self.product_brique, 'lot': self.lot_go, 'qty': 1.0},
            {'product': self.product_porte, 'lot': self.lot_menu, 'qty': 1.0},
        ]
        payload = self._make_spa_payload(lines)

        # Act
        result = self.env['sale.order'].create_from_spa(payload)

        # Assert
        order = self.env['sale.order'].browse(result['id'])
        sections = order.order_line.filtered(lambda l: l.display_type == 'line_section')
        self.assertEqual(len(sections), 2, "Should have 2 lot sections")

    def test_spa_name_contains_chantier(self):
        """Generated order name contains chantier short name."""
        # Arrange
        lines = [
            {'product': self.product_brique, 'lot': self.lot_go, 'qty': 1.0},
        ]
        payload = self._make_spa_payload(lines)

        # Act
        result = self.env['sale.order'].create_from_spa(payload)

        # Assert
        order = self.env['sale.order'].browse(result['id'])
        # Name should contain part of chantier name (Villa-Test-Bernard)
        self.assertIn('v1', order.name.lower())

    def test_spa_multiple_quotes_increment_sequence(self):
        """Creating 2 quotes for same chantier increments sequence number."""
        # Arrange
        lines = [
            {'product': self.product_brique, 'lot': self.lot_go, 'qty': 1.0},
        ]

        # Act — create 2 quotes
        result1 = self.env['sale.order'].create_from_spa(self._make_spa_payload(lines))
        result2 = self.env['sale.order'].create_from_spa(self._make_spa_payload(lines))

        # Assert
        order1 = self.env['sale.order'].browse(result1['id'])
        order2 = self.env['sale.order'].browse(result2['id'])
        self.assertNotEqual(order1.name, order2.name)
