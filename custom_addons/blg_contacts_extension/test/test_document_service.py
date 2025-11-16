# -*- coding: utf-8 -*-
from odoo.tests import tagged

from .common import PartnerDocumentCase


@tagged('post_install', '-at_install')
class TestDocumentService(PartnerDocumentCase):
    """Unit tests covering the document.service model API."""

    def test_validate_document(self):
        partner = self._create_subcontractor()
        self._set_document(partner, 'identity_card', manual_status='to_check', expiry=self.valid_expiry)

        result = self.document_service.validate_document(partner.id, 'identity_card')
        partner.invalidate_recordset(['document_identity_card_manual_status'])

        self.assertTrue(result['success'])
        self.assertEqual(partner.document_identity_card_manual_status, 'valid')

    def test_reject_document_creates_archive_and_notifies(self):
        partner = self._create_subcontractor()
        self._set_document(partner, 'identity_card', manual_status='valid', expiry=self.valid_expiry)
        with self.mock_notification_sender() as mocked:
            result = self.document_service.reject_document(
                partner.id, 'identity_card', rejection_reason='Blurry scan'
            )
            self.assertTrue(result['success'])
            mocked.assert_called_once()

        partner.invalidate_recordset(['document_identity_card_manual_status'])
        self.assertEqual(partner.document_identity_card_manual_status, 'rejected')
        archives = self.env['document.archive'].search([('partner_id', '=', partner.id)])
        self.assertTrue(archives)

    def test_send_missing_documents_request(self):
        partner = self._create_subcontractor()
        self.assertFalse(
            self.document_service.send_missing_documents_request(partner.id)['success']
        )
        self._set_document(partner, 'identity_card', manual_status='rejected', expiry=self.valid_expiry)
        with self.mock_notification_sender() as mocked:
            result = self.document_service.send_missing_documents_request(partner.id)
            self.assertTrue(result['success'])
            mocked.assert_called_once()

    def test_get_document_status_summary(self):
        partner = self._create_subcontractor()
        self._set_document(partner, 'kbis', manual_status='valid', expiry=self.valid_expiry)
        summary = self.document_service.get_document_status_summary(partner.id)
        self.assertEqual(summary['total_documents'], len(summary['documents']))
        self.assertGreaterEqual(summary['valid_documents'], 1)

    def test_preview_document_returns_url(self):
        partner = self._create_subcontractor()
        self._set_document(partner, 'identity_card', manual_status='valid', expiry=self.valid_expiry)
        action = self.document_service.preview_document(partner.id, 'identity_card')
        self.assertEqual(action['type'], 'ir.actions.act_url')
        self.assertIn('/web/content', action['url'])


