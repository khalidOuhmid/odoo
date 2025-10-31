# -*- coding: utf-8 -*-
"""
Contract Generation Tests

Tests for the new contract generation architecture.
These tests validate the clean, modular approach to contract generation.
"""

from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class TestContractGeneration(TransactionCase):
    """
    Test cases for contract generation architecture.
    
    This class tests the new contract generation system to ensure
    it works correctly and follows the established patterns.
    """

    def setUp(self):
        """Set up test data."""
        super().setUp()
        
        # Create test chantier
        self.chantier = self.env['construction.chantier'].create({
            'name': 'Test Construction Site',
            'description': 'Test construction site for contract generation',
        })
        
        # Create test subcontractor
        self.subcontractor = self.env['res.partner'].create({
            'name': 'Test Subcontractor',
            'is_company': True,
            'email': 'test@subcontractor.com',
        })
        
        # Create test lots
        self.lot1 = self.env['construction.lot'].create({
            'name': 'Test Lot 1',
            'code': 'TL1',
            'chantier_id': self.chantier.id,
            'price': 25000.0,
        })
        
        self.lot2 = self.env['construction.lot'].create({
            'name': 'Test Lot 2',
            'code': 'TL2',
            'chantier_id': self.chantier.id,
            'price': 30000.0,
        })
        
        # Assign subcontractor to lots
        self.lot1.subcontractor_ids = [(4, self.subcontractor.id)]
        self.lot2.subcontractor_ids = [(4, self.subcontractor.id)]

    def test_contract_factory_creation(self):
        """Test contract factory creation."""
        factory = self.env['construction.contract.factory']
        
        # Test single lot contract creation
        contract_data = {
            'name': 'Test Single Lot Contract',
            'chantier_id': self.chantier.id,
            'subcontractor_id': self.subcontractor.id,
            'lot_ids': [self.lot1.id],
            'start_date': '2024-01-01',
            'total_amount': 25000.0,
        }
        
        contract = factory.create_contract('single_lot', **contract_data)
        
        self.assertEqual(contract.name, 'Test Single Lot Contract')
        self.assertEqual(contract.chantier_id, self.chantier)
        self.assertEqual(contract.subcontractor_id, self.subcontractor)
        self.assertEqual(len(contract.lot_ids), 1)
        self.assertEqual(contract.lot_ids[0], self.lot1)

    def test_contract_builder_usage(self):
        """Test contract builder usage."""
        contract_builder = self.env['construction.contract.builder'](self.env)
        
        contract = (contract_builder
                 .set_basic_info(self.chantier.id, self.subcontractor.id, 'Builder Test Contract')
                 .add_lots([self.lot1.id])
                 .set_dates('2024-01-01', '2024-02-01')
                 .set_financial_terms(25000.0, '30_days', self.env.company.currency_id.id)
                 .set_legal_terms(12, True, '43.34Z')
                 .set_additional_info('Test contract created with builder')
                 .build())
        
        self.assertEqual(contract.name, 'Builder Test Contract')
        self.assertEqual(contract.chantier_id.id, self.chantier.id)
        self.assertEqual(contract.subcontractor_id.id, self.subcontractor.id)
        self.assertEqual(len(contract.lot_ids), 1)
        self.assertEqual(contract.lot_ids[0].id, self.lot1.id)

    def test_contract_validator_validation(self):
        """Test contract validator validation."""
        validator = self.env['construction.contract.validator']
        
        # Test valid contract data
        valid_contract_data = {
            'chantier_id': self.chantier.id,
            'subcontractor_id': self.subcontractor.id,
            'lot_ids': [self.lot1.id],
            'start_date': '2024-01-01',
            'end_date': '2024-02-01',
            'total_amount': 25000.0,
            'payment_terms': '30_days',
            'warranty_period': 12,
            'insurance_required': True,
            'notes': 'Test contract',
            'urssaf_code': '43.34Z',
        }
        
        # Should not raise exception
        validator.validate_contract_data(valid_contract_data)
        
        # Test invalid contract data
        invalid_contract_data = {
            'chantier_id': self.chantier.id,
            'subcontractor_id': self.subcontractor.id,
            'lot_ids': [],
            'start_date': '2024-01-01',
            'total_amount': -1000.0,
        }
        
        # Should raise ValidationError
        with self.assertRaises(ValidationError):
            validator.validate_contract_data(invalid_contract_data)

    def test_multi_lot_handler_grouping(self):
        """Test multi-lot handler grouping."""
        multi_lot_handler = self.env['construction.multi.lot.handler']
        
        # Test if lots can be grouped
        can_group = multi_lot_handler.can_group_lots([self.lot1.id, self.lot2.id], self.subcontractor.id)
        self.assertTrue(can_group)
        
        # Test grouped lots info
        grouped_info = multi_lot_handler.get_grouped_lots_info([self.lot1.id, self.lot2.id], self.subcontractor.id)
        
        self.assertEqual(grouped_info['lot_count'], 2)
        self.assertEqual(grouped_info['total_amount'], 55000.0)
        self.assertEqual(grouped_info['chantier'], self.chantier)
        self.assertEqual(grouped_info['subcontractor'], self.subcontractor)

    def test_contract_orchestrator_generation(self):
        """Test contract orchestrator generation."""
        orchestrator = self.env['construction.contract.orchestrator']
        
        contract_data = {
            'chantier_id': self.chantier.id,
            'subcontractor_id': self.subcontractor.id,
            'lot_ids': [self.lot1.id],
            'start_date': '2024-01-01',
            'end_date': '2024-02-01',
            'total_amount': 25000.0,
            'payment_terms': '30_days',
            'warranty_period': 12,
            'insurance_required': True,
            'notes': 'Orchestrator test contract',
            'urssaf_code': '43.34Z',
        }
        
        contract = orchestrator.generate_contract(contract_data)
        
        self.assertEqual(contract.chantier_id, self.chantier)
        self.assertEqual(contract.subcontractor_id, self.subcontractor)
        self.assertEqual(len(contract.lot_ids), 1)
        self.assertEqual(contract.lot_ids[0], self.lot1)
        self.assertEqual(contract.total_amount, 25000.0)

    def test_multi_lot_contract_generation(self):
        """Test multi-lot contract generation."""
        orchestrator = self.env['construction.contract.orchestrator']
        
        contract_data = {
            'chantier_id': self.chantier.id,
            'subcontractor_id': self.subcontractor.id,
            'lot_ids': [self.lot1.id, self.lot2.id],
            'start_date': '2024-01-01',
            'end_date': '2024-03-01',
            'total_amount': 55000.0,
            'payment_terms': '45_days',
            'warranty_period': 18,
            'insurance_required': True,
            'notes': 'Multi-lot test contract',
            'urssaf_code': '43.34Z',
        }
        
        contract = orchestrator.generate_contract(contract_data)
        
        self.assertEqual(contract.chantier_id, self.chantier)
        self.assertEqual(contract.subcontractor_id, self.subcontractor)
        self.assertEqual(len(contract.lot_ids), 2)
        self.assertIn(self.lot1, contract.lot_ids)
        self.assertIn(self.lot2, contract.lot_ids)
        self.assertEqual(contract.total_amount, 55000.0)
        self.assertTrue(contract.is_multi_lot)
        self.assertEqual(contract.lot_count, 2)

    def test_contract_preview_generation(self):
        """Test contract preview generation."""
        orchestrator = self.env['construction.contract.orchestrator']
        
        contract_data = {
            'chantier_id': self.chantier.id,
            'subcontractor_id': self.subcontractor.id,
            'lot_ids': [self.lot1.id],
            'start_date': '2024-01-01',
            'end_date': '2024-02-01',
            'total_amount': 25000.0,
            'payment_terms': '30_days',
            'warranty_period': 12,
            'insurance_required': True,
            'notes': 'Preview test contract',
            'urssaf_code': '43.34Z',
        }
        
        preview_html = orchestrator.generate_preview(contract_data)
        
        self.assertIsInstance(preview_html, str)
        self.assertGreater(len(preview_html), 0)
        self.assertIn('<!DOCTYPE html>', preview_html)

    def test_contract_validation(self):
        """Test contract validation."""
        orchestrator = self.env['construction.contract.orchestrator']
        
        # Test valid contract data
        valid_contract_data = {
            'chantier_id': self.chantier.id,
            'subcontractor_id': self.subcontractor.id,
            'lot_ids': [self.lot1.id],
            'start_date': '2024-01-01',
            'end_date': '2024-02-01',
            'total_amount': 25000.0,
            'payment_terms': '30_days',
            'warranty_period': 12,
            'insurance_required': True,
            'notes': 'Validation test contract',
            'urssaf_code': '43.34Z',
        }
        
        is_valid = orchestrator.validate_contract_configuration(valid_contract_data)
        self.assertTrue(is_valid)
        
        # Test invalid contract data
        invalid_contract_data = {
            'chantier_id': self.chantier.id,
            'subcontractor_id': self.subcontractor.id,
            'lot_ids': [],
            'start_date': '2024-01-01',
            'total_amount': -1000.0,
        }
        
        with self.assertRaises(ValidationError):
            orchestrator.validate_contract_configuration(invalid_contract_data)

    def test_contract_wizard_integration(self):
        """Test contract wizard integration."""
        wizard = self.env['construction.contract.generation.wizard'].create({
            'chantier_id': self.chantier.id,
            'subcontractor_id': self.subcontractor.id,
            'lot_ids': [(6, 0, [self.lot1.id])],
            'start_date': '2024-01-01',
            'end_date': '2024-02-01',
            'total_amount': 25000.0,
            'payment_terms': '30_days',
            'warranty_period': 12,
            'insurance_required': True,
            'notes': 'Wizard test contract',
            'urssaf_code': '43.34Z',
        })
        
        # Test wizard configuration
        self.assertEqual(wizard.chantier_id, self.chantier)
        self.assertEqual(wizard.subcontractor_id, self.subcontractor)
        self.assertEqual(len(wizard.lot_ids), 1)
        self.assertEqual(wizard.lot_ids[0], self.lot1)
        self.assertEqual(wizard.total_amount, 25000.0)
        
        # Test wizard validation
        wizard._validate_configuration()
        
        # Test wizard contract data preparation
        contract_data = wizard._prepare_contract_data()
        self.assertEqual(contract_data['chantier_id'], self.chantier.id)
        self.assertEqual(contract_data['subcontractor_id'], self.subcontractor.id)
        self.assertEqual(contract_data['lot_ids'], [self.lot1.id])
        self.assertEqual(contract_data['total_amount'], 25000.0)

    def test_multi_lot_contract_wizard(self):
        """Test multi-lot contract wizard."""
        wizard = self.env['construction.contract.generation.wizard'].create({
            'chantier_id': self.chantier.id,
            'subcontractor_id': self.subcontractor.id,
            'lot_ids': [(6, 0, [self.lot1.id, self.lot2.id])],
            'start_date': '2024-01-01',
            'end_date': '2024-03-01',
            'total_amount': 55000.0,
            'payment_terms': '45_days',
            'warranty_period': 18,
            'insurance_required': True,
            'notes': 'Multi-lot wizard test contract',
            'urssaf_code': '43.34Z',
        })
        
        # Test wizard multi-lot configuration
        self.assertEqual(wizard.chantier_id, self.chantier)
        self.assertEqual(wizard.subcontractor_id, self.subcontractor)
        self.assertEqual(len(wizard.lot_ids), 2)
        self.assertIn(self.lot1, wizard.lot_ids)
        self.assertIn(self.lot2, wizard.lot_ids)
        self.assertEqual(wizard.total_amount, 55000.0)
        self.assertTrue(wizard.is_multi_lot)
        self.assertEqual(wizard.lot_count, 2)
        
        # Test wizard validation
        wizard._validate_configuration()
        
        # Test wizard contract data preparation
        contract_data = wizard._prepare_contract_data()
        self.assertEqual(contract_data['chantier_id'], self.chantier.id)
        self.assertEqual(contract_data['subcontractor_id'], self.subcontractor.id)
        self.assertEqual(contract_data['lot_ids'], [self.lot1.id, self.lot2.id])
        self.assertEqual(contract_data['total_amount'], 55000.0)

    def test_contract_generation_complete_flow(self):
        """Test complete contract generation flow."""
        # Test complete flow using wizard
        wizard = self.env['construction.contract.generation.wizard'].create({
            'chantier_id': self.chantier.id,
            'subcontractor_id': self.subcontractor.id,
            'lot_ids': [(6, 0, [self.lot1.id, self.lot2.id])],
            'start_date': '2024-01-01',
            'end_date': '2024-03-01',
            'total_amount': 55000.0,
            'payment_terms': '45_days',
            'warranty_period': 18,
            'insurance_required': True,
            'notes': 'Complete flow test contract',
            'urssaf_code': '43.34Z',
        })
        
        # Test preview generation
        wizard.action_generate_preview()
        self.assertEqual(wizard.current_step, 'preview')
        self.assertTrue(wizard.preview_ready)
        self.assertIsInstance(wizard.preview_html, str)
        self.assertGreater(len(wizard.preview_html), 0)
        
        # Test contract generation
        result = wizard.action_generate_contract()
        self.assertEqual(wizard.current_step, 'finalize')
        self.assertIsNotNone(wizard.generated_contract_id)
        self.assertEqual(wizard.generated_contract_id.chantier_id, self.chantier)
        self.assertEqual(wizard.generated_contract_id.subcontractor_id, self.subcontractor)
        self.assertEqual(len(wizard.generated_contract_id.lot_ids), 2)
        self.assertTrue(wizard.generated_contract_id.is_multi_lot)
        self.assertEqual(wizard.generated_contract_id.lot_count, 2)
        
        # Test back to configuration
        wizard.action_back_to_config()
        self.assertEqual(wizard.current_step, 'config')
        self.assertFalse(wizard.preview_ready)
        self.assertEqual(wizard.preview_html, '')
        
        # Test modify and regenerate
        wizard.action_modify_and_regenerate()
        self.assertEqual(wizard.current_step, 'config')
        self.assertFalse(wizard.preview_ready)
        self.assertEqual(wizard.preview_html, '')
