# Chatter Enhanced - Extension du module Mail

## Description

Ce module étend les fonctionnalités du chatter Odoo pour offrir une interface similaire à Gmail/Outlook avec des fonctionnalités avancées de gestion des emails.

## Fonctionnalités

### 🎯 Fonctionnalités principales

- **Bouton Reply sur chaque message** : Possibilité de répondre directement à un message spécifique
- **Interface Gmail-like** : Design moderne et intuitif similaire aux clients email populaires
- **Gestion des threads** : Suivi automatique des conversations et réponses
- **Notifications améliorées** : Feedback visuel lors de l'envoi et réception des messages
- **Responsive design** : Interface adaptée aux différentes tailles d'écran

### 🔧 Fonctionnalités techniques

- **Patch du module Mail** : Extension propre du module mail d'Odoo 18
- **Système de patch JavaScript** : Utilisation du système de patch d'Odoo pour les extensions
- **Styles SCSS personnalisés** : Interface utilisateur améliorée
- **Gestion des réponses** : Compteurs automatiques et suivi des conversations

## Installation

1. Placez le module dans le dossier `custom_addons`
2. Mettez à jour la liste des modules dans Odoo
3. Installez le module "Chatter Enhanced"
4. Redémarrez le serveur Odoo si nécessaire

## Utilisation

### Répondre à un message

1. Ouvrez un enregistrement avec un chatter (contact, opportunité, etc.)
2. Dans le chatter, vous verrez un bouton "Répondre" sur chaque message
3. Cliquez sur "Répondre" pour ouvrir le compositeur de mail
4. Le sujet sera automatiquement préfixé avec "Re:"
5. Le message original sera inclus en citation

### Interface améliorée

- Les boutons d'envoi ont un design moderne avec des gradients
- Les messages ont des effets de survol et des animations
- Les notifications sont stylisées et informatives
- L'interface est responsive et s'adapte aux mobiles

## Structure du module

```
email_enhancement/
├── __init__.py
├── __manifest__.py
├── README.md
├── models/
│   ├── __init__.py
│   └── mail_message.py
├── views/
│   └── mail_message_views.xml
├── static/
│   └── src/
│       ├── js/
│       │   └── chatter_enhanced.js
│       └── scss/
│           └── chatter_enhanced.scss
└── i18n/
    └── fr.po
```

## Développement

### Ajouter de nouvelles fonctionnalités

1. **JavaScript** : Modifiez `static/src/js/chatter_enhanced.js`
2. **Styles** : Modifiez `static/src/scss/chatter_enhanced.scss`
3. **Modèles** : Modifiez `models/mail_message.py`
4. **Vues** : Modifiez `views/mail_message_views.xml`

### Tests

Pour tester le module :

1. Installez le module
2. Ouvrez un enregistrement avec chatter (ex: un contact)
3. Vérifiez que les boutons "Répondre" apparaissent
4. Testez la fonctionnalité de réponse
5. Vérifiez les styles et animations

## Compatibilité

- **Odoo** : 18.0+
- **Modules requis** : mail, web
- **Navigateurs** : Chrome, Firefox, Safari, Edge (versions récentes)

## Support

Pour toute question ou problème :

1. Vérifiez les logs du serveur Odoo
2. Consultez la console du navigateur pour les erreurs JavaScript
3. Vérifiez que le module mail est bien installé et fonctionnel

## Licence

Ce module est sous licence LGPL-3.

## Auteur

Ton nom - [Votre email]

## Version

18.0.1.0.0
