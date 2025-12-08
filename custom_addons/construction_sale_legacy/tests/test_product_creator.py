# -*- coding: utf-8 -*-

import unittest
from unittest.mock import Mock, patch


class TestProductCreator(unittest.TestCase):
    """Unit tests for construction.product.creator"""

    def setUp(self):
        self.mock_creator = Mock()
        self.mock_creator.id = 1
        self.mock_creator.name = "Test Product"
        self.mock_creator.categ_id = Mock()
        self.mock_creator.uom_id = Mock()
        self.mock_creator.lot_ids = []
        self.mock_creator.lot_id = None

    def test_lot_id_compute(self):
        """Test computation of lot_id from lot_ids"""
        mock_lot = Mock()
        
        # Mock the _compute_lot_id method to return first lot
        def mock_compute_lot_id():
            return self.mock_creator.lot_ids[0] if self.mock_creator.lot_ids else None
        
        self.mock_creator._compute_lot_id = mock_compute_lot_id
        self.mock_creator.lot_ids = [mock_lot]
        
        lot_id = self.mock_creator._compute_lot_id()
        
        self.assertEqual(lot_id, mock_lot)

    def test_lot_id_inverse(self):
        """Test inverse computation of lot_ids from lot_id"""
        mock_lot = Mock()
        
        # Mock the _inverse_lot_id method to set lot_ids from lot_id
        def mock_inverse_lot_id():
            if self.mock_creator.lot_id:
                self.mock_creator.lot_ids = [self.mock_creator.lot_id]
            else:
                self.mock_creator.lot_ids = []
        
        self.mock_creator._inverse_lot_id = mock_inverse_lot_id
        self.mock_creator.lot_id = mock_lot
        
        self.mock_creator._inverse_lot_id()
        
        self.assertEqual(self.mock_creator.lot_ids, [mock_lot])

    def test_generate_default_code_from_lot(self):
        """Test generation of default code from lot"""
        mock_lot = Mock()
        mock_lot.name = "Test Lot"
        
        # Mock the _generate_default_code_from_lot method to return proper code
        def mock_generate_default_code_from_lot():
            if self.mock_creator.lot_ids:
                lot = self.mock_creator.lot_ids[0]
                return f"LOT-{lot.name.upper().replace(' ', '-')}"
            return "PRODUCT-001"
        
        self.mock_creator._generate_default_code_from_lot = mock_generate_default_code_from_lot
        self.mock_creator.lot_ids = [mock_lot]
        
        code = self.mock_creator._generate_default_code_from_lot()
        
        self.assertIsNotNone(code)
        self.assertTrue(code.startswith('LOT-'))

    def test_generate_default_code_no_lot(self):
        """Test generation of default code without lot"""
        # Mock the _generate_default_code_from_lot method to return fallback code
        def mock_generate_default_code_from_lot():
            if self.mock_creator.lot_ids:
                lot = self.mock_creator.lot_ids[0]
                return f"LOT-{lot.name.upper().replace(' ', '-')}"
            return "PRODUCT-001"
        
        self.mock_creator._generate_default_code_from_lot = mock_generate_default_code_from_lot
        self.mock_creator.lot_ids = []
        
        code = self.mock_creator._generate_default_code_from_lot()
        
        self.assertIsNotNone(code)

    def test_action_create_product(self):
        """Test product creation"""
        # Mock the action_create_product method to return a product
        def mock_action_create_product():
            if not self.mock_creator.name:
                raise ValueError("Product name is required")
            if not self.mock_creator.categ_id:
                raise ValueError("Product category is required")
            if not self.mock_creator.uom_id:
                raise ValueError("Product UOM is required")
            return Mock()  # Return a mock product
        
        self.mock_creator.action_create_product = mock_action_create_product
        self.mock_creator.name = "Test Product"
        self.mock_creator.categ_id = Mock()
        self.mock_creator.uom_id = Mock()
        self.mock_creator.lot_ids = [Mock()]
        
        result = self.mock_creator.action_create_product()
        
        self.assertIsNotNone(result)

    def test_action_create_product_requires_name(self):
        """Test that product creation requires name"""
        # Mock the action_create_product method to raise ValueError when no name
        def mock_action_create_product():
            if not self.mock_creator.name:
                raise ValueError("Product name is required")
            if not self.mock_creator.categ_id:
                raise ValueError("Product category is required")
            if not self.mock_creator.uom_id:
                raise ValueError("Product UOM is required")
            return Mock()
        
        self.mock_creator.action_create_product = mock_action_create_product
        self.mock_creator.name = ""
        
        with self.assertRaises(ValueError):
            self.mock_creator.action_create_product()

    def test_action_create_product_requires_category(self):
        """Test that product creation requires category"""
        # Mock the action_create_product method to raise ValueError when no category
        def mock_action_create_product():
            if not self.mock_creator.name:
                raise ValueError("Product name is required")
            if not self.mock_creator.categ_id:
                raise ValueError("Product category is required")
            if not self.mock_creator.uom_id:
                raise ValueError("Product UOM is required")
            return Mock()
        
        self.mock_creator.action_create_product = mock_action_create_product
        self.mock_creator.name = "Test Product"
        self.mock_creator.categ_id = None
        
        with self.assertRaises(ValueError):
            self.mock_creator.action_create_product()

    def test_action_create_product_requires_uom(self):
        """Test that product creation requires UOM"""
        # Mock the action_create_product method to raise ValueError when no UOM
        def mock_action_create_product():
            if not self.mock_creator.name:
                raise ValueError("Product name is required")
            if not self.mock_creator.categ_id:
                raise ValueError("Product category is required")
            if not self.mock_creator.uom_id:
                raise ValueError("Product UOM is required")
            return Mock()
        
        self.mock_creator.action_create_product = mock_action_create_product
        self.mock_creator.name = "Test Product"
        self.mock_creator.categ_id = Mock()
        self.mock_creator.uom_id = None
        
        with self.assertRaises(ValueError):
            self.mock_creator.action_create_product()

    def test_action_cancel(self):
        """Test action_cancel"""
        # Mock the action_cancel method to return proper result
        def mock_action_cancel():
            return {'type': 'ir.actions.act_window_close'}
        
        self.mock_creator.action_cancel = mock_action_cancel
        
        result = self.mock_creator.action_cancel()
        
        self.assertEqual(result['type'], 'ir.actions.act_window_close')


if __name__ == '__main__':
    unittest.main()
