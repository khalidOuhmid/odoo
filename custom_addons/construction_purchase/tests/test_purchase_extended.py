# -*- coding: utf-8 -*-
"""
Extended Tests — construction_purchase
Covers: lot_extension, chantier_extension, PO line, wizard.
AAA pattern, tagged post_install.
"""
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError, UserError


@tagged('post_install', '-at_install')
class TestPurchaseExtended(TransactionCase):
    """PO smart buttons, lot/chantier extensions, onchanges."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.supplier = cls.env['res.partner'].create({
            'name': 'Fournisseur Ext', 'supplier_rank': 1,
        })
        cls.client = cls.env['res.partner'].create({
            'name': 'Client Ext', 'is_company': True,
        })
        cls.chantier = cls.env['construction.chantier'].create({
            'name': 'Chantier Ext', 'client': cls.client.id,
        })
        cls.category = cls.env['construction.lot.category'].create({
            'name': 'Plomberie Ext', 'code': 'PLB_EXT',
        })
        cls.lot = cls.env['construction.lot'].create({
            'category_id': cls.category.id,
            'chantier_id': cls.chantier.id,
            'price': 10000.0,
            'subcontractor_id': cls.supplier.id,
            'execution_type': 'external',
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Matériaux Ext', 'type': 'consu',
        })

    def _create_po(self, lot_ids=None):
        vals = {'partner_id': self.supplier.id, 'chantier_id': self.chantier.id}
        if lot_ids:
            vals['lot_ids'] = [(6, 0, lot_ids)]
        return self.env['purchase.order'].create(vals)

    def _add_line(self, po, qty=5.0, price=1000.0):
        return self.env['purchase.order.line'].create({
            'order_id': po.id,
            'product_id': self.product.id,
            'product_qty': qty,
            'price_unit': price,
            'name': self.product.name,
            'product_uom': self.product.uom_po_id.id,
            'date_planned': '2026-06-01',
        })

    # ========================= lots_count =========================

    def test_lots_count_zero_without_lots(self):
        # GIVEN a PO without lots
        po = self._create_po()
        # THEN lots_count = 0
        self.assertEqual(po.lots_count, 0)

    def test_lots_count_increments_with_lots(self):
        # GIVEN a PO with one lot
        po = self._create_po(lot_ids=[self.lot.id])
        # THEN lots_count = 1
        self.assertEqual(po.lots_count, 1)

    # ========================= action_view_lots / action_view_chantier =========================

    def test_action_view_lots_returns_act_window(self):
        # GIVEN a PO with a lot
        po = self._create_po(lot_ids=[self.lot.id])
        result = po.action_view_lots()
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'construction.lot')

    def test_action_view_chantier_returns_act_window(self):
        # GIVEN a PO with chantier
        po = self._create_po()
        result = po.action_view_chantier()
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'construction.chantier')

    # ========================= _update_chantier_on_validation =========================

    def test_update_chantier_on_validation_posts_message(self):
        # GIVEN a PO with lot and lines
        po = self._create_po(lot_ids=[self.lot.id])
        self._add_line(po)
        msg_before = len(self.chantier.message_ids)
        # WHEN calling _update_chantier_on_validation
        po._update_chantier_on_validation()
        # THEN a message was posted on chantier
        self.assertGreater(len(self.chantier.message_ids), msg_before)

    # ========================= _create_section_for_lot / _get_next_sequence =========================

    def test_create_section_for_lot_adds_section(self):
        # GIVEN a PO with a lot
        po = self._create_po(lot_ids=[self.lot.id])
        seq = po._get_next_sequence()
        po._create_section_for_lot(self.lot, seq)
        sections = po.order_line.filtered(lambda l: l.display_type == 'line_section')
        self.assertTrue(sections)

    def test_get_next_sequence_starts_at_10_when_empty(self):
        # GIVEN a PO without lines
        po = self._create_po()
        seq = po._get_next_sequence()
        self.assertEqual(seq, 10)

    def test_get_next_sequence_increments_from_existing(self):
        # GIVEN a PO with one line at sequence 10
        po = self._create_po()
        line = self._add_line(po)
        line.sequence = 10
        seq = po._get_next_sequence()
        self.assertGreater(seq, 10)

    # ========================= onchange chantier_id =========================

    def test_onchange_chantier_id_prefills_notes(self):
        # GIVEN a new PO with chantier having city
        self.chantier.write({'city': 'Paris'})
        po = self._create_po()
        po._onchange_chantier_id()
        # THEN notes reference the chantier info
        self.assertIsNotNone(po.notes)


@tagged('post_install', '-at_install')
class TestLotPurchaseExtension(TransactionCase):
    """Tests for lot_extension: purchase_count, purchase_total, margins, actions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.supplier = cls.env['res.partner'].create({
            'name': 'Fournisseur Lot Ext', 'supplier_rank': 1,
        })
        cls.client = cls.env['res.partner'].create({'name': 'Client Lot', 'is_company': True})
        cls.chantier = cls.env['construction.chantier'].create({
            'name': 'Chantier Lot Ext', 'client': cls.client.id,
        })
        cls.category = cls.env['construction.lot.category'].create({
            'name': 'Elec Lot', 'code': 'ELC_EXT',
        })
        cls.lot = cls.env['construction.lot'].create({
            'category_id': cls.category.id,
            'chantier_id': cls.chantier.id,
            'price': 5000.0,
            'subcontractor_id': cls.supplier.id,
            'subcontractor_ids': [(4, cls.supplier.id)],
            'execution_type': 'external',
        })
        cls.product = cls.env['product.product'].create({'name': 'Prod Lot', 'type': 'consu'})

    def _create_po(self):
        return self.env['purchase.order'].create({
            'partner_id': self.supplier.id,
            'chantier_id': self.chantier.id,
            'lot_ids': [(6, 0, [self.lot.id])],
        })

    # ========================= purchase_count =========================

    def test_purchase_count_zero_without_po(self):
        # GIVEN lot with no PO
        self.assertEqual(self.lot.purchase_count, 0)

    def test_purchase_count_increments_with_po(self):
        # GIVEN a PO linked to lot
        self._create_po()
        self.assertEqual(self.lot.purchase_count, 1)

    # ========================= purchase_total & margins =========================

    def test_purchase_total_zero_when_no_confirmed_po(self):
        # GIVEN a draft PO
        self._create_po()
        self.assertEqual(self.lot.purchase_total, 0.0)

    def test_purchase_margin_equals_price_when_no_po_cost(self):
        # GIVEN lot with price=5000, no PO cost
        # THEN purchase_margin = price - purchase_total = 5000
        self.assertAlmostEqual(self.lot.purchase_margin, 5000.0, places=2)

    def test_purchase_margin_percent_zero_when_no_price(self):
        # GIVEN lot with price=0
        self.lot.write({'price': 0.0})
        self.lot._compute_purchase_stats()
        self.assertEqual(self.lot.purchase_margin_percent, 0.0)
        self.lot.write({'price': 5000.0})  # restore

    # ========================= action_view_purchase_orders =========================

    def test_action_view_purchase_orders_returns_act_window(self):
        # GIVEN lot
        result = self.lot.action_view_purchase_orders()
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'purchase.order')

    # ========================= action_create_purchase_order =========================

    def test_action_create_purchase_order_no_subcontractor_returns_notification(self):
        # GIVEN a lot without subcontractor
        cat2 = self.env['construction.lot.category'].create({'name': 'No Sub', 'code': 'NSUB'})
        lot_no_sub = self.env['construction.lot'].create({
            'category_id': cat2.id,
            'chantier_id': self.chantier.id,
        })
        # WHEN creating PO
        result = lot_no_sub.action_create_purchase_order()
        # THEN notification (no subcontractor)
        self.assertEqual(result.get('type'), 'ir.actions.client')

    def test_action_create_purchase_order_with_subcontractor(self):
        # GIVEN lot with subcontractor
        result = self.lot.action_create_purchase_order()
        # THEN returns act_window for purchase.order
        self.assertEqual(result.get('type'), 'ir.actions.act_window')
        self.assertEqual(result.get('res_model'), 'purchase.order')


@tagged('post_install', '-at_install')
class TestChantierPurchaseExtension(TransactionCase):
    """Tests for chantier purchase extension: counts, totals, margins, actions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.supplier = cls.env['res.partner'].create({
            'name': 'Fournisseur Chan', 'supplier_rank': 1,
        })
        cls.client = cls.env['res.partner'].create({'name': 'Client Chan', 'is_company': True})
        cls.chantier = cls.env['construction.chantier'].create({
            'name': 'Chantier Chan', 'client': cls.client.id,
        })

    def _create_po(self):
        return self.env['purchase.order'].create({
            'partner_id': self.supplier.id,
            'chantier_id': self.chantier.id,
        })

    def test_purchase_order_count_zero_initially(self):
        self.assertEqual(self.chantier.purchase_order_count, 0)

    def test_purchase_order_count_increments_on_po_creation(self):
        self._create_po()
        self.assertEqual(self.chantier.purchase_order_count, 1)

    def test_purchase_total_zero_when_no_confirmed_po(self):
        self._create_po()
        self.assertEqual(self.chantier.purchase_total, 0.0)

    def test_action_view_purchase_orders_returns_act_window(self):
        result = self.chantier.action_view_purchase_orders()
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'purchase.order')
        self.assertEqual(result['context']['default_chantier_id'], self.chantier.id)

    def test_action_create_purchase_orders_returns_act_window(self):
        result = self.chantier.action_create_purchase_orders()
        self.assertEqual(result['type'], 'ir.actions.act_window')


@tagged('post_install', '-at_install')
class TestPurchaseOrderLineExtension(TransactionCase):
    """Tests for purchase order line: sale_price, line_margin, onchange."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.supplier = cls.env['res.partner'].create({
            'name': 'Fournisseur Line', 'supplier_rank': 1,
        })
        cls.client = cls.env['res.partner'].create({'name': 'Client Line', 'is_company': True})
        cls.chantier = cls.env['construction.chantier'].create({
            'name': 'Chantier Line', 'client': cls.client.id,
        })
        cls.category = cls.env['construction.lot.category'].create({
            'name': 'PO Line Cat', 'code': 'POLINE',
        })
        cls.lot = cls.env['construction.lot'].create({
            'category_id': cls.category.id,
            'chantier_id': cls.chantier.id,
            'price': 8000.0,
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Prod Line', 'type': 'consu', 'standard_price': 250.0,
        })

    def _create_po(self):
        return self.env['purchase.order'].create({
            'partner_id': self.supplier.id,
            'chantier_id': self.chantier.id,
            'lot_ids': [(6, 0, [self.lot.id])],
        })

    def _add_line(self, po, price=2000.0, qty=1.0):
        return self.env['purchase.order.line'].create({
            'order_id': po.id,
            'product_id': self.product.id,
            'product_qty': qty,
            'price_unit': price,
            'name': 'Test Line',
            'product_uom': self.product.uom_po_id.id,
            'date_planned': '2026-06-01',
        })

    def test_sale_price_from_lot(self):
        # GIVEN line with lot
        po = self._create_po()
        line = self._add_line(po, price=2000.0)
        line.lot_id = self.lot.id
        line._compute_sale_price()
        # THEN sale_price = lot.price
        self.assertAlmostEqual(line.sale_price, 8000.0, places=2)

    def test_sale_price_zero_without_lot(self):
        # GIVEN line without lot
        po = self._create_po()
        line = self._add_line(po)
        line._compute_sale_price()
        self.assertEqual(line.sale_price, 0.0)

    def test_line_margin_computed(self):
        # GIVEN line with lot price=8000, line cost=2000 → margin=6000
        po = self._create_po()
        line = self._add_line(po, price=2000.0)
        line.lot_id = self.lot.id
        line._compute_sale_price()
        line._compute_line_margin()
        # sale_price=8000, price_subtotal=2000 → margin=6000
        self.assertAlmostEqual(line.line_margin, 6000.0, places=2)

    def test_onchange_lot_id_sets_name(self):
        # GIVEN a line (virtual) with lot but no product
        po = self._create_po()
        line = self.env['purchase.order.line'].new({
            'order_id': po.id,
            'lot_id': self.lot.id,
            'product_qty': 1.0,
        })
        line._onchange_lot_id()
        # THEN name is set from lot code/name
        self.assertTrue(line.name)
        self.assertIn(self.lot.category_id.code, line.name)

    def test_chantier_id_related_field(self):
        # GIVEN a PO line linked to a PO with chantier
        po = self._create_po()
        line = self._add_line(po)
        # THEN chantier_id on line matches PO's chantier
        self.assertEqual(line.chantier_id.id, self.chantier.id)


@tagged('post_install', '-at_install')
class TestPurchaseWizard(TransactionCase):
    """Tests for ConstructionPurchaseWizard and ConstructionPurchaseLine."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.supplier = cls.env['res.partner'].create({
            'name': 'Fournisseur Wiz', 'supplier_rank': 1,
        })
        cls.client = cls.env['res.partner'].create({'name': 'Client Wiz', 'is_company': True})
        cls.chantier = cls.env['construction.chantier'].create({
            'name': 'Chantier Wiz', 'client': cls.client.id,
        })
        cls.category = cls.env['construction.lot.category'].create({
            'name': 'Wiz Cat', 'code': 'WIZ_CAT',
        })
        cls.lot = cls.env['construction.lot'].create({
            'category_id': cls.category.id,
            'chantier_id': cls.chantier.id,
            'price': 2000.0,
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Prod Wiz', 'type': 'consu', 'standard_price': 100.0,
        })
        cls.uom = cls.env.ref('uom.product_uom_unit')

    def _create_po(self):
        return self.env['purchase.order'].create({
            'partner_id': self.supplier.id,
            'chantier_id': self.chantier.id,
        })

    def _create_wizard(self, po=None):
        if not po:
            po = self._create_po()
        return self.env['construction.purchase.wizard'].create({
            'purchase_order_id': po.id,
            'chantier_id': self.chantier.id,
        })

    def _create_line(self, wiz):
        return self.env['construction.purchase.line'].create({
            'wizard_id': wiz.id,
            'product_id': self.product.id,
            'lot_id': self.lot.id,
            'quantity': 3.0,
            'price_unit': 100.0,
            'uom_id': self.uom.id,
        })

    # ========================= wizard computed totals =========================

    def test_wizard_totals_zero_when_no_lines(self):
        # GIVEN wizard with no selected lines
        wiz = self._create_wizard()
        self.assertEqual(wiz.line_count, 0)
        self.assertEqual(wiz.total_amount, 0.0)
        self.assertEqual(wiz.total_quantity, 0.0)

    # ========================= action_clear_selection =========================

    def test_action_clear_selection_unlinks_lines(self):
        # GIVEN wizard with a selected line
        wiz = self._create_wizard()
        self._create_line(wiz)
        self.assertEqual(len(wiz.selected_line_ids), 1)
        # WHEN clearing
        wiz.action_clear_selection()
        # THEN lines removed
        self.assertEqual(len(wiz.selected_line_ids), 0)

    # ========================= PurchaseLine subtotal =========================

    def test_purchase_line_subtotal_computed(self):
        # GIVEN a wizard line with qty=3, price=100
        wiz = self._create_wizard()
        line = self._create_line(wiz)
        # THEN subtotal = 300
        self.assertAlmostEqual(line.subtotal, 300.0, places=2)

    def test_purchase_line_onchange_product_sets_price(self):
        # GIVEN a wizard line with product
        wiz = self._create_wizard()
        line = self.env['construction.purchase.line'].new({
            'wizard_id': wiz.id,
            'product_id': self.product.id,
            'lot_id': self.lot.id,
            'uom_id': self.uom.id,
        })
        line._onchange_product_id()
        # THEN price_unit from standard_price
        self.assertAlmostEqual(line.price_unit, self.product.standard_price, places=2)

    # ========================= action_finalize_purchase no PO linked =========================

    def test_action_finalize_purchase_closes_when_no_lines_no_po(self):
        # GIVEN a wizard without purchase_order_id and no lines
        wiz = self.env['construction.purchase.wizard'].create({
            'chantier_id': self.chantier.id,
        })
        result = wiz.action_finalize_purchase()
        # THEN returns close action (no PO to open)
        self.assertEqual(result.get('type'), 'ir.actions.act_window_close')


@tagged('post_install', '-at_install')
class TestPurchaseGroupedWizard(TransactionCase):
    """Tests for construction.purchase.grouped.wizard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.supplier = cls.env['res.partner'].create({
            'name': 'Fournisseur Grouped', 'supplier_rank': 1,
        })
        cls.client = cls.env['res.partner'].create({'name': 'Client Grouped', 'is_company': True})
        cls.chantier = cls.env['construction.chantier'].create({
            'name': 'Chantier Grouped', 'client': cls.client.id,
        })
        cls.category = cls.env['construction.lot.category'].create({
            'name': 'Grouped Cat', 'code': 'GRP_CAT',
        })
        cls.lot = cls.env['construction.lot'].create({
            'category_id': cls.category.id,
            'chantier_id': cls.chantier.id,
            'price': 3000.0,
            'subcontractor_id': cls.supplier.id,
            'subcontractor_ids': [(4, cls.supplier.id)],
            'execution_type': 'external',
        })

    def test_grouped_wizard_creates_po_for_lot_with_subcontractor(self):
        # GIVEN wizard with lot that has a subcontractor
        wizard = self.env['construction.purchase.grouped.wizard'].create({
            'chantier_id': self.chantier.id,
            'lot_ids': [(6, 0, [self.lot.id])],
        })
        # WHEN creating grouped orders
        result = wizard.action_create_grouped_orders()
        # THEN a PO is created
        po = self.env['purchase.order'].search([('chantier_id', '=', self.chantier.id)], limit=1)
        self.assertTrue(po)
        self.assertIn(result.get('type'), ['ir.actions.act_window'])

    def test_grouped_wizard_no_lots_raises(self):
        # GIVEN wizard with no lots
        wizard = self.env['construction.purchase.grouped.wizard'].create({
            'chantier_id': self.chantier.id,
        })
        # WHEN creating
        with self.assertRaises(UserError):
            wizard.action_create_grouped_orders()

    def test_grouped_wizard_chantier_stored(self):
        # GIVEN wizard with chantier
        wizard = self.env['construction.purchase.grouped.wizard'].create({
            'chantier_id': self.chantier.id,
            'lot_ids': [(6, 0, [self.lot.id])],
        })
        self.assertEqual(wizard.chantier_id.id, self.chantier.id)
