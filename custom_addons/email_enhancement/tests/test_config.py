# -*- coding: utf-8 -*-

"""
Configuration pour les tests du module email_enhancement
"""

import os
import sys

# Ajouter le chemin du module aux tests
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configuration des tests
TEST_CONFIG = {
    'module_name': 'email_enhancement',
    'test_files': [
        'test_mail_message.py',
    ],
    'coverage_target': 90,  # Pourcentage de couverture de code cible
}

# Configuration pour les tests d'intégration
INTEGRATION_TEST_CONFIG = {
    'test_database': 'test_email_enhancement',
    'test_user': 'test_user@example.com',
    'test_partner': 'test_partner@example.com',
}
