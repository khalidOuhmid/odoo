# -*- coding: utf-8 -*-
"""
AAA Test Suite: construction_purchase
========================================
Couvre les modèles PurchaseOrderConstruction (lot coherence, margin,
order statistics) et le wizard de création groupée.

Pattern : Arrange → Act → Assert (AAA)
Author   : Antigravity / BLG Groupe
Version  : 1.0
"""
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError, UserError


class TestPurchaseOrderConstruction(TransactionCase):
    """Tests for purchase.order (construction extension)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # --- Partners ---
        cls.client = cls.env['res.partner'].create({
            'name': 'Client Purchase Test', 'email': 'client.po@blg.fr'
        })
        cls.supplier = cls.env['res.partner'].create({
            'name': 'Fournisseur BTP Test', 'supplier_rank': 1,
            'email': 'supplier.po@blg.fr'
        })
        # --- Chantier hierarchy ---
        cls.chapter = cls.env['construction.chapter'].create({
            'name': 'PO Test Chapter', 'code': 'POTCH',
        })
        cls.stage = cls.env['construction.stage'].create({
            'name': 'PO Test Stage', 'code': 'POSTA', 'chapter_id': cls.chapter.id,
        })
        cls.chantier = cls.env['construction.chantier'].create({
            'name': 'Chantier PO AAA Test',
            'client': cls.client.id,
            'stage_id': cls.stage.id,
        })
        # --- Lot ---
        cls.lot_a = cls.env['construction.lot'].create({
            'name': 'Lot Electricité PO',
            'code': 'LOTE1',
            'chantier_id': cls.chantier.id,
            'price': 20000.0,
        })

    def _create_po(self, lot_ids=None):
        """Helper: create a PO linked to the test chantier."""
        vals = {
            'partner_id': self.supplier.id,
            'chantier_id': self.chantier.id,
        }
        if lot_ids:
            vals['lot_ids'] = [(6, 0, lot_ids)]
        return self.env['purchase.order'].create(vals)

    # ---- Lot coherence constraint ----

    def test_lot_from_wrong_chantier_raises_validation_error(self):
        """AAA: Assigning a lot from another chantier must raise ValidationError."""
        # Arrange: create a foreign chantier and a lot belonging to it
        foreign_chantier = self.env['construction.chantier'].create({
            'name': 'Foreign Chantier',
            'client': self.client.id,
            'stage_id': self.stage.id,
        })
        foreign_lot = self.env['construction.lot'].create({
            'name': 'Lot Etranger',
            'code': 'LFOREI',
            'chantier_id': foreign_chantier.id,
            'price': 5000.0,
        })
        # Act & Assert
        with self.assertRaises(ValidationError):
            self._create_po(lot_ids=[foreign_lot.id])

    def test_lot_from_correct_chantier_is_valid(self):
        """AAA: A lot belonging to the same chantier must not raise any error."""
        # Arrange + Act
        po = self._create_po(lot_ids=[self.lot_a.id])
        # Assert
        self.assertTrue(po.exists())
        self.assertIn(self.lot_a, po.lot_ids)

    # ---- Order statistics ----

    def test_order_statistics_computed_correctly(self):
        """AAA: order_line_count and total_quantity are computed from product lines only."""
        # Arrange
        po = self._create_po()
        product = self.env['product.product'].create({
            'name': 'Matériaux Test', 'type': 'consu'
        })
        self.env['purchase.order.line'].create({
            'order_id': po.id, 'product_id': product.id,
            'product_qty': 10.0, 'price_unit': 500.0,
            'name': 'Matériaux', 'product_uom': product.uom_po_id.id,
            'date_planned': '2026-06-01',
        })
        # Also add a section (should NOT count)
        self.env['purchase.order.line'].create({
            'order_id': po.id, 'display_type': 'line_section', 'name': 'Section Test'
        })
        # Act
        po._compute_order_statistics()
        # Assert
        self.assertEqual(po.order_line_count, 1, "Only product lines should be counted")
        self.assertEqual(po.total_quantity, 10.0)

    # ---- Margin computation ----

    def test_margin_computed_when_lot_linked(self):
        """AAA: Margin = Lot sale price - PO total. Should be positive when sale > cost."""
        # Arrange: lot has price 20000, we'll simulate PO total = 14000 → margin = 6000
        po = self._create_po(lot_ids=[self.lot_a.id])
        # Force amount_total manually via a product line
        product = self.env['product.product'].create({'name': 'Béton test', 'type': 'consu'})
        self.env['purchase.order.line'].create({
            'order_id': po.id, 'product_id': product.id,
            'product_qty': 1.0, 'price_unit': 14000.0,
            'name': 'Béton test', 'product_uom': product.uom_po_id.id,
            'date_planned': '2026-06-01',
        })
        # Act
        po._compute_margin()
        # Assert: lot.price=20000, amount_total=14000 → margin=6000
        self.assertGreater(po.margin_amount, 0, "Margin should be positive (sale > cost)")
        self.assertGreater(po.margin_percent, 0, "Margin percent should be positive")

    def test_margin_zero_without_lots(self):
        """AAA: Without lots, margin must be 0 regardless of PO amount."""
        po = self._create_po()  # no lots
        po._compute_margin()
        self.assertEqual(po.margin_amount, 0)
        self.assertEqual(po.margin_percent, 0)

    # ---- action_add_product_wizard guards ----

    def test_wizard_raises_user_error_without_chantier(self):
        """AAA: action_add_product_wizard raises UserError when chantier is not set."""
        po = self.env['purchase.order'].create({'partner_id': self.supplier.id})
        with self.assertRaises(UserError):
            po.action_add_product_wizard()

    def test_organize_by_lots_raises_user_error_without_lots(self):
        """AAA: action_organize_by_lots raises UserError when no lots are associated."""
        po = self._create_po()  # no lots
        with self.assertRaises(UserError):
            po.action_organize_by_lots()

    # ---- section creation ----

    def test_create_lot_sections_adds_section_line(self):
        """AAA: Calling _create_lot_sections creates at least one section line per lot."""
        po = self._create_po(lot_ids=[self.lot_a.id])
        initial_line_count = len(po.order_line)
        # Act
        po._create_lot_sections()
        # Assert: at least one new section line was created
        self.assertGreater(len(po.order_line), initial_line_count,
                           "A section line should have been added for the lot")
        section_lines = po.order_line.filtered(lambda l: l.display_type == 'line_section')
        self.assertTrue(section_lines, "There should be a section line")
