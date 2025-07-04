# 🔧 Guide de Dépannage - Construction Sale

## 🚨 Erreurs Courantes et Solutions

### **Erreur Many2many Conflict**
```
TypeError: Many2many fields [...] use the same table and columns
```

**✅ Solution :**
1. **Tables explicites** - Tous les champs Many2many ont maintenant des noms de tables distincts
2. **Migration propre** - Script de nettoyage des tables conflictuelles

**Fichiers corrigés :**
- `models/blg_compatibility.py` - Tables Many2many explicites
- `data/migration_script.py` - Nettoyage automatique

### **Erreur CSV Index Out of Range**
```
IndexError: list index out of range
```

**✅ Solution :**
1. **Suppression des lignes vides** dans `security/ir.model.access.csv`
2. **Suppression des commentaires** qui perturbent le parser CSV
3. **Validation du format** : exactement 8 colonnes par ligne

**Fichier corrigé :**
- `security/ir.model.access.csv` - Format CSV standard

### **Erreur Model Not Found**
```
ValueError: Model 'xxx' not found
```

**✅ Solution :**
1. **Suppression des références** aux modèles non existants dans `ir.model.access.csv`
2. **Ordre de chargement** - Les modèles de base sont chargés avant les wizards

## 🔄 Processus de Migration

### **Étape 1 : Sauvegarde**
```bash
# Sauvegarde de la base de données
pg_dump -U odoo -h localhost blgtest > backup_pre_migration.sql
```

### **Étape 2 : Mise à jour du module**
```bash
# Dans le conteneur Odoo
odoo -u construction_sale -d blgtest --stop-after-init
```

### **Étape 3 : Exécution du script de migration**
```python
# Dans le shell Odoo
env = self.env
from odoo.addons.construction_sale.data.migration_script import migrate_construction_sale
migrate_construction_sale(env)
env.cr.commit()
```

### **Étape 4 : Vérification**
```python
# Vérifier que les modèles sont accessibles
env['construction.product.wizard']
env['construction.quick.product.wizard']
env['blg.quick.product.wizard']
```

## 🛠️ Scripts de Diagnostic

### **Vérifier les modèles**
```python
models_to_check = [
    'construction.product.wizard',
    'construction.product.line',
    'construction.quick.product.wizard',
    'sale.order'  # Extension
]

for model in models_to_check:
    try:
        count = env[model].search_count([])
        print(f"✓ {model}: {count} enregistrements")
    except Exception as e:
        print(f"❌ {model}: {str(e)}")
```

### **Vérifier les droits d'accès**
```python
access_records = env['ir.model.access'].search([
    ('model_id.model', 'like', 'construction.%')
])
for access in access_records:
    print(f"✓ {access.model_id.model}: {access.name}")
```

### **Vérifier les vues**
```python
views = env['ir.ui.view'].search([
    ('model', 'like', 'construction.%')
])
for view in views:
    print(f"✓ Vue {view.name}: {view.model}")
```

## 📋 Checklist Post-Migration

### **✅ Fonctionnalités de base**
- [ ] Création de devis depuis chantier
- [ ] Organisation par lots
- [ ] Ajout de produits via wizard
- [ ] Création rapide de produits
- [ ] Sauvegarde des localisations

### **✅ Interface utilisateur**
- [ ] Vues kanban avec styles modernes
- [ ] Wizards fonctionnels
- [ ] Notifications utilisateur
- [ ] Navigation fluide

### **✅ Compatibilité BLG**
- [ ] Anciens wizards accessibles
- [ ] Données existantes préservées
- [ ] Migration transparente
- [ ] Coexistence des systèmes

## 🚨 Erreurs Connues et Contournements

### **Erreur de référence de catégorie**
**Symptôme :** `ValidationError: Category is required`

**Solution :**
```python
# Forcer une catégorie par défaut
default_category = env.ref('product.product_category_all')
products_without_category = env['product.product'].search([
    ('categ_id', '=', False)
])
products_without_category.write({'categ_id': default_category.id})
```

### **Problème de cache des assets**
**Symptôme :** Styles kanban non appliqués

**Solution :**
```bash
# Redémarrer Odoo et vider le cache navigateur
docker restart docker-odoo_web-1
# F5 + Ctrl+Shift+R dans le navigateur
```

### **Conflit de wizard existant**
**Symptôme :** `IntegrityError: duplicate key value`

**Solution :**
```python
# Supprimer les wizards en conflit
conflicting_wizards = env['construction.product.wizard'].search([])
conflicting_wizards.unlink()
env.cr.commit()
```

## 📞 Support Technique

### **Logs de diagnostic**
```bash
# Activer les logs détaillés
docker exec -it docker-odoo_web-1 grep -i "construction" /var/log/odoo/odoo.log | tail -50
```

### **Mode debug Odoo**
```
# URL avec mode debug
http://localhost:8069/web?debug=1
```

### **Shell Python interactif**
```bash
# Accès au shell Odoo
docker exec -it docker-odoo_web-1 odoo shell -d blgtest
```

---

**📧 Contact Support :** dev@blggroupe.com  
**🕐 Dernière mise à jour :** Janvier 2025 