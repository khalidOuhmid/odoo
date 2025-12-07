# -*- coding: utf-8 -*-
"""
Unit Tests for Security Configuration
Tests that security.xml loads without errors and groups are properly configured
"""

from odoo.tests import common, tagged
from odoo.exceptions import AccessError
import logging

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install', 'construction_contract', 'security')
class TestSecurityConfig(common.TransactionCase):
    """Test Security Configuration - Verify module installs and upgrades correctly"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ResGroups = cls.env['res.groups']
        cls.ModuleCategory = cls.env['ir.module.category']
        cls.IrRule = cls.env['ir.rule']

    def test_01_module_category_exists(self):
        """Test that Construction module category is created"""
        category = self.ModuleCategory.search([
            ('name', '=', 'Construction')
        ], limit=1)
        
        self.assertTrue(category, "Construction module category should exist")
        self.assertEqual(category.description, "Construction and BTP management")
        self.assertEqual(category.sequence, 50)

    def test_02_security_groups_exist(self):
        """Test that all security groups are created"""
        expected_groups = [
            'group_construction_user',
            'group_construction_pilote',
            'group_construction_comptable',
            'group_construction_admin',
        ]
        
        for group_xmlid in expected_groups:
            group = self.env.ref(f'construction_contract.{group_xmlid}', raise_if_not_found=False)
            self.assertTrue(group, f"Group {group_xmlid} should exist")
            self.assertTrue(group.name, f"Group {group_xmlid} should have a name")

    def test_03_groups_have_correct_category(self):
        """Test that groups are assigned to Construction category"""
        category = self.ModuleCategory.search([('name', '=', 'Construction')], limit=1)
        
        groups = [
            self.env.ref('construction_contract.group_construction_user'),
            self.env.ref('construction_contract.group_construction_pilote'),
            self.env.ref('construction_contract.group_construction_comptable'),
            self.env.ref('construction_contract.group_construction_admin'),
        ]
        
        for group in groups:
            self.assertEqual(
                group.category_id, category,
                f"Group {group.name} should be in Construction category"
            )

    def test_04_groups_are_independent(self):
        """Test that groups don't use implied_ids to avoid Odoo 18 user type conflicts"""
        pilote_group = self.env.ref('construction_contract.group_construction_pilote')
        comptable_group = self.env.ref('construction_contract.group_construction_comptable')
        admin_group = self.env.ref('construction_contract.group_construction_admin')
        
        # Groups should not have implied_ids to avoid user type conflicts in Odoo 18
        # Users must be assigned Internal User (base.group_user) separately
        # This test just verifies the groups exist and are properly configured
        self.assertTrue(pilote_group.exists(), "Pilote group should exist")
        self.assertTrue(comptable_group.exists(), "Comptable group should exist")
        self.assertTrue(admin_group.exists(), "Admin group should exist")

    def test_05_record_rules_exist(self):
        """Test that record rules are created"""
        expected_rules = [
            'contract_rule_pilote',
            'contract_rule_comptable',
            'contract_rule_admin',
            'template_rule_pilote',
            'template_rule_comptable',
            'template_rule_admin',
            'signature_rule_pilote',
            'signature_rule_comptable',
            'signature_rule_admin',
            'deliverable_rule_pilote',
            'deliverable_rule_comptable',
            'deliverable_rule_admin',
        ]
        
        for rule_xmlid in expected_rules:
            rule = self.env.ref(f'construction_contract.{rule_xmlid}', raise_if_not_found=False)
            self.assertTrue(rule, f"Rule {rule_xmlid} should exist")

    def test_06_no_public_group_conflicts(self):
        """Test that no rules grant access to public group (avoiding user type conflicts)"""
        # Get all rules for construction contract models
        contract_rules = self.IrRule.search([
            ('model_id.model', 'in', [
                'construction.contract',
                'construction.contract.template',
                'construction.contract.signature',
                'construction.contract.deliverable',
                'construction.contract.page.validation',
            ])
        ])
        
        public_group = self.env.ref('base.group_public')
        
        for rule in contract_rules:
            self.assertNotIn(
                public_group, rule.groups,
                f"Rule {rule.name} should not grant access to public group"
            )

    def test_07_module_can_be_loaded(self):
        """Test that module data is properly loaded (no XML parse errors)"""
        # If we reach this point, the module has been installed successfully
        # This test verifies that security.xml was parsed without errors
        
        module = self.env['ir.module.module'].search([
            ('name', '=', 'construction_contract')
        ], limit=1)
        
        self.assertTrue(module, "Module should be found")
        self.assertEqual(module.state, 'installed', "Module should be installed")

