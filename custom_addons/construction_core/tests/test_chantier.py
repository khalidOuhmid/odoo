# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.tests import tagged
from odoo.exceptions import UserError, ValidationError
import datetime


@tagged('post_install', '-at_install')
class TestConstructionChantier(TransactionCase):

    def setUp(self):
        super().setUp()
        self.env = self.env(context=dict(self.env.context, tracking_disable=True))

        self.client_partner = self.env['res.partner'].create({
            'name': 'Client Test',
            'is_company': True,
        })

        self.chapter_avt = self.env['construction.chapter'].create({
            'name': 'Avant Vente Test',
            'code': 'AVT_TEST',
            'sequence': 10,
        })

        self.stage_draft = self.env['construction.stage'].create({
            'name': 'Prospect / Étude Test',
            'code': 'PROSP_TEST',
            'sequence': 1,
            'chapter_id': self.chapter_avt.id,
            'fold': False,
        })

        self.stage_da = self.env['construction.stage'].create({
            'name': 'Dossier Accepté Test',
            'code': 'DA_TEST',
            'sequence': 2,
            'chapter_id': self.chapter_avt.id,
            'fold': False,
        })

        self.env['ir.config_parameter'].sudo().set_param(
            'construction_core.default_stage_id', self.stage_draft.id
        )

        self.chantier = self.env['construction.chantier'].create({
            'name': 'Chantier Test 001',
            'client': self.client_partner.id,
            'stage_id': self.stage_draft.id,
        })

    # ========================= REFERENCE =========================

    def test_create_chantier_reference(self):
        # GIVEN a freshly created chantier
        # THEN reference should be generated (not empty or '/')
        self.assertTrue(self.chantier.reference)
        self.assertNotEqual(self.chantier.reference, '/')

    # ========================= DURATION =========================

    def test_compute_duration_planned(self):
        # GIVEN a chantier with contract dates
        self.chantier.write({
            'date_start_contract': '2025-01-01',
            'date_end_contract': '2025-01-10',
        })
        # WHEN computing planned duration
        self.chantier._compute_duration_planned()
        # THEN duration = 10 days (inclusive)
        self.assertEqual(self.chantier.duration_planned, 10)

    def test_compute_duration_planned_no_dates(self):
        # GIVEN a chantier without contract dates
        # WHEN computing planned duration
        self.chantier._compute_duration_planned()
        # THEN duration = 0
        self.assertEqual(self.chantier.duration_planned, 0)

    def test_compute_duration_actual(self):
        # GIVEN a chantier with internal dates
        self.chantier.write({
            'date_start_internal': '2025-01-01',
            'date_end_internal': '2025-01-15',
        })
        # WHEN computing actual duration
        self.chantier._compute_duration_actual()
        # THEN duration = 15 days (inclusive)
        self.assertEqual(self.chantier.duration_actual, 15)

    def test_compute_duration_actual_ongoing(self):
        # GIVEN an active chantier with start date but no end date
        self.chantier.with_context(bypass_stage_validation=True).write({
            'state': 'active',
            'date_start_internal': datetime.date.today() - datetime.timedelta(days=4),
            'date_end_internal': False,
        })
        # WHEN computing actual duration
        self.chantier._compute_duration_actual()
        # THEN duration = days since start (>= 5)
        self.assertGreaterEqual(self.chantier.duration_actual, 5)

    def test_compute_duration_actual_no_start(self):
        # GIVEN a chantier without any dates
        # WHEN computing actual duration
        self.chantier._compute_duration_actual()
        # THEN duration = 0
        self.assertEqual(self.chantier.duration_actual, 0)

    # ========================= CHAPTER NAME =========================

    def test_compute_chapter_name(self):
        # GIVEN a chantier in a stage belonging to a chapter
        # THEN chapter_name matches the chapter name
        self.chantier._compute_chapter_name()
        self.assertEqual(self.chantier.chapter_name, self.chapter_avt.name)

    def test_compute_chapter_name_no_stage(self):
        # GIVEN a chantier with no stage
        chantier_no_stage = self.env['construction.chantier'].create({
            'name': 'Chantier No Stage',
            'client': self.client_partner.id,
        })
        chantier_no_stage.with_context(bypass_stage_validation=True).write({'stage_id': False})
        # WHEN computing chapter name
        chantier_no_stage._compute_chapter_name()
        # THEN chapter_name is False/empty
        self.assertFalse(chantier_no_stage.chapter_name)

    # ========================= PROGRESS =========================

    def test_compute_progress_weighted(self):
        # GIVEN a chantier with two lots: 100€ @100%, 100€ @50%
        category_a = self.env['construction.lot.category'].create({'name': 'Lot A', 'code': 'PROG_A'})
        category_b = self.env['construction.lot.category'].create({'name': 'Lot B', 'code': 'PROG_B'})
        self.env['construction.lot'].create({
            'category_id': category_a.id, 'chantier_id': self.chantier.id,
            'price': 100.0, 'completion_percentage': 100.0,
        })
        self.env['construction.lot'].create({
            'category_id': category_b.id, 'chantier_id': self.chantier.id,
            'price': 100.0, 'completion_percentage': 50.0,
        })
        # WHEN computing progress
        self.chantier._compute_progress()
        # THEN progress = (100 + 50) / 200 * 100 = 75%
        self.assertAlmostEqual(self.chantier.progress, 75.0, places=1)

    def test_compute_progress_no_lots(self):
        # GIVEN a chantier with no lots
        # WHEN computing progress
        self.chantier._compute_progress()
        # THEN progress = 0
        self.assertEqual(self.chantier.progress, 0.0)

    def test_compute_progress_zero_price_lots(self):
        # GIVEN a chantier with lots at price=0
        cat = self.env['construction.lot.category'].create({'name': 'Lot Zero', 'code': 'ZERO_PRC'})
        self.env['construction.lot'].create({
            'category_id': cat.id, 'chantier_id': self.chantier.id,
            'price': 0.0, 'completion_percentage': 50.0,
        })
        # WHEN computing progress
        self.chantier._compute_progress()
        # THEN progress = 0 (no division by zero)
        self.assertEqual(self.chantier.progress, 0.0)

    # ========================= TOTAL COST =========================

    def test_compute_total_cost_from_lots(self):
        # GIVEN a chantier with lots (no validated sale orders)
        cat = self.env['construction.lot.category'].create({'name': 'Lot Cost', 'code': 'COST_T'})
        self.env['construction.lot'].create({
            'category_id': cat.id, 'chantier_id': self.chantier.id,
            'price': 8000.0,
        })
        # WHEN computing total cost
        self.chantier._compute_total_cost()
        # THEN total_cost = sum of lot prices
        self.assertEqual(self.chantier.total_cost, 8000.0)

    # ========================= GUARANTEE AMOUNTS =========================

    def test_compute_guarantee_amounts(self):
        # GIVEN a chantier with 2 lots (total 10000€) and 5% rate
        cat_g1 = self.env['construction.lot.category'].create({'name': 'Lot G1', 'code': 'GUAR_L1'})
        cat_g2 = self.env['construction.lot.category'].create({'name': 'Lot G2', 'code': 'GUAR_L2'})
        self.env['construction.lot'].create({'category_id': cat_g1.id, 'chantier_id': self.chantier.id, 'price': 6000.0})
        self.env['construction.lot'].create({'category_id': cat_g2.id, 'chantier_id': self.chantier.id, 'price': 4000.0})
        self.chantier.guarantee_retention_rate = 5.0
        # WHEN computing guarantee amounts
        self.chantier._compute_guarantee_amounts()
        # THEN guarantee = 10000 * 5% = 500
        self.assertAlmostEqual(self.chantier.guarantee_retention_amount, 500.0, places=2)

    def test_compute_guarantee_amounts_no_lots(self):
        # GIVEN a chantier with no lots
        self.chantier.guarantee_retention_rate = 5.0
        # WHEN computing guarantee amounts
        self.chantier._compute_guarantee_amounts()
        # THEN guarantee = 0
        self.assertEqual(self.chantier.guarantee_retention_amount, 0.0)

    # ========================= GUARANTEE RELEASE =========================

    def test_action_release_guarantee(self):
        # GIVEN a chantier with a pending guarantee
        self.chantier.write({'guarantee_status': 'pending'})
        # WHEN releasing guarantee
        self.chantier.action_release_guarantee()
        # THEN status should be released
        self.assertEqual(self.chantier.guarantee_status, 'released')

    # ========================= CRON GUARANTEE REMINDERS =========================

    def test_cron_send_guarantee_reminders_j7(self):
        # GIVEN a chantier with release date in 7 days, j7 reminder not sent
        release_date = datetime.date.today() + datetime.timedelta(days=7)
        self.chantier.with_context(bypass_stage_validation=True).write({
            'guarantee_release_date': release_date,
            'guarantee_reminder_sent_j7': False,
            'guarantee_status': 'pending',
        })
        # WHEN running cron
        self.env['construction.chantier']._cron_send_guarantee_reminders()
        # THEN j7 reminder is marked as sent
        self.assertTrue(self.chantier.guarantee_reminder_sent_j7)

    def test_cron_send_guarantee_reminders_j0(self):
        # GIVEN a chantier with release date today, j0 reminder not sent
        self.chantier.with_context(bypass_stage_validation=True).write({
            'guarantee_release_date': datetime.date.today(),
            'guarantee_reminder_sent_j0': False,
            'guarantee_status': 'pending',
        })
        # WHEN running cron
        self.env['construction.chantier']._cron_send_guarantee_reminders()
        # THEN j0 reminder is marked as sent and status is expired
        self.assertTrue(self.chantier.guarantee_reminder_sent_j0)
        self.assertEqual(self.chantier.guarantee_status, 'expired')

    def test_cron_already_sent_not_re_sent(self):
        # GIVEN a chantier with j7 already sent
        release_date = datetime.date.today() + datetime.timedelta(days=7)
        self.chantier.with_context(bypass_stage_validation=True).write({
            'guarantee_release_date': release_date,
            'guarantee_reminder_sent_j7': True,
            'guarantee_status': 'pending',
        })
        # WHEN running cron
        self.env['construction.chantier']._cron_send_guarantee_reminders()
        # THEN no double-send (still True, cron skipped it)
        self.assertTrue(self.chantier.guarantee_reminder_sent_j7)

    # ========================= AUTO-LR TRIGGER =========================

    def test_check_progress_95_trigger(self):
        # GIVEN stages T75 and LR exist
        stage_t75 = self.env['construction.stage'].create({
            'name': 'Travaux 75%', 'code': 'T75', 'sequence': 5, 'chapter_id': self.chapter_avt.id,
        })
        self.env['construction.stage'].create({
            'name': 'Levée de Réserve', 'code': 'LR', 'sequence': 6, 'chapter_id': self.chapter_avt.id,
        })
        self.chantier.with_context(bypass_stage_validation=True).write({'stage_id': stage_t75.id})
        # WHEN triggered
        self.chantier._check_progress_95_trigger()
        # THEN transitions to LR with guarantee date
        self.assertEqual(self.chantier.stage_id.code, 'LR')
        self.assertEqual(self.chantier.guarantee_status, 'pending')
        self.assertTrue(self.chantier.guarantee_release_date)

    def test_check_progress_95_trigger_non_trav_stage(self):
        # GIVEN chantier in a non-TRAV stage (PROSP_TEST)
        original_stage_id = self.chantier.stage_id.id
        # WHEN triggering 95% check
        self.chantier._check_progress_95_trigger()
        # THEN stage does NOT change (not a TRAV stage code)
        self.assertEqual(self.chantier.stage_id.id, original_stage_id)

    def test_check_progress_95_trigger_no_lr_stage(self):
        # GIVEN chantier in T75 stage and NO LR stage exists
        # Rename any existing LR stages so they can't be found
        self.env['construction.stage'].search([('code', '=', 'LR')]).write({'code': 'LR_HIDDEN'})
        stage_t75 = self.env['construction.stage'].create({
            'name': 'Travaux 75% Only', 'code': 'T75', 'sequence': 5, 'chapter_id': self.chapter_avt.id,
        })
        self.chantier.with_context(bypass_stage_validation=True).write({'stage_id': stage_t75.id})
        # WHEN triggering (no LR stage exists with code='LR')
        # THEN should not raise — silently returns, stage unchanged
        self.chantier._check_progress_95_trigger()
        self.assertEqual(self.chantier.stage_id.code, 'T75')

    # ========================= ACTION MOVE TO NEXT STAGE =========================

    def test_action_move_to_next_stage(self):
        # GIVEN a chantier in Prospect stage
        self.assertEqual(self.chantier.stage_id.code, 'PROSP_TEST')
        # WHEN moving to next stage
        self.chantier.action_move_to_next_stage()
        # THEN stage should be DA_TEST (next by sequence in same chapter)
        self.assertEqual(self.chantier.stage_id.code, 'DA_TEST')

    # ========================= WRITE VALIDATION =========================

    def test_write_date_validation_error(self):
        # GIVEN a chantier
        # WHEN writing end date before start date
        # THEN ValidationError is raised
        with self.assertRaises(ValidationError):
            self.chantier.with_context(bypass_stage_validation=True).write({
                'date_start_contract': '2025-06-01',
                'date_end_contract': '2025-01-01',
            })

    def test_write_stage_direct_forbidden_for_non_admin(self):
        # GIVEN the current user is NOT in admin group
        # Ensure user is not admin (demo user or minimal setup)
        admin_group = self.env.ref('construction_core.group_construction_admin', raise_if_not_found=False)
        if admin_group and self.env.user.has_group('construction_core.group_construction_admin'):
            self.skipTest("User has admin access – cannot test non-admin restriction")
        # WHEN writing stage_id without bypass context
        # THEN raises ValidationError
        with self.assertRaises(ValidationError):
            self.chantier.write({'stage_id': self.stage_da.id})

    def test_write_stage_bypass_context(self):
        # GIVEN a chantier in PROSP_TEST stage
        # WHEN writing stage_id with bypass_stage_validation context
        self.chantier.with_context(bypass_stage_validation=True).write({
            'stage_id': self.stage_da.id
        })
        # THEN stage changes successfully
        self.assertEqual(self.chantier.stage_id.code, 'DA_TEST')

    # ========================= SUBCONTRACTOR COUNT =========================

    def test_compute_subcontractor_count(self):
        # GIVEN two lots with different subcontractors
        st1 = self.env['res.partner'].create({'name': 'ST1', 'supplier_rank': 1})
        st2 = self.env['res.partner'].create({'name': 'ST2', 'supplier_rank': 1})
        cat_s1 = self.env['construction.lot.category'].create({'name': 'Elec', 'code': 'S_ELEC'})
        cat_s2 = self.env['construction.lot.category'].create({'name': 'Plomb', 'code': 'S_PLMB'})
        self.env['construction.lot'].create({
            'category_id': cat_s1.id, 'chantier_id': self.chantier.id,
            'execution_type': 'external', 'subcontractor_id': st1.id,
        })
        self.env['construction.lot'].create({
            'category_id': cat_s2.id, 'chantier_id': self.chantier.id,
            'execution_type': 'external', 'subcontractor_id': st2.id,
        })
        # WHEN computing subcontractor count
        self.chantier._compute_subcontractor_count()
        # THEN count = 2 (unique external subcontractors)
        self.assertEqual(self.chantier.subcontractor_count, 2)

    def test_compute_subcontractor_count_internal_lot_excluded(self):
        # GIVEN one internal lot (no subcontractor counted)
        st = self.env['res.partner'].create({'name': 'ST Internal', 'supplier_rank': 1})
        cat = self.env['construction.lot.category'].create({'name': 'Internal Lot', 'code': 'INT_LOT'})
        self.env['construction.lot'].create({
            'category_id': cat.id, 'chantier_id': self.chantier.id,
            'execution_type': 'internal', 'subcontractor_id': st.id,
        })
        # WHEN computing subcontractor count
        self.chantier._compute_subcontractor_count()
        # THEN count = 0 (internal lots excluded)
        self.assertEqual(self.chantier.subcontractor_count, 0)

    # ========================= LOTS COUNT =========================

    def test_compute_lots_count(self):
        # GIVEN two lots on the chantier
        cat1 = self.env['construction.lot.category'].create({'name': 'L1', 'code': 'LC_L1'})
        cat2 = self.env['construction.lot.category'].create({'name': 'L2', 'code': 'LC_L2'})
        self.env['construction.lot'].create({'category_id': cat1.id, 'chantier_id': self.chantier.id})
        self.env['construction.lot'].create({'category_id': cat2.id, 'chantier_id': self.chantier.id})
        # WHEN computing lots count
        self.chantier._compute_lots_count()
        # THEN count = 2
        self.assertEqual(self.chantier.lots_count, 2)

    # ========================= PROJECT SUBCONTRACTORS =========================

    def test_compute_project_subcontractors(self):
        # GIVEN two lots with subcontractors
        st1 = self.env['res.partner'].create({'name': 'PST1', 'supplier_rank': 1})
        st2 = self.env['res.partner'].create({'name': 'PST2', 'supplier_rank': 1})
        cat1 = self.env['construction.lot.category'].create({'name': 'PS Cat1', 'code': 'PSCAT1'})
        cat2 = self.env['construction.lot.category'].create({'name': 'PS Cat2', 'code': 'PSCAT2'})
        self.env['construction.lot'].create({
            'category_id': cat1.id, 'chantier_id': self.chantier.id,
            'execution_type': 'external', 'subcontractor_id': st1.id,
        })
        self.env['construction.lot'].create({
            'category_id': cat2.id, 'chantier_id': self.chantier.id,
            'execution_type': 'external', 'subcontractor_id': st2.id,
        })
        # WHEN computing project subcontractors
        self.chantier._compute_project_subcontractors()
        # THEN both appear in project_subcontractor_ids
        self.assertIn(st1, self.chantier.project_subcontractor_ids)
        self.assertIn(st2, self.chantier.project_subcontractor_ids)

    # ========================= STAGE VALIDATION INFO =========================

    def test_compute_stage_validation_info_no_stage(self):
        # GIVEN a chantier with no stage
        chantier = self.env['construction.chantier'].create({
            'name': 'No Stage Chantier', 'client': self.client_partner.id,
        })
        chantier.with_context(bypass_stage_validation=True).write({'stage_id': False})
        # WHEN computing validation info
        chantier._compute_stage_validation_info()
        # THEN info indicates no stage
        self.assertIn('Aucune étape', chantier.stage_validation_info)

    def test_compute_stage_validation_info_with_stage(self):
        # GIVEN a chantier in a stage
        # WHEN computing stage validation info
        self.chantier._compute_stage_validation_info()
        # THEN info is not empty
        self.assertTrue(self.chantier.stage_validation_info)

    # ========================= PREVIOUS STAGE TRANSITIONS =========================

    def test_cannot_move_previous_in_arch_chapter(self):
        # GIVEN chantier in the seed ARCH chapter (code='ARCH')
        stage_arch = self.env['construction.stage'].search(
            [('chapter_id.code', '=', 'ARCH')], order='sequence asc', limit=1
        )
        self.assertTrue(stage_arch, "Seed data must contain an ARCH chapter with at least one stage")
        self.chantier.with_context(bypass_stage_validation=True).write({'stage_id': stage_arch.id})
        # WHEN checking if previous stage move is allowed
        can_move, msg = self.chantier._can_move_to_previous_stage()
        # THEN blocked because ARCH is in BACKWARD_BLOCKED_CHAPTERS
        self.assertFalse(can_move)

    def test_cannot_move_previous_in_ret_chapter(self):
        # GIVEN chantier in the seed RET chapter (code='RET')
        stage_ret = self.env['construction.stage'].search(
            [('chapter_id.code', '=', 'RET')], order='sequence asc', limit=1
        )
        self.assertTrue(stage_ret, "Seed data must contain a RET chapter with at least one stage")
        self.chantier.with_context(bypass_stage_validation=True).write({'stage_id': stage_ret.id})
        # WHEN checking
        can_move, msg = self.chantier._can_move_to_previous_stage()
        # THEN blocked because RET is in BACKWARD_BLOCKED_CHAPTERS
        self.assertFalse(can_move)

    def test_cannot_move_previous_when_trav_progress_over_50(self):
        # GIVEN chantier in the seed TRAV chapter with progress > 50%
        stage_trav = self.env['construction.stage'].search(
            [('chapter_id.code', '=', 'TRAV')], order='sequence desc', limit=1
        )
        self.assertTrue(stage_trav, "Seed data must contain a TRAV chapter with stages")
        cat = self.env['construction.lot.category'].create({'name': 'Trav Cat', 'code': 'TRAV_CAT'})
        self.env['construction.lot'].create({
            'category_id': cat.id, 'chantier_id': self.chantier.id,
            'price': 1000.0, 'completion_percentage': 75.0,
        })
        self.chantier.with_context(bypass_stage_validation=True).write({'stage_id': stage_trav.id})
        # WHEN checking
        can_move, msg = self.chantier._can_move_to_previous_stage()
        # THEN blocked because progress (75%) > 50% in TRAV chapter
        self.assertFalse(can_move)

    def test_can_move_previous_in_normal_chapter(self):
        # GIVEN a standard chapter with two stages, chantier at stage2
        self.chantier.with_context(bypass_stage_validation=True).write({'stage_id': self.stage_da.id})
        can_move, msg = self.chantier._can_move_to_previous_stage()
        # THEN allowed (no blocking chapter, no TRAV progress constraint)
        self.assertTrue(can_move)

    # ========================= ACTION UPLOAD DOCUMENT — FALLBACK =========================

    def test_action_upload_document_fallback_when_no_wizard(self):
        # GIVEN construction_document module is NOT installed
        # (action_document_upload_wizard ref does not exist)
        # WHEN calling action_upload_document
        result = self.chantier.action_upload_document()
        # THEN returns fallback to ir.attachment form (not a crash)
        self.assertEqual(result.get('res_model'), 'ir.attachment')
