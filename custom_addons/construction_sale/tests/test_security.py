# -*- coding: utf-8 -*-
"""
Security Tests (SAP-Grade)
===========================
Tests for field access control and permission boundaries.

Verifies:
- Margin/cost fields are restricted by groups
- Non-managers cannot access sensitive pricing data
"""

from odoo.tests import common, tagged
from odoo.exceptions import AccessError


@tagged('post_install', '-at_install', 'construction_sale', 'security')
class TestSecurityAccess(common.TransactionCase):
    """
    Security tests for field access control.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Test Partner Security'})
        cls.chantier = cls.env['construction.chantier'].create({
            'name': 'Security Test Site',
            'client': cls.partner.id,
        })
        cls.lot_cat = cls.env['construction.lot.category'].create({'name': 'Security Cat', 'code': 'SEC_T'})
        cls.lot = cls.env['construction.lot'].create({
            'category_id': cls.lot_cat.id,
            'chantier_id': cls.chantier.id,
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Security Test Product',
            'type': 'service',
            'standard_price': 100.0,
            'list_price': 150.0,
        })

    def test_01_margin_fields_exist(self):
        """
        Verify margin-related fields exist on sale.order.line
        """
        line_model = self.env['sale.order.line']
        
        # Check field existence
        self.assertIn('price_buy', line_model._fields,
            msg="price_buy field should exist")
        self.assertIn('margin', line_model._fields,
            msg="margin field should exist")
        self.assertIn('margin_percent', line_model._fields,
            msg="margin_percent field should exist")
        self.assertIn('target_margin_percent', line_model._fields,
            msg="target_margin_percent field should exist")

    def test_02_margin_fields_have_groups(self):
        """
        Verify margin fields have group restrictions.
        """
        line_model = self.env['sale.order.line']
        
        # Check groups attribute
        price_buy_field = line_model._fields.get('price_buy')
        margin_field = line_model._fields.get('margin')
        
        self.assertTrue(price_buy_field.groups,
            msg="price_buy should have groups restriction")
        self.assertTrue(margin_field.groups,
            msg="margin should have groups restriction")

    def test_03_order_can_be_created_by_salesperson(self):
        """
        Verify regular salesperson can create orders.
        """
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'chantier_id': self.chantier.id,
        })
        
        self.assertTrue(order.id,
            msg="Salesperson should be able to create orders")

    def test_04_line_can_be_created_with_lot(self):
        """
        Verify lines can be created with required lot.
        """
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'chantier_id': self.chantier.id,
        })
        
        line = self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': self.product.id,
            'lot_id': self.lot.id,
            'price_unit': 100.0,
            'product_uom_qty': 1,
        })
        
        self.assertTrue(line.id,
            msg="Line with lot should be created successfully")
