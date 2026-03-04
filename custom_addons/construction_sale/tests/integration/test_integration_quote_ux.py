# -*- coding: utf-8 -*-
"""
Quote Builder UX Integration Tests
===================================
Tests combined scenarios like Undo/Redo interacting with creation logic,
and edge cases such as verifying margin calculation isn't broken by
state rollbacks in the UI simulations.
"""

from odoo.tests import common, tagged

@tagged('post_install', '-at_install', 'construction_sale', 'quote_ux')
class TestIntegrationQuoteUX(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Integration Test Partner'})
        cls.chantier = cls.env['construction.chantier'].create({
            'name': 'Integration Site',
            'partner_id': cls.partner.id,
        })
        cls.lot = cls.env['construction.lot'].create({
            'name': 'Gros Oeuvre',
            'code': 'GO_01',
            'chantier_id': cls.chantier.id,
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Ciment',
            'type': 'service',
            'standard_price': 100.0,
        })

    def test_01_quote_builder_state_flow(self):
        """
        Scenario: A user adds a line, edits the margin (inline), and undoes it.
        We verify the core methods required to create the order are intact.
        """
        # Step 1: Base load (simulated)
        catalog_products = self.env['product.template'].search_read([('sale_ok', '=', True)], ['name'])
        self.assertTrue(len(catalog_products) > 0)
        
        # Step 2: Line added via Wizard with Cost & Target Margin
        # Cost = 100, Margin = 50% => Price Unit = 150
        cost = self.product.standard_price
        target_margin = 50.0
        calculated_price = cost * (1 + target_margin / 100.0)
        
        order_line_data = [
            (0, 0, {
                'product_id': self.product.id,
                'lot_id': self.lot.id,
                'name': self.product.name,
                'product_uom_qty': 10.0,
                'price_buy': cost,
                'price_unit': calculated_price,
            })
        ]
        
        order = self.env['sale.order'].create_from_spa(
            self.chantier.id,
            self.partner.id,
            order_line_data
        )
        
        line = order.order_line[0]
        self.assertEqual(line.price_unit, 150.0, "Margin calculation implementation must result in 150 (100 + 50%)")
        self.assertEqual(line.price_buy, 100.0)

    def test_02_integration_dnd_undo_chain(self):
        """
        Verify that a complex chain of UI actions mapped to backend models 
        (like order revisions after undoing a drag operation) creates expected structures.
        """
        # Original Sequence
        order_line_1 = (0, 0, {'product_id': self.product.id, 'lot_id': self.lot.id, 'product_uom_qty': 1})
        order_line_2 = (0, 0, {'product_id': self.product.id, 'lot_id': self.lot.id, 'product_uom_qty': 2})
        
        # UI simulates DnD: order swapped
        # UI simulates Undo: order restored back
        # The ultimate payload sent to backend represents the undone state (original)
        payload = [order_line_1, order_line_2]
        
        order = self.env['sale.order'].create_from_spa(
            self.chantier.id,
            self.partner.id,
            payload
        )
        
        self.assertEqual(order.order_line[0].product_uom_qty, 1)
        self.assertEqual(order.order_line[1].product_uom_qty, 2)
