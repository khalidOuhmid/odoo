# construction_sale/tests/unit/test_construction_lot.py
# -*- coding: utf-8 -*-
"""
Unit Tests — construction.lot (sale price compute + code uniqueness)
=====================================================================
Covers: _compute_price_from_so, unique code per chantier constraint.
Note: The Lot model is in construction_core; construction_sale adds
      _compute_price_from_so via _inherit.
"""

from odoo.tests import tagged
from odoo.exceptions import ValidationError

from ..common import TestCommon


@tagged('post_install', '-at_install', 'construction_sale', 'unit')
class TestConstructionLot(TestCommon):
    """Unit tests for construction.lot sale-specific extensions."""

    # =========================================================================
    # _compute_price_from_so (from construction_sale/models/construction_lot.py)
    # =========================================================================

    def test_lot_price_updated_from_confirmed_sale_lines(self):
        """Price is computed from confirmed (state=sale) SO lines."""
        # Arrange
        UNIT_PRICE = 100.0
        QTY = 3.0
        order = self._create_order()
        self._create_line(order, lot=self.lot_go, price_unit=UNIT_PRICE, product_uom_qty=QTY)
        order.action_confirm()

        # Act — recompute
        self.lot_go.invalidate_recordset(['price'])

        # Assert
        EXPECTED_SUBTOTAL = UNIT_PRICE * QTY
        self.assertAlmostEqual(self.lot_go.price, EXPECTED_SUBTOTAL, places=2)

    def test_lot_price_ignores_draft_order_lines(self):
        """Draft order lines do not contribute to lot price."""
        # Arrange
        order = self._create_order()
        self._create_line(order, lot=self.lot_go, price_unit=500.0, product_uom_qty=1.0)
        # Order stays in draft — not confirmed

        # Act
        self.lot_go.invalidate_recordset(['price'])

        # Assert — lot price should be 0 (no confirmed lines)
        self.assertAlmostEqual(self.lot_go.price, 0.0, places=2)

    def test_lot_price_zero_when_no_lines(self):
        """Lot with no SO lines has price=0."""
        # Arrange — lot_menu has no lines

        # Act
        self.lot_menu.invalidate_recordset(['price'])

        # Assert
        self.assertAlmostEqual(self.lot_menu.price, 0.0, places=2)

    # =========================================================================
    # Unique code per chantier (SQL constraint + Python constraint)
    # =========================================================================

    def test_duplicate_lot_code_same_chantier_raises_error(self):
        """BR-007: Two lots with same code in same chantier is forbidden."""
        # Arrange — lot_go already has code='GO' on self.chantier

        # Act & Assert
        with self.assertRaises((ValidationError, Exception)):
            self.env['construction.lot'].create({
                'name': 'Duplicate GO',
                'code': 'GO',
                'chantier_id': self.chantier.id,
            })

    def test_same_lot_code_different_chantier_is_valid(self):
        """Same code on different chantiers is allowed."""
        # Arrange
        chantier_2 = self.env['construction.chantier'].create({
            'name': 'Autre Chantier',
            'client': self.partner.id,
        })

        # Act
        lot_2 = self.env['construction.lot'].create({
            'name': 'Gros Oeuvre 2',
            'code': 'GO',
            'chantier_id': chantier_2.id,
        })

        # Assert
        self.assertTrue(lot_2.id)
        self.assertEqual(lot_2.code, 'GO')

    def test_lot_without_code_raises_error(self):
        """Lot creation without code (required=True) raises error."""
        # Act & Assert
        with self.assertRaises(Exception):
            self.env['construction.lot'].create({
                'name': 'Lot Sans Code',
                'chantier_id': self.chantier.id,
                # No code → ORM required=True should block
            })

    def test_lot_without_chantier_raises_error(self):
        """Lot creation without chantier_id (required=True) raises error."""
        # Act & Assert
        with self.assertRaises(Exception):
            self.env['construction.lot'].create({
                'name': 'Lot Sans Chantier',
                'code': 'LSC',
                # No chantier_id → required=True
            })
