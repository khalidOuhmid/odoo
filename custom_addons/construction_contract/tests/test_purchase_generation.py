# -*- coding: utf-8 -*-
from odoo.tests import tagged, TransactionCase
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare
from datetime import date

@tagged('post_install', '-at_install', 'construction_po')
class TestPurchaseGeneration(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # 1. Company
        cls.company = cls.env.company
        
        # 2. Subcontractor
        # Use simple creation to avoid field errors
        cls.subcontractor = cls.env['res.partner'].create({
            'name': 'SARL SOUS-TRAITANT',
            'is_company': True,
            'email': 'sous-traitant@example.com',
            'supplier_rank': 1,
        })
        
        # 3. Chantier
        cls.chantier = cls.env['construction.chantier'].create({
            'name': 'Chantier Test PO',
            'client': cls.env['res.partner'].create({'name': 'Client Test'}).id,
        })
        
        # 4. Lot categories (required since category_id is NOT NULL on construction.lot)
        cls.cat_elec = cls.env['construction.lot.category'].create({
            'name': 'Electricité PO', 'code': 'ELEC_PO',
        })
        cls.cat_mac = cls.env['construction.lot.category'].create({
            'name': 'Maçonnerie PO', 'code': 'MAC_PO',
        })

        # 5. Lots
        cls.lot_elec = cls.env['construction.lot'].create({
            'category_id': cls.cat_elec.id,
            'chantier_id': cls.chantier.id,
            'execution_type': 'external',
            'subcontractor_id': cls.subcontractor.id,
        })

        cls.lot_regie = cls.env['construction.lot'].create({
            'category_id': cls.cat_mac.id,
            'chantier_id': cls.chantier.id,
            'execution_type': 'internal',
        })
        
        # 5. Product
        cls.product = cls.env['product.product'].create({
            'name': 'Installation Electrique',
            'standard_price': 100.0, # Cost
            'list_price': 150.0,     # Sale Price
            'type': 'service',
        })

    def create_validated_quote(self, lot, qty=1.0, cost=100.0, margin_percent=50.0):
        # Create Quote
        order = self.env['sale.order'].create({
            'partner_id': self.chantier.client.id,
            'chantier_id': self.chantier.id,
            'company_id': self.company.id,
        })
        
        # Determine sale price from cost and margin
        # Sale = Cost / (1 - Margin%)
        price_unit = cost
        if margin_percent < 100:
             price_unit = cost / (1 - margin_percent/100)
        
        line = self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': self.product.id,
            'lot_id': lot.id,
            'product_uom_qty': qty,
            'price_buy': cost, # Field added by construction_sale
            'target_margin_percent': margin_percent, # Field added by construction_sale
            'price_unit': price_unit, # Triggers margin compute usually, but we set it explicitly
        })
        
        # Confirm Quote
        order.action_confirm()
        return order

    def test_01_nominal_po_generation(self):
        """Test standard PO generation flow with correct cost."""
        order = self.create_validated_quote(self.lot_elec, cost=100.0, margin_percent=50.0)
        
        # Add to approved devis
        self.chantier.write({'devis_ids': [(4, order.id)]})
        
        action = self.lot_elec.action_generate_purchase_order()
        
        self.assertTrue(action['res_id'], "PO should be created")
        po = self.env['purchase.order'].browse(action['res_id'])
        
        self.assertEqual(po.partner_id, self.subcontractor)
        self.assertEqual(len(po.order_line), 1)
        
        # Price should be Cost (100)
        # 100 cost, 50% margin -> 200 sell. PO should be 100.
        self.assertAlmostEqual(po.order_line.price_unit, 100.0, places=2)
        
        expected_origin = f"Chantier {self.chantier.name} - Lot {self.lot_elec.name}"
        self.assertEqual(po.origin, expected_origin)

    def test_02_regie_exclusion(self):
        with self.assertRaisesRegex(UserError, "Régie Interne"):
            self.lot_regie.action_generate_purchase_order()

    def test_03_no_subcontractor(self):
        self.lot_elec.subcontractor_id = False
        with self.assertRaisesRegex(UserError, "assigner un sous-traitant"):
            self.lot_elec.action_generate_purchase_order()

    def test_04_precision_handling(self):
        cost = 12.33
        order = self.create_validated_quote(self.lot_elec, cost=cost)
        self.chantier.write({'devis_ids': [(4, order.id)]})
        
        action = self.lot_elec.action_generate_purchase_order()
        po = self.env['purchase.order'].browse(action['res_id'])
        
        self.assertEqual(po.order_line.price_unit, 12.33)

    def test_05_explicit_devis_selection(self):
        order_a = self.create_validated_quote(self.lot_elec, cost=100.0)
        order_b = self.create_validated_quote(self.lot_elec, cost=200.0)
        
        self.chantier.write({'devis_ids': [(6, 0, [order_a.id])]})
        
        action = self.lot_elec.action_generate_purchase_order()
        po = self.env['purchase.order'].browse(action['res_id'])
        
        costs = po.order_line.mapped('price_unit')
        self.assertIn(100.0, costs)
        self.assertNotIn(200.0, costs)
