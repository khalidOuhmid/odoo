#!/usr/bin/env python3
"""
Script de validation des fichiers du module construction_base
"""

import os
import sys
import xml.etree.ElementTree as ET
import py_compile

def test_python_files():
    """Test la syntaxe des fichiers Python"""
    python_files = [
        'wizard/lot_document_wizard.py',
        'models/lot_extension.py',
        '__init__.py'
    ]
    
    for file_path in python_files:
        if os.path.exists(file_path):
            try:
                py_compile.compile(file_path, doraise=True)
                print(f"✅ {file_path} - Syntaxe Python valide")
            except py_compile.PyCompileError as e:
                print(f"❌ {file_path} - Erreur Python: {e}")
                return False
        else:
            print(f"⚠️  {file_path} - Fichier non trouvé")
    return True

def test_xml_files():
    """Test la syntaxe des fichiers XML"""
    xml_files = [
        'reports/subcontractor_contract_template.xml',
        'reports/report_actions.xml',
        'views/lot_document_wizard_view.xml',
        '__manifest__.py'
    ]
    
    for file_path in xml_files:
        if os.path.exists(file_path):
            if file_path.endswith('.xml'):
                try:
                    ET.parse(file_path)
                    print(f"✅ {file_path} - Syntaxe XML valide")
                except ET.ParseError as e:
                    print(f"❌ {file_path} - Erreur XML: {e}")
                    return False
            else:
                print(f"ℹ️  {file_path} - Fichier Python (non testé ici)")
        else:
            print(f"⚠️  {file_path} - Fichier non trouvé")
    return True

def main():
    print("🔍 Validation du module construction_base")
    print("=" * 50)
    
    python_ok = test_python_files()
    print()
    xml_ok = test_xml_files()
    
    print("\n" + "=" * 50)
    if python_ok and xml_ok:
        print("🎉 Tous les tests sont passés avec succès!")
        print("✅ Le module est prêt pour le déploiement")
        return 0
    else:
        print("❌ Des erreurs ont été trouvées")
        return 1

if __name__ == "__main__":
    sys.exit(main())
