"""
Unit tests for Chantier Workflow

Tests cover:
- Stage transitions (forward and backward)
- Workflow validation gates
- Automatic actions on stage changes
- Progress-based stage transitions
"""

from odoo.tests import TransactionCase
from odoo.exceptions import ValidationError
from datetime import date, timedelta


class TestChantierWorkflow(TransactionCase):
    """Test suite for Chantier workflow transitions."""

    @classmethod
    def setUpClass(cls):
        """Set up test data for all test methods."""
        super().setUpClass()
        
        # Create test client
        cls.client = cls.env['res.partner'].create({
            'name': 'Test Client',
            'email': 'client@test.com',
            'phone': '0123456789',
        })
        
        # Create chapters in sequence
        cls.chapter_ao = cls.env['construction.chapter'].create({
            'name': 'Avant-Ouverture',
            'code': 'AO',
            'sequence': 1,
        })
        
        cls.chapter_prep = cls.env['construction.chapter'].create({
            'name': 'Préparation',
            'code': 'PREP',
            'sequence': 2,
        })
        
        cls.chapter_trav = cls.env['construction.chapter'].create({
            'name': 'Travaux',
            'code': 'TRAV',
            'sequence': 3,
        })
        
        cls.chapter_levee = cls.env['construction.chapter'].create({
            'name': 'Levée de réserves',
            'code': 'LEVEE',
            'sequence': 4,
        })
        
        # Create stages
        cls.stage_rec = cls.env['construction.stage'].create({
            'name': 'Réception',
            'code': 'REC',
            'chapter_id': cls.chapter_ao.id,
            'sequence': 1,
        })
        
        cls.stage_vt = cls.env['construction.stage'].create({
            'name': 'Visite technique',
            'code': 'VT',
            'chapter_id': cls.chapter_ao.id,
            'sequence': 2,
        })
        
        cls.stage_de = cls.env['construction.stage'].create({
            'name': 'Devis envoyé',
            'code': 'DE',
            'chapter_id': cls.chapter_ao.id,
            'sequence': 3,
        })
        
        cls.stage_da = cls.env['construction.stage'].create({
            'name': 'Devis accepté',
            'code': 'DA',
            'chapter_id': cls.chapter_prep.id,
            'sequence': 1,
        })
        
        cls.stage_fd = cls.env['construction.stage'].create({
            'name': 'Finalisation dossier',
            'code': 'FD',
            'chapter_id': cls.chapter_prep.id,
            'sequence': 2,
        })
        
        cls.stage_t25 = cls.env['construction.stage'].create({
            'name': 'Travaux 25%',
            'code': 'T25',
            'chapter_id': cls.chapter_trav.id,
            'sequence': 1,
        })
        
        cls.stage_t50 = cls.env['construction.stage'].create({
            'name': 'Travaux 50%',
            'code': 'T50',
            'chapter_id': cls.chapter_trav.id,
            'sequence': 2,
        })

    def _create_complete_chantier(self):
        """Helper to create a fully configured chantier."""
        chantier = self.env['construction.chantier'].create({
            'name': 'Complete Project',
            'client': self.client.id,
            'address': '123 Test Street',
            'description': 'Test description',
            'phone': '0123456789',
            'date_start_contract': date.today(),
            'date_end_contract': date.today() + timedelta(days=30),
            'date_start_internal': date.today(),
            'date_end_internal': date.today() + timedelta(days=30),
            'state': 'active',
        })
        
        # Create lot
        lot = self.env['construction.lot'].create({
            'name': 'Test Lot',
            'code': 'TL',
            'chantier_id': chantier.id,
            'price': 1000.0,
        })
        
        # Create subcontractor
        subcontractor = self.env['res.partner'].create({
            'name': 'Test Subcontractor',
            'supplier_rank': 1,
        })
        
        lot.subcontractor_ids = [(6, 0, [subcontractor.id])]
        
        return chantier, lot, subcontractor

    # ==================== Can Move To Next Stage Tests ====================

    def test_01_can_move_to_next_stage_no_stage(self):
        """Test _can_move_to_next_stage without stage."""
        chantier = self.env['construction.chantier'].create({
            'name': 'Test Project',
            'client': self.client.id,
            'address': '123 Test Street',
            'description': 'Test description',
            'phone': '0123456789',
        })
        
        chantier.with_context(bypass_stage_validation=True).write({
            'stage_id': False
        })
        
        ok, message = chantier._can_move_to_next_stage()
        
        self.assertFalse(ok, "Should not allow move without stage")
        self.assertIn('étape', message.lower(), "Message should mention stage")

    def test_02_can_move_to_next_stage_reception_complete(self):
        """Test _can_move_to_next_stage from reception with complete data."""
        chantier = self.env['construction.chantier'].create({
            'name': 'Test Project',
            'client': self.client.id,
            'address': '123 Test Street',
            'description': 'Test description',
            'phone': '0123456789',
        })
        
        chantier.with_context(bypass_stage_validation=True).write({
            'stage_id': self.stage_rec.id
        })
        
        ok, message = chantier._can_move_to_next_stage()
        
        self.assertTrue(ok, "Should allow move from reception with complete data")

    def test_03_can_move_to_next_stage_reception_incomplete(self):
        """Test _can_move_to_next_stage from reception with incomplete data."""
        chantier = self.env['construction.chantier'].create({
            'name': 'Test Project',
            'client': self.client.id,
            'address': '123 Test Street',
            'description': 'Test description',
            # Missing phone
        })
        
        chantier.with_context(bypass_stage_validation=True).write({
            'stage_id': self.stage_rec.id
        })
        
        ok, message = chantier._can_move_to_next_stage()
        
        self.assertFalse(ok, "Should not allow move with incomplete data")
        self.assertIn('téléphone', message.lower(), "Message should mention phone")

    def test_04_can_move_to_next_stage_progress_threshold(self):
        """Test _can_move_to_next_stage with progress threshold."""
        chantier = self.env['construction.chantier'].create({
            'name': 'Test Project',
            'client': self.client.id,
            'address': '123 Test Street',
            'description': 'Test description',
            'phone': '0123456789',
        })
        
        chantier.with_context(bypass_stage_validation=True).write({
            'stage_id': self.stage_t25.id
        })
        
        # Progress below 25%
        chantier.progress = 20.0
        ok, message = chantier._can_move_to_next_stage()
        self.assertFalse(ok, "Should not allow move below 25%")
        
        # Progress at 25%
        chantier.progress = 25.0
        ok, message = chantier._can_move_to_next_stage()
        self.assertTrue(ok, "Should allow move at 25%")

    # ==================== Can Move To Previous Stage Tests ====================

    def test_05_can_move_to_previous_stage_no_stage(self):
        """Test _can_move_to_previous_stage without stage."""
        chantier = self.env['construction.chantier'].create({
            'name': 'Test Project',
            'client': self.client.id,
            'address': '123 Test Street',
            'description': 'Test description',
            'phone': '0123456789',
        })
        
        chantier.with_context(bypass_stage_validation=True).write({
            'stage_id': False
        })
        
        ok, message = chantier._can_move_to_previous_stage()
        
        self.assertFalse(ok, "Should not allow move without stage")

    def test_06_can_move_to_previous_stage_from_trav_high_progress(self):
        """Test _can_move_to_previous_stage from TRAV with high progress."""
        chantier = self.env['construction.chantier'].create({
            'name': 'Test Project',
            'client': self.client.id,
            'address': '123 Test Street',
            'description': 'Test description',
            'phone': '0123456789',
        })
        
        chantier.with_context(bypass_stage_validation=True).write({
            'stage_id': self.stage_t50.id
        })
        
        chantier.progress = 60.0
        
        ok, message = chantier._can_move_to_previous_stage()
        
        self.assertFalse(ok, "Should not allow backwards move with progress > 50%")
        self.assertIn('avancés', message.lower(), "Message should mention progress")

    def test_07_can_move_to_previous_stage_allowed(self):
        """Test _can_move_to_previous_stage when allowed."""
        chantier = self.env['construction.chantier'].create({
            'name': 'Test Project',
            'client': self.client.id,
            'address': '123 Test Street',
            'description': 'Test description',
            'phone': '0123456789',
        })
        
        chantier.with_context(bypass_stage_validation=True).write({
            'stage_id': self.stage_vt.id
        })
        
        ok, message = chantier._can_move_to_previous_stage()
        
        self.assertTrue(ok, "Should allow backwards move from visit stage")

    # ==================== Get Next Stage Tests ====================

    def test_08_get_next_stage_within_chapter(self):
        """Test _get_next_stage within same chapter."""
        chantier = self.env['construction.chantier'].create({
            'name': 'Test Project',
            'client': self.client.id,
            'address': '123 Test Street',
            'description': 'Test description',
            'phone': '0123456789',
        })
        
        chantier.with_context(bypass_stage_validation=True).write({
            'stage_id': self.stage_rec.id
        })
        
        next_stage = chantier._get_next_stage()
        
        self.assertEqual(
            next_stage,
            self.stage_vt,
            "Next stage should be visit within same chapter"
        )

    def test_09_get_next_stage_to_next_chapter(self):
        """Test _get_next_stage transitioning to next chapter."""
        chantier = self.env['construction.chantier'].create({
            'name': 'Test Project',
            'client': self.client.id,
            'address': '123 Test Street',
            'description': 'Test description',
            'phone': '0123456789',
        })
        
        chantier.with_context(bypass_stage_validation=True).write({
            'stage_id': self.stage_de.id
        })
        
        next_stage = chantier._get_next_stage()
        
        # Should move to first stage of next chapter (PREP)
        self.assertEqual(
            next_stage.chapter_id,
            self.chapter_prep,
            "Should transition to next chapter"
        )

    def test_10_get_next_stage_trav_with_thresholds(self):
        """Test _get_next_stage for TRAV chapter with progress thresholds."""
        chantier = self.env['construction.chantier'].create({
            'name': 'Test Project',
            'client': self.client.id,
            'address': '123 Test Street',
            'description': 'Test description',
            'phone': '0123456789',
        })
        
        chantier.with_context(bypass_stage_validation=True).write({
            'stage_id': self.stage_t25.id
        })
        
        # Set progress to 30% (next threshold is 50%)
        chantier.progress = 30.0
        
        next_stage = chantier._get_next_stage()
        
        # Should find stage for 50% threshold
        self.assertIn(
            '50',
            next_stage.name,
            "Next stage should be for 50% threshold"
        )

    # ==================== Action Move To Next Stage Tests ====================

    def test_11_action_move_to_next_stage_success(self):
        """Test action_move_to_next_stage successful transition."""
        chantier = self.env['construction.chantier'].create({
            'name': 'Test Project',
            'client': self.client.id,
            'address': '123 Test Street',
            'description': 'Test description',
            'phone': '0123456789',
        })
        
        chantier.with_context(bypass_stage_validation=True).write({
            'stage_id': self.stage_rec.id,
            'state': 'active',
        })
        
        old_stage = chantier.stage_id
        
        result = chantier.action_move_to_next_stage()
        
        # Check stage changed
        self.assertNotEqual(
            chantier.stage_id,
            old_stage,
            "Stage should have changed"
        )
        
        # Check notification returned
        self.assertEqual(
            result.get('type'),
            'ir.actions.client',
            "Should return client action"
        )

    def test_12_action_move_to_next_stage_blocked(self):
        """Test action_move_to_next_stage blocked by validation."""
        chantier = self.env['construction.chantier'].create({
            'name': 'Test Project',
            'client': self.client.id,
            'address': '123 Test Street',
            'description': 'Test description',
            # Missing phone to block progression
        })
        
        chantier.with_context(bypass_stage_validation=True).write({
            'stage_id': self.stage_rec.id
        })
        
        with self.assertRaises(ValidationError) as cm:
            chantier.action_move_to_next_stage()
        
        self.assertIn(
            'impossible',
            str(cm.exception).lower(),
            "Should mention impossibility"
        )

    def test_13_action_move_to_next_stage_admin_bypass(self):
        """Test action_move_to_next_stage admin bypass wizard."""
        # Create admin user
        admin_group = self.env.ref('base.group_system')
        admin_user = self.env['res.users'].create({
            'name': 'Admin User',
            'login': 'admin_test_workflow',
            'groups_id': [(4, admin_group.id)],
        })
        
        chantier = self.env['construction.chantier'].create({
            'name': 'Test Project',
            'client': self.client.id,
            'address': '123 Test Street',
            'description': 'Test description',
            # Missing phone
        })
        
        chantier.with_context(bypass_stage_validation=True).write({
            'stage_id': self.stage_rec.id
        })
        
        # Admin should get wizard instead of error
        result = chantier.with_user(admin_user).action_move_to_next_stage()
        
        self.assertEqual(
            result.get('res_model'),
            'construction.force.stage.wizard',
            "Admin should get force stage wizard"
        )

    # ==================== Action Move To Previous Stage Tests ====================

    def test_14_action_move_to_previous_stage_success(self):
        """Test action_move_to_previous_stage successful transition."""
        chantier = self.env['construction.chantier'].create({
            'name': 'Test Project',
            'client': self.client.id,
            'address': '123 Test Street',
            'description': 'Test description',
            'phone': '0123456789',
        })
        
        chantier.with_context(bypass_stage_validation=True).write({
            'stage_id': self.stage_vt.id
        })
        
        result = chantier.action_move_to_previous_stage()
        
        # Should move to reception
        self.assertEqual(
            chantier.stage_id,
            self.stage_rec,
            "Should move to previous stage"
        )
        
        # Check notification
        self.assertEqual(
            result.get('params', {}).get('type'),
            'warning',
            "Should show warning notification for backwards move"
        )

    def test_15_action_move_to_previous_stage_blocked(self):
        """Test action_move_to_previous_stage blocked."""
        chantier = self.env['construction.chantier'].create({
            'name': 'Test Project',
            'client': self.client.id,
            'address': '123 Test Street',
            'description': 'Test description',
            'phone': '0123456789',
        })
        
        chantier.with_context(bypass_stage_validation=True).write({
            'stage_id': self.stage_t50.id
        })
        
        chantier.progress = 60.0
        
        with self.assertRaises(ValidationError):
            chantier.action_move_to_previous_stage()

    # ==================== Trigger Stage Actions Tests ====================

    def test_16_trigger_stage_actions_fd_advance_payment(self):
        """Test _trigger_stage_actions for FD stage advance payment."""
        chantier, lot, subcontractor = self._create_complete_chantier()
        
        # Create invoice schedule
        invoice_type = self.env['construction.invoice_type'].create({
            'name': 'Test Type',
            'code': 'TEST',
        })
        
        quote = self.env['sale.order'].create({
            'partner_id': self.client.id,
            'chantier_id': chantier.id,
        })
        
        chantier.write({
            'invoice_type_id': invoice_type.id,
            'main_quote_id': quote.id,
        })
        
        # Create advance payment schedule
        schedule = self.env['construction.invoice.schedule'].create({
            'chantier_id': chantier.id,
            'quote_id': quote.id,
            'name': 'Advance Payment',
            'is_advance_payment': True,
            'state': 'planned',
            'amount_percentage': 10.0,
        })
        
        # Set to FD stage and trigger actions
        chantier.with_context(bypass_stage_validation=True).write({
            'stage_id': self.stage_fd.id
        })
        
        chantier._trigger_stage_actions()
        
        # Advance payment should be activated
        self.assertEqual(
            schedule.state,
            'ready',
            "Advance payment should be ready"
        )
        self.assertTrue(
            schedule.is_triggered,
            "Advance payment should be triggered"
        )

    def test_17_trigger_stage_actions_message_post(self):
        """Test _trigger_stage_actions posts messages."""
        chantier, lot, subcontractor = self._create_complete_chantier()
        
        # Create invoice schedule
        invoice_type = self.env['construction.invoice_type'].create({
            'name': 'Test Type',
            'code': 'TEST',
        })
        
        quote = self.env['sale.order'].create({
            'partner_id': self.client.id,
            'chantier_id': chantier.id,
        })
        
        chantier.write({
            'invoice_type_id': invoice_type.id,
            'main_quote_id': quote.id,
        })
        
        # Create advance payment
        self.env['construction.invoice.schedule'].create({
            'chantier_id': chantier.id,
            'quote_id': quote.id,
            'name': 'Advance Payment',
            'is_advance_payment': True,
            'state': 'planned',
            'amount_percentage': 10.0,
        })
        
        initial_message_count = len(chantier.message_ids)
        
        # Trigger actions
        chantier.with_context(bypass_stage_validation=True).write({
            'stage_id': self.stage_fd.id
        })
        chantier._trigger_stage_actions()
        
        # Should have posted a message
        self.assertGreater(
            len(chantier.message_ids),
            initial_message_count,
            "Should have posted a message about advance payment"
        )

    # ==================== Get Next Progress Threshold Tests ====================

    def test_18_get_next_progress_threshold(self):
        """Test _get_next_progress_threshold."""
        chantier = self.env['construction.chantier'].create({
            'name': 'Test Project',
            'client': self.client.id,
            'address': '123 Test Street',
            'description': 'Test description',
            'phone': '0123456789',
        })
        
        # Test various progress levels
        test_cases = [
            (0, 25),
            (10, 25),
            (24.9, 25),
            (25, 50),
            (40, 50),
            (50, 75),
            (60, 75),
            (75, 100),
            (90, 100),
            (100, None),
        ]
        
        for progress, expected_threshold in test_cases:
            result = chantier._get_next_progress_threshold(progress)
            self.assertEqual(
                result,
                expected_threshold,
                f"Progress {progress}% should give threshold {expected_threshold}"
            )

    # ==================== Stage Validation Info Tests ====================

    def test_19_compute_stage_validation_info_complete(self):
        """Test _compute_stage_validation_info with complete stage."""
        chantier = self.env['construction.chantier'].create({
            'name': 'Test Project',
            'client': self.client.id,
            'address': '123 Test Street',
            'description': 'Test description',
            'phone': '0123456789',
        })
        
        chantier.with_context(bypass_stage_validation=True).write({
            'stage_id': self.stage_rec.id
        })
        
        info = chantier.stage_validation_info
        
        self.assertIn('Stage:', info, "Should show stage info")
        self.assertIn('[OK]', info, "Should show ready status")

    def test_20_compute_stage_validation_info_incomplete(self):
        """Test _compute_stage_validation_info with incomplete stage."""
        chantier = self.env['construction.chantier'].create({
            'name': 'Test Project',
            'client': self.client.id,
            'address': '123 Test Street',
            'description': 'Test description',
            # Missing phone
        })
        
        chantier.with_context(bypass_stage_validation=True).write({
            'stage_id': self.stage_rec.id
        })
        
        info = chantier.stage_validation_info
        
        self.assertIn('[BLOCKED]', info, "Should show blocked status")
        self.assertIn('téléphone', info.lower(), "Should mention missing phone")

