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
            'code': '01',
            'chantier_id': chantier.id,
            'price': 1000.0
        })
        
        # Second Lot (Duplicate Code) - Should Fail
        with self.assertRaises(Exception):
            self.lot_model.create({
                'name': 'Lot 1 Duplicate',
                'code': '01',
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
            'code': 'TC'
        })
        self.stage = self.env['construction.stage'].create({
            'name': 'Test Stage', 
            'code': 'TS', 
            'chapter_id': self.chapter.id
        })
        self.category = self.env['construction.lot.category'].create({
            'name': 'Électricité',
            'code': 'ELEC',
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

