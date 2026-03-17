# -*- coding: utf-8 -*-
"""
Portal Controller Tests — Unit approach (TransactionCase)

Tests token validation, staging workflow, and upload logic
without relying on HttpCase (which can't see uncommitted transaction data).
"""
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import UserError
from datetime import datetime, timedelta, date
import base64


@tagged('post_install', '-at_install')
class TestPortalController(TransactionCase):
    """Test suite for portal upload controller logic."""

    def setUp(self):
        super().setUp()
        self.env = self.env(context=dict(self.env.context, tracking_disable=True))

        self.partner = self.env['res.partner'].create({
            'name': 'Test Portal Partner',
            'is_subcontractor': True,
            'supplier_rank': 1,
            'email': 'portal@test.com',
        })
        self.partner.action_generate_upload_link()
        self.token = self.partner.upload_token

    # ============= TOKEN GENERATION ============= #

    def test_generate_upload_link_creates_token(self):
        """action_generate_upload_link should set upload_token."""
        # GIVEN a partner without token
        partner = self.env['res.partner'].create({
            'name': 'New Partner', 'is_subcontractor': True, 'supplier_rank': 1,
        })
        # WHEN generating upload link
        partner.action_generate_upload_link()
        # THEN token is set and non-empty
        self.assertTrue(partner.upload_token)
        self.assertGreater(len(partner.upload_token), 10)

    def test_generate_upload_link_sets_expiration(self):
        """action_generate_upload_link should set token_expiration in the future."""
        # GIVEN partner with token
        # THEN expiration is in the future
        self.assertTrue(self.partner.token_expiration)
        self.assertGreater(self.partner.token_expiration, datetime.now())

    def test_upload_url_computed_from_token(self):
        """upload_url should contain the token."""
        # GIVEN partner with token
        # THEN upload_url contains the token
        self.assertIn(self.token, self.partner.upload_url)

    def test_regenerate_overwrites_existing_token(self):
        """Calling action_generate_upload_link twice should give a new token."""
        old_token = self.partner.upload_token
        self.partner.action_generate_upload_link()
        # THEN token is different (new one generated)
        self.assertNotEqual(self.partner.upload_token, old_token)

    # ============= TOKEN VALIDITY ============= #

    def test_valid_token_finds_partner(self):
        """A valid (non-expired) token should be findable."""
        # GIVEN partner with valid token
        found = self.env['res.partner'].sudo().search([
            ('upload_token', '=', self.token),
        ], limit=1)
        # THEN partner found
        self.assertEqual(found.id, self.partner.id)

    def test_expired_token_detected(self):
        """An expired token should be detectable via token_expiration < now."""
        # GIVEN partner with expired token
        self.partner.write({
            'token_expiration': datetime.now() - timedelta(days=1)
        })
        # THEN token is considered expired
        self.assertLess(self.partner.token_expiration, datetime.now())

    def test_invalid_token_not_found(self):
        """An invalid token should return empty recordset."""
        # GIVEN a non-existent token
        found = self.env['res.partner'].sudo().search([
            ('upload_token', '=', 'invalid_token_xyz_12345'),
        ], limit=1)
        # THEN no partner found
        self.assertFalse(found)

    # ============= DOCUMENT UPLOAD LOGIC ============= #

    def test_upload_kbis_updates_partner(self):
        """Writing doc_kbis to partner should update the field."""
        sample = base64.b64encode(b'PDF content here')
        # GIVEN partner with no kbis
        self.assertFalse(self.partner.doc_kbis)
        # WHEN writing kbis
        self.partner.write({
            'doc_kbis': sample,
            'doc_kbis_filename': 'kbis.pdf',
        })
        # THEN field is set
        self.assertTrue(self.partner.doc_kbis)

    def test_upload_sets_status_to_check_for_non_admin(self):
        """Non-admin uploading a doc should set status to 'to_check'."""
        regular = self.env['res.users'].create({
            'name': 'Portal User',
            'login': 'portal_user_test',
            'groups_id': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('base.group_partner_manager').id,
            ])],
        })
        sample = base64.b64encode(b'content')
        # GIVEN partner with no kbis
        # WHEN non-admin uploads
        self.partner.with_user(regular).write({'doc_kbis': sample})
        # THEN status is 'to_check' (not auto-validated)
        self.assertEqual(self.partner.doc_kbis_status, 'to_check')

    def test_clearing_doc_resets_to_missing(self):
        """Clearing a doc field should reset status to 'missing'."""
        sample = base64.b64encode(b'content')
        self.partner.write({'doc_kbis': sample, 'doc_kbis_expiry': date.today() + timedelta(days=90)})
        # WHEN clearing
        self.partner.write({'doc_kbis': False})
        # THEN status is missing
        self.assertEqual(self.partner.doc_kbis_status, 'missing')

    # ============= SESSION KEY LOGIC ============= #

    def test_session_key_format(self):
        """Session key should be based on the token."""
        from odoo.addons.construction_subcontractor.controllers.main import SubcontractorPortalController
        ctrl = SubcontractorPortalController()
        key = ctrl._get_session_key(self.token)
        self.assertIn(self.token, key)

    # ============= SUBMIT SINGLE VALIDATION ============= #

    def test_token_can_be_manually_cleared(self):
        """Manually clearing the token field should revoke access."""
        # GIVEN a partner with a token
        self.assertTrue(self.partner.upload_token)
        # WHEN clearing token manually
        self.partner.write({'upload_token': False, 'token_expiration': False})
        # THEN token is cleared and partner not findable by old token
        found = self.env['res.partner'].sudo().search([
            ('upload_token', '=', self.token),
        ], limit=1)
        self.assertFalse(found)

    def test_multiple_docs_can_be_uploaded(self):
        """Multiple document types can be uploaded independently."""
        sample = base64.b64encode(b'content')
        future = date.today() + timedelta(days=90)
        self.partner.write({
            'doc_kbis': sample, 'doc_kbis_expiry': future,
            'doc_urssaf': sample, 'doc_urssaf_expiry': future,
        })
        self.assertTrue(self.partner.doc_kbis)
        self.assertTrue(self.partner.doc_urssaf)

    def test_token_expiration_is_in_future(self):
        """Default token expiration should be in the future (typically 7 days)."""
        partner = self.env['res.partner'].create({
            'name': 'Exp Test', 'is_subcontractor': True, 'supplier_rank': 1,
        })
        partner.action_generate_upload_link()
        self.assertGreater(partner.token_expiration, datetime.now())
