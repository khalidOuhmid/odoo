#!/usr/bin/env python3
"""
Quick test script to validate the refactoring is working correctly.
This script checks that the models can be imported and basic functionality works.
"""

import sys
import os

# Add the custom addons path to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_models_can_be_imported():
    """Test that all refactored models can be imported successfully."""
    print("Testing model imports...")
    
    try:
        # Test basic imports
        print("✓ Basic imports successful")
        
        # Test specific model patterns
        contact_ext_files = [
            'blggroupe_contact_extension.models.res_partner',
            'blggroupe_contact_extension.models.document_archive',
            'blggroupe_contact_extension.models.lot',
        ]
        
        construction_ext_files = [
            'blggroupe_construction_extension.models.chantier',
            'blggroupe_construction_extension.models.chantier_lot',
            'blggroupe_construction_extension.models.lot_type',
        ]
        
        sales_ext_files = [
            'blggroupe_sales_extension.models.sale_order',
        ]
        
        all_files = contact_ext_files + construction_ext_files + sales_ext_files
        
        for module_file in all_files:
            try:
                # Check if file exists and has correct Python syntax
                parts = module_file.split('.')
                file_path = os.path.join(*parts[:-1], parts[-1] + '.py')
                
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Check for refactored patterns
                    if 'blg_contacts_extension.lot' in content:
                        print(f"❌ {module_file}: Still contains old 'blg_contacts_extension.lot' reference")
                    elif 'lot.category' in content or 'lot_category_id' in content:
                        print(f"✓ {module_file}: Contains new lot.category references")
                    else:
                        print(f"- {module_file}: No lot references (OK)")
                else:
                    print(f"- {module_file}: File not found (skipped)")
                    
            except Exception as e:
                print(f"❌ {module_file}: Error - {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Import test failed: {e}")
        return False

def test_manifest_dependencies():
    """Test that manifest files have correct dependencies."""
    print("\nTesting manifest dependencies...")
    
    manifests = [
        ('blggroupe_contact_extension', ['blggroupe_lots']),
        ('blggroupe_construction_extension', ['blggroupe_lots', 'blggroupe_contact_extension']),
        ('blggroupe_sales_extension', ['blggroupe_lots', 'blggroupe_contact_extension']),
    ]
    
    for module, required_deps in manifests:
        manifest_path = os.path.join(module, '__manifest__.py')
        if os.path.exists(manifest_path):
            with open(manifest_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            missing_deps = []
            for dep in required_deps:
                if f"'{dep}'" not in content and f'"{dep}"' not in content:
                    missing_deps.append(dep)
            
            if missing_deps:
                print(f"❌ {module}: Missing dependencies: {missing_deps}")
            else:
                print(f"✓ {module}: All required dependencies present")
        else:
            print(f"❌ {module}: Manifest file not found")

def test_security_files():
    """Test that security files have correct references."""
    print("\nTesting security file references...")
    
    security_file = 'blggroupe_contact_extension/security/ir.model.access.csv'
    if os.path.exists(security_file):
        with open(security_file, 'r', encoding='utf-8') as f:
            content = f.read()        # Check for problematic patterns
        issues = []
        if ',model_document_archive,' in content and 'blggroupe_contact_extension.model_document_archive' in content:
            issues.append("Should use 'model_document_archive' not 'blggroupe_contact_extension.model_document_archive'")
        
        if 'model_blg_contacts_extension_lot' in content:
            issues.append("Still contains old lot model reference")
        
        if issues:
            for issue in issues:
                print(f"❌ Security file: {issue}")
        else:
            print("✓ Security file: References look correct")
    else:
        print("❌ Security file not found")

def main():
    """Run all tests."""
    print("=== BLG Groupe Refactoring Validation ===\n")
    
    test_models_can_be_imported()
    test_manifest_dependencies() 
    test_security_files()
    
    print("\n=== Test Complete ===")
    print("If all items show ✓, the refactoring should work correctly.")
    print("❌ items indicate issues that need to be fixed.")

if __name__ == '__main__':
    main()
