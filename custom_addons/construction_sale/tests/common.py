# construction_sale/tests/common.py
# -*- coding: utf-8 -*-
"""
TestCommon — Shared test fixtures for construction_sale.
========================================================
Creates all reusable data in setUpClass():
  - partner, chantier, lots (GO + MENU), products (brique + porte),
    lot categories, UoMs.
All tests inherit from this class.
"""

from odoo.tests import common, tagged


class TestCommon(common.TransactionCase):
    """Base test class with shared construction sale fixtures."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # ── Partner ──
        cls.partner = cls.env['res.partner'].create({
            'name': 'Client Test BTP',
            'email': 'test@btp.fr',
        })

        # ── Lot Categories (search or create to avoid unique constraint) ──
        LotCat = cls.env['construction.lot.category']
        cls.lot_cat_go = LotCat.search([('code', '=', 'GO')], limit=1)
        if not cls.lot_cat_go:
            cls.lot_cat_go = LotCat.create({'name': 'Gros Oeuvre', 'code': 'GO'})
        cls.lot_cat_menu = LotCat.search([('code', '=', 'MENU')], limit=1)
        if not cls.lot_cat_menu:
            cls.lot_cat_menu = LotCat.create({'name': 'Menuiserie', 'code': 'MENU'})

        # ── Chantier ──
        cls.chantier = cls.env['construction.chantier'].create({
            'name': 'Villa Test Bernard',
            'client': cls.partner.id,
        })

        # ── Lots (construction.lot) ──
        cls.lot_go = cls.env['construction.lot'].create({
            'name': 'Gros Oeuvre',
            'code': 'GO',
            'chantier_id': cls.chantier.id,
            'category_id': cls.lot_cat_go.id,
        })
        cls.lot_menu = cls.env['construction.lot'].create({
            'name': 'Menuiserie',
            'code': 'MENU',
            'chantier_id': cls.chantier.id,
            'category_id': cls.lot_cat_menu.id,
        })

        # ── UoMs ──
        cls.uom_unit = cls.env.ref('uom.product_uom_unit')
        cls.uom_meter = cls.env.ref('uom.product_uom_meter')
        # Try to find m² UoM
        cls.uom_m2 = cls.env['uom.uom'].search(
            [('name', 'ilike', 'm²')], limit=1
        ) or cls.env['uom.uom'].search(
            [('name', 'ilike', 'square')], limit=1
        ) or cls.uom_meter

        # ── Products ──
        cls.product_brique = cls.env['product.product'].create({
            'name': 'Brique 20cm',
            'type': 'service',
            'standard_price': 1.50,
            'list_price': 2.25,
            'uom_id': cls.uom_unit.id,
            'uom_po_id': cls.uom_unit.id,
            'lot_category_ids': [(6, 0, [cls.lot_cat_go.id])],
        })
        cls.product_porte = cls.env['product.product'].create({
            'name': 'Porte PVC',
            'type': 'service',
            'standard_price': 150.0,
            'list_price': 225.0,
            'uom_id': cls.uom_unit.id,
            'uom_po_id': cls.uom_unit.id,
            'lot_category_ids': [(6, 0, [cls.lot_cat_menu.id])],
        })

    # ── Helpers ──

    def _create_order(self, **kwargs):
        """Create a sale.order linked to the test chantier."""
        vals = {
            'partner_id': self.partner.id,
            'chantier_id': self.chantier.id,
        }
        vals.update(kwargs)
        return self.env['sale.order'].create(vals)

    def _create_line(self, order, product=None, lot=None, **kwargs):
        """Create a sale.order.line with sensible defaults."""
        vals = {
            'order_id': order.id,
            'product_id': (product or self.product_brique).id,
            'lot_id': (lot or self.lot_go).id,
            'product_uom_qty': 1.0,
            'price_unit': (product or self.product_brique).list_price,
        }
        vals.update(kwargs)
        return self.env['sale.order.line'].create(vals)
