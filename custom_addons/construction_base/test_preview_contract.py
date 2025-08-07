# -*- coding: utf-8 -*-
"""
Script de test pour la prévisualisation du contrat.
Teste la génération d'aperçu et de contrat définitif.
"""

import logging

_logger = logging.getLogger(__name__)


def test_contract_preview(env):
    """Test de la prévisualisation du contrat."""
    
    _logger.info("🧪 Début du test de prévisualisation du contrat")
    
    try:
        # Récupérer un lot avec sous-traitant
        lot = env['construction.lot'].search([
            ('subcontractor_id', '!=', False),
            ('price', '>', 0)
        ], limit=1)
        
        if not lot:
            _logger.warning("⚠️ Aucun lot avec sous-traitant trouvé pour le test")
            return False
            
        _logger.info(f"✅ Lot trouvé: {lot.name} - Sous-traitant: {lot.subcontractor_id.name}")
        
        # Créer le wizard
        wizard_vals = {
            'lot_id': lot.id,
            'chantier_id': lot.chantier_id.id,
            'subcontractor_id': lot.subcontractor_id.id,
        }
        
        wizard = env['lot.document.wizard'].create(wizard_vals)
        _logger.info(f"✅ Wizard créé avec ID: {wizard.id}")
        
        # Test de la prévisualisation
        _logger.info("🔄 Test de génération de l'aperçu...")
        result = wizard.action_preview_contract()
        
        if wizard.preview_contract_pdf:
            _logger.info("✅ Aperçu généré avec succès!")
            _logger.info(f"📄 Taille du PDF: {len(wizard.preview_contract_pdf)} bytes")
            _logger.info(f"📄 Nom du fichier: {wizard.preview_filename}")
        else:
            _logger.error("❌ Échec de la génération de l'aperçu")
            return False
            
        # Test de la génération du contrat définitif
        _logger.info("🔄 Test de génération du contrat définitif...")
        result = wizard.action_generate_final_contract()
        
        if wizard.document_subcontractor_contract:
            _logger.info("✅ Contrat définitif généré avec succès!")
            _logger.info(f"📄 Taille du PDF définitif: {len(wizard.document_subcontractor_contract)} bytes")
        else:
            _logger.error("❌ Échec de la génération du contrat définitif")
            return False
            
        # Vérifier que le contrat est sauvegardé sur le lot
        if lot.document_subcontractor_contract:
            _logger.info("✅ Contrat sauvegardé sur le lot avec succès!")
        else:
            _logger.error("❌ Le contrat n'a pas été sauvegardé sur le lot")
            return False
            
        _logger.info("🎉 Tous les tests de prévisualisation sont passés avec succès!")
        return True
        
    except Exception as e:
        _logger.error(f"❌ Erreur lors du test de prévisualisation: {e}")
        return False


def main():
    """Fonction principale de test."""
    _logger.info("🚀 Démarrage des tests de prévisualisation du contrat")
    
    # Simuler l'environnement Odoo
    # Note: Ce script doit être exécuté dans le contexte Odoo
    pass


if __name__ == "__main__":
    main() 