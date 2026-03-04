# -*- coding: utf-8 -*-
"""
AAA Test Suite: construction_invoice — InvoiceSchedule & BillingStep
========================================================================
Couvre les règles métier critiques :
  - Calcul du montant de la facture selon le % d'avancement
  - Blocage si trigger_percentage non atteint
  - Annulation impossible si déjà facturé
  - Calcul amount_fixed avec marge deduite

Pattern : Arrange → Act → Assert (AAA)
Author   : Antigravity / BLG Groupe
Version  : 1.0
"""
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError
from odoo import fields


class TestInvoiceSchedule(TransactionCase):
    """Tests for construction.invoice.schedule model (trigger logic)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = cls.env['res.partner'].create({
            'name': 'Client Invoice Test', 'email': 'client.inv@blg.fr'
        })
        cls.chapter = cls.env['construction.chapter'].create({
            'name': 'Invoice Test Chapter', 'code': 'INVTCH',
        })
        cls.stage = cls.env['construction.stage'].create({
            'name': 'Invoice Test Stage', 'code': 'INVSTA', 'chapter_id': cls.chapter.id,
        })
        cls.chantier = cls.env['construction.chantier'].create({
            'name': 'Chantier InvSched AAA',
            'client': cls.client.id,
            'stage_id': cls.stage.id,
        })

    def _create_schedule(self, trigger_pct=25.0, amount_pct=25.0, state='planned',
                         is_advance=False, **kwargs):
        """Helper: create an InvoiceSchedule."""
        vals = {
            'chantier_id': self.chantier.id,
            'name': f'Échéance {trigger_pct}%',
            'trigger_percentage': trigger_pct,
            'amount_percentage': amount_pct,
            'state': state,
            'is_advance_payment': is_advance,
        }
        vals.update(kwargs)
        return self.env['construction.invoice.schedule'].create(vals)

    # ---- State machine transitions ----

    def test_action_mark_planned_sets_state(self):
        """AAA: action_mark_planned transitions state from draft to planned."""
        schedule = self._create_schedule(state='draft')
        schedule.action_mark_planned()
        self.assertEqual(schedule.state, 'planned')

    def test_action_mark_ready_fails_below_trigger(self):
        """AAA: action_mark_ready raises UserError when chantier progress < trigger%."""
        # Arrange: chantier at 0% progress, trigger at 25%
        schedule = self._create_schedule(trigger_pct=25.0, state='planned')
        self.chantier.progress = 10.0  # below trigger
        # Act & Assert
        with self.assertRaises(UserError):
            schedule.action_mark_ready()

    def test_action_mark_ready_succeeds_at_trigger(self):
        """AAA: action_mark_ready succeeds when chantier progress >= trigger%."""
        schedule = self._create_schedule(trigger_pct=25.0, state='planned')
        self.chantier.progress = 25.0
        # Act
        schedule.action_mark_ready()
        # Assert
        self.assertEqual(schedule.state, 'ready')
        self.assertTrue(schedule.is_triggered)

    def test_advance_payment_bypasses_progress_check(self):
        """AAA: is_advance_payment=True skips progress gate on action_mark_ready."""
        schedule = self._create_schedule(trigger_pct=50.0, state='planned', is_advance=True)
        self.chantier.progress = 0.0  # would normally block
        # Act — should NOT raise
        schedule.action_mark_ready()
        self.assertEqual(schedule.state, 'ready')

    def test_action_create_invoice_raises_when_not_ready(self):
        """AAA: action_create_invoice raises UserError when state != ready."""
        schedule = self._create_schedule(state='planned')
        with self.assertRaises(UserError):
            schedule.action_create_invoice()

    def test_action_cancel_raises_when_invoiced(self):
        """AAA: action_cancel raises UserError when already invoiced."""
        schedule = self._create_schedule(state='invoiced')
        # Create a fake invoice so invoice_id is set
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.client.id,
        })
        schedule.invoice_id = invoice.id
        with self.assertRaises(UserError):
            schedule.action_cancel()

    def test_action_cancel_succeeds_when_draft(self):
        """AAA: action_cancel succeeds without an invoice."""
        schedule = self._create_schedule(state='planned')
        schedule.action_cancel()
        self.assertEqual(schedule.state, 'cancelled')

    # ---- Amount fixed computation ----

    def test_amount_fixed_computed_from_chantier_total_cost(self):
        """AAA: amount_fixed = chantier.total_cost * amount_percentage / 100."""
        # Arrange: force total_cost via SQL field (normally computed from lots)
        self.chantier.total_cost = 100000.0
        schedule = self._create_schedule(amount_pct=30.0)  # 30% of 100,000 = 30,000
        schedule._compute_amount_fixed()
        self.assertAlmostEqual(schedule.amount_fixed, 30000.0, places=2)

    def test_amount_fixed_applies_margin_deduction(self):
        """AAA: amount_fixed deducts margin_percentage from the base before applying %."""
        # Arrange: base 100,000 with 10% margin → net 90,000 → 30% of 90,000 = 27,000
        self.chantier.total_cost = 100000.0
        schedule = self._create_schedule(amount_pct=30.0, margin_percentage=10.0)
        schedule._compute_amount_fixed()
        self.assertAlmostEqual(schedule.amount_fixed, 27000.0, places=2)

    # ---- Cron trigger ----

    def test_cron_marks_ready_when_progress_exceeded(self):
        """AAA: cron_check_triggers marks a planned schedule ready when threshold reached."""
        schedule = self._create_schedule(trigger_pct=25.0, state='planned')
        self.chantier.progress = 50.0
        # Act
        self.env['construction.invoice.schedule'].cron_check_triggers()
        # Assert
        self.assertEqual(schedule.state, 'ready')

    def test_cron_skips_advance_payment_schedules(self):
        """AAA: cron_check_triggers skips is_advance_payment=True schedules."""
        schedule = self._create_schedule(trigger_pct=25.0, state='planned', is_advance=True)
        self.chantier.progress = 100.0
        self.env['construction.invoice.schedule'].cron_check_triggers()
        # An advance payment should NOT be auto-triggered by the cron
        self.assertEqual(schedule.state, 'planned')
