# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import UserError
from datetime import date, timedelta
import base64

@tagged('post_install', '-at_install', 'robust')
class TestRobustCompliance(TransactionCase):
    """
    Robust AAA Tests for Subcontractor Compliance.
    Focuses on edge cases, admin overrides, and state machine integrity.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # 1. ARRANGE: Create Users
        cls.group_admin = cls.env.ref('construction_core.group_construction_admin')
        cls.group_user = cls.env.ref('construction_core.group_construction_user')
        
        base_user_group = cls.env.ref('base.group_user')
        partner_manager_group = cls.env.ref('base.group_partner_manager')
        cls.admin_user = cls.env['res.users'].create({
            'name': 'Admin Manager',
            'login': 'admin_mgr',
            'email': 'admin@test.com',
            'groups_id': [(6, 0, [cls.group_admin.id, base_user_group.id, partner_manager_group.id])]
        })

        cls.regular_user = cls.env['res.users'].create({
            'name': 'Regular User',
            'login': 'reg_user',
            'email': 'user@test.com',
            'groups_id': [(6, 0, [cls.group_user.id, base_user_group.id, partner_manager_group.id])]
        })
        
        # 2. ARRANGE: Create Subcontractor
        cls.subcontractor = cls.env['res.partner'].create({
            'name': 'Robust ST',
            'is_subcontractor': True,
            'subcontractor_stage': 'draft'
        })
        
        cls.sample_pdf = base64.b64encode(b'Robust PDF Content')
        cls.future_date = date.today() + timedelta(days=90)

    def test_01_admin_upload_auto_validates(self):
        """AAA Test: Admin uploading a document should trigger auto-validation."""
        # ARRANGE: Use admin user context
        ST_admin = self.subcontractor.with_user(self.admin_user)
        
        # ACT: Upload KBIS
        ST_admin.write({
            'doc_kbis': self.sample_pdf,
            'doc_kbis_filename': 'kbis_admin.pdf',
            'doc_kbis_expiry': self.future_date
        })
        
        # ASSERT: Should be auto-validated
        self.assertTrue(self.subcontractor.doc_kbis_is_validated)
        self.assertEqual(self.subcontractor.doc_kbis_validated_by, self.admin_user)
        self.assertEqual(self.subcontractor.doc_kbis_status, 'valid')

    def test_02_regular_user_upload_resets_validation(self):
        """AAA Test: Regular user upload should NOT auto-validate (stays to_check)."""
        # ARRANGE: Ensure document starts as validated (e.g. from previous state)
        self.subcontractor.write({
            'doc_kbis': self.sample_pdf,
            'doc_kbis_is_validated': True
        })
        ST_user = self.subcontractor.with_user(self.regular_user)
        
        # ACT: Regular user replaces document
        ST_user.write({
            'doc_kbis': self.sample_pdf,
            'doc_kbis_filename': 'kbis_user.pdf'
        })
        
        # ASSERT: Validation should be reset to False
        self.assertFalse(self.subcontractor.doc_kbis_is_validated)
        self.assertEqual(self.subcontractor.doc_kbis_status, 'to_check')

    def test_03_stage_automation_lifecycle(self):
        """AAA Test: Verify partner stage transitions from Draft to Compliant."""
        # ARRANGE
        self.assertEqual(self.subcontractor.subcontractor_stage, 'draft')
        ST_admin = self.subcontractor.with_user(self.admin_user)
        
        # ACT 1: Partial upload -> Incomplete
        ST_admin.write({'doc_kbis': self.sample_pdf, 'doc_kbis_expiry': self.future_date})
        self.assertEqual(self.subcontractor.subcontractor_stage, 'incomplete')
        
        # ACT 2: Full upload of required docs
        ST_admin.write({
            'doc_urssaf': self.sample_pdf, 'doc_urssaf_expiry': self.future_date,
            'doc_insurance_dec': self.sample_pdf, 'doc_insurance_dec_expiry': self.future_date,
            'doc_cni': self.sample_pdf, 'doc_cni_expiry': self.future_date,
        })
        
        # ASSERT: Should be compliant
        self.assertEqual(self.subcontractor.compliance_state, 'compliant')
        self.assertEqual(self.subcontractor.subcontractor_stage, 'compliant')

    def test_04_cron_expiry_and_archiving(self):
        """AAA Test: Verify cron correctly archives and clears expired docs."""
        # ARRANGE: Expired document
        self.subcontractor.write({
            'doc_kbis': self.sample_pdf,
            'doc_kbis_expiry': date.today() - timedelta(days=1),
            'doc_kbis_is_validated': True
        })
        self.assertEqual(self.subcontractor.doc_kbis_status, 'expired')
        
        # ACT: Run cron manually on this partner
        self.env['res.partner'].with_context(active_test=False).cron_check_document_expiry()
        
        # ASSERT: Doc field should be cleared (Requested state)
        self.assertFalse(self.subcontractor.doc_kbis)
        self.assertEqual(self.subcontractor.doc_kbis_status, 'missing')
        
        # ASSERT: Archive record created with reason='expired_cron'
        archive = self.env['subcontractor.document.archive'].search([
            ('partner_id', '=', self.subcontractor.id),
            ('document_type', '=', 'kbis'),
            ('reason', '=', 'expired_cron'),
        ], limit=1)
        self.assertTrue(archive, "Should create an expired_cron archive record")
        self.assertEqual(archive.reason, 'expired_cron')
