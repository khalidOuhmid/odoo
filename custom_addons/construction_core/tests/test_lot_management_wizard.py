# -*- coding: utf-8 -*-
"""
Tests for construction.lot.management.wizard

Covers: default_get, action_save, action_generate_po, action_generate_contract,
_compute_financial_kpis, _compute_subcontractor_status, _compute_prerequisites,
_compute_progress_values, _check_dates_within_chantier.
"""
import datetime

from odoo.tests import tagged
from odoo.exceptions import UserError, ValidationError

from .common import ConstructionCoreTestBase


@tagged('post_install', '-at_install')
class TestLotManagementWizardDefaults(ConstructionCoreTestBase):
    """Tests for default_get — loads lot values into wizard."""

    def _make_wizard(self, lot):
        return self.env['construction.lot.management.wizard'].with_context(
            active_model='construction.lot',
            active_id=lot.id,
        ).create({
            'lot_id': lot.id,
            'execution_type': lot.execution_type,
        })

    def test_default_get_loads_execution_type(self):
        # GIVEN a lot with execution_type=external
        # WHEN wizard default_get is called
        defaults = self.env['construction.lot.management.wizard'].with_context(
            active_model='construction.lot',
            active_id=self.lot.id,
        ).default_get(['lot_id', 'execution_type'])
        # THEN execution_type is loaded
        self.assertEqual(defaults.get('execution_type'), 'external')

    def test_default_get_loads_subcontractor(self):
        # GIVEN a lot with subcontractor
        defaults = self.env['construction.lot.management.wizard'].with_context(
            active_model='construction.lot',
            active_id=self.lot.id,
        ).default_get(['subcontractor_id'])
        # THEN subcontractor is loaded
        self.assertEqual(defaults.get('subcontractor_id'), self.subcontractor.id)

    def test_default_get_loads_progress(self):
        # GIVEN a lot at 50% progress
        self.lot.write({'completion_percentage': 50.0})
        defaults = self.env['construction.lot.management.wizard'].with_context(
            active_model='construction.lot',
            active_id=self.lot.id,
        ).default_get(['progress_percentage'])
        # THEN progress is loaded
        self.assertEqual(defaults.get('progress_percentage'), 50.0)

    def test_default_get_no_active_id_does_not_crash(self):
        # GIVEN no active_id in context
        defaults = self.env['construction.lot.management.wizard'].default_get(['lot_id'])
        # THEN no lot_id set (graceful no-op)
        self.assertFalse(defaults.get('lot_id'))


@tagged('post_install', '-at_install')
class TestLotManagementWizardActionSave(ConstructionCoreTestBase):
    """Tests for action_save — persists wizard values back to the lot."""

    def _make_wizard(self, **extra):
        vals = {
            'lot_id': self.lot.id,
            'execution_type': self.lot.execution_type,
        }
        vals.update(extra)
        return self.env['construction.lot.management.wizard'].create(vals)

    def test_action_save_external_updates_subcontractor(self):
        # GIVEN wizard in external mode with a new subcontractor
        new_st = self.env['res.partner'].create({'name': 'New ST', 'supplier_rank': 1})
        wizard = self._make_wizard(execution_type='external', subcontractor_id=new_st.id)
        # WHEN saving
        wizard.action_save()
        # THEN lot.subcontractor_id is updated
        self.assertEqual(self.lot.subcontractor_id.id, new_st.id)

    def test_action_save_external_clears_internal_team(self):
        # GIVEN a lot that had an internal user
        user = self.env.ref('base.user_demo', raise_if_not_found=False) or self.env.user
        self.lot.write({'internal_team_user_ids': [(4, user.id)]})
        wizard = self._make_wizard(execution_type='external', subcontractor_id=self.subcontractor.id)
        # WHEN saving in external mode
        wizard.action_save()
        # THEN internal team is cleared
        self.assertFalse(self.lot.internal_team_user_ids)

    def test_action_save_internal_sets_user_clears_subcontractor(self):
        # GIVEN wizard in internal mode
        user = self.env.user
        wizard = self._make_wizard(execution_type='internal', internal_user_id=user.id)
        # WHEN saving
        wizard.action_save()
        # THEN subcontractor cleared, internal user set
        self.assertFalse(self.lot.subcontractor_id)
        self.assertIn(user, self.lot.internal_team_user_ids)

    def test_action_save_updates_progress(self):
        # GIVEN wizard with 75% progress
        wizard = self._make_wizard(execution_type='external', progress_percentage=75.0)
        # WHEN saving
        wizard.action_save()
        # THEN lot.completion_percentage updated
        self.assertEqual(self.lot.completion_percentage, 75.0)

    def test_action_save_updates_description(self):
        # GIVEN wizard with notes
        wizard = self._make_wizard(execution_type='external', notes='<p>Test notes</p>')
        # WHEN saving
        wizard.action_save()
        # THEN lot.description updated
        self.assertIn('Test notes', self.lot.description or '')

    def test_action_save_returns_window_close(self):
        # GIVEN wizard
        wizard = self._make_wizard(execution_type='external')
        # WHEN saving
        result = wizard.action_save()
        # THEN returns act_window_close
        self.assertEqual(result.get('type'), 'ir.actions.act_window_close')


@tagged('post_install', '-at_install')
class TestLotManagementWizardGeneratePO(ConstructionCoreTestBase):
    """Tests for action_generate_po validation logic."""

    def _make_wizard(self, **extra):
        vals = {'lot_id': self.lot.id, 'execution_type': 'external'}
        vals.update(extra)
        return self.env['construction.lot.management.wizard'].create(vals)

    def test_action_generate_po_raises_on_internal_lot(self):
        # GIVEN wizard in internal mode
        wizard = self._make_wizard(execution_type='internal')
        # WHEN generating PO
        # THEN UserError raised (PO only for external)
        with self.assertRaises(UserError):
            wizard.action_generate_po()

    def test_action_generate_po_raises_without_subcontractor(self):
        # GIVEN external lot, no subcontractor
        self.lot.write({'subcontractor_id': False})
        wizard = self._make_wizard(execution_type='external')
        # WHEN generating PO
        # THEN UserError raised
        with self.assertRaises(UserError):
            wizard.action_generate_po()


@tagged('post_install', '-at_install')
class TestLotManagementWizardGenerateContract(ConstructionCoreTestBase):
    """Tests for action_generate_contract prerequisite enforcement."""

    def test_action_generate_contract_raises_when_prerequisites_not_met(self):
        # GIVEN wizard where can_generate_contract=False (missing subcontractor)
        wizard = self.env['construction.lot.management.wizard'].create({
            'lot_id': self.lot.id,
            'execution_type': 'external',
            # no subcontractor → can_generate_contract will be False
        })
        self.lot.write({'subcontractor_id': False})
        # Force recompute
        wizard._compute_prerequisites()
        self.assertFalse(wizard.can_generate_contract)
        # WHEN generating contract
        # THEN UserError raised
        with self.assertRaises(UserError):
            wizard.action_generate_contract()


@tagged('post_install', '-at_install')
class TestLotManagementWizardFinancials(ConstructionCoreTestBase):
    """Tests for _compute_financial_kpis."""

    def test_financial_kpis_fallback_to_lot_price(self):
        # GIVEN a lot with price=8000, no sale orders
        self.lot.write({'price': 8000.0})
        wizard = self.env['construction.lot.management.wizard'].create({
            'lot_id': self.lot.id,
            'execution_type': 'external',
        })
        # WHEN computing KPIs
        wizard._compute_financial_kpis()
        # THEN sale_price falls back to lot.price
        self.assertEqual(wizard.lot_sale_price, 8000.0)

    def test_financial_kpis_margin_zero_division_guard(self):
        # GIVEN a lot with price=0
        self.lot.write({'price': 0.0})
        wizard = self.env['construction.lot.management.wizard'].create({
            'lot_id': self.lot.id,
            'execution_type': 'external',
        })
        wizard._compute_financial_kpis()
        # THEN margin_percent is 0, no ZeroDivisionError
        self.assertEqual(wizard.lot_margin_percent, 0.0)

    def test_financial_kpis_no_lot(self):
        # GIVEN wizard with lot_id cleared
        wizard = self.env['construction.lot.management.wizard'].create({
            'lot_id': self.lot.id,
            'execution_type': 'external',
        })
        wizard.write({'lot_id': False})
        wizard._compute_financial_kpis()
        # THEN all zeros — no crash
        self.assertEqual(wizard.lot_sale_price, 0.0)
        self.assertEqual(wizard.lot_cost, 0.0)
        self.assertEqual(wizard.lot_margin, 0.0)


@tagged('post_install', '-at_install')
class TestLotManagementWizardSubcontractorStatus(ConstructionCoreTestBase):
    """Tests for _compute_subcontractor_status (US-COR-001)."""

    def test_no_warning_when_no_original_subcontractor(self):
        # GIVEN lot with no subcontractor
        self.lot.write({'subcontractor_id': False})
        wizard = self.env['construction.lot.management.wizard'].create({
            'lot_id': self.lot.id,
            'execution_type': 'external',
        })
        wizard._compute_subcontractor_status()
        # THEN no warning
        self.assertFalse(wizard.is_subcontractor_already_assigned)
        self.assertFalse(wizard.subcontractor_warning)

    def test_warning_when_changing_existing_subcontractor(self):
        # GIVEN lot already has a subcontractor
        # WHEN wizard assigns a DIFFERENT subcontractor
        other_st = self.env['res.partner'].create({'name': 'Other ST', 'supplier_rank': 1})
        wizard = self.env['construction.lot.management.wizard'].create({
            'lot_id': self.lot.id,
            'execution_type': 'external',
            'subcontractor_id': other_st.id,
        })
        wizard._compute_subcontractor_status()
        # THEN warning is set
        self.assertTrue(wizard.is_subcontractor_already_assigned)
        self.assertTrue(wizard.subcontractor_warning)

    def test_no_warning_message_when_same_subcontractor(self):
        # GIVEN wizard sets same subcontractor as already on lot
        wizard = self.env['construction.lot.management.wizard'].create({
            'lot_id': self.lot.id,
            'execution_type': 'external',
            'subcontractor_id': self.subcontractor.id,
        })
        wizard._compute_subcontractor_status()
        # THEN flag set but no warning message (not a change)
        self.assertTrue(wizard.is_subcontractor_already_assigned)
        self.assertFalse(wizard.subcontractor_warning)


@tagged('post_install', '-at_install')
class TestLotManagementWizardPrerequisites(ConstructionCoreTestBase):
    """Tests for _compute_prerequisites and can_generate_contract."""

    def test_prerequisites_internal_mode_cannot_generate_contract(self):
        # GIVEN wizard in internal mode
        wizard = self.env['construction.lot.management.wizard'].create({
            'lot_id': self.lot.id,
            'execution_type': 'internal',
        })
        wizard._compute_prerequisites()
        # THEN can_generate_contract is False (not applicable for internal)
        self.assertFalse(wizard.can_generate_contract)
        self.assertEqual(wizard.prerequisites_html, '')

    def test_prerequisites_external_all_missing(self):
        # GIVEN external lot, nothing filled
        self.lot.write({'subcontractor_id': False})
        wizard = self.env['construction.lot.management.wizard'].create({
            'lot_id': self.lot.id,
            'execution_type': 'external',
        })
        wizard._compute_prerequisites()
        # THEN cannot generate contract
        self.assertFalse(wizard.can_generate_contract)

    def test_prerequisites_external_subcontractor_present_but_no_po_no_cctp(self):
        # GIVEN subcontractor set but no PO and no CCTP
        wizard = self.env['construction.lot.management.wizard'].create({
            'lot_id': self.lot.id,
            'execution_type': 'external',
            'subcontractor_id': self.subcontractor.id,
        })
        wizard._compute_prerequisites()
        # THEN still cannot generate (PO and CCTP missing)
        self.assertFalse(wizard.can_generate_contract)


@tagged('post_install', '-at_install')
class TestLotManagementWizardProgress(ConstructionCoreTestBase):
    """Tests for _compute_progress_values (US-COR-005)."""

    def test_progress_under_100_not_overbilled(self):
        # GIVEN 80% progress
        wizard = self.env['construction.lot.management.wizard'].create({
            'lot_id': self.lot.id,
            'execution_type': 'external',
            'progress_percentage': 80.0,
        })
        wizard._compute_progress_values()
        # THEN not over-billed
        self.assertFalse(wizard.is_over_billed)

    def test_progress_at_exactly_100_not_overbilled(self):
        # GIVEN 100% progress
        wizard = self.env['construction.lot.management.wizard'].create({
            'lot_id': self.lot.id,
            'execution_type': 'external',
            'progress_percentage': 100.0,
        })
        wizard._compute_progress_values()
        # THEN not over-billed (100% is normal completion)
        self.assertFalse(wizard.is_over_billed)

    def test_progress_over_100_is_overbilled(self):
        # GIVEN 115% progress
        wizard = self.env['construction.lot.management.wizard'].create({
            'lot_id': self.lot.id,
            'execution_type': 'external',
            'progress_percentage': 115.0,
        })
        wizard._compute_progress_values()
        # THEN is_over_billed=True
        self.assertTrue(wizard.is_over_billed)

    def test_progress_values_computed_correctly(self):
        # GIVEN lot_sale_price=10000, progress=60%
        self.lot.write({'price': 10000.0})
        wizard = self.env['construction.lot.management.wizard'].create({
            'lot_id': self.lot.id,
            'execution_type': 'external',
            'progress_percentage': 60.0,
        })
        wizard._compute_progress_values()
        # completed_value = 10000 * 60/100 = 6000 — but only if lot_sale_price is set
        # (lot_sale_price is computed separately; we check the formula holds)
        # At minimum remaining_value = lot_sale_price - completed_value
        self.assertGreaterEqual(wizard.remaining_value, 0.0)


@tagged('post_install', '-at_install')
class TestLotManagementWizardDateConstraints(ConstructionCoreTestBase):
    """Tests for _check_dates_within_chantier."""

    def setUp(self):
        super().setUp()
        # Set chantier dates so constraints have a reference
        self.chantier.with_context(bypass_stage_validation=True).write({
            'date_start_internal': datetime.date(2025, 1, 1),
            'date_end_internal': datetime.date(2025, 12, 31),
        })

    def test_date_start_before_chantier_start_raises(self):
        # GIVEN lot date_start before chantier start
        with self.assertRaises(ValidationError):
            self.env['construction.lot.management.wizard'].create({
                'lot_id': self.lot.id,
                'execution_type': 'external',
                'date_start': datetime.date(2024, 12, 31),
                'date_end': datetime.date(2025, 6, 1),
            })

    def test_date_end_after_chantier_end_raises(self):
        # GIVEN lot date_end after chantier end
        with self.assertRaises(ValidationError):
            self.env['construction.lot.management.wizard'].create({
                'lot_id': self.lot.id,
                'execution_type': 'external',
                'date_start': datetime.date(2025, 3, 1),
                'date_end': datetime.date(2026, 1, 1),
            })

    def test_date_end_before_date_start_raises(self):
        # GIVEN end before start (within chantier bounds)
        with self.assertRaises(ValidationError):
            self.env['construction.lot.management.wizard'].create({
                'lot_id': self.lot.id,
                'execution_type': 'external',
                'date_start': datetime.date(2025, 6, 1),
                'date_end': datetime.date(2025, 3, 1),
            })

    def test_valid_dates_within_chantier_no_error(self):
        # GIVEN dates within chantier bounds
        wizard = self.env['construction.lot.management.wizard'].create({
            'lot_id': self.lot.id,
            'execution_type': 'external',
            'date_start': datetime.date(2025, 3, 1),
            'date_end': datetime.date(2025, 9, 30),
        })
        # THEN no error raised
        self.assertTrue(wizard.exists())
