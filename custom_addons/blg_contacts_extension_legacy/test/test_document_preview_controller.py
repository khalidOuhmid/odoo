# -*- coding: utf-8 -*-
import base64
from datetime import timedelta

from odoo import fields
from odoo.tests import HttpCase, tagged

from ..models.document_config import DOCUMENT_TYPES


@tagged('post_install', '-at_install')
class TestDocumentPreviewController(HttpCase):
    """Integration tests for the document preview/download controller."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Preview User',
            'login': 'preview.user',
            'password': 'preview',
            'email': 'preview@test.com',
            'groups_id': [(6, 0, [cls.env.ref('base.group_user').id])],
        })
        cls.partner = cls.env['res.partner'].create({
            'name': 'Preview Partner',
            'email': 'preview.partner@test.com',
            'contact_type': 'sous_traitant',
        })
        config = DOCUMENT_TYPES['identity_card']
        values = {
            config['content_field']: base64.b64encode(b'%PDF-1.7\nPreview\n%%EOF'),
            config['filename_field']: 'preview.pdf',
            config['manual_status_field']: 'valid',
        }
        if config.get('expiry_field'):
            values[config['expiry_field']] = fields.Date.today() + timedelta(days=90)
        cls.partner.write(values)

    def test_authenticated_user_can_download_document(self):
        self.authenticate('preview.user', 'preview')
        response = self.url_open(
            f"/blg_contacts/document/preview/{self.partner.id}/identity_card?direct=1"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'%PDF', response.content)

    def test_authenticated_user_can_access_download_route(self):
        self.authenticate('preview.user', 'preview')
        response = self.url_open(f"/blg_contacts/document/download/{self.partner.id}/identity_card")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'%PDF', response.content)
