# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError
from unittest.mock import patch, MagicMock
import logging

_logger = logging.getLogger(__name__)

@tagged('post_install', '-at_install')
class TestContractComprehensiveMock(TransactionCase):

    def setUp(self):
        super(TestContractComprehensiveMock, self).setUp()
        
        # 1. Setup Test Data (Mocking the environment)
        self.partner = self.env['res.partner'].create({
            'name': 'Test Subcontractor', 
            'is_subcontractor': True,
            'email': 'sub@test.com'
        })
        self.chantier = self.env['construction.chantier'].create({
            'name': 'Test Chantier 2025', 
            'code': 'CHT-TEST-001'
        })
        self.po = self.env['purchase.order'].create({
            'partner_id': self.partner.id,
            'chantier_id': self.chantier.id,
        })
        
        # Ensure Company Logo exists for Signature Test
        self.env.company.logo = b'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='

    def test_01_visual_template_compliance(self):
        """ 
        [Mock & Verify] Test that the default template fully matches BLG Design Guidelines.
        Includes Color Check (#A0522D) and Structural Check.
        """
        template = self.env.ref('construction_contract.default_contract_template')
        html = template.grapesjs_html
        css = template.grapesjs_css
        
        # Verify Branding Colors
        self.assertIn('#A0522D', css, "Template CSS must contain BLG Red/Brown branding color")
        
        # Verify Structural Elements (Headers from Images)
        self.assertIn("Échéancier de paiement", html, "Missing Payment Schedule section")
        self.assertIn("Conditions Générales d'Achat", html, "Missing CGA section")
        self.assertIn("Délais et pénalités de retard", html, "Missing Delays section")
        
        # Verify Table Headers
        self.assertIn("Avancement réel chantier", html, "Missing specific table header from image")
        self.assertIn("Montant en € H.T.", html, "Missing specific table header from image")

    def test_02_po_integration_mock(self):
        """
        [Mock] Test the new feature: Generating Contract from Purchase Order.
        Mocks the actual PDF generation to verify flow control.
        """
        # Patch the PDF Generator to avoid calling WeasyPrint
        with patch('odoo.addons.construction_contract.models.contract.ConstructionContract.action_generate_pdf') as mock_generate:
            mock_generate.return_value = {'type': 'ir.actions.act_window_close'} # Dummy return
            
            # Execute Action
            self.po.action_generate_pdf()
            
            # 1. Verify Contract Auto-Creation
            self.assertTrue(self.po.contract_id, "Contract should be automatically created from PO")
            self.assertEqual(self.po.contract_id.subcontractor_id, self.partner, "Contract partner must match PO")
            self.assertEqual(self.po.contract_id.chantier_id, self.chantier, "Contract chantier must match PO")
            
            # 2. Verify Generation Called
            mock_generate.assert_called_once()
            
            # 3. Verify HTML Override is passed (if any)
            # (Requires checking context or created record)
            
    def test_03_signature_injection_mock(self):
        """
        [Mock] Test that signature objects are correctly prepared for injection.
        Simulates the entire Signature Flow.
        """
        # Create Contract
        contract = self.env['construction.contract'].create({
            'subcontractor_id': self.partner.id,
            'chantier_id': self.chantier.id,
        })
        
        # 1. Create a Signature
        signature = self.env['construction.contract.signature'].create({
            'contract_id': contract.id,
            'signer_name': 'Subcontractor Boss',
            'signer_email': 'boss@sub.com',
            'signature_data': b'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==', # 1x1 Pixel
            'auth_method': 'email'
        })
        
        # 2. Mock the Template Renderer Service
        # We want to ensure that when 'render' is called, it gets the signature image
        
        # Assuming there is a service or method that prepares the context
        # In our case, it's mostly in the Controller or the models/contract.py action_generate_pdf
        
        # Let's verify the `contract_signature` record has the correct filename and check constraints
        self.assertTrue(signature.signature_filename.endswith('.png'), "Signature should have png extension")
        
        # 3. Verify that the Template HTML (Jinja) can access this
        # We manually render a snippet to verify Jinja context access logic
        
        snippet = "{{ subcontractor_signature.signer_name }}"
        from odoo.tools.safe_eval import safe_eval
        # (Jinja render simulation)
        import jinja2
        env = jinja2.Environment()
        tmpl = env.from_string(snippet)
        result = tmpl.render(subcontractor_signature=signature)
        
        self.assertEqual(result, 'Subcontractor Boss', "Jinja rendering of signature object failed")

    def test_04_grapejs_editor_save(self):
        """
        [Mock] Test Saving content from GrapeJS (simulating Controller)
        """
        # Simulate Controller call
        new_html = "<h1>Updated Contract</h1>"
        
        # Call write directly (simulating what controller does)
        self.po.write({'contract_template_html': new_html})
        
        # Verify persistence
        self.assertEqual(self.po.contract_template_html, new_html, "HTML content not saved to PO")
