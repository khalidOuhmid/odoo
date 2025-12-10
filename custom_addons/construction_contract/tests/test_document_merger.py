# -*- coding: utf-8 -*-
"""
Unit Tests for PDF Merger Service
Tests the multi-document merging functionality
"""

from odoo.tests import common, tagged
from odoo.exceptions import UserError
import base64
import io


@tagged('post_install', '-at_install', 'construction_contract', 'pdf_merger')
class TestDocumentMerger(common.TransactionCase):
    """Test PDF Document Merger"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # Create test data
        cls.chantier = cls.env['construction.chantier'].create({
            'name': 'Test Construction Site',
            'reference': 'SITE-001',
            'address': '123 Test Street',
            'city': 'Paris',
            'zip_code': '75001',
        })
        
        cls.subcontractor = cls.env['res.partner'].create({
            'name': 'Test Subcontractor',
            'contact_type': 'sous_traitant',
            'company_registry': '12345678901234',
            'email': 'test@subcontractor.com',
            'phone': '+33123456789',
            'document_URSSAF_status': 'valid',
            'document_KBIS_status': 'valid',
            'document_insurance_status': 'valid',
        })
        
        cls.lot = cls.env['construction.lot'].create({
            'name': 'Test Work Package',
            'chantier_id': cls.chantier.id,
            'description': 'Test description',
        })
        
        cls.template = cls.env['construction.contract.template'].create({
            'name': 'Test Template',
            'grapesjs_html': '<h1>Contract: {{ contract.name }}</h1><p>Test content</p>',
            'grapesjs_css': 'body { font-family: Arial; }',
        })
        
        cls.contract = cls.env['construction.contract'].create({
            'chantier_id': cls.chantier.id,
            'subcontractor_id': cls.subcontractor.id,
            'lot_ids': [(6, 0, [cls.lot.id])],
            'template_id': cls.template.id,
            'date': '2025-11-16',
            'start_date': '2025-11-16',
            'end_date': '2025-12-16',
            'retention_rate': 5.0,
        })
        
        cls.pdf_service = cls.env['construction.contract.pdf.generator']
        cls.merger_service = cls.env['construction.contract.pdf.merger']
        
        # Generate main contract PDF
        cls.pdf_service.generate_pdf(cls.contract)

    def _create_simple_pdf(self, content="Test PDF"):
        """Helper to create a simple PDF for testing"""
        try:
            from weasyprint import HTML
            html = f"""
            <!DOCTYPE html>
            <html>
            <head><meta charset="UTF-8"></head>
            <body>
                <h1>{content}</h1>
                <p>This is a test PDF document.</p>
            </body>
            </html>
            """
            pdf_bytes = HTML(string=html).write_pdf()
            return base64.b64encode(pdf_bytes)
        except ImportError:
            # Fallback: create minimal PDF manually
            # This is a minimal valid PDF structure
            pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /Resources 4 0 R /MediaBox [0 0 612 792] /Contents 5 0 R >>
endobj
4 0 obj
<< /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >>
endobj
5 0 obj
<< /Length 44 >>
stream
BT
/F1 12 Tf
100 700 Td
(Test PDF) Tj
ET
endstream
endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000214 00000 n 
0000000304 00000 n 
trailer
<< /Size 6 /Root 1 0 R >>
startxref
398
%%EOF"""
            return base64.b64encode(pdf_content)

    def test_01_validate_pdf_format(self):
        """Test PDF format validation"""
        # Valid PDF
        valid_pdf = self._create_simple_pdf()
        self.assertTrue(
            self.merger_service.validate_pdf_format(base64.b64decode(valid_pdf)),
            "Should validate correct PDF"
        )
        
        # Invalid PDF (not a PDF)
        invalid_pdf = b"This is not a PDF"
        self.assertFalse(
            self.merger_service.validate_pdf_format(invalid_pdf),
            "Should reject non-PDF content"
        )
        
        # Empty data
        self.assertFalse(
            self.merger_service.validate_pdf_format(b""),
            "Should reject empty data"
        )

    def test_02_merge_contract_with_single_attachment(self):
        """Test merging contract with one attachment"""
        # Create deliverable with PDF
        deliverable = self.env['construction.contract.deliverable'].create({
            'contract_id': self.contract.id,
            'name': 'Planning Document',
            'deliverable_type': 'planning_general',
            'document': self._create_simple_pdf("Planning"),
            'document_name': 'planning.pdf',
            'merge_in_contract': True,
            'merge_order': 10,
        })
        
        # Merge
        merged_pdf = self.merger_service.merge_contract_with_attachments(self.contract)
        
        self.assertIsNotNone(merged_pdf, "Should return merged PDF")
        self.assertGreater(len(merged_pdf), 0, "Merged PDF should have content")
        self.assertTrue(merged_pdf.startswith(b'%PDF'), "Should be valid PDF")

    def test_03_merge_contract_with_multiple_attachments(self):
        """Test merging contract with multiple attachments in order"""
        # Create multiple deliverables
        deliverables = []
        for i, (name, doc_type, order) in enumerate([
            ('Planning General', 'planning_general', 10),
            ('Planning Subcontractor', 'planning_subcontractor', 20),
            ('Purchase Order', 'purchase_order', 30),
        ]):
            deliverable = self.env['construction.contract.deliverable'].create({
                'contract_id': self.contract.id,
                'name': name,
                'deliverable_type': doc_type,
                'document': self._create_simple_pdf(name),
                'document_name': f'{name.lower().replace(" ", "_")}.pdf',
                'merge_in_contract': True,
                'merge_order': order,
            })
            deliverables.append(deliverable)
        
        # Merge
        merged_pdf = self.merger_service.merge_contract_with_attachments(self.contract)
        
        self.assertIsNotNone(merged_pdf, "Should return merged PDF")
        self.assertTrue(merged_pdf.startswith(b'%PDF'), "Should be valid PDF")
        
        # Verify merged PDF is larger than individual PDFs
        main_pdf_size = len(base64.b64decode(self.contract.pdf_document))
        self.assertGreater(
            len(merged_pdf),
            main_pdf_size,
            "Merged PDF should be larger than main contract PDF"
        )

    def test_04_merge_validates_pdf_format(self):
        """Test that non-PDF attachments are rejected"""
        # Create deliverable with non-PDF content
        self.env['construction.contract.deliverable'].create({
            'contract_id': self.contract.id,
            'name': 'Invalid Document',
            'deliverable_type': 'other',
            'document': base64.b64encode(b"Not a PDF"),
            'document_name': 'invalid.pdf',
            'merge_in_contract': True,
            'merge_order': 10,
        })
        
        # Should raise error
        with self.assertRaises(UserError) as context:
            self.merger_service.merge_contract_with_attachments(self.contract)
        
        self.assertIn('not a valid PDF', str(context.exception))

    def test_05_merge_without_attachments_returns_main_pdf(self):
        """Test that merge without attachments returns main PDF unchanged"""
        # No deliverables marked for merge
        merged_pdf = self.merger_service.merge_contract_with_attachments(self.contract)
        
        main_pdf = base64.b64decode(self.contract.pdf_document)
        
        self.assertEqual(
            merged_pdf,
            main_pdf,
            "Should return main PDF when no attachments to merge"
        )

    def test_06_merge_respects_merge_order(self):
        """Test that deliverables are merged in correct order"""
        # Create deliverables with specific order
        deliverables = []
        for order, name in [(30, 'Third'), (10, 'First'), (20, 'Second')]:
            deliverable = self.env['construction.contract.deliverable'].create({
                'contract_id': self.contract.id,
                'name': name,
                'deliverable_type': 'other',
                'document': self._create_simple_pdf(name),
                'document_name': f'{name.lower()}.pdf',
                'merge_in_contract': True,
                'merge_order': order,
            })
            deliverables.append(deliverable)
        
        # Preview merge structure
        preview = self.merger_service.preview_merge_structure(self.contract)
        
        self.assertEqual(preview['section_count'], 4, "Should have 4 sections (main + 3 attachments)")
        
        # Check order (after main contract)
        section_names = [s['name'] for s in preview['sections'][1:]]
        self.assertEqual(section_names, ['First', 'Second', 'Third'], "Should be in correct order")

    def test_07_merge_only_includes_marked_deliverables(self):
        """Test that only deliverables marked for merge are included"""
        # Create deliverables, some marked for merge, some not
        self.env['construction.contract.deliverable'].create({
            'contract_id': self.contract.id,
            'name': 'To Merge',
            'deliverable_type': 'planning_general',
            'document': self._create_simple_pdf("To Merge"),
            'document_name': 'to_merge.pdf',
            'merge_in_contract': True,
            'merge_order': 10,
        })
        
        self.env['construction.contract.deliverable'].create({
            'contract_id': self.contract.id,
            'name': 'Not To Merge',
            'deliverable_type': 'other',
            'document': self._create_simple_pdf("Not To Merge"),
            'document_name': 'not_to_merge.pdf',
            'merge_in_contract': False,
            'merge_order': 20,
        })
        
        # Preview
        preview = self.merger_service.preview_merge_structure(self.contract)
        
        self.assertEqual(preview['section_count'], 2, "Should have 2 sections (main + 1 marked)")

    def test_08_merge_fails_without_main_pdf(self):
        """Test that merge fails if main contract PDF doesn't exist"""
        # Create new contract without PDF
        contract_no_pdf = self.contract.copy({
            'date': '2025-11-17',
        })
        contract_no_pdf.write({'pdf_document': False})
        
        # Should raise error
        with self.assertRaises(UserError) as context:
            self.merger_service.merge_contract_with_attachments(contract_no_pdf)
        
        self.assertIn('must be generated', str(context.exception).lower())

    def test_09_get_mergeable_deliverables(self):
        """Test getting list of deliverables that can be merged"""
        # Create mix of valid and invalid deliverables
        valid_deliverable = self.env['construction.contract.deliverable'].create({
            'contract_id': self.contract.id,
            'name': 'Valid PDF',
            'deliverable_type': 'planning_general',
            'document': self._create_simple_pdf("Valid"),
            'document_name': 'valid.pdf',
        })
        
        invalid_deliverable = self.env['construction.contract.deliverable'].create({
            'contract_id': self.contract.id,
            'name': 'Invalid PDF',
            'deliverable_type': 'other',
            'document': base64.b64encode(b"Not a PDF"),
            'document_name': 'invalid.pdf',
        })
        
        # Get mergeable
        mergeable = self.merger_service.get_mergeable_deliverables(self.contract)
        
        self.assertIn(valid_deliverable, mergeable, "Should include valid PDF")
        self.assertNotIn(invalid_deliverable, mergeable, "Should exclude invalid PDF")

    def test_10_preview_merge_structure(self):
        """Test preview of merge structure"""
        # Create deliverables
        self.env['construction.contract.deliverable'].create({
            'contract_id': self.contract.id,
            'name': 'Planning',
            'deliverable_type': 'planning_general',
            'document': self._create_simple_pdf("Planning"),
            'document_name': 'planning.pdf',
            'merge_in_contract': True,
            'merge_order': 10,
        })
        
        # Preview
        preview = self.merger_service.preview_merge_structure(self.contract)
        
        self.assertIn('section_count', preview)
        self.assertIn('sections', preview)
        self.assertIn('total_size_kb', preview)
        self.assertEqual(preview['section_count'], 2, "Should have 2 sections")
        
        # Check section details
        for section in preview['sections']:
            self.assertIn('name', section)
            self.assertIn('type', section)
            self.assertIn('size_kb', section)
            self.assertIn('is_valid', section)

    def test_11_integration_generate_and_merge(self):
        """Test full integration: generate PDF and merge with attachments"""
        # Create deliverable
        self.env['construction.contract.deliverable'].create({
            'contract_id': self.contract.id,
            'name': 'Purchase Order',
            'deliverable_type': 'purchase_order',
            'document': self._create_simple_pdf("Purchase Order"),
            'document_name': 'po.pdf',
            'merge_in_contract': True,
            'merge_order': 10,
        })
        
        # Regenerate PDF (should trigger merge)
        self.contract.action_generate_pdf()
        
        # Verify PDF was updated
        self.assertTrue(self.contract.pdf_document, "Should have PDF")
        
        # PDF should be larger than before (includes merged document)
        # Note: This is a basic check, actual size depends on TOC generation

    def test_12_merge_with_empty_deliverable_document(self):
        """Test that deliverables without documents are skipped"""
        # Create deliverable without document
        self.env['construction.contract.deliverable'].create({
            'contract_id': self.contract.id,
            'name': 'No Document',
            'deliverable_type': 'other',
            'document': False,
            'document_url': 'http://example.com/doc.pdf',
            'merge_in_contract': True,
            'merge_order': 10,
        })
        
        # Should not fail, just skip the deliverable
        merged_pdf = self.merger_service.merge_contract_with_attachments(self.contract)
        
        self.assertIsNotNone(merged_pdf, "Should return PDF")
        
        # Should be same as main PDF (no merge happened)
        main_pdf = base64.b64decode(self.contract.pdf_document)
        self.assertEqual(merged_pdf, main_pdf, "Should skip deliverable without document")
