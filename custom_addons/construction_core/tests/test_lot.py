# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError

class TestConstructionLot(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create common fixtures
        cls.client_partner = cls.env['res.partner'].create({
            'name': 'Client Test',
            'is_company': True,
        })
        
        cls.subcontractor = cls.env['res.partner'].create({
            'name': 'Subcontractor Test',
            'is_company': True,
            'supplier_rank': 1,
        })
        
        cls.chantier = cls.env['construction.chantier'].create({
            'name': 'Chantier Test Lots',
            'client': cls.client_partner.id,
        })
        
        cls.category = cls.env['construction.lot.category'].create({
            'name': 'Gros Oeuvre Test',
            'code': 'GO_TEST',
        })
        
        cls.lot = cls.env['construction.lot'].create({
            'name': 'Lot Test 001',
            'code': 'L01_SETUP',
            'category_id': cls.category.id,
            'chantier_id': cls.chantier.id,
            'execution_type': 'external',
        })

    def setUp(self):
        super().setUp()

    def test_unique_lot_code(self):
        # GIVEN a lot with a code
        self.lot.write({'code': 'L01_TEST'})
        
        # WHEN creating another lot with same code
        # THEN it should raise Exception (because SQL constraint raises IntegrityError)
        with self.assertRaises(Exception):
            self.env['construction.lot'].create({
                'name': 'Lot Test 002',
                'category_id': self.category.id,
                'chantier_id': self.chantier.id,
                'code': 'L01_SETUP', # Same as setup code
            })

    def test_compute_is_finished(self):
        # GIVEN a lot
        self.assertFalse(self.lot.is_finished)
        # WHEN completion reaches 100
        self.lot.write({'completion_percentage': 100})
        # THEN is_finished is True
        self.assertTrue(self.lot.is_finished)

    def test_compute_document_status(self):
        # GIVEN a lot with a subcontractor but no documents
        self.lot.write({'subcontractor_id': self.subcontractor.id})
        # WHEN checking document status
        self.lot._compute_document_status()
        # THEN status should be checked
        self.assertIn(self.lot.document_status, ['ok', 'warning', 'error'])

    def test_compute_lot_financials(self):
        # GIVEN a lot with a subcontractor
        self.lot.write({'subcontractor_id': self.subcontractor.id})
        # AND a signed contract
        self.env['construction.contract'].create({
            'name': 'Contrat Test',
            'subcontractor_id': self.subcontractor.id,
            'chantier_id': self.chantier.id,
            'lot_ids': [(4, self.lot.id)],
            'state': 'signed',
            'total_amount_ht': 1000.0,
        })
        # WHEN computing financials
        self.lot._compute_lot_financials()
        # THEN revenue should reflect the price
        # And since we didn't add PO lines, cost should be 0
        self.assertEqual(self.lot.revenue_total, self.lot.price)
        self.assertEqual(self.lot.cost_total, 0.0)

    def test_check_completion_percentage(self):
        # GIVEN a lot
        # WHEN setting completion < 0
        # THEN ValidationError
        with self.assertRaises(ValidationError):
            self.lot.write({'completion_percentage': -10})
        
        # WHEN setting > 100
        # THEN is_over_billed is true (no error)
        self.lot.write({'completion_percentage': 150})
        self.assertTrue(self.lot.is_over_billed)

    def test_action_mark_complete(self):
        # GIVEN an incomplete lot
        self.assertEqual(self.lot.completion_percentage, 0.0)
        # WHEN marking complete
        self.lot.action_mark_complete()
        # THEN completion is 100 and it is finished
        self.assertEqual(self.lot.completion_percentage, 100.0)
        self.assertTrue(self.lot.is_finished)
