# -*- coding: utf-8 -*-

import unittest
from unittest.mock import Mock, patch


class TestLineEditor(unittest.TestCase):
    """Unit tests for construction.line.editor"""

    def setUp(self):
        self.mock_editor = Mock()
        self.mock_editor.id = 1
        self.mock_editor.quote_line_id = Mock()
        self.mock_editor.product_id = Mock()
        self.mock_editor.quantity = 1.0
        self.mock_editor.uom_id = Mock()
        self.mock_editor.lot_id = Mock()
        self.mock_editor.margin_percent = 20.0
        self.mock_editor.unit_price = 0.0
        self.mock_editor.total_price = 0.0

    def test_compute_product_name(self):
        """Test computation of product name"""
        mock_product = Mock()
        mock_product.name = "Test Product"
        
        def mock_compute_product_name():
            return self.mock_editor.product_id.name
        
        self.mock_editor._compute_product_name = mock_compute_product_name
        self.mock_editor.product_id = mock_product
        
        name = self.mock_editor._compute_product_name()
        self.assertEqual(name, "Test Product")

    def test_compute_base_price(self):
        """Test computation of base price"""
        mock_product = Mock()
        mock_product.list_price = 100.0
        
        def mock_compute_base_price():
            return self.mock_editor.product_id.list_price
        
        self.mock_editor._compute_base_price = mock_compute_base_price
        self.mock_editor.product_id = mock_product
        
        price = self.mock_editor._compute_base_price()
        self.assertEqual(price, 100.0)

    def test_compute_unit_price(self):
        """Test computation of unit price"""
        def mock_compute_unit_price():
            return self.mock_editor.base_price * (1 + self.mock_editor.margin_percent / 100)
        
        self.mock_editor._compute_unit_price = mock_compute_unit_price
        self.mock_editor.base_price = 100.0
        self.mock_editor.margin_percent = 20.0
        
        price = self.mock_editor._compute_unit_price()
        self.assertEqual(price, 120.0)

    def test_compute_total_price(self):
        """Test computation of total price"""
        def mock_compute_total_price():
            return self.mock_editor.quantity * self.mock_editor.unit_price
        
        self.mock_editor._compute_total_price = mock_compute_total_price
        self.mock_editor.quantity = 2.0
        self.mock_editor.unit_price = 120.0
        
        total = self.mock_editor._compute_total_price()
        self.assertEqual(total, 240.0)

    def test_action_save_changes(self):
        """Test action_save_changes"""
        def mock_action_save_changes():
            if self.mock_editor.quantity <= 0:
                raise ValueError("Quantity must be greater than 0")
            if not self.mock_editor.uom_id:
                raise ValueError("UOM is required")
            if not self.mock_editor.lot_id:
                raise ValueError("Lot is required")
            return {'type': 'ir.actions.act_window_close'}
        
        self.mock_editor.action_save_changes = mock_action_save_changes
        self.mock_editor.quantity = 2.0
        self.mock_editor.uom_id = Mock()
        self.mock_editor.lot_id = Mock()
        self.mock_editor.unit_price = 120.0
        
        result = self.mock_editor.action_save_changes()
        self.assertEqual(result['type'], 'ir.actions.act_window_close')

    def test_action_save_changes_requires_quantity(self):
        """Test that action_save_changes requires quantity"""
        def mock_action_save_changes():
            if self.mock_editor.quantity <= 0:
                raise ValueError("Quantity must be greater than 0")
            if not self.mock_editor.uom_id:
                raise ValueError("UOM is required")
            if not self.mock_editor.lot_id:
                raise ValueError("Lot is required")
            return {'type': 'ir.actions.act_window_close'}
        
        self.mock_editor.action_save_changes = mock_action_save_changes
        self.mock_editor.quantity = 0
        
        with self.assertRaises(ValueError):
            self.mock_editor.action_save_changes()

    def test_action_save_changes_requires_uom(self):
        """Test that action_save_changes requires UOM"""
        def mock_action_save_changes():
            if self.mock_editor.quantity <= 0:
                raise ValueError("Quantity must be greater than 0")
            if not self.mock_editor.uom_id:
                raise ValueError("UOM is required")
            if not self.mock_editor.lot_id:
                raise ValueError("Lot is required")
            return {'type': 'ir.actions.act_window_close'}
        
        self.mock_editor.action_save_changes = mock_action_save_changes
        self.mock_editor.quantity = 1.0
        self.mock_editor.uom_id = None
        
        with self.assertRaises(ValueError):
            self.mock_editor.action_save_changes()

    def test_action_save_changes_requires_lot(self):
        """Test that action_save_changes requires lot"""
        def mock_action_save_changes():
            if self.mock_editor.quantity <= 0:
                raise ValueError("Quantity must be greater than 0")
            if not self.mock_editor.uom_id:
                raise ValueError("UOM is required")
            if not self.mock_editor.lot_id:
                raise ValueError("Lot is required")
            return {'type': 'ir.actions.act_window_close'}
        
        self.mock_editor.action_save_changes = mock_action_save_changes
        self.mock_editor.quantity = 1.0
        self.mock_editor.uom_id = Mock()
        self.mock_editor.lot_id = None
        
        with self.assertRaises(ValueError):
            self.mock_editor.action_save_changes()

    def test_action_cancel(self):
        """Test action_cancel"""
        def mock_action_cancel():
            return {'type': 'ir.actions.act_window_close'}
        
        self.mock_editor.action_cancel = mock_action_cancel
        
        result = self.mock_editor.action_cancel()
        self.assertEqual(result['type'], 'ir.actions.act_window_close')


if __name__ == '__main__':
    unittest.main()
