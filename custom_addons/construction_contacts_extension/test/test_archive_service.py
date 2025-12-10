# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from .common import PartnerDocumentCase
from ..models.document_config import DOCUMENT_TYPES


@tagged('post_install', '-at_install')
class TestArchiveService(PartnerDocumentCase):
    """Tests for the archive.service helpers."""

    def test_archive_document_version(self):
        partner = self._create_subcontractor()
        config = DOCUMENT_TYPES['identity_card']
        self._set_document(partner, 'identity_card', manual_status='valid', expiry=self.valid_expiry)

        archive = self.archive_service.archive_document_version(
            partner.id,
            'identity_card',
            getattr(partner, config['content_field']),
            getattr(partner, config['filename_field']),
            'validation',
        )
        self.assertTrue(archive)
        self.assertEqual(archive.partner_id, partner)
        self.assertEqual(archive.document_type, 'identity_card')

    def test_cleanup_old_archives(self):
        partner = self._create_subcontractor()
        archive = self.env['document.archive'].create({
            'name': 'Old.pdf',
            'document': self.sample_pdf,
            'document_type': 'identity_card',
            'partner_id': partner.id,
            'archive_date': fields.Datetime.now() - timedelta(days=400),
        })
        stats = self.archive_service.cleanup_old_archives(retention_days=30, batch_size=10)
        self.assertEqual(stats['total_deleted'], 1)
        self.assertFalse(archive.exists())

