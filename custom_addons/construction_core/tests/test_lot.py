# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.tests import tagged
from odoo.exceptions import UserError, ValidationError
from psycopg2 import IntegrityError
import datetime


@tagged('post_install', '-at_install')
class TestConstructionLot(TransactionCase):

    def setUp(self):
        super().setUp()
        self.env = self.env(context=dict(self.env.context, tracking_disable=True))

        self.client_partner = self.env['res.partner'].create({
            'name': 'Client Test', 'is_company': True,
        })
        self.subcontractor = self.env['res.partner'].create({
            'name': 'Subcontractor Test', 'is_company': True, 'supplier_rank': 1,
        })
        self.chantier = self.env['construction.chantier'].create({
            'name': 'Chantier Test Lots', 'client': self.client_partner.id,
        })
        self.category = self.env['construction.lot.category'].create({
            'name': 'Gros Oeuvre Test', 'code': 'GO_TEST',
        })
        self.lot = self.env['construction.lot'].create({
            'category_id': self.category.id,
            'chantier_id': self.chantier.id,
            'execution_type': 'external',
        })

    # ========================= UNIQUENESS =========================

    def test_unique_lot_code(self):
        # GIVEN a lot with a category already assigned to a chantier
        # WHEN creating another lot with same category on same chantier
        # THEN SQL unique constraint raises IntegrityError
        with self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.env['construction.lot'].create({
                    'category_id': self.category.id,
                    'chantier_id': self.chantier.id,
                })

    # ========================= IS FINISHED / OVER BILLED =========================

    def test_compute_is_finished_false_at_zero(self):
        # GIVEN a lot at 0%
        # THEN is_finished is False
        self.assertFalse(self.lot.is_finished)

    def test_compute_is_finished_true_at_100(self):
        # GIVEN a lot at 0%
        # WHEN completion reaches 100
        self.lot.write({'completion_percentage': 100})
        # THEN is_finished is True
        self.assertTrue(self.lot.is_finished)

    def test_compute_is_over_billed_at_exactly_100(self):
        # GIVEN a lot at exactly 100%
        self.lot.write({'completion_percentage': 100.0})
        self.lot._compute_is_finished()
        # THEN is_over_billed is False (exactly 100 is not over-billed)
        self.assertFalse(self.lot.is_over_billed)

    def test_compute_is_over_billed_above_100(self):
        # GIVEN a lot at 150%
        self.lot.write({'completion_percentage': 150.0})
        self.lot._compute_is_finished()
        # THEN is_over_billed is True
        self.assertTrue(self.lot.is_over_billed)

    # ========================= WEIGHTED VALUE =========================

    def test_compute_weighted_value(self):
        # GIVEN a lot with price=200 and completion=50%
        self.lot.write({'price': 200.0, 'completion_percentage': 50.0})
        # WHEN computing weighted value
        self.lot._compute_weighted_value()
        # THEN weighted_value = 200 * 0.5 = 100
        self.assertAlmostEqual(self.lot.weighted_value, 100.0, places=2)

    def test_compute_weighted_value_zero_price(self):
        # GIVEN a lot with price=0
        self.lot.write({'price': 0.0, 'completion_percentage': 75.0})
        self.lot._compute_weighted_value()
        # THEN weighted_value = 0
        self.assertAlmostEqual(self.lot.weighted_value, 0.0, places=2)

    # ========================= REMAINING VALUE =========================

    def test_compute_remaining_value(self):
        # GIVEN a lot with price=1000 and weighted_value=400
        self.lot.write({'price': 1000.0, 'completion_percentage': 40.0})
        self.lot._compute_weighted_value()
        # WHEN computing remaining value
        self.lot._compute_remaining_value()
        # THEN remaining = 1000 - 400 = 600
        self.assertAlmostEqual(self.lot.remaining_value, 600.0, places=2)

    # ========================= FINANCIALS =========================

    def test_compute_lot_financials(self):
        # GIVEN a lot with a price
        self.lot.write({'price': 5000.0})
        # WHEN computing financials
        self.lot._compute_lot_financials()
        # THEN revenue = price, cost = 0 (no PO lines), margin = price
        self.assertEqual(self.lot.revenue_total, 5000.0)
        self.assertEqual(self.lot.cost_total, 0.0)
        self.assertEqual(self.lot.margin_eur, 5000.0)

    def test_compute_lot_financials_margin_percent(self):
        # GIVEN a lot with price=1000 and no PO (cost=0)
        self.lot.write({'price': 1000.0})
        self.lot._compute_lot_financials()
        # THEN margin_percent = 100%
        self.assertAlmostEqual(self.lot.margin_percent, 100.0, places=2)

    def test_compute_lot_financials_zero_revenue(self):
        # GIVEN a lot with price=0
        self.lot.write({'price': 0.0})
        self.lot._compute_lot_financials()
        # THEN margin_percent = 0 (no division by zero)
        self.assertAlmostEqual(self.lot.margin_percent, 0.0, places=2)

    # ========================= DOCUMENT STATUS =========================

    def test_compute_document_status_internal(self):
        # GIVEN an internal lot (no documents required)
        self.lot.write({'execution_type': 'internal'})
        # WHEN computing document status
        self.lot._compute_document_status()
        # THEN status is 'ok' (internal lots don't require compliance docs)
        self.assertEqual(self.lot.document_status, 'ok')

    def test_compute_document_status_external_no_docs(self):
        # GIVEN an external lot with no CCTP and no planning
        self.lot.write({'execution_type': 'external'})
        self.lot._compute_document_status()
        # THEN status is 'error' (missing mandatory docs)
        self.assertEqual(self.lot.document_status, 'error')

    def test_compute_document_status_valid_selection(self):
        # GIVEN a lot with a subcontractor but no documents
        self.lot.write({'subcontractor_id': self.subcontractor.id})
        # WHEN checking document status
        self.lot._compute_document_status()
        # THEN status is one of the valid values
        self.assertIn(self.lot.document_status, ['ok', 'warning', 'error', 'danger'])

    # ========================= COMPLETION CONSTRAINT =========================

    def test_check_completion_percentage_negative(self):
        # GIVEN a lot
        # WHEN setting completion < 0
        # THEN ValidationError is raised
        with self.assertRaises(ValidationError):
            self.lot.write({'completion_percentage': -10})

    def test_check_completion_percentage_over_100_allowed(self):
        # GIVEN a lot
        # WHEN setting completion > 100
        # THEN is_over_billed is True (no error raised)
        self.lot.write({'completion_percentage': 150})
        self.assertTrue(self.lot.is_over_billed)

    # ========================= DATE CONSTRAINTS =========================

    def test_lot_date_start_before_chantier(self):
        # GIVEN a chantier with internal start date
        self.chantier.with_context(bypass_stage_validation=True).write({
            'date_start_internal': datetime.date(2025, 3, 1),
        })
        # WHEN lot start is before chantier start
        # THEN UserError is raised
        with self.assertRaises(UserError):
            self.lot.write({'date_start_planned': datetime.date(2025, 1, 1)})

    def test_lot_date_end_after_chantier(self):
        # GIVEN a chantier with internal end date
        self.chantier.with_context(bypass_stage_validation=True).write({
            'date_end_internal': datetime.date(2025, 6, 30),
        })
        # WHEN lot end is after chantier end
        # THEN UserError is raised
        with self.assertRaises(UserError):
            self.lot.write({'date_end_planned': datetime.date(2025, 12, 31)})

    def test_lot_date_order_invalid(self):
        # GIVEN a lot
        # WHEN end date is before start date
        # THEN ValidationError is raised
        with self.assertRaises(ValidationError):
            self.lot.write({
                'date_start_planned': datetime.date(2025, 6, 1),
                'date_end_planned': datetime.date(2025, 1, 1),
            })

    def test_lot_date_order_valid(self):
        # GIVEN valid dates (start < end)
        # WHEN writing valid date range
        self.lot.write({
            'date_start_planned': datetime.date(2025, 1, 1),
            'date_end_planned': datetime.date(2025, 6, 30),
        })
        # THEN no error and dates are saved
        self.assertEqual(self.lot.date_start_planned, datetime.date(2025, 1, 1))
        self.assertEqual(self.lot.date_end_planned, datetime.date(2025, 6, 30))

    # ========================= ACTION MARK COMPLETE =========================

    def test_action_mark_complete(self):
        # GIVEN an incomplete lot
        self.assertEqual(self.lot.completion_percentage, 0.0)
        # WHEN marking complete
        self.lot.action_mark_complete()
        # THEN completion is 100 and it is finished
        self.assertEqual(self.lot.completion_percentage, 100.0)
        self.assertTrue(self.lot.is_finished)

    # ========================= ACTION GENERATE PO SAFE =========================

    def test_action_generate_po_safe_no_module(self):
        # GIVEN purchase module not providing action_generate_purchase_order
        # (lot doesn't have that method in construction_core alone)
        # WHEN calling action_generate_po_safe
        # THEN UserError is raised
        with self.assertRaises(UserError):
            self.lot.action_generate_po_safe()

    # ========================= ACTION CREATE ADDITIONAL PO =========================

    def test_action_create_additional_po_no_subcontractor(self):
        # GIVEN a lot without subcontractor
        self.lot.write({'subcontractor_id': False})
        # WHEN creating additional PO
        # THEN UserError is raised
        with self.assertRaises(UserError):
            self.lot.action_create_additional_po()

    def test_action_create_additional_po_with_subcontractor(self):
        # GIVEN a lot with a subcontractor
        self.lot.write({'subcontractor_id': self.subcontractor.id})
        # WHEN creating additional PO
        result = self.lot.action_create_additional_po()
        # THEN returns an act_window action for purchase.order
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'purchase.order')

    # ========================= ACTION CREATE ADDITIONAL QUOTE =========================

    def test_action_create_additional_quote(self):
        # GIVEN a lot on a chantier with a client
        # WHEN creating an additional quote
        result = self.lot.action_create_additional_quote()
        # THEN returns an act_window action for sale.order
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'sale.order')
        self.assertEqual(result['context']['default_chantier_id'], self.chantier.id)

    # ========================= ACTION OPEN LOT COCKPIT =========================

    def test_action_open_lot_cockpit(self):
        # GIVEN a lot
        # WHEN opening the cockpit
        result = self.lot.action_open_lot_cockpit()
        # THEN returns act_window for construction.lot with the lot's ID
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'construction.lot')
        self.assertEqual(result['res_id'], self.lot.id)

    # ========================= ACTION VIEW DOCUMENTS =========================

    def test_action_view_documents(self):
        # GIVEN a lot
        # WHEN viewing documents
        result = self.lot.action_view_documents()
        # THEN returns act_window for ir.attachment
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'ir.attachment')

    # ========================= ACTION VIEW PURCHASE ORDERS =========================

    def test_action_view_purchase_orders(self):
        # GIVEN a lot
        # WHEN viewing purchase orders
        result = self.lot.action_view_purchase_orders()
        # THEN returns act_window for purchase.order
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'purchase.order')

    # ========================= ACTION OPEN CONTRACT =========================

    def test_action_open_contract_no_contract(self):
        # GIVEN construction.contract is installed and lot has no contract
        if 'construction.contract' not in self.env:
            self.skipTest("construction.contract not installed — contract_id field not available")
        # WHEN trying to open the contract — contract_id is False
        # THEN UserError is raised (no contract linked)
        with self.assertRaises(UserError):
            self.lot.action_open_contract()

    # ========================= ACTION VIEW RELATED DOCUMENTS =========================

    def test_action_view_related_documents(self):
        # GIVEN a lot
        # WHEN viewing related documents
        result = self.lot.action_view_related_documents()
        # THEN returns a display_notification client action
        self.assertEqual(result['type'], 'ir.actions.client')
        self.assertEqual(result['tag'], 'display_notification')

    # ========================= ONCHANGE =========================

    def test_onchange_is_finished_sets_100(self):
        # GIVEN a lot at 0% and is_finished set to True
        self.lot.completion_percentage = 0.0
        self.lot.is_finished = True
        # WHEN onchange fires
        self.lot._onchange_is_finished()
        # THEN completion is set to 100%
        self.assertEqual(self.lot.completion_percentage, 100.0)

    def test_onchange_execution_type_to_internal_clears_subcontractor(self):
        # GIVEN a lot with a subcontractor
        self.lot.subcontractor_id = self.subcontractor
        # WHEN switching to internal
        self.lot.execution_type = 'internal'
        self.lot._onchange_execution_type()
        # THEN subcontractor is cleared
        self.assertFalse(self.lot.subcontractor_id)

    def test_onchange_execution_type_to_external_clears_team(self):
        # GIVEN a lot whose execution_type is about to change to external
        # The onchange must set internal_team_user_ids = [(5, 0, 0)] → clears the field
        self.lot.write({'execution_type': 'internal'})
        # WHEN switching to external via onchange
        self.lot.execution_type = 'external'
        self.lot._onchange_execution_type()
        # THEN internal_team_user_ids is cleared (False / empty recordset)
        self.assertFalse(self.lot.internal_team_user_ids)

    # ========================= LOT CATEGORY =========================

    def test_lot_category_unique_code(self):
        # GIVEN a lot category with code 'UNIQ'
        self.env['construction.lot.category'].create({'name': 'Unique Cat', 'code': 'UNIQ_TEST'})
        # WHEN creating another with same code
        # THEN SQL constraint raises
        with self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.env['construction.lot.category'].create({'name': 'Duplicate Cat', 'code': 'UNIQ_TEST'})

    # ========================= HELPER METHODS =========================

    def test_has_validated_po_no_po(self):
        # GIVEN a lot with no PO
        # WHEN checking for validated PO
        result = self.lot._has_validated_po()
        # THEN returns False
        self.assertFalse(result)
