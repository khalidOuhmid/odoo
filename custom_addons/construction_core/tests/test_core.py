# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase

class TestConstructionCore(TransactionCase):

    def setUp(self):
        super(TestConstructionCore, self).setUp()
        self.chantier_model = self.env['construction.chantier']
        self.lot_model = self.env['construction.lot']
        
        # Create test master data
        self.chapter = self.env['construction.chapter'].create({'name': 'Test Chapter', 'code': 'TC'})
        self.stage = self.env['construction.stage'].create({
            'name': 'Test Stage', 
            'code': 'TS', 
            'chapter_id': self.chapter.id
        })

    def test_create_chantier(self):
        """Test creation of Chantier"""
        chantier = self.chantier_model.create({
            'name': 'Test Chantier',
            'client': self.env.ref('base.partner_demo').id,
            'stage_id': self.stage.id
        })
        self.assertTrue(chantier.name == 'Test Chantier')
        self.assertTrue(chantier.reference)

    def test_lot_uniqueness(self):
        """Test Lot Uniqueness Constraint"""
        chantier = self.chantier_model.create({
            'name': 'Test Chantier Lot',
            'client': self.env.ref('base.partner_demo').id,
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
        with self.assertRaises(Exception): # We expect IntegrityError or ValidationError
             self.lot_model.create({
                'name': 'Lot 1 Duplicate',
                'code': '01',
                'chantier_id': chantier.id,
                'price': 2000.0
            })
