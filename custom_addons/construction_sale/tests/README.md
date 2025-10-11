# Tests Unitaires - Module Construction Sale

Ce dossier contient tous les tests unitaires pour le module `construction_sale`.

## Structure des Tests

### 📋 `test_construction_quote_wizard.py`
**Tests pour le wizard principal de création de devis**

- **Objectif** : Valider le fonctionnement du wizard de devis intelligent
- **Couverture** : 
  - Création et initialisation du wizard
  - Calculs automatiques (totaux, sous-totaux, marges)
  - Gestion des lots et chantiers
  - Actions de création de devis
  - Validation des données
  - Gestion des erreurs
- **Classes testées** : `ConstructionQuoteWizard`
- **Méthodes importantes** : 
  - `_compute_total_amount()`
  - `action_create_quote()`
  - `action_add_product()`
  - `action_close_wizard()`

### 🛍️ `test_product_dialog.py`
**Tests pour le dialogue d'ajout de produit**

- **Objectif** : Valider l'ajout intelligent de produits avec auto-assignation
- **Couverture** :
  - Ouverture et initialisation du dialogue
  - Auto-assignation aux lots du chantier
  - Calculs de prix avec marges
  - Validation des quantités et unités de mesure
  - Actions de confirmation et annulation
- **Classes testées** : `ProductAddDialog`
- **Méthodes importantes** :
  - `_compute_available_lots()`
  - `action_add_to_lots()`
  - `action_cancel()`

### ✏️ `test_line_editor.py`
**Tests pour l'éditeur de ligne de produit**

- **Objectif** : Valider l'édition en ligne des produits ajoutés
- **Couverture** :
  - Modification des quantités et prix
  - Changement d'unités de mesure
  - Modification des informations de pièce
  - Validation des changements
  - Gestion des erreurs de saisie
- **Classes testées** : `ConstructionLineEditor`
- **Méthodes importantes** :
  - `action_save_changes()`
  - `action_cancel()`
  - `_compute_available_lots()`

### 🏭 `test_product_creator.py`
**Tests pour le créateur de produit**

- **Objectif** : Valider la création de nouveaux produits avec auto-assignation
- **Couverture** :
  - Création de produits avec validation
  - Auto-assignation aux lots du wizard
  - Validation des codes produit uniques
  - Gestion des prix et unités de mesure
  - Gestion des erreurs de création
- **Classes testées** : `ProductCreator`
- **Méthodes importantes** :
  - `action_create_product()`
  - `action_cancel()`

### 📦 `test_sale_order_extension.py`
**Tests pour l'extension du modèle sale.order**

- **Objectif** : Valider l'intégration avec les chantiers
- **Couverture** :
  - Ajout du champ `chantier_id`
  - Relations avec les lots de construction
  - Recherche et filtrage par chantier
  - Cohérence des données
- **Classes testées** : `sale.order` (extension)
- **Champs testés** : `chantier_id`

### 📄 `test_quote_line.py`
**Tests pour les lignes de devis**

- **Objectif** : Valider les calculs et la gestion des lignes
- **Couverture** :
  - Calculs de sous-totaux (quantité × prix)
  - Gestion des unités de mesure multiples
  - Informations de pièce et notes de construction
  - Calculs de marges
  - Modifications et mises à jour automatiques
- **Classes testées** : `ConstructionQuoteLine`
- **Méthodes importantes** :
  - `_compute_subtotal()`
  - Champs calculés divers

### ❌ `test_wizard_cancel_confirm.py`
**Tests pour le dialogue de confirmation d'annulation**

- **Objectif** : Valider la fermeture sécurisée du wizard
- **Couverture** :
  - Affichage des messages d'avertissement
  - Confirmation de fermeture
  - Retour au wizard (annulation)
  - Préservation des données
- **Classes testées** : `WizardCancelConfirm`
- **Méthodes importantes** :
  - `action_confirm_close()`
  - `action_cancel_return()`

## 🚀 Exécution des Tests

### Tous les tests
```bash
# Depuis le répertoire Odoo
python odoo-bin -d test_database -i construction_sale --test-enable --stop-after-init
```

### Tests spécifiques
```bash
# Test du wizard principal seulement
python odoo-bin -d test_database --test-tags construction_sale.test_construction_quote_wizard

# Test des dialogues
python odoo-bin -d test_database --test-tags construction_sale.test_product_dialog,construction_sale.test_line_editor
```

### Avec coverage
```bash
# Installation de coverage
pip install coverage

# Exécution avec couverture
coverage run --source=addons/construction_sale odoo-bin -d test_database -i construction_sale --test-enable --stop-after-init

# Rapport de couverture
coverage report -m
coverage html  # Génère un rapport HTML
```

## 📊 Couverture des Tests

### Fonctionnalités Couvertes ✅

1. **Wizard de Devis Intelligent**
   - ✅ Sélection des lots par chantier uniquement
   - ✅ Unités de mesure configurables (m², ml, lots, kg, etc.)
   - ✅ Fermeture intelligente avec confirmation
   - ✅ Lignes de produits cliquables et éditables

2. **Gestion des Produits**
   - ✅ Ajout avec auto-assignation aux lots
   - ✅ Création de nouveaux produits
   - ✅ Édition en ligne des propriétés
   - ✅ Validation des données

3. **Calculs et Automatisations**
   - ✅ Calculs de totaux et sous-totaux
   - ✅ Gestion des marges
   - ✅ Conversion d'unités de mesure
   - ✅ Mise à jour automatique des vues

4. **Interface Utilisateur**
   - ✅ Dialogues popup intelligents
   - ✅ Confirmations de sécurité
   - ✅ Navigation fluide entre les vues
   - ✅ Messages d'erreur informatifs

### Types de Tests Implémentés

- **Tests Unitaires** : Validation des méthodes individuelles
- **Tests d'Intégration** : Validation des interactions entre modèles
- **Tests de Validation** : Validation des contraintes métier
- **Tests d'Interface** : Validation des actions et transitions
- **Tests d'Erreur** : Validation de la gestion des cas d'erreur

## 📝 Documentation des Tests

Chaque test est documenté avec :

- **PyDoc complète** : Description de l'objectif du test
- **Section "Vérifie que"** : Liste claire des assertions
- **Données de test** : Configuration claire des données nécessaires
- **Commentaires inline** : Explication des étapes importantes

## 🔧 Maintenance

### Ajout de Nouveaux Tests

1. Créer le fichier dans le dossier `tests/`
2. Hériter de `TransactionCase`
3. Ajouter la classe dans `tests/__init__.py`
4. Suivre la convention de nommage : `test_[module_name].py`

### Conventions

- **Noms de classes** : `TestNomDuModele`
- **Noms de méthodes** : `test_description_specifique`
- **SetUpClass** : Configuration des données de base réutilisables
- **Assertions claires** : Messages d'erreur explicites

## 🏗️ Architecture de Test

```
tests/
├── __init__.py                      # Import de tous les tests
├── test_construction_quote_wizard.py   # Tests wizard principal
├── test_product_dialog.py             # Tests dialogue produit
├── test_line_editor.py                # Tests éditeur ligne
├── test_product_creator.py            # Tests créateur produit
├── test_sale_order_extension.py       # Tests extension commande
├── test_quote_line.py                 # Tests lignes de devis
└── test_wizard_cancel_confirm.py      # Tests confirmation fermeture
```

Chaque fichier est autonome et peut être exécuté indépendamment.
