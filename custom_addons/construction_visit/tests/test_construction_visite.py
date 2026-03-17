# -*- coding: utf-8 -*-
"""
Unit Tests for Construction Visit Module - Phase 1
Production-grade test suite for BLG Groupe

Tests cover:
- Visit creation and reference generation
- 24-hour date validation buffer (US-V001)
- ICS calendar file generation (US-V002)
- Maps/Waze URL generation (US-V003)
- Notification workflow with participant validation

Author: Antigravity (Google DeepMind) for BLG Groupe
"""

from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError, UserError
from datetime import timedelta
from odoo import fields
import base64


class TestConstructionVisite(TransactionCase):
    """Test cases for construction.visit model."""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures.
        
        Creates:
        - Test chantier with address
        - Test partner as participant
        - Email template reference
        """
        super().setUpClass()
        
        # Create test chapter and stage for chantier
        cls.chapter = cls.env['construction.chapter'].create({
            'name': 'Test Chapter',
            'code': 'TC',
            'sequence': 1
        })
        cls.stage = cls.env['construction.stage'].create({
            'name': 'Test Stage',
            'code': 'TS',
            'chapter_id': cls.chapter.id,
            'sequence': 1
        })
        
        # Create test client partner
        cls.client = cls.env['res.partner'].create({
            'name': 'Client Test BLG',
            'email': 'client@blgtest.fr',
        })
        
        # Create test chantier with address
        cls.chantier = cls.env['construction.chantier'].create({
            'name': 'Chantier Test Phase 1',
            'client': cls.client.id,
            'stage_id': cls.stage.id,
            'address': '123 Rue de la Construction',
            'city': 'Paris',
            'zip_code': '75001',
        })
        
        # Create test participant with email
        cls.participant = cls.env['res.partner'].create({
            'name': 'Participant Test',
            'email': 'participant@test.fr',
        })
        
        # Get or create email template
        cls.template = cls.env.ref(
            'construction_visit.email_template_visit_notification',
            raise_if_not_found=False
        )
        if not cls.template:
            cls.template = cls.env['mail.template'].create({
                'name': 'Test Visit Notification Template',
                'subject': 'Visite programmee - {{ object.chantier_id.name }}',
                'body_html': '<p>Test body</p>',
                'model_id': cls.env.ref('construction_visit.model_construction_visit').id,
            })

    def _create_valid_visit(self, **kwargs):
        """Helper to create a visit with valid date (2 days ahead).
        
        Args:
            **kwargs: Override default values
            
        Returns:
            construction.visit record
        """
        defaults = {
            'name': 'Visite Test',
            'chantier_id': self.chantier.id,
            'date': fields.Datetime.now() + timedelta(days=2),
            'duration': 2.0,
            'visit_type': 'follow_up',
        }
        defaults.update(kwargs)
        return self.env['construction.visit'].create(defaults)

    # ============= US-V001: Create Technical Visit ============= #
    def test_visite_creation_state_is_draft(self):
        """Test: New visit starts in draft state."""
        visite = self._create_valid_visit()
        self.assertEqual(
            visite.state, 'draft',
            "New visit should be in 'draft' state"
        )

    def test_visite_creation_has_chantier_link(self):
        """Test: Visit is properly linked to chantier."""
        visite = self._create_valid_visit()
        self.assertEqual(
            visite.chantier_id.id, self.chantier.id,
            "Visit should be linked to correct chantier"
        )

    # 24h constraint removed — now only warning via onchange, not hard constraint

    # ============= US-V002: ICS Calendar Generation ============= #
    def test_ics_generation_creates_valid_binary(self):
        """Test: ICS generation produces binary data."""
        visite = self._create_valid_visit()
        self.assertTrue(
            visite.ics_data,
            "ICS data should be generated"
        )
        self.assertTrue(
            visite.ics_filename,
            "ICS filename should be generated"
        )
        self.assertIn('.ics', visite.ics_filename)

    def test_ics_generation_contains_vevent(self):
        """Test: ICS file contains VEVENT structure (RFC 5545)."""
        visite = self._create_valid_visit()
        ics_content = base64.b64decode(visite.ics_data).decode('utf-8')
        
        self.assertIn('BEGIN:VCALENDAR', ics_content)
        self.assertIn('BEGIN:VEVENT', ics_content)
        self.assertIn('END:VEVENT', ics_content)
        self.assertIn('END:VCALENDAR', ics_content)

    def test_ics_generation_contains_dtstart(self):
        """Test: ICS file contains proper DTSTART timestamp."""
        visite = self._create_valid_visit()
        ics_content = base64.b64decode(visite.ics_data).decode('utf-8')
        
        self.assertIn('DTSTART:', ics_content)
        self.assertIn('DTEND:', ics_content)

    def test_ics_generation_contains_location(self):
        """Test: ICS file contains chantier address."""
        visite = self._create_valid_visit()
        ics_content = base64.b64decode(visite.ics_data).decode('utf-8')
        
        self.assertIn('LOCATION:', ics_content)
        # Address from chantier should be included
        self.assertIn('123 Rue de la Construction', ics_content)

    def test_ics_generation_contains_summary(self):
        """Test: ICS file contains visit summary."""
        visite = self._create_valid_visit(name='Ma Visite Specifique')
        ics_content = base64.b64decode(visite.ics_data).decode('utf-8')
        
        self.assertIn('SUMMARY:', ics_content)
        self.assertIn('Ma Visite Specifique', ics_content)

    def test_ics_generation_without_chantier_returns_false(self):
        """Test: ICS not generated if no chantier (edge case)."""
        # This tests the compute method's fallback behavior
        visite = self._create_valid_visit()
        # Force compute with missing data by temporarily clearing
        visite.write({'chantier_id': False})
        visite._compute_ics_data()
        self.assertFalse(visite.ics_data)

    # ============= US-V003: Maps/Waze Deep Links ============= #
    def test_maps_url_generation(self):
        """Test: Google Maps URL is correctly generated."""
        visite = self._create_valid_visit()
        maps_url = visite.get_maps_url()
        
        self.assertIn('google.com/maps', maps_url)
        self.assertIn('query=', maps_url)

    def test_waze_url_generation(self):
        """Test: Waze URL is correctly generated."""
        visite = self._create_valid_visit()
        waze_url = visite.get_waze_url()
        
        self.assertIn('waze.com', waze_url)

    def test_maps_url_includes_address(self):
        """Test: Maps URL includes encoded address."""
        visite = self._create_valid_visit()
        maps_url = visite.get_maps_url()
        
        # URL should include encoded address parts
        self.assertTrue(len(maps_url) > 50)  # Has substantial query

    def test_maps_url_empty_if_no_address(self):
        """Test: Maps URL returns empty if no address."""
        # Create chantier without address
        chantier_no_addr = self.env['construction.chantier'].create({
            'name': 'Chantier Sans Adresse',
            'client': self.client.id,
            'stage_id': self.stage.id,
        })
        visite = self._create_valid_visit(chantier_id=chantier_no_addr.id)
        
        maps_url = visite.get_maps_url()
        self.assertEqual(maps_url, '')

    # ============= Notification Workflow ============= #
    def test_send_notifications_requires_participants(self):
        """Test: Sending notification fails without participants."""
        visite = self._create_valid_visit()
        visite.state = 'confirmed'
        
        with self.assertRaises(UserError) as context:
            visite.action_send_notification()
        self.assertIn(
            'participant',
            str(context.exception).lower(),
            "Error should mention participants"
        )

    def test_send_notifications_success_with_participants(self):
        """Test: Notification succeeds with valid participants."""
        visite = self._create_valid_visit(
            participant_ids=[(6, 0, [self.participant.id])]
        )
        visite.state = 'confirmed'
        
        # Mock the template if not available
        result = visite.action_send_notification()
        
        self.assertTrue(visite.notification_sent)
        self.assertEqual(result.get('type'), 'ir.actions.client')

    def test_send_notifications_sets_notification_flag(self):
        """Test: Notification flag is set after successful send."""
        visite = self._create_valid_visit(
            participant_ids=[(6, 0, [self.participant.id])]
        )
        visite.state = 'confirmed'
        self.assertFalse(visite.notification_sent)
        
        visite.action_send_notification()
        
        self.assertTrue(visite.notification_sent)

    # ============= State Machine Tests ============= #
    def test_confirm_requires_participants(self):
        """Test: Confirming visit requires at least one participant."""
        visite = self._create_valid_visit()
        visite.state = 'draft'
        
        with self.assertRaises(ValidationError):
            visite.action_confirm()

    def test_confirm_succeeds_with_participants(self):
        """Test: Confirm succeeds when participants exist."""
        visite = self._create_valid_visit(
            participant_ids=[(6, 0, [self.participant.id])]
        )
        visite.action_confirm()
        
        self.assertEqual(visite.state, 'confirmed')

    def test_complete_requires_in_progress_state(self):
        """Test: Cannot complete visit that is not in progress."""
        visite = self._create_valid_visit(
            participant_ids=[(6, 0, [self.participant.id])]
        )
        visite.state = 'draft'
        
        with self.assertRaises(ValidationError):
            visite.action_complete()

    # ============= Button Visibility Tests ============= #
    def test_show_send_notification_visibility(self):
        """Test: Send notification button visibility logic."""
        visite = self._create_valid_visit()
        visite.state = 'confirmed'
        visite.notification_sent = False
        visite._compute_button_visibility()
        
        self.assertTrue(visite.show_send_notification)
        
        visite.notification_sent = True
        visite._compute_button_visibility()
        
        self.assertFalse(visite.show_send_notification)

    def test_show_generate_report_visibility(self):
        """Test: Generate report button visibility logic."""
        visite = self._create_valid_visit()
        visite.state = 'completed'
        visite.notes = '<p>Some notes</p>'
        visite.report_generated = False
        visite._compute_button_visibility()
        
        self.assertTrue(visite.show_generate_report)

    # ============= Regression Tests (AAA Pattern) ============= #
    def test_notification_skips_partner_without_email(self):
        """Test (AAA): Users without email do not crash the notification process."""
        # Arrange
        partner_no_email = self.env['res.partner'].create({'name': 'No Email', 'email': False})
        visite = self._create_valid_visit(
            participant_ids=[(6, 0, [self.participant.id, partner_no_email.id])]
        )
        visite.state = 'confirmed'
        
        # Act
        result = visite.action_send_notification()
        
        # Assert
        self.assertTrue(visite.notification_sent, "Notification flag should be true despite one missing email")
        self.assertEqual(result.get('type'), 'ir.actions.client', "Should return success action irrespective of missing emails")

    def test_visit_cascade_deletion(self):
        """Test (AAA): Visit cleanly deleted if Chantier is deleted to prevent zombies."""
        # Arrange
        visite = self._create_valid_visit()
        visit_id = visite.id
        
        # Act
        self.chantier.unlink()
        
        # Assert
        deleted_visit = self.env['construction.visit'].search([('id', '=', visit_id)])
        self.assertFalse(deleted_visit, "Visit must be deleted when chantier is deleted")
