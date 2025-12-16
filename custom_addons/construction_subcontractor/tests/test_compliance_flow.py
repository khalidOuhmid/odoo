# -*- coding: utf-8 -*-
"""
Compliance Flow Tests - Subcontractor Document Compliance

Comprehensive tests for document status computation, compliance states,
and automated stage transitions with SAP-style state coverage.
"""
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError, UserError
from datetime import date, timedelta
import base64

@tagged('post_install', '-at_install')
class TestComplianceFlow(TransactionCase):
    """Test suite for subcontractor compliance state machine."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures for all test methods."""
        super().setUpClass()
        
        # Create test partner (subcontractor)
        cls.Partner = cls.env['res.partner']
        cls.Wizard = cls.env['subcontractor.assignment.wizard']
        
        cls.plumber = cls.Partner.create({
            'name': 'Mario Bros Plomberie',
            'is_subcontractor': True,
            'supplier_rank': 1,
            'email': 'mario@plomberie.test',
        })
        
        # Create a generic client partner for chantier
        cls.client_partner = cls.Partner.create({
            'name': 'Test Client',
            'is_company': True,
            'email': 'client@test.com',
        })
        
        # Create chantier and lot for assignment tests
        cls.Chantier = cls.env['construction.chantier']
        cls.Lot = cls.env['construction.lot']
        
        cls.chantier = cls.Chantier.create({
            'name': 'Test Chantier',
            'client': cls.client_partner.id,
            'address': '123 Test St',
            'company_id': cls.env.company.id,
        })
        
        category = cls.env['construction.lot.category'].create({
            'name': 'Plomberie',
            'code': 'PLB',
        })
        
        cls.lot = cls.Lot.create({
            'name': 'Lot Plomberie',
            'code': 'LOT-PLOMB-01',
            'category_id': category.id,
            'chantier_id': cls.chantier.id,
            'execution_type': 'external',
            'sequence': 10,
        })
        
        cls.sample_doc = base64.b64encode(b'Test PDF Content')
        cls.future_date = date.today() + timedelta(days=90)
        cls.expired_date = date.today() - timedelta(days=1)
        cls.expiring_soon_date = date.today() + timedelta(days=15)

    def _validate_all_docs(self):
        """Helper to validate all uploaded documents for plumber."""
        vals = {}
        for key in ['kbis', 'urssaf', 'insurance_dec', 'insurance_pro', 'cni', 'rib']:
            if getattr(self.plumber, f'doc_{key}'):
                vals[f'doc_{key}_is_validated'] = True
        if vals:
            self.plumber.write(vals)
    
    # ============= DOCUMENT STATUS TESTS ============= #
    
    def test_status_missing_when_no_document(self):
        """Document status should be 'missing' when no file uploaded."""
        self.assertEqual(
            self.plumber.doc_kbis_status, 'missing',
            "Status should be 'missing' when no document"
        )
    
    def test_status_valid_with_future_expiry(self):
        """Document status should be 'valid' with future expiry date."""
        self.plumber.write({
            'doc_kbis': self.sample_doc,
            'doc_kbis_expiry': self.future_date,
        })
        self._validate_all_docs()
        self.assertEqual(
            self.plumber.doc_kbis_status, 'valid',
            "Status should be 'valid' with future expiry"
        )
    
    def test_status_expired_with_past_date(self):
        """Document status should be 'expired' when expiry date is past."""
        self.plumber.write({
            'doc_kbis': self.sample_doc,
            'doc_kbis_expiry': self.expired_date,
        })
        self._validate_all_docs()
        self.assertEqual(
            self.plumber.doc_kbis_status, 'expired',
            "Status should be 'expired' with past expiry date"
        )
    
    def test_status_expiring_when_within_threshold(self):
        """Document status should be 'expiring' when within warning threshold."""
        self.plumber.write({
            'doc_kbis': self.sample_doc,
            'doc_kbis_expiry': self.expiring_soon_date,
        })
        self._validate_all_docs()
        self.assertEqual(
            self.plumber.doc_kbis_status, 'expiring',
            "Status should be 'expiring' when expiry is within 30 days"
        )
    
    # ============= COMPLIANCE STATE TESTS ============= #
    
    def test_compliance_missing_when_no_docs(self):
        """Compliance state should be 'missing' when required documents absent."""
        self.assertEqual(
            self.plumber.compliance_state, 'missing',
            "Compliance should be 'missing' when no documents"
        )
    
    def test_compliance_compliant_with_all_valid_docs(self):
        """Compliance state should be 'compliant' when all required docs valid."""
        self.plumber.write({
            'doc_kbis': self.sample_doc,
            'doc_kbis_expiry': self.future_date,
            'doc_urssaf': self.sample_doc,
            'doc_urssaf_expiry': self.future_date,
            'doc_insurance_dec': self.sample_doc,
            'doc_insurance_dec_expiry': self.future_date,
            'doc_cni': self.sample_doc,
            'doc_cni_expiry': self.future_date,
        })
        self._validate_all_docs()
        self.assertEqual(
            self.plumber.compliance_state, 'compliant',
            "Compliance should be 'compliant' with all valid required docs"
        )
    
    def test_compliance_incomplete_with_partial_docs(self):
        """Compliance state should be 'incomplete' with only some docs."""
        self.plumber.write({
            'doc_kbis': self.sample_doc,
            'doc_kbis_expiry': self.future_date,
            # Missing other required docs
        })
        self._validate_all_docs()
        self.assertEqual(
            self.plumber.compliance_state, 'incomplete',
            "Compliance should be 'incomplete' with partial documents"
        )
    
    def test_compliance_expired_with_one_expired_doc(self):
        """Compliance state should be 'expired' if any required doc expired."""
        self.plumber.write({
            'doc_kbis': self.sample_doc,
            'doc_kbis_expiry': self.expired_date,  # This one expired
            'doc_urssaf': self.sample_doc,
            'doc_urssaf_expiry': self.future_date,
            'doc_insurance_dec': self.sample_doc,
            'doc_insurance_dec_expiry': self.future_date,
            'doc_cni_expiry': self.future_date,
        })
        self._validate_all_docs()
        self.assertEqual(
            self.plumber.compliance_state, 'expired',
            "Compliance should be 'expired' when any required doc is expired"
        )
    
    # ============= ALERT LEVEL TESTS ============= #
    
    def test_alert_level_false_when_no_docs(self):
        """Alert level should be False when no documents exist."""
        self.assertFalse(
            self.plumber.alert_level,
            "Alert level should be False with no documents"
        )
    
    def test_alert_level_green_when_all_valid(self):
        """Alert level should be 'green' when all docs valid with >30 days."""
        self.plumber.write({
            'doc_kbis': self.sample_doc,
            'doc_kbis_expiry': date.today() + timedelta(days=60),
            'doc_urssaf': self.sample_doc,
            'doc_urssaf_expiry': date.today() + timedelta(days=60),
            'doc_insurance_dec': self.sample_doc,
            'doc_insurance_dec_expiry': date.today() + timedelta(days=60),
            'doc_cni_expiry': date.today() + timedelta(days=60),
        })
        self._validate_all_docs()
        self.assertEqual(
            self.plumber.alert_level, 'green',
            "Alert level should be 'green' with all valid docs >30 days"
        )
    
    def test_alert_level_yellow_when_expiring_soon(self):
        """Alert level should be 'yellow' when doc expires within 30 days."""
        self.plumber.write({
            'doc_kbis': self.sample_doc,
            'doc_kbis_expiry': date.today() + timedelta(days=20),
            'doc_urssaf': self.sample_doc,
            'doc_urssaf_expiry': date.today() + timedelta(days=60),
            'doc_insurance_dec': self.sample_doc,
            'doc_insurance_dec_expiry': date.today() + timedelta(days=60),
            'doc_cni_expiry': date.today() + timedelta(days=60),
        })
        self._validate_all_docs()
        self.assertEqual(
            self.plumber.alert_level, 'yellow',
            "Alert level should be 'yellow' when any doc expires within 30 days"
        )
    
    def test_alert_level_red_when_expired(self):
        """Alert level should be 'red' when any doc is expired."""
        self.plumber.write({
            'doc_kbis': self.sample_doc,
            'doc_kbis_expiry': self.expired_date,
            'doc_urssaf': self.sample_doc,
            'doc_urssaf_expiry': self.future_date,
            'doc_insurance_dec': self.sample_doc,
            'doc_insurance_dec_expiry': self.future_date,
            'doc_cni_expiry': self.future_date,
        })
        self._validate_all_docs()
        self.assertEqual(
            self.plumber.alert_level, 'red',
            "Alert level should be 'red' with any expired document"
        )
    
    # ============= ASSIGNMENT WIZARD TESTS ============= #
    
    def test_wizard_blocked_without_decennale(self):
        """Wizard should block assignment without valid Décennale."""
        wizard = self.Wizard.create({
            'lot_id': self.lot.id,
            'partner_id': self.plumber.id
        })
        
        self.assertTrue(
            wizard.is_blocked,
            "Wizard should be blocked without Décennale"
        )
        self.assertIn(
            'Décennale', wizard.blocking_reasons,
            "Blocking reason should mention Décennale"
        )
    
    def test_wizard_blocked_assignment_raises_error(self):
        """Attempting to confirm blocked wizard should raise UserError."""
        wizard = self.Wizard.create({
            'lot_id': self.lot.id,
            'partner_id': self.plumber.id
        })
        
        with self.assertRaises(UserError):
            wizard.action_confirm()
    
    def test_wizard_force_assignment_requires_reason(self):
        """Force assignment without reason should raise UserError."""
        wizard = self.Wizard.create({
            'lot_id': self.lot.id,
            'partner_id': self.plumber.id
        })
        wizard.force_assignment = True
        
        with self.assertRaises(UserError):
            wizard.action_confirm()
    
    def test_wizard_force_assignment_with_reason_succeeds(self):
        """Force assignment with reason should succeed."""
        wizard = self.Wizard.create({
            'lot_id': self.lot.id,
            'partner_id': self.plumber.id
        })
        wizard.force_assignment = True
        wizard.force_reason = "Urgent project requirement"
        
        wizard.action_confirm()
        
        self.assertEqual(
            self.lot.subcontractor_id, self.plumber,
            "Subcontractor should be assigned after force"
        )
    
    def test_wizard_compliant_assignment_succeeds(self):
        """Assignment should succeed with compliant subcontractor."""
        # Make subcontractor compliant
        self.plumber.write({
            'doc_kbis': self.sample_doc,
            'doc_kbis_expiry': self.future_date,
            'doc_urssaf': self.sample_doc,
            'doc_urssaf_expiry': self.future_date,
            'doc_insurance_dec': self.sample_doc,
            'doc_insurance_dec_expiry': self.future_date,
            'doc_cni_expiry': self.future_date,
        })
        self._validate_all_docs()
        
        wizard = self.Wizard.create({
            'lot_id': self.lot.id,
            'partner_id': self.plumber.id
        })
        
        self.assertFalse(
            wizard.is_blocked,
            "Wizard should not be blocked for compliant subcontractor"
        )
        
        wizard.action_confirm()
        
        self.assertEqual(
            self.lot.subcontractor_id, self.plumber,
            "Subcontractor should be assigned"
        )
    
    # ============= STAGE AUTOMATION TESTS ============= #
    
    def test_stage_updates_on_document_upload(self):
        """Subcontractor stage should update when documents uploaded."""
        self.plumber.subcontractor_stage = 'draft'
        
        # Upload all required docs
        self.plumber.write({
            'doc_kbis': self.sample_doc,
            'doc_kbis_expiry': self.future_date,
            'doc_urssaf': self.sample_doc,
            'doc_urssaf_expiry': self.future_date,
            'doc_insurance_dec': self.sample_doc,
            'doc_insurance_dec_expiry': self.future_date,
            'doc_cni_expiry': self.future_date,
        })
        self._validate_all_docs()
        
        self.assertEqual(
            self.plumber.subcontractor_stage, 'compliant',
            "Stage should auto-update to 'compliant'"
        )
    
    # ============= CRON TESTS ============= #
    
    def test_cron_creates_activity_for_expired_docs(self):
        """Cron should create activity for expired documents."""
        self.plumber.write({
            'doc_kbis': self.sample_doc,
            'doc_kbis_expiry': self.expired_date,
            'doc_urssaf': self.sample_doc,
            'doc_urssaf_expiry': self.future_date,
            'doc_insurance_dec': self.sample_doc,
            'doc_insurance_dec_expiry': self.future_date,
            'doc_cni_expiry': self.future_date,
        })
        self._validate_all_docs()
        
        # Run cron
        self.Partner.cron_check_document_expiry()
        
        # Check for activity
        activity = self.env['mail.activity'].search([
            ('res_id', '=', self.plumber.id),
            ('res_model', '=', 'res.partner'),
            ('summary', '=', 'Documents expirés')
        ])
        self.assertTrue(activity, "Should create activity for expired docs")
