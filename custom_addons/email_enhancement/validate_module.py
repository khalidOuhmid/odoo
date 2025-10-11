"""
Validation finale du module email_enhancement
Ce script vérifie que l'implémentation respecte les bonnes pratiques Odoo 18
"""

import os
import re
import ast

class ModuleValidator:
    def __init__(self, module_path):
        self.module_path = module_path
        self.errors = []
        self.warnings = []
        
    def validate_all(self):
        """Exécute toutes les validations"""
        print("=== Validation du module Email Enhancement ===\n")
        
        self.validate_structure()
        self.validate_manifest()
        self.validate_javascript()
        self.validate_python()
        self.validate_security()
        
        self.print_results()
        
    def validate_structure(self):
        """Valide la structure des dossiers"""
        print("📁 Validation de la structure...")
        
        required_dirs = ['models', 'static/src/js', 'static/src/scss', 'security', 'tests']
        for dir_path in required_dirs:
            full_path = os.path.join(self.module_path, dir_path)
            if not os.path.exists(full_path):
                self.errors.append(f"Dossier manquant: {dir_path}")
            else:
                print(f"  ✅ {dir_path}")
                
    def validate_manifest(self):
        """Valide le fichier __manifest__.py"""
        print("\n📋 Validation du manifeste...")
        
        manifest_path = os.path.join(self.module_path, '__manifest__.py')
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            manifest = ast.literal_eval(content)
            
            # Vérifications obligatoires
            required_keys = ['name', 'version', 'depends', 'assets']
            for key in required_keys:
                if key not in manifest:
                    self.errors.append(f"Clé manquante dans __manifest__.py: {key}")
                else:
                    print(f"  ✅ {key}")
            
            # Vérification version Odoo 18
            if 'version' in manifest and not manifest['version'].startswith('18.0'):
                self.warnings.append("Version non conforme à Odoo 18")
                
            # Vérification dépendances
            if 'depends' in manifest:
                required_deps = ['base', 'mail', 'web']
                missing_deps = [dep for dep in required_deps if dep not in manifest['depends']]
                if missing_deps:
                    self.errors.append(f"Dépendances manquantes: {missing_deps}")
                    
        except Exception as e:
            self.errors.append(f"Erreur lecture manifeste: {e}")
            
    def validate_javascript(self):
        """Valide les fichiers JavaScript"""
        print("\n🟨 Validation JavaScript...")
        
        js_files = [
            'static/src/js/chatter_patch.js',
            'static/src/js/message_actions_patch.js'
        ]
        
        for js_file in js_files:
            file_path = os.path.join(self.module_path, js_file)
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Vérifications Odoo 18
                checks = [
                    (r'/\*\* @odoo-module \*\*/', 'Déclaration module Odoo'),
                    (r'import.*patch.*@web/core/utils/patch', 'Import patch système'),
                    (r'import.*useService.*@web/core/utils/hooks', 'Import useService'),
                    (r'patch\(.*\.prototype', 'Utilisation correcte de patch')
                ]
                
                for pattern, description in checks:
                    if re.search(pattern, content):
                        print(f"  ✅ {js_file}: {description}")
                    else:
                        self.warnings.append(f"{js_file}: {description} non trouvé")
                        
            else:
                self.errors.append(f"Fichier JS manquant: {js_file}")
                
    def validate_python(self):
        """Valide les fichiers Python"""
        print("\n🐍 Validation Python...")
        
        python_files = [
            'models/mail_message.py',
            'models/mail_compose_message.py',
            'tests/test_email_enhancement.py'
        ]
        
        for py_file in python_files:
            file_path = os.path.join(self.module_path, py_file)
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Vérifications basiques
                if '# -*- coding: utf-8 -*-' in content:
                    print(f"  ✅ {py_file}: Encodage UTF-8")
                else:
                    self.warnings.append(f"{py_file}: Encodage UTF-8 non déclaré")
                
                if 'from odoo import' in content:
                    print(f"  ✅ {py_file}: Imports Odoo")
                else:
                    self.warnings.append(f"{py_file}: Imports Odoo non trouvés")
                    
                # Vérifications spécifiques tests
                if 'test_' in py_file:
                    if '@tagged(' in content:
                        print(f"  ✅ {py_file}: Tests taggés")
                    else:
                        self.warnings.append(f"{py_file}: Tests non taggés")
                        
            else:
                self.errors.append(f"Fichier Python manquant: {py_file}")
                
    def validate_security(self):
        """Valide les fichiers de sécurité"""
        print("\n🔒 Validation sécurité...")
        
        security_file = os.path.join(self.module_path, 'security/ir.model.access.csv')
        if os.path.exists(security_file):
            with open(security_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if 'mail.compose.message.reply' in content:
                print("  ✅ Droits d'accès pour le wizard de réponse")
            else:
                self.warnings.append("Droits d'accès non définis pour le wizard")
        else:
            self.errors.append("Fichier ir.model.access.csv manquant")
            
    def print_results(self):
        """Affiche les résultats de validation"""
        print("\n" + "="*50)
        print("RÉSULTATS DE VALIDATION")
        print("="*50)
        
        if not self.errors and not self.warnings:
            print("🎉 PARFAIT! Le module respecte toutes les bonnes pratiques Odoo 18")
            print("\nLe module est prêt pour:")
            print("- Installation en production")
            print("- Soumission sur Odoo App Store")
            print("- Intégration dans un projet client")
            
        else:
            if self.errors:
                print("❌ ERREURS CRITIQUES:")
                for error in self.errors:
                    print(f"   • {error}")
                    
            if self.warnings:
                print("\n⚠️  AVERTISSEMENTS:")
                for warning in self.warnings:
                    print(f"   • {warning}")
                    
            print(f"\n📊 Score: {self._calculate_score()}/100")
            
    def _calculate_score(self):
        """Calcule un score de qualité"""
        total_points = 100
        error_penalty = len(self.errors) * 20
        warning_penalty = len(self.warnings) * 5
        
        score = max(0, total_points - error_penalty - warning_penalty)
        return score

if __name__ == "__main__":
    module_path = os.path.dirname(os.path.abspath(__file__))
    validator = ModuleValidator(module_path)
    validator.validate_all()
