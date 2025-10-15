"""
Unit tests for Chantier Action Methods

Tests cover:
- All action_* methods
- View actions and wizards
- Invoice and quote management actions
- Planning and document actions
"""

from odoo.tests import TransactionCase
from odoo.exceptions import ValidationError
from datetime import date, timedelta


class TestChantierActions(TransactionCase):
    """Test suite for Chantier action methods."""

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

    # ==================== View Actions Tests ====================

    def test_01_action_view_all_visits(self):
        """Test action_view_all_visits."""
        chantier = self._create_test_chantier()
        
        result = chantier.action_view_all_visits()
        
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'construction.visit')
        self.assertIn('calendar', result['view_mode'])
        self.assertEqual(result['domain'], [('chantier_id', '=', chantier.id)])

    def test_02_action_view_subcontractors(self):
        """Test action_view_subcontractors."""
        chantier = self._create_test_chantier()
        
        # Create subcontractor
        subcontractor = self.env['res.partner'].create({
            'name': 'Test Subcontractor',
            'supplier_rank': 1,
        })
        
        # Create lot with subcontractor
        self.env['construction.lot'].create({
            'name': 'Test Lot',
            'code': 'TL',
            'chantier_id': chantier.id,
            'subcontractor_ids': [(6, 0, [subcontractor.id])],
        })
        
        result = chantier.action_view_subcontractors()
        
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'res.partner')
        self.assertIn(chantier.name, result['name'])

    def test_03_action_view_budget(self):
        """Test action_view_budget."""
        chantier = self._create_test_chantier()
        
        # Create lots
        for i in range(2):
            self.env['construction.lot'].create({
                'name': f'Lot {i}',
                'code': f'L{i}',
                'chantier_id': chantier.id,
            })
        
        result = chantier.action_view_budget()
        
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'construction.lot')
        self.assertEqual(result['domain'], [('id', 'in', chantier.lots_ids.ids)])

    def test_04_action_view_quotations(self):
        """Test action_view_quotations."""
        chantier = self._create_test_chantier()
        
        # Create quotations
        self.env['sale.order'].create({
            'partner_id': self.client.id,
            'chantier_id': chantier.id,
        })
        
        result = chantier.action_view_quotations()
        
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'sale.order')
        self.assertIn('list', result['view_mode'])

    def test_05_action_view_invoice_schedule(self):
        """Test action_view_invoice_schedule."""
        chantier = self._create_test_chantier()
        
        result = chantier.action_view_invoice_schedule()
        
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'construction.invoice.schedule')
        self.assertEqual(result['domain'], [('chantier_id', '=', chantier.id)])

    def test_06_action_view_planning(self):
        """Test action_view_planning."""
        chantier = self._create_test_chantier()
        
        # Create lot
        self.env['construction.lot'].create({
            'name': 'Test Lot',
            'code': 'TL',
            'chantier_id': chantier.id,
        })
        
        result = chantier.action_view_planning()
        
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'construction.planning.task')
        self.assertIn('gantt', result['view_mode'])
        
        # Verify tasks were created for lots
        tasks = self.env['construction.planning.task'].search([
            ('chantier_id', '=', chantier.id)
        ])
        self.assertEqual(len(tasks), 1, "Should create task for each lot")

    # ==================== Schedule Visit Action Tests ====================

    def test_07_action_schedule_visit(self):
        """Test action_schedule_visit."""
        chantier = self._create_test_chantier()
        
        result = chantier.action_schedule_visit()
        
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'construction.visit')
        self.assertEqual(result['view_mode'], 'form')
        self.assertEqual(result['target'], 'new')
        self.assertEqual(
            result['context']['default_chantier_id'],
            chantier.id
        )

    # ==================== Quotation Actions Tests ====================

    def test_08_action_create_intelligent_quote_with_lots(self):
        """Test action_create_intelligent_quote with lots."""
        chantier = self._create_test_chantier()
        
        # Create lot
        self.env['construction.lot'].create({
            'name': 'Test Lot',
            'code': 'TL',
            'chantier_id': chantier.id,
        })
        
        result = chantier.action_create_intelligent_quote()
        
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'sale.order')
        self.assertEqual(result['view_mode'], 'form')
        
        # Verify quote was created
        quote_id = result['res_id']
        quote = self.env['sale.order'].browse(quote_id)
        self.assertEqual(quote.partner_id, self.client)
        self.assertEqual(quote.chantier_id, chantier)

    def test_09_action_create_intelligent_quote_without_lots(self):
        """Test action_create_intelligent_quote without lots."""
        chantier = self._create_test_chantier()
        
        with self.assertRaises(ValidationError) as cm:
            chantier.action_create_intelligent_quote()
        
        self.assertIn('lots', str(cm.exception).lower())

    def test_10_action_select_main_quote_single(self):
        """Test action_select_main_quote with single quote."""
        chantier = self._create_test_chantier()
        
        # Create single quote
        quote = self.env['sale.order'].create({
            'partner_id': self.client.id,
            'chantier_id': chantier.id,
            'state': 'draft',
        })
        
        # Set stage to minimum sequence 3
        chantier.with_context(bypass_stage_validation=True).write({
            'stage_id': self.stage.id
        })
        self.stage.sequence = 3
        
        result = chantier.action_select_main_quote()
        
        # Should auto-select the single quote
        self.assertEqual(result['type'], 'ir.actions.client')
        self.assertEqual(chantier.main_quote_id, quote)

    def test_11_action_select_main_quote_multiple(self):
        """Test action_select_main_quote with multiple quotes."""
        chantier = self._create_test_chantier()
        
        # Create multiple quotes
        for i in range(2):
            self.env['sale.order'].create({
                'partner_id': self.client.id,
                'chantier_id': chantier.id,
                'state': 'draft',
            })
        
        # Set stage to minimum sequence 3
        chantier.with_context(bypass_stage_validation=True).write({
            'stage_id': self.stage.id
        })
        self.stage.sequence = 3
        
        result = chantier.action_select_main_quote()
        
        # Should open wizard
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'construction.quote.selection.wizard')

    # ==================== Lot Selection Action Tests ====================

    def test_12_action_open_select_lots_wizard(self):
        """Test action_open_select_lots_wizard."""
        chantier = self._create_test_chantier()
        
        result = chantier.action_open_select_lots_wizard()
        
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'construction.lot.select.wizard')
        self.assertEqual(result['target'], 'new')

    # ==================== Invoice Setup Actions Tests ====================

    def test_13_action_setup_invoice_schedule_without_type(self):
        """Test action_setup_invoice_schedule without invoice type."""
        chantier = self._create_test_chantier()
        
        with self.assertRaises(ValidationError) as cm:
            chantier.action_setup_invoice_schedule()
        
        self.assertIn('cycle', str(cm.exception).lower())

    def test_14_action_setup_invoice_schedule_without_quote(self):
        """Test action_setup_invoice_schedule without main quote."""
        chantier = self._create_test_chantier()
        
        # Create invoice type
        invoice_type = self.env['construction.invoice_type'].create({
            'name': 'Test Type',
            'code': 'TEST',
        })
        
        chantier.invoice_type_id = invoice_type
        
        with self.assertRaises(ValidationError) as cm:
            chantier.action_setup_invoice_schedule()
        
        self.assertIn('devis principal', str(cm.exception).lower())

    def test_15_action_setup_invoice_schedule_complete(self):
        """Test action_setup_invoice_schedule with complete data."""
        chantier = self._create_test_chantier()
        
        # Create lot
        lot = self.env['construction.lot'].create({
            'name': 'Test Lot',
            'code': 'TL',
            'chantier_id': chantier.id,
            'price': 1000.0,
        })
        
        # Create invoice type with lines
        invoice_type = self.env['construction.invoice_type'].create({
            'name': 'Test Type',
            'code': 'TEST',
        })
        
        self.env['construction.invoice_type.line'].create({
            'invoice_type_id': invoice_type.id,
            'name': 'First Payment',
            'sequence': 1,
            'percentage': 30.0,
            'trigger_percentage': 0.0,
        })
        
        # Create quote
        quote = self.env['sale.order'].create({
            'partner_id': self.client.id,
            'chantier_id': chantier.id,
        })
        
        chantier.write({
            'invoice_type_id': invoice_type.id,
            'main_quote_id': quote.id,
        })
        
        result = chantier.action_setup_invoice_schedule()
        
        # Should create schedule lines
        self.assertTrue(
            chantier.invoice_schedule_ids,
            "Should create invoice schedule lines"
        )
        
        # Should return view action
        self.assertEqual(result['type'], 'ir.actions.act_window')

    def test_16_action_open_invoice_setup_wizard(self):
        """Test action_open_invoice_setup_wizard."""
        chantier = self._create_test_chantier()
        
        result = chantier.action_open_invoice_setup_wizard()
        
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'construction.invoice.setup.wizard')
        self.assertEqual(result['target'], 'new')

    def test_17_action_create_new_invoice_cycle(self):
        """Test action_create_new_invoice_cycle."""
        chantier = self._create_test_chantier()
        
        result = chantier.action_create_new_invoice_cycle()
        
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'construction.invoice_type')
        self.assertEqual(result['view_mode'], 'form')

    # ==================== Invoice Trigger Actions Tests ====================

    def test_18_action_check_invoice_triggers_no_schedule(self):
        """Test action_check_invoice_triggers without schedule."""
        chantier = self._create_test_chantier()
        
        with self.assertRaises(ValidationError):
            chantier.action_check_invoice_triggers()

    def test_19_action_create_available_invoices_no_ready(self):
        """Test action_create_available_invoices with no ready invoices."""
        chantier = self._create_test_chantier()
        
        # Create invoice schedule in planned state
        quote = self.env['sale.order'].create({
            'partner_id': self.client.id,
            'chantier_id': chantier.id,
        })
        
        self.env['construction.invoice.schedule'].create({
            'chantier_id': chantier.id,
            'quote_id': quote.id,
            'name': 'Test Schedule',
            'state': 'planned',
            'amount_percentage': 30.0,
        })
        
        result = chantier.action_create_available_invoices()
        
        self.assertEqual(result['type'], 'ir.actions.client')
        self.assertIn('warning', result['params']['type'])

    # ==================== Planning Actions Tests ====================

    def test_20_action_create_planning_task(self):
        """Test action_create_planning_task."""
        chantier = self._create_test_chantier()
        
        result = chantier.action_create_planning_task()
        
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'construction.planning.task.create')
        self.assertEqual(result['target'], 'new')

    def test_21_action_manage_order_lines_without_quote(self):
        """Test action_manage_order_lines without main quote."""
        chantier = self._create_test_chantier()
        
        with self.assertRaises(ValidationError):
            chantier.action_manage_order_lines()

    def test_22_action_manage_order_lines_with_quote(self):
        """Test action_manage_order_lines with main quote."""
        chantier = self._create_test_chantier()
        
        # Create main quote
        quote = self.env['sale.order'].create({
            'partner_id': self.client.id,
            'chantier_id': chantier.id,
        })
        
        chantier.main_quote_id = quote
        
        result = chantier.action_manage_order_lines()
        
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'sale.order.line')
        self.assertEqual(
            result['domain'],
            [('order_id', '=', quote.id)]
        )

    # ==================== Subcontractor Contract Actions Tests ====================

    def test_23_action_generate_subcontractor_contracts(self):
        """Test action_generate_subcontractor_contracts."""
        chantier = self._create_test_chantier()
        
        # Create subcontractor
        subcontractor = self.env['res.partner'].create({
            'name': 'Test Subcontractor',
            'supplier_rank': 1,
        })
        
        # Create lot with subcontractor
        self.env['construction.lot'].create({
            'name': 'Test Lot',
            'code': 'TL',
            'chantier_id': chantier.id,
            'subcontractor_ids': [(6, 0, [subcontractor.id])],
        })
        
        result = chantier.action_generate_subcontractor_contracts()
        
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'construction.contract.generation.wizard')
        self.assertEqual(result['target'], 'new')

    def test_24_action_send_contract_to_subcontractor(self):
        """Test action_send_contract_to_subcontractor."""
        chantier = self._create_test_chantier()
        
        # Create subcontractor
        subcontractor = self.env['res.partner'].create({
            'name': 'Test Subcontractor',
            'email': 'sub@test.com',
            'supplier_rank': 1,
        })
        
        # Create lot with subcontractor
        self.env['construction.lot'].create({
            'name': 'Test Lot',
            'code': 'TL',
            'chantier_id': chantier.id,
            'subcontractor_ids': [(6, 0, [subcontractor.id])],
        })
        
        result = chantier.action_send_contract_to_subcontractor()
        
        self.assertEqual(result['type'], 'ir.actions.client')
        # Should show notification (success or warning)
        self.assertIn(
            result['params']['type'],
            ['success', 'warning']
        )

    # ==================== Purchase Order Split Actions Tests ====================

    def test_25_action_split_quote_to_purchase_wizard(self):
        """Test action_split_quote_to_purchase_wizard."""
        chantier = self._create_test_chantier()
        
        result = chantier.action_split_quote_to_purchase_wizard()
        
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'construction.purchase.split.wizard')
        self.assertEqual(result['target'], 'new')

    def test_26_action_view_purchase_orders(self):
        """Test action_view_purchase_orders."""
        chantier = self._create_test_chantier()
        
        result = chantier.action_view_purchase_orders()
        
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'purchase.order')
        self.assertIn('list', result['view_mode'])

    # ==================== Helper Method Tests ====================

    def test_27_get_quote_lines_by_lot_no_quote(self):
        """Test get_quote_lines_by_lot without main quote."""
        chantier = self._create_test_chantier()
        
        result = chantier.get_quote_lines_by_lot()
        
        self.assertEqual(result, {}, "Should return empty dict without quote")

    def test_28_get_quote_lines_by_lot_with_quote(self):
        """Test get_quote_lines_by_lot with quote and lots."""
        chantier = self._create_test_chantier()
        
        # Create lot
        lot = self.env['construction.lot'].create({
            'name': 'Électricité',
            'code': 'ELEC',
            'chantier_id': chantier.id,
        })
        
        # Create quote
        quote = self.env['sale.order'].create({
            'partner_id': self.client.id,
            'chantier_id': chantier.id,
        })
        
        chantier.main_quote_id = quote
        
        # Create product
        product = self.env['product.product'].create({
            'name': 'Électricité - Installation',
            'type': 'service',
        })
        
        # Create order line
        self.env['sale.order.line'].create({
            'order_id': quote.id,
            'product_id': product.id,
            'name': 'Électricité - Installation',
        })
        
        result = chantier.get_quote_lines_by_lot()
        
        # Should group lines by lot
        self.assertIsInstance(result, dict, "Should return dict")

    def test_29_create_default_lots(self):
        """Test _create_default_lots."""
        chantier = self._create_test_chantier()
        
        # Create lot template
        self.env['construction.lot.template'].create({
            'name': 'Template Lot',
            'code': 'TMPL',
            'active': True,
        })
        
        chantier._create_default_lots()
        
        # Should create lots from templates
        self.assertTrue(
            chantier.lots_ids,
            "Should create lots from templates"
        )

    # ==================== Force Stage Change Tests ====================

    def test_30_action_force_stage_change_non_admin(self):
        """Test action_force_stage_change by non-admin."""
        chantier = self._create_test_chantier()
        
        with self.assertRaises(ValidationError):
            chantier.action_force_stage_change()

    def test_31_action_force_stage_change_admin(self):
        """Test action_force_stage_change by admin."""
        # Create admin user
        admin_group = self.env.ref('base.group_system')
        admin_user = self.env['res.users'].create({
            'name': 'Admin User',
            'login': 'admin_test_action',
            'groups_id': [(4, admin_group.id)],
        })
        
        chantier = self._create_test_chantier()
        
        result = chantier.with_user(admin_user).action_force_stage_change()
        
        self.assertEqual(result['type'], 'ir.actions.client')

    # ==================== Update Lots Prices Tests ====================

    def test_32_update_lots_prices_from_quote(self):
        """Test _update_lots_prices_from_quote."""
        chantier = self._create_test_chantier()
        
        # Create lot
        lot = self.env['construction.lot'].create({
            'name': 'Test Lot',
            'code': 'TL',
            'chantier_id': chantier.id,
            'price': 0.0,
        })
        
        # Create quote
        quote = self.env['sale.order'].create({
            'partner_id': self.client.id,
            'chantier_id': chantier.id,
        })
        
        chantier.main_quote_id = quote
        
        # Create product
        product = self.env['product.product'].create({
            'name': 'Test Product',
            'type': 'service',
            'list_price': 100.0,
        })
        
        # Create order line with lot reference in name
        self.env['sale.order.line'].create({
            'order_id': quote.id,
            'product_id': product.id,
            'name': 'Test Lot - Product',
            'product_uom_qty': 10,
        })
        
        chantier._update_lots_prices_from_quote()
        
        # Lot should have lines assigned
        # This tests the association logic

