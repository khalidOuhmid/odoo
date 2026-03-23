# -*- coding: utf-8 -*-
"""
Tests for the Chantier stage machine validators and stage navigation.

Coverage:
- check_reception_stage         (REC → VT)
- check_quotation_accepted_stage (DA → FD)
- check_dossier_finalization_stage (FD → T25)
- check_construction_percentage_stage (T25/T50/T75/T100 → next)
- check_warranty_stage          (T100 → LR)
- check_warranty_retention_stage (RET → DC)
- action_move_to_previous_stage (all blocking cases)
- action_move_to_next_stage     (blocked → UserError or wizard per user role)
"""
import datetime
from odoo.tests.common import TransactionCase
from odoo.tests import tagged
from odoo.exceptions import UserError


# ================================================================
# check_reception_stage
# ================================================================

@tagged('post_install', '-at_install')
class TestCheckReceptionStage(TransactionCase):

    def setUp(self):
        super().setUp()
        self.env = self.env(context=dict(self.env.context, tracking_disable=True))

        chapter = self.env['construction.chapter'].create({
            'name': 'REC Test Chapter', 'code': 'REC_CH', 'sequence': 91,
        })
        stage = self.env['construction.stage'].create({
            'name': 'REC Stage', 'code': 'REC_TEST',
            'chapter_id': chapter.id, 'sequence': 10,
        })
        self.client = self.env['res.partner'].create({
            'name': 'Client REC', 'is_company': True,
        })
        self.chantier = self.env['construction.chantier'].create({
            'name': 'Chantier REC Test',
            'client': self.client.id,
            'stage_id': stage.id,
        })

    def test_passes_when_all_required_fields_filled(self):
        # ARRANGE
        self.chantier.write({
            'address': '12 rue de la Paix, 75001 Paris',
            'description': 'Rénovation complète du bâtiment',
            'phone': '0612345678',
        })
        # ACT
        ok, message = self.chantier.check_reception_stage()
        # ASSERT
        self.assertTrue(ok)
        self.assertEqual(message, "OK")

    def test_fails_when_address_missing(self):
        # ARRANGE — no address
        self.chantier.write({'description': 'Desc', 'phone': '0612345678'})
        # ACT
        ok, message = self.chantier.check_reception_stage()
        # ASSERT
        self.assertFalse(ok)
        self.assertIn("Adresse", message)

    def test_fails_when_description_missing(self):
        # ARRANGE — no description
        self.chantier.write({'address': '12 rue Test', 'phone': '0612345678'})
        # ACT
        ok, message = self.chantier.check_reception_stage()
        # ASSERT
        self.assertFalse(ok)
        self.assertIn("Description", message)

    def test_fails_when_phone_missing(self):
        # ARRANGE — no phone
        self.chantier.write({'address': '12 rue Test', 'description': 'Description OK'})
        # ACT
        ok, message = self.chantier.check_reception_stage()
        # ASSERT
        self.assertFalse(ok)
        self.assertIn("Téléphone", message)

    def test_fails_and_reports_all_missing_fields(self):
        # ARRANGE — only client is set (no address, description, phone)
        # ACT
        ok, message = self.chantier.check_reception_stage()
        # ASSERT — all three missing fields mentioned in one message
        self.assertFalse(ok)
        self.assertIn("Adresse", message)
        self.assertIn("Description", message)
        self.assertIn("Téléphone", message)


# ================================================================
# check_quotation_accepted_stage  (DA validator)
# ================================================================

@tagged('post_install', '-at_install')
class TestCheckQuotationAcceptedStage(TransactionCase):

    def setUp(self):
        super().setUp()
        self.env = self.env(context=dict(self.env.context, tracking_disable=True))

        chapter = self.env['construction.chapter'].create({
            'name': 'DA Test Chapter', 'code': 'DA_CH', 'sequence': 92,
        })
        stage = self.env['construction.stage'].create({
            'name': 'DA Stage', 'code': 'DA_TEST',
            'chapter_id': chapter.id, 'sequence': 10,
        })
        self.client = self.env['res.partner'].create({
            'name': 'Client DA', 'is_company': True,
        })
        self.category = self.env['construction.lot.category'].create({
            'name': 'DA Category', 'code': 'DA_CAT',
        })
        self.chantier = self.env['construction.chantier'].create({
            'name': 'Chantier DA Test',
            'client': self.client.id,
            'stage_id': stage.id,
        })

    def _set_all_dates(self):
        self.chantier.with_context(bypass_stage_validation=True).write({
            'date_start_contract': '2025-01-01',
            'date_end_contract': '2025-12-31',
            'date_start_internal': '2025-01-01',
            'date_end_internal': '2025-12-31',
        })

    def test_fails_with_no_lots(self):
        # ARRANGE — no lots at all
        # ACT
        ok, message = self.chantier.check_quotation_accepted_stage()
        # ASSERT
        self.assertFalse(ok)
        self.assertIn("Lots", message)

    def test_fails_when_external_lot_has_no_subcontractor(self):
        # ARRANGE — external lot without subcontractor
        self.env['construction.lot'].create({
            'category_id': self.category.id,
            'chantier_id': self.chantier.id,
            'execution_type': 'external',
        })
        self._set_all_dates()
        # ACT
        ok, message = self.chantier.check_quotation_accepted_stage()
        # ASSERT
        self.assertFalse(ok)
        self.assertIn("Sous-traitants", message)

    def test_fails_when_contract_start_date_missing(self):
        # ARRANGE — external lot has subcontractor but no contract start date
        st = self.env['res.partner'].create({'name': 'ST DA No Date', 'supplier_rank': 1})
        self.env['construction.lot'].create({
            'category_id': self.category.id,
            'chantier_id': self.chantier.id,
            'execution_type': 'external',
            'subcontractor_id': st.id,
        })
        # Only set end dates
        self.chantier.with_context(bypass_stage_validation=True).write({
            'date_end_contract': '2025-12-31',
            'date_end_internal': '2025-12-31',
        })
        # ACT
        ok, message = self.chantier.check_quotation_accepted_stage()
        # ASSERT
        self.assertFalse(ok)
        self.assertIn("contractuelle", message)

    def test_passes_with_internal_lot_and_all_dates(self):
        # ARRANGE — internal lot (no subcontractor required) with all dates
        self.env['construction.lot'].create({
            'category_id': self.category.id,
            'chantier_id': self.chantier.id,
            'execution_type': 'internal',
        })
        self._set_all_dates()
        # ACT
        ok, message = self.chantier.check_quotation_accepted_stage()
        # ASSERT
        self.assertTrue(ok, f"Expected pass but got: {message}")

    def test_passes_with_external_lot_subcontractor_and_all_dates(self):
        # ARRANGE — external lot with subcontractor + all required dates
        st = self.env['res.partner'].create({'name': 'ST DA Valid', 'supplier_rank': 1})
        self.env['construction.lot'].create({
            'category_id': self.category.id,
            'chantier_id': self.chantier.id,
            'execution_type': 'external',
            'subcontractor_id': st.id,
        })
        self._set_all_dates()
        # ACT
        ok, message = self.chantier.check_quotation_accepted_stage()
        # ASSERT
        self.assertTrue(ok, f"Expected pass but got: {message}")


# ================================================================
# check_dossier_finalization_stage  (FD validator)
# ================================================================

@tagged('post_install', '-at_install')
class TestCheckDossierFinalizationStage(TransactionCase):

    def setUp(self):
        super().setUp()
        self.env = self.env(context=dict(self.env.context, tracking_disable=True))

        chapter = self.env['construction.chapter'].create({
            'name': 'FD Test Chapter', 'code': 'FD_CH', 'sequence': 93,
        })
        stage = self.env['construction.stage'].create({
            'name': 'FD Stage', 'code': 'FD_TEST',
            'chapter_id': chapter.id, 'sequence': 10,
        })
        self.client = self.env['res.partner'].create({
            'name': 'Client FD', 'is_company': True,
        })
        self.category = self.env['construction.lot.category'].create({
            'name': 'FD Category', 'code': 'FD_CAT',
        })
        self.chantier = self.env['construction.chantier'].create({
            'name': 'Chantier FD Test',
            'client': self.client.id,
            'stage_id': stage.id,
        })

    def test_fails_when_no_lots_defined(self):
        # ARRANGE — no lots on the chantier
        # ACT
        ok, message = self.chantier.check_dossier_finalization_stage()
        # ASSERT
        self.assertFalse(ok)
        self.assertIn("Aucun lot", message)

    def test_fails_when_external_lot_has_no_subcontractor(self):
        # ARRANGE — external lot without subcontractor
        self.env['construction.lot'].create({
            'category_id': self.category.id,
            'chantier_id': self.chantier.id,
            'execution_type': 'external',
        })
        # ACT
        ok, message = self.chantier.check_dossier_finalization_stage()
        # ASSERT
        self.assertFalse(ok)
        self.assertIn("Sous-traitant non assigné", message)

    def test_fails_when_contractual_dates_missing(self):
        # ARRANGE — only internal lots (no PO/contract needed) but no dates
        self.env['construction.lot'].create({
            'category_id': self.category.id,
            'chantier_id': self.chantier.id,
            'execution_type': 'internal',
        })
        # ACT
        ok, message = self.chantier.check_dossier_finalization_stage()
        # ASSERT
        self.assertFalse(ok)
        self.assertIn("contractuelles", message)

    def test_passes_with_internal_lots_and_dates(self):
        # ARRANGE — only internal lots (PO/contract/CCTP checks are skipped)
        # plus the required contractual dates
        self.env['construction.lot'].create({
            'category_id': self.category.id,
            'chantier_id': self.chantier.id,
            'execution_type': 'internal',
        })
        self.chantier.with_context(bypass_stage_validation=True).write({
            'date_start_contract': '2025-01-01',
            'date_end_contract': '2025-12-31',
        })
        # ACT
        ok, message = self.chantier.check_dossier_finalization_stage()
        # ASSERT
        self.assertTrue(ok, f"Expected pass but got: {message}")


# ================================================================
# check_construction_percentage_stage  (T25/T50/T75/T100 validator)
# ================================================================

@tagged('post_install', '-at_install')
class TestCheckConstructionPercentageStage(TransactionCase):

    def setUp(self):
        super().setUp()
        self.env = self.env(context=dict(self.env.context, tracking_disable=True))

        self.chapter = self.env['construction.chapter'].create({
            'name': 'TRAV Test Chapter', 'code': 'TRAVT_CH', 'sequence': 94,
        })
        self.client = self.env['res.partner'].create({
            'name': 'Client TRAV', 'is_company': True,
        })

    def _make_chantier_at_stage(self, code, sequence):
        stage = self.env['construction.stage'].create({
            'name': f'Stage {code}', 'code': code,
            'chapter_id': self.chapter.id, 'sequence': sequence,
        })
        chantier = self.env['construction.chantier'].create({
            'name': f'Chantier {code} Test',
            'client': self.client.id,
            'stage_id': stage.id,
        })
        return chantier

    def _add_lot_with_progress(self, chantier, completion_percentage):
        cat_code = f'PCT_{chantier.stage_id.code}_{completion_percentage}'[:20]
        cat = self.env['construction.lot.category'].create({
            'name': f'Cat {completion_percentage}%', 'code': cat_code,
        })
        self.env['construction.lot'].create({
            'category_id': cat.id,
            'chantier_id': chantier.id,
            'execution_type': 'internal',
            'price': 1000.0,
            'completion_percentage': completion_percentage,
        })

    def test_t25_passes_when_progress_at_30_percent(self):
        # ARRANGE
        chantier = self._make_chantier_at_stage('T25', 10)
        self._add_lot_with_progress(chantier, 30.0)
        # ACT
        ok, message = chantier.check_construction_percentage_stage()
        # ASSERT
        self.assertTrue(ok, f"T25 should pass at 30%, got: {message}")

    def test_t25_fails_when_progress_below_25_percent(self):
        # ARRANGE
        chantier = self._make_chantier_at_stage('T25', 11)
        self._add_lot_with_progress(chantier, 10.0)
        # ACT
        ok, message = chantier.check_construction_percentage_stage()
        # ASSERT
        self.assertFalse(ok)
        self.assertIn("25%", message)

    def test_t50_passes_when_progress_at_60_percent(self):
        # ARRANGE
        chantier = self._make_chantier_at_stage('T50', 20)
        self._add_lot_with_progress(chantier, 60.0)
        # ACT
        ok, message = chantier.check_construction_percentage_stage()
        # ASSERT
        self.assertTrue(ok, f"T50 should pass at 60%, got: {message}")

    def test_t50_fails_when_progress_below_50_percent(self):
        # ARRANGE
        chantier = self._make_chantier_at_stage('T50', 21)
        self._add_lot_with_progress(chantier, 40.0)
        # ACT
        ok, message = chantier.check_construction_percentage_stage()
        # ASSERT
        self.assertFalse(ok)
        self.assertIn("50%", message)

    def test_t75_fails_when_progress_below_75_percent(self):
        # ARRANGE
        chantier = self._make_chantier_at_stage('T75', 30)
        self._add_lot_with_progress(chantier, 50.0)
        # ACT
        ok, message = chantier.check_construction_percentage_stage()
        # ASSERT
        self.assertFalse(ok)
        self.assertIn("75%", message)

    def test_t100_passes_at_full_completion(self):
        # ARRANGE
        chantier = self._make_chantier_at_stage('T100', 40)
        self._add_lot_with_progress(chantier, 100.0)
        # ACT
        ok, message = chantier.check_construction_percentage_stage()
        # ASSERT
        self.assertTrue(ok, f"T100 should pass at 100%, got: {message}")

    def test_t100_fails_below_100_percent(self):
        # ARRANGE
        chantier = self._make_chantier_at_stage('T100', 41)
        self._add_lot_with_progress(chantier, 99.0)
        # ACT
        ok, message = chantier.check_construction_percentage_stage()
        # ASSERT
        self.assertFalse(ok)
        self.assertIn("100%", message)


# ================================================================
# check_warranty_stage  (LR validator)
# ================================================================

@tagged('post_install', '-at_install')
class TestCheckWarrantyStage(TransactionCase):

    def setUp(self):
        super().setUp()
        self.env = self.env(context=dict(self.env.context, tracking_disable=True))

        chapter = self.env['construction.chapter'].create({
            'name': 'LR Test Chapter', 'code': 'LR_CH', 'sequence': 95,
        })
        stage = self.env['construction.stage'].create({
            'name': 'LR Stage', 'code': 'LR_TEST',
            'chapter_id': chapter.id, 'sequence': 10,
        })
        self.client = self.env['res.partner'].create({
            'name': 'Client LR', 'is_company': True,
        })
        self.chantier = self.env['construction.chantier'].create({
            'name': 'Chantier LR Test',
            'client': self.client.id,
            'stage_id': stage.id,
        })

    def _add_lot_with_progress(self, completion_percentage, code_suffix=''):
        cat = self.env['construction.lot.category'].create({
            'name': f'LR Cat {code_suffix}', 'code': f'LRC{code_suffix}',
        })
        self.env['construction.lot'].create({
            'category_id': cat.id,
            'chantier_id': self.chantier.id,
            'execution_type': 'internal',
            'price': 1000.0,
            'completion_percentage': completion_percentage,
        })

    def test_passes_when_progress_is_100_percent(self):
        # ARRANGE
        self._add_lot_with_progress(100.0, 'OK')
        # ACT
        ok, message = self.chantier.check_warranty_stage()
        # ASSERT
        self.assertTrue(ok, f"LR should pass at 100%, got: {message}")

    def test_fails_when_progress_below_100_percent(self):
        # ARRANGE
        self._add_lot_with_progress(80.0, 'FAIL')
        # ACT
        ok, message = self.chantier.check_warranty_stage()
        # ASSERT
        self.assertFalse(ok)
        self.assertIn("100", message)

    def test_fails_when_no_lots_progress_is_zero(self):
        # ARRANGE — no lots means progress = 0
        # ACT
        ok, message = self.chantier.check_warranty_stage()
        # ASSERT
        self.assertFalse(ok)


# ================================================================
# check_warranty_retention_stage  (RET validator)
# ================================================================

@tagged('post_install', '-at_install')
class TestCheckWarrantyRetentionStage(TransactionCase):

    def setUp(self):
        super().setUp()
        self.env = self.env(context=dict(self.env.context, tracking_disable=True))

        chapter = self.env['construction.chapter'].create({
            'name': 'RET Test Chapter', 'code': 'RETT_CH', 'sequence': 96,
        })
        stage = self.env['construction.stage'].create({
            'name': 'RET Stage', 'code': 'RET_TEST',
            'chapter_id': chapter.id, 'sequence': 10,
        })
        self.client = self.env['res.partner'].create({
            'name': 'Client RET', 'is_company': True,
        })
        self.chantier = self.env['construction.chantier'].create({
            'name': 'Chantier RET Test',
            'client': self.client.id,
            'stage_id': stage.id,
        })

    def test_fails_when_end_date_not_defined(self):
        # ARRANGE — no date_end_contract
        # ACT
        ok, message = self.chantier.check_warranty_retention_stage()
        # ASSERT
        self.assertFalse(ok)
        self.assertIn("fin contractuelle", message)

    def test_fails_when_warranty_period_still_active(self):
        # ARRANGE — contract ended 6 months ago (warranty = 365 days, still in progress)
        recent_end = datetime.date.today() - datetime.timedelta(days=180)
        self.chantier.with_context(bypass_stage_validation=True).write({
            'date_end_contract': recent_end,
        })
        # ACT
        ok, message = self.chantier.check_warranty_retention_stage()
        # ASSERT
        self.assertFalse(ok)
        self.assertIn("garantie", message)

    def test_message_includes_remaining_days_when_warranty_active(self):
        # ARRANGE — warranty ends in 100 days
        end_date = datetime.date.today() - datetime.timedelta(days=265)
        self.chantier.with_context(bypass_stage_validation=True).write({
            'date_end_contract': end_date,
        })
        # ACT
        ok, message = self.chantier.check_warranty_retention_stage()
        # ASSERT — message should mention remaining days
        self.assertFalse(ok)
        self.assertIn("jours", message)

    def test_passes_after_full_warranty_period_elapsed(self):
        # ARRANGE — contract ended 400 days ago (> 365 day warranty period)
        past_end = datetime.date.today() - datetime.timedelta(days=400)
        self.chantier.with_context(bypass_stage_validation=True).write({
            'date_end_contract': past_end,
        })
        # ACT
        ok, message = self.chantier.check_warranty_retention_stage()
        # ASSERT
        self.assertTrue(ok, f"Expected pass after warranty period, got: {message}")


# ================================================================
# action_move_to_previous_stage
# ================================================================

@tagged('post_install', '-at_install')
class TestActionMoveToPreviousStage(TransactionCase):

    def setUp(self):
        super().setUp()
        self.env = self.env(context=dict(self.env.context, tracking_disable=True))

        # Chapter AVT (seq 10) with two stages: S1 (seq 10), S2 (seq 20)
        self.chapter_avt = self.env['construction.chapter'].create({
            'name': 'AVT Prev Test', 'code': 'AVTP', 'sequence': 10,
        })
        self.stage_s1 = self.env['construction.stage'].create({
            'name': 'Stage 1 AVTP', 'code': 'S1_AVTP',
            'chapter_id': self.chapter_avt.id, 'sequence': 10,
        })
        self.stage_s2 = self.env['construction.stage'].create({
            'name': 'Stage 2 AVTP', 'code': 'S2_AVTP',
            'chapter_id': self.chapter_avt.id, 'sequence': 20,
        })

        # Chapter TRAV (seq 20) with one stage
        self.chapter_trav = self.env['construction.chapter'].create({
            'name': 'TRAV Prev Test', 'code': 'TRAV', 'sequence': 20,
        })
        self.stage_trav = self.env['construction.stage'].create({
            'name': 'TRAV Prev Stage', 'code': 'T25_PREV',
            'chapter_id': self.chapter_trav.id, 'sequence': 10,
        })

        # Chapter ARCH (backward-blocked)
        self.chapter_arch = self.env['construction.chapter'].create({
            'name': 'ARCH Prev Test', 'code': 'ARCH', 'sequence': 90,
        })
        self.stage_arch = self.env['construction.stage'].create({
            'name': 'ARCH Stage', 'code': 'ARCH_TST',
            'chapter_id': self.chapter_arch.id, 'sequence': 10,
        })

        # Chapter RET (backward-blocked)
        self.chapter_ret = self.env['construction.chapter'].create({
            'name': 'RET Prev Test', 'code': 'RET', 'sequence': 85,
        })
        self.stage_ret = self.env['construction.stage'].create({
            'name': 'RET Stage', 'code': 'RET_TST',
            'chapter_id': self.chapter_ret.id, 'sequence': 10,
        })

        self.client = self.env['res.partner'].create({
            'name': 'Client Prev Stage', 'is_company': True,
        })
        self.chantier = self.env['construction.chantier'].create({
            'name': 'Chantier Previous Stage Test',
            'client': self.client.id,
            'stage_id': self.stage_s2.id,
        })

    def test_moves_to_prior_stage_in_same_chapter(self):
        # ARRANGE — chantier at S2, S1 is the previous stage
        self.assertEqual(self.chantier.stage_id.code, 'S2_AVTP')
        # ACT
        self.chantier.action_move_to_previous_stage()
        # ASSERT
        self.assertEqual(self.chantier.stage_id.code, 'S1_AVTP')

    def test_blocked_in_arch_chapter(self):
        # ARRANGE — chantier in ARCH (backward always blocked)
        self.chantier.with_context(bypass_stage_validation=True).write({
            'stage_id': self.stage_arch.id,
        })
        # ACT / ASSERT
        with self.assertRaises(UserError):
            self.chantier.action_move_to_previous_stage()

    def test_blocked_in_ret_chapter(self):
        # ARRANGE — chantier in RET (backward always blocked)
        self.chantier.with_context(bypass_stage_validation=True).write({
            'stage_id': self.stage_ret.id,
        })
        # ACT / ASSERT
        with self.assertRaises(UserError):
            self.chantier.action_move_to_previous_stage()

    def test_blocked_in_trav_with_progress_above_50_percent(self):
        # ARRANGE — chantier in TRAV chapter at 60% progress
        self.chantier.with_context(bypass_stage_validation=True).write({
            'stage_id': self.stage_trav.id,
        })
        cat = self.env['construction.lot.category'].create({
            'name': 'TRAV High Cat', 'code': 'TVH_C',
        })
        self.env['construction.lot'].create({
            'category_id': cat.id,
            'chantier_id': self.chantier.id,
            'execution_type': 'internal',
            'price': 1000.0,
            'completion_percentage': 60.0,
        })
        # ACT / ASSERT
        with self.assertRaises(UserError):
            self.chantier.action_move_to_previous_stage()

    def test_allowed_in_trav_with_progress_below_50_percent(self):
        # ARRANGE — chantier in TRAV chapter at 30% progress (below 50% threshold)
        self.chantier.with_context(bypass_stage_validation=True).write({
            'stage_id': self.stage_trav.id,
        })
        cat = self.env['construction.lot.category'].create({
            'name': 'TRAV Low Cat', 'code': 'TVL_C',
        })
        self.env['construction.lot'].create({
            'category_id': cat.id,
            'chantier_id': self.chantier.id,
            'execution_type': 'internal',
            'price': 1000.0,
            'completion_percentage': 30.0,
        })
        # ACT — should not raise
        self.chantier.action_move_to_previous_stage()
        # ASSERT — stage has changed (went back to AVT's last stage)
        self.assertNotEqual(self.chantier.stage_id.code, 'T25_PREV')

    def test_raises_user_error_at_first_stage(self):
        # ARRANGE — chantier is at the very first stage (S1, no previous stage exists)
        self.chantier.with_context(bypass_stage_validation=True).write({
            'stage_id': self.stage_s1.id,
        })
        # ACT / ASSERT
        with self.assertRaises(UserError):
            self.chantier.action_move_to_previous_stage()


# ================================================================
# action_move_to_next_stage — blocked path
# ================================================================

@tagged('post_install', '-at_install')
class TestActionMoveToNextStageBlocked(TransactionCase):

    def setUp(self):
        super().setUp()
        self.env = self.env(context=dict(self.env.context, tracking_disable=True))

        chapter = self.env['construction.chapter'].create({
            'name': 'Blocked Next Chapter', 'code': 'BLK_CH', 'sequence': 97,
        })
        # Stage REC has check_reception_stage validator (requires address, description, phone)
        self.stage_rec = self.env['construction.stage'].create({
            'name': 'Réception Test', 'code': 'REC',
            'chapter_id': chapter.id, 'sequence': 10,
        })
        self.stage_vt = self.env['construction.stage'].create({
            'name': 'Visite Technique Test', 'code': 'VT',
            'chapter_id': chapter.id, 'sequence': 20,
        })
        self.client = self.env['res.partner'].create({
            'name': 'Client Blocked', 'is_company': True,
        })
        self.chantier = self.env['construction.chantier'].create({
            'name': 'Chantier Blocked Next Test',
            'client': self.client.id,
            'stage_id': self.stage_rec.id,
        })

    def test_raises_user_error_for_non_admin_when_validator_fails(self):
        # ARRANGE — create a regular user without construction admin group
        user = self.env['res.users'].create({
            'name': 'Regular User Blocked',
            'login': 'regular_blocked_test_user',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        # Ensure user is not in admin group
        admin_group = self.env.ref(
            'construction_core.group_construction_admin', raise_if_not_found=False
        )
        if admin_group:
            admin_group.users = [(3, user.id)]

        chantier_as_user = self.chantier.with_user(user)
        # ACT / ASSERT — missing required fields → validator fails → UserError for non-admin
        with self.assertRaises(UserError):
            chantier_as_user.action_move_to_next_stage()

    def test_returns_force_wizard_for_admin_when_validator_fails(self):
        # ARRANGE — add current test user to admin group
        admin_group = self.env.ref(
            'construction_core.group_construction_admin', raise_if_not_found=False
        )
        if not admin_group:
            self.skipTest("Admin group not found in construction_core")
        admin_group.users = [(4, self.env.user.id)]

        # Chantier in REC with missing required fields (address, description, phone)
        # ACT
        result = self.chantier.action_move_to_next_stage()
        # ASSERT — admin gets the force stage wizard, not an error
        self.assertEqual(result.get('type'), 'ir.actions.act_window')
        self.assertEqual(result.get('res_model'), 'construction.force.stage.wizard')

    def test_transitions_successfully_when_validator_passes(self):
        # ARRANGE — fill all required fields for REC stage
        self.chantier.with_context(bypass_stage_validation=True).write({
            'address': '12 rue du Test, 75001 Paris',
            'description': 'Description complète des travaux',
            'phone': '0612345678',
        })
        # ACT
        result = self.chantier.action_move_to_next_stage()
        # ASSERT — stage advanced to VT
        self.assertEqual(self.chantier.stage_id.code, 'VT')
        self.assertEqual(result.get('tag'), 'reload')
