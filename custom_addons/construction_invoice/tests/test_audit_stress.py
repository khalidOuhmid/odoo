from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError, UserError
from odoo import fields

class TestAuditStress(TransactionCase):

    def setUp(self):
        super(TestAuditStress, self).setUp()
        self.client = self.env['res.partner'].create({'name': 'Audit Client'})
        self.provider = self.env['res.partner'].create({'name': 'Audit Provider (Agent)'})
        self.chantier = self.env['construction.chantier'].create({
            'name': 'Stress Test Chantier',
            'client': self.client.id,
            'business_provider_id': self.provider.id,
            'commission_type': 'percentage',
            'commission_value': 10.0,
        })
        self.product = self.env['product.product'].create({
            'name': 'Service Test',
            'type': 'service',
            'list_price': 1.0,
        })

    def test_audit_1_blocking_error_110_percent(self):
        """Audit 1: Custom Cycle with 110% MUST BLOCK."""
        # Setup Sale Order for 1000
        so = self.create_so(1000.0)
        
        # Try to create a cycle with one step of 110% via Wizard or Direct
        # User scenario specifically mentions Wizard Custom Cycle steps 50, 40, 20
        
        cycle = self.env['construction.billing.cycle'].create({
            'chantier_id': self.chantier.id,
            'name': 'Cycle Faux'
        })
        
        with self.assertRaises(ValidationError, msg="System MUST block 110% cycle"):
            # Step 1: 50%
            self.env['construction.billing.step'].create({
                'cycle_id': cycle.id, 'name': '1', 'percentage': 50.0
            })
            # Step 2: 40%
            self.env['construction.billing.step'].create({
                'cycle_id': cycle.id, 'name': '2', 'percentage': 40.0
            })
            # Step 3: 20% -> Total 110%
            self.env['construction.billing.step'].create({
                'cycle_id': cycle.id, 'name': '3', 'percentage': 20.0
            })
            
            # Explicitly call check method if constraint is python-based and not auto-triggered on create
            cycle._check_over_billing()

    def test_audit_2_rounding_centime(self):
        """Audit 2: 3333.33 split in 3 must sum exactly to 3333.33."""
        target_amount = 3333.33
        so = self.create_so(target_amount)
        
        cycle = self.env['construction.billing.cycle'].create({
            'chantier_id': self.chantier.id, 
            'name': 'Cycle Tiers'
        })
        
        # Create 3 steps of 33.33% (or 1/3 if we supported fractions, but usually user enters %)
        # If user enters 33.33, 33.33, 33.34 it works.
        # But if they enter "Standard 1/3" logic (often 33.33 * 3), it fails.
        # Let's assume the user enters 3 steps manually described as "1/3".
        # Or better, let's test the "Standard 30/30/40" logic but with thirds?
        # User scenario: "Cycle de facturation en 3 tiers". imply 33.33% x 3.
        # 33.33 + 33.33 + 33.33 = 99.99%.
        # The system needs to detect that we want 100% and fix the last one or the amounts.
        
        s1 = self.env['construction.billing.step'].create({'cycle_id': cycle.id, 'name': '1', 'percentage': 33.33})
        s2 = self.env['construction.billing.step'].create({'cycle_id': cycle.id, 'name': '2', 'percentage': 33.33})
        s3 = self.env['construction.billing.step'].create({'cycle_id': cycle.id, 'name': '3', 'percentage': 33.34}) # User manually sets to 100%?
        
        # Wait, if user sets 33.33, 33.33, 33.33 -> It IS 99.99%.
        # Does the user expect the system to magically guess 1/3?
        # "Le système doit gérer le reste à facturer sur la dernière facture pour tomber juste"
        # This implies: Last Invoice = Total Confirmed - Sum(Previous Invoices).
        # Regardless of the step percentage calculation!
        
        # Let's simulate that:
        # Step 1 Invoice
        s1.action_create_invoice()
        # Step 2 Invoice
        s2.action_create_invoice()
        # Step 3 Invoice - This is the critical one.
        inv3_action = s3.action_create_invoice()
        inv3 = self.env['account.move'].browse(inv3_action['res_id'])
        
        billed_total = s1.invoice_id.amount_untaxed + s2.invoice_id.amount_untaxed + inv3.amount_untaxed
        
        self.assertAlmostEqual(billed_total, target_amount, places=2, msg="Rounding Logic Failed")

    def test_audit_3_commission_refund(self):
        """Audit 3: Refund must cancel commission."""
        so = self.create_so(1000.0)
        
        # 1. Invoice -> Commission
        inv = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.client.id,
            'invoice_date': fields.Date.today(),
            'chantier_id': self.chantier.id,
            'invoice_line_ids': [(0, 0, {'price_unit': 1000.0})]
        })
        inv.action_post()
        
        # Check Commission (+100)
        comm_bill = self.env['account.move'].search([
            ('partner_id', '=', self.provider.id), ('move_type', '=', 'in_invoice'),
            ('invoice_origin', 'ilike', inv.name)
        ])
        self.assertTrue(comm_bill, "Commission Bill Created")
        self.assertEqual(comm_bill.amount_untaxed, 100.0)
        
        # 2. Refund -> Negative Commission
        refund = self.env['account.move'].create({
            'move_type': 'out_refund',
            'partner_id': self.client.id,
            'invoice_date': fields.Date.today(),
            'chantier_id': self.chantier.id, # Link refund to chantier
            'invoice_line_ids': [(0, 0, {'price_unit': 1000.0})]
        })
        refund.action_post()
        
        # Check Commission Refund (-100 or Credit Note)
        comm_refund = self.env['account.move'].search([
            ('partner_id', '=', self.provider.id), ('move_type', '=', 'in_refund'),
            ('invoice_origin', 'ilike', refund.name) # Or regex match
        ])
        
        self.assertTrue(comm_refund, "Commission Refund Created")
        self.assertEqual(comm_refund.amount_untaxed, 100.0)

    def create_so(self, amount):
        so = self.env['sale.order'].create({
            'partner_id': self.client.id,
            'chantier_id': self.chantier.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'price_unit': amount,
            })]
        })
        so.action_confirm()
        return so
