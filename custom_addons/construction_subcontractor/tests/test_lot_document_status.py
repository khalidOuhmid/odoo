# -*- coding: utf-8 -*-
"""
Lot Document Status Tests

Tests for the document_status computed field on construction.lot.
Covers the three possible values (danger / warning / success) and their
consistency with the decoration-* attributes in lot_integration_views.xml.
"""
from datetime import date, timedelta

import base64

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestLotDocumentStatus(TransactionCase):
    """Tests for _compute_document_status on construction.lot."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.sample_doc = base64.b64encode(b'PDF content')
        cls.future_date = date.today() + timedelta(days=90)

        # Shared client partner
        cls.client = cls.env['res.partner'].create({
            'name': 'Client Test',
            'is_company': True,
        })

        # Subcontractor partner
        cls.subcontractor = cls.env['res.partner'].create({
            'name': 'ST Document Status',
            'is_subcontractor': True,
            'supplier_rank': 1,
        })

        # Chantier
        cls.chantier = cls.env['construction.chantier'].create({
            'name': 'Chantier Status Test',
            'client': cls.client.id,
            'address': '1 rue du Test',
            'company_id': cls.env.company.id,
        })

        # Lot category
        cls.category = cls.env['construction.lot.category'].create({
            'name': 'Test Category',
            'code': 'TST',
        })

        # Lot linked to subcontractor
        cls.lot = cls.env['construction.lot'].create({
            'name': 'Lot Status Test',
            'code': 'LOT-STS-01',
            'category_id': cls.category.id,
            'chantier_id': cls.chantier.id,
            'execution_type': 'external',
            'subcontractor_id': cls.subcontractor.id,
            'sequence': 10,
        })

    def _give_all_valid_docs(self):
        """Helper: give subcontractor all four required valid documents."""
        self.subcontractor.write({
            'doc_kbis': self.sample_doc,
            'doc_kbis_expiry': self.future_date,
            'doc_kbis_is_validated': True,
            'doc_urssaf': self.sample_doc,
            'doc_urssaf_expiry': self.future_date,
            'doc_urssaf_is_validated': True,
            'doc_insurance_dec': self.sample_doc,
            'doc_insurance_dec_expiry': self.future_date,
            'doc_insurance_dec_is_validated': True,
            'doc_cni': self.sample_doc,
            'doc_cni_expiry': self.future_date,
            'doc_cni_is_validated': True,
        })

    # ============= GUARD CASES ============= #

    def test_no_subcontractor_returns_false(self):
        """Arrange: lot without subcontractor. Expect: document_status is False."""
        # Arrange: create a dedicated chantier to avoid unique (category, chantier) constraint
        other_client = self.env['res.partner'].create({
            'name': 'Client No ST',
            'is_company': True,
        })
        other_chantier = self.env['construction.chantier'].create({
            'name': 'Chantier No ST',
            'client': other_client.id,
            'address': '2 rue du Sans-ST',
            'company_id': self.env.company.id,
        })
        lot = self.env['construction.lot'].create({
            'name': 'Lot Sans ST',
            'code': 'LOT-NOST-01',
            'category_id': self.category.id,
            'chantier_id': other_chantier.id,
            'execution_type': 'external',
            'sequence': 99,
        })
        # Act — field is computed
        # Assert
        self.assertFalse(
            lot.document_status,
            "document_status should be False when no subcontractor is set"
        )

    # ============= DANGER STATE ============= #

    def test_document_status_danger_when_all_docs_missing(self):
        """Arrange: subcontractor with no documents. Expect: document_status == 'danger'."""
        # Arrange
        self.subcontractor.write({
            'doc_kbis': False,
            'doc_urssaf': False,
            'doc_insurance_dec': False,
            'doc_cni': False,
        })
        # Act
        status = self.lot.document_status
        # Assert
        self.assertEqual(
            status, 'danger',
            "document_status should be 'danger' when required docs are missing"
        )

    def test_document_status_danger_when_one_doc_expired(self):
        """Arrange: all docs valid except KBIS which is expired. Expect: document_status == 'danger'."""
        # Arrange
        expired = date.today() - timedelta(days=1)
        self._give_all_valid_docs()
        self.subcontractor.write({
            'doc_kbis_expiry': expired,
        })
        # Act
        status = self.lot.document_status
        # Assert
        self.assertEqual(
            status, 'danger',
            "document_status should be 'danger' when any required doc is expired"
        )

    def test_document_status_danger_when_one_doc_rejected(self):
        """Arrange: subcontractor has KBIS rejected. Expect: document_status == 'danger'."""
        # Arrange
        self._give_all_valid_docs()
        # Simulate rejection by clearing the field (sets status to 'missing')
        self.subcontractor.write({'doc_kbis': False})
        # Assert document_status reflects the missing state as danger
        self.assertEqual(
            self.lot.document_status, 'danger',
            "document_status should be 'danger' when a required doc is missing/rejected"
        )

    # ============= WARNING STATE ============= #

    def test_document_status_warning_when_one_doc_expiring(self):
        """Arrange: all docs valid, one expires within 30 days. Expect: document_status == 'warning'."""
        # Arrange: give all valid docs first
        self._give_all_valid_docs()
        expiring_soon = date.today() + timedelta(days=15)
        self.subcontractor.write({
            'doc_kbis_expiry': expiring_soon,
        })
        # Act
        status = self.lot.document_status
        # Assert
        self.assertEqual(
            status, 'warning',
            "document_status should be 'warning' when any required doc is expiring within 30 days"
        )

    def test_document_status_warning_when_one_doc_to_check(self):
        """Arrange: one doc uploaded but not validated. Expect: document_status == 'warning'."""
        # Arrange: give all valid docs, then add an unvalidated one
        self._give_all_valid_docs()
        # Upload new URSSAF without validating — triggers reset of validation via write override
        regular_user = self.env['res.users'].create({
            'name': 'Regular User Status',
            'login': 'reg_user_status_test',
            'groups_id': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('base.group_partner_manager').id,
            ])],
        })
        new_doc = base64.b64encode(b'New URSSAF Content')
        self.subcontractor.with_user(regular_user).write({
            'doc_urssaf': new_doc,
            'doc_urssaf_expiry': self.future_date,
        })
        # Act
        status = self.lot.document_status
        # Assert
        self.assertEqual(
            status, 'warning',
            "document_status should be 'warning' when any required doc is 'to_check'"
        )

    # ============= SUCCESS STATE ============= #

    def test_document_status_success_when_all_docs_valid(self):
        """Arrange: all required docs present, validated, future expiry. Expect: document_status == 'success'."""
        # Arrange
        self._give_all_valid_docs()
        # Act
        status = self.lot.document_status
        # Assert
        self.assertEqual(
            status, 'success',
            "document_status should be 'success' when all required docs are valid"
        )

    # ============= VALUE CONSISTENCY WITH XML VIEWS ============= #

    def test_document_status_values_match_view_decorations(self):
        """document_status values must match the decoration-* attributes in lot_integration_views.xml."""
        # Arrange: collect the field's selection values
        field_def = self.env['construction.lot']._fields.get('document_status')
        self.assertIsNotNone(field_def, "document_status field must exist on construction.lot")
        selection_values = [v[0] for v in field_def.selection]
        # Assert: all three values expected by the XML view are present
        for expected in ('danger', 'warning', 'success'):
            self.assertIn(
                expected, selection_values,
                f"Selection value '{expected}' is required by lot_integration_views.xml "
                f"but is missing from document_status field definition"
            )
