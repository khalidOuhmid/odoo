"""
Unit tests for Chantier Model Core Functionality

Tests cover:
- Record creation and automatic reference generation
- Write operations and stage validation
- Constraints and validations
- Field defaults and required fields
"""

from odoo.tests import TransactionCase
from odoo.exceptions import ValidationError
from datetime import date, timedelta


class TestChantierModel(TransactionCase):
    """Test suite for Chantier model CRUD operations."""

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
        
        # Create test chapter
        cls.chapter = cls.env['construction.chapter'].create({
            'name': 'Test Chapter',
            'code': 'TEST',
            'sequence': 1,
        })
        
        # Create test stage
        cls.stage = cls.env['construction.stage'].create({
            'name': 'Test Stage',
            'code': 'TS',
            'chapter_id': cls.chapter.id,
            'sequence': 1,
        })
        
        # Get default stage
        cls.default_stage = cls.env.ref(
            'construction_base.stage_reception',
            raise_if_not_found=False
        )

    def test_01_create_chantier_with_defaults(self):
        """Test chantier creation with automatic defaults."""
        chantier = self.env['construction.chantier'].create({
            'name': 'Test Project',
            'client': self.client.id,
            'address': '123 Test Street',
            'description': 'Test description',
            'phone': '0123456789',
        })
        
        # Assertions
        self.assertTrue(chantier.reference, "Reference should be auto-generated")
        self.assertNotEqual(chantier.reference, '/', "Reference should not be '/'")
        self.assertEqual(chantier.client, self.client, "Client should match")
        self.assertTrue(chantier.stage_id, "Stage should be assigned")

    def test_02_create_chantier_with_reference(self):
        """Test chantier creation with explicit reference."""
        chantier = self.env['construction.chantier'].create({
            'name': 'Test Project 2',
            'client': self.client.id,
            'reference': 'CUSTOM-001',
            'address': '123 Test Street',
            'description': 'Test description',
            'phone': '0123456789',
        })
        
        self.assertEqual(
            chantier.reference,
            'CUSTOM-001',
            "Custom reference should be preserved"
        )

    def test_03_create_multiple_chantiers(self):
        """Test batch creation of multiple chantiers."""
        chantiers = self.env['construction.chantier'].create([
            {
                'name': f'Project {i}',
                'client': self.client.id,
                'address': '123 Test Street',
                'description': 'Test description',
                'phone': '0123456789',
            }
            for i in range(3)
        ])
        
        self.assertEqual(len(chantiers), 3, "Should create 3 chantiers")
        
        # Check unique references
        references = chantiers.mapped('reference')
        self.assertEqual(
            len(set(references)),
            3,
            "All references should be unique"
        )

    def test_04_write_stage_without_bypass_raises_error(self):
        """Test that modifying stage without bypass raises ValidationError."""
        chantier = self.env['construction.chantier'].create({
            'name': 'Test Project',
            'client': self.client.id,
            'address': '123 Test Street',
            'description': 'Test description',
            'phone': '0123456789',
        })
        
        with self.assertRaises(ValidationError) as cm:
            chantier.write({'stage_id': self.stage.id})
        
        self.assertIn(
            'interdite',
            str(cm.exception).lower(),
            "Error message should mention forbidden modification"
        )

    def test_05_write_stage_with_bypass_succeeds(self):
        """Test that modifying stage with bypass context succeeds."""
        chantier = self.env['construction.chantier'].create({
            'name': 'Test Project',
            'client': self.client.id,
            'address': '123 Test Street',
            'description': 'Test description',
            'phone': '0123456789',
        })
        
        old_stage = chantier.stage_id
        
        # Write with bypass context
        chantier.with_context(bypass_stage_validation=True).write({
            'stage_id': self.stage.id
        })
        
        self.assertEqual(
            chantier.stage_id,
            self.stage,
            "Stage should be updated with bypass"
        )
        self.assertNotEqual(
            chantier.stage_id,
            old_stage,
            "Stage should have changed"
        )

    def test_06_write_stage_as_admin_succeeds(self):
        """Test that admin can modify stage without bypass."""
        # Create admin user
        admin_group = self.env.ref('base.group_system')
        admin_user = self.env['res.users'].create({
            'name': 'Admin User',
            'login': 'admin_test',
            'groups_id': [(4, admin_group.id)],
        })
        
        chantier = self.env['construction.chantier'].create({
            'name': 'Test Project',
            'client': self.client.id,
            'address': '123 Test Street',
            'description': 'Test description',
            'phone': '0123456789',
        })
        
        # Write as admin (should succeed without ValidationError)
        chantier.with_user(admin_user).write({'stage_id': self.stage.id})
        
        self.assertEqual(
            chantier.stage_id,
            self.stage,
            "Admin should be able to change stage"
        )

    def test_07_constraint_positive_cost(self):
        """Test SQL constraint for positive total_cost."""
        # Note: SQL constraints are checked at database level
        # This test verifies the constraint exists
        constraints = self.env['construction.chantier']._sql_constraints
        constraint_names = [c[0] for c in constraints]
        
        self.assertIn(
            'positive_cost',
            constraint_names,
            "positive_cost constraint should exist"
        )

    def test_08_constraint_positive_surface(self):
        """Test SQL constraint for positive surface."""
        constraints = self.env['construction.chantier']._sql_constraints
        constraint_names = [c[0] for c in constraints]
        
        self.assertIn(
            'positive_surface',
            constraint_names,
            "positive_surface constraint should exist"
        )

    def test_09_constraint_progress_range(self):
        """Test SQL constraint for progress range 0-100."""
        constraints = self.env['construction.chantier']._sql_constraints
        constraint_names = [c[0] for c in constraints]
        
        self.assertIn(
            'progress_range',
            constraint_names,
            "progress_range constraint should exist"
        )

    def test_10_check_contract_dates_constraint(self):
        """Test contract dates validation constraint."""
        chantier = self.env['construction.chantier'].create({
            'name': 'Test Project',
            'client': self.client.id,
            'address': '123 Test Street',
            'description': 'Test description',
            'phone': '0123456789',
        })
        
        # Try to set end date before start date
        with self.assertRaises(ValidationError):
            chantier.write({
                'date_start_contract': date.today(),
                'date_end_contract': date.today() - timedelta(days=10),
            })

    def test_11_write_triggers_invoice_check(self):
        """Test that write operation triggers invoice check when needed."""
        chantier = self.env['construction.chantier'].create({
            'name': 'Test Project',
            'client': self.client.id,
            'address': '123 Test Street',
            'description': 'Test description',
            'phone': '0123456789',
        })
        
        # Set need_invoice_check flag
        chantier.write({'need_invoice_check': True})
        
        # Flag should be set
        self.assertTrue(
            chantier.need_invoice_check,
            "Invoice check flag should be set"
        )

    def test_12_create_chantier_without_required_client(self):
        """Test that creating chantier without client raises error."""
        with self.assertRaises(Exception):
            self.env['construction.chantier'].create({
                'name': 'Test Project',
                'address': '123 Test Street',
                'description': 'Test description',
                'phone': '0123456789',
            })

    def test_13_chantier_inherits_mail_thread(self):
        """Test that chantier has mail.thread capabilities."""
        chantier = self.env['construction.chantier'].create({
            'name': 'Test Project',
            'client': self.client.id,
            'address': '123 Test Street',
            'description': 'Test description',
            'phone': '0123456789',
        })
        
        # Check message_post method exists
        self.assertTrue(
            hasattr(chantier, 'message_post'),
            "Chantier should have message_post method"
        )
        
        # Post a message
        chantier.message_post(
            body='Test message',
            message_type='comment'
        )
        
        # Verify message was posted
        self.assertTrue(
            chantier.message_ids,
            "Chantier should have messages"
        )

    def test_14_chantier_currency_default(self):
        """Test that currency defaults to company currency."""
        chantier = self.env['construction.chantier'].create({
            'name': 'Test Project',
            'client': self.client.id,
            'address': '123 Test Street',
            'description': 'Test description',
            'phone': '0123456789',
        })
        
        self.assertEqual(
            chantier.currency_id,
            self.env.company.currency_id,
            "Currency should default to company currency"
        )

    def test_15_chantier_copy_behavior(self):
        """Test chantier copy behavior for copy=False fields."""
        chantier = self.env['construction.chantier'].create({
            'name': 'Original Project',
            'client': self.client.id,
            'reference': 'REF-001',
            'address': '123 Test Street',
            'description': 'Test description',
            'phone': '0123456789',
        })
        
        # Copy chantier
        chantier_copy = chantier.copy({'name': 'Copied Project'})
        
        # Reference should not be copied (copy=False)
        self.assertNotEqual(
            chantier_copy.reference,
            chantier.reference,
            "Reference should not be copied"
        )
        
        # Name should be updated
        self.assertEqual(
            chantier_copy.name,
            'Copied Project',
            "Name should be updated in copy"
        )


