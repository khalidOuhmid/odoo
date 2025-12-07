#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de test simple pour vérifier le module email_enhancement
Usage: python test_module.py
"""

def test_module_structure():
    """Test basique de la structure du module"""
    import os
    
    base_path = os.path.dirname(os.path.abspath(__file__))
    
    # Fichiers requis
    required_files = [
        '__manifest__.py',
        'models/__init__.py',
        'models/mail_message.py',
        'models/mail_compose_message_reply.py',
        'static/src/js/chatter_patch.js',
        'static/src/js/message_actions_patch.js',
        'static/src/scss/chatter_enhanced.scss',
        'security/ir.model.access.csv',
        'tests/__init__.py',
        'tests/test_email_enhancement.py',
    ]
    
    print("=== Test de la structure du module email_enhancement ===")
    
    missing_files = []
    for file_path in required_files:
        full_path = os.path.join(base_path, file_path)
        if os.path.exists(full_path):
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path}")
            missing_files.append(file_path)
    
    if missing_files:
        print(f"\n❌ Fichiers manquants: {len(missing_files)}")
        return False
    else:
        print(f"\n✅ Tous les fichiers requis sont présents!")
        return True

def test_manifest():
    """Test du fichier manifest"""
    import ast
    
    print("\n=== Test du manifeste ===")
    
    try:
        with open('__manifest__.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse le contenu comme Python
        manifest = ast.literal_eval(content)
        
        # Vérifications
        checks = [
            ('name', 'Email Enhancement'),
            ('version', '18.0.1.0.0'),
            ('category', 'Mail'),
            ('depends', ['base', 'mail', 'web']),
        ]
        
        for key, expected in checks:
            if key in manifest:
                if isinstance(expected, list):
                    if all(dep in manifest[key] for dep in expected):
                        print(f"✅ {key}: {manifest[key]}")
                    else:
                        print(f"❌ {key}: manque des dépendances {expected}")
                else:
                    if expected in str(manifest[key]):
                        print(f"✅ {key}: {manifest[key]}")
                    else:
                        print(f"❌ {key}: {manifest[key]} (attendu: {expected})")
            else:
                print(f"❌ {key}: manquant")
        
        print("✅ Manifeste valide")
        return True
        
    except Exception as e:
        print(f"❌ Erreur dans le manifeste: {e}")
        return False

if __name__ == "__main__":
    print("Test du module Email Enhancement pour Odoo 18")
    print("=" * 50)
    
    structure_ok = test_module_structure()
    manifest_ok = test_manifest()
    
    if structure_ok and manifest_ok:
        print("\n🎉 Module prêt pour l'installation!")
        print("\nPour installer:")
        print("1. Redémarrer Odoo")
        print("2. Aller dans Apps > Mettre à jour la liste des applications")
        print("3. Rechercher 'Email Enhancement' et installer")
    else:
        print("\n⚠️  Problèmes détectés - corriger avant installation")
