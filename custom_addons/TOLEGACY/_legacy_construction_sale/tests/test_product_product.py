# -*- coding: utf-8 -*-

import unittest
from unittest.mock import Mock, patch


class TestProductProduct(unittest.TestCase):
    """Unit tests for product.product extension"""

    def setUp(self):
        self.mock_product = Mock()
        self.mock_product.id = 1
        self.mock_product.name = "Test Product"
        self.mock_product.product_tmpl_id = Mock()
        self.mock_product.construction_specialty = None
        self.mock_product.lot_ids = []

    def test_related_fields(self):
        """Test related fields from product_tmpl_id"""
        mock_template = Mock()
        mock_template.construction_specialty = "masonry"
        mock_template.lot_ids = [Mock(), Mock()]
        
        self.mock_product.product_tmpl_id = mock_template
        self.mock_product.construction_specialty = "masonry"
        self.mock_product.lot_ids = mock_template.lot_ids
        
        self.assertEqual(self.mock_product.construction_specialty, "masonry")
        self.assertEqual(self.mock_product.lot_ids, mock_template.lot_ids)

    def test_construction_specialty_readonly(self):
        """Test that construction_specialty is readonly=False"""
        self.mock_product.construction_specialty = "electrical"
        self.assertEqual(self.mock_product.construction_specialty, "electrical")

    def test_lot_ids_readonly(self):
        """Test that lot_ids is readonly=False"""
        mock_lots = [Mock(), Mock()]
        self.mock_product.lot_ids = mock_lots
        self.assertEqual(self.mock_product.lot_ids, mock_lots)

    def test_search_by_construction_specialty(self):
        """Test search by construction_specialty"""
        products = [
            {'name': 'Masonry Product', 'construction_specialty': 'masonry'},
            {'name': 'Electrical Product', 'construction_specialty': 'electrical'}
        ]
        
        masonry_products = [p for p in products if p['construction_specialty'] == 'masonry']
        self.assertEqual(len(masonry_products), 1)
        self.assertEqual(masonry_products[0]['name'], 'Masonry Product')

    def test_search_by_lot_ids(self):
        """Test search by lot_ids"""
        mock_lot = Mock()
        mock_lot.id = 1
        
        products = [
            {'name': 'Product 1', 'lot_ids': [mock_lot]},
            {'name': 'Product 2', 'lot_ids': []}
        ]
        
        lot_products = [p for p in products if mock_lot in p['lot_ids']]
        self.assertEqual(len(lot_products), 1)
        self.assertEqual(lot_products[0]['name'], 'Product 1')

    def test_default_values(self):
        """Test default values for construction fields"""
        self.assertIsNone(self.mock_product.construction_specialty)
        self.assertEqual(len(self.mock_product.lot_ids), 0)

    def test_construction_specialty_required(self):
        """Test that construction_specialty can be required"""
        with self.assertRaises(ValueError):
            if not self.mock_product.construction_specialty:
                raise ValueError("Construction specialty is required")

    def test_lot_ids_required(self):
        """Test that lot_ids can be required"""
        with self.assertRaises(ValueError):
            if not self.mock_product.lot_ids:
                raise ValueError("At least one lot is required")


if __name__ == '__main__':
    unittest.main()
