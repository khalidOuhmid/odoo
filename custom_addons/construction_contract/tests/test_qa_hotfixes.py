# -*- coding: utf-8 -*-
from odoo.tests import common, tagged
from odoo.exceptions import UserError
from datetime import date, timedelta

@tagged('post_install', '-at_install', 'qual_hotfix')
class TestCriticalHotfixes(common.TransactionCase):
    
    def setUp(self):
        super(TestCriticalHotfixes, self).setUp()
        
        # Test Data Setup
        self.Chantier = self.env['construction.chantier']
        self.Lot = self.env['construction.lot']
        self.Partner = self.env['res.partner']
        self.SaleOrder = self.env['sale.order']
        self.Product = self.env['product.product']
        
        # Partner Subcontractor
        self.subcontractor = self.Partner.create({
            'name': 'QA Plomberie',
            'is_subcontractor': True,
            'supplier_rank': 1,
            # Initially no documents
        })
        
        # Chantier
        self.chantier = self.Chantier.create({
            'name': 'Chantier QA 01',
            'client': self.Partner.create({'name': 'Client Test'}).id
        })
        
        # Lot 1
        self.lot1 = self.Lot.create({
            'name': 'Lot 1 Plumber',
            'code': 'LOT-01',
            'chantier_id': self.chantier.id,
            'subcontractor_id': self.subcontractor.id,
            'execution_type': 'external',
        })
        
        # Product
        self.product = self.Product.create({
            'name': 'Tuyau Test',
            'type': 'product',
            'standard_price': 50.0,
        })

    # ================= TEST 1: DOCUMENT STATUS (FEU TRICOLORE) =================
    def test_01_document_status_logic(self):
        """Test 'Feu Tricolore' Logic: Check Red/Orange/Green status based on docs."""
        # 1. Start: No documents -> Should be DANGER (Red)
        self.lot1._compute_document_status()
        self.assertEqual(self.lot1.document_status, 'danger', "FAIL: Status should be DANGER when documents missing.")
        
        # 2. Add Valid Documents
        today = date.today()
        valid_date = today + timedelta(days=60)
        
        self.subcontractor.write({
            'doc_kbis': b'RkZ', 'doc_kbis_expiry': valid_date,
            'doc_urssaf': b'RkZ', 'doc_urssaf_expiry': valid_date,
            'doc_insurance_dec': b'RkZ', 'doc_insurance_dec_expiry': valid_date,
            'doc_cni': b'RkZ', 'doc_cni_expiry': valid_date,
        })
        
        self.lot1._compute_document_status()
        self.assertEqual(self.lot1.document_status, 'success', "FAIL: Status should be SUCCESS (Green) when all docs valid.")
        
        # 3. Warning Scenario: One doc expires < 30 days
        soon_expiry = today + timedelta(days=15)
        self.subcontractor.write({'doc_kbis_expiry': soon_expiry})
        
        self.lot1._compute_document_status()
        self.assertEqual(self.lot1.document_status, 'warning', "FAIL: Status should be WARNING (Orange) when expiry < 30 days.")
        
        # 4. Critical Scenario: One doc expired or missing (removed)
        self.subcontractor.write({'doc_urssaf': False})
        
        self.lot1._compute_document_status()
        self.assertEqual(self.lot1.document_status, 'danger', "FAIL: Status should be DANGER (Red) when doc missing.")
        
        print("✅ PASS: Test 1 (Feu Tricolore) passed.")

    # ================= TEST 2: PRODUCT QTY (CRASH BC) =================
    def test_02_product_qty_crash_fix(self):
        """Test 'Crash BC': Ensure PO generation works even if SO line qty is 0/Missing."""
        # Create Quote
        so = self.SaleOrder.create({
            'partner_id': self.chantier.client.id,
            'chantier_id': self.chantier.id,
        })
        # Line with 0 qty (simulating issue)
        so_line = self.env['sale.order.line'].create({
            'order_id': so.id,
            'product_id': self.product.id,
            'lot_id': self.lot1.id,
            'product_uom_qty': 0.0, # Danger!
            'price_unit': 100.0,
            'price_buy': 40.0,
        })
        so.action_confirm()
        
        # Call Generate PO (Direct call on Lot to simulate button click)
        # Should NOT crash
        try:
            self.lot1.action_generate_purchase_order()
        except Exception as e:
            self.fail(f"FAIL: Crash during PO generation: {e}")
            
        # Verify PO created
        po = self.env['purchase.order'].search([('lot_ids', 'in', self.lot1.id)], limit=1)
        self.assertTrue(po, "FAIL: PO not created.")
        self.assertEqual(len(po.order_line), 2, "FAIL: Should have section + 1 product line.") # Section + Line
        
        product_line = po.order_line.filtered(lambda l: l.product_id)
        self.assertEqual(product_line.product_qty, 1.0, "FAIL: Qty should default to 1.0 logic.")
        
        print("✅ PASS: Test 2 (Product Qty) passed.")

    # ================= TEST 3: MULTI-LOTS INTELLIGENCE =================
    def test_03_multi_lot_grouping(self):
        """Test 'Multi-Lots': Verify Wizard intercept when second lot exists."""
        # Create Lot 2 for same sub
        lot2 = self.Lot.create({
            'name': 'Lot 2 Heat',
            'code': 'LOT-02',
            'chantier_id': self.chantier.id,
            'subcontractor_id': self.subcontractor.id, # Same sub
            'execution_type': 'external',
        })
        
        # Action from Lot 1
        action = self.lot1.action_generate_purchase_order()
        
        # Verify Interception
        self.assertIsInstance(action, dict, "FAIL: Should return an Action dictionary.")
        self.assertEqual(action.get('res_model'), 'construction.lot.grouping.wizard', 
                         "FAIL: Should open 'construction.lot.grouping.wizard'.")
        
        # Verify Context passing target lots
        ctx = action.get('context', {})
        target_ids = ctx.get('default_lot_ids')
        self.assertIn(self.lot1.id, target_ids, "FAIL: Lot 1 missing from wizard context.")
        self.assertIn(lot2.id, target_ids, "FAIL: Lot 2 missing from wizard context.")
        
        print("✅ PASS: Test 3 (Multi-Lots) passed.")

    # ================= TEST 4: CONTRACT SECURITY (VALIDATION) =================
    def test_04_contract_security(self):
        """Test 'Police des Contrats': Blocking validation for missing docs."""
        # Ensure Chantier has NO documents
        self.assertFalse(self.chantier.document_ids)
        
        # Action: Generate Contract
        action = self.lot1.action_generate_contract_wizard()
        
        # Verify Blocking Wizard
        self.assertTrue(action, "FAIL: Should return action.")
        self.assertEqual(action.get('res_model'), 'construction.contract.validation.wizard',
                         "FAIL: Should open Validation Wizard because docs are missing.")
                         
        # Verify Missing Items Content
        missing_html = action.get('context', {}).get('default_missing_items', '')
        self.assertIn('CCTP', missing_html)
        self.assertIn('Planning', missing_html)
        
        # Action Force Generate
        wizard = self.env['construction.contract.validation.wizard'].create({
            'lot_id': self.lot1.id,
            'missing_items': missing_html
        })
        
        # Force it
        force_action = wizard.action_force_generate()
        
        # Now it should proceed (e.g. return action_open_contract_editor or something else, NOT the validation wizard)
        # Note: If it succeeds, it returns the contract editor action (dict)
        self.assertNotEqual(force_action.get('res_model'), 'construction.contract.validation.wizard',
                            "FAIL: Should validation passed after forcing.")
        
        # Verify Chatter Log
        logs = self.chantier.message_ids.filtered(lambda m: "Contrat généré de force" in m.body)
        self.assertTrue(logs, "FAIL: Should log forced generation in chatter.")
        
        print("✅ PASS: Test 4 (Contract Security) passed.")
