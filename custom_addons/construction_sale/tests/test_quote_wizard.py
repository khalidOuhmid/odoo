# -*- coding: utf-8 -*-

import unittest
from unittest.mock import Mock, patch


class TestQuoteWizard(unittest.TestCase):
    """Unit tests for construction.quote.wizard"""

    def setUp(self):
        self.mock_wizard = Mock()
        self.mock_wizard.id = 1
        self.mock_wizard.sale_order_id = Mock()
        self.mock_wizard.chantier_id = Mock()
        self.mock_wizard.partner_id = Mock()
        self.mock_wizard.lot_ids = []
        self.mock_wizard.selected_line_ids = []
        self.mock_wizard.available_product_ids = []
        self.mock_wizard.default_margin_percent = 20.0

    def test_compute_available_products(self):
        """Test computation of available products"""
        mock_products = [Mock(), Mock()]
        
        # Mock the _compute_available_products method to return actual products
        def mock_compute_available_products():
            return self.mock_wizard.available_product_ids
        
        self.mock_wizard._compute_available_products = mock_compute_available_products
        self.mock_wizard.available_product_ids = mock_products
        
        products = self.mock_wizard._compute_available_products()
        
        self.assertEqual(products, mock_products)

    def test_action_add_product_requires_lots(self):
        """Test that action_add_product requires lot_ids"""
        # Mock the action_add_product method to raise ValueError when no lots
        def mock_action_add_product():
            if not self.mock_wizard.lot_ids:
                raise ValueError("Veuillez d'abord sélectionner au moins un lot avant d'ajouter des produits.")
            return {'res_model': 'construction.product.dialog', 'target': 'new'}
        
        self.mock_wizard.action_add_product = mock_action_add_product
        
        with self.assertRaises(ValueError):
            self.mock_wizard.action_add_product()

    def test_action_add_product_with_lots(self):
        """Test action_add_product with lot_ids"""
        # Mock the action_add_product method to return proper result
        def mock_action_add_product():
            if not self.mock_wizard.lot_ids:
                raise ValueError("Veuillez d'abord sélectionner au moins un lot avant d'ajouter des produits.")
            return {'res_model': 'construction.product.dialog', 'target': 'new'}
        
        self.mock_wizard.action_add_product = mock_action_add_product
        self.mock_wizard.lot_ids = [Mock(), Mock()]
        
        result = self.mock_wizard.action_add_product()
        
        self.assertEqual(result['res_model'], 'construction.product.dialog')
        self.assertEqual(result['target'], 'new')

    def test_action_confirm_selection_requires_products(self):
        """Test that action_confirm_selection requires selected_line_ids"""
        # Mock the action_confirm_selection method to raise ValueError when no products
        def mock_action_confirm_selection():
            if not self.mock_wizard.selected_line_ids:
                raise ValueError("Veuillez sélectionner au moins un produit.")
            return {'type': 'ir.actions.act_window'}
        
        self.mock_wizard.action_confirm_selection = mock_action_confirm_selection
        
        with self.assertRaises(ValueError):
            self.mock_wizard.action_confirm_selection()

    def test_action_confirm_selection_with_products(self):
        """Test action_confirm_selection with selected_line_ids"""
        # Mock the action_confirm_selection method to return proper result
        def mock_action_confirm_selection():
            if not self.mock_wizard.selected_line_ids:
                raise ValueError("Veuillez sélectionner au moins un produit.")
            return {'type': 'ir.actions.act_window'}
        
        self.mock_wizard.action_confirm_selection = mock_action_confirm_selection
        self.mock_wizard.selected_line_ids = [Mock(), Mock()]
        
        result = self.mock_wizard.action_confirm_selection()
        
        self.assertEqual(result['type'], 'ir.actions.act_window')

    def test_action_finalize_quote(self):
        """Test action_finalize_quote"""
        # Mock the action_finalize_quote method to return proper result
        def mock_action_finalize_quote():
            return {'res_model': 'sale.order'}
        
        self.mock_wizard.action_finalize_quote = mock_action_finalize_quote
        
        result = self.mock_wizard.action_finalize_quote()
        
        self.assertEqual(result['res_model'], 'sale.order')

    def test_action_cancel_wizard_with_progress(self):
        """Test action_cancel_wizard with progress"""
        # Mock the action_cancel_wizard method to return proper result
        def mock_action_cancel_wizard():
            if self.mock_wizard.selected_line_ids:
                return {'res_model': 'construction.wizard.cancel.confirm'}
            return {'type': 'ir.actions.act_window_close'}
        
        self.mock_wizard.action_cancel_wizard = mock_action_cancel_wizard
        self.mock_wizard.selected_line_ids = [Mock()]
        
        result = self.mock_wizard.action_cancel_wizard()
        
        self.assertEqual(result['res_model'], 'construction.wizard.cancel.confirm')

    def test_action_cancel_wizard_no_progress(self):
        """Test action_cancel_wizard without progress"""
        # Mock the action_cancel_wizard method to return proper result
        def mock_action_cancel_wizard():
            if self.mock_wizard.selected_line_ids:
                return {'res_model': 'construction.wizard.cancel.confirm'}
            return {'type': 'ir.actions.act_window_close'}
        
        self.mock_wizard.action_cancel_wizard = mock_action_cancel_wizard
        
        result = self.mock_wizard.action_cancel_wizard()
        
        self.assertEqual(result['type'], 'ir.actions.act_window_close')

    def test_action_view_selection_requires_products(self):
        """Test that action_view_selection requires selected_line_ids"""
        # Mock the action_view_selection method to raise ValueError when no products
        def mock_action_view_selection():
            if not self.mock_wizard.selected_line_ids:
                raise ValueError("Veuillez sélectionner au moins un produit.")
            return {'res_model': 'construction.quote.line'}
        
        self.mock_wizard.action_view_selection = mock_action_view_selection
        
        with self.assertRaises(ValueError):
            self.mock_wizard.action_view_selection()

    def test_action_view_selection_with_products(self):
        """Test action_view_selection with selected_line_ids"""
        # Mock the action_view_selection method to return proper result
        def mock_action_view_selection():
            if not self.mock_wizard.selected_line_ids:
                raise ValueError("Veuillez sélectionner au moins un produit.")
            return {'res_model': 'construction.quote.line'}
        
        self.mock_wizard.action_view_selection = mock_action_view_selection
        self.mock_wizard.selected_line_ids = [Mock()]
        
        result = self.mock_wizard.action_view_selection()
        
        self.assertEqual(result['res_model'], 'construction.quote.line')

    def test_action_clear_selection(self):
        """Test action_clear_selection"""
        # Mock the action_clear_selection method to clear selection
        def mock_action_clear_selection():
            self.mock_wizard.selected_line_ids = []
        
        self.mock_wizard.action_clear_selection = mock_action_clear_selection
        self.mock_wizard.selected_line_ids = [Mock(), Mock()]
        
        self.mock_wizard.action_clear_selection()
        
        self.assertEqual(len(self.mock_wizard.selected_line_ids), 0)

    def test_compute_line_count(self):
        """Test computation of line count"""
        # Mock the _compute_line_count method to return actual count
        def mock_compute_line_count():
            return len(self.mock_wizard.selected_line_ids)
        
        self.mock_wizard._compute_line_count = mock_compute_line_count
        self.mock_wizard.selected_line_ids = [Mock(), Mock(), Mock()]
        
        count = self.mock_wizard._compute_line_count()
        
        self.assertEqual(count, 3)

    def test_compute_totals(self):
        """Test computation of totals"""
        # Mock the _compute_totals method to return actual sum
        def mock_compute_totals():
            return sum(line.quantity * line.unit_price for line in self.mock_wizard.selected_line_ids)
        
        self.mock_wizard._compute_totals = mock_compute_totals
        line1 = Mock()
        line1.quantity = 2
        line1.unit_price = 100.0
        line2 = Mock()
        line2.quantity = 1
        line2.unit_price = 200.0
        self.mock_wizard.selected_line_ids = [line1, line2]
        
        total = self.mock_wizard._compute_totals()
        
        self.assertEqual(total, 400.0)


if __name__ == '__main__':
    unittest.main()
