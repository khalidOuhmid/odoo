# -*- coding: utf-8 -*-
"""Integration tests for the Contract Signature model.

Covers signature creation, size validation, device type computation,
invalidation workflow, and certificate detail extraction.
"""

from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError
from .common import ContractTestMixin
import base64


@tagged('post_install', '-at_install', 'construction_contract', 'signature')
class TestContractSignature(TransactionCase, ContractTestMixin):
    """Integration tests for construction.contract.signature in Odoo 18."""

    @classmethod
    def setUpClass(cls):
        """Initialize shared test data for signature tests."""
        super().setUpClass()
        cls.setUpContractData()
        # Minimal valid PNG (1x1 pixel)
        cls.mock_sig = base64.b64encode(
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
            b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx'
            b'\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
        )

    def _create_sig(self, **overrides):
        """Helper to create a signature with valid defaults."""
        vals = {
            'contract_id': self.contract.id,
            'signer_name': 'Jean Dupont',
            'signer_email': 'jean@example.com',
            'signature_data': self.mock_sig,
            'ip_address': '192.168.1.100',
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'authentication_method': 'email',
        }
        vals.update(overrides)
        return self.env['construction.contract.signature'].create(vals)

    # ------------------------------------------------------------------
    # Creation
    # ------------------------------------------------------------------

    def test_create_signature_stores_data(self):
        """Verify that creating a signature record stores all required fields.

        Raises:
            AssertionError: If any required field is empty after creation.
        """
        # Arrange & Act
        sig = self._create_sig()

        # Assert
        self.assertTrue(sig.id, 'Signature record must be created')
        self.assertEqual(sig.signer_name, 'Jean Dupont')
        self.assertEqual(sig.contract_id, self.contract)
        self.assertTrue(sig.signature_data, 'Signature data must be stored')

    # ------------------------------------------------------------------
    # Device type computation
    # ------------------------------------------------------------------

    def test_device_type_desktop_from_user_agent(self):
        """Verify device_type is 'desktop' for a Windows user agent.

        Raises:
            AssertionError: If device_type is not 'desktop'.
        """
        # Arrange & Act
        sig = self._create_sig(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )

        # Assert
        self.assertEqual(sig.device_type, 'desktop',
                         'Windows user agent must be detected as desktop')

    def test_device_type_mobile_from_user_agent(self):
        """Verify device_type is 'mobile' for an iPhone user agent.

        Raises:
            AssertionError: If device_type is not 'mobile'.
        """
        # Arrange & Act
        sig = self._create_sig(
            user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)'
        )

        # Assert
        self.assertIn(sig.device_type, ('mobile', 'tablet'),
                      'iPhone user agent must be detected as mobile or tablet')

    # ------------------------------------------------------------------
    # Size constraint (MAX_SIGNATURE_SIZE_MB = 5)
    # ------------------------------------------------------------------

    def test_oversized_signature_warns_but_creates(self):
        """Verify that a signature exceeding 5 MB logs a warning but still creates.

        Raises:
            AssertionError: If record is not created for oversized signature.
        """
        # Arrange — create a 6 MB base64 string
        oversized_sig = base64.b64encode(b'X' * (6 * 1024 * 1024))

        # Act — model logs warning but doesn't block creation
        sig = self._create_sig(signature_data=oversized_sig)

        # Assert
        self.assertTrue(sig.id, 'Signature should still be created despite oversize warning')

    # ------------------------------------------------------------------
    # Invalidation
    # ------------------------------------------------------------------

    def test_action_invalidate_returns_wizard_action(self):
        """Verify that action_invalidate opens the invalidation wizard.

        Raises:
            AssertionError: If the returned action is not a wizard form.
        """
        # Arrange
        sig = self._create_sig()

        # Act — action_invalidate opens a wizard, requires admin
        result = sig.sudo().action_invalidate()

        # Assert
        self.assertEqual(result['type'], 'ir.actions.act_window',
                         'action_invalidate must return a window action')
        self.assertEqual(result['res_model'], 'signature.invalidation.wizard')
        self.assertEqual(result['target'], 'new')

    # ------------------------------------------------------------------
    # Certificate details
    # ------------------------------------------------------------------

    def test_get_signature_details_for_certificate(self):
        """Verify _get_signature_details_for_certificate returns expected nested dict.

        Raises:
            AssertionError: If returned dict is missing expected keys.
        """
        # Arrange
        sig = self._create_sig()

        # Act
        details = sig._get_signature_details_for_certificate()

        # Assert
        self.assertIsInstance(details, dict, 'Must return a dict')
        self.assertIn('signer', details)
        self.assertIn('technical', details)
        self.assertEqual(details['signer']['name'], 'Jean Dupont')
        self.assertEqual(details['technical']['ip'], '192.168.1.100')

    # ------------------------------------------------------------------
    # Filename computation
    # ------------------------------------------------------------------

    def test_signature_filename_computed(self):
        """Verify that signature_filename is auto-computed.

        Raises:
            AssertionError: If signature_filename is empty.
        """
        # Arrange & Act
        sig = self._create_sig()

        # Assert
        self.assertTrue(sig.signature_filename,
                        'signature_filename must be computed and non-empty')
