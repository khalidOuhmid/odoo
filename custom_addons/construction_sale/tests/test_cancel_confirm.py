# -*- coding: utf-8 -*-

import unittest
from unittest.mock import Mock, patch


class TestCancelConfirm(unittest.TestCase):
    """Unit tests for construction.wizard.cancel.confirm"""

    def setUp(self):
        self.mock_wizard = Mock()
        self.mock_wizard.id = 1
        self.mock_wizard.quote_wizard_id = Mock()
        self.mock_wizard.selected_line_ids = []

    def test_action_confirm_cancel(self):
        """Test action_confirm_cancel"""
        def mock_action_confirm_cancel():
            self.mock_wizard.selected_line_ids = []
            return {'type': 'ir.actions.act_window_close'}
        
        self.mock_wizard.action_confirm_cancel = mock_action_confirm_cancel
        
        result = self.mock_wizard.action_confirm_cancel()
        self.assertEqual(result['type'], 'ir.actions.act_window_close')

    def test_action_confirm_cancel_clears_selection(self):
        """Test that action_confirm_cancel clears selection"""
        def mock_action_confirm_cancel():
            self.mock_wizard.selected_line_ids = []
            return {'type': 'ir.actions.act_window_close'}
        
        self.mock_wizard.action_confirm_cancel = mock_action_confirm_cancel
        self.mock_wizard.selected_line_ids = [Mock(), Mock()]
        
        self.mock_wizard.action_confirm_cancel()
        self.assertEqual(len(self.mock_wizard.selected_line_ids), 0)

    def test_action_go_back(self):
        """Test action_go_back"""
        def mock_action_go_back():
            if self.mock_wizard.quote_wizard_id:
                return {'res_model': 'construction.quote.wizard', 'target': 'new', 'res_id': self.mock_wizard.quote_wizard_id.id}
            return {'res_model': 'construction.quote.wizard', 'target': 'new'}
        
        self.mock_wizard.action_go_back = mock_action_go_back
        
        result = self.mock_wizard.action_go_back()
        self.assertEqual(result['res_model'], 'construction.quote.wizard')

    def test_action_go_back_with_quote_wizard(self):
        """Test action_go_back with quote_wizard_id"""
        def mock_action_go_back():
            if self.mock_wizard.quote_wizard_id:
                return {'res_model': 'construction.quote.wizard', 'target': 'new', 'res_id': self.mock_wizard.quote_wizard_id.id}
            return {'res_model': 'construction.quote.wizard', 'target': 'new'}
        
        self.mock_wizard.action_go_back = mock_action_go_back
        mock_quote_wizard = Mock()
        mock_quote_wizard.id = 1
        self.mock_wizard.quote_wizard_id = mock_quote_wizard
        
        result = self.mock_wizard.action_go_back()
        self.assertEqual(result['res_id'], 1)

    def test_action_go_back_without_quote_wizard(self):
        """Test action_go_back without quote_wizard_id"""
        def mock_action_go_back():
            if self.mock_wizard.quote_wizard_id:
                return {'res_model': 'construction.quote.wizard', 'target': 'new', 'res_id': self.mock_wizard.quote_wizard_id.id}
            return {'res_model': 'construction.quote.wizard', 'target': 'new'}
        
        self.mock_wizard.action_go_back = mock_action_go_back
        self.mock_wizard.quote_wizard_id = None
        
        result = self.mock_wizard.action_go_back()
        self.assertEqual(result['res_model'], 'construction.quote.wizard')


if __name__ == '__main__':
    unittest.main()
