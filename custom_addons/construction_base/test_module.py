#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script pour exécuter la génération des données de test pour construction_base
À lancer depuis le shell Odoo:

1. Démarrez le shell Odoo:
   ./odoo-bin shell -d your_database

2. Exécutez ce script:
   exec(open('/path/to/test_module.py').read())
"""

import logging
import os
from importlib import reload

_logger = logging.getLogger(__name__)

def run_test_data_creation():
    """Exécute la création des données de test"""
    try:
        # Importer le module de création de données
        import create_test_data
        # Recharger pour être sûr d'avoir la dernière version
        reload(create_test_data)
        
        # Exécuter la fonction principale
        result = create_test_data.main(env)
        
        _logger.info("✅ Génération des données de test terminée avec succès!")
        
        # Afficher un résumé
        print("\n" + "="*50)
        print("RÉSUMÉ DES DONNÉES DE TEST CRÉÉES")
        print("="*50)
        print(f"Clients: {len(result['clients'])}")
        print(f"Sous-traitants: {len(result['subcontractors'])}")
        print(f"Chantiers: {len(result['chantiers'])}")
        print("\nDétail des chantiers:")
        for i, chantier in enumerate(result['chantiers'], 1):
            print(f"{i}. {chantier.name} - {chantier.stage_id.name} - Client: {chantier.client.name}")
            print(f"   Lots: {', '.join(chantier.lots_ids.mapped('name'))}")
            print(f"   Progression: {chantier.progress}%")
            print(f"   Montant: {chantier.total_cost:,.2f} €")
            print(f"   Facturation: {chantier.invoice_type_id.name}")
            print()
        print("="*50)
        print("Pour voir les données dans l'interface, actualisez votre navigateur.")
        print("="*50)
        
        return result
        
    except Exception as e:
        _logger.error(f"❌ Erreur lors de la génération des données de test: {e}")
        import traceback
        traceback.print_exc()
        return False

# Exécuter la fonction
if 'env' in globals():
    run_test_data_creation()
else:
    _logger.error("Ce script doit être exécuté depuis le shell Odoo (variable 'env' non trouvée)")
