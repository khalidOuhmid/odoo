# -*- coding: utf-8 -*-
"""
Unit Tests for PDF Generation Service
Tests the WeasyPrint-based PDF generation
"""

from odoo.tests import common, tagged
from odoo.exceptions import UserError
import base64


@tagged('post_install', '-at_install', 'construction_contract', 'pdf_generation')
class TestPDFGeneration(common.TransactionCase):
    """Test PDF Generation with WeasyPrint"""

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
            # Mock required documents
            'document_URSSAF_status': 'valid',
            'document_KBIS_status': 'valid',
            'document_insurance_status': 'valid',
        })
        
        cls.lot = cls.env['construction.lot'].create({
            'name': 'Test Work Package',
            'chantier_id': cls.chantier.id,
            'description': 'Test description',
        })
        
        # Create a simple template with actual content
        cls.template = cls.env['construction.contract.template'].create({
            'name': 'Test Template',
            'grapesjs_html': '''
                <div>
                    <h1>Contract: {{ contract.name }}</h1>
                    <p>Construction Site: {{ chantier.name }}</p>
                    <p>Subcontractor: {{ subcontractor.name }}</p>
                    <p>Start Date: {{ contract.start_date }}</p>
                    <p>End Date: {{ contract.end_date }}</p>
                    <p>Total Amount: {{ contract.total_amount_ttc }}</p>
                    
                    <h2>Work Packages</h2>
                    <ul>
                    {% for lot in lots %}
                        <li>{{ lot.name }} - {{ lot.amount }}</li>
                    {% endfor %}
                    </ul>
                </div>
            ''',
            'grapesjs_css': '''
                body {
                    font-family: Arial, sans-serif;
                    margin: 20px;
                }
                h1 {
                    color: #2c3e50;
                }
                p {
                    margin: 10px 0;
                }
            ''',
        })
        
        # Create test contract
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

    def test_01_weasyprint_available(self):
        """Test that WeasyPrint is available"""
        result = self.pdf_service.test_weasyprint_installation()
        
        self.assertTrue(
            result['weasyprint_available'],
            "WeasyPrint must be installed for PDF generation"
        )
        
        self.assertTrue(
            result['test_pdf_generation'],
            f"WeasyPrint test failed: {result.get('error')}"
        )
        
        self.assertFalse(result.get('error'), f"Installation error: {result.get('error')}")

    def test_02_generate_simple_pdf(self):
        """Test generating a PDF from a simple HTML"""
        html = """
        <!DOCTYPE html>
        <html>
        <head><meta charset="UTF-8"><title>Test</title></head>
        <body>
            <h1>Test PDF</h1>
            <p>This is a test paragraph.</p>
        </body>
        </html>
        """
        
        pdf_bytes = self.pdf_service._convert_html_to_pdf(html)
        
        self.assertIsNotNone(pdf_bytes, "PDF should be generated")
        self.assertGreater(len(pdf_bytes), 100, "PDF should have reasonable size")
        
        # Check PDF magic number
        self.assertTrue(pdf_bytes.startswith(b'%PDF'), "Should be a valid PDF file")

    def test_03_generate_contract_pdf(self):
        """Test generating PDF for a contract"""
        result = self.pdf_service.generate_pdf(self.contract)
        
        self.assertTrue(result, "PDF generation should return True")
        self.assertTrue(self.contract.pdf_document, "Contract should have PDF")
        self.assertGreater(
            len(base64.b64decode(self.contract.pdf_document)),
            100,
            "PDF should have reasonable size"
        )

    def test_04_pdf_page_count(self):
        """Test PDF page counting"""
        self.pdf_service.generate_pdf(self.contract)
        
        self.assertGreater(
            self.contract.pdf_page_count,
            0,
            "PDF should have at least 1 page"
        )

    def test_05_pdf_hash_calculation(self):
        """Test PDF hash calculation for integrity"""
        self.pdf_service.generate_pdf(self.contract)
        
        self.assertTrue(
            self.contract.pdf_hash_before_signature,
            "PDF should have hash"
        )
        self.assertEqual(
            len(self.contract.pdf_hash_before_signature),
            64,
            "SHA-256 hash should be 64 characters"
        )

    def test_06_pdf_optimization(self):
        """Test PDF optimization reduces file size"""
        html = """
        <!DOCTYPE html>
        <html>
        <body>
            <h1>Test</h1>
            """ + "<p>Lorem ipsum dolor sit amet</p>" * 100 + """
        </body>
        </html>
        """
        
        pdf_original = self.pdf_service._convert_html_to_pdf(html)
        pdf_optimized = self.pdf_service._optimize_pdf(pdf_original)
        
        self.assertLessEqual(
            len(pdf_optimized),
            len(pdf_original),
            "Optimized PDF should not be larger than original"
        )

    def test_07_empty_html_fails(self):
        """Test that empty HTML raises error"""
        # Create contract with empty template
        empty_template = self.template.copy({'grapesjs_html': ''})
        contract = self.contract.copy({'template_id': empty_template.id})
        
        with self.assertRaises(UserError) as context:
            self.pdf_service.generate_pdf(contract)
        
        self.assertIn('empty', str(context.exception).lower())

    def test_08_invalid_html_fails_gracefully(self):
        """Test that invalid HTML is handled gracefully"""
        # Create template with broken Jinja2 syntax
        broken_template = self.template.copy({
            'grapesjs_html': '<h1>{{ contract.nonexistent_field }}</h1>'
        })
        contract = self.contract.copy({'template_id': broken_template.id})
        
        # Should not crash, just log warning or use empty value
        try:
            self.pdf_service.generate_pdf(contract)
        except UserError as e:
            # It's ok if it raises UserError with clear message
            self.assertIsNotNone(str(e))

    def test_09_batch_generation(self):
        """Test batch PDF generation"""
        # Create multiple contracts
        contracts = self.env['construction.contract']
        for i in range(3):
            contracts |= self.contract.copy({
                'date': f'2025-11-{16+i:02d}',
            })
        
        result = self.pdf_service.batch_generate_pdfs(contracts)
        
        self.assertEqual(result['total'], 3, "Should process 3 contracts")
        self.assertEqual(result['success'], 3, "All should succeed")
        self.assertEqual(result['errors'], 0, "No errors expected")

    def test_10_regenerate_pdf(self):
        """Test regenerating PDF for existing contract"""
        # Generate first PDF
        self.pdf_service.generate_pdf(self.contract)
        first_hash = self.contract.pdf_hash_before_signature
        
        # Regenerate
        self.pdf_service.regenerate_pdf(self.contract)
        second_hash = self.contract.pdf_hash_before_signature
        
        # Hashes should be the same if template hasn't changed
        self.assertEqual(
            first_hash,
            second_hash,
            "Regenerated PDF should have same hash if template unchanged"
        )

    def test_11_pdf_with_special_characters(self):
        """Test PDF generation with special characters (accents, etc.)"""
        # Create template with French characters
        french_template = self.template.copy({
            'grapesjs_html': '''
                <div>
                    <h1>Contrat de Sous-Traitance</h1>
                    <p>Société: {{ subcontractor.name }}</p>
                    <p>Montant: {{ contract.total_amount_ttc }} €</p>
                    <p>Caractères spéciaux: é è à ù ç œ</p>
                </div>
            '''
        })
        contract = self.contract.copy({'template_id': french_template.id})
        
        result = self.pdf_service.generate_pdf(contract)
        
        self.assertTrue(result, "Should handle special characters")
        self.assertTrue(contract.pdf_document, "PDF should be generated")

    def test_12_pdf_with_tables(self):
        """Test PDF generation with HTML tables"""
        table_template = self.template.copy({
            'grapesjs_html': '''
                <table border="1" style="width:100%; border-collapse: collapse;">
                    <thead>
                        <tr>
                            <th>Item</th>
                            <th>Amount</th>
                        </tr>
                    </thead>
                    <tbody>
                    {% for lot in lots %}
                        <tr>
                            <td>{{ lot.name }}</td>
                            <td>{{ lot.amount }}</td>
                        </tr>
                    {% endfor %}
                    </tbody>
                </table>
            '''
        })
        contract = self.contract.copy({'template_id': table_template.id})
        
        result = self.pdf_service.generate_pdf(contract)
        
        self.assertTrue(result, "Should handle HTML tables")

    def test_13_pdf_with_images(self):
        """Test PDF with embedded images (base64)"""
        # Small 1x1 red PNG in base64
        red_pixel = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
        
        image_template = self.template.copy({
            'grapesjs_html': f'''
                <div>
                    <h1>Contract with Image</h1>
                    <img src="{red_pixel}" alt="test" width="100" height="100" />
                </div>
            '''
        })
        contract = self.contract.copy({'template_id': image_template.id})
        
        result = self.pdf_service.generate_pdf(contract)
        
        self.assertTrue(result, "Should handle embedded images")

    def test_14_pdf_with_long_content(self):
        """Test PDF with long content spanning multiple pages"""
        long_template = self.template.copy({
            'grapesjs_html': '''
                <h1>Long Document</h1>
                ''' + '\n'.join([f'<p>Paragraph {i}: Lorem ipsum dolor sit amet, consectetur adipiscing elit.</p>' for i in range(200)]) + '''
            '''
        })
        contract = self.contract.copy({'template_id': long_template.id})
        
        self.pdf_service.generate_pdf(contract)
        
        self.assertGreaterEqual(
            contract.pdf_page_count,
            2,
            "Long content should span multiple pages"
        )

    def test_15_pdf_integrity_hash_changes(self):
        """Test that PDF hash changes when content changes"""
        self.pdf_service.generate_pdf(self.contract)
        first_hash = self.contract.pdf_hash_before_signature
        
        # Modify template
        self.contract.template_id.grapesjs_html += '<p>New content</p>'
        
        # Regenerate
        self.pdf_service.regenerate_pdf(self.contract)
        second_hash = self.contract.pdf_hash_before_signature
        
        self.assertNotEqual(
            first_hash,
            second_hash,
            "Hash should change when template content changes"
        )



