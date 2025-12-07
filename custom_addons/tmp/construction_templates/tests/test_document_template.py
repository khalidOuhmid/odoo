# -*- coding: utf-8 -*-
"""
Unit Tests for Construction Templates Module
Tests CRUD operations, constraints, and versioning
"""

from odoo.tests import common, tagged
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install', 'construction_templates')
class TestDocumentTemplate(common.TransactionCase):
    """Test Document Template Model"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Template = cls.env['construction.document.template']
        cls.SignatureZone = cls.env['construction.signature.zone']
        cls.Version = cls.env['construction.template.version']
        cls.company = cls.env.company

    def test_01_template_creation(self):
        """Test template creation with required fields"""
        template = self.Template.create({
            'name': 'Test Contract Template',
            'code': 'TEST-001',
            'template_type': 'contract',
            'html_content': '<div>Test content</div>',
        })
        
        self.assertTrue(template, "Template should be created")
        self.assertEqual(template.version, 1, "Initial version should be 1")
        self.assertFalse(template.is_active, "Template should not be active by default")

    def test_02_template_code_uniqueness(self):
        """Test template code uniqueness per company"""
        self.Template.create({
            'name': 'Template 1',
            'code': 'UNIQUE-001',
            'template_type': 'contract',
        })
        
        with self.assertRaises(Exception):
            self.Template.create({
                'name': 'Template 2',
                'code': 'UNIQUE-001',
                'template_type': 'invoice',
            })

    def test_03_active_template_constraint(self):
        """Test only one active template per type per company"""
        template1 = self.Template.create({
            'name': 'Contract Template 1',
            'code': 'CONTRACT-001',
            'template_type': 'contract',
            'is_active': True,
        })
        
        with self.assertRaises(ValidationError):
            self.Template.create({
                'name': 'Contract Template 2',
                'code': 'CONTRACT-002',
                'template_type': 'contract',
                'is_active': True,
            })

    def test_04_activate_deactivates_others(self):
        """Test action_activate deactivates other templates of same type"""
        template1 = self.Template.create({
            'name': 'Contract Template 1',
            'code': 'ACT-001',
            'template_type': 'contract',
            'is_active': True,
        })
        
        template2 = self.Template.create({
            'name': 'Contract Template 2',
            'code': 'ACT-002',
            'template_type': 'contract',
            'is_active': False,
        })
        
        template2.action_activate()
        template1.invalidate_recordset(['is_active'])
        
        self.assertTrue(template2.is_active, "Template 2 should be active")
        self.assertFalse(template1.is_active, "Template 1 should be deactivated")

    def test_05_version_snapshot_on_create(self):
        """Test version snapshot created on template creation"""
        template = self.Template.create({
            'name': 'Version Test',
            'code': 'VER-001',
            'template_type': 'contract',
            'html_content': '<div>Initial</div>',
        })
        
        self.assertEqual(len(template.version_history_ids), 1)
        self.assertEqual(template.version_history_ids[0].version_number, 1)

    def test_06_version_increment_on_content_change(self):
        """Test version increments when content changes"""
        template = self.Template.create({
            'name': 'Version Test',
            'code': 'VER-002',
            'template_type': 'contract',
            'html_content': '<div>Initial</div>',
        })
        
        initial_version = template.version
        template.write({'html_content': '<div>Updated</div>'})
        
        self.assertEqual(template.version, initial_version + 1)
        self.assertEqual(len(template.version_history_ids), 2)


@tagged('post_install', '-at_install', 'construction_templates')
class TestSignatureZone(common.TransactionCase):
    """Test Signature Zone Model"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Template = cls.env['construction.document.template']
        cls.SignatureZone = cls.env['construction.signature.zone']
        
        cls.template = cls.Template.create({
            'name': 'Test Template',
            'code': 'SIG-001',
            'template_type': 'contract',
        })

    def test_01_signature_zone_creation(self):
        """Test signature zone creation"""
        zone = self.SignatureZone.create({
            'template_id': self.template.id,
            'zone_type': 'subcontractor',
            'position_x': 10.0,
            'position_y': 80.0,
            'label': 'Signature sous-traitant',
        })
        
        self.assertTrue(zone, "Zone should be created")
        self.assertEqual(zone.width, 200.0, "Default width should be 200")
        self.assertEqual(zone.height, 80.0, "Default height should be 80")

    def test_02_position_validation(self):
        """Test position bounds validation (0-100%)"""
        with self.assertRaises(ValidationError):
            self.SignatureZone.create({
                'template_id': self.template.id,
                'zone_type': 'company',
                'position_x': 150.0,
                'position_y': 50.0,
            })
        
        with self.assertRaises(ValidationError):
            self.SignatureZone.create({
                'template_id': self.template.id,
                'zone_type': 'company',
                'position_x': -10.0,
                'position_y': 50.0,
            })

    def test_03_dimension_validation(self):
        """Test dimension validation (positive values)"""
        with self.assertRaises(ValidationError):
            self.SignatureZone.create({
                'template_id': self.template.id,
                'zone_type': 'company',
                'position_x': 10.0,
                'position_y': 50.0,
                'width': -100.0,
            })
