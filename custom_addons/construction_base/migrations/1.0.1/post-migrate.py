# -*- coding: utf-8 -*-
"""
Migration script pour construction_base v1.0.1
Correction de la contrainte d'unicité des codes de lots
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Migration pour corriger les contraintes d'unicité des lots"""
    
    # Supprimer l'ancienne contrainte d'unicité globale sur le code
    try:
        cr.execute("""
            ALTER TABLE lot DROP CONSTRAINT IF EXISTS lot_code_unique;
        """)
        _logger.info("Ancienne contrainte d'unicité supprimée avec succès")
    except Exception as e:
        _logger.warning(f"Erreur lors de la suppression de l'ancienne contrainte: {e}")
    
    # Ajouter la nouvelle contrainte d'unicité par chantier pour construction.lot
    try:
        cr.execute("""
            ALTER TABLE construction_lot 
            ADD CONSTRAINT construction_lot_code_chantier_uniq 
            UNIQUE (code, chantier_id);
        """)
        _logger.info("Nouvelle contrainte d'unicité par chantier ajoutée avec succès")
    except Exception as e:
        _logger.warning(f"Erreur lors de l'ajout de la nouvelle contrainte: {e}")
    
    _logger.info("Migration construction_base v1.0.1 terminée") 