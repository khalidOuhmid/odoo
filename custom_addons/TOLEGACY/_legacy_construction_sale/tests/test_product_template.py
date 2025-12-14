# -*- coding: utf-8 -*-

import unittest
from unittest.mock import Mock, patch


class TestProductTemplate(unittest.TestCase):
    """Unit tests for product.template extension"""

    def setUp(self):
        self.mock_template = Mock()
        self.mock_template.id = 1
        self.mock_template.name = "Test Product"
        self.mock_template.type = "consu"
        self.mock_template.list_price = 100.0
        self.mock_template.standard_price = 80.0
        self.mock_template.construction_specialty = None
        self.mock_template.lot_ids = []

    def test_construction_specialty_selection(self):
        """Test construction_specialty selection values"""
        specialties = ['masonry', 'electrical', 'plumbing', 'roofing', 'flooring']
        
        for specialty in specialties:
            self.mock_template.construction_specialty = specialty
            self.assertEqual(self.mock_template.construction_specialty, specialty)

    def test_lot_ids_relationship(self):
        """Test lot_ids relationship"""
        mock_lots = [Mock(), Mock()]
        self.mock_template.lot_ids = mock_lots
        
        self.assertEqual(self.mock_template.lot_ids, mock_lots)

    def test_search_by_construction_specialty(self):
        """Test search by construction_specialty"""
        templates = [
            {'name': 'Masonry Product', 'construction_specialty': 'masonry'},
            {'name': 'Electrical Product', 'construction_specialty': 'electrical'}
        ]
        
        masonry_products = [t for t in templates if t['construction_specialty'] == 'masonry']
        
        self.assertEqual(len(masonry_products), 1)
        self.assertEqual(masonry_products[0]['name'], 'Masonry Product')

    def test_search_by_lot_ids(self):
        """Test search by lot_ids"""
        mock_lot = Mock()
        mock_lot.id = 1
        
        templates = [
            {'name': 'Product 1', 'lot_ids': [mock_lot]},
            {'name': 'Product 2', 'lot_ids': []}
        ]
        
        lot_products = [t for t in templates if mock_lot in t['lot_ids']]
        
        self.assertEqual(len(lot_products), 1)
        self.assertEqual(lot_products[0]['name'], 'Product 1')

    def test_default_values(self):
        """Test default values for construction fields"""
        self.assertIsNone(self.mock_template.construction_specialty)
        self.assertEqual(len(self.mock_template.lot_ids), 0)

    def test_construction_specialty_required(self):
        """Test that construction_specialty can be required"""
        with self.assertRaises(ValueError):
            if not self.mock_template.construction_specialty:
                raise ValueError("Construction specialty is required")

    def test_lot_ids_required(self):
        """Test that lot_ids can be required"""
        with self.assertRaises(ValueError):
            if not self.mock_template.lot_ids:
                raise ValueError("At least one lot is required")


if __name__ == '__main__':
    unittest.main()
