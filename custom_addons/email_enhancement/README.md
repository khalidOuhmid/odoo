# Email Enhancement Module

Module d'amélioration de l'interface du chatter Odoo 18 pour une meilleure expérience utilisateur des emails.

## Fonctionnalités

### 1. Ouverture directe du Full Composer
- **Problème résolu** : Cliquer sur "Envoyer un message" ouvrait une petite zone de texte avec un lien "Full composer"
- **Solution** : Le bouton "Envoyer un message" ouvre maintenant directement le full composer
- **Implémentation** : Patch du composant `Chatter` pour intercepter l'action `toggleComposer`

### 2. Bouton Reply pour les messages
- **Problème résolu** : Pas de moyen de créer une vraie réponse liée à un message spécifique
- **Solution** : Ajout d'un bouton "Reply" dans les actions de message
- **Implémentation** : Extension du registre `messageActionsRegistry` avec une nouvelle action "email-reply"

## Structure technique

### Fichiers JavaScript
- `static/src/js/chatter_patch.js` : Patch du composant Chatter
- `static/src/js/message_actions_patch.js` : Extension des actions de message

### Modèles Python
- `models/mail_message.py` : Extension du modèle mail.message
- `models/mail_compose_message_reply.py` : Wizard spécialisé pour les réponses

### Tests
- `tests/test_email_enhancement.py` : Tests unitaires complets

### Styles
- `static/src/scss/chatter_enhanced.scss` : Styles pour les améliorations visuelles

## Installation

1. Copier le module dans `custom_addons/`
2. Redémarrer Odoo
3. Installer le module depuis l'interface Apps

## Architecture respectée

### Bonnes pratiques Odoo 18
- ✅ Utilisation du système de patch OWL
- ✅ Extension des registres plutôt que remplacement
- ✅ Tests unitaires avec @tagged
- ✅ Services d'action appropriés
- ✅ Héritage des modèles correct

### Conformité technique
- ✅ Pas de modification des fichiers core
- ✅ Utilisation des hooks et services standards
- ✅ Respect de l'architecture des composants
- ✅ Code documenté avec docstrings

## Utilisation

### Nouvelle expérience "Send message"
1. Ouvrir un enregistrement avec chatter
2. Cliquer sur "Envoyer un message"
3. Le full composer s'ouvre directement

### Nouvelle fonctionnalité Reply
1. Survoler un message dans le chatter
2. Cliquer sur le bouton "Reply" (icône fa-reply)
3. Le full composer s'ouvre avec le contexte de réponse approprié

## Tests

Exécuter les tests :
```bash
odoo-bin -d db_test -i email_enhancement --test-tags=email_enhancement
```

## Compatibilité

- Odoo 18.0+
- Dépend de : base, mail, web
- Compatible avec les modules mail standards

## Développement

Le module respecte l'architecture d'Odoo 18 et peut être étendu facilement :
- Actions de message supplémentaires via le registre
- Nouvelles améliorations du chatter via patches
- Extensions du modèle mail.message
│   └── mail_message.py               # Extension du modèle mail.message
├── static/src/
│   ├── js/
│   │   ├── chatter_enhanced.js       # Interception du bouton Send message
│   │   └── message_actions_enhanced.js # Interception du bouton Reply
│   └── scss/
│       └── chatter_enhanced.scss     # Styles CSS
├── security/
│   └── ir.model.access.csv           # Permissions
└── tests/
    └── test_mail_message.py          # Tests unitaires
```

## Compatibilité

- **Odoo** : 18.0+
- **Dépendances** : base, mail, web

## Licence

LGPL-3
