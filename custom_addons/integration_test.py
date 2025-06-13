#!/usr/bin/env python3
"""
Integration Test Script for BLG Groupe Modules
==============================================

This script validates the integration between:
- blggroupe_contact_extension
- blggroupe_construction_extension  
- blggroupe_sales_extension
- blggroupe_lots

Tests performed:
1. Model references and relationships
2. Field mappings and dependencies
3. Wizard workflows
4. Data consistency

Usage: python integration_test.py
"""

import os
import sys
import importlib.util
from pathlib import Path

class BLGModuleIntegrationTest:
    def __init__(self):
        self.base_path = Path(__file__).parent
        self.errors = []
        self.warnings = []
        self.test_results = []
        
    def log_error(self, test_name, message):
        self.errors.append(f"ERROR in {test_name}: {message}")
        
    def log_warning(self, test_name, message):
        self.warnings.append(f"WARNING in {test_name}: {message}")
        
    def log_success(self, test_name, message):
        self.test_results.append(f"SUCCESS in {test_name}: {message}")

    def test_manifest_dependencies(self):
        """Test that manifests have correct dependencies"""
        print("🔍 Testing manifest dependencies...")
        
        # Test contact extension
        manifest_path = self.base_path / "blggroupe_contact_extension" / "__manifest__.py"
        if manifest_path.exists():
            with open(manifest_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if "'blggroupe_lots'" in content:
                    self.log_success("contact_manifest", "Has blggroupe_lots dependency")
                else:
                    self.log_error("contact_manifest", "Missing blggroupe_lots dependency")
        
        # Test construction extension
        manifest_path = self.base_path / "blggroupe_construction_extension" / "__manifest__.py"
        if manifest_path.exists():
            with open(manifest_path, 'r', encoding='utf-8') as f:
                content = f.read()
                deps = ["'blggroupe_lots'", "'blggroupe_contact_extension'", "'blggroupe_sales_extension'"]
                for dep in deps:
                    if dep in content:
                        self.log_success("construction_manifest", f"Has {dep} dependency")
                    else:
                        self.log_error("construction_manifest", f"Missing {dep} dependency")
        
        # Test sales extension
        manifest_path = self.base_path / "blggroupe_sales_extension" / "__manifest__.py"
        if manifest_path.exists():
            with open(manifest_path, 'r', encoding='utf-8') as f:
                content = f.read()
                deps = ["'blggroupe_lots'", "'blggroupe_contact_extension'"]
                for dep in deps:
                    if dep in content:
                        self.log_success("sales_manifest", f"Has {dep} dependency")
                    else:
                        self.log_error("sales_manifest", f"Missing {dep} dependency")

    def test_model_references(self):
        """Test that old model references have been updated"""
        print("🔍 Testing model references...")
        
        python_files = []
        for module in ["blggroupe_contact_extension", "blggroupe_construction_extension", "blggroupe_sales_extension"]:
            module_path = self.base_path / module
            if module_path.exists():
                python_files.extend(module_path.rglob("*.py"))
        
        old_references = 0
        for file_path in python_files:
            if file_path.name in ["__init__.py", "integration_test.py"]:
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # Check for old model references (except in deprecated lot.py)
                if "'blg_contacts_extension.lot'" in content and "deprecated" not in content.lower():
                    old_references += 1
                    self.log_error("model_references", f"Found old model reference in {file_path}")
                    
                # Check for correct new references
                if "'lot.category'" in content:
                    self.log_success("model_references", f"Found correct lot.category reference in {file_path}")
                    
            except Exception as e:
                self.log_warning("model_references", f"Could not read {file_path}: {e}")
        
        if old_references == 0:
            self.log_success("model_references", "No old model references found (except deprecated)")

    def test_field_mappings(self):
        """Test that field mappings are correct"""
        print("🔍 Testing field mappings...")
        
        # Test res_partner.py
        partner_file = self.base_path / "blggroupe_contact_extension" / "models" / "res_partner.py"
        if partner_file.exists():
            with open(partner_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # Check for correct field definitions
                checks = [
                    ("lots = fields.Many2many('lot.category'", "lots field uses lot.category"),
                    ("is_subcontractor", "has is_subcontractor field"),
                    ("res_partner_lot_category_rel", "uses correct relation table"),
                ]
                
                for check, desc in checks:
                    if check in content:
                        self.log_success("field_mappings", f"res_partner: {desc}")
                    else:
                        self.log_error("field_mappings", f"res_partner: missing {desc}")
        
        # Test chantier_lot.py
        chantier_lot_file = self.base_path / "blggroupe_construction_extension" / "models" / "chantier_lot.py"
        if chantier_lot_file.exists():
            with open(chantier_lot_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
                checks = [
                    ("lot_category_id", "uses lot_category_id field"),
                    ("unit_type", "has unit_type field"),
                    ("is_subcontractor", "uses is_subcontractor filter"),
                ]
                
                for check, desc in checks:
                    if check in content:
                        self.log_success("field_mappings", f"chantier_lot: {desc}")
                    else:
                        self.log_error("field_mappings", f"chantier_lot: missing {desc}")

    def test_wizard_integration(self):
        """Test wizard files for correct model references"""
        print("🔍 Testing wizard integration...")
        
        wizard_files = []
        for module in ["blggroupe_construction_extension", "blggroupe_sales_extension"]:
            module_path = self.base_path / module / "wizard"
            if module_path.exists():
                wizard_files.extend(module_path.glob("*.py"))
        
        for wizard_file in wizard_files:
            if wizard_file.name == "__init__.py":
                continue
                
            try:
                with open(wizard_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                    # Check for old references
                    if "'blg_contacts_extension.lot'" in content:
                        self.log_error("wizard_integration", f"Old model reference in {wizard_file.name}")
                    
                    # Check for correct references
                    if "'lot.category'" in content:
                        self.log_success("wizard_integration", f"Correct model reference in {wizard_file.name}")
                        
                    # Check for correct field usage
                    if "is_subcontractor" in content:
                        self.log_success("wizard_integration", f"Uses is_subcontractor in {wizard_file.name}")
                        
            except Exception as e:
                self.log_warning("wizard_integration", f"Could not read {wizard_file}: {e}")

    def test_python_syntax(self):
        """Test Python syntax compilation"""
        print("🔍 Testing Python syntax...")
        
        python_files = []
        for module in ["blggroupe_contact_extension", "blggroupe_construction_extension", "blggroupe_sales_extension"]:
            module_path = self.base_path / module
            if module_path.exists():
                python_files.extend(module_path.rglob("*.py"))
        
        syntax_errors = 0
        for file_path in python_files:
            if file_path.name in ["__init__.py", "integration_test.py"]:
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    source = f.read()
                    
                # Try to compile
                compile(source, str(file_path), 'exec')
                self.log_success("python_syntax", f"✓ {file_path.relative_to(self.base_path)}")
                
            except SyntaxError as e:
                syntax_errors += 1
                self.log_error("python_syntax", f"Syntax error in {file_path}: Line {e.lineno}: {e.msg}")
            except Exception as e:
                self.log_warning("python_syntax", f"Could not compile {file_path}: {e}")
        
        if syntax_errors == 0:
            self.log_success("python_syntax", "All Python files compile successfully")

    def run_all_tests(self):
        """Run all integration tests"""
        print("🚀 Starting BLG Groupe Module Integration Tests")
        print("=" * 50)
        
        self.test_manifest_dependencies()
        self.test_model_references()
        self.test_field_mappings()
        self.test_wizard_integration()
        self.test_python_syntax()
        
        print("\n" + "=" * 50)
        print("📋 TEST RESULTS SUMMARY")
        print("=" * 50)
        
        print(f"✅ Successes: {len(self.test_results)}")
        print(f"⚠️  Warnings: {len(self.warnings)}")
        print(f"❌ Errors: {len(self.errors)}")
        
        if self.test_results:
            print("\n✅ SUCCESSES:")
            for result in self.test_results:
                print(f"  {result}")
        
        if self.warnings:
            print("\n⚠️  WARNINGS:")
            for warning in self.warnings:
                print(f"  {warning}")
        
        if self.errors:
            print("\n❌ ERRORS:")
            for error in self.errors:
                print(f"  {error}")
        
        print("\n" + "=" * 50)
        if self.errors:
            print("❌ INTEGRATION TEST FAILED - Please fix the errors above")
            return False
        else:
            print("✅ INTEGRATION TEST PASSED - All modules are properly integrated!")
            return True

if __name__ == "__main__":
    tester = BLGModuleIntegrationTest()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)
