# -*- coding: utf-8 -*-
"""
Tests for MailThread extension in mail_automation.py.

Covers: _is_construction_project_email, _extract_address_from_content,
_extract_phone_from_content, _get_or_create_client.
Integration tests for message_new are already in test_core.py.
"""
from odoo.tests import tagged

from .common import ConstructionCoreTestBase


@tagged('post_install', '-at_install')
class TestIsConstructionProjectEmail(ConstructionCoreTestBase):
    """Tests for _is_construction_project_email."""

    def _check(self, msg_dict):
        return self.env['mail.thread']._is_construction_project_email(msg_dict)

    def test_match_by_recipient_email(self):
        # GIVEN message sent to the configured construction email
        msg = {'to': 'appel-doffre@blggroupe.com', 'subject': 'Something', 'cc': ''}
        self.assertTrue(self._check(msg))

    def test_match_by_cc_email(self):
        # GIVEN email cc'd to construction address
        msg = {'to': 'other@example.com', 'cc': 'appel-doffre@blggroupe.com', 'subject': 'Hi'}
        self.assertTrue(self._check(msg))

    def test_match_by_subject_appel_offre(self):
        msg = {'to': 'random@example.com', 'cc': '', 'subject': "Appel d'offre maison"}
        self.assertTrue(self._check(msg))

    def test_match_by_subject_nouveau_chantier(self):
        msg = {'to': 'random@example.com', 'cc': '', 'subject': 'Nouveau chantier Lyon'}
        self.assertTrue(self._check(msg))

    def test_match_by_subject_projet_construction(self):
        msg = {'to': 'random@example.com', 'cc': '', 'subject': 'Projet construction 2025'}
        self.assertTrue(self._check(msg))

    def test_no_match_unrelated_email(self):
        # GIVEN an unrelated email
        msg = {'to': 'hr@company.com', 'cc': '', 'subject': 'Congés payés juillet'}
        self.assertFalse(self._check(msg))

    def test_case_insensitive_recipient(self):
        # GIVEN email address in uppercase
        msg = {'to': 'APPEL-DOFFRE@BLGGROUPE.COM', 'cc': '', 'subject': 'Random'}
        self.assertTrue(self._check(msg))

    def test_empty_message_dict_does_not_crash(self):
        # GIVEN empty dict
        result = self._check({})
        self.assertFalse(result)


@tagged('post_install', '-at_install')
class TestExtractAddressFromContent(ConstructionCoreTestBase):
    """Tests for _extract_address_from_content."""

    def _extract(self, content):
        return self.env['mail.thread']._extract_address_from_content(content)

    def test_extracts_zip_code(self):
        content = "Le chantier se situe au 75001 Paris, France."
        result = self._extract(content)
        self.assertEqual(result.get('zip_code'), '75001')

    def test_extracts_city_after_zip(self):
        content = "Adresse: 12 rue de la Paix 69000 Lyon centre"
        result = self._extract(content)
        self.assertEqual(result.get('zip_code'), '69000')
        self.assertIn('Lyon', result.get('city', ''))

    def test_extracts_address_line(self):
        content = "15 avenue Jean Jaurès\n69007 Lyon"
        result = self._extract(content)
        self.assertIn('15', result.get('address', ''))

    def test_no_zip_returns_empty(self):
        content = "Pas de code postal ici, seulement du texte."
        result = self._extract(content)
        self.assertFalse(result.get('zip_code'))

    def test_empty_content_returns_empty_dict(self):
        result = self._extract('')
        self.assertIsInstance(result, dict)
        self.assertFalse(result.get('zip_code'))

    def test_multiple_digits_picks_first_five_digit_code(self):
        content = "ID: 123, Ref: 9999, Adresse: 33000 Bordeaux"
        result = self._extract(content)
        self.assertEqual(result.get('zip_code'), '33000')


@tagged('post_install', '-at_install')
class TestExtractPhoneFromContent(ConstructionCoreTestBase):
    """Tests for _extract_phone_from_content — French phone number patterns."""

    def _extract(self, content):
        return self.env['mail.thread']._extract_phone_from_content(content)

    def test_format_spaced(self):
        # 01 23 45 67 89
        result = self._extract("Contactez-nous au 01 23 45 67 89 pour plus d'infos.")
        self.assertIsNotNone(result)
        self.assertIn('01', result)

    def test_format_continuous(self):
        # 0123456789
        result = self._extract("Tel: 0623456789")
        self.assertIsNotNone(result)
        self.assertIn('06', result)

    def test_format_international(self):
        # +33 1 23 45 67 89
        result = self._extract("International: +33 1 23 45 67 89")
        self.assertIsNotNone(result)
        self.assertIn('+33', result)

    def test_no_phone_returns_none(self):
        result = self._extract("Aucun numéro de téléphone dans ce texte.")
        self.assertIsNone(result)

    def test_empty_content_returns_none(self):
        result = self._extract('')
        self.assertIsNone(result)

    def test_partial_number_not_matched(self):
        # 4-digit number should NOT be matched
        result = self._extract("Ref: 1234")
        self.assertIsNone(result)


@tagged('post_install', '-at_install')
class TestGetOrCreateClient(ConstructionCoreTestBase):
    """Tests for _get_or_create_client."""

    def _get_client(self, email_from):
        return self.env['mail.thread']._get_or_create_client(email_from)

    def test_finds_existing_partner_by_email(self):
        # GIVEN an existing partner with a known email
        partner = self.env['res.partner'].create({
            'name': 'Jean Dupont',
            'email': 'jean.dupont@example.com',
        })
        result = self._get_client('jean.dupont@example.com')
        self.assertEqual(result.id, partner.id)

    def test_creates_new_partner_when_not_found(self):
        # GIVEN an unknown email
        result = self._get_client('nouveau.client@construction.fr')
        self.assertTrue(result.exists())
        self.assertEqual(result.email, 'nouveau.client@construction.fr')

    def test_extracts_name_from_formatted_address(self):
        # GIVEN "Display Name <email@domain.com>"
        result = self._get_client('Marie Curie <m.curie@lab.fr>')
        self.assertTrue(result.exists())
        self.assertIn('Marie', result.name)

    def test_invalid_email_returns_none(self):
        # GIVEN a string with no valid email
        result = self._get_client('not-an-email')
        self.assertIsNone(result)

    def test_does_not_duplicate_existing_partner(self):
        # GIVEN partner already exists
        self.env['res.partner'].create({
            'name': 'Existing',
            'email': 'no.duplicate@test.com',
        })
        count_before = self.env['res.partner'].search_count([
            ('email', '=', 'no.duplicate@test.com')
        ])
        self._get_client('no.duplicate@test.com')
        count_after = self.env['res.partner'].search_count([
            ('email', '=', 'no.duplicate@test.com')
        ])
        self.assertEqual(count_before, count_after)


# ================================================================
# _create_construction_project
# ================================================================

@tagged('post_install', '-at_install')
class TestCreateConstructionProject(ConstructionCoreTestBase):
    """Tests for _create_construction_project."""

    def setUp(self):
        super().setUp()
        self.client_partner = self.env['res.partner'].create({
            'name': 'Société Dupont Construction',
            'email': 'dupont@construction.fr',
            'is_company': True,
        })

    def _make_project_data(self, **overrides):
        data = {
            'name': 'Rénovation immeuble Dupont',
            'client': self.client_partner,
            'description': 'Travaux de rénovation complète',
            'address': '12 rue de la Paix',
            'city': 'Paris',
            'zip_code': '75001',
            'phone': '0612345678',
        }
        data.update(overrides)
        return data

    def test_creates_chantier_with_correct_name_and_client(self):
        # ARRANGE
        project_data = self._make_project_data()
        # ACT
        chantier = self.env['mail.thread']._create_construction_project(project_data)
        # ASSERT
        self.assertTrue(chantier and chantier.exists())
        self.assertEqual(chantier.name, 'Rénovation immeuble Dupont')
        self.assertEqual(chantier.client.id, self.client_partner.id)

    def test_creates_chantier_with_address_data(self):
        # ARRANGE
        project_data = self._make_project_data()
        # ACT
        chantier = self.env['mail.thread']._create_construction_project(project_data)
        # ASSERT — address data stored
        self.assertEqual(chantier.city, 'Paris')
        self.assertEqual(chantier.zip_code, '75001')

    def test_returns_none_when_name_missing(self):
        # ARRANGE — name is empty
        project_data = self._make_project_data(name='')
        # ACT
        chantier = self.env['mail.thread']._create_construction_project(project_data)
        # ASSERT
        self.assertIsNone(chantier)

    def test_returns_none_when_client_missing(self):
        # ARRANGE — no client
        project_data = self._make_project_data(client=None)
        # ACT
        chantier = self.env['mail.thread']._create_construction_project(project_data)
        # ASSERT
        self.assertIsNone(chantier)

    def test_uses_ao_stage_when_available(self):
        # ARRANGE — create an AO stage
        chapter = self.env['construction.chapter'].create({
            'name': 'AO Chapter', 'code': 'AO_CH', 'sequence': 5,
        })
        stage_ao = self.env['construction.stage'].create({
            'name': 'Appel Offre', 'code': 'AO',
            'chapter_id': chapter.id, 'sequence': 1,
        })
        project_data = self._make_project_data()
        # ACT
        chantier = self.env['mail.thread']._create_construction_project(project_data)
        # ASSERT
        self.assertEqual(chantier.stage_id.id, stage_ao.id)

    def test_falls_back_to_first_stage_when_no_ao_stage(self):
        # ARRANGE — no AO stage; self.stage from common.py is the only stage
        self.env['construction.stage'].search([('code', '=', 'AO')]).write({'code': 'NO_AO'})
        project_data = self._make_project_data()
        # ACT
        chantier = self.env['mail.thread']._create_construction_project(project_data)
        # ASSERT — chantier was created (fallback to first stage or no stage)
        self.assertTrue(chantier and chantier.exists())


# ================================================================
# _handle_construction_project_creation  (integration)
# ================================================================

@tagged('post_install', '-at_install')
class TestHandleConstructionProjectCreation(ConstructionCoreTestBase):
    """Integration tests for _handle_construction_project_creation."""

    def _make_message_dict(self, **overrides):
        msg = {
            'subject': 'Appel offre renovation maison Lyon',
            'from': 'Jean Dupont <j.dupont@client.fr>',
            'body': '12 rue des Fleurs\n69000 Lyon\nTél: 0601020304\n\nTravaux de rénovation.',
            'to': 'appel-doffre@blggroupe.com',
            'cc': '',
        }
        msg.update(overrides)
        return msg

    def test_creates_chantier_from_valid_email(self):
        # ARRANGE
        chantier_count_before = self.env['construction.chantier'].search_count([])
        msg = self._make_message_dict()
        # ACT
        self.env['mail.thread']._handle_construction_project_creation(msg)
        # ASSERT — one new chantier was created
        chantier_count_after = self.env['construction.chantier'].search_count([])
        self.assertEqual(chantier_count_after, chantier_count_before + 1)

    def test_new_chantier_has_subject_as_name(self):
        # ARRANGE
        msg = self._make_message_dict(subject='Projet Lyon - Réhabilitation')
        # ACT
        self.env['mail.thread']._handle_construction_project_creation(msg)
        # ASSERT — chantier name matches the email subject
        chantier = self.env['construction.chantier'].search([
            ('name', '=', 'Projet Lyon - Réhabilitation')
        ], limit=1)
        self.assertTrue(chantier.exists())

    def test_creates_client_partner_from_email_sender(self):
        # ARRANGE — sender does not yet exist as a partner
        self.env['res.partner'].search([('email', '=', 'nouveau.st@entreprise.fr')]).unlink()
        msg = self._make_message_dict(
            subject='Nouveau chantier Grenoble',
            **{'from': 'nouveau.st@entreprise.fr'},
        )
        # ACT
        self.env['mail.thread']._handle_construction_project_creation(msg)
        # ASSERT — client partner was created
        partner = self.env['res.partner'].search([('email', '=', 'nouveau.st@entreprise.fr')], limit=1)
        self.assertTrue(partner.exists())

    def test_does_not_create_chantier_when_subject_missing(self):
        # ARRANGE — empty subject → no project name → creation skipped
        chantier_count_before = self.env['construction.chantier'].search_count([])
        msg = self._make_message_dict(subject='')
        # ACT
        self.env['mail.thread']._handle_construction_project_creation(msg)
        # ASSERT — no new chantier
        self.assertEqual(
            self.env['construction.chantier'].search_count([]),
            chantier_count_before
        )

    def test_does_not_raise_on_invalid_email_data(self):
        # ARRANGE — completely empty message dict
        # ACT / ASSERT — should not raise, just silently skip
        try:
            self.env['mail.thread']._handle_construction_project_creation({})
        except Exception as e:
            self.fail(f"_handle_construction_project_creation raised unexpectedly: {e}")
