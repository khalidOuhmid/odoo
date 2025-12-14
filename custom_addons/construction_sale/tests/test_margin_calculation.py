# -*- coding: utf-8 -*-
"""
Margin Calculation Tests (SAP-Grade)
=====================================
Tests for the markup formula: price = cost × (1 + margin%)

Deterministic, isolated, no external dependencies.
"""

from odoo.tests import common, tagged


@tagged('post_install', '-at_install', 'construction_sale', 'margin')
class TestMarginCalculation(common.TransactionCase):
    """
    Unit tests for margin/markup calculations.
    
    Formula being tested: selling_price = cost × (1 + margin_percent/100)
    Examples:
        - 15€ cost, 50% margin → 22.50€
        - 15€ cost, 100% margin → 30€
        - 15€ cost, 0% margin → 15€
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Test Partner Margin'})
        cls.chantier = cls.env['construction.chantier'].create({
            'name': 'Margin Test Site',
            'partner_id': cls.partner.id,
        })
        cls.lot = cls.env['construction.lot'].create({
            'name': 'Lot Margin Test',
            'code': 'LMT01',
            'chantier_id': cls.chantier.id,
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Test Product Margin',
            'type': 'service',
            'standard_price': 15.0,  # Cost price
            'list_price': 22.50,     # Selling price with 50% markup
        })

    def _create_order_with_line(self, price_buy, price_unit):
        """Helper to create order with a single line."""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'chantier_id': self.chantier.id,
        })
        line = self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': self.product.id,
            'lot_id': self.lot.id,
            'price_buy': price_buy,
            'price_unit': price_unit,
            'product_uom_qty': 1.0,
        })
        return order, line

    # =========================================================================
    # MARKUP FORMULA TESTS
    # =========================================================================

    def test_01_markup_50_percent(self):
        """
        Test 50% markup: 15€ × 1.5 = 22.50€
        Margin = 22.50 - 15 = 7.50€
        Margin % = 7.50 / 22.50 = 33.33% (of selling price)
        """
        order, line = self._create_order_with_line(price_buy=15.0, price_unit=22.50)
        
        # Verify margin (selling - cost)
        self.assertAlmostEqual(line.margin, 7.50, places=2,
            msg="Margin should be 7.50€ (22.50 - 15.00)")
        
        # Verify margin percent (margin / selling_price * 100)
        expected_margin_pct = (7.50 / 22.50) * 100
        self.assertAlmostEqual(line.margin_percent, expected_margin_pct, places=1,
            msg="Margin percent should be ~33.33%")

    def test_02_markup_100_percent(self):
        """
        Test 100% markup: 15€ × 2.0 = 30€
        Margin = 30 - 15 = 15€
        """
        order, line = self._create_order_with_line(price_buy=15.0, price_unit=30.0)
        
        self.assertAlmostEqual(line.margin, 15.0, places=2,
            msg="Margin should be 15€ for 100% markup")
        self.assertAlmostEqual(line.margin_percent, 50.0, places=1,
            msg="Margin percent should be 50% (15/30)")

    def test_03_markup_zero_margin(self):
        """
        Test 0% markup: price == cost
        Margin = 0€
        """
        order, line = self._create_order_with_line(price_buy=15.0, price_unit=15.0)
        
        self.assertAlmostEqual(line.margin, 0.0, places=2,
            msg="Margin should be 0€ when no markup")
        self.assertAlmostEqual(line.margin_percent, 0.0, places=1,
            msg="Margin percent should be 0%")

    def test_04_high_margin_200_percent(self):
        """
        Test 200% markup: 15€ × 3.0 = 45€
        Margin = 45 - 15 = 30€
        """
        order, line = self._create_order_with_line(price_buy=15.0, price_unit=45.0)
        
        self.assertAlmostEqual(line.margin, 30.0, places=2,
            msg="Margin should be 30€ for 200% markup")

    def test_05_zero_cost_edge_case(self):
        """
        Edge case: cost = 0 should not cause division errors
        """
        order, line = self._create_order_with_line(price_buy=0.0, price_unit=20.0)
        
        self.assertAlmostEqual(line.margin, 20.0, places=2,
            msg="Margin should equal selling price when cost is 0")

    def test_06_quantity_multiplier(self):
        """
        Test margin scales with quantity: qty=3, margin=7.50 → total margin = 22.50
        """
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'chantier_id': self.chantier.id,
        })
        line = self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': self.product.id,
            'lot_id': self.lot.id,
            'price_buy': 15.0,
            'price_unit': 22.50,
            'product_uom_qty': 3.0,
        })
        
        # Total margin = (22.50 - 15.00) × 3 = 22.50
        self.assertAlmostEqual(line.margin, 22.50, places=2,
            msg="Margin should be 22.50€ for qty=3")

    def test_07_negative_margin_scenario(self):
        """
        Edge case: selling below cost (negative margin)
        Cost = 20€, Price = 15€ → Margin = -5€
        """
        order, line = self._create_order_with_line(price_buy=20.0, price_unit=15.0)
        
        self.assertAlmostEqual(line.margin, -5.0, places=2,
            msg="Margin should be negative when selling below cost")

    def test_08_decimal_precision(self):
        """
        Test decimal precision with complex values
        Cost = 12.347€, Price = 18.999€
        """
        order, line = self._create_order_with_line(price_buy=12.347, price_unit=18.999)
        
        expected_margin = 18.999 - 12.347
        self.assertAlmostEqual(line.margin, expected_margin, places=2,
            msg="Margin should handle decimal precision correctly")
