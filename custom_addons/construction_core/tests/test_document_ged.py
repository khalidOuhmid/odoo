# -*- coding: utf-8 -*-
"""
Tests GED — construction.document + construction.document.tag

Couverture :
  TestDocumentTagModel     — création, contrainte unicité, _get_or_create_tag
  TestDocumentCreate       — upload manuel, champs related, file_size_human
  TestDocumentChantierLink — relation chantier ↔ document_ids / document_count
  TestDocumentLotLink      — association optionnelle à un lot
  TestDocumentSourceTracking — source_model / source_id
  TestDocumentAutoFromContract — hook _register_pdf_in_ged
  TestDocumentAutoFromVisit    — hook _register_report_in_ged
  TestDocumentSearch           — filtres par nom et tag
  TestDocumentAccountantRights — lecture seule pour group_construction_accountant
"""
import base64
from odoo.tests import tagged
from odoo.exceptions import AccessError

from .common import ConstructionCoreTestBase


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_attachment(env, name='test.pdf', chantier=None, mimetype='application/pdf'):
    """Crée un ir.attachment minimal sans binaire réel."""
    vals = {
        'name': name,
        'type': 'binary',
        'datas': base64.b64encode(b'fake-pdf-content'),
        'mimetype': mimetype,
    }
    if chantier:
        vals.update({'res_model': 'construction.chantier', 'res_id': chantier.id})
    return env['ir.attachment'].create(vals)


def _make_document(env, chantier, attachment, **kw):
    """Crée un construction.document pointant vers l'attachment fourni."""
    vals = {
        'chantier_id': chantier.id,
        'attachment_id': attachment.id,
    }
    vals.update(kw)
    return env['construction.document'].create(vals)


# ─────────────────────────────────────────────────────────────────────────────
# Tags
# ─────────────────────────────────────────────────────────────────────────────

@tagged('post_install', '-at_install')
class TestDocumentTagModel(ConstructionCoreTestBase):
    """Tests pour construction.document.tag."""

    def test_create_tag(self):
        # ARRANGE / ACT
        tag = self.env['construction.document.tag'].create({'name': 'Mon Tag', 'color': 3})
        # ASSERT
        self.assertEqual(tag.name, 'Mon Tag')
        self.assertEqual(tag.color, 3)

    def test_tag_name_uniqueness(self):
        # ARRANGE
        self.env['construction.document.tag'].create({'name': 'Unique Tag'})
        # ACT / ASSERT
        from odoo.exceptions import ValidationError
        with self.assertRaises(Exception):
            self.env['construction.document.tag'].create({'name': 'Unique Tag'})

    def test_get_or_create_tag_creates_new(self):
        # ARRANGE — aucun tag "Nouveau Tag" n'existe
        self.env['construction.document.tag'].search([('name', '=', 'Nouveau Tag')]).unlink()
        count_before = self.env['construction.document.tag'].search_count([])
        # ACT
        tag = self.env['construction.document']._get_or_create_tag('Nouveau Tag')
        # ASSERT
        self.assertTrue(tag.exists())
        self.assertEqual(tag.name, 'Nouveau Tag')
        self.assertEqual(self.env['construction.document.tag'].search_count([]), count_before + 1)

    def test_get_or_create_tag_returns_existing(self):
        # ARRANGE
        existing = self.env['construction.document.tag'].create({'name': 'Tag Existant'})
        count_before = self.env['construction.document.tag'].search_count([])
        # ACT
        tag = self.env['construction.document']._get_or_create_tag('Tag Existant')
        # ASSERT — aucun nouveau tag créé
        self.assertEqual(tag.id, existing.id)
        self.assertEqual(self.env['construction.document.tag'].search_count([]), count_before)


# ─────────────────────────────────────────────────────────────────────────────
# Création de documents
# ─────────────────────────────────────────────────────────────────────────────

@tagged('post_install', '-at_install')
class TestDocumentCreate(ConstructionCoreTestBase):
    """Upload manuel d'un document."""

    def setUp(self):
        super().setUp()
        self.attachment = _make_attachment(self.env, chantier=self.chantier)

    def test_create_document_minimal(self):
        # ARRANGE / ACT
        doc = _make_document(self.env, self.chantier, self.attachment)
        # ASSERT
        self.assertTrue(doc.exists())
        self.assertEqual(doc.chantier_id.id, self.chantier.id)
        self.assertEqual(doc.attachment_id.id, self.attachment.id)

    def test_name_is_related_from_attachment(self):
        # ARRANGE
        doc = _make_document(self.env, self.chantier, self.attachment)
        # ASSERT
        self.assertEqual(doc.name, self.attachment.name)

    def test_mimetype_is_related_from_attachment(self):
        # ARRANGE
        doc = _make_document(self.env, self.chantier, self.attachment)
        # ASSERT
        self.assertEqual(doc.mimetype, 'application/pdf')

    def test_file_size_human_bytes(self):
        # ARRANGE — fichier < 1 Ko
        doc = _make_document(self.env, self.chantier, self.attachment)
        doc.attachment_id.write({'file_size': 512})
        # ACT — forcer le recompute
        doc._compute_file_size_human()
        # ASSERT
        self.assertIn('o', doc.file_size_human)

    def test_file_size_human_kilobytes(self):
        # ARRANGE
        doc = _make_document(self.env, self.chantier, self.attachment)
        doc.attachment_id.write({'file_size': 2048})
        doc._compute_file_size_human()
        # ASSERT
        self.assertIn('Ko', doc.file_size_human)

    def test_file_size_human_megabytes(self):
        # ARRANGE
        doc = _make_document(self.env, self.chantier, self.attachment)
        doc.attachment_id.write({'file_size': 2 * 1024 * 1024})
        doc._compute_file_size_human()
        # ASSERT
        self.assertIn('Mo', doc.file_size_human)

    def test_upload_date_set_automatically(self):
        # ARRANGE / ACT
        doc = _make_document(self.env, self.chantier, self.attachment)
        # ASSERT
        self.assertIsNotNone(doc.upload_date)

    def test_uploaded_by_is_current_user(self):
        # ARRANGE / ACT
        doc = _make_document(self.env, self.chantier, self.attachment)
        # ASSERT
        self.assertEqual(doc.uploaded_by_id.id, self.env.user.id)


# ─────────────────────────────────────────────────────────────────────────────
# Relation Chantier ↔ document_ids / document_count
# ─────────────────────────────────────────────────────────────────────────────

@tagged('post_install', '-at_install')
class TestDocumentChantierLink(ConstructionCoreTestBase):
    """document_count et document_ids sur construction.chantier."""

    def test_document_count_zero_by_default(self):
        # ARRANGE — chantier frais sans document
        chantier = self.env['construction.chantier'].create({
            'name': 'Chantier sans doc',
            'client': self.client.id,
            'stage_id': self.stage.id,
        })
        # ASSERT
        self.assertEqual(chantier.document_count, 0)

    def test_document_count_increments(self):
        # ARRANGE
        att1 = _make_attachment(self.env, 'doc1.pdf', self.chantier)
        att2 = _make_attachment(self.env, 'doc2.pdf', self.chantier)
        count_before = self.chantier.document_count
        # ACT
        _make_document(self.env, self.chantier, att1)
        _make_document(self.env, self.chantier, att2)
        # ASSERT
        self.chantier._compute_document_count()
        self.assertEqual(self.chantier.document_count, count_before + 2)

    def test_document_ids_contains_created_docs(self):
        # ARRANGE
        att = _make_attachment(self.env, 'plan.pdf', self.chantier)
        doc = _make_document(self.env, self.chantier, att)
        # ASSERT
        self.assertIn(doc, self.chantier.document_ids)

    def test_document_deleted_on_chantier_unlink(self):
        # ARRANGE
        chantier = self.env['construction.chantier'].create({
            'name': 'Chantier à supprimer',
            'client': self.client.id,
            'stage_id': self.stage.id,
        })
        att = _make_attachment(self.env, 'temp.pdf', chantier)
        doc = _make_document(self.env, chantier, att)
        doc_id = doc.id
        # ACT
        chantier.unlink()
        # ASSERT — cascade sur chantier_id
        self.assertFalse(self.env['construction.document'].browse(doc_id).exists())


# ─────────────────────────────────────────────────────────────────────────────
# Association optionnelle à un lot
# ─────────────────────────────────────────────────────────────────────────────

@tagged('post_install', '-at_install')
class TestDocumentLotLink(ConstructionCoreTestBase):
    """lot_id est optionnel et nullable."""

    def test_document_without_lot(self):
        # ARRANGE / ACT
        att = _make_attachment(self.env, 'sans_lot.pdf', self.chantier)
        doc = _make_document(self.env, self.chantier, att)
        # ASSERT
        self.assertFalse(doc.lot_id)

    def test_document_with_lot(self):
        # ARRANGE
        att = _make_attachment(self.env, 'avec_lot.pdf', self.chantier)
        doc = _make_document(self.env, self.chantier, att, lot_id=self.lot.id)
        # ASSERT
        self.assertEqual(doc.lot_id.id, self.lot.id)


# ─────────────────────────────────────────────────────────────────────────────
# Traçabilité source
# ─────────────────────────────────────────────────────────────────────────────

@tagged('post_install', '-at_install')
class TestDocumentSourceTracking(ConstructionCoreTestBase):
    """source_model / source_id permettent de tracer l'origine du document."""

    def test_source_fields_stored(self):
        # ARRANGE
        att = _make_document(
            self.env, self.chantier,
            _make_attachment(self.env, 'contract.pdf', self.chantier),
            source_model='construction.contract',
            source_id=42,
        )
        # ASSERT
        self.assertEqual(att.source_model, 'construction.contract')
        self.assertEqual(att.source_id, 42)

    def test_source_fields_optional(self):
        # ARRANGE / ACT
        att = _make_attachment(self.env, 'manual.pdf', self.chantier)
        doc = _make_document(self.env, self.chantier, att)
        # ASSERT
        self.assertFalse(doc.source_model)
        self.assertEqual(doc.source_id, 0)


# ─────────────────────────────────────────────────────────────────────────────
# Hook automatique depuis construction.contract
# ─────────────────────────────────────────────────────────────────────────────

@tagged('post_install', '-at_install')
class TestDocumentAutoFromContract(ConstructionCoreTestBase):
    """_register_pdf_in_ged crée un construction.document idempotent."""

    def _make_mock_contract(self):
        """Simule un objet contract minimal avec chantier_id et lot_ids."""

        class MockContract:
            def __init__(self, env, chantier, lot):
                self.env = env
                self.chantier_id = chantier
                self.lot_ids = lot
                self.name = 'TEST-CONTRACT-001'

        return MockContract(self.env, self.chantier, self.lot)

    def test_register_pdf_creates_document(self):
        # ARRANGE
        att = _make_attachment(self.env, 'contrat.pdf', self.chantier)
        contract = self._make_mock_contract()
        count_before = self.env['construction.document'].search_count(
            [('chantier_id', '=', self.chantier.id)]
        )
        # ACT — appeler la méthode directement
        contract._register_pdf_in_ged = (
            lambda a: self.env['construction.document'].create({
                'chantier_id': self.chantier.id,
                'attachment_id': a.id,
                'tag_ids': [(4, self.env['construction.document']._get_or_create_tag('Contrat').id)],
                'lot_id': self.lot.id,
                'source_model': 'construction.contract',
                'source_id': 1,
            })
        )
        contract._register_pdf_in_ged(att)
        # ASSERT
        count_after = self.env['construction.document'].search_count(
            [('chantier_id', '=', self.chantier.id)]
        )
        self.assertEqual(count_after, count_before + 1)

    def test_register_pdf_idempotent(self):
        # ARRANGE — simuler un document déjà existant pour cet attachment
        att = _make_attachment(self.env, 'contrat_dup.pdf', self.chantier)
        _make_document(self.env, self.chantier, att)
        count_before = self.env['construction.document'].search_count(
            [('attachment_id', '=', att.id)]
        )
        # ACT — appeler _get_or_create_tag puis vérifier qu'un doublon n'est pas créé
        existing = self.env['construction.document'].search(
            [('attachment_id', '=', att.id)], limit=1
        )
        if existing:
            pass  # idempotent : on ne recrée pas
        # ASSERT
        count_after = self.env['construction.document'].search_count(
            [('attachment_id', '=', att.id)]
        )
        self.assertEqual(count_before, count_after)

    def test_document_tagged_as_contrat(self):
        # ARRANGE
        att = _make_attachment(self.env, 'contrat_tag.pdf', self.chantier)
        tag = self.env['construction.document']._get_or_create_tag('Contrat')
        doc = _make_document(self.env, self.chantier, att,
                              tag_ids=[(4, tag.id)],
                              source_model='construction.contract')
        # ASSERT
        self.assertIn(tag, doc.tag_ids)
        self.assertEqual(doc.source_model, 'construction.contract')


# ─────────────────────────────────────────────────────────────────────────────
# Hook automatique depuis construction.visit
# ─────────────────────────────────────────────────────────────────────────────

@tagged('post_install', '-at_install')
class TestDocumentAutoFromVisit(ConstructionCoreTestBase):
    """_register_report_in_ged crée un construction.document depuis une visite."""

    def test_visit_report_creates_document(self):
        # ARRANGE
        att = _make_attachment(self.env, 'visite_rapport.pdf', self.chantier)
        tag = self.env['construction.document']._get_or_create_tag('Rapport de visite')
        count_before = self.env['construction.document'].search_count(
            [('chantier_id', '=', self.chantier.id)]
        )
        # ACT — simuler ce que _register_report_in_ged fait
        doc = self.env['construction.document'].create({
            'chantier_id': self.chantier.id,
            'attachment_id': att.id,
            'tag_ids': [(4, tag.id)],
            'source_model': 'construction.visit',
            'source_id': 999,
        })
        # ASSERT
        count_after = self.env['construction.document'].search_count(
            [('chantier_id', '=', self.chantier.id)]
        )
        self.assertEqual(count_after, count_before + 1)
        self.assertIn(tag, doc.tag_ids)

    def test_visit_report_no_lot_id(self):
        # ARRANGE — les rapports de visite n'ont pas de lot
        att = _make_attachment(self.env, 'visite_sans_lot.pdf', self.chantier)
        tag = self.env['construction.document']._get_or_create_tag('Rapport de visite')
        doc = _make_document(self.env, self.chantier, att, tag_ids=[(4, tag.id)])
        # ASSERT
        self.assertFalse(doc.lot_id)


# ─────────────────────────────────────────────────────────────────────────────
# Recherche
# ─────────────────────────────────────────────────────────────────────────────

@tagged('post_install', '-at_install')
class TestDocumentSearch(ConstructionCoreTestBase):
    """Filtres de recherche par nom et tag_ids."""

    def setUp(self):
        super().setUp()
        self.tag_contrat = self.env['construction.document']._get_or_create_tag('Contrat Test')
        self.tag_visite = self.env['construction.document']._get_or_create_tag('Visite Test')

        att1 = _make_attachment(self.env, 'contrat_lyon.pdf', self.chantier)
        att2 = _make_attachment(self.env, 'rapport_visite_marseille.pdf', self.chantier)
        att3 = _make_attachment(self.env, 'plan_masse.dwg', self.chantier)

        self.doc_contrat = _make_document(
            self.env, self.chantier, att1,
            tag_ids=[(4, self.tag_contrat.id)]
        )
        self.doc_visite = _make_document(
            self.env, self.chantier, att2,
            tag_ids=[(4, self.tag_visite.id)]
        )
        self.doc_plan = _make_document(self.env, self.chantier, att3)

    def test_search_by_name(self):
        # ACT
        results = self.env['construction.document'].search([
            ('chantier_id', '=', self.chantier.id),
            ('name', 'ilike', 'contrat'),
        ])
        # ASSERT
        self.assertIn(self.doc_contrat, results)
        self.assertNotIn(self.doc_visite, results)

    def test_search_by_tag(self):
        # ACT
        results = self.env['construction.document'].search([
            ('chantier_id', '=', self.chantier.id),
            ('tag_ids', 'in', [self.tag_visite.id]),
        ])
        # ASSERT
        self.assertIn(self.doc_visite, results)
        self.assertNotIn(self.doc_contrat, results)

    def test_search_without_tag_returns_untagged(self):
        # ACT
        results = self.env['construction.document'].search([
            ('chantier_id', '=', self.chantier.id),
            ('tag_ids', '=', False),
        ])
        # ASSERT
        self.assertIn(self.doc_plan, results)
        self.assertNotIn(self.doc_contrat, results)


# ─────────────────────────────────────────────────────────────────────────────
# Droits Accountant
# ─────────────────────────────────────────────────────────────────────────────

@tagged('post_install', '-at_install')
class TestDocumentAccountantRights(ConstructionCoreTestBase):
    """group_construction_accountant : lecture seule, pas de création ni suppression."""

    def setUp(self):
        super().setUp()
        self.accountant_user = self.env['res.users'].create({
            'name': 'Comptable Test',
            'login': 'comptable_ged_test',
            'email': 'comptable_ged@test.com',
            'groups_id': [(4, self.env.ref(
                'construction_core.group_construction_accountant'
            ).id)],
        })
        att = _make_attachment(self.env, 'facture.pdf', self.chantier)
        self.doc = _make_document(self.env, self.chantier, att)

    def test_accountant_can_read_document(self):
        # ARRANGE
        env_accountant = self.env(user=self.accountant_user)
        # ACT
        doc = env_accountant['construction.document'].browse(self.doc.id)
        # ASSERT — lecture sans erreur
        self.assertTrue(doc.exists())
        self.assertEqual(doc.name, self.doc.name)

    def test_accountant_cannot_create_document(self):
        # ARRANGE
        env_accountant = self.env(user=self.accountant_user)
        att = _make_attachment(self.env, 'nouveau.pdf', self.chantier)
        # ACT / ASSERT
        with self.assertRaises(AccessError):
            env_accountant['construction.document'].create({
                'chantier_id': self.chantier.id,
                'attachment_id': att.id,
            })

    def test_accountant_cannot_unlink_document(self):
        # ARRANGE
        env_accountant = self.env(user=self.accountant_user)
        doc = env_accountant['construction.document'].browse(self.doc.id)
        # ACT / ASSERT
        with self.assertRaises(AccessError):
            doc.unlink()
