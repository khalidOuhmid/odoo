# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.exceptions import AccessError, ValidationError
from .common import ContractTestMixin
import base64

@tagged('post_install', '-at_install', 'construction_contract_security')
class TestContractSecurity(TransactionCase, ContractTestMixin):
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.setUpContractData()

    def test_sec_01_unauthorized_token_use(self):
        """SC_SEC_01 – Accès non autorisé (Bad Token)"""
        self.contract.action_generate_pdf()
        self.contract.action_send_for_signature()
        
        bad_token = "invalid_token_12345"
        
        # Try to validate page with bad token
        with self.assertRaises(ValidationError):
            self.contract.portal_validate_page(1, bad_token)
            
        # Try to sign with bad token
        with self.assertRaises(ValidationError):
            self.contract.portal_save_signature("data:...", bad_token)

    def test_sec_02_html_injection(self):
        """SC_SEC_02 – Injection & altération de template"""
        # Inject malicious HTML in variable
        malicious_name = '<script>alert("Hacked")</script><b>Bold</b>'
        self.subcontractor.name = malicious_name
        
        # Generate Context
        ctx = self.contract._get_contract_data_context()
        
        # Verify sanitization
        # We expect escaped chars
        self.assertIn('&lt;script&gt;', ctx['partner_name'])
        self.assertNotIn('<script>', ctx['partner_name'])
        
        # Check if PDF generation crashes or includes script
        # (Assuming PDF gen works)
        # self.contract.action_generate_pdf()
        # pdf_content = base64.b64decode(self.contract.pdf_document)
        # self.assertNotIn(b'<script>', pdf_content) # PDF is binary, but text stream usually compressed. 
        # Only HTML check is reliable.

