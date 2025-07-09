# -*- coding: utf-8 -*-
"""
Document Configuration

This module defines the document types and their configurations for
subcontractor document management. It centralizes all document-related
metadata and field mapping.
"""

# Document type configurations
# Each document type defines its field names and display properties
DOCUMENT_TYPES = {
    'identity_card': {
        'key': 'identity_card',
        'display_name': "Identity Card",
        'display_name_fr': "Carte d'identité",
        'filename_prefix': "Carte d'identité",
        'content_field': 'document_identity_card',
        'filename_field': 'document_identity_card_filename',
        'expiry_field': 'document_identity_card_expiry',
        'status_field': 'document_identity_card_status',
        'manual_status_field': 'document_identity_card_manual_status',
        'last_notif_field': 'last_notif_expiry_identity_card',
        'has_expiry': True,
        'required': True,
        'sort_order': 1,
    },
    'urssaf': {
        'key': 'urssaf',
        'display_name': "URSSAF Certificate",
        'display_name_fr': "URSSAF",
        'filename_prefix': "Attestation URSSAF",
        'content_field': 'document_URSSAF',
        'filename_field': 'document_URSSAF_filename',
        'expiry_field': 'document_URSSAF_expiry',
        'status_field': 'document_URSSAF_status',
        'manual_status_field': 'document_URSSAF_manual_status',
        'last_notif_field': 'last_notif_expiry_urssaf',
        'has_expiry': True,
        'required': True,
        'sort_order': 2,
    },
    'kbis': {
        'key': 'kbis',
        'display_name': "KBIS Extract",
        'display_name_fr': "KBIS",
        'filename_prefix': "Extrait KBIS",
        'content_field': 'document_KBIS',
        'filename_field': 'document_KBIS_filename',
        'expiry_field': 'document_KBIS_expiry',
        'status_field': 'document_KBIS_status',
        'manual_status_field': 'document_KBIS_manual_status',
        'last_notif_field': 'last_notif_expiry_kbis',
        'has_expiry': True,
        'required': True,
        'sort_order': 3,
    },
    'insurance': {
        'key': 'insurance',
        'display_name': "Insurance Certificate",
        'display_name_fr': "Assurance",
        'filename_prefix': "Attestation Assurance",
        'content_field': 'document_insurance',
        'filename_field': 'document_insurance_filename',
        'expiry_field': 'document_insurance_expiry',
        'status_field': 'document_insurance_status',
        'manual_status_field': 'document_insurance_manual_status',
        'last_notif_field': 'last_notif_expiry_insurance',
        'has_expiry': True,
        'required': True,
        'sort_order': 4,
    },
    'rib': {
        'key': 'rib',
        'display_name': "Bank Details (RIB)",
        'display_name_fr': "RIB",
        'filename_prefix': "RIB",
        'content_field': 'document_RIB',
        'filename_field': 'document_RIB_filename',
        'status_field': 'document_RIB_status',
        'manual_status_field': 'document_RIB_manual_status',
        'last_notif_field': 'last_notif_rib',
        'has_expiry': False,
        'required': True,
        'sort_order': 5,
    },
}

# Document status configurations
DOCUMENT_STATUSES = {
    'valid': {
        'label': 'Valid',
        'label_fr': 'Valide',
        'color': 'success',
        'icon': 'fa-check-circle',
        'priority': 1,
    },
    'expiring': {
        'label': 'Expiring Soon',
        'label_fr': 'Expire bientôt',
        'color': 'warning',
        'icon': 'fa-clock-o',
        'priority': 2,
    },
    'expired': {
        'label': 'Expired',
        'label_fr': 'Expiré',
        'color': 'danger',
        'icon': 'fa-exclamation-circle',
        'priority': 3,
    },
    'to_check': {
        'label': 'To Check',
        'label_fr': 'À vérifier',
        'color': 'info',
        'icon': 'fa-question-circle',
        'priority': 4,
    },
    'missing': {
        'label': 'Missing',
        'label_fr': 'Manquant',
        'color': 'secondary',
        'icon': 'fa-file-o',
        'priority': 5,
    },
    'rejected': {
        'label': 'Rejected',
        'label_fr': 'Rejeté',
        'color': 'danger',
        'icon': 'fa-times-circle',
        'priority': 6,
    },
}

# Email template configurations
EMAIL_TEMPLATES = {
    'document_expired': {
        'name': 'Document Expired Notification',
        'subject': 'Urgent: Document Expired - {{ partner_name }}',
        'template_ref': 'blg_contacts_extension.email_template_document_expired',
    },
    'document_expiring': {
        'name': 'Document Expiring Soon Notification',
        'subject': 'Reminder: Document Expiring Soon - {{ partner_name }}',
        'template_ref': 'blg_contacts_extension.email_template_document_expiring',
    },
    'document_rejected': {
        'name': 'Document Rejected Notification',
        'subject': 'Document Rejected - Action Required - {{ partner_name }}',
        'template_ref': 'blg_contacts_extension.email_template_document_rejected',
    },
    'missing_documents_request': {
        'name': 'Missing Documents Request',
        'subject': 'Document Upload Required - {{ partner_name }}',
        'template_ref': 'blg_contacts_extension.email_template_missing_documents_request',
    },
}

# Business rules and constants
BUSINESS_RULES = {
    'expiry_warning_days': 30,  # Days before expiry to show warning
    'expired_reminder_frequency_days': 7,  # Frequency for expired document reminders
    'expiring_notification_frequency_days': 30,  # Frequency for expiring document notifications
    'token_validity_days': 7,  # Upload token validity period
    'allowed_file_extensions': ['.pdf'],  # Allowed document file extensions
    'max_file_size_mb': 10,  # Maximum file size in MB
    'notification_batch_size': 100,  # Batch size for notification processing
}

# Security groups
SECURITY_GROUPS = {
    'document_manager': 'blg_contacts_extension.group_conductrice_travaux',
    'director': 'blg_contacts_extension.group_directeur_general',
    'system_admin': 'base.group_system',
}


def get_document_config(doc_type_key):
    """
    Get document configuration by key.
    
    Args:
        doc_type_key (str): Document type key
        
    Returns:
        dict: Document configuration or None if not found
    """
    return DOCUMENT_TYPES.get(doc_type_key)


def get_document_status_config(status_key):
    """
    Get document status configuration by key.
    
    Args:
        status_key (str): Status key
        
    Returns:
        dict: Status configuration or None if not found
    """
    return DOCUMENT_STATUSES.get(status_key)


def get_required_documents():
    """
    Get list of required document types.
    
    Returns:
        list: List of required document type keys
    """
    return [key for key, config in DOCUMENT_TYPES.items() if config.get('required', False)]


def get_documents_with_expiry():
    """
    Get list of document types that have expiry dates.
    
    Returns:
        list: List of document type keys with expiry dates
    """
    return [key for key, config in DOCUMENT_TYPES.items() if config.get('has_expiry', False)]


def get_sorted_documents():
    """
    Get document types sorted by sort_order.
    
    Returns:
        list: List of (key, config) tuples sorted by sort_order
    """
    return sorted(DOCUMENT_TYPES.items(), key=lambda x: x[1].get('sort_order', 999))
