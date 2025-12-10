# -*- coding: utf-8 -*-
import base64
from datetime import date, timedelta
from contextlib import contextmanager
from unittest.mock import patch

from odoo import fields
from odoo.tests.common import TransactionCase

from ..models.document_config import DOCUMENT_TYPES


class PartnerDocumentCase(TransactionCase):
    """Base helpers shared across document-related test suites."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env['res.partner']
        cls.document_service = cls.env['document.service']
        cls.archive_service = cls.env['archive.service']
        cls.sample_pdf = base64.b64encode(b'%PDF-1.7\nBLG Test\n%%EOF')
        cls.today = date.today()
        cls.valid_expiry = cls.today + timedelta(days=60)
        cls.expiring_expiry = cls.today + timedelta(days=10)
        cls.expired_expiry = cls.today - timedelta(days=1)
        cls.env['ir.config_parameter'].sudo().set_param('web.base.url', 'http://test.example.com')

    def _create_subcontractor(self, **overrides):
        """Create a partner configured as subcontractor with sane defaults."""
        values = {
            'name': overrides.get('name', 'Test Subcontractor'),
            'email': overrides.get('email', 'subcontractor@test.example.com'),
            'contact_type': 'sous_traitant',
        }
        values.update(overrides)
        return self.partner_model.create(values)

    def _create_user(self, login, groups=None):
        """Utility to build a user for access-rights scenarios."""
        groups = groups or [self.env.ref('base.group_user').id]
        return self.env['res.users'].with_context(no_reset_password=True).create({
            'name': login,
            'login': login,
            'password': 'test',
            'email': f'{login}@example.com',
            'groups_id': [(6, 0, groups)],
        })

    def _set_document(self, partner, doc_key, manual_status='to_check', expiry=None):
        """Attach a PDF document to the partner for the given doc config key."""
        config = DOCUMENT_TYPES[doc_key]
        vals = {
            config['content_field']: self.sample_pdf,
            config['filename_field']: f"{config['filename_prefix']} - {partner.name}.pdf",
            config['manual_status_field']: manual_status,
        }
        if config.get('has_expiry'):
            vals[config['expiry_field']] = expiry or self.valid_expiry
        partner.write(vals)
        return partner

    @contextmanager
    def mock_mail_template(self, return_value=True):
        """Patch mail.template send_mail to avoid sending real emails."""
        with patch(
            'odoo.addons.mail.models.mail_template.MailTemplate.send_mail',
            return_value=return_value,
        ) as mocked:
            yield mocked

    @contextmanager
    def mock_notification_sender(self, return_value=True):
        """Patch the generic document email utility."""
        with patch(
            'odoo.addons.blg_contacts_extension.models.res_partner.document_email_utils.send_document_notification',
            return_value=return_value,
        ) as mocked:
            yield mocked

    def _invalidate(self, partner, fields_list=None):
        """Force recompute of transient fields on the given partner."""
        partner.flush()
        if fields_list:
            partner.invalidate_recordset(fields_list)
        else:
            partner.invalidate_recordset()
        return partner

