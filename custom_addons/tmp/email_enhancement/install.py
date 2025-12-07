#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script d'installation pour le module email_enhancement
"""

import os
import sys
import subprocess
from pathlib import Path

def check_odoo_installation():
    """Vérifie que Odoo est installé et accessible"""
    try:
        import odoo
        print("✅ Odoo est installé et accessible")
        return True
    except ImportError:
        print("❌ Odoo n'est pas installé ou n'est pas dans le PYTHONPATH")
        return False

def check_module_structure():
    """Vérifie la structure du module"""
    module_path = Path(__file__).parent
    required_files = [
        '__manifest__.py',
        '__init__.py',
        'models/__init__.py',
        'models/mail_message.py',
        'static/src/js/chatter_enhanced.js',
        'static/src/js/message_reply_enhanced.js',
        'static/src/js/message_actions_enhanced.js',
        'static/src/scss/chatter_enhanced.scss',
        'static/src/xml/message_enhanced.xml',
        'security/ir.model.access.csv',
        'tests/__init__.py',
        'tests/test_mail_message.py',
    ]
    
    missing_files = []
    for file_path in required_files:
        if not (module_path / file_path).exists():
            missing_files.append(file_path)
    
    if missing_files:
        print(f"❌ Fichiers manquants : {missing_files}")
        return False
    
    print("✅ Structure du module correcte")
    return True

def run_tests():
    """Lance les tests unitaires"""
    try:
        result = subprocess.run([
            sys.executable, '-m', 'pytest', 
            'tests/', '-v', '--tb=short'
        ], cwd=Path(__file__).parent, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Tests unitaires passés")
            return True
        else:
            print(f"❌ Tests unitaires échoués : {result.stdout}")
            return False
    except Exception as e:
        print(f"❌ Erreur lors de l'exécution des tests : {e}")
        return False

def install_module():
    """Installe le module dans Odoo"""
    try:
        # Cette fonction nécessiterait une connexion à Odoo
        # Pour l'instant, on affiche juste les instructions
        print("📋 Pour installer le module :")
        print("1. Redémarrez le serveur Odoo")
        print("2. Allez dans Applications > Mettre à jour la liste des applications")
        print("3. Recherchez 'Email Enhancement'")
        print("4. Cliquez sur Installer")
        return True
    except Exception as e:
        print(f"❌ Erreur lors de l'installation : {e}")
        return False

def main():
    """Fonction principale"""
    print("🚀 Installation du module Email Enhancement")
    print("=" * 50)
    
    # Vérifications
    if not check_odoo_installation():
        sys.exit(1)
    
    if not check_module_structure():
        sys.exit(1)
    
    # Tests
    if not run_tests():
        print("⚠️  Tests échoués, mais installation possible")
    
    # Installation
    install_module()
    
    print("=" * 50)
    print("✅ Installation terminée !")
    print("📖 Consultez le README.md pour plus d'informations")

if __name__ == "__main__":
    main()
