# -*- coding: utf-8 -*-
"""
Extended Tests for construction_visit — coverage des zones non couvertes.
AAA pattern, tagged post_install.
"""
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError, UserError
from odoo import fields
from datetime import timedelta


@tagged('post_install', '-at_install')
class TestVisitStateMachine(TransactionCase):
    """State machine: plan, start, complete, cancel, reset."""

    def setUp(self):
        super().setUp()
        self.env = self.env(context=dict(self.env.context, tracking_disable=True))

        client = self.env['res.partner'].create({'name': 'Client SM', 'is_company': True})
        self.chantier = self.env['construction.chantier'].create({
            'name': 'Chantier SM', 'client': client.id,
        })
        self.participant = self.env['res.partner'].create({
            'name': 'Part SM', 'email': 'part@sm.test',
        })

    def _visit(self, **kw):
        defaults = {
            'name': 'Visite SM',
            'chantier_id': self.chantier.id,
            'date': fields.Datetime.now() + timedelta(hours=36),
            'visit_type': 'follow_up',
        }
        defaults.update(kw)
        return self.env['construction.visit'].create(defaults)

    # ========================= action_plan =========================

    def test_action_plan_from_draft(self):
        # GIVEN a draft visit
        v = self._visit()
        self.assertEqual(v.state, 'draft')
        # WHEN planning
        v.action_plan()
        # THEN state is planned
        self.assertEqual(v.state, 'planned')

    def test_action_plan_from_non_draft_raises(self):
        # GIVEN a confirmed visit
        v = self._visit(participant_ids=[(6, 0, [self.participant.id])])
        v.action_confirm()
        # WHEN planning again
        # THEN ValidationError
        with self.assertRaises(ValidationError):
            v.action_plan()

    # ========================= action_start =========================

    def test_action_start_from_confirmed(self):
        # GIVEN a confirmed visit
        v = self._visit(participant_ids=[(6, 0, [self.participant.id])])
        v.action_confirm()
        # WHEN starting
        v.action_start()
        # THEN in_progress
        self.assertEqual(v.state, 'in_progress')

    def test_action_start_from_non_confirmed_raises(self):
        # GIVEN a draft visit
        v = self._visit()
        # WHEN starting from draft
        # THEN ValidationError
        with self.assertRaises(ValidationError):
            v.action_start()

    def test_action_confirm_from_planned(self):
        # GIVEN a planned visit with participants
        v = self._visit(participant_ids=[(6, 0, [self.participant.id])])
        v.action_plan()
        self.assertEqual(v.state, 'planned')
        # WHEN confirming from planned
        v.action_confirm()
        # THEN confirmed
        self.assertEqual(v.state, 'confirmed')

    # ========================= action_complete =========================

    def test_action_complete_sets_date_finished(self):
        # GIVEN a visit in in_progress
        v = self._visit(participant_ids=[(6, 0, [self.participant.id])])
        v.action_confirm()
        v.action_start()
        # WHEN completing
        result = v.action_complete()
        # THEN state=completed, date_finished set, returns reload action
        self.assertEqual(v.state, 'completed')
        self.assertTrue(v.date_finished)
        self.assertEqual(result.get('type'), 'ir.actions.client')
        self.assertEqual(result.get('tag'), 'reload')

    # ========================= action_cancel =========================

    def test_action_cancel_from_draft(self):
        # GIVEN a draft visit
        v = self._visit()
        # WHEN cancelling
        v.action_cancel()
        # THEN cancelled
        self.assertEqual(v.state, 'cancelled')

    def test_action_cancel_from_confirmed(self):
        # GIVEN a confirmed visit
        v = self._visit(participant_ids=[(6, 0, [self.participant.id])])
        v.action_confirm()
        # WHEN cancelling
        v.action_cancel()
        # THEN cancelled
        self.assertEqual(v.state, 'cancelled')

    def test_action_cancel_completed_raises(self):
        # GIVEN a completed visit
        v = self._visit(participant_ids=[(6, 0, [self.participant.id])])
        v.action_confirm()
        v.action_start()
        v.action_complete()
        # WHEN cancelling
        # THEN ValidationError
        with self.assertRaises(ValidationError):
            v.action_cancel()

    # ========================= action_reset_to_draft =========================

    def test_action_reset_to_draft_clears_flags(self):
        # GIVEN a confirmed visit with notification sent
        v = self._visit(participant_ids=[(6, 0, [self.participant.id])])
        v.action_confirm()
        v.write({'notification_sent': True, 'report_generated': True, 'report_sent': True})
        # WHEN resetting
        v.action_reset_to_draft()
        # THEN draft + all flags False
        self.assertEqual(v.state, 'draft')
        self.assertFalse(v.notification_sent)
        self.assertFalse(v.report_generated)
        self.assertFalse(v.report_sent)

    # ========================= button visibility =========================

    def test_show_send_report_visibility(self):
        # GIVEN completed visit with report generated but not sent
        v = self._visit()
        v.write({'state': 'completed', 'report_generated': True, 'report_sent': False})
        v._compute_button_visibility()
        # THEN show_send_report is True
        self.assertTrue(v.show_send_report)
        # WHEN report is also sent
        v.report_sent = True
        v._compute_button_visibility()
        # THEN show_send_report is False
        self.assertFalse(v.show_send_report)

    def test_button_visibility_all_false_in_draft(self):
        # GIVEN a draft visit
        v = self._visit()
        v._compute_button_visibility()
        # THEN all buttons hidden
        self.assertFalse(v.show_send_notification)
        self.assertFalse(v.show_generate_report)
        self.assertFalse(v.show_send_report)

    # ========================= refresh_stages =========================

    def test_refresh_stages_returns_state_dict(self):
        # GIVEN a confirmed visit
        v = self._visit(participant_ids=[(6, 0, [self.participant.id])])
        v.action_confirm()
        # WHEN refreshing
        result = v.refresh_stages()
        # THEN returns dict with state key
        self.assertIn('state', result)
        self.assertEqual(result['state'], 'confirmed')
        self.assertIn('show_send_notification', result)

    # ========================= visit types =========================

    def test_visit_type_initial(self):
        v = self._visit(visit_type='initial')
        self.assertEqual(v.visit_type, 'initial')

    def test_visit_type_technical(self):
        v = self._visit(visit_type='technical')
        self.assertEqual(v.visit_type, 'technical')

    def test_visit_type_final(self):
        v = self._visit(visit_type='final')
        self.assertEqual(v.visit_type, 'final')

    # ========================= report actions =========================

    def test_action_generate_report_requires_completed_state(self):
        # GIVEN a draft visit
        v = self._visit()
        # WHEN generating report
        # THEN UserError (not completed)
        with self.assertRaises(UserError):
            v.action_generate_report()

    def test_action_send_report_no_report_raises(self):
        # GIVEN a completed visit without report
        v = self._visit(participant_ids=[(6, 0, [self.participant.id])])
        v.action_confirm()
        v.action_start()
        v.action_complete()
        v.report_generated = False
        # WHEN sending report
        # THEN UserError
        with self.assertRaises(UserError):
            v.action_send_report()

    def test_action_send_report_no_participants_raises(self):
        # GIVEN a completed visit with report but no participants
        v = self._visit()
        v.write({'state': 'completed', 'report_generated': True})
        # WHEN sending report
        # THEN UserError (no participants)
        with self.assertRaises(UserError):
            v.action_send_report()

    def test_action_send_report_no_attachment_raises(self):
        # GIVEN a completed visit with report_generated=True but no PDF attachment
        v = self._visit(participant_ids=[(6, 0, [self.participant.id])])
        v.write({'state': 'completed', 'report_generated': True})
        # WHEN sending report (no attachment found)
        # THEN UserError
        with self.assertRaises(UserError):
            v.action_send_report()

    # ========================= onchange date buffer =========================

    def test_onchange_date_buffer_warning_returned_for_soon_date(self):
        # GIVEN a virtual record (new()) — no constraint triggered, date < 24h
        v = self.env['construction.visit'].new({
            'name': 'Onchange Test',
            'chantier_id': self.chantier.id,
            'date': fields.Datetime.now() + timedelta(hours=2),
            'visit_type': 'follow_up',
        })
        # WHEN onchange fires
        result = v._onchange_date_buffer()
        # THEN returns warning dict
        self.assertIsNotNone(result)
        self.assertIn('warning', result)

    def test_onchange_date_buffer_no_warning_for_far_date(self):
        # GIVEN a virtual record with date > 24h away
        v = self.env['construction.visit'].new({
            'name': 'Onchange Far',
            'chantier_id': self.chantier.id,
            'date': fields.Datetime.now() + timedelta(days=5),
            'visit_type': 'follow_up',
        })
        # WHEN onchange fires
        result = v._onchange_date_buffer()
        # THEN no warning returned
        self.assertIsNone(result)

    # ========================= waze without address =========================

    def test_get_waze_url_empty_if_no_address(self):
        # GIVEN a visit on a chantier without address/city
        client = self.env['res.partner'].create({'name': 'Cl', 'is_company': True})
        chantier_no_addr = self.env['construction.chantier'].create({
            'name': 'No Addr', 'client': client.id,
        })
        v = self._visit(chantier_id=chantier_no_addr.id)
        # WHEN getting waze URL
        result = v.get_waze_url()
        # THEN empty string
        self.assertEqual(result, '')

    # ========================= cron =========================

    def test_cron_notifies_visits_within_48h(self):
        # GIVEN a confirmed visit within 48h with participants
        v = self._visit(
            date=fields.Datetime.now() + timedelta(hours=36),
            participant_ids=[(6, 0, [self.participant.id])],
        )
        v.action_confirm()
        self.assertFalse(v.notification_sent)
        # WHEN cron runs
        self.env['construction.visit']._cron_send_visit_notifications()
        # THEN notification sent
        self.assertTrue(v.notification_sent)

    def test_cron_skips_already_notified_visits(self):
        # GIVEN a confirmed visit already notified
        v = self._visit(
            date=fields.Datetime.now() + timedelta(hours=36),
            participant_ids=[(6, 0, [self.participant.id])],
        )
        v.action_confirm()
        v.notification_sent = True
        # WHEN cron runs
        self.env['construction.visit']._cron_send_visit_notifications()
        # THEN still True (not sent again)
        self.assertTrue(v.notification_sent)

    def test_cron_skips_visits_beyond_48h(self):
        # GIVEN a confirmed visit > 48h away
        v = self._visit(
            date=fields.Datetime.now() + timedelta(hours=72),
            participant_ids=[(6, 0, [self.participant.id])],
        )
        v.action_confirm()
        # WHEN cron runs
        self.env['construction.visit']._cron_send_visit_notifications()
        # THEN NOT notified
        self.assertFalse(v.notification_sent)


@tagged('post_install', '-at_install')
class TestChantierVisitExtension(TransactionCase):
    """Tests for chantier_extension: visit_count, actions, check_visit_stage."""

    def setUp(self):
        super().setUp()
        self.env = self.env(context=dict(self.env.context, tracking_disable=True))

        client = self.env['res.partner'].create({'name': 'Cl Ext', 'is_company': True})
        self.chantier = self.env['construction.chantier'].create({
            'name': 'Chantier Ext', 'client': client.id,
        })
        self.participant = self.env['res.partner'].create({
            'name': 'Part Ext', 'email': 'part@ext.test',
        })

    def _visit(self, **kw):
        defaults = {
            'name': 'V Ext',
            'chantier_id': self.chantier.id,
            'date': fields.Datetime.now() + timedelta(hours=36),
            'visit_type': 'follow_up',
        }
        defaults.update(kw)
        return self.env['construction.visit'].create(defaults)

    def test_visit_count_zero_initially(self):
        # GIVEN a chantier without visits
        self.assertEqual(self.chantier.visit_count, 0)

    def test_visit_count_increments_on_visit_creation(self):
        # GIVEN a chantier
        # WHEN creating a visit
        self._visit()
        # THEN visit_count = 1
        self.assertEqual(self.chantier.visit_count, 1)

    def test_visit_count_multiple(self):
        # GIVEN 3 visits
        for i in range(3):
            self._visit(name=f'V {i}', date=fields.Datetime.now() + timedelta(hours=36+i))
        # THEN count = 3
        self.assertEqual(self.chantier.visit_count, 3)

    def test_action_view_visits_returns_act_window(self):
        # GIVEN chantier
        result = self.chantier.action_view_visits()
        # THEN act_window for construction.visit
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'construction.visit')
        self.assertEqual(result['context']['default_chantier_id'], self.chantier.id)

    def test_action_plan_visit_returns_form(self):
        # GIVEN chantier
        result = self.chantier.action_plan_visit()
        # THEN form for construction.visit
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'construction.visit')
        self.assertEqual(result['view_mode'], 'form')

    def test_check_visit_stage_no_visits(self):
        # GIVEN no visits
        ok, msg = self.chantier.check_visit_stage()
        # THEN False
        self.assertFalse(ok)
        self.assertIn('visite', msg.lower())

    def test_check_visit_stage_no_completed_visit(self):
        # GIVEN a draft visit (not completed)
        self._visit()
        ok, msg = self.chantier.check_visit_stage()
        # THEN False
        self.assertFalse(ok)

    def test_check_visit_stage_with_completed_visit(self):
        # GIVEN a completed visit
        v = self._visit(participant_ids=[(6, 0, [self.participant.id])])
        v.action_confirm()
        v.action_start()
        v.action_complete()
        # WHEN checking
        ok, msg = self.chantier.check_visit_stage()
        # THEN True
        self.assertTrue(ok)
        self.assertEqual(msg, 'OK')
