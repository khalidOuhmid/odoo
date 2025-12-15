# -*- coding: utf-8 -*-
"""
Document Validation Wizard Tests

Tests for the document preview/validate/reject workflow.
"""
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import UserError
from datetime import date, timedelta
import base64

@tagged('post_install', '-at_install')
class TestDocumentValidation(TransactionCase):
    """Test suite for document validation wizard."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures."""
        super().setUpClass()
        
        cls.Partner = cls.env['res.partner']
        cls.Wizard = cls.env['document.validation.wizard']
        
        cls.subcontractor = cls.Partner.create({
            'name': 'Test Sous-traitant',
            'is_subcontractor': True,
            'supplier_rank': 1,
            'email': 'test@soustraitant.test',
        })
        
        cls.sample_doc = base64.b64encode(b'Test Document Content')
        cls.future_date = date.today() + timedelta(days=90)
    
    def _create_wizard(self, doc_type='kbis'):
        """Helper to create wizard with given doc type."""
        return self.Wizard.create({
            'partner_id': self.subcontractor.id,
            'doc_type': doc_type,
        })
    
    # ============= VALIDATION TESTS ============= #
    
    def test_validate_document_success(self):
        """Validating a document should succeed and update status."""
        # Set up document to validate
        self.subcontractor.write({
            'doc_kbis': self.sample_doc,
            'doc_kbis_expiry': self.future_date,
        })
        
        wizard = self._create_wizard('kbis')
        
        # Should have document content
        self.assertTrue(wizard.doc_content, "Wizard should load document content")
        
        # Validate should succeed
        result = wizard.action_validate()
        self.assertEqual(result.get('type'), 'ir.actions.act_window_close')
    
    def test_validate_without_document_raises_error(self):
        """Validating without document should raise UserError."""
        wizard = self._create_wizard('kbis')
        
        with self.assertRaises(UserError):
            wizard.action_validate()
    
    def test_doc_content_computed_correctly(self):
        """Document content should be computed from partner record."""
        self.subcontractor.write({
            'doc_kbis': self.sample_doc,
            'doc_kbis_filename': 'kbis_test.pdf',
        })
        
        wizard = self._create_wizard('kbis')
        
        self.assertEqual(wizard.doc_content, self.sample_doc)
        self.assertEqual(wizard.doc_filename, 'kbis_test.pdf')
        self.assertEqual(wizard.doc_mimetype, 'application/pdf')
    
    def test_mimetype_detection_pdf(self):
        """Should detect PDF mimetype correctly."""
        self.subcontractor.write({
            'doc_kbis': self.sample_doc,
            'doc_kbis_filename': 'test.PDF',
        })
        
        wizard = self._create_wizard('kbis')
        self.assertEqual(wizard.doc_mimetype, 'application/pdf')
    
    def test_mimetype_detection_jpeg(self):
        """Should detect JPEG mimetype correctly."""
        self.subcontractor.write({
            'doc_kbis': self.sample_doc,
            'doc_kbis_filename': 'test.jpg',
        })
        
        wizard = self._create_wizard('kbis')
        self.assertEqual(wizard.doc_mimetype, 'image/jpeg')
    
    def test_mimetype_detection_png(self):
        """Should detect PNG mimetype correctly."""
        self.subcontractor.write({
            'doc_kbis': self.sample_doc,
            'doc_kbis_filename': 'test.png',
        })
        
        wizard = self._create_wizard('kbis')
        self.assertEqual(wizard.doc_mimetype, 'image/png')
    
    # ============= REJECTION TESTS ============= #
    
    def test_reject_requires_reason(self):
        """Rejecting without reason should raise UserError."""
        self.subcontractor.write({
            'doc_kbis': self.sample_doc,
            'doc_kbis_expiry': self.future_date,
        })
        
        wizard = self._create_wizard('kbis')
        
        with self.assertRaises(UserError):
            wizard.action_reject()
    
    def test_reject_clears_document(self):
        """Rejecting should clear the document from partner."""
        self.subcontractor.write({
            'doc_kbis': self.sample_doc,
            'doc_kbis_expiry': self.future_date,
        })
        
        wizard = self._create_wizard('kbis')
        wizard.rejection_reason = "Document is blurry and unreadable"
        
        wizard.action_reject()
        
        self.assertFalse(
            self.subcontractor.doc_kbis,
            "Document should be cleared after rejection"
        )
    
    def test_reject_posts_chatter_message(self):
        """Rejecting should post a message in chatter."""
        self.subcontractor.write({
            'doc_kbis': self.sample_doc,
            'doc_kbis_expiry': self.future_date,
        })
        
        # Count messages before
        msg_count_before = len(self.subcontractor.message_ids)
        
        wizard = self._create_wizard('kbis')
        wizard.rejection_reason = "Document is blurry"
        wizard.action_reject()
        
        # Count messages after
        msg_count_after = len(self.subcontractor.message_ids)
        
        self.assertGreater(
            msg_count_after, msg_count_before,
            "Should post rejection message in chatter"
        )
    
    def test_reject_without_document_raises_error(self):
        """Rejecting without document should raise UserError."""
        wizard = self._create_wizard('kbis')
        wizard.rejection_reason = "Some reason"
        
        with self.assertRaises(UserError):
            wizard.action_reject()
    
    # ============= DOWNLOAD TESTS ============= #
    
    def test_download_returns_url_action(self):
        """Download should return an action with download URL."""
        self.subcontractor.write({
            'doc_kbis': self.sample_doc,
            'doc_kbis_filename': 'test.pdf',
        })
        
        wizard = self._create_wizard('kbis')
        result = wizard.action_download()
        
        self.assertEqual(result.get('type'), 'ir.actions.act_url')
        self.assertIn('download=true', result.get('url', ''))
    
    def test_download_without_document_raises_error(self):
        """Download without document should raise UserError."""
        wizard = self._create_wizard('kbis')
        
        with self.assertRaises(UserError):
            wizard.action_download()
    
    # ============= PARTNER ACTION TESTS ============= #
    
    def test_partner_open_validation_wizard(self):
        """Partner action should open validation wizard correctly."""
        self.subcontractor.write({
            'doc_kbis': self.sample_doc,
        })
        
        result = self.subcontractor.with_context(
            default_doc_type='kbis'
        ).action_open_validation_wizard()
        
        self.assertEqual(result.get('res_model'), 'document.validation.wizard')
        self.assertEqual(result.get('target'), 'new')
        self.assertEqual(result['context']['default_doc_type'], 'kbis')
    
    def test_partner_open_validation_without_doc_type_raises_error(self):
        """Opening wizard without doc_type should raise UserError."""
        with self.assertRaises(UserError):
            self.subcontractor.action_open_validation_wizard()
