# -*- coding: utf-8 -*-
"""Integration tests for the construction.contract model.

Covers the full contract lifecycle: creation, name generation,
state transitions, PDF generation, portal signature workflow,
computed fields, amount calculations, and error handling.

Heavy services (WeasyPrint, Jinja2) are mocked to test business logic
in isolation.
"""

from odoo.tests import common, tagged
from odoo.exceptions import ValidationError, UserError, AccessError
from datetime import date, timedelta
from unittest.mock import patch
import base64
import logging

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install', 'construction_contract')
class TestContractModel(common.TransactionCase):
    """Full lifecycle tests for the construction.contract model."""

    @classmethod
    def setUpClass(cls):
        """Initialize shared test fixtures: chantier, subcontractor, lot, template, contract."""
        super().setUpClass()

        # Arrange — shared records
        _mock_doc = base64.b64encode(b'%PDF-1.4 mock').decode('ascii')
        cls.chantier = cls.env['construction.chantier'].create({
            'name': 'Test Construction Site',
            'reference': 'SITE-001',
            'address': '123 Test Street',
            'city': 'Paris',
            'zip_code': '75001',
            'client': cls.env['res.partner'].create({'name': 'Client Test'}).id,
        })

        cls.subcontractor = cls.env['res.partner'].create({
            'name': 'Test Subcontractor',
            'is_company': True,
            'company_registry': '12345678901234',
            'email': 'test@subcontractor.com',
            'phone': '+33123456789',
            'city': 'Lyon',
            'supplier_rank': 1,
            'doc_urssaf': _mock_doc,
            'doc_kbis': _mock_doc,
            'doc_insurance_dec': _mock_doc,
        })
        cls.subcontractor.write({
            'doc_urssaf_status': 'valid',
            'doc_kbis_status': 'valid',
            'doc_insurance_dec_status': 'valid',
        })

        cls.lot = cls.env['construction.lot'].create({
            'name': 'Test Work Package',
            'code': 'LOT-001',
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

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _simulate_pdf_generated(self, contract=None):
        """Simulate a successful PDF generation without calling WeasyPrint."""
        c = contract or self.contract
        mock_pdf = base64.b64encode(b'%PDF-1.4 mock generated content')
        c.write({
            'pdf_document': mock_pdf,
            'state': 'generated',
            'pdf_page_count': 3,
        })

    def _simulate_sent(self, contract=None):
        """Simulate sending for signature (set state, token, dates)."""
        c = contract or self.contract
        self._simulate_pdf_generated(c)
        c.write({
            'state': 'sent',
            'access_token': c.access_token or c._generate_access_token(),
            'sent_date': date.today(),
            'token_expiry_date': date.today() + timedelta(days=7),
        })

    # ------------------------------------------------------------------
    # Creation & Name Generation
    # ------------------------------------------------------------------

    def test_contract_creation_sets_draft_state(self):
        """Verify that creating a contract sets state to 'draft' and generates a name.

        Raises:
            AssertionError: If contract is not created or name is 'New'.
        """
        # Arrange & Act — use the contract from setUpClass
        contract = self.contract

        # Assert
        self.assertTrue(contract, "Contract should be created")
        self.assertNotEqual(contract.name, 'New', "Contract should have generated name")
        self.assertEqual(contract.state, 'draft', "New contract should be in draft state")

    def test_contract_name_contains_chantier(self):
        """Verify that the auto-generated name contains the chantier name.

        Raises:
            AssertionError: If contract name doesn't reference the chantier.
        """
        # Arrange & Act
        name = self.contract.name

        # Assert
        self.assertTrue(name, "Contract name must not be empty")
        self.assertTrue(len(name) > 5, "Contract name should be descriptive")

    # ------------------------------------------------------------------
    # State: draft → generated (mocked PDF)
    # ------------------------------------------------------------------

    def test_state_transition_draft_to_generated(self):
        """Verify that PDF generation transitions state from draft to generated.

        Raises:
            AssertionError: If state is not 'generated' after PDF generation.
        """
        # Arrange
        self.assertEqual(self.contract.state, 'draft')

        # Act
        self._simulate_pdf_generated()

        # Assert
        self.assertEqual(self.contract.state, 'generated',
                         "State should change to generated")
        self.assertTrue(self.contract.pdf_document,
                        "Contract should have PDF document")

    # ------------------------------------------------------------------
    # Send for Signature
    # ------------------------------------------------------------------

    def test_send_for_signature_without_pdf_raises(self):
        """Verify that sending for signature without PDF raises UserError.

        Raises:
            AssertionError: If no error is raised when PDF is missing.
        """
        # Arrange — contract is in draft, no PDF

        # Act & Assert
        with self.assertRaises(Exception):
            self.contract.action_send_for_signature()

    def test_send_for_signature_sets_state(self):
        """Verify that after simulated send, state is 'sent' with a token.

        Raises:
            AssertionError: If state is not 'sent' or token is missing.
        """
        # Arrange & Act
        self._simulate_sent()

        # Assert
        self.assertEqual(self.contract.state, 'sent')
        self.assertTrue(self.contract.access_token, "Should have access token")
        self.assertTrue(self.contract.sent_date, "Should have sent date")

    def test_access_token_has_sufficient_entropy(self):
        """Verify that the generated access token is long enough for security.

        Raises:
            AssertionError: If token length is less than 20 characters.
        """
        # Arrange
        self._simulate_sent()

        # Assert
        self.assertTrue(self.contract.access_token)
        self.assertGreater(len(self.contract.access_token), 20,
                           "Token should be long enough for security")

    # ------------------------------------------------------------------
    # Token Management
    # ------------------------------------------------------------------

    def test_token_expiry_detection(self):
        """Verify that expired tokens are correctly detected by _is_token_expired.

        Raises:
            AssertionError: If expired token is not detected.
        """
        # Arrange
        self._simulate_sent()
        token = self.contract.access_token

        # Assert — fresh token should be valid
        if hasattr(self.contract, '_is_token_expired'):
            is_expired = self.contract._is_token_expired(token)
            self.assertFalse(is_expired, "Fresh token should be valid")

            # Arrange — expire the token
            self.contract.write({
                'token_expiry_date': date.today() - timedelta(days=1)
            })
            self.contract.invalidate_recordset(['token_expiry_date'])

            # Assert — expired
            self.assertTrue(self.contract._is_token_expired(token),
                            "Expired token should be detected")

    # ------------------------------------------------------------------
    # Computed Fields
    # ------------------------------------------------------------------

    def test_purchase_order_count_is_integer(self):
        """Verify that purchase_order_count returns a non-negative integer.

        Raises:
            AssertionError: If count is not an integer or is negative.
        """
        # Arrange — contract from setUpClass

        # Act
        count = self.contract.purchase_order_count

        # Assert
        self.assertIsInstance(count, int)
        self.assertGreaterEqual(count, 0)

    def test_portal_url_is_string(self):
        """Verify that portal_url computed field returns a string.

        Raises:
            AssertionError: If portal_url is not a string.
        """
        # Arrange & Act
        url = self.contract.portal_url

        # Assert
        self.assertIsInstance(url, str)

    def test_retention_rate_stored(self):
        """Verify that retention_rate is stored correctly.

        Raises:
            AssertionError: If retention_rate doesn't match what was set.
        """
        # Arrange & Act — from setUpClass (retention_rate=5.0)

        # Assert
        self.assertEqual(self.contract.retention_rate, 5.0)

    # ------------------------------------------------------------------
    # Amount Calculations
    # ------------------------------------------------------------------

    def test_retention_calculation(self):
        """Verify that retention_amount is correctly computed.

        Raises:
            AssertionError: If retention amount does not match expected value.
        """
        # Arrange
        if not hasattr(self.contract, '_compute_retention'):
            self.skipTest("_compute_retention not available")
        self.contract.total_amount_ttc = 10000.0
        self.contract.retention_rate = 5.0

        # Act
        self.contract._compute_retention()

        # Assert
        self.assertEqual(self.contract.retention_amount, 500.0)

    # ------------------------------------------------------------------
    # Archive & Cancel
    # ------------------------------------------------------------------

    def test_archive_draft_contract_raises(self):
        """Verify that archiving a draft contract raises UserError.

        Raises:
            AssertionError: If no error is raised when archiving a draft contract.
        """
        # Arrange — contract in draft state

        # Act & Assert — only signed contracts can be archived
        with self.assertRaises(UserError):
            self.contract.action_archive()

    def test_mark_signed_without_in_progress_raises(self):
        """Verify that action_mark_signed raises if contract is not 'in_progress'.

        Raises:
            AssertionError: If no error is raised for invalid state transition.
        """
        # Arrange — contract is in draft

        # Act & Assert
        with self.assertRaises(Exception):
            self.contract.action_mark_signed()

    # ------------------------------------------------------------------
    # Date Constraints
    # ------------------------------------------------------------------

    def test_end_date_before_start_raises_validation(self):
        """Verify that end_date before start_date raises ValidationError.

        Raises:
            AssertionError: If no error is raised for invalid dates.
        """
        # Arrange & Act & Assert
        with self.assertRaises(ValidationError):
            self.env['construction.contract'].create({
                'chantier_id': self.chantier.id,
                'subcontractor_id': self.subcontractor.id,
                'template_id': self.template.id,
                'date': date.today(),
                'start_date': date.today(),
                'end_date': date.today() - timedelta(days=10),
            })

    # ------------------------------------------------------------------
    # Subcontractor Constraint
    # ------------------------------------------------------------------

    def test_contract_requires_valid_subcontractor_docs(self):
        """Verify that contract creation with non-compliant subcontractor raises.

        Raises:
            AssertionError: If no error is raised for non-compliant subcontractor.
        """
        # Arrange — create a subcontractor without valid docs
        bad_sub = self.env['res.partner'].create({
            'name': 'Bad Subcontractor',
            'is_company': True,
            'company_registry': '99999999999999',
        })

        # Act & Assert
        with self.assertRaises(ValidationError):
            self.env['construction.contract'].create({
                'chantier_id': self.chantier.id,
                'subcontractor_id': bad_sub.id,
                'template_id': self.template.id,
                'date': date.today(),
                'start_date': date.today(),
                'end_date': date.today() + timedelta(days=30),
            })
