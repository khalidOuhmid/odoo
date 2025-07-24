# 🔄 Résumé des Changements - Migration Lots v1.0.1

## ✅ Problème Résolu

**Avant :** Les lots étaient partagés entre tous les chantiers (Many2many)
- Modifier un lot sur le Chantier A modifiait le même lot sur le Chantier B

**Après :** Chaque chantier a ses propres lots (One2many)
- Chaque chantier a ses propres instances de lots, complètement indépendantes

## 📋 Fichiers Modifiés

### 1. **Modèles principaux**

#### `construction_base/models/chantier.py`
- ✅ Changé `lots_ids` de `Many2many` vers `One2many`
- ✅ Ajouté méthode `_create_default_lots()` pour créer les lots automatiquement
- ✅ Ajouté méthode `action_select_main_quote()` pour sélectionner le devis principal
- ✅ Ajouté méthode `_update_lots_prices_from_quote()` pour calculer les prix des lots

#### `construction_base/models/lot_extension.py`
- ✅ Ajouté champ `chantier_id` (Many2one, required)
- ✅ Ajouté champ `price_from_quote` calculé depuis le devis principal
- ✅ Modifié `currency_id` pour utiliser celle du chantier
- ✅ Mis à jour toutes les méthodes pour utiliser la relation directe

### 2. **Wizards**

#### `construction_base/wizard/quote_selection_wizard.py` (NOUVEAU)
- ✅ Wizard pour sélectionner le devis principal du chantier
- ✅ Calcul automatique des prix des lots après sélection

#### `construction_base/wizard/__init__.py`
- ✅ Ajouté import du nouveau wizard

### 3. **Vues**

#### `construction_base/views/chantier_views.xml`
- ✅ Ajouté bouton "Sélectionner devis principal" (visible stage ≥ 3)
- ✅ Ajouté champ `main_quote_id` dans le formulaire
- ✅ Ajouté colonne `price_from_quote` dans l'onglet lots

#### `construction_base/views/quote_selection_wizard_views.xml` (NOUVEAU)
- ✅ Vue formulaire pour le wizard de sélection

### 4. **Migration**

#### `construction_base/migrations/1.0.1/post-migrate.py` (NOUVEAU)
- ✅ Script de migration automatique
- ✅ Convertit les relations Many2many existantes

#### `construction_base/data/migration_actions.xml` (NOUVEAU)
- ✅ Action serveur pour migration manuelle via interface

#### `construction_base/__manifest__.py`
- ✅ Version mise à jour vers 1.0.1
- ✅ Ajout des nouveaux fichiers

## 🎯 Nouvelles Fonctionnalités

### 1. **Sélection du Devis Principal** (Stage 3+)
```
Action: "Sélectionner devis principal"
Résultat: Wizard de sélection + calcul automatique des prix des lots
```

### 2. **Calcul Automatique des Prix**
- Nouveau champ `price_from_quote` dans chaque lot
- Calcul basé sur les lignes du devis principal
- Affichage côte-à-côte avec le prix estimé

### 3. **Création Automatique des Lots**
- À la création d'un nouveau chantier
- Basé sur tous les modèles de lots existants

## 🔧 Instructions de Test

### 1. **Mise à jour du module**
```bash
# Via interface Odoo
Apps > Construction Base > Upgrade
```

### 2. **Vérification post-migration**
1. ✅ Chaque chantier doit avoir ses lots dans l'onglet "Lots de travaux"
2. ✅ Créer un nouveau chantier → lots automatiquement créés
3. ✅ Tester la sélection du devis principal (stage ≥ 3)

### 3. **Test complet**
```python
# Test via odoo-shell (optionnel)
chantier = env['construction.chantier'].search([], limit=1)
print(f"Chantier: {chantier.name}")
print(f"Lots: {len(chantier.lots_ids)}")
for lot in chantier.lots_ids:
    print(f"  - {lot.name} (Chantier: {lot.chantier_id.name})")
```

### 4. **Migration manuelle si nécessaire**
- Menu: Paramètres > Technique > Actions serveur
- Rechercher: "Migrer les lots vers chantiers spécifiques"
- Exécuter l'action

## 🚨 Points d'Attention

### Compatibilité
- Le champ `lot_selection_ids` maintient la compatibilité avec les anciens modules
- Les vues existantes continuent de fonctionner

### Contraintes
- Chaque lot doit maintenant appartenir à un chantier (`required=True`)
- La devise du lot suit celle du chantier

## 🆘 Résolution de Problèmes

### Erreur: "chantier_id is required"
```python
# Solution: Exécuter la migration
env['construction.chantier'].search([])._create_default_lots()
```

### Lots manquants après migration
```python
# Solution: Recréer pour un chantier spécifique
chantier = env['construction.chantier'].browse(ID_CHANTIER)
chantier._create_default_lots()
```

### Prix non calculés
```python
# Solution: Forcer le recalcul
chantier._update_lots_prices_from_quote()
```

---

**✅ Migration prête pour déploiement !**

Tous les fichiers sont modifiés et testés. La migration devrait se faire automatiquement lors de la mise à jour du module vers la v1.0.1.
