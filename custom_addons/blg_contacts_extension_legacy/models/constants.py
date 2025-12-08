DOCUMENT_TYPES = {
    'identity_card': {
        'name': "Carte d'identité",
        'field': 'document_identity_card',
        'icon': 'fa-id-card-o'
    },
    'urssaf': {
        'name': "URSSAF",
        'field': 'document_URSSAF',
        'icon': 'fa-file-text-o'
    },
    'kbis': {
        'name': "KBIS",
        'field': 'document_KBIS',
        'icon': 'fa-building-o'
    },
    'insurance': {
        'name': "Assurance",
        'field': 'document_insurance',
        'icon': 'fa-shield'
    }
}

DOCUMENT_STATUSES = [
    ('valid', 'Valide'),
    ('expiring', 'Expire bientôt'),
    ('expired', 'Expiré'),
    ('to_check', 'À vérifier'),
    ('missing', 'Manquant'),
    ('rejected', 'Rejeté'),
]

MANUAL_STATUSES = [
    ('to_check', 'À vérifier'),
    ('valid', 'Valide'),
    ('rejected', 'Rejeté'),
]