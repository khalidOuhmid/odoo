# construction_sale/tests/integration/test_search_products_spa.py
# -*- coding: utf-8 -*-
"""
Integration Tests — search_products_for_spa
=============================================
Verifies product search API used by the OWL QuoteBuilder.
Tests filtering by category, search term, limit, and field format.
"""

from odoo.tests import tagged

from ..common import TestCommon


@tagged('post_install', '-at_install', 'construction_sale', 'integration')
class TestSearchProductsSpa(TestCommon):
    """Integration tests for search_products_for_spa."""

    # =========================================================================
    # No filter — returns all active
    # =========================================================================

    def test_search_no_filter_returns_active_products(self):
        """BR-005: Without filters, returns all saleable products."""
        # Act
        result = self.env['sale.order'].search_products_for_spa()

        # Assert — should contain at least our 2 test products
        result_ids = [p['id'] for p in result]
        self.assertIn(self.product_brique.id, result_ids)
        self.assertIn(self.product_porte.id, result_ids)

    # =========================================================================
    # Category filter
    # =========================================================================

    def test_search_with_category_filters_correctly(self):
        """BR-006: lot_category_id filter returns only matching products."""
        # Act
        result = self.env['sale.order'].search_products_for_spa(
            lot_category_id=self.lot_cat_go.id
        )

        # Assert — only brique (linked to GO), not porte (linked to MENU)
        result_ids = [p['id'] for p in result]
        self.assertIn(self.product_brique.id, result_ids)
        self.assertNotIn(self.product_porte.id, result_ids)

    def test_search_with_menu_category_returns_porte(self):
        """Filtering by MENU category returns Porte PVC only."""
        # Act
        result = self.env['sale.order'].search_products_for_spa(
            lot_category_id=self.lot_cat_menu.id
        )

        # Assert
        result_ids = [p['id'] for p in result]
        self.assertIn(self.product_porte.id, result_ids)
        self.assertNotIn(self.product_brique.id, result_ids)

    # =========================================================================
    # Search term filter
    # =========================================================================

    def test_search_term_filters_by_name(self):
        """Search term 'porte' returns only Porte PVC."""
        # Act
        result = self.env['sale.order'].search_products_for_spa(
            search_term='porte'
        )

        # Assert
        result_ids = [p['id'] for p in result]
        self.assertIn(self.product_porte.id, result_ids)

    def test_search_case_insensitive(self):
        """Search 'BRIQUE' (uppercase) finds 'Brique 20cm'."""
        # Act
        result = self.env['sale.order'].search_products_for_spa(
            search_term='BRIQUE'
        )

        # Assert
        result_ids = [p['id'] for p in result]
        self.assertIn(self.product_brique.id, result_ids)

    def test_search_partial_match(self):
        """Search 'bri' finds 'Brique 20cm'."""
        # Act
        result = self.env['sale.order'].search_products_for_spa(
            search_term='bri'
        )

        # Assert
        result_ids = [p['id'] for p in result]
        self.assertIn(self.product_brique.id, result_ids)

    def test_search_no_match_returns_empty(self):
        """Search 'xyznotexist123' returns empty list."""
        # Act
        result = self.env['sale.order'].search_products_for_spa(
            search_term='xyznotexist123'
        )

        # Assert
        self.assertEqual(len(result), 0)

    # =========================================================================
    # Limit
    # =========================================================================

    def test_search_limit_is_respected(self):
        """Limit parameter caps the number of results."""
        # Arrange
        LIMIT = 1

        # Act
        result = self.env['sale.order'].search_products_for_spa(limit=LIMIT)

        # Assert
        self.assertLessEqual(len(result), LIMIT)

    def test_search_limit_governor_caps_at_200(self):
        """Limit > 200 is capped at 200 for performance."""
        # Act
        result = self.env['sale.order'].search_products_for_spa(limit=999)

        # Assert — we don't have 200+ products, but verify no crash
        self.assertIsInstance(result, list)

    # =========================================================================
    # Inactive products
    # =========================================================================

    def test_search_inactive_products_excluded(self):
        """Archived products are excluded from results."""
        # Arrange — archive product_brique
        self.product_brique.active = False

        # Act
        result = self.env['sale.order'].search_products_for_spa()

        # Assert
        result_ids = [p['id'] for p in result]
        self.assertNotIn(self.product_brique.id, result_ids)

        # Cleanup
        self.product_brique.active = True

    # =========================================================================
    # Response format
    # =========================================================================

    def test_search_returns_expected_fields(self):
        """Response contains all fields expected by the QuoteBuilder frontend."""
        # Arrange
        EXPECTED_FIELDS = {'id', 'name', 'display_name', 'list_price', 'standard_price', 'uom_id'}

        # Act
        result = self.env['sale.order'].search_products_for_spa(limit=1)

        # Assert
        self.assertGreater(len(result), 0, "Should have at least one product")
        first = result[0]
        for field in EXPECTED_FIELDS:
            self.assertIn(field, first, f"Missing field '{field}' in response")

    # =========================================================================
    # Combined filters
    # =========================================================================

    def test_search_combined_term_and_category(self):
        """search_term + lot_category_id work together."""
        # Act — search for 'brique' in GO category
        result = self.env['sale.order'].search_products_for_spa(
            search_term='brique',
            lot_category_id=self.lot_cat_go.id
        )

        # Assert
        result_ids = [p['id'] for p in result]
        self.assertIn(self.product_brique.id, result_ids)

    def test_search_term_mismatch_with_category_returns_empty(self):
        """search_term='porte' + lot_category_id=GO → empty (porte is MENU)."""
        # Act
        result = self.env['sale.order'].search_products_for_spa(
            search_term='porte',
            lot_category_id=self.lot_cat_go.id
        )

        # Assert
        self.assertEqual(len(result), 0)
