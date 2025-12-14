# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError, UserError, AccessError
from datetime import date, timedelta
from odoo.tools import mute_logger
from odoo import fields

@tagged('post_install', '-at_install')
class TestComplianceFlow(TransactionCase):

        
        # Create Wizard
        wizard = self.Wizard.create({
            'lot_id': self.lot.id,
            'partner_id': self.plumber.id
        })
        
        # Verify Blocked
        self.assertTrue(wizard.is_blocked, "Wizard should be blocked")
        self.assertTrue('Décennale' in wizard.blocking_reasons, "Reason should mention Décennale")
        
        # Try confirm -> Expect Error
        with self.assertRaises(UserError):
            wizard.action_confirm()
            
        # Force Assignment
        wizard.force_assignment = True
        wizard.force_reason = "Mario said it's ok"
        wizard.action_confirm()
        
        # Verify Assigned
        self.assertEqual(self.lot.subcontractor_id, self.plumber, "Partner should be assigned after force")

    def test_cron_expiration_alert(self):
        """Test that cron generates alert for expiring documents."""
        # Set expiry to past (Critical Red)
        expired_date = date.today() - timedelta(days=1)
        self.plumber.write({
            'doc_kbis': base64.b64encode(b'DATA'),
            'doc_kbis_expiry': expired_date,
            'doc_urssaf': base64.b64encode(b'DATA'),
            'doc_urssaf_expiry': date.today() + timedelta(days=90),
            'doc_insurance_dec': base64.b64encode(b'DATA'),
            'doc_insurance_dec_expiry': date.today() + timedelta(days=90),
            'doc_cni': base64.b64encode(b'DATA'),
            'doc_cni_expiry': date.today() + timedelta(days=90),
        })
        
        # Force recompute
        self.plumber._compute_doc_statuses()
        self.plumber._compute_compliance_state()
        self.plumber._compute_alert_level()
        
        # Now run Cron
        # Note: Cron currently filters on compliance_state in ['expired', 'incomplete']
        # Since one doc is expired, compliance_state should be 'expired'.
        self.Partner.cron_check_document_expiry()
        
        # Verify Activity
        activity = self.env['mail.activity'].search([
            ('res_id', '=', self.plumber.id),
            ('res_model', '=', 'res.partner'),
            ('summary', '=', 'Documents expirés')
        ])
        self.assertTrue(activity, "Should create an activity for expired doc")

    def test_subcontractor_stage_automation(self):
        """Test stage moves to 'compliant' when docs uploaded."""
        self.plumber.subcontractor_stage = 'draft'
        
        # Upload all required docs
        docs = {
            'doc_kbis': base64.b64encode(b'K'),
            'doc_kbis_expiry': date.today() + timedelta(days=90),
            'doc_urssaf': base64.b64encode(b'U'),
            'doc_urssaf_expiry': date.today() + timedelta(days=90),
            'doc_insurance_dec': base64.b64encode(b'I'),
            'doc_insurance_dec_expiry': date.today() + timedelta(days=90),
            'doc_cni': base64.b64encode(b'C'),
            'doc_cni_expiry': date.today() + timedelta(days=90),
        }
        self.plumber.write(docs)
        
        # Verify Auto-move
        self.assertEqual(self.plumber.subcontractor_stage, 'compliant', "Stage should auto-update to compliant")
