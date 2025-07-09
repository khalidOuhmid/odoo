# Division de Devis par Lots

## Vue d'ensemble

La fonctionnalité de **Division de Devis** permet de diviser automatiquement un devis principal en sous-devis spécialisés par lot de construction, puis de les assigner aux sous-traitants appropriés.

## Fonctionnement

### Quand utiliser cette fonctionnalité ?

- Au stage **"Finalisation dossier"** du chantier
- Lorsque le devis principal est confirmé 
- Quand les lots sont définis et les sous-traitants assignés

### Exemple d'utilisation

**Situation initiale :**
- Devis principal : "Rénovation Villa Dupont" - 45 000€
- Contient : Général, Maçonnerie, Électricité
- Sous-traitants : 
  - Entreprise Martin (spécialisée Général)
  - Maçonnerie Durand (spécialisée Maçonnerie) 
  - Électricité Laurent (spécialisée Électricité)

**Après division :**
- Sous-devis 1 : "Général" → Entreprise Martin (15 000€)
- Sous-devis 2 : "Maçonnerie" → Maçonnerie Durand (20 000€)
- Sous-devis 3 : "Électricité" → Électricité Laurent (10 000€)

## Comment utiliser la fonctionnalité

### Méthode 1 : Division rapide
1. Aller sur le chantier au stage "Finalisation dossier"
2. Cliquer sur le bouton **"🔀 Diviser devis"** dans le header
3. La division se fait automatiquement

### Méthode 2 : Assistant guidé
1. Cliquer sur **"🧙 Assistant division"**
2. Sélectionner le devis à diviser
3. Prévisualiser la division
4. Confirmer l'opération

### Méthode 3 : Depuis l'onglet devis
1. Aller dans l'onglet "💰 Devis & Commandes"
2. Utiliser les boutons de division ou d'accès rapide

## Algorithme de division

### Analyse du devis
1. **Sections** : Détection des sections par mot-clé (📋 Général, 📋 Maçonnerie, etc.)
2. **Lignes produit** : Attribution par contexte de section ou analyse du nom/catégorie
3. **Groupement** : Regroupement par lot avec calcul des totaux

### Attribution aux sous-traitants
1. Recherche des sous-traitants spécialisés dans chaque lot
2. Attribution automatique au premier spécialisé trouvé
3. Gestion des cas sans spécialiste

### Création des sous-devis
1. Copie des informations du devis principal
2. Création des sections et lignes spécifiques au lot
3. Attribution du sous-traitant approprié
4. Mise à jour du devis principal avec les références

## Accès rapide aux sous-devis

### Bouton "⚡ Édition rapide"
- Ouvre directement le sous-devis en popup pour modification
- Idéal pour ajuster les prix ou quantités rapidement

### Bouton "📋 Voir sous-devis"
- Affiche la liste complète des sous-devis
- Groupés par sous-traitant pour navigation facile

## Sécurité et contrôles

### Pré-requis obligatoires
- ✅ Chantier au stage "Finalisation dossier" (code: FD)
- ✅ Devis confirmé (state: sale/done)
- ✅ Lots assignés au devis
- ✅ Lignes de produits présentes
- ✅ Sous-traitants assignés au chantier

### Validation
- Contrôle de cohérence des lots
- Vérification des permissions utilisateur
- Gestion des erreurs avec messages explicites

## Architecture technique

### Services utilisés
- **`QuoteSplitService`** : Logique métier de division
- **Mixins** : Intégration avec les sous-traitants via `blg_contacts_extension`

### Modèles impliqués
- `construction.chantier` : Point d'entrée
- `sale.order` : Devis principal et sous-devis
- `construction.lot` : Lots de construction
- `res.partner` : Sous-traitants

### Workflow
```
1. Validation pré-requis
2. Analyse structure du devis
3. Groupement par lots
4. Création des sous-devis
5. Attribution aux sous-traitants
6. Mise à jour des références
```

## Messages et notifications

### Succès
- Nombre de sous-devis créés
- Ouverture automatique de la vue des résultats

### Erreurs courantes
- "Stage incorrect" → Passer au stage Finalisation
- "Aucun lot" → Assigner des lots au devis
- "Pas de sous-traitants" → Assigner des sous-traitants au chantier

## Intégration avec les modules

### Compatibilité
- ✅ `construction_sale` : Extension des devis
- ✅ `blg_contacts_extension` : Gestion des sous-traitants
- ✅ `construction_lots` : Modèle standardisé des lots

### Dépendances
- Champ `lot_ids` sur `sale.order`
- Méthodes de sous-traitants sur `res.partner`
- Workflow de stages sur `construction.chantier` 