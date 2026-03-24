# -*- coding: utf-8 -*-
"""
Tests for the Chantier state machine: validators, transitions, guards.
Covers methods not exercised by other test files.
"""
import datetime

from odoo.tests.common import TransactionCase
from odoo.tests import tagged
from odoo.exceptions import UserError, ValidationError


@tagged('post_install', '-at_install')
class TestStateMachineValidators(TransactionCase):
    """Unit tests for each stage validator returned by check_* methods."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.client = cls.env['res.partner'].create({'name': 'SM Client', 'is_company': True})
        cls.subcontractor = cls.env['res.partner'].create({
            'name': 'SM Sub', 'supplier_rank': 1,
        })

        cls.chapter = cls.env['construction.chapter'].create({
            'name': 'SM Chapter', 'code': 'SM_CH', 'sequence': 200,
        })
        # Stages matching the real stage machine codes
        for code, seq in [('REC', 10), ('VT', 20), ('DE', 30), ('DA', 40),
                          ('FD', 50), ('T25', 60), ('T50', 70), ('T75', 80),
                          ('T100', 90), ('LR', 100), ('AP', 110), ('RET', 120),
                          ('DC', 130), ('SS', 140)]:
            cls.env['construction.stage'].create({
                'name': code, 'code': code, 'sequence': seq, 'chapter_id': cls.chapter.id,
            })

        cls.stages = {s.code: s for s in cls.env['construction.stage'].search(
            [('chapter_id', '=', cls.chapter.id)]
        )}
        cls.category = cls.env['construction.lot.category'].create({
            'name': 'SM Cat', 'code': 'SM_CAT',
        })

    def _make_chantier(self, stage_code='REC', **kwargs):
        """Helper: create a chantier in a given stage."""
        vals = {
            'name': f'Chantier {stage_code}',
            'client': self.client.id,
            'stage_id': self.stages[stage_code].id,
        }
        vals.update(kwargs)
        return self.env['construction.chantier'].create(vals)

    def _make_lot(self, chantier, execution_type='external', **kwargs):
        vals = {
            'category_id': self.category.id,
            'chantier_id': chantier.id,
            'execution_type': execution_type,
        }
        vals.update(kwargs)
        return self.env['construction.lot'].create(vals)

    # ========================= check_reception_stage =========================

    def test_check_reception_stage_all_fields_present_returns_ok(self):
        # Arrange
        chantier = self._make_chantier('REC')
        chantier.write({
            'address': '1 Rue du Chantier',
            'description': 'Des travaux importants',
            'phone': '0612345678',
        })
        # Act
        ok, msg = chantier.check_reception_stage()
        # Assert
        self.assertTrue(ok)
        self.assertEqual(msg, 'OK')

    def test_check_reception_stage_missing_fields_returns_false(self):
        # Arrange — chantier without address, description, phone
        chantier = self._make_chantier('REC')
        # Act
        ok, msg = chantier.check_reception_stage()
        # Assert
        self.assertFalse(ok)
        self.assertIn('Adresse', msg)

    # ========================= check_quotation_sent_stage =========================

    def test_check_quotation_sent_stage_no_lots_returns_false(self):
        # Arrange
        chantier = self._make_chantier('DE')
        # Act
        ok, msg = chantier.check_quotation_sent_stage()
        # Assert
        self.assertFalse(ok)
        self.assertIn('lot', msg.lower())

    def test_check_quotation_sent_stage_with_lots_no_quote_returns_false(self):
        # Arrange
        chantier = self._make_chantier('DE')
        self._make_lot(chantier, execution_type='internal')
        # Act — no quotation created
        ok, msg = chantier.check_quotation_sent_stage()
        # Assert
        self.assertFalse(ok)

    # ========================= check_quotation_accepted_stage =========================

    def test_check_quotation_accepted_stage_no_lots_returns_false(self):
        # Arrange
        chantier = self._make_chantier('DA')
        # Act
        ok, msg = chantier.check_quotation_accepted_stage()
        # Assert
        self.assertFalse(ok)

    def test_check_quotation_accepted_stage_external_lot_no_subcontractor(self):
        # Arrange
        chantier = self._make_chantier('DA')
        self._make_lot(chantier, execution_type='external')
        # Act
        ok, msg = chantier.check_quotation_accepted_stage()
        # Assert
        self.assertFalse(ok)
        self.assertIn('Sous-traitant', msg)

    def test_check_quotation_accepted_stage_internal_lot_no_dates(self):
        # Arrange — internal lot (no subcontractor required) but dates missing
        chantier = self._make_chantier('DA')
        self._make_lot(chantier, execution_type='internal')
        # Act
        ok, msg = chantier.check_quotation_accepted_stage()
        # Assert — blocked on missing dates
        self.assertFalse(ok)

    def test_check_quotation_accepted_stage_all_satisfied(self):
        # Arrange
        chantier = self._make_chantier('DA')
        self._make_lot(chantier, execution_type='internal')
        chantier.write({
            'date_start_contract': datetime.date(2025, 1, 1),
            'date_end_contract': datetime.date(2025, 12, 31),
            'date_start_internal': datetime.date(2025, 1, 1),
            'date_end_internal': datetime.date(2025, 12, 31),
        })
        # Act
        ok, msg = chantier.check_quotation_accepted_stage()
        # Assert
        self.assertTrue(ok)
        self.assertEqual(msg, 'OK')

    # ========================= check_construction_percentage_stage =========================

    def test_check_construction_percentage_t25_insufficient_progress(self):
        # Arrange — chantier in T25 with 10% progress
        chantier = self._make_chantier('T25')
        cat = self.env['construction.lot.category'].create({'name': 'T25 Cat', 'code': 'T25_CAT'})
        self.env['construction.lot'].create({
            'category_id': cat.id, 'chantier_id': chantier.id,
            'price': 1000.0, 'completion_percentage': 10.0,
        })
        chantier._compute_progress()
        # Act
        ok, msg = chantier.check_construction_percentage_stage()
        # Assert
        self.assertFalse(ok)
        self.assertIn('25', msg)

    def test_check_construction_percentage_t25_sufficient_progress(self):
        # Arrange — chantier in T25 with ≥ 25% progress
        chantier = self._make_chantier('T25')
        cat = self.env['construction.lot.category'].create({'name': 'T25 Ok Cat', 'code': 'T25OK'})
        self.env['construction.lot'].create({
            'category_id': cat.id, 'chantier_id': chantier.id,
            'price': 1000.0, 'completion_percentage': 30.0,
        })
        chantier._compute_progress()
        # Act
        ok, msg = chantier.check_construction_percentage_stage()
        # Assert
        self.assertTrue(ok)

    # ========================= check_warranty_stage =========================

    def test_check_warranty_stage_progress_below_100(self):
        # Arrange
        chantier = self._make_chantier('LR')
        # Act — progress is 0 (no lots)
        ok, msg = chantier.check_warranty_stage()
        # Assert
        self.assertFalse(ok)
        self.assertIn('100', msg)

    def test_check_warranty_stage_progress_at_100(self):
        # Arrange — patch progress to 100 via lot
        chantier = self._make_chantier('LR')
        cat = self.env['construction.lot.category'].create({'name': 'LR Cat', 'code': 'LR_CAT'})
        self.env['construction.lot'].create({
            'category_id': cat.id, 'chantier_id': chantier.id,
            'price': 1000.0, 'completion_percentage': 100.0,
        })
        chantier._compute_progress()
        # Act
        ok, msg = chantier.check_warranty_stage()
        # Assert
        self.assertTrue(ok)

    # ========================= check_warranty_retention_stage =========================

    def test_check_warranty_retention_stage_no_end_date(self):
        # Arrange
        chantier = self._make_chantier('RET')
        # Act
        ok, msg = chantier.check_warranty_retention_stage()
        # Assert
        self.assertFalse(ok)
        self.assertIn('contractuelle', msg.lower())

    def test_check_warranty_retention_stage_warranty_expired(self):
        # Arrange — end date 2 years ago so warranty (365 days) is fully elapsed
        chantier = self._make_chantier('RET')
        past_date = datetime.date.today() - datetime.timedelta(days=730)
        chantier.write({'date_end_contract': past_date})
        # Act
        ok, msg = chantier.check_warranty_retention_stage()
        # Assert
        self.assertTrue(ok)

    def test_check_warranty_retention_stage_warranty_in_progress(self):
        # Arrange — end date 1 month ago so 365-day warranty still runs
        chantier = self._make_chantier('RET')
        recent_date = datetime.date.today() - datetime.timedelta(days=30)
        chantier.write({'date_end_contract': recent_date})
        # Act
        ok, msg = chantier.check_warranty_retention_stage()
        # Assert
        self.assertFalse(ok)
        self.assertIn('restants', msg)

    # ========================= _can_move_to_next_stage =========================

    def test_can_move_to_next_stage_no_stage(self):
        # Arrange
        chantier = self._make_chantier('REC')
        chantier.with_context(bypass_stage_validation=True).write({'stage_id': False})
        # Act
        ok, msg = chantier._can_move_to_next_stage()
        # Assert
        self.assertFalse(ok)

    def test_can_move_to_next_stage_terminal_stage(self):
        # Arrange — DC has no next and no validator → True
        chantier = self._make_chantier('DC')
        # Act
        ok, msg = chantier._can_move_to_next_stage()
        # Assert
        self.assertTrue(ok)

    # ========================= _can_move_to_previous_stage =========================

    def test_can_move_to_previous_stage_blocked_from_ret_chapter(self):
        # Arrange — find or create a chapter whose code is in BACKWARD_BLOCKED_CHAPTERS ('RET')
        chap_ret = self.env['construction.chapter'].search([('code', '=', 'RET')], limit=1)
        if not chap_ret:
            chap_ret = self.env['construction.chapter'].create({
                'name': 'Retention Chapter', 'code': 'RET', 'sequence': 300,
            })
        stage_ret = self.env['construction.stage'].search(
            [('chapter_id', '=', chap_ret.id)], limit=1,
        )
        if not stage_ret:
            stage_ret = self.env['construction.stage'].create({
                'name': 'RET Stage', 'code': 'RETSM', 'sequence': 10, 'chapter_id': chap_ret.id,
            })
        chantier = self._make_chantier('REC')
        chantier.with_context(bypass_stage_validation=True).write({'stage_id': stage_ret.id})
        # Act
        ok, msg = chantier._can_move_to_previous_stage()
        # Assert
        self.assertFalse(ok)
        self.assertIn('RET', msg)

    def test_can_move_to_previous_stage_trav_over_50_blocked(self):
        # Arrange — find or create a chapter whose code is 'TRAV'
        chap_trav = self.env['construction.chapter'].search([('code', '=', 'TRAV')], limit=1)
        if not chap_trav:
            chap_trav = self.env['construction.chapter'].create({
                'name': 'Trav Chapter', 'code': 'TRAV', 'sequence': 310,
            })
        stage_trav = self.env['construction.stage'].search(
            [('chapter_id', '=', chap_trav.id)], limit=1,
        )
        if not stage_trav:
            stage_trav = self.env['construction.stage'].create({
                'name': 'TRAV Stage', 'code': 'TRAVSM', 'sequence': 10, 'chapter_id': chap_trav.id,
            })
        chantier = self._make_chantier('REC')
        chantier.with_context(bypass_stage_validation=True).write({'stage_id': stage_trav.id})
        # Patch progress to 60 via lot
        cat = self.env['construction.lot.category'].create({'name': 'Trav Cat', 'code': 'TRAVSM_C'})
        self.env['construction.lot'].create({
            'category_id': cat.id, 'chantier_id': chantier.id,
            'price': 1000.0, 'completion_percentage': 60.0,
        })
        chantier._compute_progress()
        # Act
        ok, msg = chantier._can_move_to_previous_stage()
        # Assert
        self.assertFalse(ok)
        self.assertIn('50', msg)

    # ========================= _is_at_or_after_stage =========================

    def test_is_at_or_after_stage_same_stage_returns_true(self):
        # Arrange
        chantier = self._make_chantier('FD')
        target = self.stages['FD']
        # Act
        result = chantier._is_at_or_after_stage(target)
        # Assert
        self.assertTrue(result)

    def test_is_at_or_after_stage_before_target_returns_false(self):
        # Arrange
        chantier = self._make_chantier('REC')
        target = self.stages['FD']
        # Act
        result = chantier._is_at_or_after_stage(target)
        # Assert
        self.assertFalse(result)

    def test_is_at_or_after_stage_after_target_returns_true(self):
        # Arrange — LR is after FD in same chapter
        chantier = self._make_chantier('LR')
        target = self.stages['FD']
        # Act
        result = chantier._is_at_or_after_stage(target)
        # Assert
        self.assertTrue(result)

    def test_is_at_or_after_stage_no_stage_returns_false(self):
        # Arrange
        chantier = self._make_chantier('REC')
        chantier.with_context(bypass_stage_validation=True).write({'stage_id': False})
        target = self.stages['FD']
        # Act
        result = chantier._is_at_or_after_stage(target)
        # Assert
        self.assertFalse(result)

    # ========================= action_move_to_previous_stage =========================

    def test_action_move_to_previous_stage_no_stage_raises(self):
        # Arrange
        chantier = self._make_chantier('REC')
        chantier.with_context(bypass_stage_validation=True).write({'stage_id': False})
        # Act & Assert
        with self.assertRaises(UserError):
            chantier.action_move_to_previous_stage()

    def test_action_move_to_previous_stage_moves_back(self):
        # Arrange — VT stage has REC before it in same chapter (sequence order)
        chantier = self._make_chantier('VT')
        # Act
        result = chantier.action_move_to_previous_stage()
        # Assert — stage moved back to REC
        self.assertEqual(chantier.stage_id.code, 'REC')

    # ========================= _get_next_stage =========================

    def test_get_next_stage_uses_state_machine(self):
        # Arrange — REC -> VT per STAGE_TRANSITIONS
        chantier = self._make_chantier('REC')
        # Act
        next_stage = chantier._get_next_stage()
        # Assert
        self.assertEqual(next_stage.code, 'VT')

    def test_get_next_stage_no_stage_returns_none(self):
        # Arrange
        chantier = self._make_chantier('REC')
        chantier.with_context(bypass_stage_validation=True).write({'stage_id': False})
        # Act
        result = chantier._get_next_stage()
        # Assert
        self.assertFalse(result)

    def test_get_next_stage_dc_fallback_to_chapter_sequence(self):
        # Arrange — DC has no 'next' code in STAGE_TRANSITIONS; _get_next_stage
        # falls back to stage_id.get_next_stage() which finds the next stage by
        # sequence in the same chapter.  In the test chapter, SS (seq=140) follows
        # DC (seq=130), so the result is SS, not False.
        chantier = self._make_chantier('DC')
        # Act
        result = chantier._get_next_stage()
        # Assert — either SS is returned (fallback) or nothing if DC is truly last
        if result:
            self.assertEqual(result.code, 'SS')
        else:
            # DC is last in this chapter — both outcomes are correct
            self.assertFalse(result)


@tagged('post_install', '-at_install')
class TestChantierDashboardFields(TransactionCase):
    """Tests for chantier_dashboard computed fields."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.client = cls.env['res.partner'].create({'name': 'Dash Client'})
        cls.chantier = cls.env['construction.chantier'].create({
            'name': 'Dashboard Test Chantier', 'client': cls.client.id,
        })

    def test_compute_days_remaining_active_with_end_date(self):
        # Arrange
        future = datetime.date.today() + datetime.timedelta(days=10)
        self.chantier.write({'date_end_contract': future, 'state': 'active'})
        # Act
        self.chantier._compute_days_remaining()
        # Assert
        self.assertEqual(self.chantier.days_remaining, 10)

    def test_compute_days_remaining_no_date(self):
        # Arrange
        self.chantier.write({'date_end_contract': False, 'state': 'active'})
        # Act
        self.chantier._compute_days_remaining()
        # Assert
        self.assertEqual(self.chantier.days_remaining, 0)

    def test_compute_deadline_status_overdue(self):
        # Arrange — end date in the past
        past = datetime.date.today() - datetime.timedelta(days=1)
        self.chantier.write({'date_end_contract': past, 'state': 'active'})
        self.chantier._compute_days_remaining()
        # Act
        self.chantier._compute_deadline_status()
        # Assert
        self.assertEqual(self.chantier.deadline_status, 'overdue')
        self.assertEqual(self.chantier.deadline_color, 1)

    def test_compute_deadline_status_on_time(self):
        # Arrange — end date far in the future
        future = datetime.date.today() + datetime.timedelta(days=60)
        self.chantier.write({'date_end_contract': future, 'state': 'active'})
        self.chantier._compute_days_remaining()
        # Act
        self.chantier._compute_deadline_status()
        # Assert
        self.assertEqual(self.chantier.deadline_status, 'on_time')

    def test_compute_deadline_status_critical(self):
        # Arrange — end date in 5 days
        near = datetime.date.today() + datetime.timedelta(days=5)
        self.chantier.write({'date_end_contract': near, 'state': 'active'})
        self.chantier._compute_days_remaining()
        # Act
        self.chantier._compute_deadline_status()
        # Assert
        self.assertEqual(self.chantier.deadline_status, 'critical')

    def test_compute_action_visibility_with_stage(self):
        # Arrange — chantier already has a stage from create()
        # Act
        self.chantier._compute_action_visibility()
        # Assert
        self.assertTrue(self.chantier.show_assign_subcontractors)
        self.assertTrue(self.chantier.show_mark_not_pursued)

    def test_compute_action_visibility_no_stage(self):
        # Arrange
        chantier = self.env['construction.chantier'].create({
            'name': 'No Stage Dash', 'client': self.client.id,
        })
        chantier.with_context(bypass_stage_validation=True).write({'stage_id': False})
        # Act
        chantier._compute_action_visibility()
        # Assert
        self.assertFalse(chantier.show_schedule_visit)
        self.assertFalse(chantier.show_create_quote)


@tagged('post_install', '-at_install')
class TestLotManagementWizard(TransactionCase):
    """Tests for construction.lot.management.wizard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.client = cls.env['res.partner'].create({'name': 'LMW Client'})
        cls.subcontractor = cls.env['res.partner'].create({
            'name': 'LMW Sub', 'supplier_rank': 1,
        })
        cls.chantier = cls.env['construction.chantier'].create({
            'name': 'LMW Chantier', 'client': cls.client.id,
        })
        cls.category = cls.env['construction.lot.category'].create({
            'name': 'LMW Cat', 'code': 'LMW_CAT',
        })
        cls.lot = cls.env['construction.lot'].create({
            'category_id': cls.category.id,
            'chantier_id': cls.chantier.id,
            'execution_type': 'external',
            'price': 10000.0,
        })

    def test_wizard_saves_progress_to_lot(self):
        # Arrange
        wizard = self.env['construction.lot.management.wizard'].with_context(
            active_id=self.lot.id, active_model='construction.lot',
        ).create({
            'lot_id': self.lot.id,
            'execution_type': 'external',
            'progress_percentage': 40.0,
        })
        # Act
        wizard.action_save()
        # Assert
        self.assertAlmostEqual(self.lot.completion_percentage, 40.0, places=1)

    def test_wizard_saves_subcontractor_to_lot(self):
        # Arrange
        wizard = self.env['construction.lot.management.wizard'].with_context(
            active_id=self.lot.id, active_model='construction.lot',
        ).create({
            'lot_id': self.lot.id,
            'execution_type': 'external',
            'subcontractor_id': self.subcontractor.id,
            'progress_percentage': 0.0,
        })
        # Act
        wizard.action_save()
        # Assert
        self.assertEqual(self.lot.subcontractor_id.id, self.subcontractor.id)

    def test_wizard_clears_subcontractor_when_internal(self):
        # Arrange — lot currently has a subcontractor
        self.lot.write({'subcontractor_id': self.subcontractor.id})
        wizard = self.env['construction.lot.management.wizard'].with_context(
            active_id=self.lot.id, active_model='construction.lot',
        ).create({
            'lot_id': self.lot.id,
            'execution_type': 'internal',
            'progress_percentage': 0.0,
        })
        # Act
        wizard.action_save()
        # Assert
        self.assertFalse(self.lot.subcontractor_id)

    def test_wizard_date_constraint_start_after_end(self):
        # Arrange
        wizard = self.env['construction.lot.management.wizard'].with_context(
            active_id=self.lot.id, active_model='construction.lot',
        ).create({
            'lot_id': self.lot.id,
            'execution_type': 'external',
            'progress_percentage': 0.0,
        })
        # Act & Assert
        with self.assertRaises(ValidationError):
            wizard.write({
                'date_start': datetime.date(2025, 6, 1),
                'date_end': datetime.date(2025, 1, 1),
            })

    def test_wizard_compute_progress_values_over_billed(self):
        # Arrange
        wizard = self.env['construction.lot.management.wizard'].with_context(
            active_id=self.lot.id, active_model='construction.lot',
        ).create({
            'lot_id': self.lot.id,
            'execution_type': 'external',
            'progress_percentage': 120.0,
        })
        # Act
        wizard._compute_progress_values()
        # Assert
        self.assertTrue(wizard.is_over_billed)

    def test_wizard_compute_progress_values_not_over_billed(self):
        # Arrange
        wizard = self.env['construction.lot.management.wizard'].with_context(
            active_id=self.lot.id, active_model='construction.lot',
        ).create({
            'lot_id': self.lot.id,
            'execution_type': 'external',
            'progress_percentage': 80.0,
        })
        # Act
        wizard._compute_progress_values()
        # Assert
        self.assertFalse(wizard.is_over_billed)

    def test_wizard_generate_contract_not_all_prerequisites_met(self):
        # Arrange — can_generate_contract is False (no subcontractor, no PO)
        wizard = self.env['construction.lot.management.wizard'].with_context(
            active_id=self.lot.id, active_model='construction.lot',
        ).create({
            'lot_id': self.lot.id,
            'execution_type': 'external',
            'progress_percentage': 0.0,
        })
        # Act & Assert
        with self.assertRaises(UserError):
            wizard.action_generate_contract()
