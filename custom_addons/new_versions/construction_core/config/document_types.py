# config/document_types.py
"""Configuration centralisée des types de documents"""

from datetime import timedelta

DOCUMENT_TYPES = {
    'identity_card': {
        'label': "Carte d'identité",
        'label_en': "Identity Card",
        'has_expiry': True,
        'notification_days': 30,
        'required_roles': ['subcontractor'],
        'mime_types': ['application/pdf', 'image/jpeg', 'image/png'],
        'max_size_mb': 5,
        'description': "Document d'identité officiel",
        'is_generated': False,
    },
    'urssaf': {
        'label': "URSSAF",
        'label_en': "URSSAF Certificate",
        'has_expiry': True,
        'notification_days': 45,
        'required_roles': ['subcontractor'],
        'mime_types': ['application/pdf'],
        'max_size_mb': 10,
        'description': "Attestation de régularité URSSAF",
        'is_generated': False,
    },
    'kbis': {
        'label': "KBIS",
        'label_en': "KBIS Extract",
        'has_expiry': True,
        'notification_days': 80,
        'required_roles': ['subcontractor'],
        'mime_types': ['application/pdf'],
        'max_size_mb': 5,
        'description': "Extrait KBIS de moins de 3 mois",
        'is_generated': False,

    },
    'insurance': {
        'label': "Assurance",
        'label_en': "Insurance Certificate",
        'has_expiry': True,
        'notification_days': 30,
        'required_roles': ['subcontractor'],
        'mime_types': ['application/pdf'],
        'max_size_mb': 10,
        'description': "Attestation d'assurance responsabilité civile",
        'is_generated': False,

    },
    'rib': {
        'label': "RIB",
        'label_en': "Bank Details",
        'has_expiry': False,
        'notification_days': None,
        'required_roles': ['subcontractor', 'supplier'],
        'mime_types': ['application/pdf', 'image/jpeg', 'image/png'],
        'max_size_mb': 2,
        'description': "Relevé d'identité bancaire",
        'is_generated': False,

    },
    'subcontracting_agreement': {
        'label': 'Contract de sous-traitance',
        'label_en': 'Subcontracting Agreement',
        'has_expiry': False,
        'notification_days': None,
        'required_roles': ['subcontractor'],
        'mime_types': ['application/pdf'],
        'max_size_mb': 10,
        'description': "Contrat de sous-traitance",
        'is_generated': True,
    },
    'cctp': {
        'label': 'cahier des clauses techniques particulières',
        'label_en': 'CCTP',
        'has_expiry': False,
        'notification_days': None,
        'required_roles': ['subcontractor'],
        'mime_types': ['application/pdf'],
        'max_size_mb': 10,
        'description': "Cahier des clauses techniques particulières",
        'is_generated': False,
    },
    'general_planning': {
        'label': 'Planning général',
        'label_en': 'General planning',
        'has_expiry': False,
        'notification_days': None,
        'required_roles': ['subcontractor'],
        'mime_types': ['application/pdf'],
        'max_size_mb': 10,
        'description': "Planning général",
        'is_generated': True,
    },
    'subcontractor_planning': {
        'label': 'Planning de la sous-traitance',
        'label_en': 'Subcontractor planning',
        'has_expiry': False,
        'notification_days': None,
        'required_roles': ['subcontractor'],
        'mime_types': ['application/pdf'],
        'max_size_mb': 10,
        'description': "Planning de la sous-traitance",
        'is_generated': True,
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

"""Constantes métier partagées"""

GENERIC_STATES = [
    ('draft', 'Brouillon'),
    ('progress', 'En cours'),
    ('done', 'Terminé'),
    ('cancelled', 'Annulé')
]

PRIORITY_LEVELS = [
    ('low', 'Faible'),
    ('normal', 'Normale'),
    ('high', 'Élevée'),
    ('urgent', 'Urgente')
]

DEFAULT_DELAYS = {
    'document_expiry_warning': 30,
    'quote_validity': 30,
    'task_default_duration': 1,
}
