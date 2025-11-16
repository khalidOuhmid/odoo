# -*- coding: utf-8 -*-
from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import PartnerDocumentCase


@tagged('post_install', '-at_install')
class TestPartnerDocuments(PartnerDocumentCase):
    """Unit tests focused on res.partner document workflows."""

    def test_status_computation_pipeline(self):
        partner = self._create_subcontractor()
        self.assertEqual(partner.document_identity_card_status, 'missing')

        self._set_document(partner, 'identity_card', manual_status='valid', expiry=self.valid_expiry)
        self._invalidate(partner, [
            'document_identity_card_status', 'has_expiring_documents', 'has_expired_documents'
        ])
        self.assertEqual(partner.document_identity_card_status, 'valid')

        self._set_document(partner, 'identity_card', manual_status='valid', expiry=self.expiring_expiry)
        self._invalidate(partner, ['document_identity_card_status', 'has_expiring_documents'])
        self.assertEqual(partner.document_identity_card_status, 'expiring')
        self.assertTrue(partner.has_expiring_documents)

        self._set_document(partner, 'identity_card', manual_status='valid', expiry=self.expired_expiry)
        self._invalidate(partner, ['document_identity_card_status', 'has_expired_documents'])
        self.assertEqual(partner.document_identity_card_status, 'expired')
        self.assertTrue(partner.has_expired_documents)

    def test_validate_document_access_rights(self):
        partner = self._create_subcontractor()
        user = self._create_user('no_doc_access')
        with self.assertRaises(AccessError):
            partner.with_user(user)._validate_document_access_rights()

    def test_generate_upload_token_details_contains_context_params(self):
        partner = self._create_subcontractor()
        url = partner.with_context(reminder=True)._generate_upload_token_details()
        self.assertIn('/documents/upload/', url)
        self.assertIn('reminder=1', url)
        self.assertTrue(partner.upload_token)

    def test_send_missing_documents_request(self):
        partner = self._create_subcontractor()
        self._set_document(partner, 'identity_card', manual_status='rejected', expiry=self.valid_expiry)
        with self.mock_notification_sender() as mocked:
            result = partner.send_missing_documents_request(['Carte d\'identité'])
            self.assertTrue(result)
            mocked.assert_called_once()

    def test_check_document_expiry_triggers_notification(self):
        partner = self._create_subcontractor()
        self._set_document(partner, 'identity_card', manual_status='valid', expiry=self.expired_expiry)
        with self.mock_notification_sender() as mocked:
            self.partner_model.check_document_expiry()
            self.assertGreaterEqual(mocked.call_count, 1)

    def test_filter_helpers(self):
        compliant = self._create_subcontractor(name='Compliant', email='compliant@test.com')
        other = self._create_subcontractor(name='Missing', email='missing@test.com')
        self._set_document(compliant, 'kbis', manual_status='valid', expiry=self.valid_expiry)

        valid_partners = self.partner_model.get_subcontractors_by_document_status('valid')
        self.assertIn(compliant, valid_partners)
        self.assertNotIn(other, valid_partners)

        by_lot = self.partner_model.get_subcontractors_by_lot(None)
        self.assertIn(compliant, by_lot)

        filtered = self.partner_model.filter_subcontractors(status='valid', document_type='kbis')
        self.assertEqual(filtered, compliant)


