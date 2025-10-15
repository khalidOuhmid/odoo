"""
Unit tests for Chantier Validation Methods

Tests cover:
- Stage validation methods (check_*)
- Business rule validations
- Workflow progression conditions
"""

from odoo.tests import TransactionCase
from datetime import date, timedelta


class TestChantierValidation(TransactionCase):
    """Test suite for Chantier validation methods."""

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
        
        # Create test chapters
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
        
        cls.chapter_ret = cls.env['construction.chapter'].create({
            'name': 'Retenue',
            'code': 'RET',
            'sequence': 5,
        })
        
        # Create test stages
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
        
        cls.stage_t75 = cls.env['construction.stage'].create({
            'name': 'Travaux 75%',
            'code': 'T75',
            'chapter_id': cls.chapter_trav.id,
            'sequence': 3,
        })
        
        cls.stage_lr = cls.env['construction.stage'].create({
            'name': 'Levée de réserves',
            'code': 'LR',
            'chapter_id': cls.chapter_levee.id,
            'sequence': 1,
        })
        
        cls.stage_ret = cls.env['construction.stage'].create({
            'name': 'Retenue',
            'code': 'RET',
            'chapter_id': cls.chapter_ret.id,
            'sequence': 1,
        })

    def _create_test_chantier(self, **kwargs):
        """Helper method to create test chantier."""
        default_values = {
            'name': 'Test Project',
            'client': self.client.id,
            'address': '123 Test Street',
            'description': 'Test description',
            'phone': '0123456789',
        }
        default_values.update(kwargs)
        return self.env['construction.chantier'].create(default_values)

    # ==================== Reception Stage Tests ====================

    def test_01_check_reception_stage_complete(self):
        """Test check_reception_stage with all required fields."""
        chantier = self._create_test_chantier()
        chantier.with_context(bypass_stage_validation=True).write({
            'stage_id': self.stage_rec.id
        })
        
        ok, message = chantier.check_reception_stage()
        
        self.assertTrue(ok, "Validation should pass with all fields")
        self.assertEqual(message, "", "Message should be empty on success")

    def test_02_check_reception_stage_missing_client(self):
        """Test check_reception_stage with missing client."""
        chantier = self._create_test_chantier()
        chantier.client = False
        
        ok, message = chantier.check_reception_stage()
        
        self.assertFalse(ok, "Validation should fail without client")
        self.assertIn('client', message.lower(), "Message should mention client")

    def test_03_check_reception_stage_missing_address(self):
        """Test check_reception_stage with missing address."""
        chantier = self._create_test_chantier(address=False)
        
        ok, message = chantier.check_reception_stage()
        
        self.assertFalse(ok, "Validation should fail without address")
        self.assertIn('adresse', message.lower(), "Message should mention address")

    def test_04_check_reception_stage_missing_description(self):
        """Test check_reception_stage with missing description."""
        chantier = self._create_test_chantier(description=False)
        
        ok, message = chantier.check_reception_stage()
        
        self.assertFalse(ok, "Validation should fail without description")
        self.assertIn('description', message.lower(), "Message should mention description")

    def test_05_check_reception_stage_missing_phone(self):
        """Test check_reception_stage with missing phone."""
        chantier = self._create_test_chantier(phone=False)
        
        ok, message = chantier.check_reception_stage()
        
        self.assertFalse(ok, "Validation should fail without phone")
        self.assertIn('téléphone', message.lower(), "Message should mention phone")

    def test_06_check_reception_stage_multiple_missing(self):
        """Test check_reception_stage with multiple missing fields."""
        chantier = self._create_test_chantier(
            address=False,
            description=False,
            phone=False
        )
        
        ok, message = chantier.check_reception_stage()
        
        self.assertFalse(ok, "Validation should fail with missing fields")
        # Should mention all missing fields
        self.assertIn('adresse', message.lower())
        self.assertIn('description', message.lower())
        self.assertIn('téléphone', message.lower())

    # ==================== Visit Stage Tests ====================

    def test_07_check_visit_stage_no_visits(self):
        """Test check_visit_stage with no visits."""
        chantier = self._create_test_chantier()
        
        ok, message = chantier.check_visit_stage()
        
        self.assertFalse(ok, "Validation should fail without visits")
        self.assertIn('visite', message.lower(), "Message should mention visit")

    def test_08_check_visit_stage_with_completed_visit(self):
        """Test check_visit_stage with completed visit."""
        chantier = self._create_test_chantier()
        
        # Create a completed visit
        self.env['construction.visit'].create({
            'chantier_id': chantier.id,
            'name': 'Test Visit',
            'state': 'completed',
            'visit_date': date.today(),
        })
        
        ok, message = chantier.check_visit_stage()
        
        self.assertTrue(ok, "Validation should pass with completed visit")
        self.assertEqual(message, "OK", "Message should be OK")

    def test_09_check_visit_stage_with_draft_visit(self):
        """Test check_visit_stage with only draft visit."""
        chantier = self._create_test_chantier()
        
        # Create a draft visit
        self.env['construction.visit'].create({
            'chantier_id': chantier.id,
            'name': 'Test Visit',
            'state': 'draft',
            'visit_date': date.today(),
        })
        
        ok, message = chantier.check_visit_stage()
        
        self.assertFalse(ok, "Validation should fail with only draft visit")
        self.assertIn('terminée', message.lower(), "Message should mention not completed")

    # ==================== Quotation Sent Stage Tests ====================

    def test_10_check_quotation_sent_stage_no_lots(self):
        """Test check_quotation_sent_stage with no lots."""
        chantier = self._create_test_chantier()
        
        ok, message = chantier.check_quotation_sent_stage()
        
        self.assertFalse(ok, "Validation should fail without lots")
        self.assertIn('lots', message.lower(), "Message should mention lots")

    def test_11_check_quotation_sent_stage_no_quotations(self):
        """Test check_quotation_sent_stage with lots but no quotations."""
        chantier = self._create_test_chantier()
        
        # Create a lot
        self.env['construction.lot'].create({
            'name': 'Test Lot',
            'code': 'TL',
            'chantier_id': chantier.id,
        })
        
        ok, message = chantier.check_quotation_sent_stage()
        
        self.assertFalse(ok, "Validation should fail without quotations")
        self.assertIn('devis', message.lower(), "Message should mention quotation")

    def test_12_check_quotation_sent_stage_no_accepted_quotation(self):
        """Test check_quotation_sent_stage with draft quotation."""
        chantier = self._create_test_chantier()
        
        # Create a lot
        self.env['construction.lot'].create({
            'name': 'Test Lot',
            'code': 'TL',
            'chantier_id': chantier.id,
        })
        
        # Create draft quotation
        self.env['sale.order'].create({
            'partner_id': self.client.id,
            'chantier_id': chantier.id,
            'state': 'draft',
        })
        
        ok, message = chantier.check_quotation_sent_stage()
        
        self.assertFalse(ok, "Validation should fail without accepted quotation")
        self.assertIn('accepté', message.lower(), "Message should mention acceptance")

    def test_13_check_quotation_sent_stage_with_accepted_quotation(self):
        """Test check_quotation_sent_stage with accepted quotation."""
        chantier = self._create_test_chantier()
        
        # Create a lot
        self.env['construction.lot'].create({
            'name': 'Test Lot',
            'code': 'TL',
            'chantier_id': chantier.id,
        })
        
        # Create accepted quotation
        self.env['sale.order'].create({
            'partner_id': self.client.id,
            'chantier_id': chantier.id,
            'state': 'sale',
        })
        
        ok, message = chantier.check_quotation_sent_stage()
        
        self.assertTrue(ok, "Validation should pass with accepted quotation")
        self.assertEqual(message, "OK", "Message should be OK")

    # ==================== Quotation Accepted Stage Tests ====================

    def test_14_check_quotation_accepted_stage_missing_subcontractor(self):
        """Test check_quotation_accepted_stage with missing subcontractor."""
        chantier = self._create_test_chantier()
        
        # Create a lot without subcontractor
        self.env['construction.lot'].create({
            'name': 'Test Lot',
            'code': 'TL',
            'chantier_id': chantier.id,
        })
        
        ok, message = chantier.check_quotation_accepted_stage()
        
        self.assertFalse(ok, "Validation should fail without subcontractor")
        self.assertIn('sous-traitant', message.lower(), "Message should mention subcontractor")

    def test_15_check_quotation_accepted_stage_missing_dates(self):
        """Test check_quotation_accepted_stage with missing contract dates."""
        chantier = self._create_test_chantier()
        
        ok, message = chantier.check_quotation_accepted_stage()
        
        self.assertFalse(ok, "Validation should fail without dates")
        self.assertIn('date', message.lower(), "Message should mention date")

    def test_16_check_quotation_accepted_stage_complete(self):
        """Test check_quotation_accepted_stage with all requirements."""
        chantier = self._create_test_chantier()
        
        # Create subcontractor
        subcontractor = self.env['res.partner'].create({
            'name': 'Test Subcontractor',
            'supplier_rank': 1,
        })
        
        # Create lot with subcontractor
        self.env['construction.lot'].create({
            'name': 'Test Lot',
            'code': 'TL',
            'chantier_id': chantier.id,
            'subcontractor_ids': [(6, 0, [subcontractor.id])],
        })
        
        # Set dates
        chantier.write({
            'date_start_contract': date.today(),
            'date_end_contract': date.today() + timedelta(days=30),
            'date_start_internal': date.today(),
            'date_end_internal': date.today() + timedelta(days=30),
        })
        
        ok, message = chantier.check_quotation_accepted_stage()
        
        self.assertTrue(ok, "Validation should pass with all requirements")
        self.assertEqual(message, "OK", "Message should be OK")

    # ==================== Construction Progress Stage Tests ====================

    def test_17_check_construction_25_percentage_stage(self):
        """Test check_construction_25_percentage_stage."""
        chantier = self._create_test_chantier()
        
        # Progress < 25%
        chantier.progress = 20.0
        ok, message = chantier.check_construction_25_percentage_stage()
        self.assertFalse(ok, "Should fail with progress < 25%")
        
        # Progress = 25%
        chantier.progress = 25.0
        ok, message = chantier.check_construction_25_percentage_stage()
        self.assertTrue(ok, "Should pass with progress = 25%")
        
        # Progress > 25%
        chantier.progress = 30.0
        ok, message = chantier.check_construction_25_percentage_stage()
        self.assertTrue(ok, "Should pass with progress > 25%")

    def test_18_check_construction_50_percentage_stage(self):
        """Test check_construction_50_percentage_stage."""
        chantier = self._create_test_chantier()
        
        # Progress < 50%
        chantier.progress = 40.0
        ok, message = chantier.check_construction_50_percentage_stage()
        self.assertFalse(ok, "Should fail with progress < 50%")
        
        # Progress >= 50%
        chantier.progress = 50.0
        ok, message = chantier.check_construction_50_percentage_stage()
        self.assertTrue(ok, "Should pass with progress >= 50%")

    def test_19_check_construction_75_percentage_stage(self):
        """Test check_construction_75_percentage_stage."""
        chantier = self._create_test_chantier()
        
        # Progress < 75%
        chantier.progress = 60.0
        ok, message = chantier.check_construction_75_percentage_stage()
        self.assertFalse(ok, "Should fail with progress < 75%")
        
        # Progress >= 75%
        chantier.progress = 75.0
        ok, message = chantier.check_construction_75_percentage_stage()
        self.assertTrue(ok, "Should pass with progress >= 75%")

    def test_20_check_construction_100_percentage_stage(self):
        """Test check_construction_100_percentage_stage."""
        chantier = self._create_test_chantier()
        
        # Progress < 100%
        chantier.progress = 95.0
        ok, message = chantier.check_construction_100_percentage_stage()
        self.assertFalse(ok, "Should fail with progress < 100%")
        
        # Progress = 100%
        chantier.progress = 100.0
        ok, message = chantier.check_construction_100_percentage_stage()
        self.assertTrue(ok, "Should pass with progress = 100%")

    # ==================== Warranty Stage Tests ====================

    def test_21_check_warranty_stage_incomplete_progress(self):
        """Test check_warranty_stage with incomplete progress."""
        chantier = self._create_test_chantier()
        chantier.progress = 95.0
        
        ok, message = chantier.check_warranty_stage()
        
        self.assertFalse(ok, "Should fail with progress < 100%")
        self.assertIn('réserves', message.lower(), "Message should mention reserves")

    def test_22_check_warranty_stage_no_reception_doc(self):
        """Test check_warranty_stage without reception document."""
        chantier = self._create_test_chantier()
        chantier.progress = 100.0
        
        ok, message = chantier.check_warranty_stage()
        
        self.assertFalse(ok, "Should fail without reception document")
        self.assertIn('réception', message.lower(), "Message should mention reception")

    def test_23_check_warranty_stage_complete(self):
        """Test check_warranty_stage with all requirements."""
        chantier = self._create_test_chantier()
        chantier.progress = 100.0
        
        # Create reception document
        self.env['construction.document'].create({
            'chantier_id': chantier.id,
            'name': 'Reception Document',
            'document_type': 'schedule',
        })
        
        ok, message = chantier.check_warranty_stage()
        
        self.assertTrue(ok, "Should pass with complete requirements")
        self.assertEqual(message, "OK", "Message should be OK")

    # ==================== Warranty Retention Stage Tests ====================

    def test_24_check_warranty_retention_stage_within_period(self):
        """Test check_warranty_retention_stage during warranty period."""
        chantier = self._create_test_chantier()
        chantier.date_end_contract = date.today() - timedelta(days=30)
        
        ok, message = chantier.check_warranty_retention_stage()
        
        self.assertFalse(ok, "Should fail during warranty period")
        self.assertIn('garantie', message.lower(), "Message should mention warranty")

    def test_25_check_warranty_retention_stage_after_period(self):
        """Test check_warranty_retention_stage after warranty period."""
        chantier = self._create_test_chantier()
        chantier.date_end_contract = date.today() - timedelta(days=400)
        
        ok, message = chantier.check_warranty_retention_stage()
        
        self.assertTrue(ok, "Should pass after warranty period (365 days)")
        self.assertEqual(message, "OK", "Message should be OK")

    # ==================== Dossier Finalization Stage Tests ====================

    def test_26_check_dossier_finalization_stage_no_lots(self):
        """Test check_dossier_finalization_stage with no lots."""
        chantier = self._create_test_chantier()
        
        ok, message = chantier.check_dossier_finalization_stage()
        
        self.assertFalse(ok, "Should fail without lots")
        self.assertIn('lot', message.lower(), "Message should mention lot")

    def test_27_check_dossier_finalization_stage_no_invoice_type(self):
        """Test check_dossier_finalization_stage without invoice type."""
        chantier = self._create_test_chantier()
        
        # Create lot with subcontractor
        subcontractor = self.env['res.partner'].create({
            'name': 'Test Subcontractor',
            'supplier_rank': 1,
        })
        
        self.env['construction.lot'].create({
            'name': 'Test Lot',
            'code': 'TL',
            'chantier_id': chantier.id,
            'subcontractor_ids': [(6, 0, [subcontractor.id])],
        })
        
        # Create accepted quote for subcontractor
        self.env['sale.order'].create({
            'partner_id': subcontractor.id,
            'chantier_id': chantier.id,
            'state': 'sale',
        })
        
        chantier.write({
            'date_start_contract': date.today(),
            'date_end_contract': date.today() + timedelta(days=30),
        })
        
        ok, message = chantier.check_dossier_finalization_stage()
        
        self.assertFalse(ok, "Should fail without invoice type")
        self.assertIn('cycle', message.lower(), "Message should mention cycle")

    def test_28_check_dossier_finalization_stage_no_main_quote(self):
        """Test check_dossier_finalization_stage without main quote."""
        chantier = self._create_test_chantier()
        
        # Create invoice type
        invoice_type = self.env['construction.invoice_type'].create({
            'name': 'Test Invoice Type',
            'code': 'TEST',
        })
        
        # Create lot with subcontractor
        subcontractor = self.env['res.partner'].create({
            'name': 'Test Subcontractor',
            'supplier_rank': 1,
        })
        
        self.env['construction.lot'].create({
            'name': 'Test Lot',
            'code': 'TL',
            'chantier_id': chantier.id,
            'subcontractor_ids': [(6, 0, [subcontractor.id])],
        })
        
        # Create accepted quote for subcontractor
        self.env['sale.order'].create({
            'partner_id': subcontractor.id,
            'chantier_id': chantier.id,
            'state': 'sale',
        })
        
        chantier.write({
            'invoice_type_id': invoice_type.id,
            'date_start_contract': date.today(),
            'date_end_contract': date.today() + timedelta(days=30),
        })
        
        ok, message = chantier.check_dossier_finalization_stage()
        
        self.assertFalse(ok, "Should fail without main quote")
        self.assertIn('devis principal', message.lower(), "Message should mention main quote")

