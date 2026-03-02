# -*- coding: utf-8 -*-
"""Integration tests for the Contract Deliverable model.

Covers CRUD, constraints, file size computation, and factory methods.
"""

from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError
from .common import ContractTestMixin
import base64


@tagged('post_install', '-at_install', 'construction_contract', 'deliverable')
class TestContractDeliverable(TransactionCase, ContractTestMixin):
    """Integration tests for construction.contract.deliverable in Odoo 18."""

    @classmethod
    def setUpClass(cls):
        """Initialize shared test data for deliverable tests."""
        super().setUpClass()
        cls.setUpContractData()

    # ------------------------------------------------------------------
    # Creation & File Size Computation
    # ------------------------------------------------------------------

    def test_create_deliverable_with_document_computes_file_size(self):
        """Verify that creating a deliverable with a binary document computes file_size.

        Raises:
            AssertionError: If file_size is zero for a non-empty document.
        """
        # Arrange
        content = b'%PDF-1.4 mock small file content for test'
        b64_content = base64.b64encode(content)

        # Act
        deliverable = self.env['construction.contract.deliverable'].create({
            'name': 'Planning Général Test',
            'contract_id': self.contract.id,
            'deliverable_type': 'planning_general',
            'document': b64_content,
            'document_name': 'planning.pdf',
        })

        # Assert
        self.assertGreater(deliverable.file_size, 0,
                           'File size must be > 0 for a non-empty document')
        self.assertTrue(deliverable.file_size_readable,
                        'file_size_readable must be a non-empty string')

    def test_create_deliverable_with_url_no_document(self):
        """Verify that a deliverable can be created with URL instead of file.

        Raises:
            AssertionError: If deliverable creation fails with URL-only.
        """
        # Arrange & Act
        deliverable = self.env['construction.contract.deliverable'].create({
            'name': 'Lien Externe',
            'contract_id': self.contract.id,
            'deliverable_type': 'other',
            'document_url': 'https://example.com/cctp.pdf',
        })

        # Assert
        self.assertTrue(deliverable.id, 'Deliverable with URL must be created')
        self.assertEqual(deliverable.file_size, 0,
                         'File size must be 0 for URL-only deliverable')

    # ------------------------------------------------------------------
    # Constraint: file size limit (20 MB)
    # ------------------------------------------------------------------

    def test_file_size_limit_raises_on_oversized_document(self):
        """Verify that uploading a >20 MB document raises ValidationError.

        Raises:
            AssertionError: If no ValidationError is raised for oversized files.
        """
        # Arrange — create 21 MB of data
        oversized = base64.b64encode(b'X' * (21 * 1024 * 1024))

        # Act & Assert
        with self.assertRaises(ValidationError):
            self.env['construction.contract.deliverable'].create({
                'name': 'Fichier Trop Gros',
                'contract_id': self.contract.id,
                'deliverable_type': 'other',
                'document': oversized,
                'document_name': 'huge.pdf',
            })

    # ------------------------------------------------------------------
    # Constraint: must have document OR URL
    # ------------------------------------------------------------------

    def test_no_document_no_url_raises_validation_error(self):
        """Verify that deliverable without document or URL raises ValidationError.

        Raises:
            AssertionError: If no ValidationError is raised for empty deliverable.
        """
        # Arrange — create with a doc first, then clear it
        deliverable = self.env['construction.contract.deliverable'].create({
            'name': 'Initially With Doc',
            'contract_id': self.contract.id,
            'deliverable_type': 'other',
            'document': base64.b64encode(b'%PDF mock'),
            'document_name': 'temp.pdf',
        })

        # Act & Assert — clearing both should trigger constraint
        with self.assertRaises(ValidationError):
            deliverable.write({'document': False, 'document_url': False})

    # ------------------------------------------------------------------
    # Action: Download
    # ------------------------------------------------------------------

    def test_action_download_returns_url_action(self):
        """Verify that action_download returns an ir.actions.act_url dict.

        Raises:
            AssertionError: If the returned action is not a URL action.
        """
        # Arrange
        deliverable = self.env['construction.contract.deliverable'].create({
            'name': 'Téléchargeable',
            'contract_id': self.contract.id,
            'deliverable_type': 'purchase_order',
            'document': base64.b64encode(b'%PDF mock'),
            'document_name': 'bc.pdf',
        })

        # Act
        action = deliverable.action_download()

        # Assert
        self.assertEqual(action['type'], 'ir.actions.act_url',
                         'action_download must return a URL action')


@tagged('post_install', '-at_install', 'construction_contract', 'deliverable')
class TestContractDeliverableFactory(TransactionCase, ContractTestMixin):
    """Integration tests for deliverable factory methods."""

    @classmethod
    def setUpClass(cls):
        """Initialize test data for factory method tests."""
        super().setUpClass()
        cls.setUpContractData()

    def test_create_from_partner_document_urssaf(self):
        """Verify that create_from_partner_document creates a deliverable from URSSAF doc.

        Raises:
            AssertionError: If deliverable is not created or has wrong type.
        """
        # Arrange — ensure subcontractor has document_URSSAF set
        # (set in common.py with legacy field names)
        service = self.env['construction.contract.deliverable']

        # Act
        try:
            deliverable = service.create_from_partner_document(
                self.contract, 'urssaf'
            )
        except ValidationError as e:
            if 'does not have' in str(e):
                self.skipTest('document_URSSAF field not available in this env')
            raise

        # Assert
        self.assertTrue(deliverable, 'Deliverable must be created')
        self.assertEqual(deliverable.contract_id, self.contract)
        self.assertEqual(deliverable.partner_document_type, 'urssaf')
