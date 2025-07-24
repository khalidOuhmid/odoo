# Génération de Contrats de Sous-traitance

## Fonctionnalité

Ce module permet de générer automatiquement des contrats de sous-traitance pour les lots de construction, basés sur le template visible dans les images fournies.

## Utilisation

1. **Accéder au wizard** : Depuis un lot de construction, utiliser l'action "Gérer les documents du lot"

2. **Générer le contrat** : 
   - Cliquer sur "📋 Générer contrat de sous-traitance"
   - Le système génère automatiquement un PDF basé sur les données du lot

3. **Prévisualiser** :
   - Cliquer sur "👁️ Prévisualiser contrat" pour voir le PDF avant génération

## Contenu du contrat

Le contrat généré inclut :

### 1. Désignation des parties contractantes
- Informations BLG Groupe (contractant général)
- Informations du sous-traitant (nom, adresse, TVA/référence)

### 2. Désignation des prestations
- Nom de l'opération (lot)
- Maître d'œuvre (BLG Groupe)
- Nature des travaux (description du lot)
- Lieu d'exécution (adresse du chantier)

### 3. Prix
- Prix total du lot
- Clause de prix ferme et non révisable
- Mention d'autoliquidation

### 4. Échéancier de paiement
- 30% à 30% d'avancement
- 60% à 60% d'avancement  
- 100% à 100% d'avancement
- Montants calculés automatiquement

### 5. Délais
- Référence au planning prévisionnel

### 6. Documents contractuels
- Liste des documents et annexes

### 7. Documents à transmettre
- Liste des documents requis du sous-traitant

### 8. Validité
- Conditions d'acceptation du contrat

### 9. Signatures
- Emplacements pour signatures BLG Groupe et sous-traitant
- Date de génération automatique

## Données requises

Pour générer le contrat, le lot doit avoir :
- Un nom
- Un prix
- Une description des travaux
- Un sous-traitant assigné
- Un chantier avec une adresse

## Personnalisation

Pour personnaliser le template :
1. Modifier `reports/subcontractor_contract_template.xml`
2. Ajouter les logos dans `static/img/` (voir README dans ce dossier)
3. Redémarrer Odoo après modifications

## Fichiers concernés

- `wizard/lot_document_wizard.py` : Logique de génération
- `reports/subcontractor_contract_template.xml` : Template QWeb
- `reports/report_actions.xml` : Configuration du rapport
- `views/lot_document_wizard_view.xml` : Interface utilisateur
