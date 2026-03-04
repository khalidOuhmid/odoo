# -*- coding: utf-8 -*-
"""
AAA Test Suite: construction_base
===================================
Couvre les modèles Chapter, Stage, et Chantier.

Pattern : Arrange → Act → Assert (AAA)
Author   : Antigravity / BLG Groupe
Version  : 1.0
"""
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError
from datetime import date, timedelta
from odoo import fields


class TestConstructionChapter(TransactionCase):
    """Tests for construction.chapter model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.chapter = cls.env['construction.chapter'].create({
            'name': 'AO Test Chapter',
            'code': 'AOTST',
            'sequence': 1,
        })

    # ---- Constraints ----

    def test_chapter_code_unique(self):
        """AAA: Duplicate chapter codes must raise an IntegrityError / ValidationError."""
        # Arrange: existing chapter has code 'AOTST'
        # Act & Assert
        with self.assertRaises(Exception):
            self.env['construction.chapter'].create({
                'name': 'Another Chapter',
                'code': 'AOTST',  # duplicate
            })

    def test_chapter_name_unique(self):
        """AAA: Duplicate chapter names must raise an error."""
        with self.assertRaises(Exception):
            self.env['construction.chapter'].create({
                'name': 'AO Test Chapter',  # duplicate
                'code': 'XXX99',
            })

    def test_chapter_sequence_must_be_positive(self):
        """AAA: Negative sequence must fail SQL constraint."""
        with self.assertRaises(Exception):
            self.env['construction.chapter'].create({
                'name': 'Neg Seq Chapter',
                'code': 'NEGQ',
                'sequence': -1,
            })

    # ---- Computed Fields ----

    def test_chapter_stage_count_computed(self):
        """AAA: stage_count is updated when a stage is added."""
        # Arrange
        before = self.chapter.stage_count
        # Act
        self.env['construction.stage'].create({
            'name': 'Stage Init',
            'code': 'STINIT',
            'chapter_id': self.chapter.id,
        })
        self.chapter._compute_counts()
        # Assert
        self.assertEqual(self.chapter.stage_count, before + 1)

    def test_chapter_action_view_chantiers_returns_action(self):
        """AAA: action_view_chantiers returns an act_window dict."""
        # Act
        result = self.chapter.action_view_chantiers()
        # Assert
        self.assertEqual(result.get('type'), 'ir.actions.act_window')
        self.assertEqual(result.get('res_model'), 'construction.chantier')


class TestConstructionStage(TransactionCase):
    """Tests for construction.stage model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.chapter = cls.env['construction.chapter'].create({
            'name': 'Test Chapter Stage Suite',
            'code': 'TCHST',
        })
        cls.stage_a = cls.env['construction.stage'].create({
            'name': 'Stage A',
            'code': 'STA',
            'chapter_id': cls.chapter.id,
            'sequence': 10,
        })
        cls.stage_b = cls.env['construction.stage'].create({
            'name': 'Stage B',
            'code': 'STB',
            'chapter_id': cls.chapter.id,
            'sequence': 20,
        })

    # ---- Full Name ----

    def test_full_name_computed_correctly(self):
        """AAA: full_name combines chapter name and stage name."""
        self.stage_a._compute_full_name()
        self.assertEqual(self.stage_a.full_name, 'Test Chapter Stage Suite - Stage A')

    # ---- Stage Navigation ----

    def test_get_next_stage_returns_stage_b(self):
        """AAA: get_next_stage from A returns B (sequence order)."""
        # Act
        next_stage = self.stage_a.get_next_stage()
        # Assert
        self.assertEqual(next_stage.id, self.stage_b.id)

    def test_get_next_stage_last_returns_empty(self):
        """AAA: get_next_stage from the final stage returns empty recordset."""
        result = self.stage_b.get_next_stage()
        self.assertFalse(result)

    def test_get_previous_stage_returns_stage_a(self):
        """AAA: get_previous_stage from B returns A."""
        # Act
        prev = self.stage_b.get_previous_stage()
        # Assert
        self.assertEqual(prev.id, self.stage_a.id)

    def test_get_previous_stage_first_returns_empty(self):
        """AAA: get_previous_stage from first stage returns empty."""
        result = self.stage_a.get_previous_stage()
        self.assertFalse(result)

    # ---- SQL Constraints ----

    def test_stage_code_unique_within_chapter(self):
        """AAA: Duplicate (code, chapter_id) raises an error."""
        with self.assertRaises(Exception):
            self.env['construction.stage'].create({
                'name': 'Stage A Duplicate',
                'code': 'STA',  # duplicate within same chapter
                'chapter_id': self.chapter.id,
            })


class TestConstructionChantier(TransactionCase):
    """Tests for construction.chantier model — the core domain model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.chapter = cls.env['construction.chapter'].create({
            'name': 'Appel Offre Test',
            'code': 'AOTEST',
        })
        cls.stage = cls.env['construction.stage'].create({
            'name': 'Réception',
            'code': 'REC',
            'chapter_id': cls.chapter.id,
            'sequence': 10,
        })
        cls.client = cls.env['res.partner'].create({
            'name': 'Client BLG Test',
            'email': 'client.base.test@blg.fr',
        })

    def _create_chantier(self, **kwargs):
        """Helper: create a chantier with safe defaults."""
        defaults = {
            'name': 'Chantier AAA Test',
            'client': self.client.id,
            'stage_id': self.stage.id,
            'address': '5 Rue du Bâtiment',
            'city': 'Paris',
        }
        defaults.update(kwargs)
        return self.env['construction.chantier'].create(defaults)
    
    # ---- Reference Auto-generation ----

    def test_reference_auto_generated_on_create(self):
        """AAA: Reference is auto-generated and not '/' after creation."""
        # Act
        chantier = self._create_chantier()
        # Assert
        self.assertTrue(chantier.reference)
        self.assertNotEqual(chantier.reference, '/')

    def test_two_chantiers_have_different_references(self):
        """AAA: Two separate chantiers must have unique references."""
        c1 = self._create_chantier(name='Chantier Alpha')
        c2 = self._create_chantier(name='Chantier Beta')
        self.assertNotEqual(c1.reference, c2.reference)

    # ---- Date Constraints ----

    def test_contract_start_after_end_raises_validation_error(self):
        """AAA: Setting start_date > end_date must raise a ValidationError."""
        # Arrange
        chantier = self._create_chantier()
        today = date.today()
        # Act & Assert
        with self.assertRaises(ValidationError):
            chantier.write({
                'date_start_contract': today + timedelta(days=10),
                'date_end_contract': today,
            })

    def test_contract_dates_equal_allowed(self):
        """AAA: start == end (single-day contract) should be valid."""
        chantier = self._create_chantier()
        today = date.today()
        # Should not raise
        chantier.write({
            'date_start_contract': today,
            'date_end_contract': today,
        })

    # ---- Duration Computations ----

    def test_duration_planned_computed(self):
        """AAA: Planned duration in days is correctly computed from contract dates."""
        chantier = self._create_chantier()
        today = date.today()
        chantier.write({
            'date_start_contract': today,
            'date_end_contract': today + timedelta(days=29),
        })
        chantier._compute_duration_planned()
        self.assertEqual(chantier.duration_planned, 30)

    # ---- Deadline Status ----

    def test_deadline_status_on_time(self):
        """AAA: deadline_status is on_time when > 30 days remaining."""
        chantier = self._create_chantier()
        chantier.write({'date_end_contract': date.today() + timedelta(days=90)})
        chantier._compute_days_remaining()
        chantier._compute_deadline_status()
        self.assertEqual(chantier.deadline_status, 'on_time')

    def test_deadline_status_warning(self):
        """AAA: deadline_status is warning when <= 30 days remaining."""
        chantier = self._create_chantier()
        chantier.write({'date_end_contract': date.today() + timedelta(days=20)})
        chantier._compute_days_remaining()
        chantier._compute_deadline_status()
        self.assertEqual(chantier.deadline_status, 'warning')

    def test_deadline_status_late(self):
        """AAA: deadline_status is late when <= 7 days remaining."""
        chantier = self._create_chantier()
        chantier.write({'date_end_contract': date.today() + timedelta(days=5)})
        chantier._compute_days_remaining()
        chantier._compute_deadline_status()
        self.assertEqual(chantier.deadline_status, 'late')

    # ---- Stage Validators ----

    def test_check_reception_stage_fails_without_address(self):
        """AAA: Stage reception validator fails if address is missing."""
        chantier = self._create_chantier(address=False, description='test', phone='0102030405')
        ok, msg = chantier.check_reception_stage()
        self.assertFalse(ok)
        self.assertIn('adresse', msg)

    def test_check_reception_stage_fails_without_description(self):
        """AAA: Stage reception validator fails if description is missing."""
        chantier = self._create_chantier(description=False, phone='0102030405')
        ok, msg = chantier.check_reception_stage()
        self.assertFalse(ok)
        self.assertIn('description', msg)

    def test_check_reception_stage_passes_with_all_fields(self):
        """AAA: Stage reception validator passes when all required fields are present."""
        chantier = self._create_chantier(
            address='123 Rue OK',
            description='Travaux de rénovation complète',
            phone='0102030405'
        )
        ok, msg = chantier.check_reception_stage()
        self.assertTrue(ok)

    def test_check_progress_25_fails_below_threshold(self):
        """AAA: Progress must be >= 25 to pass the T25 stage validator."""
        chantier = self._create_chantier()
        chantier.progress = 10.0
        ok, msg = chantier.check_construction_25_percentage_stage()
        self.assertFalse(ok)

    def test_check_progress_25_passes_at_threshold(self):
        """AAA: Progress >= 25 passes the T25 stage validator."""
        chantier = self._create_chantier()
        chantier.progress = 25.0
        ok, _ = chantier.check_construction_25_percentage_stage()
        self.assertTrue(ok)

    def test_check_warranty_stage_fails_below_100(self):
        """AAA: Warranty stage fails if progress < 100."""
        chantier = self._create_chantier()
        chantier.progress = 80.0
        ok, msg = chantier.check_warranty_stage()
        self.assertFalse(ok)

    # ---- Chapter Name Computed ----

    def test_chapter_name_computed_from_stage(self):
        """AAA: chapter_name follows the assigned stage's parent chapter."""
        chantier = self._create_chantier()
        chantier._compute_chapter_name()
        self.assertEqual(chantier.chapter_name, self.chapter.name)

    # ---- Next Progress Threshold ----

    def test_next_progress_threshold_below_25(self):
        """AAA: Next threshold below 25% is 25."""
        chantier = self._create_chantier()
        result = chantier._get_next_progress_threshold(10.0)
        self.assertEqual(result, 25)

    def test_next_progress_threshold_above_75(self):
        """AAA: Next threshold above 75% is 100."""
        chantier = self._create_chantier()
        result = chantier._get_next_progress_threshold(80.0)
        self.assertEqual(result, 100)

    def test_next_progress_threshold_complete(self):
        """AAA: No next threshold when already at 100%."""
        chantier = self._create_chantier()
        result = chantier._get_next_progress_threshold(100.0)
        self.assertIsNone(result)
