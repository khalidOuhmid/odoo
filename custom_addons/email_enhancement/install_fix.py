# -*- coding: utf-8 -*-
"""
Patch d'installation pour le module email_enhancement
Corrige les problèmes d'installation identifiés
"""

def apply_installation_fixes():
    """Applique les corrections nécessaires pour l'installation"""
    print("🔧 Application des corrections d'installation...")
    
    # 1. Vérifier que le fichier de sécurité est vide (pas de nouveau modèle)
    import os
    security_file = 'security/ir.model.access.csv'
    
    if os.path.exists(security_file):
        with open(security_file, 'r') as f:
            content = f.read().strip()
        
        # Ne doit contenir que l'en-tête
        expected_content = "id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink"
        
        if content == expected_content:
            print("✅ Fichier de sécurité correct")
        else:
            print("⚠️  Correction du fichier de sécurité...")
            with open(security_file, 'w') as f:
                f.write(expected_content)
            print("✅ Fichier de sécurité corrigé")
    
    # 2. Vérifier la structure des modèles
    models_init = 'models/__init__.py'
    if os.path.exists(models_init):
        with open(models_init, 'r') as f:
            content = f.read()
        
        if 'mail_compose_message' in content and 'mail_message' in content:
            print("✅ Imports des modèles corrects")
        else:
            print("⚠️  Problème dans les imports des modèles")
    
    print("🎉 Module prêt pour l'installation!")
    return True

if __name__ == "__main__":
    apply_installation_fixes()
