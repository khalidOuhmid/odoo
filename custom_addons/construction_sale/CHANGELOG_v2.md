# CHANGELOG - Construction Sale Extension

## Version 2.0.0 - Améliorations Majeures

### ✨ Nouvelles Fonctionnalités

#### 🎯 Sélection de Lot Améliorée
- **AJOUTÉ** : Sélection normale de lot avec filtrage automatique selon le chantier
- **AJOUTÉ** : Assignation automatique du lot lors de la création de produit
- **AMÉLIORÉ** : Plus besoin de sélectionner manuellement le lot à chaque ajout

#### 📏 Unités de Mesure Configurables
- **AJOUTÉ** : Champ unité de mesure dans le popup d'ajout de produit
- **AJOUTÉ** : Support complet des unités BTP (m², ml, lots, kg, etc.)
- **AJOUTÉ** : Modification d'unité possible lors de l'édition de ligne
- **AJOUTÉ** : Auto-sélection de l'unité du produit par défaut

#### 🚪 Gestion Intelligente de la Fermeture
- **AJOUTÉ** : Popup de confirmation si fermeture avec progression en cours
- **AJOUTÉ** : Options multiples : sauvegarder/continuer/fermer sans sauvegarder
- **AJOUTÉ** : Bouton "Fermer l'assistant" sécurisé dans le footer
- **SUPPRIMÉ** : Risque de perte de progression avec la croix native

#### ✏️ Lignes Cliquables et Éditables
- **AJOUTÉ** : Bouton "✏️" sur chaque ligne pour édition directe
- **AJOUTÉ** : Popup d'édition dédié `ConstructionLineEditor`
- **AJOUTÉ** : Modification de tous les champs : quantité, unité, prix, lot, localisation
- **AJOUTÉ** : Validation en temps réel lors de l'édition

### 🧹 Nettoyage du Code

#### 📚 Documentation
- **AJOUTÉ** : PyDoc complète pour toutes les classes et méthodes
- **SUPPRIMÉ** : Commentaires inutiles et sections redondantes
- **AMÉLIORÉ** : Documentation claire et concise

#### 🏗️ Architecture
- **REFACTORISÉ** : Code épuré selon les standards Odoo 18
- **SUPPRIMÉ** : Code boilerplate et commentaires de section
- **AJOUTÉ** : Nouvelles classes dédiées pour chaque fonctionnalité
- **AMÉLIORÉ** : Séparation des responsabilités

#### 🔧 Modèles
- **AJOUTÉ** : `ConstructionLineEditor` pour l'édition de lignes
- **AJOUTÉ** : `WizardCancelConfirm` pour la confirmation de fermeture
- **AJOUTÉ** : Champ `uom_id` dans `ConstructionQuoteLine`
- **AMÉLIORÉ** : Méthodes `create()` avec initialisation automatique

### 🛠️ Améliorations Techniques

#### 📋 Interface Utilisateur
- **AJOUTÉ** : Colonne "Unité" dans la liste des produits sélectionnés
- **AJOUTÉ** : Champ unité de mesure dans tous les popups
- **RÉORGANISÉ** : Ordre des colonnes pour une meilleure lisibilité
- **AMÉLIORÉ** : Responsive design et accessibilité

#### 🔒 Sécurité
- **AJOUTÉ** : Accès pour les nouveaux modèles dans `ir.model.access.csv`
- **AJOUTÉ** : Validation des données avant sauvegarde
- **AMÉLIORÉ** : Gestion des erreurs utilisateur

#### ⚡ Performance
- **OPTIMISÉ** : Calculs des totaux avec gestion des valeurs nulles
- **AMÉLIORÉ** : Recherche de produits avec limite de résultats
- **NETTOYÉ** : Suppression du code redondant

### 🚫 Suppressions

- **SUPPRIMÉ** : Tous les commentaires de section (`# ===...===`)
- **SUPPRIMÉ** : Code commenté et méthodes inutilisées
- **SUPPRIMÉ** : Descriptions redondantes dans les champs
- **SUPPRIMÉ** : Attributs `attrs` dépréciés (syntaxe tree XML)

### 🐛 Corrections

- **CORRIGÉ** : Gestion du champ `product_uom` dans la création des lignes de commande
- **CORRIGÉ** : Initialisation automatique de l'unité de mesure
- **CORRIGÉ** : Validation des champs obligatoires
- **CORRIGÉ** : Retour au wizard après édition/ajout

### 📦 Compatibilité

- **CONFIRMÉ** : Compatible Odoo 18.0 uniquement
- **CONFIRMÉ** : Pas d'usage d'attributs dépréciés
- **CONFIRMÉ** : Syntaxe XML moderne sans `tree` et `attrs`
- **TESTÉ** : Intégration avec le module `construction_base`
