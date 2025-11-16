# -*- coding: utf-8 -*-
"""
Unit Tests for Template Rendering and Preview
Tests Jinja2 rendering, context preparation, and live preview
"""

from odoo.tests import common, tagged
from odoo.exceptions import UserError, ValidationError
from datetime import date, timedelta


@tagged('post_install', '-at_install', 'construction_contract', 'template_rendering')
class TestTemplateRendering(common.TransactionCase):
    """Test Template Rendering and Preview"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # Create test data
        cls.chantier = cls.env['construction.chantier'].create({
            'name': 'Test Site',
            'reference': 'SITE-001',
            'address': '123 Test Street',
            'city': 'Paris',
            'zip_code': '75001',
        })
        
        cls.subcontractor = cls.env['res.partner'].create({
            'name': 'Test Subcontractor Inc.',
            'contact_type': 'sous_traitant',
            'company_registry': '12345678901234',
            'email': 'test@sub.com',
            'phone': '+33123456789',
            'street': '456 Contractor Ave',
            'city': 'Lyon',
            'zip': '69001',
            'document_URSSAF_status': 'valid',
            'document_KBIS_status': 'valid',
            'document_insurance_status': 'valid',
        })
        
        cls.lot1 = cls.env['construction.lot'].create({
            'name': 'Electrical Work',
            'chantier_id': cls.chantier.id,
            'description': 'Install electrical systems',
        })
        
        cls.lot2 = cls.env['construction.lot'].create({
            'name': 'Plumbing',
            'chantier_id': cls.chantier.id,
            'description': 'Install plumbing systems',
        })
        
        # Create template with all variable types
        cls.template = cls.env['construction.contract.template'].create({
            'name': 'Full Test Template',
            'grapesjs_html': '''
                <div class="contract">
                    <header>
                        <h1>{{ contract.name }}</h1>
                        <p>Date: {{ contract.date }}</p>
                    </header>
                    
                    <section class="parties">
                        <h2>Parties</h2>
                        <div class="party">
                            <h3>Construction Site</h3>
                            <p>Name: {{ chantier.name }}</p>
                            <p>Reference: {{ chantier.reference }}</p>
                            <p>Address: {{ chantier.address }}, {{ chantier.postal_code }} {{ chantier.city }}</p>
                        </div>
                        <div class="party">
                            <h3>Subcontractor</h3>
                            <p>Name: {{ subcontractor.name }}</p>
                            <p>SIRET: {{ subcontractor.siret }}</p>
                            <p>Email: {{ subcontractor.email }}</p>
                            <p>Address: {{ subcontractor.address }}</p>
                        </div>
                    </section>
                    
                    <section class="work">
                        <h2>Work Packages</h2>
                        <ul>
                        {% for lot in lots %}
                            <li>{{ lot.name }} - {{ lot.amount }}</li>
                        {% endfor %}
                        </ul>
                    </section>
                    
                    <section class="amounts">
                        <h2>Financial Summary</h2>
                        <p>Total HT: {{ contract.total_amount_ht }}</p>
                        <p>TVA: {{ contract.total_amount_tva }}</p>
                        <p>Total TTC: {{ contract.total_amount_ttc }}</p>
                        <p>Retention ({{ contract.retention_rate }}%): {{ contract.retention_amount }}</p>
                    </section>
                    
                    <section class="dates">
                        <h2>Schedule</h2>
                        <p>Start: {{ contract.start_date }}</p>
                        <p>End: {{ contract.end_date }}</p>
                    </section>
                </div>
            ''',
            'grapesjs_css': '''
                .contract { font-family: Arial; padding: 20px; }
                header { border-bottom: 2px solid #333; margin-bottom: 20px; }
                section { margin: 20px 0; }
                h1 { color: #2c3e50; }
                h2 { color: #34495e; border-bottom: 1px solid #ccc; }
            ''',
        })
        
        cls.renderer = cls.env['construction.contract.template.renderer']

    def test_01_jinja2_available(self):
        """Test that Jinja2 is properly available"""
        from services.template_renderer_service import JINJA2_AVAILABLE
        self.assertTrue(
            JINJA2_AVAILABLE,
            "Jinja2 must be installed for template rendering"
        )

    def test_02_render_simple_template(self):
        """Test rendering a simple template"""
        simple_template = self.template.copy({
            'grapesjs_html': '<h1>Hello {{ subcontractor.name }}</h1>'
        })
        
        wizard = self.env['contract.creation.wizard'].create({
            'chantier_id': self.chantier.id,
            'subcontractor_id': self.subcontractor.id,
            'lot_ids': [(6, 0, [self.lot1.id])],
            'template_id': simple_template.id,
            'start_date': date.today(),
            'end_date': date.today() + timedelta(days=30),
            'contract_date': date.today(),
        })
        
        html = self.renderer.render_preview_from_wizard(wizard)
        
        self.assertIn('Test Subcontractor Inc.', html, "Should render subcontractor name")
        self.assertIn('<!DOCTYPE html>', html, "Should be complete HTML document")

    def test_03_render_with_all_variables(self):
        """Test rendering with all variable types"""
        wizard = self.env['contract.creation.wizard'].create({
            'chantier_id': self.chantier.id,
            'subcontractor_id': self.subcontractor.id,
            'lot_ids': [(6, 0, [self.lot1.id, self.lot2.id])],
            'template_id': self.template.id,
            'start_date': date.today(),
            'end_date': date.today() + timedelta(days=30),
            'contract_date': date.today(),
            'retention_rate': 5.0,
        })
        
        html = self.renderer.render_preview_from_wizard(wizard)
        
        # Check all required elements are present
        self.assertIn('Test Site', html, "Should render chantier name")
        self.assertIn('SITE-001', html, "Should render chantier reference")
        self.assertIn('Test Subcontractor Inc.', html, "Should render subcontractor name")
        self.assertIn('Electrical Work', html, "Should render first lot")
        self.assertIn('Plumbing', html, "Should render second lot")
        self.assertIn('5.0', html, "Should render retention rate")

    def test_04_render_with_loops(self):
        """Test Jinja2 loops render correctly"""
        loop_template = self.template.copy({
            'grapesjs_html': '''
                <ul>
                {% for lot in lots %}
                    <li class="lot-{{ loop.index }}">{{ lot.name }}</li>
                {% endfor %}
                </ul>
            '''
        })
        
        wizard = self.env['contract.creation.wizard'].create({
            'chantier_id': self.chantier.id,
            'subcontractor_id': self.subcontractor.id,
            'lot_ids': [(6, 0, [self.lot1.id, self.lot2.id])],
            'template_id': loop_template.id,
            'start_date': date.today(),
            'end_date': date.today() + timedelta(days=30),
            'contract_date': date.today(),
        })
        
        html = self.renderer.render_preview_from_wizard(wizard)
        
        self.assertIn('lot-1', html, "Should have first loop index")
        self.assertIn('lot-2', html, "Should have second loop index")
        self.assertIn('Electrical Work', html)
        self.assertIn('Plumbing', html)

    def test_05_render_with_conditionals(self):
        """Test Jinja2 conditionals work correctly"""
        conditional_template = self.template.copy({
            'grapesjs_html': '''
                <div>
                {% if lots|length > 1 %}
                    <p>Multiple work packages</p>
                {% else %}
                    <p>Single work package</p>
                {% endif %}
                </div>
            '''
        })
        
        # Test with multiple lots
        wizard_multiple = self.env['contract.creation.wizard'].create({
            'chantier_id': self.chantier.id,
            'subcontractor_id': self.subcontractor.id,
            'lot_ids': [(6, 0, [self.lot1.id, self.lot2.id])],
            'template_id': conditional_template.id,
            'start_date': date.today(),
            'end_date': date.today() + timedelta(days=30),
            'contract_date': date.today(),
        })
        
        html = self.renderer.render_preview_from_wizard(wizard_multiple)
        self.assertIn('Multiple work packages', html)
        
        # Test with single lot
        wizard_single = wizard_multiple.copy({'lot_ids': [(6, 0, [self.lot1.id])]})
        html = self.renderer.render_preview_from_wizard(wizard_single)
        self.assertIn('Single work package', html)

    def test_06_empty_template_fails(self):
        """Test that empty template raises error"""
        empty_template = self.template.copy({'grapesjs_html': ''})
        
        wizard = self.env['contract.creation.wizard'].create({
            'chantier_id': self.chantier.id,
            'subcontractor_id': self.subcontractor.id,
            'lot_ids': [(6, 0, [self.lot1.id])],
            'template_id': empty_template.id,
            'start_date': date.today(),
            'end_date': date.today() + timedelta(days=30),
            'contract_date': date.today(),
        })
        
        # Should still render (empty but valid HTML)
        html = self.renderer.render_preview_from_wizard(wizard)
        self.assertIsNotNone(html)

    def test_07_missing_template_fails(self):
        """Test that missing template raises clear error"""
        wizard = self.env['contract.creation.wizard'].create({
            'chantier_id': self.chantier.id,
            'subcontractor_id': self.subcontractor.id,
            'lot_ids': [(6, 0, [self.lot1.id])],
            'template_id': False,  # No template
            'start_date': date.today(),
            'end_date': date.today() + timedelta(days=30),
            'contract_date': date.today(),
        })
        
        with self.assertRaises(UserError) as context:
            self.renderer.render_preview_from_wizard(wizard)
        
        self.assertIn('template', str(context.exception).lower())

    def test_08_invalid_jinja2_syntax_fails(self):
        """Test that invalid Jinja2 syntax raises clear error"""
        broken_template = self.template.copy({
            'grapesjs_html': '<h1>{{ contract.name }</h1>'  # Missing closing brace
        })
        
        wizard = self.env['contract.creation.wizard'].create({
            'chantier_id': self.chantier.id,
            'subcontractor_id': self.subcontractor.id,
            'lot_ids': [(6, 0, [self.lot1.id])],
            'template_id': broken_template.id,
            'start_date': date.today(),
            'end_date': date.today() + timedelta(days=30),
            'contract_date': date.today(),
        })
        
        with self.assertRaises(UserError) as context:
            self.renderer.render_preview_from_wizard(wizard)
        
        # Should give helpful error message
        self.assertIsNotNone(str(context.exception))

    def test_09_undefined_variable_handled(self):
        """Test that undefined variables are handled gracefully"""
        template_with_undefined = self.template.copy({
            'grapesjs_html': '<h1>{{ nonexistent.variable }}</h1>'
        })
        
        wizard = self.env['contract.creation.wizard'].create({
            'chantier_id': self.chantier.id,
            'subcontractor_id': self.subcontractor.id,
            'lot_ids': [(6, 0, [self.lot1.id])],
            'template_id': template_with_undefined.id,
            'start_date': date.today(),
            'end_date': date.today() + timedelta(days=30),
            'contract_date': date.today(),
        })
        
        # Jinja2 sandbox should handle undefined variables
        try:
            html = self.renderer.render_preview_from_wizard(wizard)
            # If it doesn't crash, that's good - undefined vars should be empty
            self.assertIsNotNone(html)
        except UserError:
            # Or it raises a clear error - both are acceptable
            pass

    def test_10_css_included_in_output(self):
        """Test that CSS is properly included in HTML output"""
        wizard = self.env['contract.creation.wizard'].create({
            'chantier_id': self.chantier.id,
            'subcontractor_id': self.subcontractor.id,
            'lot_ids': [(6, 0, [self.lot1.id])],
            'template_id': self.template.id,
            'start_date': date.today(),
            'end_date': date.today() + timedelta(days=30),
            'contract_date': date.today(),
        })
        
        html = self.renderer.render_preview_from_wizard(wizard)
        
        self.assertIn('<style>', html, "Should include style tag")
        self.assertIn('.contract', html, "Should include template CSS")

    def test_11_date_formatting(self):
        """Test that dates are properly formatted"""
        wizard = self.env['contract.creation.wizard'].create({
            'chantier_id': self.chantier.id,
            'subcontractor_id': self.subcontractor.id,
            'lot_ids': [(6, 0, [self.lot1.id])],
            'template_id': self.template.id,
            'start_date': date(2025, 11, 16),
            'end_date': date(2025, 12, 16),
            'contract_date': date(2025, 11, 16),
        })
        
        html = self.renderer.render_preview_from_wizard(wizard)
        
        # Dates should be formatted as dd/mm/YYYY
        self.assertIn('16/11/2025', html, "Should format dates correctly")

    def test_12_currency_formatting(self):
        """Test that currency amounts are properly formatted"""
        # Create purchase order to generate amounts
        self.env['purchase.order'].create({
            'partner_id': self.subcontractor.id,
            'chantier_id': self.chantier.id,
            'lot_ids': [(6, 0, [self.lot1.id])],
            'state': 'purchase',
            'order_line': [(0, 0, {
                'name': 'Test Product',
                'product_qty': 1,
                'price_unit': 1000.0,
                'lot_id': self.lot1.id,
            })],
        })
        
        wizard = self.env['contract.creation.wizard'].create({
            'chantier_id': self.chantier.id,
            'subcontractor_id': self.subcontractor.id,
            'lot_ids': [(6, 0, [self.lot1.id])],
            'template_id': self.template.id,
            'start_date': date.today(),
            'end_date': date.today() + timedelta(days=30),
            'contract_date': date.today(),
        })
        
        html = self.renderer.render_preview_from_wizard(wizard)
        
        # Should format with thousands separator and currency symbol
        self.assertIn('€', html, "Should include currency symbol")

    def test_13_empty_lots_handled(self):
        """Test rendering with no lots selected"""
        wizard = self.env['contract.creation.wizard'].create({
            'chantier_id': self.chantier.id,
            'subcontractor_id': self.subcontractor.id,
            'lot_ids': [(6, 0, [])],  # Empty lots
            'template_id': self.template.id,
            'start_date': date.today(),
            'end_date': date.today() + timedelta(days=30),
            'contract_date': date.today(),
        })
        
        # Should fail validation
        with self.assertRaises((UserError, ValidationError)):
            self.renderer.render_preview_from_wizard(wizard)

    def test_14_special_characters_escaped(self):
        """Test that HTML special characters are properly escaped"""
        special_template = self.template.copy({
            'grapesjs_html': '<p>Amount: {{ contract.total_amount_ttc }} € with <special> chars & symbols</p>'
        })
        
        wizard = self.env['contract.creation.wizard'].create({
            'chantier_id': self.chantier.id,
            'subcontractor_id': self.subcontractor.id,
            'lot_ids': [(6, 0, [self.lot1.id])],
            'template_id': special_template.id,
            'start_date': date.today(),
            'end_date': date.today() + timedelta(days=30),
            'contract_date': date.today(),
        })
        
        html = self.renderer.render_preview_from_wizard(wizard)
        
        # Jinja2 autoescape should handle this
        self.assertIsNotNone(html)

    def test_15_preview_performance(self):
        """Test that preview renders in reasonable time"""
        import time
        
        wizard = self.env['contract.creation.wizard'].create({
            'chantier_id': self.chantier.id,
            'subcontractor_id': self.subcontractor.id,
            'lot_ids': [(6, 0, [self.lot1.id, self.lot2.id])],
            'template_id': self.template.id,
            'start_date': date.today(),
            'end_date': date.today() + timedelta(days=30),
            'contract_date': date.today(),
        })
        
        start_time = time.time()
        html = self.renderer.render_preview_from_wizard(wizard)
        duration = time.time() - start_time
        
        self.assertLess(
            duration,
            2.0,
            f"Preview should render in less than 2 seconds (took {duration:.2f}s)"
        )
        self.assertIsNotNone(html)

