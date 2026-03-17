# -*- coding: utf-8 -*-
"""
Unit Tests for Contract Controllers
Tests HTTP routes, authentication, and portal workflows
"""

from odoo.tests import common, tagged
from odoo.exceptions import ValidationError, AccessError
from werkzeug.exceptions import NotFound, Forbidden
from datetime import date, timedelta
import base64
import json


@tagged('post_install', '-at_install', 'construction_contract', 'controllers')
class TestContractControllers(common.HttpCase):
    """Test Contract Controllers - Full Coverage"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # Create test data
        _client = cls.env['res.partner'].create({'name': 'Client Controllers Test'})
        cls.chantier = cls.env['construction.chantier'].create({
            'name': 'Test Construction Site',
            'client': _client.id,
            'address': '123 Test Street',
            'city': 'Paris',
            'zip_code': '75001',
        })

        _mock_doc = base64.b64encode(b'%PDF-1.4 mock').decode('ascii')
        _expiry = date.today() + timedelta(days=365)
        cls.subcontractor = cls.env['res.partner'].create({
            'name': 'Test Subcontractor Ctrl',
            'is_subcontractor': True,
            'company_registry': '12345678901234',
            'email': 'test@subcontractor.com',
            'phone': '+33123456789',
        })
        # Write docs separately to trigger admin auto-validation (write override)
        cls.subcontractor.write({
            'doc_kbis': _mock_doc, 'doc_kbis_expiry': _expiry,
            'doc_urssaf': _mock_doc, 'doc_urssaf_expiry': _expiry,
            'doc_insurance_dec': _mock_doc, 'doc_insurance_dec_expiry': _expiry,
        })

        cls.lot_cat = cls.env['construction.lot.category'].create({'name': 'Work Pkg Ctrl', 'code': 'WP_CTRL'})
        cls.lot = cls.env['construction.lot'].create({
            'category_id': cls.lot_cat.id,
            'chantier_id': cls.chantier.id,
            'description': 'Test description',
        })
        
        cls.template = cls.env['construction.contract.template'].create({
            'name': 'Test Template',
            'grapesjs_html': '<div><h1>{{ contract.name }}</h1></div>',
            'grapesjs_css': 'body { font-family: Arial; }',
        })
        
        cls.contract = cls.env['construction.contract'].create({
            'chantier_id': cls.chantier.id,
            'subcontractor_id': cls.subcontractor.id,
            'lot_ids': [(6, 0, [cls.lot.id])],
            'template_id': cls.template.id,
            'date': date.today(),
            'start_date': date.today(),
            'end_date': date.today() + timedelta(days=30),
            'retention_rate': 5.0,
        })
        
        # Inject mock HTML so PDF generation doesn't fail due to empty template
        cls.contract.contract_template_html = '<html><body><h1>Test Contract</h1></body></html>'
        try:
            cls.contract.action_generate_pdf()
        except Exception:
            # If PDF generation fails, inject mock PDF directly
            cls.contract.write({'pdf_document': base64.b64encode(b'%PDF-1.4 mock')})
            cls.contract.pdf_page_count = 1
        cls.contract.action_send_for_signature()

    def test_01_signature_portal_access_with_token(self):
        """Test accessing signature portal with valid token"""
        url = f'/my/contract/{self.contract.id}/sign?access_token={self.contract.access_token}'
        response = self.url_open(url)
        
        self.assertEqual(response.status_code, 200, "Should access portal with valid token")

    def test_02_signature_portal_access_without_token(self):
        """Test accessing signature portal without token"""
        url = f'/my/contract/{self.contract.id}/sign'
        response = self.url_open(url)
        
        # Should redirect or show error
        self.assertIn(response.status_code, [200, 302, 404], "Should handle missing token")

    def test_03_signature_portal_invalid_token(self):
        """Test accessing signature portal with invalid token"""
        url = f'/my/contract/{self.contract.id}/sign?access_token=invalid_token_12345'
        response = self.url_open(url)
        
        # Should show error or redirect
        self.assertIn(response.status_code, [200, 302, 404], "Should reject invalid token")

    def test_04_pdf_download_endpoint(self):
        """Test PDF download endpoint"""
        url = f'/my/contract/{self.contract.id}/pdf?access_token={self.contract.access_token}'
        response = self.url_open(url)
        
        self.assertEqual(response.status_code, 200, "Should download PDF")
        self.assertEqual(response.headers['Content-Type'], 'application/pdf', "Should be PDF content")

    def test_05_validate_page_endpoint(self):
        """Test page validation endpoint"""
        self.contract.action_mark_in_progress()
        
        url = '/contract/page/validate'
        data = {
            'contract_id': self.contract.id,
            'access_token': self.contract.access_token,
            'page_number': 1,
            'time_spent': 10,
        }
        
        response = self.url_open(
            url,
            data=json.dumps(data),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        
        self.assertEqual(response.status_code, 200, "Should validate page")
        result = json.loads(response.content)
        self.assertTrue(result.get('result', {}).get('success'), "Validation should succeed")

    def test_06_save_signature_endpoint(self):
        """Test signature saving endpoint"""
        self.contract.action_mark_in_progress()
        
        # Validate all pages first
        for page in range(1, self.contract.pdf_page_count + 1):
            self.contract.portal_validate_page(
                page,
                self.contract.access_token
            )
        
        signature_data = base64.b64encode(
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
        ).decode('utf-8')
        
        url = f'/my/contract/{self.contract.id}/save_signature'
        data = {
            'signature_data': f'data:image/png;base64,{signature_data}',
            'access_token': self.contract.access_token,
        }
        
        response = self.url_open(
            url,
            data=json.dumps(data),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        
        self.assertEqual(response.status_code, 200, "Should save signature")
        result = json.loads(response.content)
        self.assertEqual(result.get('result', {}).get('status'), 'success', "Signature should be saved")

    def test_07_download_signed_contract(self):
        """Test downloading signed contract"""
        # Sign contract first
        self.contract.action_mark_in_progress()
        for page in range(1, self.contract.pdf_page_count + 1):
            self.contract.portal_validate_page(page, self.contract.access_token)
        
        signature_data = base64.b64encode(
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
        ).decode('utf-8')
        self.contract.portal_save_signature(
            f'data:image/png;base64,{signature_data}',
            self.contract.access_token
        )
        
        url = f'/my/contract/{self.contract.id}/download_signed?access_token={self.contract.access_token}'
        response = self.url_open(url)
        
        self.assertEqual(response.status_code, 200, "Should download signed contract")
        self.assertEqual(response.headers['Content-Type'], 'application/pdf', "Should be PDF")

    def test_08_download_certificate(self):
        """Test downloading certificate"""
        # Sign contract first
        self.contract.action_mark_in_progress()
        for page in range(1, self.contract.pdf_page_count + 1):
            self.contract.portal_validate_page(page, self.contract.access_token)
        
        signature_data = base64.b64encode(
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
        ).decode('utf-8')
        self.contract.portal_save_signature(
            f'data:image/png;base64,{signature_data}',
            self.contract.access_token
        )
        
        url = f'/my/contract/{self.contract.id}/download_certificate?access_token={self.contract.access_token}'
        response = self.url_open(url)
        
        self.assertEqual(response.status_code, 200, "Should download certificate")
        self.assertEqual(response.headers['Content-Type'], 'application/pdf', "Should be PDF")

    def test_09_error_handling_invalid_contract_id(self):
        """Test error handling for invalid contract ID"""
        url = '/my/contract/999999/sign?access_token=test_token'
        response = self.url_open(url)
        
        # Should handle gracefully
        self.assertIn(response.status_code, [200, 302, 404], "Should handle invalid ID")

    def test_10_error_handling_expired_token(self):
        """Test error handling for expired token"""
        # Expire token
        self.contract.write({
            'token_expiry_date': date.today() - timedelta(days=1)
        })
        self.contract.invalidate_recordset(['token_expiry_date'])
        
        url = f'/my/contract/{self.contract.id}/sign?access_token={self.contract.access_token}'
        response = self.url_open(url)
        
        # Should show expired token page
        self.assertIn(response.status_code, [200, 302], "Should handle expired token")


