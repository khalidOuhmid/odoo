# -*- coding: utf-8 -*-
"""
Unit Tests for Construction Core Module
FAANG-level: Comprehensive coverage for critical features
"""

from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


class TestConstructionCore(TransactionCase):
    """Test cases for construction.chantier model."""

    def setUp(self):
        super(TestConstructionCore, self).setUp()
        self.chantier_model = self.env['construction.chantier']
        self.lot_model = self.env['construction.lot']
        
        # Create test master data
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
        
        # Create test partner
        self.test_partner = self.env['res.partner'].create({
            'name': 'Test Client',
            'email': 'test@example.com',
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
        """Test lot uniqueness constraint per chantier."""
        chantier = self.chantier_model.create({
            'name': 'Test Chantier Lot',
            'client': self.test_partner.id,
            'stage_id': self.stage.id
        })
        
        # First Lot
        self.lot_model.create({
            'name': 'Lot 1',
            'code': '01_TEST',
            'chantier_id': chantier.id,
            'price': 1000.0
        })
        
        # Second Lot (Duplicate Code) - Should Fail
        with self.assertRaises(Exception):
            self.lot_model.create({
                'name': 'Lot 1 Duplicate',
                'code': '01_TEST',
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
        
        # Call message_new
        chantier = self.chantier_model.message_new(msg_dict)
        
        # Verify chantier was created with correct values
        self.assertTrue(chantier.id)
        self.assertEqual(chantier.name, 'Nouveau projet construction maison')
        self.assertIn('Description du projet', chantier.description)
        # Stage should be set to first stage
        self.assertTrue(chantier.stage_id)
        # Client should be created from email
        self.assertTrue(chantier.client)

    def test_message_new_with_existing_partner(self):
        """Test message_new finds existing partner by email."""
        # Create partner first
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
        
        # Should use existing partner
        self.assertEqual(chantier.client.id, partner.id)


class TestForceStageWizard(TransactionCase):
    """Test cases for force stage wizard (Mission 3)."""

    def setUp(self):
        super(TestForceStageWizard, self).setUp()
        
        # Create master data
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
        # Grant admin access for test
        admin_group = self.env.ref('construction_core.group_construction_admin', raise_if_not_found=False)
        if admin_group:
            self.env.user.groups_id = [(4, admin_group.id)]
        
        wizard = self.env['construction.force.stage.wizard'].create({
            'chantier_id': self.chantier.id,
            'current_stage_id': self.stage1.id,
            'new_stage_id': self.stage2.id,
            'reason': 'Test reason for forcing stage change',
        })
        
        # This should not raise MarkupSafe ValueError
        try:
            wizard.action_force_stage()
        except ValueError as e:
            if 'unsupported format character' in str(e):
                self.fail("MarkupSafe bug still present: " + str(e))
            raise
        
        # Verify stage was changed
        self.assertEqual(self.chantier.stage_id.id, self.stage2.id)


class TestLotSubcontractorWizard(TransactionCase):
    """Test cases for lot subcontractor assign wizard (Mission 4)."""

    def setUp(self):
        super(TestLotSubcontractorWizard, self).setUp()
        
        # Create master data
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
        
        # Verify lot was created
        lot = self.env['construction.lot'].search([
            ('chantier_id', '=', self.chantier.id),
            ('category_id', '=', self.category.id)
        ])
        self.assertEqual(len(lot), 1)
        self.assertEqual(lot.name, 'Électricité')
        self.assertEqual(lot.subcontractor_id.id, self.subcontractor.id)
        self.assertEqual(lot.price, 5000.0)


class TestFinancialEdgeCases(TransactionCase):
    """
    HOTFIX A2: Edge case tests for financial calculations.
    Critical for production certification.
    """

    def setUp(self):
        super(TestFinancialEdgeCases, self).setUp()
        
        # Create master data
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

    def test_negative_margin(self):
        """
        Test A2.1: System handles negative margin (cost > price) without crash.
        Scenario: Lot sold at 1000€ but cost is 1500€ → margin = -500€
        """
        lot = self.env['construction.lot'].create({
            'name': 'Lot Marge Négative',
            'code': 'NEG01',
            'chantier_id': self.chantier.id,
            'price': 1000.0,  # Revenue
            'execution_type': 'external',
            'subcontractor_id': self.subcontractor.id,
        })
        
        # Simulate cost > revenue by setting revenue_total and cost_total
        # In real scenario, cost comes from PO lines. We test the compute logic directly.
        lot.revenue_total = 1000.0
        lot.cost_total = 1500.0  # This would be computed from PO lines
        
        # Manually trigger financial compute (since fields are computed)
        lot._compute_lot_financials()
        
        # Assertions: No crash, margin is negative
        self.assertEqual(lot.margin_eur, -500.0, "Margin should be negative when cost > revenue")
        self.assertLess(lot.margin_percent, 0, "Margin percent should be negative")

    def test_division_zero(self):
        """
        Test A2.2: Division by zero handling when revenue is 0.
        Verifies margin_percent returns 0.0 instead of ZeroDivisionError.
        """
        lot = self.env['construction.lot'].create({
            'name': 'Lot Prix Zero',
            'code': 'ZERO01',
            'chantier_id': self.chantier.id,
            'price': 0.0,  # Zero revenue!
            'execution_type': 'internal',
        })
        
        # Trigger compute
        lot._compute_lot_financials()
        
        # Assertions: No crash, margin_percent is 0
        self.assertEqual(lot.revenue_total, 0.0)
        self.assertEqual(lot.margin_percent, 0.0, "margin_percent must be 0 when revenue is 0, not error")

    def test_over_billing(self):
        """
        Test A2.3: Over-billing detection (completion > 100%).
        Verifies is_over_billed flag activates correctly.
        """
        lot = self.env['construction.lot'].create({
            'name': 'Lot Surfacturation',
            'code': 'OVER01',
            'chantier_id': self.chantier.id,
            'price': 10000.0,
            'completion_percentage': 50.0,  # Start at 50%
            'execution_type': 'internal',
        })
        
        # Initially not over-billed
        self.assertFalse(lot.is_over_billed, "Should not be over-billed at 50%")
        self.assertFalse(lot.is_finished, "Should not be finished at 50%")
        
        # Set to exactly 100%
        lot.completion_percentage = 100.0
        lot._compute_is_finished()
        self.assertTrue(lot.is_finished, "Should be finished at 100%")
        self.assertFalse(lot.is_over_billed, "Should NOT be over-billed at exactly 100%")
        
        # Set to 115% (over-billing)
        lot.completion_percentage = 115.0
        lot._compute_is_finished()
        self.assertTrue(lot.is_over_billed, "Must be over-billed when > 100%")
        self.assertTrue(lot.is_finished, "Should still be finished")
        
        # Verify weighted value exceeds price (financial impact)
        lot._compute_weighted_value()
        self.assertGreater(lot.weighted_value, lot.price, 
                          "Weighted value should exceed price when over-billed")
