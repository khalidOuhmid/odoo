# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError

@tagged('post_install', '-at_install')
class TestConstructionCore(TransactionCase):

    def setUp(self):
        super(TestConstructionCore, self).setUp()
        self.Chantier = self.env['construction.chantier']
        self.Lot = self.env['construction.lot']
        
        # Create Partner
        self.partner = self.env['res.partner'].create({'name': 'Client Test'})

    def test_chantier_lifecycle(self):
        """Test the state machine of a Chantier."""
        chantier = self.Chantier.create({
            'name': 'Chantier Test',
            'partner_id': self.partner.id
        })
        self.assertEqual(chantier.state, 'draft')
        
        chantier.action_confirm_study()
        self.assertEqual(chantier.state, 'study')
        
        chantier.action_start_prep()
        self.assertEqual(chantier.state, 'prep')

    def test_lot_budget_aggregation(self):
        """Test that lot budgets aggregate to chantier."""
        chantier = self.Chantier.create({
            'name': 'Budget Chantier',
            'partner_id': self.partner.id
        })
        
        lot1 = self.Lot.create({
            'name': 'Lot 1',
            'chantier_id': chantier.id,
            'budget_amount': 1000.0
        })
        
        lot2 = self.Lot.create({
            'name': 'Lot 2',
            'chantier_id': chantier.id,
            'budget_amount': 2000.0
        })
        
        chantier.invalidate_recordset() # Refresh computed fields
        self.assertEqual(chantier.budget_total, 3000.0)
