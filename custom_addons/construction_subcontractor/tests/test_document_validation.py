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

        # Create a regular (non-admin) user for tests that require non-admin upload behavior
        # Needs group_partner_manager to write on res.partner (compliance doc fields)
        cls.regular_user = cls.env['res.users'].create({
            'name': 'Regular User Test',
            'login': 'regular_user_docval_test',
            'groups_id': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref('base.group_partner_manager').id,
            ])],
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
        """Validating a document should succeed and update status (non-admin upload)."""
        # Upload as non-admin so doc is NOT auto-validated
        self.subcontractor.with_user(self.regular_user).write({
            'doc_kbis': self.sample_doc,
            'doc_kbis_expiry': self.future_date,
        })

        wizard = self._create_wizard('kbis')

        # Should have document content
        self.assertTrue(wizard.doc_content, "Wizard should load document content")

        # Validate should succeed after preview
        wizard.action_preview()  # Must preview first
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
    
    # ============= NEW VALIDATION STATE MACHINE TESTS ============= #
    
    def test_upload_sets_status_to_check(self):
        """Non-admin upload should set status to 'to_check', NOT 'valid'."""
        self.subcontractor.with_user(self.regular_user).write({
            'doc_kbis': self.sample_doc,
            'doc_kbis_expiry': self.future_date,
        })

        # Status should be to_check because non-admin upload does not auto-validate
        self.assertEqual(
            self.subcontractor.doc_kbis_status,
            'to_check',
            "Non-admin upload should set status to 'to_check', not 'valid'"
        )
        self.assertFalse(
            self.subcontractor.doc_kbis_is_validated,
            "Non-admin upload should have is_validated=False"
        )
    
    def test_validation_requires_preview(self):
        """Validation should fail if PDF not previewed first (non-admin upload)."""
        # Use a fake PDF (must start with %PDF to trigger the preview requirement)
        fake_pdf = base64.b64encode(b'%PDF-1.4 fake PDF content for testing')
        # Use non-admin upload so doc is not auto-validated
        # Set filename with .pdf extension so wizard detects application/pdf mimetype
        self.subcontractor.with_user(self.regular_user).write({
            'doc_kbis': fake_pdf,
            'doc_kbis_filename': 'kbis_test.pdf',
            'doc_kbis_expiry': self.future_date,
        })

        wizard = self._create_wizard('kbis')

        # has_previewed should be False by default
        self.assertFalse(wizard.has_previewed)

        # Trying to validate without preview should raise error mentioning 'prévisualiser'
        with self.assertRaises(UserError) as context:
            wizard.action_validate()

        self.assertIn('prévisualiser', str(context.exception).lower())
    
    def test_validation_after_preview_succeeds(self):
        """Validation should succeed after preview and set correct fields (non-admin upload)."""
        # Use non-admin upload so doc is not auto-validated
        self.subcontractor.with_user(self.regular_user).write({
            'doc_kbis': self.sample_doc,
            'doc_kbis_expiry': self.future_date,
        })

        wizard = self._create_wizard('kbis')

        # Preview first
        wizard.action_preview()
        self.assertTrue(wizard.has_previewed, "action_preview should set has_previewed=True")

        # Now validate (as admin)
        wizard.action_validate()

        # Check validation fields are set
        self.assertTrue(self.subcontractor.doc_kbis_is_validated)
        self.assertEqual(self.subcontractor.doc_kbis_validated_by, self.env.user)
        self.assertIsNotNone(self.subcontractor.doc_kbis_validated_at)

        # Check status is now valid
        self.assertEqual(self.subcontractor.doc_kbis_status, 'valid')
    
    def test_new_upload_resets_validation(self):
        """Re-uploading a document as non-admin should reset validation state."""
        # First: admin validates a document
        self.subcontractor.write({
            'doc_kbis': self.sample_doc,
            'doc_kbis_expiry': self.future_date,
            'doc_kbis_is_validated': True,
        })

        # Verify initial state is valid
        self.assertEqual(self.subcontractor.doc_kbis_status, 'valid')

        # Now simulating a NEW upload by a non-admin user
        new_doc = base64.b64encode(b'New Document Content')
        self.subcontractor.with_user(self.regular_user).write({
            'doc_kbis': new_doc,
        })

        # Validation should be reset by non-admin upload
        self.assertFalse(
            self.subcontractor.doc_kbis_is_validated,
            "Non-admin new upload should reset is_validated to False"
        )
        self.assertEqual(
            self.subcontractor.doc_kbis_status,
            'to_check',
            "New upload should reset status to 'to_check'"
        )
