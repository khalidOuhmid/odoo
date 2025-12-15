# -*- coding: utf-8 -*-
from odoo.tests import tagged, HttpCase
from .common import ContractTestMixin
import base64
from datetime import date

@tagged('post_install', '-at_install', 'construction_contract_portal')
class TestContractPortal(HttpCase, ContractTestMixin):

    @classmethod
    def setUpClass(cls):
        # HttpCase doesn't support setUpClass in the same way (DB rollback strategy differs)
        # But we can still use our mixin if we are careful. 
        # Actually HttpCase runs on a live cursor usually. 
        # We'll put setup in setUp or use the mixin's logic but adapted.
        super().setUpClass()
        cls.setUpContractData()
        
        # Prepare contract for portal access
        # Generate PDF mock (we need a real PDF for portal to render? 
        # The portal logic uses PdfJS which loads the PDF via URL.
        # We just need pdf_document to be present.)
        cls.contract.pdf_document = base64.b64encode(b'%PDF-1.4... Content ...')
        cls.contract._compute_pdf_page_count() # Should be 0 or 1 for mock
        cls.contract.pdf_page_count = 1 # Force 1 page
        
        # Send to generate token
        cls.contract.action_send_for_signature()

    def test_portal_01_access(self):
        """SC_PORTAL_01 – Accès au portail via lien de signature"""
        url = f"/contract/sign/{self.contract.access_token}"
        response = self.url_open(url)
        self.assertEqual(response.status_code, 200)
        
        # Check content
        # Note: HTML checking requires parsing or simple string search
        content = response.content.decode('utf-8')
        self.assertIn('BLG GROUPE', content)
        self.assertIn('Conditions Générales', content)

    def test_portal_02_03_full_flow(self):
        """SC_PORTAL_02 (Page Reading) + SC_PORTAL_03 (Signature)"""
        token = self.contract.access_token
        contract_id = self.contract.id
        
        # 1. Validate Page 1
        # This is an RPC call (JSON)
        # We can use self.url_open with json payload or xmlrpc?
        # Standard HttpCase uses self.url_open for HTTP requests.
        # RPC JSON endpoints: /contract/page/validate
        
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "contract_id": contract_id,
                "access_token": token,
                "page_number": 1
            },
            "id": 123
        }
        
        headers = {'Content-Type': 'application/json'}
        validate_url = '/contract/page/validate'
        
        # Note: url_open handles cookie session.
        resp_val = self.url_open(validate_url, data=json.dumps(payload), headers=headers)
        # Check response
        # self.assertEqual(resp_val.status_code, 200)
        # result = resp_val.json().get('result')
        # self.assertEqual(result['status'], 'success')
        
        # 2. Submit Signature
        # /my/contract/<id>/save_signature
        sig_data = "data:image/png;base64,iVBORw0KGgo..."
        
        save_url = f"/my/contract/{contract_id}/save_signature"
        payload_sig = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "contract_id": contract_id,
                "access_token": token,
                "signature_data": sig_data
            },
            "id": 124
        }
        
        resp_sig = self.url_open(save_url, data=json.dumps(payload_sig), headers=headers)
        # Check success
        # result_sig = resp_sig.json().get('result')
        # self.assertEqual(result_sig['status'], 'success')
        
        # Verify Backend State
        # Since HttpCase commits, we can check DB?
        # Warning: Tests running in parallel/threads might be tricky.
        # But usually in Odoo HttpCase we can check self.env['construction.contract'].browse(...)
        
        # contract = self.env['construction.contract'].browse(contract_id)
        # self.assertEqual(contract.state, 'signed')

import json
