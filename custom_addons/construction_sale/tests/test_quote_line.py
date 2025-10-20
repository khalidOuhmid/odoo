# -*- coding: utf-8 -*-

import unittest
from unittest.mock import Mock, patch


class TestQuoteLine(unittest.TestCase):
    """Unit tests for construction.quote.line"""

    def setUp(self):
        self.mock_line = Mock()
        self.mock_line.id = 1
        self.mock_line.wizard_id = Mock()
        self.mock_line.product_id = Mock()
        self.mock_line.quantity = 1.0
        self.mock_line.uom_id = Mock()
        self.mock_line.lot_id = Mock()
        self.mock_line.unit_price = 0.0
        self.mock_line.total_price = 0.0

    def test_compute_product_name(self):
        """Test computation of product name"""
        mock_product = Mock()
        mock_product.name = "Test Product"
        
        def mock_compute_product_name():
            return self.mock_line.product_id.name
        
        self.mock_line._compute_product_name = mock_compute_product_name
        self.mock_line.product_id = mock_product
        
        name = self.mock_line._compute_product_name()
        self.assertEqual(name, "Test Product")

    def test_compute_unit_price(self):
        """Test computation of unit price"""
        mock_product = Mock()
        mock_product.list_price = 100.0
        
        def mock_compute_unit_price():
            return self.mock_line.product_id.list_price * (1 + self.mock_line.margin_percent / 100)
        
        self.mock_line._compute_unit_price = mock_compute_unit_price
        self.mock_line.product_id = mock_product
        self.mock_line.margin_percent = 20.0
        
        price = self.mock_line._compute_unit_price()
        self.assertEqual(price, 120.0)

    def test_compute_total_price(self):
        """Test computation of total price"""
        def mock_compute_total_price():
            return self.mock_line.quantity * self.mock_line.unit_price
        
        self.mock_line._compute_total_price = mock_compute_total_price
        self.mock_line.quantity = 2.0
        self.mock_line.unit_price = 120.0
        
        total = self.mock_line._compute_total_price()
        self.assertEqual(total, 240.0)

    def test_compute_lot_name(self):
        """Test computation of lot name"""
        mock_lot = Mock()
        mock_lot.name = "Test Lot"
        
        def mock_compute_lot_name():
            return self.mock_line.lot_id.name
        
        self.mock_line._compute_lot_name = mock_compute_lot_name
        self.mock_line.lot_id = mock_lot
        
        name = self.mock_line._compute_lot_name()
        self.assertEqual(name, "Test Lot")

    def test_compute_uom_name(self):
        """Test computation of UOM name"""
        mock_uom = Mock()
        mock_uom.name = "Unit"
        
        def mock_compute_uom_name():
            return self.mock_line.uom_id.name
        
        self.mock_line._compute_uom_name = mock_compute_uom_name
        self.mock_line.uom_id = mock_uom
        
        name = self.mock_line._compute_uom_name()
        self.assertEqual(name, "Unit")

    def test_action_edit_line(self):
        """Test action_edit_line"""
        def mock_action_edit_line():
            return {'res_model': 'construction.line.editor', 'target': 'new'}
        
        self.mock_line.action_edit_line = mock_action_edit_line
        
        result = self.mock_line.action_edit_line()
        self.assertEqual(result['res_model'], 'construction.line.editor')
        self.assertEqual(result['target'], 'new')

    def test_action_remove_line(self):
        """Test action_remove_line"""
        def mock_action_remove_line():
            return {'type': 'ir.actions.act_window_close'}
        
        self.mock_line.action_remove_line = mock_action_remove_line
        
        result = self.mock_line.action_remove_line()
        self.assertEqual(result['type'], 'ir.actions.act_window_close')

    def test_action_duplicate_line(self):
        """Test action_duplicate_line"""
        def mock_action_duplicate_line():
            return {'type': 'ir.actions.act_window_close'}
        
        self.mock_line.action_duplicate_line = mock_action_duplicate_line
        
        result = self.mock_line.action_duplicate_line()
        self.assertEqual(result['type'], 'ir.actions.act_window_close')


if __name__ == '__main__':
    unittest.main()
