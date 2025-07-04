# Module Construction Base - BLG Groupe

Module de gestion des chantiers BTP pour BLG Groupe, développé selon le cahier des charges pour optimiser et réduire le temps consacré aux tâches administratives et à la planification des chantiers.

## Vue d'ensemble

Ce module fournit une solution complète pour la gestion des projets de construction, organisée en trois modules complémentaires :

- **construction_base** : Module principal de gestion des travaux
- **construction_lots** : Gestion des lots de construction
- **construction_sale** : Gestion des ventes et devis

## Structure du Workflow

### Chapitres et Étapes

Le module organise les chantiers selon 6 chapitres principaux :

#### 1. Appel d'offre
- **Réception** : Création initiale du chantier
- **Visite technique** : Organisation et suivi des visites sur site
- **Devis envoyé** : Envoi du devis au client

#### 2. Préparation chantier
- **Devis accepté** : Confirmation de la commande
- **Finalisation dossier** : Préparation administrative et technique

#### 3. Travaux
- Progression par paliers : 0-25%, 25-50%, 50-75%, 75-100%
- Facturation automatique aux seuils de 30%, 60% et 90%

#### 4. Levée de réserves/Attente de paiement
- **Levée de réserves** : Traitement des réserves client
- **Attente de paiement** : Suivi des paiements

#### 5. Retenue garantie
- Gestion automatique de la retenue de 5% pendant 1 an

#### 6. Archive
- **Dossier clôturé** : Archivage des projets terminés
- **Sans suite** : Projets abandonnés

## Profils Utilisateurs et Droits d'Accès

### Directeur Général
- Accès complet à l'ensemble de l'ERP
- Peut forcer les changements d'étapes

### Conductrice de Travaux
- Accès au module gestion des travaux
- Restriction sur la modification de l'état des chantiers
- Doit respecter le workflow défini

### Administrateur BLG
- Droits d'administration complets
- Peut forcer l'état d'un chantier
- Gestion des paramètres système

## Fonctionnalités Principales

### 1. Création et Suivi des Chantiers

**Champs disponibles :**
- Référence automatique (CH/YYYY/00001)
- Nom du chantier
- Client (référence contact)
- Adresse complète du chantier
- Téléphone
- Dates contractuelles et internes (début/fin)
- Dates réelles (début/fin)
- Coût total
- Timer visuel avec indicateur de couleur pour les échéances
- Personnes assignées (équipe)
- Étiquettes (tags)
- Progression (%)

**Import depuis Email :**
- Création de chantier par wizard
- L'objet devient le nom du chantier
- Le corps est importé dans la description
- Extraction automatique du téléphone et de l'adresse

### 2. Gestion des Visites Techniques

- Interface optimisée pour utilisation terrain
- Champs date et personnes assignées
- Attachement de documents multiples
- Notes et observations
- Intégration avec le calendrier

### 3. Gestion des Devis

**Système de sélection par lots :**
- Général
- Démolition
- Maçonnerie
- Plâtrerie
- Plomberie CVC
- Électricité
- Menuiserie extérieure
- Menuiserie intérieure
- Peinture & finition
- Sol souple et parquet
- Carrelage & faïence

**Fonctionnalités :**
- Wizard de création de devis intelligent
- Filtrage des produits par lot
- Génération PDF
- Boutons "Devis validé" et "Sans suite"
- Progression automatique du workflow

### 4. Facturation par Paliers

**Paliers de facturation :**
- 30% : Premier acompte
- 60% : Deuxième acompte
- 90% : Troisième acompte avec retenue de garantie
- 100% : Solde final

**Retenue de garantie :**
- 5% automatiquement calculé
- Durée : 1 an
- Gestion automatique de la libération

### 5. Suivi de l'Avancement

**Progression :**
- Calcul automatique basé sur les lots terminés
- Indicateurs visuels (couleurs)
- Alertes pour les échéances

**États du chantier :**
- Actif
- Suspendu
- Terminé
- Abandonné

### 6. Sécurité et Workflow

**Contrôle du workflow :**
- Progression séquentielle obligatoire pour la conductrice de travaux
- Validation des conditions avant passage à l'étape suivante
- Messages d'information sur les conditions requises

**Traçabilité :**
- Historique complet des modifications
- Messages automatiques lors des changements d'étapes
- Intégration avec le système de messagerie Odoo

## Installation

1. Placer les modules dans le dossier `addons` d'Odoo
2. Mettre à jour la liste des modules
3. Installer dans l'ordre :
   - construction_lots
   - construction_base
   - construction_sale

## Configuration

1. **Groupes utilisateurs** : Assigner les utilisateurs aux groupes appropriés via Paramètres > Utilisateurs
2. **Séquences** : Les références de chantiers sont générées automatiquement (CH/ANNÉE/NUMÉRO)
3. **Workflow** : Les chapitres et étapes sont pré-configurés et actifs

## Utilisation

### Créer un nouveau chantier

1. Menu Construction > Chantiers > Créer
2. Remplir les informations obligatoires (nom, client)
3. Le chantier démarre automatiquement à l'étape "Réception"

### Importer depuis un email

1. Menu Construction > Importer depuis Email
2. Coller l'objet et le corps de l'email
3. Sélectionner le client si connu
4. Créer le chantier

### Progression dans le workflow

1. Utiliser les boutons d'action selon l'étape actuelle
2. Respecter les conditions affichées dans le champ "Info de validation"
3. Les administrateurs peuvent forcer le changement via le champ stage_id

### Facturation par paliers

1. Depuis un devis confirmé lié à un chantier
2. Utiliser l'action "Créer facture palier"
3. La facture est créée automatiquement selon la progression

## Support

Pour toute question ou assistance, contacter l'équipe IT de BLG Groupe. 