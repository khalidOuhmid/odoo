#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test rapide des corrections appliquées
"""

def test_field_corrections():
    """Test que les corrections de champs sont bonnes"""
    print("🔍 Vérification des corrections de champs...")
    
    # Lire le fichier mail_compose_message.py
    with open('models/mail_compose_message.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Vérifications
    checks = [
        ('author_id', 'Utilise author_id au lieu de author'),
        ('parent_message.author_id', 'Accès correct au champ author_id'),
    ]
    
    for pattern, description in checks:
        if pattern in content:
            print(f"  ✅ {description}")
        else:
            print(f"  ❌ {description}")
    
    # Vérifier qu'on n'utilise plus l'ancien champ
    if 'parent_message.author' in content and 'parent_message.author_id' not in content:
        print("  ❌ Utilise encore l'ancien champ 'author'")
    elif 'parent_message.author_id' in content:
        print("  ✅ Utilise le bon champ 'author_id'")
    
    # Lire le fichier JavaScript
    with open('static/src/js/message_actions_patch.js', 'r', encoding='utf-8') as f:
        js_content = f.read()
    
    print("\n🟨 Vérification JavaScript...")
    
    if 'message.author_id' in js_content:
        print("  ✅ JavaScript utilise author_id")
    else:
        print("  ❌ JavaScript n'utilise pas author_id")
    
    if 'message.author?.partner' in js_content:
        print("  ❌ JavaScript utilise encore l'ancien pattern")
    else:
        print("  ✅ JavaScript n'utilise plus l'ancien pattern")
    
    print("\n🎉 Vérifications terminées!")

if __name__ == "__main__":
    test_field_corrections()
