# Création Automatique de Chantiers depuis les Emails

## Vue d'ensemble

Ce module permet de créer automatiquement des chantiers dans le système BLG Groupe lorsqu'un email est reçu sur une adresse dédiée aux appels d'offre.

## Fonctionnement

### 1. Configuration

L'adresse email dédiée est configurée dans les paramètres système :
- **Clé** : `construction_base.construction_project_email`
- **Valeur par défaut** : `appel-doffre@blggroupe.com`

### 2. Déclenchement

La création automatique se déclenche quand :
- Un email est reçu sur l'adresse dédiée
- OU le sujet de l'email contient des mots-clés spécifiques :
  - "appel d'offre"
  - "appel doffre" 
  - "projet construction"
  - "chantier"

### 3. Extraction des données

Le système extrait automatiquement :
- **Nom du chantier** : Sujet de l'email
- **Client** : Expéditeur de l'email (créé automatiquement si inexistant)
- **Description** : Contenu de l'email
- **Adresse** : Détectée dans le contenu (code postal, ville, adresse complète)
- **Téléphone** : Numéros de téléphone français détectés

### 4. Création du chantier

Le chantier est créé avec :
- **Stage** : "Appel d'offre" (AO)
- **État** : Actif
- **Client** : Expéditeur de l'email
- **Données extraites** : Nom, description, adresse, téléphone

## Configuration

### Paramètres système

1. **Adresse email dédiée** :
   ```bash
   construction_base.construction_project_email = appel-doffre@blggroupe.com
   ```

2. **Activation/désactivation** :
   ```bash
   construction_base.auto_create_from_email = True/False
   ```

3. **Envoi automatique d'emails de confirmation** :
   ```bash
   construction_base.auto_send_confirmation_email = True/False
   ```

### Modification des paramètres

Via l'interface Odoo :
1. Aller dans **Paramètres > Technique > Paramètres > Paramètres système**
2. Rechercher les clés `construction_base.*`
3. Modifier les valeurs selon les besoins

## Notifications

### Activités internes

Une activité est créée automatiquement pour :
- Notifier l'équipe de la création du chantier
- Permettre le suivi et la validation des informations

### Emails de confirmation

Si activé, un email de confirmation est envoyé au client avec :
- Récapitulatif des informations du chantier
- Confirmation de réception de la demande
- Engagement de recontact

## Logs et surveillance

### Fichiers de logs

Les actions sont enregistrées dans les logs Odoo :
- Création réussie : `INFO`
- Erreurs d'extraction : `WARNING`
- Erreurs de création : `ERROR`

### Surveillance recommandée

1. **Vérifier les logs** régulièrement
2. **Contrôler les chantiers créés** automatiquement
3. **Valider les informations** extraites
4. **Compléter les données** manquantes

## Exemple d'utilisation

### Email reçu

```
De : client@example.com
À : appel-doffre@blggroupe.com
Sujet : Construction maison individuelle - Lyon

Bonjour,

Je souhaite construire une maison individuelle de 120m².

Adresse du terrain :
123 Rue de la Paix
69000 Lyon

Téléphone : 01 23 45 67 89

Merci de me recontacter.

Cordialement,
Jean Dupont
```

### Chantier créé automatiquement

- **Nom** : "Construction maison individuelle - Lyon"
- **Client** : Jean Dupont (créé automatiquement)
- **Description** : Contenu complet de l'email
- **Adresse** : "123 Rue de la Paix"
- **Ville** : "Lyon"
- **Code postal** : "69000"
- **Téléphone** : "01 23 45 67 89"
- **Stage** : "Appel d'offre"

## Sécurité et contrôle

### Validation requise

Les chantiers créés automatiquement nécessitent :
1. **Validation manuelle** des informations
2. **Complétion** des données manquantes
3. **Vérification** du client et de l'adresse
4. **Analyse** de la faisabilité

### Contrôles automatiques

Le système vérifie :
- Présence d'un nom de projet
- Validité de l'adresse email
- Existence du stage "Appel d'offre"
- Droits d'accès de l'utilisateur

## Dépannage

### Problèmes courants

1. **Chantier non créé** :
   - Vérifier l'adresse email de destination
   - Contrôler les logs d'erreur
   - Valider la configuration

2. **Données manquantes** :
   - Vérifier le format de l'email
   - Contrôler l'extraction des données
   - Compléter manuellement si nécessaire

3. **Client non créé** :
   - Vérifier l'adresse email de l'expéditeur
   - Contrôler les droits de création

### Support

Pour toute question ou problème :
- Consulter les logs Odoo
- Vérifier la configuration
- Contacter l'équipe technique BLG Groupe
