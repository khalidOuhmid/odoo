"""
blg_contacts_extension.models.document_config
============================================

This module provides centralized configuration for document management in BLG Groupe,
including document types, field mappings, and helper functions.

Features:
---------
- Defines document types and their field mappings for partner document management.
- Provides helper functions to retrieve field names, dependencies, and UI options.

Configuration:
--------------
DOCUMENT_CONFIGS: dict
    Maps document type keys to their configuration (name, fields, expiry, etc.).

Helper Functions:
-----------------
- get_all_field_names: Returns all field names used in configurations.
- get_document_types_requiring_expiry: Lists document types needing expiry dates.
- get_document_dependencies: Maps computed fields to their dependencies.
- get_document_view_options: Maps status values to UI display classes.
- get_document_field_groups: Groups fields by document type for UI.
- has_expiry_date: Checks if a document type requires an expiry date.

Author: BLG IT Team
"""

# Standard document configurations used across the application
DOCUMENT_CONFIGS = {
    'identity_card': {
        'name': "Carte d'identité",
        'content_field': 'document_identity_card',
        'filename_field': 'document_identity_card_filename',
        'expiry_field': 'document_identity_card_expiry',
        'status_field': 'document_identity_card_status',
        'manual_status_field': 'document_identity_card_manual_status',
        'last_notif_field': 'last_notif_expiry_identity_card',
        'filename_prefix': 'CARTE_IDENTITE',
    },
    'urssaf': {
        'name': "URSSAF",
        'content_field': 'document_URSSAF',
        'filename_field': 'document_URSSAF_filename',
        'expiry_field': 'document_URSSAF_expiry',
        'status_field': 'document_URSSAF_status',
        'manual_status_field': 'document_URSSAF_manual_status',
        'last_notif_field': 'last_notif_expiry_urssaf',
        'filename_prefix': 'URSSAF',
        'auto_expiry_months': 3,
    },
    'kbis': {
        'name': "KBIS",
        'content_field': 'document_KBIS',
        'filename_field': 'document_KBIS_filename',
        'expiry_field': 'document_KBIS_expiry',
        'status_field': 'document_KBIS_status',
        'manual_status_field': 'document_KBIS_manual_status',
        'last_notif_field': 'last_notif_expiry_kbis',
        'filename_prefix': 'KBIS',
        'auto_expiry_months': 3,
    },
    'insurance': {
        'name': "Assurance",
        'content_field': 'document_insurance',
        'filename_field': 'document_insurance_filename',
        'expiry_field': 'document_insurance_expiry',
        'status_field': 'document_insurance_status',
        'manual_status_field': 'document_insurance_manual_status',
        'last_notif_field': 'last_notif_expiry_insurance',
        'filename_prefix': 'ASSURANCE',
    },
    'rib': {
        'name': "RIB",
        'content_field': 'document_RIB',
        'filename_field': 'document_RIB_filename',
        'status_field': 'document_RIB_status',
        'manual_status_field': 'document_RIB_manual_status',
        'last_notif_field': 'last_notif_rib',
        'filename_prefix': 'RIB',
    },
}


def get_all_field_names(config_type=None):
    """
    Return all field names used in document configurations.
    
    Args:
        config_type (str, optional): Specific field type to retrieve (e.g., 'content_field')
        
    Returns:
        list: List of field names
    """
    if config_type:
        return [config[config_type] for config in DOCUMENT_CONFIGS.values() if config_type in config]

    # Get all unique field names
    fields = set()
    for config in DOCUMENT_CONFIGS.values():
        for field_key, field_name in config.items():
            if field_key.endswith('_field'):
                fields.add(field_name)
    return list(fields)


def get_document_types_requiring_expiry():
    """Returns a list of document types that require expiry dates"""
    return [key for key, config in DOCUMENT_CONFIGS.items() if 'expiry_field' in config]


def get_document_dependencies():
    """
    Returns a mapping of which fields depend on others for computed fields
    
    Returns:
        dict: Mapping of computed fields to their dependencies
    """
    dependencies = {}

    # Status fields depend on content, expiry, and manual status
    status_fields = get_all_field_names('status_field')
    dependencies.update({
        status_field: [
                          config['content_field'] for config in DOCUMENT_CONFIGS.values()
                          if 'status_field' in config and config['status_field'] == status_field
                      ] + [
                          config['manual_status_field'] for config in DOCUMENT_CONFIGS.values()
                          if 'status_field' in config and config['status_field'] == status_field
                      ] + [
                          config['expiry_field'] for config in DOCUMENT_CONFIGS.values()
                          if 'status_field' in config and config[
                'status_field'] == status_field and 'expiry_field' in config
                      ]
        for status_field in status_fields
    })

    return dependencies


def get_document_view_options():
    """
    Returns mapping options for document status badges in views
    
    Returns:
        dict: Mapping of status values to display classes
    """
    return {
        'valid': 'success',
        'expiring': 'warning',
        'expired': 'danger',
        'to_check': 'info',
        'rejected': 'danger',
        'missing': 'secondary'
    }


def get_document_field_groups():
    """
    Group document fields by document type for UI organization
    
    Returns:
        dict: Field groups organized by document type
    """
    result = {}
    for doc_type, config in DOCUMENT_CONFIGS.items():
        result[doc_type] = {
            'name': config['name'],
            'fields': {
                'content': config['content_field'],
                'filename': config['filename_field'],
                'status': config['status_field'],
                'manual_status': config['manual_status_field'],
            }
        }
        if 'expiry_field' in config:
            result[doc_type]['fields']['expiry'] = config['expiry_field']

    return result


def has_expiry_date(doc_type):
    """
    Check if a document type requires an expiration date
    
    Args:
        doc_type (str): Document type key
        
    Returns:
        bool: True if this document type requires an expiration date
    """
    return 'expiry_field' in DOCUMENT_CONFIGS.get(doc_type, {})


def get_status_fields():
    """Retourne tous les champs de statut définis"""
    return [config['status_field'] for config in DOCUMENT_CONFIGS.values() if 'status_field' in config]
