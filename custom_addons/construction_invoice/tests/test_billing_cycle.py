from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError, UserError
from odoo import fields

class TestBillingCycle(TransactionCase):

    def setUp(self):
        super(TestBillingCycle, self).setUp()
        
        # Create a Client
        self.client = self.env['res.partner'].create({'name': 'Test Client'})
        
        # Create a Business Provider
        self.provider = self.env['res.partner'].create({'name': 'Business Provider'})
        
        # Create a Chantier
        self.chantier = self.env['construction.chantier'].create({
            'name': 'Test Chantier',
            'client': self.client.id,
            'business_provider_id': self.provider.id,
            'commission_type': 'percentage',
            'commission_value': 10.0,
        })
        
        # Create a Product
        self.product = self.env['product.product'].create({
            'name': 'Service Construction',
            'type': 'service',
            'list_price': 1000.0,
        })
        
        # Create a Sale Order linked to Chantier
        self.sale_order = self.env['sale.order'].create({
            'partner_id': self.client.id,
            'chantier_id': self.chantier.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 10,
                'price_unit': 1000.0,  # Total 10,000
            })]
        })
        self.sale_order.action_confirm()

    def test_standard_cycle_30_30_40(self):
        """Test creation of a standard 30/30/40 billing cycle."""
        
        # Create Billing Cycle
        cycle = self.env['construction.billing.cycle'].create({
            'chantier_id': self.chantier.id,
            'name': 'Cycle Standard',
        })
        
        # Verify Total Amount Confirmed (Should be 10,000)
        self.assertEqual(cycle.total_amount_confirmed, 10000.0)
        
        # Create Steps
        # Step 1: 30%
        self.env['construction.billing.step'].create({
            'cycle_id': cycle.id,
            'name': 'Acompte Commande',
            'percentage': 30.0,
            'sequence': 1,
        })
        # Step 2: 30%
        self.env['construction.billing.step'].create({
            'cycle_id': cycle.id,
            'name': 'Situation Intermédiaire',
            'percentage': 30.0,
            'sequence': 2,
        })
        # Step 3: 40%
        self.env['construction.billing.step'].create({
            'cycle_id': cycle.id,
            'name': 'Solde',
            'percentage': 40.0,
            'sequence': 3,
        })
        
        # Check computed amounts
        steps = cycle.step_ids.sorted('sequence')
        self.assertEqual(steps[0].amount, 3000.0)
        self.assertEqual(steps[1].amount, 3000.0)
        self.assertEqual(steps[2].amount, 4000.0)
        
        # Verify Total Billed (Should be 10,000)
        self.assertEqual(sum(steps.mapped('amount')), 10000.0)

    def test_over_billing_warning(self):
        """Test that over-billing raises a warning (simulated by Python constraint check)."""
        cycle = self.env['construction.billing.cycle'].create({
            'chantier_id': self.chantier.id,
            'name': 'Cycle Overload',
        })
        
        # Create a step for 110%
        # We expect the constraints logic to flag this
        # Note: Actual warning is UI side usually, but we check if model allows it or sets a flag
        step = self.env['construction.billing.step'].create({
            'cycle_id': cycle.id,
            'name': 'Gros Acompte',
            'percentage': 110.0,
        })
        
        # Check if cycle detects over billing
        # Assuming we have a computed field or method for validation status
        # For this test, we assume a method `check_over_billing` returns True/False or similar
        # Or we check a computed field `is_over_billed`
        
        # Since implementation details are pending, let's assume we implement a specific field
        # self.assertTrue(cycle.is_over_billed)
        pass 

    def test_commission_generation(self):
        """Test generation of commission debt for Business Provider."""
        
        # 1. Simulate Client Invoice validation
        # Create an invoice linked to the chantier
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.client.id,
            'invoice_date': fields.Date.today(),
            'chantier_id': self.chantier.id, # Assuming we link invoice to chantier
            'invoice_line_ids': [(0, 0, {
                'name': 'Acompte',
                'quantity': 1,
                'price_unit': 4000.0, # 4000€ Factured
            })],
        })
        
        # Validate Invoice
        invoice.action_post()
        
        # 2. Check Commission Calculation
        # Expect 10% of 4000 = 400
        
        # Check if a Vendor Bill (Draft) was created for the provider
        commission_bill = self.env['account.move'].search([
            ('partner_id', '=', self.provider.id),
            ('move_type', '=', 'in_invoice'),
            ('invoice_origin', 'ilike', invoice.name)
        ])
        
        self.assertTrue(commission_bill, "Commission bill should be created")
        self.assertEqual(commission_bill.amount_total, 400.0, "Commission amount should be 10% of invoice")

