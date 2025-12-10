# -*- coding: utf-8 -*-
import base64
from datetime import date, timedelta

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestContractValidationService(TransactionCase):
    """Tests for construction.contract.validation.service helper."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env['res.partner']
        cls.validation_service = cls.env['construction.contract.validation.service']
        cls.sample_pdf = base64.b64encode(b'%PDF-1.7\nBLG Test\n%%EOF')
        cls.expiring_expiry = date.today() + timedelta(days=10)
        cls.valid_expiry = date.today() + timedelta(days=90)

    def _create_subcontractor(self, has_siret=True, expiry=None):
        partner = self.partner_model.create({
            'name': 'Test Subcontractor',
            'email': 'sub@test.example.com',
            'contact_type': 'sous_traitant',
            'company_registry': '12345678900011' if has_siret else False,
        })
        expiry_date = expiry or self.valid_expiry
        document_fields = (
            ('document_URSSAF', 'document_URSSAF_filename', 'document_URSSAF_manual_status', 'document_URSSAF_expiry'),
            ('document_KBIS', 'document_KBIS_filename', 'document_KBIS_manual_status', 'document_KBIS_expiry'),
            ('document_insurance', 'document_insurance_filename', 'document_insurance_manual_status', 'document_insurance_expiry'),
        )
        for content_field, filename_field, manual_field, expiry_field in document_fields:
            partner.write({
                content_field: self.sample_pdf,
                filename_field: 'test.pdf',
                manual_field: 'valid',
                expiry_field: expiry_date,
            })
        partner.invalidate_recordset([
            'document_URSSAF_status',
            'document_KBIS_status',
            'document_insurance_status',
        ])
        return partner

    def test_expiring_documents_are_accepted(self):
        partner = self._create_subcontractor(expiry=self.expiring_expiry)
        # Sanity check: statuses should be marked as expiring
        self.assertEqual(partner.document_URSSAF_status, 'expiring')

        result = self.validation_service.validate_subcontractor_eligibility(partner)
        self.assertTrue(result['eligible'])
        self.assertFalse(result['warnings'])

    def test_missing_siret_is_reported(self):
        partner = self._create_subcontractor(has_siret=False)
        result = self.validation_service.validate_subcontractor_eligibility(partner)
        self.assertFalse(result['eligible'])
        self.assertTrue(any('SIRET' in warning for warning in result['warnings']))

