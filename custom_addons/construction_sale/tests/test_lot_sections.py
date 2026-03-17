# -*- coding: utf-8 -*-
"""
Lot Section Tests (SAP-Grade)
==============================
Tests for section insertion and line resequencing by lot.

Regression tests for bugs:
- Sections not created
- Duplicate sections on re-run
- Incorrect sequence ordering
"""

from odoo.tests import common, tagged


@tagged('post_install', '-at_install', 'construction_sale', 'sections')
class TestLotSections(common.TransactionCase):
    """
    Integration tests for lot section insertion.
    
    Verifies:
    - One section per lot is created
    - Sections have display_type='line_section'
    - Correct BLG naming format: === CODE - NAME ===
    - Lines are correctly sequenced
    - No duplicates on re-run
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Test Partner Sections'})
        cls.chantier = cls.env['construction.chantier'].create({
            'name': 'Section Test Site',
            'client': cls.partner.id,
        })

        LotCat = cls.env['construction.lot.category']
        cls.cat_plumb = LotCat.create({'name': 'Plomberie Sect', 'code': 'PLB_S'})
        cls.cat_elec = LotCat.create({'name': 'Electricite Sect', 'code': 'ELC_S'})
        cls.cat_paint = LotCat.create({'name': 'Peinture Sect', 'code': 'PNT_S'})

        # Create multiple lots
        cls.lot_plumbing = cls.env['construction.lot'].create({
            'category_id': cls.cat_plumb.id,
            'chantier_id': cls.chantier.id,
        })
        cls.lot_electrical = cls.env['construction.lot'].create({
            'category_id': cls.cat_elec.id,
            'chantier_id': cls.chantier.id,
        })
        cls.lot_painting = cls.env['construction.lot'].create({
            'category_id': cls.cat_paint.id,
            'chantier_id': cls.chantier.id,
        })
        
        cls.product = cls.env['product.product'].create({
            'name': 'Test Product Sections',
            'type': 'service',
            'standard_price': 10.0,
            'list_price': 15.0,
        })

    def _create_order_with_mixed_lots(self):
        """Create order with lines across multiple lots."""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'chantier_id': self.chantier.id,
        })
        
        # Create lines in random lot order (not grouped)
        self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': self.product.id,
            'lot_id': self.lot_electrical.id,  # Lot 02
            'price_unit': 100.0,
            'product_uom_qty': 1,
        })
        self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': self.product.id,
            'lot_id': self.lot_plumbing.id,  # Lot 01
            'price_unit': 150.0,
            'product_uom_qty': 2,
        })
        self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': self.product.id,
            'lot_id': self.lot_electrical.id,  # Lot 02 again
            'price_unit': 200.0,
            'product_uom_qty': 1,
        })
        self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': self.product.id,
            'lot_id': self.lot_painting.id,  # Lot 03
            'price_unit': 50.0,
            'product_uom_qty': 5,
        })
        
        return order

    # =========================================================================
    # SECTION CREATION TESTS
    # =========================================================================

    def test_01_section_created_per_lot(self):
        """
        Verify one section is created per unique lot.
        3 different lots → 3 sections
        """
        order = self._create_order_with_mixed_lots()
        
        # Trigger resequencing
        order._resequence_lines_by_lot()
        
        # Count section lines
        sections = order.order_line.filtered(lambda l: l.display_type == 'line_section')
        
        self.assertEqual(len(sections), 3,
            msg="Should have exactly 3 sections for 3 lots")

    def test_02_section_format_blg_style(self):
        """
        Verify sections use BLG format: === CODE - NAME ===
        """
        order = self._create_order_with_mixed_lots()
        order._resequence_lines_by_lot()
        
        sections = order.order_line.filtered(lambda l: l.display_type == 'line_section')
        section_names = [s.name for s in sections]
        
        # Check format pattern
        for name in section_names:
            self.assertTrue(name.startswith('==='),
                msg=f"Section '{name}' should start with ===")
            self.assertTrue(name.endswith('==='),
                msg=f"Section '{name}' should end with ===")

    def test_03_no_duplicate_sections_on_rerun(self):
        """
        Verify rerunning resequencing doesn't create duplicate sections.
        """
        order = self._create_order_with_mixed_lots()
        
        # Run twice
        order._resequence_lines_by_lot()
        order._resequence_lines_by_lot()
        
        sections = order.order_line.filtered(lambda l: l.display_type == 'line_section')
        
        self.assertEqual(len(sections), 3,
            msg="Should still have exactly 3 sections after re-run")

    def test_04_lines_grouped_under_correct_section(self):
        """
        Verify lines are grouped under their lot's section.
        """
        order = self._create_order_with_mixed_lots()
        order._resequence_lines_by_lot()
        
        lines = order.order_line.sorted('sequence')
        
        # Track current lot context
        current_lot_section = None
        lot_to_section = {}
        
        for line in lines:
            if line.display_type == 'line_section':
                current_lot_section = line.name
            elif line.lot_id:
                # This line should be under a section matching its lot
                lot_code = line.lot_id.code
                if lot_code not in lot_to_section:
                    lot_to_section[lot_code] = current_lot_section
                    self.assertIn(lot_code, current_lot_section or '',
                        msg=f"Line should be under section containing lot code {lot_code}")

    def test_05_sequences_are_contiguous(self):
        """
        Verify sequence numbers are properly assigned.
        """
        order = self._create_order_with_mixed_lots()
        order._resequence_lines_by_lot()
        
        lines = order.order_line.sorted('sequence')
        sequences = [l.sequence for l in lines]
        
        # Sequences should be unique and ordered
        self.assertEqual(len(sequences), len(set(sequences)),
            msg="All sequences should be unique")
        
        # Verify ascending order
        for i in range(1, len(sequences)):
            self.assertGreater(sequences[i], sequences[i-1],
                msg="Sequences should be in ascending order")

    # =========================================================================
    # EDGE CASE TESTS
    # =========================================================================

    def test_06_empty_order_no_crash(self):
        """
        Verify resequencing on empty order doesn't crash.
        """
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'chantier_id': self.chantier.id,
        })
        
        # Should not raise
        order._resequence_lines_by_lot()
        
        self.assertEqual(len(order.order_line), 0,
            msg="Empty order should remain empty")

    def test_07_single_lot_single_section(self):
        """
        Order with all lines in one lot → 1 section only.
        """
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'chantier_id': self.chantier.id,
        })
        
        for i in range(3):
            self.env['sale.order.line'].create({
                'order_id': order.id,
                'product_id': self.product.id,
                'lot_id': self.lot_plumbing.id,
                'price_unit': 100.0 + i,
                'product_uom_qty': 1,
            })
        
        order._resequence_lines_by_lot()
        
        sections = order.order_line.filtered(lambda l: l.display_type == 'line_section')
        self.assertEqual(len(sections), 1,
            msg="Should have 1 section for single lot")

    def test_08_action_resequence_lines_returns_reload(self):
        """
        Verify public action returns reload client action.
        """
        order = self._create_order_with_mixed_lots()
        
        result = order.action_resequence_lines()
        
        self.assertEqual(result.get('type'), 'ir.actions.client',
            msg="Should return client action")
        self.assertEqual(result.get('tag'), 'reload',
            msg="Should trigger page reload")
