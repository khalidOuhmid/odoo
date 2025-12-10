# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.tests import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestPortalDocumentUpload(HttpCase):
    """HTTP-level smoke tests for the public portal upload controller."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({
            'name': 'Portal Partner',
            'email': 'portal@test.com',
            'contact_type': 'sous_traitant',
            'upload_token': 'portal-token',
            'token_expiration': fields.Datetime.now() + timedelta(days=1),
        })

    def test_portal_page_renders_with_valid_token(self):
        response = self.url_open(f"/documents/upload/{self.partner.upload_token}")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Documents administratifs', response.content)

    def test_portal_page_shows_error_for_expired_token(self):
        self.partner.write({'token_expiration': fields.Datetime.now() - timedelta(days=1)})
        response = self.url_open(f"/documents/upload/{self.partner.upload_token}")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Lien expir', response.content)


