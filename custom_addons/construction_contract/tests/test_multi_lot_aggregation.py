# -*- coding: utf-8 -*-
"""
Unit Tests for Multi-Lot Contract Aggregation

Tests the SAP-grade multi-lot detection and aggregation features:
- Auto-detection of related lots for same subcontractor
- Aggregation of purchase orders across lots
- One Lot → One Contract integrity
- Wizard auto-selection behavior
"""

from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError
from datetime import date, timedelta
import logging

_logger = logging.getLogger(__name__)


@tagged('contract', 'multi_lot', 'aggregation')
class TestMultiLotAggregation(TransactionCase):
    """
    Test Suite for Multi-Lot Contract Aggregation
    """

    @classmethod
    def setUpClass(cls):
        """Set up test data"""
        super().setUpClass()
        
        # Get or create required records
        cls.partner_model = cls.env['res.partner']
        cls.chantier_model = cls.env['construction.chantier']
        cls.lot_model = cls.env['construction.lot']
        cls.contract_model = cls.env['construction.contract']
        cls.wizard_model = cls.env['contract.creation.wizard']

        import base64
        from datetime import date, timedelta
        _mock_doc = base64.b64encode(b'%PDF-1.4 mock').decode('ascii')
        _expiry = date.today() + timedelta(days=365)

        # Create subcontractor with compliant docs and SIRET
        cls.subcontractor = cls.partner_model.create({
            'name': 'Test Subcontractor Multi-Lot',
            'company_type': 'company',
            'is_company': True,
            'company_registry': '12345678901234',
        })
        cls.subcontractor.write({
            'doc_urssaf': _mock_doc, 'doc_urssaf_expiry': _expiry,
            'doc_kbis': _mock_doc, 'doc_kbis_expiry': _expiry,
            'doc_insurance_dec': _mock_doc, 'doc_insurance_dec_expiry': _expiry,
        })

        # Create client partner
        cls.client = cls.partner_model.create({'name': 'Client Multi-Lot Test'})

        # Create chantier
        cls.chantier = cls.chantier_model.create({
            'name': 'Test Chantier Multi-Lot',
            'client': cls.client.id,
        })

        # Create lot categories
        LotCat = cls.env['construction.lot.category']
        cls.cat_1 = LotCat.create({'name': 'Gros Oeuvre ML', 'code': 'GO_ML'})
        cls.cat_2 = LotCat.create({'name': 'Electricite ML', 'code': 'ELEC_ML'})
        cls.cat_3 = LotCat.create({'name': 'Plomberie ML', 'code': 'PLOM_ML'})
        cls.cat_4 = LotCat.create({'name': 'Interne ML', 'code': 'INT_ML'})

        # Create 3 lots for the same subcontractor
        cls.lot_1 = cls.lot_model.create({
            'category_id': cls.cat_1.id,
            'chantier_id': cls.chantier.id,
            'subcontractor_id': cls.subcontractor.id,
            'execution_type': 'external',
        })

        cls.lot_2 = cls.lot_model.create({
            'category_id': cls.cat_2.id,
            'chantier_id': cls.chantier.id,
            'subcontractor_id': cls.subcontractor.id,
            'execution_type': 'external',
        })

        cls.lot_3 = cls.lot_model.create({
            'category_id': cls.cat_3.id,
            'chantier_id': cls.chantier.id,
            'subcontractor_id': cls.subcontractor.id,
            'execution_type': 'external',
        })

        # Create an internal lot (should NOT be aggregated)
        cls.lot_internal = cls.lot_model.create({
            'category_id': cls.cat_4.id,
            'chantier_id': cls.chantier.id,
            'execution_type': 'internal',  # No subcontractor
        })

    def test_01_lot_has_no_contract_initially(self):
        """Test that lots have no contract assigned initially"""
        self.assertFalse(self.lot_1.contract_id, "Lot 1 should have no contract initially")
        self.assertFalse(self.lot_2.contract_id, "Lot 2 should have no contract initially")
        self.assertFalse(self.lot_3.contract_id, "Lot 3 should have no contract initially")

    def test_02_wizard_detects_related_lots(self):
        """Test that wizard correctly detects related lots for same subcontractor"""
        # Create wizard with chantier and subcontractor
        wizard = self.wizard_model.create({
            'chantier_id': self.chantier.id,
            'subcontractor_id': self.subcontractor.id,
            'start_date': date.today(),
            'end_date': date.today() + timedelta(days=90),
        })
        
        # Check aggregation warning
        self.assertTrue(wizard.show_aggregation_warning, 
                       "Should show aggregation warning for 3 related lots")
        self.assertEqual(wizard.related_lot_count, 3,
                        "Should detect exactly 3 related lots")

    def test_03_wizard_auto_selects_related_lots(self):
        """Test that wizard auto-selects all related lots on subcontractor change"""
        wizard = self.wizard_model.create({
            'chantier_id': self.chantier.id,
            'subcontractor_id': self.subcontractor.id,
            'start_date': date.today(),
            'end_date': date.today() + timedelta(days=90),
        })

        # Trigger onchange to auto-select lots
        wizard._onchange_auto_select_related_lots()
        
        # Check that all 3 external lots are selected
        lot_ids = wizard.lot_ids.ids
        self.assertIn(self.lot_1.id, lot_ids, "Lot 1 should be auto-selected")
        self.assertIn(self.lot_2.id, lot_ids, "Lot 2 should be auto-selected")
        self.assertIn(self.lot_3.id, lot_ids, "Lot 3 should be auto-selected")
        self.assertNotIn(self.lot_internal.id, lot_ids, 
                        "Internal lot should NOT be auto-selected")

    def test_04_contract_assigns_lots_via_one2many(self):
        """Test that creating a contract properly assigns lot_ids"""
        # Create contract template first
        template = self.env['construction.contract.template'].search([], limit=1)
        if not template:
            template = self.env['construction.contract.template'].create({
                'name': 'Test Template',
                'is_default': True,
            })
        
        # Create contract
        contract = self.contract_model.create({
            'chantier_id': self.chantier.id,
            'subcontractor_id': self.subcontractor.id,
            'template_id': template.id,
            'start_date': date.today(),
            'end_date': date.today() + timedelta(days=90),
        })
        
        # Assign lots to contract
        self.lot_1.contract_id = contract.id
        self.lot_2.contract_id = contract.id
        
        # Verify relationship
        self.assertEqual(len(contract.lot_ids), 2, 
                        "Contract should have 2 lots assigned")
        self.assertIn(self.lot_1, contract.lot_ids)
        self.assertIn(self.lot_2, contract.lot_ids)
        
        # Verify inverse relation
        self.assertEqual(self.lot_1.contract_id, contract,
                        "Lot 1 should reference the contract")
        self.assertEqual(self.lot_2.contract_id, contract,
                        "Lot 2 should reference the contract")

    def test_05_lot_cannot_be_on_multiple_contracts(self):
        """Test data integrity: a lot cannot be assigned to multiple contracts"""
        # This test verifies the Many2one relationship prevents double assignment
        template = self.env['construction.contract.template'].search([], limit=1)
        
        # Create first contract
        contract_1 = self.contract_model.create({
            'chantier_id': self.chantier.id,
            'subcontractor_id': self.subcontractor.id,
            'template_id': template.id,
            'start_date': date.today(),
            'end_date': date.today() + timedelta(days=90),
        })
        
        # Assign lot_3 to contract_1
        self.lot_3.contract_id = contract_1.id
        
        # Create second contract
        contract_2 = self.contract_model.create({
            'chantier_id': self.chantier.id,
            'subcontractor_id': self.subcontractor.id,
            'template_id': template.id,
            'start_date': date.today(),
            'end_date': date.today() + timedelta(days=90),
        })
        
        # Assign lot_3 to contract_2 (should move it from contract_1)
        self.lot_3.contract_id = contract_2.id
        
        # Verify lot moved to contract_2
        self.assertEqual(self.lot_3.contract_id, contract_2,
                        "Lot 3 should now be on contract_2")
        self.assertNotIn(self.lot_3, contract_1.lot_ids,
                        "Lot 3 should NOT be on contract_1 anymore")
        self.assertIn(self.lot_3, contract_2.lot_ids,
                     "Lot 3 should be on contract_2")

    def test_06_wizard_excludes_lots_with_contract(self):
        """Test that wizard only shows lots without existing contracts"""
        template = self.env['construction.contract.template'].search([], limit=1)
        
        # Create contract and assign lot_1
        contract = self.contract_model.create({
            'chantier_id': self.chantier.id,
            'subcontractor_id': self.subcontractor.id,
            'template_id': template.id,
            'start_date': date.today(),
            'end_date': date.today() + timedelta(days=90),
        })
        self.lot_1.contract_id = contract.id
        
        # Create wizard for same subcontractor
        wizard = self.wizard_model.create({
            'chantier_id': self.chantier.id,
            'subcontractor_id': self.subcontractor.id,
            'start_date': date.today(),
            'end_date': date.today() + timedelta(days=90),
        })
        
        # Should only detect 2 lots now (lot_2 and lot_3, excluding lot_1 which has contract)
        self.assertEqual(wizard.related_lot_count, 2,
                        "Should only detect 2 lots without contracts")
        
        # Verify available lots excludes lot_1
        available_lot_ids = wizard.available_lot_ids.ids
        self.assertNotIn(self.lot_1.id, available_lot_ids,
                        "Lot 1 with contract should not be available")


@tagged('contract', 'proof_file')
class TestProofFileGeneration(TransactionCase):
    """
    Test Suite for SAP-Grade Proof File Generation
    """

    @classmethod
    def setUpClass(cls):
        """Set up test data"""
        super().setUpClass()
        
        # Create minimal contract for testing
        import base64 as _b64
        _mock_doc = _b64.b64encode(b'%PDF-1.4 mock').decode('ascii')
        _expiry = date.today() + timedelta(days=365)

        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Subcontractor Proof',
            'company_type': 'company',
            'is_company': True,
            'company_registry': '99988877701234',
        })
        cls.partner.write({
            'doc_urssaf': _mock_doc, 'doc_urssaf_expiry': _expiry,
            'doc_kbis': _mock_doc, 'doc_kbis_expiry': _expiry,
            'doc_insurance_dec': _mock_doc, 'doc_insurance_dec_expiry': _expiry,
        })

        cls.client_proof = cls.env['res.partner'].create({'name': 'Client Proof'})
        cls.chantier = cls.env['construction.chantier'].create({
            'name': 'Test Chantier Proof',
            'client': cls.client_proof.id,
        })

        template = cls.env['construction.contract.template'].search([], limit=1)
        if not template:
            template = cls.env['construction.contract.template'].create({
                'name': 'Test Template Proof',
            })

        cls.contract = cls.env['construction.contract'].create({
            'chantier_id': cls.chantier.id,
            'subcontractor_id': cls.partner.id,
            'template_id': template.id,
            'start_date': date.today(),
            'end_date': date.today() + timedelta(days=90),
            'pdf_hash_before_signature': 'abc123hash',
            'bypass_compliance_check': True,
        })
        cls.contract.pdf_page_count = 7

    def test_01_proof_file_generates_json(self):
        """Test that proof file generation creates valid JSON"""
        import json
        
        proof_json = self.contract._generate_proof_file()
        
        self.assertIsNotNone(proof_json, "Proof file should be generated")
        
        # Parse JSON to verify it's valid
        proof_data = json.loads(proof_json)
        
        self.assertEqual(proof_data['version'], '1.0')
        self.assertIn('contract', proof_data)
        self.assertIn('document_integrity', proof_data)
        self.assertIn('reading_audit_trail', proof_data)
        self.assertIn('legal_notice', proof_data)

    def test_02_proof_file_contains_contract_info(self):
        """Test that proof file contains correct contract information"""
        import json
        
        proof_json = self.contract._generate_proof_file()
        proof_data = json.loads(proof_json)
        
        contract_info = proof_data['contract']
        self.assertEqual(contract_info['reference'], self.contract.name)
        self.assertEqual(contract_info['chantier_name'], self.chantier.name)
        self.assertEqual(contract_info['subcontractor_name'], self.partner.name)

    def test_03_proof_file_stores_in_contract(self):
        """Test that proof file is stored in contract record"""
        self.contract._generate_proof_file()
        
        self.assertTrue(self.contract.signature_proof_generated,
                       "signature_proof_generated should be True")
        self.assertIsNotNone(self.contract.signature_proof_json,
                            "signature_proof_json should be populated")
