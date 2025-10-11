# Construction Sale Extension - Version Améliorée

Module d'extension pour la création de devis intelligents dans le contexte de projets de construction.

## 🚀 Nouvelles Fonctionnalités

### 1. Sélection de Lot Normale
- **Sélection automatique** : Les lots sont filtrés selon le chantier
- **Assignation unique** : Chaque produit est assigné à UN lot spécifique
- **Prédéfinition** : Lors de la création d'un produit, le lot est prédéfini

### 2. Unités de Mesure Configurables  
- **Large choix** : m², ml, lots, kg, pièces, heures, etc.
- **Unités BTP** : Support des unités spécifiques à la construction
- **Modification** : Changement d'unité possible à tout moment

### 3. Gestion Intelligente de la Fermeture
- **Protection** : Alerte si fermeture avec progression en cours
- **Options** :
  - Sauvegarder et fermer
  - Continuer l'assistant  
  - Fermer sans sauvegarder (avec confirmation)

### 4. Lignes Cliquables et Éditables
- **Modification directe** : Clic sur le bouton ✏️ pour modifier
- **Tous les champs** : quantité, unité, prix, lot, localisation, notes
- **Interface intuitive** : Popup d'édition dédié

### 5. Code Propre
- **PyDoc complète** : Documentation claire
- **Code épuré** : Suppression des commentaires inutiles
- **Standards Odoo 18** : Bonnes pratiques respectées

## 📋 Utilisation

1. **Sélectionner les lots** du chantier à traiter
2. **Rechercher des produits** avec les filtres
3. **Ajouter un produit** : clic sur "+" → popup avec unité de mesure
4. **Modifier une ligne** : clic sur "✏️" → édition complète
5. **Créer des produits** : "🆕 Nouveau produit" pour articles spécifiques
6. **Finaliser** : "🏁 Finaliser" pour organiser le devis par lots

## 🛡️ Sécurité

- Confirmation avant fermeture avec progression
- Sauvegarde automatique des produits ajoutés
- Validation des données en temps réel

## 🔧 Modèles Techniques

- `ConstructionQuoteWizard` : Assistant principal
- `ConstructionQuoteLine` : Lignes avec unités de mesure
- `ProductAddDialog` : Popup d'ajout avec UdM
- `ConstructionLineEditor` : Éditeur de ligne dédié  
- `WizardCancelConfirm` : Confirmation de fermeture

## 📦 Installation

Compatible **Odoo 18.0** uniquement
Dépend du module `construction_base`
