# Changelog des modifications - Module Construction Sale

## Version 18.0.1.1.0 - Modifications demandées

### 🎯 Modifications principales

#### 1. **Inversion de la position du numéro de salle et de la localisation**
- **Fichier modifié** : `wizards/popup_views.xml`
- **Changement** : Dans le popup d'ajout de produit, la localisation apparaît maintenant avant le numéro de salle
- **Impact** : Interface plus intuitive avec la localisation en premier

#### 2. **Injection du lot concerné lors de l'ajout d'un produit**
- **Fichier modifié** : `wizards/quote_wizard.py`
- **Changement** : Le lot est maintenant automatiquement assigné lors de la création des lignes de devis
- **Impact** : Organisation automatique des produits par lots dans le devis

#### 3. **Ajout d'unités de mesure BTP**
- **Fichiers créés** : 
  - `data/construction_uom_data.xml` - Nouvelles unités de mesure BTP
  - `data/construction_product_categories.xml` - Catégories de produits BTP
  - `data/construction_products_data.xml` - Produits BTP d'exemple
- **Nouvelles unités** : m², m, kg, t, L, m³, pièce, ml, h, jour
- **Impact** : Support complet des unités de mesure du BTP

#### 4. **Retour sur l'instance du wizard de création de devis**
- **Fichier modifié** : `wizards/quote_wizard.py`
- **Changement** : 
  - Nouvelle méthode `action_finalize_quote()` pour finaliser le devis
  - Modification de `action_confirm_selection()` pour rester sur le wizard
  - Bouton "🏁 Finaliser le devis" ajouté dans l'interface
- **Impact** : Possibilité de continuer à ajouter des produits sans perdre la progression

#### 5. **Suppression de l'ajout automatique du produit au devis**
- **Fichier modifié** : `wizards/quote_wizard.py`
- **Changement** : 
  - Suppression des champs `add_to_quote` et `quantity` du modèle `ProductCreator`
  - Suppression de la méthode `_add_product_to_quote()`
  - Les produits créés ne sont plus automatiquement ajoutés au devis
- **Impact** : Contrôle total sur l'ajout des produits au devis

#### 6. **Injection du nom du chantier lors de la création d'un devis**
- **Fichier modifié** : `models/sale_order_extension.py`
- **Changement** : 
  - Ajout de la méthode `create()` pour injecter automatiquement le nom du chantier
  - Modification de `_onchange_chantier_id()` pour mettre à jour le nom du devis
- **Impact** : Les devis sont automatiquement nommés "Devis - [Nom du chantier]"

### 🔧 Modifications techniques

#### Modifications du wizard (`wizards/quote_wizard.py`)
- Ajout du champ `uom_id` dans le modèle `ProductCreator`
- Ajout des méthodes `_get_default_uom_id()` et `_get_default_category_id()`
- Modification de l'ordre d'affichage des informations de localisation
- Ajout de la méthode `action_finalize_quote()`

#### Modifications des vues (`wizards/popup_views.xml`)
- Inversion de l'ordre des champs localisation et numéro de salle
- Ajout du champ unité de mesure dans le popup de création de produit

#### Modifications des vues du wizard (`wizards/quote_wizard_views.xml`)
- Ajout du bouton "🏁 Finaliser le devis"
- Modification du bouton "✅ Finaliser le devis" en "✅ Ajouter au devis"

#### Modifications du modèle sale.order (`models/sale_order_extension.py`)
- Ajout de la méthode `create()` pour l'injection automatique du nom du chantier
- Modification de `_onchange_chantier_id()` pour la mise à jour du nom

#### Nouveaux fichiers de données
- `data/construction_uom_data.xml` : Unités de mesure BTP
- `data/construction_product_categories.xml` : Catégories de produits BTP
- `data/construction_products_data.xml` : Produits BTP d'exemple

### 📋 Manifeste (`__manifest__.py`)
- Ajout des nouveaux fichiers de données dans la section `data`

### 🎨 Interface utilisateur
- **Popup d'ajout de produit** : Localisation avant numéro de salle
- **Popup de création de produit** : Ajout du champ unité de mesure
- **Wizard principal** : Nouveau bouton "🏁 Finaliser le devis"
- **Organisation** : Produits automatiquement organisés par lots

### 🚀 Fonctionnalités ajoutées
1. **Gestion complète des unités de mesure BTP** : m², m, kg, t, L, m³, etc.
2. **Catégories de produits spécialisées BTP** : Matériaux, Finition, Équipements, Prestations
3. **Produits d'exemple BTP** : Peinture, carrelage, isolation, plomberie, électricité, etc.
4. **Workflow amélioré** : Possibilité de continuer à ajouter des produits sans perdre la progression
5. **Nommage automatique des devis** : Injection du nom du chantier

### 🔄 Workflow utilisateur amélioré
1. **Création d'un devis** : Le nom du chantier est automatiquement injecté
2. **Sélection des lots** : Les lots du chantier sont pré-sélectionnés
3. **Ajout de produits** : Chaque produit est assigné à un lot spécifique
4. **Création de produits** : Possibilité de choisir l'unité de mesure appropriée
5. **Organisation** : Les produits sont automatiquement organisés par sections de lots
6. **Progression** : Possibilité de continuer à ajouter des produits ou de finaliser le devis

### ✅ Tests recommandés
1. Créer un nouveau devis depuis un chantier
2. Vérifier que le nom du chantier est injecté automatiquement
3. Ajouter des produits avec différentes unités de mesure
4. Créer un nouveau produit personnalisé avec une unité de mesure BTP
5. Vérifier l'organisation par lots dans le devis final
6. Tester le workflow de progression (ajouter puis finaliser)

---

**Note** : Toutes les modifications respectent les standards Odoo 18 et les principes SOLID. Le code est compatible avec les modules existants et n'ajoute pas de code boilerplate inutile.

