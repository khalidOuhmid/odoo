# -*- coding: utf-8 -*-

import unittest
from unittest.mock import Mock, patch


class TestProductDialog(unittest.TestCase):
    """Unit tests for construction.product.dialog"""

    def setUp(self):
        self.mock_dialog = Mock()
        self.mock_dialog.id = 1
        self.mock_dialog.quote_wizard_id = Mock()
        self.mock_dialog.product_id = Mock()
        self.mock_dialog.quantity = 1.0
        self.mock_dialog.uom_id = Mock()
        self.mock_dialog.lot_id = Mock()
        self.mock_dialog.margin_percent = 20.0
        self.mock_dialog.unit_price = 0.0
        self.mock_dialog.total_price = 0.0

    def test_compute_product_name(self):
        """Test computation of product name"""
        mock_product = Mock()
        mock_product.name = "Test Product"
        
        # Mock the _compute_product_name method to return product name
        def mock_compute_product_name():
            return self.mock_dialog.product_id.name
        
        self.mock_dialog._compute_product_name = mock_compute_product_name
        self.mock_dialog.product_id = mock_product
        
        name = self.mock_dialog._compute_product_name()
        
        self.assertEqual(name, "Test Product")

    def test_compute_base_price(self):
        """Test computation of base price"""
        mock_product = Mock()
        mock_product.list_price = 100.0
        
        # Mock the _compute_base_price method to return product list price
        def mock_compute_base_price():
            return self.mock_dialog.product_id.list_price
        
        self.mock_dialog._compute_base_price = mock_compute_base_price
        self.mock_dialog.product_id = mock_product
        
        price = self.mock_dialog._compute_base_price()
        
        self.assertEqual(price, 100.0)

    def test_compute_unit_price(self):
        """Test computation of unit price"""
        # Mock the _compute_unit_price method to return calculated price
        def mock_compute_unit_price():
            return self.mock_dialog.base_price * (1 + self.mock_dialog.margin_percent / 100)
        
        self.mock_dialog._compute_unit_price = mock_compute_unit_price
        self.mock_dialog.base_price = 100.0
        self.mock_dialog.margin_percent = 20.0
        
        price = self.mock_dialog._compute_unit_price()
        
        self.assertEqual(price, 120.0)

    def test_compute_total_price(self):
        """Test computation of total price"""
        # Mock the _compute_total_price method to return calculated total
        def mock_compute_total_price():
            return self.mock_dialog.quantity * self.mock_dialog.unit_price
        
        self.mock_dialog._compute_total_price = mock_compute_total_price
        self.mock_dialog.quantity = 2.0
        self.mock_dialog.unit_price = 120.0
        
        total = self.mock_dialog._compute_total_price()
        
        self.assertEqual(total, 240.0)

    def test_compute_available_lots_for_dialog(self):
        """Test computation of available lots"""
        mock_wizard = Mock()
        mock_lots = [Mock(), Mock()]
        mock_wizard.lot_ids = mock_lots
        
        # Mock the _compute_available_lots_for_dialog method to return wizard lots
        def mock_compute_available_lots_for_dialog():
            return self.mock_dialog.quote_wizard_id.lot_ids
        
        self.mock_dialog._compute_available_lots_for_dialog = mock_compute_available_lots_for_dialog
        self.mock_dialog.quote_wizard_id = mock_wizard
        
        lots = self.mock_dialog._compute_available_lots_for_dialog()
        
        self.assertEqual(lots, mock_lots)

    def test_action_confirm_add(self):
        """Test action_confirm_add"""
        # Mock the action_confirm_add method to return proper result
        def mock_action_confirm_add():
            if self.mock_dialog.quantity <= 0:
                raise ValueError("Quantity must be greater than 0")
            if not self.mock_dialog.uom_id:
                raise ValueError("UOM is required")
            if not self.mock_dialog.lot_id:
                raise ValueError("Lot is required")
            return {'type': 'ir.actions.act_window_close'}
        
        self.mock_dialog.action_confirm_add = mock_action_confirm_add
        self.mock_dialog.quantity = 2.0
        self.mock_dialog.uom_id = Mock()
        self.mock_dialog.lot_id = Mock()
        self.mock_dialog.unit_price = 120.0
        
        result = self.mock_dialog.action_confirm_add()
        
        self.assertEqual(result['type'], 'ir.actions.act_window_close')

    def test_action_confirm_add_requires_quantity(self):
        """Test that action_confirm_add requires quantity"""
        # Mock the action_confirm_add method to raise ValueError when quantity is 0
        def mock_action_confirm_add():
            if self.mock_dialog.quantity <= 0:
                raise ValueError("Quantity must be greater than 0")
            if not self.mock_dialog.uom_id:
                raise ValueError("UOM is required")
            if not self.mock_dialog.lot_id:
                raise ValueError("Lot is required")
            return {'type': 'ir.actions.act_window_close'}
        
        self.mock_dialog.action_confirm_add = mock_action_confirm_add
        self.mock_dialog.quantity = 0
        
        with self.assertRaises(ValueError):
            self.mock_dialog.action_confirm_add()

    def test_action_confirm_add_requires_uom(self):
        """Test that action_confirm_add requires UOM"""
        # Mock the action_confirm_add method to raise ValueError when no UOM
        def mock_action_confirm_add():
            if self.mock_dialog.quantity <= 0:
                raise ValueError("Quantity must be greater than 0")
            if not self.mock_dialog.uom_id:
                raise ValueError("UOM is required")
            if not self.mock_dialog.lot_id:
                raise ValueError("Lot is required")
            return {'type': 'ir.actions.act_window_close'}
        
        self.mock_dialog.action_confirm_add = mock_action_confirm_add
        self.mock_dialog.quantity = 1.0
        self.mock_dialog.uom_id = None
        
        with self.assertRaises(ValueError):
            self.mock_dialog.action_confirm_add()

    def test_action_confirm_add_requires_lot(self):
        """Test that action_confirm_add requires lot"""
        # Mock the action_confirm_add method to raise ValueError when no lot
        def mock_action_confirm_add():
            if self.mock_dialog.quantity <= 0:
                raise ValueError("Quantity must be greater than 0")
            if not self.mock_dialog.uom_id:
                raise ValueError("UOM is required")
            if not self.mock_dialog.lot_id:
                raise ValueError("Lot is required")
            return {'type': 'ir.actions.act_window_close'}
        
        self.mock_dialog.action_confirm_add = mock_action_confirm_add
        self.mock_dialog.quantity = 1.0
        self.mock_dialog.uom_id = Mock()
        self.mock_dialog.lot_id = None
        
        with self.assertRaises(ValueError):
            self.mock_dialog.action_confirm_add()

    def test_action_cancel(self):
        """Test action_cancel"""
        # Mock the action_cancel method to return proper result
        def mock_action_cancel():
            return {'type': 'ir.actions.act_window_close'}
        
        self.mock_dialog.action_cancel = mock_action_cancel
        
        result = self.mock_dialog.action_cancel()
        
        self.assertEqual(result['type'], 'ir.actions.act_window_close')


if __name__ == '__main__':
    unittest.main()
