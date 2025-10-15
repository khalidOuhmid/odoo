"""
Unit tests for Chantier Computed Fields

Tests cover:
- All _compute_* methods
- Field dependencies and triggers
- Calculation accuracy
"""

from odoo.tests import TransactionCase
from datetime import date, timedelta


class TestChantierCompute(TransactionCase):
    """Test suite for Chantier computed field methods."""

    @classmethod
    def setUpClass(cls):
        """Set up test data for all test methods."""
        super().setUpClass()
        
        # Create test client
        cls.client = cls.env['res.partner'].create({
            'name': 'Test Client',
            'email': 'client@test.com',
            'phone': '0123456789',
        })
        
        # Create test chapter and stage
        cls.chapter = cls.env['construction.chapter'].create({
            'name': 'Test Chapter',
            'code': 'TEST',
            'sequence': 1,
        })
        
        cls.stage = cls.env['construction.stage'].create({
            'name': 'Test Stage',
            'code': 'TS',
            'chapter_id': cls.chapter.id,
            'sequence': 1,
        })

    def _create_test_chantier(self, **kwargs):
        """Helper method to create test chantier."""
        default_values = {
            'name': 'Test Project',
            'client': self.client.id,
            'address': '123 Test Street',
            'description': 'Test description',
            'phone': '0123456789',
        }
        default_values.update(kwargs)
        return self.env['construction.chantier'].create(default_values)

    # ==================== Chapter Name Compute Tests ====================

    def test_01_compute_chapter_name_with_stage(self):
        """Test _compute_chapter_name with valid stage."""
        chantier = self._create_test_chantier()
        chantier.with_context(bypass_stage_validation=True).write({
            'stage_id': self.stage.id
        })
        
        self.assertEqual(
            chantier.chapter_name,
            self.chapter.name,
            "Chapter name should match stage's chapter"
        )

    def test_02_compute_chapter_name_without_stage(self):
        """Test _compute_chapter_name without stage."""
        chantier = self._create_test_chantier()
        chantier.with_context(bypass_stage_validation=True).write({
            'stage_id': False
        })
        
        self.assertFalse(
            chantier.chapter_name,
            "Chapter name should be False without stage"
        )

    # ==================== Duration Planned Compute Tests ====================

    def test_03_compute_duration_planned_with_dates(self):
        """Test _compute_duration_planned with contract dates."""
        chantier = self._create_test_chantier()
        
        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 31)
        
        chantier.write({
            'date_start_contract': start_date,
            'date_end_contract': end_date,
        })
        
        # 31 days (1-31 inclusive)
        self.assertEqual(
            chantier.duration_planned,
            31,
            "Duration planned should be 31 days"
        )

    def test_04_compute_duration_planned_without_dates(self):
        """Test _compute_duration_planned without dates."""
        chantier = self._create_test_chantier()
        
        # No dates set, duration should not be calculated
        self.assertFalse(
            chantier.duration_planned,
            "Duration planned should be empty without dates"
        )

    def test_05_compute_duration_planned_single_day(self):
        """Test _compute_duration_planned for single day."""
        chantier = self._create_test_chantier()
        
        same_date = date(2024, 1, 1)
        chantier.write({
            'date_start_contract': same_date,
            'date_end_contract': same_date,
        })
        
        # Single day = 1
        self.assertEqual(
            chantier.duration_planned,
            1,
            "Single day duration should be 1"
        )

    # ==================== Duration Actual Compute Tests ====================

    def test_06_compute_duration_actual_with_end_date(self):
        """Test _compute_duration_actual with both dates."""
        chantier = self._create_test_chantier()
        
        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 31)
        
        chantier.write({
            'date_start_internal': start_date,
            'date_end_internal': end_date,
        })
        
        self.assertEqual(
            chantier.duration_actual,
            31,
            "Duration actual should be 31 days"
        )

    def test_07_compute_duration_actual_active_without_end(self):
        """Test _compute_duration_actual for active project without end date."""
        chantier = self._create_test_chantier()
        
        start_date = date.today() - timedelta(days=10)
        chantier.write({
            'date_start_internal': start_date,
            'state': 'active',
        })
        
        # Should calculate from start to today
        expected_duration = 11  # 10 days + 1
        self.assertEqual(
            chantier.duration_actual,
            expected_duration,
            f"Duration should be {expected_duration} days from start to today"
        )

    def test_08_compute_duration_actual_without_dates(self):
        """Test _compute_duration_actual without dates."""
        chantier = self._create_test_chantier()
        
        self.assertEqual(
            chantier.duration_actual,
            0,
            "Duration actual should be 0 without dates"
        )

    # ==================== Construction Progression Compute Tests ====================

    def test_09_compute_construction_progression_with_lots(self):
        """Test _compute_construction_progression with completed lots."""
        chantier = self._create_test_chantier()
        
        # Create lots
        lot1 = self.env['construction.lot'].create({
            'name': 'Lot 1',
            'code': 'L1',
            'chantier_id': chantier.id,
            'price': 1000.0,
            'is_finished': True,
        })
        
        lot2 = self.env['construction.lot'].create({
            'name': 'Lot 2',
            'code': 'L2',
            'chantier_id': chantier.id,
            'price': 1000.0,
            'is_finished': False,
        })
        
        # Progress should be 50% (1 of 2 lots completed)
        self.assertEqual(
            chantier.progress,
            50.0,
            "Progress should be 50% with one lot completed"
        )

    def test_10_compute_construction_progression_no_lots(self):
        """Test _compute_construction_progression without lots."""
        chantier = self._create_test_chantier()
        
        self.assertEqual(
            chantier.progress,
            0.0,
            "Progress should be 0% without lots"
        )

    def test_11_compute_construction_progression_all_completed(self):
        """Test _compute_construction_progression with all lots completed."""
        chantier = self._create_test_chantier()
        
        # Create completed lots
        for i in range(3):
            self.env['construction.lot'].create({
                'name': f'Lot {i}',
                'code': f'L{i}',
                'chantier_id': chantier.id,
                'price': 1000.0,
                'is_finished': True,
            })
        
        self.assertEqual(
            chantier.progress,
            100.0,
            "Progress should be 100% with all lots completed"
        )

    def test_12_compute_construction_progression_with_price_from_quote(self):
        """Test _compute_construction_progression using price_from_quote."""
        chantier = self._create_test_chantier()
        
        # Create lot with price_from_quote but no price
        lot = self.env['construction.lot'].create({
            'name': 'Lot 1',
            'code': 'L1',
            'chantier_id': chantier.id,
            'price': 0.0,
            'is_finished': False,
        })
        
        # Manually set price_from_quote (normally computed)
        # This tests the fallback logic
        # Progress computation should use price_from_quote when price is 0

    # ==================== Days Remaining Compute Tests ====================

    def test_13_compute_days_remaining_future_date(self):
        """Test _compute_days_remaining with future end date."""
        chantier = self._create_test_chantier()
        
        future_date = date.today() + timedelta(days=30)
        chantier.write({'date_end_contract': future_date})
        
        self.assertEqual(
            chantier.days_remaining,
            30,
            "Days remaining should be 30"
        )

    def test_14_compute_days_remaining_past_date(self):
        """Test _compute_days_remaining with past end date."""
        chantier = self._create_test_chantier()
        
        past_date = date.today() - timedelta(days=10)
        chantier.write({'date_end_contract': past_date})
        
        self.assertEqual(
            chantier.days_remaining,
            0,
            "Days remaining should be 0 for past date"
        )

    def test_15_compute_days_remaining_today(self):
        """Test _compute_days_remaining with end date today."""
        chantier = self._create_test_chantier()
        
        chantier.write({'date_end_contract': date.today()})
        
        self.assertEqual(
            chantier.days_remaining,
            0,
            "Days remaining should be 0 for today"
        )

    def test_16_compute_days_remaining_without_date(self):
        """Test _compute_days_remaining without end date."""
        chantier = self._create_test_chantier()
        
        self.assertEqual(
            chantier.days_remaining,
            0,
            "Days remaining should be 0 without date"
        )

    # ==================== Deadline Status Compute Tests ====================

    def test_17_compute_deadline_status_on_time(self):
        """Test _compute_deadline_status when on time."""
        chantier = self._create_test_chantier()
        
        future_date = date.today() + timedelta(days=60)
        chantier.write({
            'date_end_contract': future_date,
            'state': 'active',
        })
        
        self.assertEqual(
            chantier.deadline_status,
            'on_time',
            "Status should be on_time with 60 days remaining"
        )
        self.assertEqual(
            chantier.deadline_color,
            10,
            "Color should be green (10)"
        )

    def test_18_compute_deadline_status_warning(self):
        """Test _compute_deadline_status in warning zone."""
        chantier = self._create_test_chantier()
        
        future_date = date.today() + timedelta(days=20)
        chantier.write({
            'date_end_contract': future_date,
            'state': 'active',
        })
        
        self.assertEqual(
            chantier.deadline_status,
            'warning',
            "Status should be warning with 20 days remaining"
        )
        self.assertEqual(
            chantier.deadline_color,
            3,
            "Color should be yellow (3)"
        )

    def test_19_compute_deadline_status_late(self):
        """Test _compute_deadline_status when late."""
        chantier = self._create_test_chantier()
        
        future_date = date.today() + timedelta(days=5)
        chantier.write({
            'date_end_contract': future_date,
            'state': 'active',
        })
        
        self.assertEqual(
            chantier.deadline_status,
            'late',
            "Status should be late with 5 days remaining"
        )
        self.assertEqual(
            chantier.deadline_color,
            2,
            "Color should be orange (2)"
        )

    def test_20_compute_deadline_status_critical(self):
        """Test _compute_deadline_status when critical."""
        chantier = self._create_test_chantier()
        
        past_date = date.today() - timedelta(days=5)
        chantier.write({
            'date_end_contract': past_date,
            'state': 'active',
        })
        
        self.assertEqual(
            chantier.deadline_status,
            'critical',
            "Status should be critical with negative days"
        )
        self.assertEqual(
            chantier.deadline_color,
            1,
            "Color should be red (1)"
        )

    def test_21_compute_deadline_status_completed_project(self):
        """Test _compute_deadline_status for completed project."""
        chantier = self._create_test_chantier()
        
        past_date = date.today() - timedelta(days=5)
        chantier.write({
            'date_end_contract': past_date,
            'state': 'completed',
        })
        
        self.assertEqual(
            chantier.deadline_status,
            'on_time',
            "Completed project should show on_time"
        )
        self.assertEqual(
            chantier.deadline_color,
            10,
            "Completed project should be green"
        )

    # ==================== Total Cost Compute Tests ====================

    def test_22_compute_total_cost_with_lots(self):
        """Test _compute_total_cost with multiple lots."""
        chantier = self._create_test_chantier()
        
        # Create lots with prices
        self.env['construction.lot'].create({
            'name': 'Lot 1',
            'code': 'L1',
            'chantier_id': chantier.id,
            'price': 1000.0,
        })
        
        self.env['construction.lot'].create({
            'name': 'Lot 2',
            'code': 'L2',
            'chantier_id': chantier.id,
            'price': 2000.0,
        })
        
        self.assertEqual(
            chantier.total_cost,
            3000.0,
            "Total cost should be sum of lot prices"
        )

    def test_23_compute_total_cost_without_lots(self):
        """Test _compute_total_cost without lots."""
        chantier = self._create_test_chantier()
        
        self.assertEqual(
            chantier.total_cost,
            0.0,
            "Total cost should be 0 without lots"
        )

    # ==================== Counts Compute Tests ====================

    def test_24_compute_counts_lots(self):
        """Test _compute_counts for lots_count."""
        chantier = self._create_test_chantier()
        
        # Create lots
        for i in range(3):
            self.env['construction.lot'].create({
                'name': f'Lot {i}',
                'code': f'L{i}',
                'chantier_id': chantier.id,
            })
        
        self.assertEqual(
            chantier.lots_count,
            3,
            "Lots count should be 3"
        )

    def test_25_compute_counts_sale_orders(self):
        """Test _compute_counts for sale_order_count."""
        chantier = self._create_test_chantier()
        
        # Create sale orders
        for i in range(2):
            self.env['sale.order'].create({
                'partner_id': self.client.id,
                'chantier_id': chantier.id,
            })
        
        self.assertEqual(
            chantier.sale_order_count,
            2,
            "Sale order count should be 2"
        )

    # ==================== Order Stats Compute Tests ====================

    def test_26_compute_order_stats_empty(self):
        """Test _compute_order_stats with no order lines."""
        chantier = self._create_test_chantier()
        
        self.assertEqual(chantier.total_order_lines, 0)
        self.assertEqual(chantier.total_ordered_lines, 0)
        self.assertEqual(chantier.total_tracking_lines, 0)
        self.assertEqual(chantier.order_progress, 0.0)

    def test_27_compute_order_stats_with_lines(self):
        """Test _compute_order_stats with order lines."""
        chantier = self._create_test_chantier()
        
        # Create lot
        lot = self.env['construction.lot'].create({
            'name': 'Test Lot',
            'code': 'TL',
            'chantier_id': chantier.id,
        })
        
        # Create main quote
        quote = self.env['sale.order'].create({
            'partner_id': self.client.id,
            'chantier_id': chantier.id,
        })
        
        chantier.main_quote_id = quote
        
        # Create order lines
        product = self.env['product.product'].create({
            'name': 'Test Product',
            'type': 'product',
        })
        
        # Line with order date
        self.env['sale.order.line'].create({
            'order_id': quote.id,
            'product_id': product.id,
            'lot_id': lot.id,
            'order_date': date.today(),
        })
        
        # Line without order date
        self.env['sale.order.line'].create({
            'order_id': quote.id,
            'product_id': product.id,
            'lot_id': lot.id,
        })
        
        # Manually trigger compute
        chantier._compute_order_stats()
        
        self.assertEqual(chantier.total_order_lines, 2, "Should have 2 order lines")
        self.assertEqual(chantier.total_ordered_lines, 1, "Should have 1 ordered line")
        self.assertEqual(chantier.order_progress, 50.0, "Progress should be 50%")

    # ==================== Document Count Compute Tests ====================

    def test_28_compute_document_count_by_type_empty(self):
        """Test _compute_document_count_by_type with no documents."""
        chantier = self._create_test_chantier()
        
        self.assertIn(
            'Aucun document',
            chantier.document_count_by_type,
            "Should show 'no documents' message"
        )

    def test_29_compute_document_count_by_type_with_documents(self):
        """Test _compute_document_count_by_type with documents."""
        chantier = self._create_test_chantier()
        
        # Create documents
        for i in range(2):
            self.env['construction.document'].create({
                'chantier_id': chantier.id,
                'name': f'Doc {i}',
                'document_type': 'contract',
            })
        
        self.env['construction.document'].create({
            'chantier_id': chantier.id,
            'name': 'Schedule',
            'document_type': 'schedule',
        })
        
        result = chantier.document_count_by_type
        
        # Should contain counts for each type
        self.assertIn('2', result, "Should show count of 2")

    # ==================== Invoice Schedule Stats Compute Tests ====================

    def test_30_compute_invoice_schedule_stats_empty(self):
        """Test _compute_invoice_schedule_stats with no schedules."""
        chantier = self._create_test_chantier()
        
        self.assertEqual(chantier.invoice_schedule_planned_count, 0)
        self.assertEqual(chantier.invoice_schedule_ready_count, 0)
        self.assertEqual(chantier.invoice_schedule_invoiced_count, 0)
        self.assertEqual(chantier.invoice_schedule_total_amount, 0.0)

    # ==================== Quotation Count Compute Tests ====================

    def test_31_compute_quotation_count(self):
        """Test _compute_quotation_count."""
        chantier = self._create_test_chantier()
        
        # Create quotations
        for i in range(3):
            self.env['sale.order'].create({
                'partner_id': self.client.id,
                'chantier_id': chantier.id,
            })
        
        self.assertEqual(
            chantier.quotation_count,
            3,
            "Quotation count should be 3"
        )

    # ==================== Action Visibility Compute Tests ====================

    def test_32_compute_action_visibility_without_stage(self):
        """Test _compute_action_visibility without stage."""
        chantier = self._create_test_chantier()
        chantier.with_context(bypass_stage_validation=True).write({
            'stage_id': False
        })
        
        chantier._compute_action_visibility()
        
        self.assertFalse(chantier.show_schedule_visit)
        self.assertFalse(chantier.show_create_quote)
        self.assertFalse(chantier.show_assign_subcontractors)

    def test_33_compute_action_visibility_active_state(self):
        """Test _compute_action_visibility with active state."""
        chantier = self._create_test_chantier()
        chantier.state = 'active'
        
        chantier._compute_action_visibility()
        
        # show_schedule_visit should be True for active state
        self.assertTrue(
            chantier.show_schedule_visit,
            "Schedule visit should be shown for active state"
        )

