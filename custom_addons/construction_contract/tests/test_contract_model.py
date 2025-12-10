# -*- coding: utf-8 -*-
"""
Unit Tests for Contract Model
Tests contract lifecycle, signature workflow, and business logic
"""

from odoo.tests import common, tagged
from odoo.exceptions import ValidationError, UserError, AccessError
from datetime import date, timedelta
import base64
import logging

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install', 'construction_contract', 'contract_model')
class TestContractModel(common.TransactionCase):
    """Test Contract Model - Full Coverage"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # Create test data
        cls.chantier = cls.env['construction.chantier'].create({
            'name': 'Test Construction Site',
            'reference': 'SITE-001',
            'address': '123 Test Street',
            'city': 'Paris',
            'zip_code': '75001',
        })
        
        cls.subcontractor = cls.env['res.partner'].create({
            'name': 'Test Subcontractor',
            'contact_type': 'sous_traitant',
            'company_registry': '12345678901234',
            'email': 'test@subcontractor.com',
            'phone': '+33123456789',
            'city': 'Lyon',
            'document_URSSAF_status': 'valid',
            'document_KBIS_status': 'valid',
            'document_insurance_status': 'valid',
        })
        
        cls.lot = cls.env['construction.lot'].create({
            'name': 'Test Work Package',
            'chantier_id': cls.chantier.id,
            'description': 'Test description',
        })
        
        cls.template = cls.env['construction.contract.template'].create({
            'name': 'Test Template',
            'grapesjs_html': '<div><h1>{{ contract.name }}</h1></div>',
            'grapesjs_css': 'body { font-family: Arial; }',
        })
        
        cls.contract = cls.env['construction.contract'].create({
            'chantier_id': cls.chantier.id,
            'subcontractor_id': cls.subcontractor.id,
            'lot_ids': [(6, 0, [cls.lot.id])],
            'template_id': cls.template.id,
            'date': date.today(),
            'start_date': date.today(),
            'end_date': date.today() + timedelta(days=30),
            'retention_rate': 5.0,
        })

    def test_01_contract_creation(self):
        """Test contract creation with all required fields"""
        contract = self.env['construction.contract'].create({
            'chantier_id': self.chantier.id,
            'subcontractor_id': self.subcontractor.id,
            'lot_ids': [(6, 0, [self.lot.id])],
            'template_id': self.template.id,
            'date': date.today(),
            'start_date': date.today(),
            'end_date': date.today() + timedelta(days=30),
        })
        
        self.assertTrue(contract, "Contract should be created")
        self.assertNotEqual(contract.name, 'New', "Contract should have generated name")
        self.assertEqual(contract.state, 'draft', "New contract should be in draft state")

    def test_02_contract_name_generation(self):
        """Test contract name sequence generation"""
        contract1 = self.contract.copy({
            'name': 'New',
        })
        contract1._compute_name()
        
        contract2 = self.env['construction.contract'].create({
            'chantier_id': self.chantier.id,
            'subcontractor_id': self.subcontractor.id,
            'lot_ids': [(6, 0, [self.lot.id])],
            'template_id': self.template.id,
            'date': date.today(),
            'start_date': date.today(),
            'end_date': date.today() + timedelta(days=30),
        })
        
        self.assertNotEqual(contract1.name, contract2.name, "Contracts should have unique names")

    def test_03_state_validation(self):
        """Test state validation and transitions"""
        # Test valid transition: draft -> generated
        self.assertEqual(self.contract.state, 'draft')
        self.contract.action_generate_pdf()
        self.assertEqual(self.contract.state, 'generated', "State should change to generated")

    def test_04_pdf_generation(self):
        """Test PDF generation workflow"""
        self.assertEqual(self.contract.state, 'draft')
        
        result = self.contract.action_generate_pdf()
        
        self.assertTrue(result, "PDF generation should succeed")
        self.assertTrue(self.contract.pdf_document, "Contract should have PDF")
        self.assertEqual(self.contract.state, 'generated', "State should be generated")

    def test_05_regenerate_pdf(self):
        """Test PDF regeneration"""
        # Generate initial PDF
        self.contract.action_generate_pdf()
        first_hash = self.contract.pdf_hash_before_signature
        
        # Regenerate
        self.contract.action_regenerate_pdf()
        second_hash = self.contract.pdf_hash_before_signature
        
        # Hashes should be same if no template change
        self.assertEqual(first_hash, second_hash, "Hashes should match if template unchanged")

    def test_06_send_for_signature(self):
        """Test sending contract for signature"""
        self.contract.action_generate_pdf()
        
        result = self.contract.action_send_for_signature()
        
        self.assertTrue(result, "Send should succeed")
        self.assertEqual(self.contract.state, 'sent', "State should be sent")
        self.assertTrue(self.contract.sent_date, "Should have sent date")
        self.assertTrue(self.contract.access_token, "Should have access token")

    def test_07_token_generation(self):
        """Test access token generation"""
        self.contract.action_generate_pdf()
        self.contract.action_send_for_signature()
        
        self.assertTrue(self.contract.access_token, "Should have access token")
        self.assertGreater(len(self.contract.access_token), 20, "Token should be long enough")

    def test_08_token_expiry(self):
        """Test token expiry validation"""
        self.contract.action_generate_pdf()
        self.contract.action_send_for_signature()
        
        # Token should be valid
        self.assertFalse(self.contract._is_token_expired(self.contract.access_token))
        
        # Expire token
        self.contract.write({
            'token_expiry_date': date.today() - timedelta(days=1)
        })
        self.contract.invalidate_recordset(['token_expiry_date'])
        
        self.assertTrue(self.contract._is_token_expired(self.contract.access_token))

    def test_09_page_validation(self):
        """Test page validation workflow"""
        self.contract.action_generate_pdf()
        self.contract.action_send_for_signature()
        self.contract.action_mark_in_progress()
        
        # Validate first page
        result = self.contract.portal_validate_page(
            1,
            self.contract.access_token,
            time_spent=10
        )
        
        self.assertTrue(result.get('success'), "Validation should succeed")
        self.assertEqual(result.get('validated_pages'), [1], "Should have validated page 1")

    def test_10_signature_save(self):
        """Test signature saving"""
        self.contract.action_generate_pdf()
        self.contract.action_send_for_signature()
        self.contract.action_mark_in_progress()
        
        # Validate all pages first
        for page in range(1, self.contract.pdf_page_count + 1):
            self.contract.portal_validate_page(page, self.contract.access_token)
        
        # Create signature image (minimal PNG)
        signature_data = base64.b64encode(
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
        ).decode('utf-8')
        
        result = self.contract.portal_save_signature(
            signature_data,
            self.contract.access_token,
            ip_address='127.0.0.1',
            user_agent='Test Agent'
        )
        
        self.assertEqual(result['status'], 'success', "Signature should be saved")
        self.assertTrue(self.contract.signature_id, "Contract should have signature")
        self.assertEqual(self.contract.state, 'signed', "Contract should be signed")

    def test_11_signature_requires_all_pages_validated(self):
        """Test that all pages must be validated before signing"""
        self.contract.action_generate_pdf()
        self.contract.action_send_for_signature()
        self.contract.action_mark_in_progress()
        
        signature_data = base64.b64encode(
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
        ).decode('utf-8')
        
        with self.assertRaises(ValidationError) as context:
            self.contract.portal_save_signature(
                signature_data,
                self.contract.access_token
            )
        
        self.assertIn('pages must be validated', str(context.exception))

    def test_12_invalid_token_rejected(self):
        """Test that invalid tokens are rejected"""
        self.contract.action_generate_pdf()
        self.contract.action_send_for_signature()
        
        with self.assertRaises(ValidationError) as context:
            self.contract.portal_validate_page(1, 'invalid_token')
        
        self.assertIn('invalid', str(context.exception).lower())

    def test_13_expired_token_rejected(self):
        """Test that expired tokens are rejected"""
        self.contract.action_generate_pdf()
        self.contract.action_send_for_signature()
        self.contract.write({
            'token_expiry_date': date.today() - timedelta(days=1)
        })
        self.contract.invalidate_recordset(['token_expiry_date'])
        
        with self.assertRaises(ValidationError) as context:
            self.contract.portal_validate_page(1, self.contract.access_token)
        
        self.assertIn('expired', str(context.exception).lower())

    def test_14_computed_fields(self):
        """Test computed fields calculation"""
        # Test portal_url
        self.contract.action_generate_pdf()
        self.contract.action_send_for_signature()
        
        portal_url = self.contract.portal_url
        self.assertIn('/my/contract/', portal_url)
        self.assertIn(self.contract.access_token, portal_url)
        
        # Test purchase_order_count
        count = self.contract.purchase_order_count
        self.assertIsInstance(count, int)
        self.assertGreaterEqual(count, 0)

    def test_15_amount_calculations(self):
        """Test amount calculation fields"""
        # Create purchase order
        po = self.env['purchase.order'].create({
            'partner_id': self.subcontractor.id,
            'chantier_id': self.chantier.id,
            'lot_ids': [(6, 0, [self.lot.id])],
            'state': 'purchase',
            'order_line': [(0, 0, {
                'name': 'Test Product',
                'product_qty': 1,
                'price_unit': 1000.0,
                'lot_id': self.lot.id,
            })],
        })
        
        self.contract._compute_purchase_orders()
        
        self.assertGreater(self.contract.total_amount_ht, 0, "Should calculate HT amount")
        self.assertGreater(self.contract.total_amount_ttc, 0, "Should calculate TTC amount")

    def test_16_retention_calculation(self):
        """Test retention amount calculation"""
        self.contract.total_amount_ttc = 10000.0
        self.contract.retention_rate = 5.0
        self.contract._compute_retention()
        
        expected_retention = 10000.0 * 0.05
        self.assertEqual(self.contract.retention_amount, expected_retention)

    def test_17_certificate_generation(self):
        """Test certificate of completion generation"""
        # Sign contract first
        self.contract.action_generate_pdf()
        self.contract.action_send_for_signature()
        self.contract.action_mark_in_progress()
        
        # Validate all pages
        for page in range(1, self.contract.pdf_page_count + 1):
            self.contract.portal_validate_page(page, self.contract.access_token)
        
        # Save signature
        signature_data = base64.b64encode(
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
        ).decode('utf-8')
        self.contract.portal_save_signature(
            signature_data,
            self.contract.access_token
        )
        
        # Certificate should be generated
        self.assertTrue(self.contract.certificate_of_completion, "Should have certificate")

    def test_18_cannot_cancel_signed_contract(self):
        """Test that signed contracts cannot be cancelled"""
        self.contract.action_generate_pdf()
        self.contract.action_send_for_signature()
        self.contract.action_mark_in_progress()
        
        # Validate and sign
        for page in range(1, self.contract.pdf_page_count + 1):
            self.contract.portal_validate_page(page, self.contract.access_token)
        
        signature_data = base64.b64encode(
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
        ).decode('utf-8')
        self.contract.portal_save_signature(
            signature_data,
            self.contract.access_token
        )
        
        # Try to cancel
        with self.assertRaises(UserError) as context:
            self.contract.action_cancel()
        
        self.assertIn('signed', str(context.exception).lower())

    def test_19_reminder_sending(self):
        """Test reminder sending"""
        self.contract.action_generate_pdf()
        self.contract.action_send_for_signature()
        
        result = self.contract.action_send_reminder()
        
        self.assertTrue(result, "Reminder should be sent")

    def test_20_archive_contract(self):
        """Test contract archiving"""
        self.contract.action_archive()
        
        self.assertFalse(self.contract.active, "Contract should be archived")

    def test_21_pdf_with_signature_context(self):
        """Test PDF regeneration with signature in context"""
        self.contract.action_generate_pdf()
        self.contract.action_send_for_signature()
        self.contract.action_mark_in_progress()
        
        # Validate all pages and sign
        for page in range(1, self.contract.pdf_page_count + 1):
            self.contract.portal_validate_page(page, self.contract.access_token)
        
        signature_data = base64.b64encode(
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
        ).decode('utf-8')
        self.contract.portal_save_signature(
            signature_data,
            self.contract.access_token
        )
        
        # PDF should be regenerated with signature
        self.assertTrue(self.contract.pdf_document, "Should have PDF with signature")

    def test_22_error_handling_invalid_state(self):
        """Test error handling for invalid state transitions"""
        # Try to mark as signed without going through workflow
        with self.assertRaises(UserError) as context:
            self.contract.action_mark_signed()
        
        self.assertIn('in progress', str(context.exception).lower())

    def test_23_error_handling_missing_pdf(self):
        """Test error handling when PDF doesn't exist"""
        # Try to send without PDF
        with self.assertRaises(UserError) as context:
            self.contract.action_send_for_signature()
        
        self.assertIn('pdf', str(context.exception).lower())

    def test_24_portal_url_computation(self):
        """Test portal URL computation"""
        self.contract.action_generate_pdf()
        self.contract.action_send_for_signature()
        
        url = self.contract._compute_portal_url()
        
        self.assertIn('/my/contract/', url)
        self.assertIn(str(self.contract.id), url)
        self.assertIn(self.contract.access_token, url)


