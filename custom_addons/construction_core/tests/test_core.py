# -*- coding: utf-8 -*-
"""
Unit Tests for Construction Core Module
"""

from odoo.tests.common import TransactionCase
from odoo.tests import tagged
from odoo.exceptions import UserError


@tagged('post_install', '-at_install')
class TestConstructionCore(TransactionCase):
    """Test cases for construction.chantier model."""

    def setUp(self):
        super(TestConstructionCore, self).setUp()
        self.env = self.env(context=dict(self.env.context, tracking_disable=True))
        self.chantier_model = self.env['construction.chantier']
        self.lot_model = self.env['construction.lot']

        self.chapter = self.env['construction.chapter'].create({
            'name': 'Test Chapter',
            'code': 'TC',
            'sequence': 1
        })
        self.stage = self.env['construction.stage'].create({
            'name': 'Test Stage',
            'code': 'TS',
            'chapter_id': self.chapter.id,
            'sequence': 1
        })
        self.test_partner = self.env['res.partner'].create({
            'name': 'Test Client',
            'email': 'test@example.com',
        })
        # P1 FIX: category_id is required on construction.lot
        self.category = self.env['construction.lot.category'].create({
            'name': 'Test Category',
            'code': 'TC_LOT',
        })

    def test_create_chantier(self):
        """Test basic chantier creation."""
        chantier = self.chantier_model.create({
            'name': 'Test Chantier',
            'client': self.test_partner.id,
            'stage_id': self.stage.id
        })
        self.assertEqual(chantier.name, 'Test Chantier')
        self.assertTrue(chantier.reference)

    def test_lot_uniqueness(self):
        """Test lot uniqueness constraint per chantier (unique category_id + chantier_id)."""
        chantier = self.chantier_model.create({
            'name': 'Test Chantier Lot',
            'client': self.test_partner.id,
            'stage_id': self.stage.id
        })

        # P1 FIX: category_id is required — lot name/code are derived from it
        self.lot_model.create({
            'category_id': self.category.id,
            'chantier_id': chantier.id,
            'price': 1000.0
        })

        # Second lot with same category on same chantier — should fail (unique constraint)
        with self.assertRaises(Exception):
            with self.env.cr.savepoint():
                self.lot_model.create({
                    'category_id': self.category.id,
                    'chantier_id': chantier.id,
                    'price': 2000.0
                })

    def test_message_new_creates_chantier(self):
        """Test chantier creation from incoming email (Mission 2)."""
        msg_dict = {
            'subject': 'Nouveau projet construction maison',
            'body': '<p>Description du projet avec <b>HTML</b> formatting</p>',
            'from': 'client@example.com',
        }

        chantier = self.chantier_model.message_new(msg_dict)

        self.assertTrue(chantier.id)
        self.assertEqual(chantier.name, 'Nouveau projet construction maison')
        self.assertIn('Description du projet', chantier.description)
        self.assertTrue(chantier.stage_id)
        self.assertTrue(chantier.client)

    def test_message_new_with_existing_partner(self):
        """Test message_new finds existing partner by email."""
        partner = self.env['res.partner'].create({
            'name': 'Existing Client',
            'email': 'existing@example.com',
        })

        msg_dict = {
            'subject': 'Project from existing client',
            'body': 'Test body',
            'from': 'existing@example.com',
        }

        chantier = self.chantier_model.message_new(msg_dict)
        self.assertEqual(chantier.client.id, partner.id)


@tagged('post_install', '-at_install')
class TestForceStageWizard(TransactionCase):
    """Test cases for force stage wizard (Mission 3)."""

    def setUp(self):
        super(TestForceStageWizard, self).setUp()
        self.env = self.env(context=dict(self.env.context, tracking_disable=True))

        self.chapter = self.env['construction.chapter'].create({
            'name': 'Test Chapter',
            'code': 'TC',
            'sequence': 1
        })
        self.stage1 = self.env['construction.stage'].create({
            'name': 'Stage 1',
            'code': 'S1',
            'chapter_id': self.chapter.id,
            'sequence': 1
        })
        self.stage2 = self.env['construction.stage'].create({
            'name': 'Stage 2',
            'code': 'S2',
            'chapter_id': self.chapter.id,
            'sequence': 2
        })
        self.partner = self.env['res.partner'].create({
            'name': 'Test Partner',
        })
        self.chantier = self.env['construction.chantier'].create({
            'name': 'Test Chantier',
            'client': self.partner.id,
            'stage_id': self.stage1.id
        })

    def test_force_stage_wizard_creates_message(self):
        """Test force stage wizard creates proper message without errors."""
        admin_group = self.env.ref('construction_core.group_construction_admin', raise_if_not_found=False)
        if admin_group:
            self.env.user.groups_id = [(4, admin_group.id)]

        wizard = self.env['construction.force.stage.wizard'].create({
            'chantier_id': self.chantier.id,
            'current_stage_id': self.stage1.id,
            'new_stage_id': self.stage2.id,
            'reason': 'Test reason for forcing stage change',
        })

        try:
            wizard.action_force_stage()
        except ValueError as e:
            if 'unsupported format character' in str(e):
                self.fail("MarkupSafe bug still present: " + str(e))
            raise

        self.assertEqual(self.chantier.stage_id.id, self.stage2.id)


@tagged('post_install', '-at_install')
class TestLotSubcontractorWizard(TransactionCase):
    """Test cases for lot subcontractor assign wizard (Mission 4)."""

    def setUp(self):
        super(TestLotSubcontractorWizard, self).setUp()
        self.env = self.env(context=dict(self.env.context, tracking_disable=True))

        self.chapter = self.env['construction.chapter'].create({
            'name': 'Test Chapter',
            'code': 'TC_SUB_TEST'
        })
        self.stage = self.env['construction.stage'].create({
            'name': 'Test Stage',
            'code': 'TS_SUB_TEST',
            'chapter_id': self.chapter.id
        })
        self.category = self.env['construction.lot.category'].create({
            'name': 'Électricité Test',
            'code': 'ELEC_TEST',
        })
        self.partner = self.env['res.partner'].create({
            'name': 'Test Client',
        })
        self.subcontractor = self.env['res.partner'].create({
            'name': 'Test Subcontractor',
            'supplier_rank': 1,
        })
        self.chantier = self.env['construction.chantier'].create({
            'name': 'Test Chantier',
            'client': self.partner.id,
            'stage_id': self.stage.id
        })

    def test_wizard_creates_lot_with_category(self):
        """Test wizard creates lot from category selection."""
        wizard = self.env['construction.lot.subcontractor.assign.wizard'].create({
            'chantier_id': self.chantier.id,
            'lot_category_id': self.category.id,
            'subcontractor_id': self.subcontractor.id,
            'create_new_lot': True,
            'lot_price': 5000.0,
        })

        wizard.action_assign()

        lot = self.env['construction.lot'].search([
            ('chantier_id', '=', self.chantier.id),
            ('category_id', '=', self.category.id)
        ])
        self.assertEqual(len(lot), 1)
        self.assertEqual(lot.subcontractor_id.id, self.subcontractor.id)
        self.assertEqual(lot.price, 5000.0)


@tagged('post_install', '-at_install')
class TestFinancialEdgeCases(TransactionCase):
    """
    HOTFIX A2: Edge case tests for financial calculations.
    Critical for production certification.
    """

    def setUp(self):
        super(TestFinancialEdgeCases, self).setUp()
        self.env = self.env(context=dict(self.env.context, tracking_disable=True))

        self.chapter = self.env['construction.chapter'].create({
            'name': 'Test Chapter',
            'code': 'TC',
            'sequence': 1
        })
        self.stage = self.env['construction.stage'].create({
            'name': 'Test Stage',
            'code': 'TS',
            'chapter_id': self.chapter.id,
            'sequence': 1
        })
        self.partner = self.env['res.partner'].create({
            'name': 'Test Client',
            'email': 'test@example.com',
        })
        self.subcontractor = self.env['res.partner'].create({
            'name': 'Test ST',
            'supplier_rank': 1,
        })
        self.chantier = self.env['construction.chantier'].create({
            'name': 'Test Financial Chantier',
            'client': self.partner.id,
            'stage_id': self.stage.id
        })
        # P1 FIX: category_id is required on construction.lot
        self.category = self.env['construction.lot.category'].create({
            'name': 'Test Fin Category',
            'code': 'TFC',
        })

    def test_margin_with_price(self):
        """
        Test A2.1: System computes margin correctly from lot price.
        When no PO lines exist, cost=0, margin=revenue=price.
        Testing cost > price requires construction_purchase (PO lines with lot_id).
        """
        lot = self.env['construction.lot'].create({
            'category_id': self.category.id,
            'chantier_id': self.chantier.id,
            'price': 1000.0,
            'execution_type': 'internal',
        })

        lot._compute_lot_financials()

        # Revenue = price, cost = 0 (no PO), margin = 100%
        self.assertEqual(lot.revenue_total, 1000.0)
        self.assertEqual(lot.cost_total, 0.0)
        self.assertEqual(lot.margin_eur, 1000.0)
        self.assertEqual(lot.margin_percent, 100.0)

    def test_division_zero(self):
        """
        Test A2.2: Division by zero handling when revenue is 0.
        Verifies margin_percent returns 0.0 instead of ZeroDivisionError.
        """
        lot = self.env['construction.lot'].create({
            'category_id': self.category.id,
            'chantier_id': self.chantier.id,
            'price': 0.0,
            'execution_type': 'internal',
        })

        lot._compute_lot_financials()

        self.assertEqual(lot.revenue_total, 0.0)
        self.assertEqual(lot.margin_percent, 0.0, "margin_percent must be 0 when revenue is 0, not ZeroDivisionError")

    def test_over_billing(self):
        """
        Test A2.3: Over-billing detection (completion > 100%).
        Verifies is_over_billed flag activates correctly.
        """
        lot = self.env['construction.lot'].create({
            'category_id': self.category.id,
            'chantier_id': self.chantier.id,
            'price': 10000.0,
            'completion_percentage': 50.0,
            'execution_type': 'internal',
        })

        self.assertFalse(lot.is_over_billed, "Should not be over-billed at 50%")
        self.assertFalse(lot.is_finished, "Should not be finished at 50%")

        lot.completion_percentage = 100.0
        lot._compute_is_finished()
        self.assertTrue(lot.is_finished, "Should be finished at 100%")
        self.assertFalse(lot.is_over_billed, "Should NOT be over-billed at exactly 100%")

        lot.completion_percentage = 115.0
        lot._compute_is_finished()
        self.assertTrue(lot.is_over_billed, "Must be over-billed when > 100%")
        self.assertTrue(lot.is_finished, "Should still be finished")

        lot._compute_weighted_value()
        self.assertGreater(lot.weighted_value, lot.price,
                           "Weighted value should exceed price when over-billed")
