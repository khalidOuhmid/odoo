# -*- coding: utf-8 -*-
"""Integration tests for the Lot Extension model (TASK-008).

Covers purchase order display in lot management:
- Purchase order computed field (purchase_order_ids / purchase_order_count)
- Smart button action (action_view_purchase_orders)
- Contract generation from lot
- PO generation from lot
"""

from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError
from .common import ContractTestMixin
from datetime import date


@tagged('post_install', '-at_install', 'construction_contract', 'lot_extension')
class TestLotExtensionPurchaseOrders(TransactionCase, ContractTestMixin):
    """Integration tests for purchase order visibility on construction lots.

    Validates that lots correctly compute their related purchase orders
    and that the smart button action returns a proper window action.
    """

    @classmethod
    def setUpClass(cls):
        """Initialize shared test data for lot extension tests."""
        super().setUpClass()
        cls.setUpContractData()

    # ------------------------------------------------------------------
    # TASK-008: Purchase Order computed fields
    # ------------------------------------------------------------------

    def test_lot_po_count_zero_when_no_po_linked(self):
        """Verify that a lot with no linked PO has purchase_order_count == 0.

        Raises:
            AssertionError: If count is not zero for an unlinked lot.
        """
        # Arrange
        new_lot = self.env['construction.lot'].create({
            'name': 'Lot Sans BC',
            'code': 'LSB_01',
            'chantier_id': self.chantier.id,
            'execution_type': 'external',
        })

        # Act
        count = new_lot.purchase_order_count

        # Assert
        self.assertEqual(count, 0, 'Lot with no linked PO must have count 0')
        self.assertFalse(new_lot.purchase_order_ids, 'purchase_order_ids must be empty')

    def test_lot_po_count_increments_when_po_linked(self):
        """Verify that linking a PO to a lot increments purchase_order_count.

        Raises:
            AssertionError: If count does not match number of linked POs.
        """
        # Arrange
        po = self.env['purchase.order'].create({
            'partner_id': self.subcontractor.id,
            'date_order': date.today(),
            'lot_ids': [(6, 0, [self.lot.id])],
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'name': 'Service Test',
                'product_qty': 1,
                'price_unit': 500.0,
            })],
        })

        # Act
        self.lot.invalidate_recordset(['purchase_order_ids', 'purchase_order_count'])
        count = self.lot.purchase_order_count

        # Assert
        self.assertEqual(count, 1, 'Lot linked to 1 PO must have count 1')
        self.assertIn(po, self.lot.purchase_order_ids)

    def test_lot_po_count_multiple_pos(self):
        """Verify purchase_order_count when multiple POs reference the same lot.

        Raises:
            AssertionError: If count does not equal number of distinct POs.
        """
        # Arrange
        po1 = self.env['purchase.order'].create({
            'partner_id': self.subcontractor.id,
            'lot_ids': [(6, 0, [self.lot.id])],
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'name': 'PO1',
                'product_qty': 1,
                'price_unit': 100.0,
            })],
        })
        po2 = self.env['purchase.order'].create({
            'partner_id': self.subcontractor.id,
            'lot_ids': [(6, 0, [self.lot.id])],
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'name': 'PO2',
                'product_qty': 2,
                'price_unit': 200.0,
            })],
        })

        # Act
        self.lot.invalidate_recordset(['purchase_order_ids', 'purchase_order_count'])

        # Assert
        self.assertEqual(self.lot.purchase_order_count, 2,
                         'Lot linked to 2 POs must have count 2')
        self.assertIn(po1, self.lot.purchase_order_ids)
        self.assertIn(po2, self.lot.purchase_order_ids)

    # ------------------------------------------------------------------
    # TASK-008: Smart button action
    # ------------------------------------------------------------------

    def test_action_view_purchase_orders_returns_window_action(self):
        """Verify that action_view_purchase_orders returns a proper act_window dict.

        Raises:
            AssertionError: If the action dict is missing required keys.
        """
        # Arrange
        self.env['purchase.order'].create({
            'partner_id': self.subcontractor.id,
            'lot_ids': [(6, 0, [self.lot.id])],
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'name': 'Test',
                'product_qty': 1,
                'price_unit': 100.0,
            })],
        })

        # Act
        action = self.lot.action_view_purchase_orders()

        # Assert
        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_model'], 'purchase.order')
        self.assertIn('list', action['view_mode'])
        self.assertTrue(action['domain'], 'Domain must be set to filter POs')

    def test_action_view_purchase_orders_empty_lot(self):
        """Verify action returns an act_window even when lot has no POs.

        Raises:
            AssertionError: If action raises or returns unexpected result.
        """
        # Arrange
        empty_lot = self.env['construction.lot'].create({
            'name': 'Empty Lot',
            'code': 'EMP_01',
            'chantier_id': self.chantier.id,
            'execution_type': 'external',
        })

        # Act
        action = empty_lot.action_view_purchase_orders()

        # Assert
        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['domain'], [('id', 'in', [])])

    # ------------------------------------------------------------------
    # Contract link
    # ------------------------------------------------------------------

    def test_lot_has_contract_flag(self):
        """Verify has_contract is True when contract_id is set.

        Raises:
            AssertionError: If has_contract is False for a linked lot.
        """
        # Arrange — contract is created in setUpContractData with self.lot

        # Act
        self.lot.invalidate_recordset(['has_contract'])

        # Assert
        self.assertTrue(self.lot.has_contract,
                        'Lot linked to contract must have has_contract=True')

    def test_lot_has_contract_false_when_unlinked(self):
        """Verify has_contract is False for a lot without contract.

        Raises:
            AssertionError: If has_contract is True for an unlinked lot.
        """
        # Arrange
        standalone_lot = self.env['construction.lot'].create({
            'name': 'Standalone Lot',
            'code': 'SL_01',
            'chantier_id': self.chantier.id,
            'execution_type': 'external',
        })

        # Act — no contract linked

        # Assert
        self.assertFalse(standalone_lot.has_contract)


@tagged('post_install', '-at_install', 'construction_contract', 'lot_extension')
class TestLotExtensionPOGeneration(TransactionCase, ContractTestMixin):
    """Integration tests for PO generation from lot (action_generate_purchase_order).

    Validates prerequisite checks, PO creation mechanics, and error handling
    for the lot-to-PO workflow.
    """

    @classmethod
    def setUpClass(cls):
        """Initialize test data for PO generation tests."""
        super().setUpClass()
        cls.setUpContractData()

    def test_generate_po_raises_on_internal_lot(self):
        """Verify that generating a PO for an internal lot raises UserError.

        Raises:
            AssertionError: If no UserError is raised for internal lots.
        """
        # Arrange
        internal_lot = self.env['construction.lot'].create({
            'name': 'Lot Régie',
            'code': 'REG_01',
            'chantier_id': self.chantier.id,
            'execution_type': 'internal',
        })

        # Act & Assert
        with self.assertRaises(UserError):
            internal_lot.action_generate_purchase_order()

    def test_generate_po_raises_when_no_subcontractor(self):
        """Verify that generating a PO without subcontractor raises UserError.

        Raises:
            AssertionError: If no UserError is raised for missing subcontractor.
        """
        # Arrange
        lot_no_st = self.env['construction.lot'].create({
            'name': 'Lot Sans ST',
            'code': 'NST_01',
            'chantier_id': self.chantier.id,
            'execution_type': 'external',
            'subcontractor_id': False,
        })

        # Act & Assert
        with self.assertRaises(UserError):
            lot_no_st.action_generate_purchase_order()
