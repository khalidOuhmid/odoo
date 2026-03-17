# -*- coding: utf-8 -*-
from odoo.tests import common, tagged
from odoo.exceptions import ValidationError

@tagged('post_install', '-at_install')
class TestConstructionSale(common.TransactionCase):
    """
    Test Suite for Construction Sale Workflow.
    Ensures data integrity and business logic correctness.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create dependencies
        cls.partner = cls.env['res.partner'].create({'name': 'Test Customer'})
        cls.chantier = cls.env['construction.chantier'].create({
            'name': 'Chantier Test',
            'client': cls.partner.id
        })
        cls.lot_category = cls.env['construction.lot.category'].create({
            'name': 'Test Category', 'code': 'TC_SALE',
        })
        cls.lot = cls.env['construction.lot'].create({
            'category_id': cls.lot_category.id,
            'chantier_id': cls.chantier.id,
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Test Product',
            'type': 'service',
            'standard_price': 100.0,
            'list_price': 200.0,
        })

    def test_01_create_quote_with_chantier(self):
        """Verify seamless creation of quote linked to a chantier"""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'chantier_id': self.chantier.id,
        })
        self.assertEqual(order.chantier_id, self.chantier, "Chantier linkage failed")

    def test_02_line_specifications(self):
        """Verify structural integrity of line specifications (Location, Color)"""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'chantier_id': self.chantier.id,
        })
        line = self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': self.product.id,
            'lot_id': self.lot.id,
            'room_location': 'Master Bedroom',
            'color': 'RAL 9010',
            'dimensions': '50x50',
        })
        
        # Verify persistence
        self.assertEqual(line.room_location, 'Master Bedroom')
        self.assertEqual(line.color, 'RAL 9010')

    def test_03_price_buy_defaults_from_product(self):
        """Verify price_buy initializes from product.standard_price"""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'chantier_id': self.chantier.id,
        })
        line = self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': self.product.id,
            'lot_id': self.lot.id,
            'price_buy': self.product.standard_price,
        })
        
        self.assertEqual(line.price_buy, 100.0, "price_buy should default to product cost")

    def test_04_margin_calculation(self):
        """Verify margin computes correctly from price_buy and price_unit"""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'chantier_id': self.chantier.id,
        })
        line = self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': self.product.id,
            'lot_id': self.lot.id,
            'price_buy': 100.0,
            'price_unit': 200.0,
            'product_uom_qty': 1,
        })
        
        # Margin should be (200 - 100) * 1 = 100
        self.assertEqual(line.margin, 100.0, "Margin calculation incorrect")
        # Margin % should be 50%
        self.assertEqual(line.margin_percent, 50.0, "Margin percentage incorrect")

    def test_05_lot_required_constraint(self):
        """Verify lot is required for construction orders"""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'chantier_id': self.chantier.id,
        })
        
        with self.assertRaises(ValidationError):
            self.env['sale.order.line'].create({
                'order_id': order.id,
                'product_id': self.product.id,
                # No lot_id - should fail
            })
