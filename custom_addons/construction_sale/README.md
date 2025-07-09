# 🏗️ Construction Sale Extension

**Module Odoo moderne et épuré pour la gestion des devis construction**

[![Version](https://img.shields.io/badge/version-2.0.0-green.svg)](https://github.com/blggroupe)
[![Odoo](https://img.shields.io/badge/odoo-17.0-blue.svg)](https://www.odoo.com)
[![License](https://img.shields.io/badge/license-LGPL--3-orange.svg)](https://www.gnu.org/licenses/lgpl-3.0)

## 📋 Vue d'ensemble

Le module **Construction Sale Extension** est une extension intelligente pour la création de devis dans le contexte de projets de construction. Il s'intègre parfaitement avec le module `construction_base` pour offrir une expérience utilisateur moderne et efficace.

## ✨ Fonctionnalités principales

### 🚀 Assistant intelligent de devis

- **Interface moderne** : Wizard intuitif avec design contemporain
- **Gestion par lots** : Organisation automatique des produits par lots de construction
- **Recherche avancée** : Filtrage intelligent des produits par catégorie et lots
- **Intégration native** : Liaison directe avec les chantiers de construction

### 📋 Gestion des devis construction

- **Validation intelligente** : Progression automatique des étapes de chantier
- **Organisation automatique** : Création de sections par lots
- **Informations détaillées** : Localisation par pièce, niveau, notes techniques
- **Statistiques temps réel** : Compteurs de lignes, quantités, montants

### 🎨 Interface utilisateur

- **Design moderne** : Interface responsive avec animations fluides
- **Feedback visuel** : Notifications et indicateurs de progression
- **UX optimisée** : Double-clic pour ajouter, glisser-déposer, recherche instantanée

## 🏗️ Architecture refactorisée

### **Structure modulaire**

```
construction_sale/
├── __manifest__.py                 # Configuration du module
├── README.md                       # Documentation
├── models/
│   ├── __init__.py
│   ├── sale_order_extension.py     # Extension sale.order (SOLID)
│   └── product_template.py         # Extension product.template
├── wizards/
│   ├── __init__.py
│   ├── quote_wizard.py             # Wizard principal (clean code)
│   └── quote_wizard_views.xml      # Vues XML du wizard
├── views/
│   ├── modern_wizards.xml          # Interface moderne principale
│   └── sale_order_views.xml        # Vues sale.order adaptées
├── static/src/
│   ├── scss/
│   │   └── quote_builder.scss      # Styles modernes
│   └── js/
│       └── quote_builder.js        # Interactions JavaScript
├── security/
│   └── ir.model.access.csv         # Droits d'accès
└── data/
    ├── product_category_data.xml   # Catégories de produits
    └── product_sequence_data.xml   # Séquences automatiques
```

### **Séparation des responsabilités**

| Module | Responsabilité |
|--------|---------------|
| `sale_order_extension.py` | 🎯 **Logique métier moderne** - Actions, calculs, workflow |
| `product_wizard.py` | 🧙 **Assistant principal** - Recherche et sélection de produits |

## 🚀 Installation

### **Prérequis**
- Odoo 17.0+
- Module `construction_base` installé
- Module `blggroupe_lots` (pour compatibilité BLG)

### **Installation standard**
```bash
# 1. Copier le module
cp -r construction_sale /path/to/odoo/addons/

# 2. Redémarrer Odoo
sudo systemctl restart odoo

# 3. Installer depuis l'interface
# Apps > construction_sale > Install
```

## 💼 Utilisation

### **Workflow principal**

1. **📋 Créer un devis depuis un chantier**
   ```
   Chantier → Bouton "Créer devis" → Devis avec chantier pré-rempli
   ```

2. **🏗️ Organiser par lots**
   ```
   Devis → "📋 Organiser par lots" → Sections automatiques créées
   ```

3. **➕ Ajouter des produits**
   ```
   Devis → "➕ Ajouter produits" → Wizard moderne → Sélection par lot
   ```

4. **📍 Préciser la localisation**
   ```
   Lignes devis → Pièce, Étage, Notes → Information complète
   ```

### **Interface moderne**

#### **🔍 Recherche de produits**
- **Filtres intelligents** : Nom, catégorie, prix
- **Vue Kanban** : Cartes produits avec images
- **Ajout rapide** : Clic sur "+" pour ajouter

#### **🛒 Panier de sélection**
- **Vue tableau** : Édition en ligne des quantités
- **Localisation** : Pièce et étage par ligne
- **Total temps réel** : Calcul automatique

#### **⚡ Création rapide**
- **Formulaire simplifié** : Nom, prix, catégorie
- **Catégorie intelligente** : Suggestion selon le lot
- **Aperçu** : Nom final généré automatiquement

## 🔧 Configuration

### **Catégories de produits**
Le module crée automatiquement une hiérarchie de catégories :

```
📂 Construction
  ├── 🔨 Démolition
  ├── 🧱 Maçonnerie  
  ├── 🚿 Plomberie CVC
  ├── ⚡ Électricité
  ├── 🚪 Menuiserie extérieure
  ├── 🚪 Menuiserie intérieure
  ├── 🎨 Peinture & finition
  ├── 🏠 Sol souple et parquet
  └── 🏺 Carrelage & faïence
```

### **États personnalisés**
Nouveaux états pour les devis construction :
- **✅ Validé** : Devis accepté par le client
- **❌ Sans suite** : Devis abandonné

### **Champs spécialisés**
Extensions pour les lignes de devis :
- **📍 Localisation** : `room_location` (Ex: "Salon")
- **🏢 Niveau** : `floor_level` (Ex: "Rez-de-chaussée")  
- **📝 Notes** : `construction_notes` (Instructions techniques)

## 🔄 Migration depuis l'ancienne version

### **Automatique**
- ✅ **Données préservées** : Aucune perte de devis existants
- ✅ **Compatibilité BLG** : Anciens wizards fonctionnent
- ✅ **Nouvelle interface** : Disponible immédiatement

### **Manuelle (recommandée)**
```python
# Script de migration des devis existants
def migrate_quotes():
    orders = env['sale.order'].search([('state', 'in', ['draft', 'sent'])])
    for order in orders:
        # Associer au chantier si possible
        if order.blg_chantier_id:
            order.chantier_id = find_matching_chantier(order.blg_chantier_id)
        
        # Convertir les lots BLG vers lots construction
        if order.lot_selection_ids:
            order.lot_ids = convert_blg_lots(order.lot_selection_ids)
```

## 🐛 Dépannage

### **Erreurs courantes**

#### **❌ "Field undefined" pour BLG**
```bash
# Solution : Installer la compatibilité BLG
pip install --upgrade construction_sale
# OU désactiver temporairement les modules BLG
```

#### **❌ "Catégorie manquante" pour produits**
```python
# Recréer les catégories
env['product.category'].search([('name', '=', 'Construction')]).unlink()
# Puis réinstaller le module
```

#### **❌ Interface ancienne affichée**
```bash
# Vider le cache navigateur + F5
# OU redémarrer Odoo en mode debug
```

## 🚀 Roadmap

### **Version 2.1** (Q2 2025)
- [ ] 📱 **Application mobile** pour saisie terrain
- [ ] 🤖 **IA suggestion** produits selon chantier  
- [ ] 📊 **Tableaux de bord** avancés
- [ ] 🔄 **Synchronisation** avec logiciels tiers

### **Version 2.2** (Q3 2025)
- [ ] 🏷️ **Code-barres** pour inventaire
- [ ] 📸 **Photos produits** intégrées
- [ ] 🗂️ **Templates devis** pré-configurés
- [ ] 💬 **Chat intégré** avec équipes

## 🤝 Contribution

### **Développement**
```bash
# 1. Fork le projet
git clone https://github.com/blggroupe/construction_sale

# 2. Créer une branche
git checkout -b feature/nouvelle-fonctionnalite

# 3. Développer et tester
# 4. Soumettre une pull request
```

### **Signaler un bug**
- 📧 **Email** : dev@blggroupe.com
- 🐛 **Issues** : GitHub Issues
- 💬 **Chat** : Teams BLG IT

## 📄 Licence

Ce module est sous licence **LGPL-3.0**. Voir le fichier [LICENSE](LICENSE) pour plus de détails.

---

## 📞 Support

- **📧 Email** : support@blggroupe.com
- **📱 Téléphone** : +33 1 23 45 67 89
- **🌐 Site web** : [www.blggroupe.com](https://www.blggroupe.com)
- **📚 Documentation** : [docs.blggroupe.com](https://docs.blggroupe.com)

---

<div align="center">

**Développé avec ❤️ par l'équipe BLG IT**

*Construction Sale Extension - Simplifiez vos devis construction avec Odoo*

</div> 