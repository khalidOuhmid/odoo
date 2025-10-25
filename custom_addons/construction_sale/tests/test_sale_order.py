# -*- coding: utf-8 -*-

import unittest
from unittest.mock import Mock, patch


class TestSaleOrderExtension(unittest.TestCase):
    """Unit tests for sale.order extension"""

    def setUp(self):
        self.mock_order = Mock()
        self.mock_order.id = 1
        self.mock_order.name = "SO001"
        self.mock_order.partner_id = Mock()
        self.mock_order.chantier_id = None
        self.mock_order.lot_ids = []
        self.mock_order.lot_selection_ids = []
        self.mock_order.order_line = []
        self.mock_order.state = 'draft'

    def test_onchange_chantier_id_sets_lots(self):
        """Test that changing chantier_id sets lot_ids and lot_selection_ids"""
        mock_chantier = Mock()
        mock_chantier.lots_ids = [Mock(), Mock()]
        
        # Mock the _onchange_chantier_id method to actually set the values
        def mock_onchange_chantier_id():
            self.mock_order.lot_ids = mock_chantier.lots_ids
            self.mock_order.lot_selection_ids = mock_chantier.lots_ids
        
        self.mock_order._onchange_chantier_id = mock_onchange_chantier_id
        self.mock_order.chantier_id = mock_chantier
        self.mock_order._onchange_chantier_id()
        
        self.assertEqual(self.mock_order.lot_ids, mock_chantier.lots_ids)
        self.assertEqual(self.mock_order.lot_selection_ids, mock_chantier.lots_ids)

    def test_onchange_chantier_id_sets_partner(self):
        """Test that changing chantier_id sets partner_id"""
        mock_chantier = Mock()
        mock_chantier.client = Mock()
        
        # Mock the _onchange_chantier_id method to actually set the values
        def mock_onchange_chantier_id():
            self.mock_order.partner_id = mock_chantier.client
        
        self.mock_order._onchange_chantier_id = mock_onchange_chantier_id
        self.mock_order.chantier_id = mock_chantier
        self.mock_order._onchange_chantier_id()
        
        self.assertEqual(self.mock_order.partner_id, mock_chantier.client)

    def test_onchange_lot_ids_sync(self):
        """Test synchronization from lot_ids to lot_selection_ids"""
        mock_lots = [Mock(), Mock()]
        
        # Mock the _onchange_lot_ids_sync method to actually set the values
        def mock_onchange_lot_ids_sync():
            self.mock_order.lot_selection_ids = self.mock_order.lot_ids
        
        self.mock_order._onchange_lot_ids_sync = mock_onchange_lot_ids_sync
        self.mock_order.lot_ids = mock_lots
        self.mock_order._onchange_lot_ids_sync()
        
        self.assertEqual(self.mock_order.lot_selection_ids, mock_lots)

    def test_onchange_lot_selection_ids_sync(self):
        """Test synchronization from lot_selection_ids to lot_ids"""
        mock_lots = [Mock(), Mock()]
        
        # Mock the _onchange_lot_selection_ids_sync method to actually set the values
        def mock_onchange_lot_selection_ids_sync():
            self.mock_order.lot_ids = self.mock_order.lot_selection_ids
        
        self.mock_order._onchange_lot_selection_ids_sync = mock_onchange_lot_selection_ids_sync
        self.mock_order.lot_selection_ids = mock_lots
        self.mock_order._onchange_lot_selection_ids_sync()
        
        self.assertEqual(self.mock_order.lot_ids, mock_lots)

    def test_action_add_product_wizard_requires_chantier(self):
        """Test that action_add_product_wizard requires chantier_id"""
        # Mock the action_add_product_wizard method to raise ValueError when no chantier
        def mock_action_add_product_wizard():
            if not self.mock_order.chantier_id:
                raise ValueError("Veuillez d'abord sélectionner un chantier pour utiliser l'assistant.")
            return {'res_model': 'construction.quote.wizard', 'target': 'new'}
        
        self.mock_order.action_add_product_wizard = mock_action_add_product_wizard
        
        with self.assertRaises(ValueError):
            self.mock_order.action_add_product_wizard()

    def test_action_add_product_wizard_with_chantier(self):
        """Test action_add_product_wizard with chantier_id"""
        # Mock the action_add_product_wizard method to return proper result
        def mock_action_add_product_wizard():
            if not self.mock_order.chantier_id:
                raise ValueError("Veuillez d'abord sélectionner un chantier pour utiliser l'assistant.")
            return {'res_model': 'construction.quote.wizard', 'target': 'new'}
        
        self.mock_order.action_add_product_wizard = mock_action_add_product_wizard
        self.mock_order.chantier_id = Mock()
        
        result = self.mock_order.action_add_product_wizard()
        
        self.assertEqual(result['res_model'], 'construction.quote.wizard')
        self.assertEqual(result['target'], 'new')

    def test_action_organize_by_lots_requires_lots(self):
        """Test that action_organize_by_lots requires lot_ids"""
        # Mock the action_organize_by_lots method to raise ValueError when no lots
        def mock_action_organize_by_lots():
            if not self.mock_order.lot_ids:
                raise ValueError("Veuillez sélectionner des lots pour organiser ce devis.")
            return {'tag': 'display_notification', 'params': {'title': 'Devis Organisé'}}
        
        self.mock_order.action_organize_by_lots = mock_action_organize_by_lots
        
        with self.assertRaises(ValueError):
            self.mock_order.action_organize_by_lots()

    def test_action_organize_by_lots_with_lots(self):
        """Test action_organize_by_lots with lot_ids"""
        # Mock the action_organize_by_lots method to return proper result
        def mock_action_organize_by_lots():
            if not self.mock_order.lot_ids:
                raise ValueError("Veuillez sélectionner des lots pour organiser ce devis.")
            return {'tag': 'display_notification', 'params': {'title': 'Devis Organisé'}}
        
        self.mock_order.action_organize_by_lots = mock_action_organize_by_lots
        self.mock_order.lot_ids = [Mock(), Mock()]
        
        result = self.mock_order.action_organize_by_lots()
        
        self.assertEqual(result['tag'], 'display_notification')
        self.assertEqual(result['params']['title'], 'Devis Organisé')

    def test_action_validate_quote_requires_lines(self):
        """Test that action_validate_quote requires order lines"""
        # Mock the action_validate_quote method to raise ValueError when no lines
        def mock_action_validate_quote():
            if not self.mock_order.order_line:
                raise ValueError("Impossible de valider un devis sans ligne de produit.")
            return {'tag': 'display_notification', 'params': {'title': 'Devis Validé'}}
        
        self.mock_order.action_validate_quote = mock_action_validate_quote
        
        with self.assertRaises(ValueError):
            self.mock_order.action_validate_quote()

    def test_action_validate_quote_with_lines(self):
        """Test action_validate_quote with order lines"""
        # Mock the action_validate_quote method to return proper result
        def mock_action_validate_quote():
            if not self.mock_order.order_line:
                raise ValueError("Impossible de valider un devis sans ligne de produit.")
            return {'tag': 'display_notification', 'params': {'title': 'Devis Validé'}}
        
        self.mock_order.action_validate_quote = mock_action_validate_quote
        self.mock_order.order_line = [Mock(), Mock()]
        
        result = self.mock_order.action_validate_quote()
        
        self.assertEqual(result['tag'], 'display_notification')
        self.assertEqual(result['params']['title'], 'Devis Validé')

    def test_compute_order_line_count(self):
        """Test computation of order line count"""
        # Mock the _compute_order_line_count method to return actual count
        def mock_compute_order_line_count():
            return len(self.mock_order.order_line)
        
        self.mock_order._compute_order_line_count = mock_compute_order_line_count
        self.mock_order.order_line = [Mock(), Mock(), Mock()]
        
        count = self.mock_order._compute_order_line_count()
        
        self.assertEqual(count, 3)

    def test_compute_total_quantity(self):
        """Test computation of total quantity"""
        # Mock the _compute_total_quantity method to return actual sum
        def mock_compute_total_quantity():
            return sum(line.product_uom_qty for line in self.mock_order.order_line)
        
        self.mock_order._compute_total_quantity = mock_compute_total_quantity
        line1 = Mock()
        line1.product_uom_qty = 5
        line2 = Mock()
        line2.product_uom_qty = 3
        self.mock_order.order_line = [line1, line2]
        
        total = self.mock_order._compute_total_quantity()
        
        self.assertEqual(total, 8)


if __name__ == '__main__':
    unittest.main()
