# -*- coding: utf-8 -*-
"""
Portal Controller Tests

HTTP tests for subcontractor document upload portal endpoints.
Tests token validation, staging workflow, and submission.
"""
from odoo.tests.common import HttpCase, tagged
from datetime import datetime, timedelta
import base64
import json


@tagged('post_install', '-at_install')
class TestPortalController(HttpCase):
    """Test suite for portal upload controller endpoints."""
    
    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        
        # Create test subcontractor with upload token
        self.partner = self.env['res.partner'].create({
            'name': 'Test Portal Partner',
            'is_subcontractor': True,
            'supplier_rank': 1,
            'email': 'portal@test.com',
        })
        
        # Generate upload token
        self.partner.action_generate_upload_link()
        self.token = self.partner.upload_token
    
    # ============= PAGE ACCESS TESTS ============= #
    
    def test_upload_page_accessible_with_valid_token(self):
        """Upload page should be accessible with valid token."""
        response = self.url_open(f'/subcontractor/upload/{self.token}')
        
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Portail Partenaire', response.content)
    
    def test_upload_page_denied_with_invalid_token(self):
        """Upload page should show error with invalid token."""
        response = self.url_open('/subcontractor/upload/invalid_token_12345')
        
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'invalide', response.content.lower())
    
    def test_upload_page_denied_with_expired_token(self):
        """Upload page should show error with expired token."""
        # Expire the token
        self.partner.write({
            'token_expiration': datetime.now() - timedelta(days=1)
        })
        
        response = self.url_open(f'/subcontractor/upload/{self.token}')
        
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'expir', response.content.lower())
    
    # ============= STAGING ENDPOINT TESTS ============= #
    
    def test_stage_document_requires_file(self):
        """Stage endpoint should require a file."""
        response = self.url_open(
            f'/subcontractor/upload/{self.token}/stage',
            data={'doc_key': 'kbis'},
        )
        
        result = json.loads(response.content)
        self.assertFalse(result.get('success', True))
    
    def test_stage_document_requires_doc_key(self):
        """Stage endpoint should require doc_key parameter."""
        response = self.url_open(
            f'/subcontractor/upload/{self.token}/stage',
            data={},
        )
        
        result = json.loads(response.content)
        self.assertFalse(result.get('success', True))
    
    # ============= SESSION STATE TESTS ============= #
    
    def test_session_state_returns_empty_initially(self):
        """Session state should return empty for new session."""
        response = self.url_open(
            f'/subcontractor/upload/{self.token}/session-state',
            data=json.dumps({}),
            headers={'Content-Type': 'application/json'},
        )
        
        result = json.loads(response.content)
        self.assertTrue(result.get('success'))
        self.assertEqual(result.get('staged_count'), 0)
    
    # ============= SUBMIT TESTS ============= #
    
    def test_submit_all_with_empty_session_returns_error(self):
        """Submit all should return error when session is empty."""
        response = self.url_open(
            f'/subcontractor/upload/{self.token}/submit-all',
            data=json.dumps({}),
            headers={'Content-Type': 'application/json'},
        )
        
        result = json.loads(response.content)
        self.assertFalse(result.get('success', True))
    
    def test_submit_single_with_invalid_token_fails(self):
        """Submit single should fail with invalid token."""
        response = self.url_open(
            '/subcontractor/upload/invalid_token/submit-single',
            data=json.dumps({
                'doc_key': 'kbis',
                'file_base64': base64.b64encode(b'test').decode(),
                'filename': 'test.pdf'
            }),
            headers={'Content-Type': 'application/json'},
        )
        
        result = json.loads(response.content)
        self.assertFalse(result.get('success', True))
    
    # ============= CLEAR STAGED TESTS ============= #
    
    def test_clear_staged_succeeds(self):
        """Clear staged should succeed even with empty session."""
        response = self.url_open(
            f'/subcontractor/upload/{self.token}/clear-staged',
            data=json.dumps({}),
            headers={'Content-Type': 'application/json'},
        )
        
        result = json.loads(response.content)
        self.assertTrue(result.get('success'))
