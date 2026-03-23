# -*- coding: utf-8 -*-
"""
Contract Constants
Central location for all module constants and enumerations
"""

# Contract workflow states
CONTRACT_STATES = [
    ('draft', 'Brouillon'),
    ('generated', 'Validation Interne'),
    ('sent', 'Envoyé'),
    ('in_progress', 'En Signature'),
    ('signed', 'Signé'),
    ('cancelled', 'Annulé'),
    ('archived', 'Archivé'),
]

# Authentication methods for signature
AUTHENTICATION_METHODS = [
    ('email', 'Email Only'),
    ('email_sms', 'Email + SMS 2FA'),
    ('email_sms_id', 'Email + SMS + ID Verification'),
]

# Deliverable types
DELIVERABLE_TYPES = [
    ('planning_general', 'General Planning'),
    ('planning_subcontractor', 'Subcontractor Planning'),
    ('purchase_order', 'Purchase Order'),
    ('technical_doc', 'Technical Documentation'),
    ('insurance', 'Insurance Certificate'),
    ('urssaf', 'URSSAF Certificate'),
    ('kbis', 'KBIS Extract'),
    ('other', 'Other Document'),
]

# Configuration parameters
TOKEN_EXPIRY_DAYS = 7                    # Portal access token validity in days
DEFAULT_RETENTION_RATE = 5.0             # Default retention rate percentage (garantie)
MIN_PAGE_READ_TIME = 10                  # Minimum seconds per page before validation
MAX_SIGNATURE_SIZE_MB = 5                # Maximum signature image size

# Legal articles structure (French construction law)
LEGAL_ARTICLES = {
    'article_1': {
        'title': 'Object of Contract',
        'order': 1,
        'mandatory': True,
    },
    'article_2': {
        'title': 'Duration and Deadlines',
        'order': 2,
        'mandatory': True,
    },
    'article_3': {
        'title': 'Price and Payment Terms',
        'order': 3,
        'mandatory': True,
    },
    'article_4': {
        'title': 'Main Contractor Obligations',
        'order': 4,
        'mandatory': True,
    },
    'article_5': {
        'title': 'Subcontractor Obligations',
        'order': 5,
        'mandatory': True,
    },
    'article_6': {
        'title': 'Insurance and Guarantees',
        'order': 6,
        'mandatory': True,
    },
    'article_7': {
        'title': 'Termination Conditions',
        'order': 7,
        'mandatory': False,
    },
    'article_8': {
        'title': 'Dispute Resolution',
        'order': 8,
        'mandatory': False,
    },
    'article_9': {
        'title': 'Late Penalties',
        'order': 9,
        'mandatory': False,
    },
    'article_10': {
        'title': 'Prevention Plan (PPSPS)',
        'order': 10,
        'mandatory': False,
    },
}

# PDF generation settings
PDF_MARGINS = {
    'top': 20,
    'bottom': 20,
    'left': 15,
    'right': 15,
}

# Notification settings
EMAIL_RETRY_ATTEMPTS = 3

# Injectable variables: mapping of Jinja2 path → (label, odoo_field_or_method)
# Used by the Owl contract editor sidebar to refresh live preview after field saves.
# Key: dotted path as used in template (e.g. "contract.total_amount_ht")
# Value: human-readable label shown in the variable picker
INJECTABLE_VARIABLES = {
    # ── Contract header ──
    'contract.name':               "Référence contrat",
    'contract.start_date':         "Date de début",
    'contract.end_date':           "Date de fin",
    # ── Financial ──
    'contract.total_amount_ht':    "Montant HT",
    'contract.total_amount_tva':   "TVA",
    'contract.total_amount_ttc':   "Montant TTC",
    'contract.retention_rate':     "Taux de retenue (%)",
    'contract.retention_amount':   "Montant de la retenue",
    # ── Parties ──
    'contract.master_name':        "Nom maître d'œuvre",
    'contract.master_address':     "Adresse maître d'œuvre",
    'contract.signatory_contractor':    "Signataire BLG",
    'contract.signatory_subcontractor': "Signataire sous-traitant",
    # ── Penalties ──
    'contract.penalty_retard_jour':     "Pénalité retard/jour (€)",
    'contract.penalty_docs_delay':      "Pénalité documents (€)",
    'contract.penalty_safety':          "Pénalité sécurité (€)",
    'contract.penalty_cleaning':        "Pénalité nettoyage (€)",
    # ── Chantier ──
    'chantier.name':               "Nom du chantier",
    'chantier.reference':          "Référence chantier",
    'chantier.address':            "Adresse du chantier",
    'chantier.city':               "Ville",
    # ── Subcontractor ──
    'subcontractor.name':          "Raison sociale ST",
    'subcontractor.siret':         "SIRET",
    'subcontractor.email':         "Email ST",
    # ── Computed blocks ──
    'billing_schedule':            "Tableau échéancier de facturation",
}
SMS_RETRY_ATTEMPTS = 2
NOTIFICATION_DELAY_HOURS = 24           # Hours before sending reminder
