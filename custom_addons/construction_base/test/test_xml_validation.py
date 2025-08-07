# -*- coding: utf-8 -*-
"""
Tests pour la validation des fichiers XML
"""

import xml.etree.ElementTree as ET
import os
import logging

_logger = logging.getLogger(__name__)


def test_xml_files():
    """Test de validation des fichiers XML."""
    
    # Liste des fichiers XML à tester
    xml_files = [
        'reports/subcontractor_contract_template.xml',
        'reports/report_actions.xml',
        'data/email_templates.xml',
        'views/subcontractor_contract_views.xml',
        'views/chantier_views.xml',
        'wizard/contract_preview_wizard_views.xml',
    ]
    
    errors = []
    
    for xml_file in xml_files:
        try:
            if os.path.exists(xml_file):
                ET.parse(xml_file)
                print(f"✅ {xml_file} - XML valide")
            else:
                print(f"⚠️ {xml_file} - Fichier non trouvé")
        except ET.ParseError as e:
            error_msg = f"❌ {xml_file} - Erreur XML: {e}"
            print(error_msg)
            errors.append(error_msg)
        except Exception as e:
            error_msg = f"❌ {xml_file} - Erreur: {e}"
            print(error_msg)
            errors.append(error_msg)
    
    if errors:
        print(f"\n❌ {len(errors)} erreur(s) trouvée(s):")
        for error in errors:
            print(f"  - {error}")
        return False
    else:
        print("\n✅ Tous les fichiers XML sont valides")
        return True


if __name__ == "__main__":
    test_xml_files() 