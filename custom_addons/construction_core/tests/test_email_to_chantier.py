# -*- coding: utf-8 -*-
"""
Integration tests for automatic Chantier creation via email alias.

Tests the full pipeline:
  inbound raw email → message_process → message_new → construction.chantier

The alias `appel-doffre@blggroupe.com` must be configured in mail_config.xml.
"""
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from odoo.tests import tagged

from .common import ConstructionCoreTestBase


def _build_raw_email(subject, from_addr, to_addr, body_text):
    """Helper to construct a minimal RFC-2822 raw email as bytes."""
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = from_addr
    msg['To'] = to_addr
    msg['Message-ID'] = f'<test-{subject[:10].replace(" ", "")}@test.local>'
    msg.attach(MIMEText(body_text, 'plain', 'utf-8'))
    return msg.as_bytes()


@tagged('post_install', '-at_install')
class TestEmailToChantierViaMessageProcess(ConstructionCoreTestBase):
    """
    Full end-to-end tests using message_process.

    These verify that an email routed to construction.chantier (via alias or
    direct model call) creates a proper chantier record at the REC stage.
    """

    def _process(self, subject, from_addr='client@example.fr', to_addr='appel-doffre@blggroupe.com', body=''):
        raw = _build_raw_email(subject, from_addr, to_addr, body)
        self.env['mail.thread'].message_process('construction.chantier', raw)

    # ------------------------------------------------------------------
    # TC-ET-01: chantier created with correct name
    # ------------------------------------------------------------------
    def test_chantier_created_with_email_subject_as_name(self):
        subject = 'Projet rénovation Lyon 69001'
        count_before = self.env['construction.chantier'].search_count([])
        self._process(subject)
        count_after = self.env['construction.chantier'].search_count([])
        self.assertEqual(count_after, count_before + 1)
        chantier = self.env['construction.chantier'].search(
            [('name', '=', subject)], limit=1
        )
        self.assertTrue(chantier.exists(), "Chantier not found by subject")

    # ------------------------------------------------------------------
    # TC-ET-02: chantier is placed at stage_reception (REC)
    # ------------------------------------------------------------------
    def test_chantier_starts_at_reception_stage(self):
        subject = 'Appel offre maison Paris TC-ET-02'
        rec_stage = self.env.ref('construction_core.stage_reception', raise_if_not_found=False)
        self._process(subject)
        chantier = self.env['construction.chantier'].search(
            [('name', '=', subject)], limit=1
        )
        self.assertTrue(chantier.exists())
        if rec_stage:
            self.assertEqual(
                chantier.stage_id.id, rec_stage.id,
                f"Expected stage REC (id={rec_stage.id}), got {chantier.stage_id.code}"
            )
        else:
            # If stage_reception is not in DB (bare test env), stage must still be set
            self.assertTrue(chantier.stage_id, "Stage should always be set")

    # ------------------------------------------------------------------
    # TC-ET-03: partner is created from sender email
    # ------------------------------------------------------------------
    def test_partner_created_from_sender_email(self):
        from_addr = 'nouveauclient@batiment.fr'
        subject = 'Chantier Bordeaux TC-ET-03'
        # Ensure no prior partner
        self.env['res.partner'].search([('email', '=', from_addr)]).unlink()
        self._process(subject, from_addr=from_addr)
        partner = self.env['res.partner'].search([('email', '=', from_addr)], limit=1)
        self.assertTrue(partner.exists(), "Partner should have been created from sender email")

    # ------------------------------------------------------------------
    # TC-ET-04: existing partner is reused, not duplicated
    # ------------------------------------------------------------------
    def test_existing_partner_is_reused(self):
        from_addr = 'existing.client@blg.fr'
        subject = 'Chantier Marseille TC-ET-04'
        existing = self.env['res.partner'].create({
            'name': 'Existing BLG Client',
            'email': from_addr,
        })
        count_before = self.env['res.partner'].search_count([('email', '=', from_addr)])
        self._process(subject, from_addr=from_addr)
        count_after = self.env['res.partner'].search_count([('email', '=', from_addr)])
        self.assertEqual(count_before, count_after, "Partner was duplicated")
        chantier = self.env['construction.chantier'].search(
            [('name', '=', subject)], limit=1
        )
        self.assertTrue(chantier.exists())
        self.assertEqual(chantier.client.id, existing.id)

    # ------------------------------------------------------------------
    # TC-ET-05: body text is stored as description
    # ------------------------------------------------------------------
    def test_body_stored_as_description(self):
        subject = 'Chantier Grenoble TC-ET-05'
        body = '15 avenue Jean Jaurès\n38000 Grenoble\nRénovation totale façade.'
        self._process(subject, body=body)
        chantier = self.env['construction.chantier'].search(
            [('name', '=', subject)], limit=1
        )
        self.assertTrue(chantier.exists())
        # Description should contain the plain-text body content
        self.assertTrue(chantier.description, "Description should not be empty")

    # ------------------------------------------------------------------
    # TC-ET-06: message is posted to chantier thread after creation
    # ------------------------------------------------------------------
    def test_message_logged_on_chantier_thread(self):
        subject = 'Chantier Nantes TC-ET-06'
        self._process(subject)
        chantier = self.env['construction.chantier'].search(
            [('name', '=', subject)], limit=1
        )
        self.assertTrue(chantier.exists())
        # At least one message on the thread (the creation message)
        messages = chantier.message_ids
        self.assertTrue(messages, "Chantier thread should have at least one message")
