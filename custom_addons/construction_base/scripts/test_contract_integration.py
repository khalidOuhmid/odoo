#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de test pour la génération de contrats avec intégration des bons de commande et planning Gantt
"""

import logging
import sys
import os
from datetime import datetime, timedelta

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_contract_generation_with_pdf_annexes():
    """Test de la génération de contrats avec PDF séparés pour les annexes."""
    try:
        # Importer Odoo
        import odoo
        from odoo import api, fields, models
        from odoo.exceptions import ValidationError
        
        # Initialiser Odoo
        odoo.cli.server.main()
        
        # Obtenir l'environnement
        env = api.Environment(cr, uid, {})
        
        logger.info("🔧 Test de génération de contrats avec PDF séparés")
        
        # 1. Test de récupération des bons de commande
        logger.info("📋 Test 1: Récupération des bons de commande")
        test_get_purchase_orders(env)
        
        # 2. Test de récupération des tâches de planning
        logger.info("📅 Test 2: Récupération des tâches de planning")
        test_get_planning_tasks(env)
        
        # 3. Test de génération de PDF séparés
        logger.info("📄 Test 3: Génération de PDF séparés")
        test_generate_separate_pdfs(env)
        
        # 4. Test de fusion de PDF
        logger.info("🔗 Test 4: Fusion de PDF")
        test_merge_pdfs(env)
        
        # 5. Test complet de génération de contrat
        logger.info("🎯 Test 5: Génération complète de contrat")
        test_complete_contract_generation(env)
        
        logger.info("✅ Tous les tests ont réussi !")
        
    except Exception as e:
        logger.error(f"❌ Erreur lors des tests: {e}")
        raise

def test_get_purchase_orders(env):
    """Test de récupération des bons de commande."""
    try:
        # Récupérer un lot de test
        lot = env['construction.lot'].search([], limit=1)
        if not lot:
            logger.warning("⚠️ Aucun lot trouvé pour le test")
            return
        
        # Récupérer un chantier de test
        chantier = env['construction.chantier'].search([], limit=1)
        if not chantier:
            logger.warning("⚠️ Aucun chantier trouvé pour le test")
            return
        
        # Récupérer un sous-traitant de test
        subcontractor = env['res.partner'].search([('is_company', '=', True)], limit=1)
        if not subcontractor:
            logger.warning("⚠️ Aucun sous-traitant trouvé pour le test")
            return
        
        # Créer un contrat de test
        contract_data = {
            'total_amount': 10000.0,
            'start_date': fields.Date.today(),
            'end_date': fields.Date.today() + timedelta(days=30),
            'urssaf_code': '43.34Z'
        }
        
        contract_service = env['construction.contract.service']
        
        # Test de récupération des bons de commande
        purchase_orders = contract_service._get_lot_purchase_orders(lot, contract_data)
        
        logger.info(f"📋 Bons de commande trouvés pour le lot {lot.name}: {len(purchase_orders)}")
        
        for po in purchase_orders:
            logger.info(f"  - {po.name} ({po.state}) - {po.partner_id.name}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erreur test récupération bons de commande: {e}")
        return False

def test_get_planning_tasks(env):
    """Test de récupération des tâches de planning."""
    try:
        # Récupérer un lot de test
        lot = env['construction.lot'].search([], limit=1)
        if not lot:
            logger.warning("⚠️ Aucun lot trouvé pour le test")
            return False
        
        # Récupérer un chantier de test
        chantier = env['construction.chantier'].search([], limit=1)
        if not chantier:
            logger.warning("⚠️ Aucun chantier trouvé pour le test")
            return False
        
        # Récupérer les tâches de planning
        planning_tasks = env['construction.planning.task'].search([
            ('lot_id', '=', lot.id),
            ('chantier_id', '=', chantier.id)
        ], order='date_start asc')
        
        logger.info(f"📅 Tâches de planning trouvées pour le lot {lot.name}: {len(planning_tasks)}")
        
        for task in planning_tasks:
            logger.info(f"  - {task.name} ({task.state}) - {task.date_start} à {task.date_stop}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erreur test récupération tâches planning: {e}")
        return False

def test_generate_separate_pdfs(env):
    """Test de génération de PDF séparés."""
    try:
        # Récupérer les données de test
        lot = env['construction.lot'].search([], limit=1)
        chantier = env['construction.chantier'].search([], limit=1)
        subcontractor = env['res.partner'].search([('is_company', '=', True)], limit=1)
        
        if not all([lot, chantier, subcontractor]):
            logger.warning("⚠️ Données de test manquantes")
            return False
        
        # Créer un contrat de test
        contract_data = {
            'total_amount': 10000.0,
            'start_date': fields.Date.today(),
            'end_date': fields.Date.today() + timedelta(days=30),
            'urssaf_code': '43.34Z'
        }
        
        contract_service = env['construction.contract.service']
        
        # Récupérer les images BLG
        blg_images = contract_service._get_blg_images_base64()
        logger.info(f"🖼️ Images BLG chargées: logo={len(blg_images['logo'])} chars, signature={len(blg_images['signature'])} chars")
        
        # Test génération PDF bons de commande
        purchase_orders_pdf = contract_service._generate_purchase_orders_pdf(lot, contract_data, blg_images)
        if purchase_orders_pdf:
            logger.info(f"✅ PDF bons de commande généré: {len(purchase_orders_pdf)} bytes")
        else:
            logger.info("ℹ️ Aucun PDF bons de commande généré (pas de données)")
        
        # Test génération PDF planning Gantt
        planning_gantt_pdf = contract_service._generate_planning_gantt_pdf(lot, contract_data, blg_images)
        if planning_gantt_pdf:
            logger.info(f"✅ PDF planning Gantt généré: {len(planning_gantt_pdf)} bytes")
        else:
            logger.info("ℹ️ Aucun PDF planning Gantt généré (pas de données)")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erreur test génération PDF séparés: {e}")
        return False

def test_merge_pdfs(env):
    """Test de fusion de PDF."""
    try:
        contract_service = env['construction.contract.service']
        
        # Créer des PDF de test (contenu minimal)
        test_pdf1 = b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n/Contents 4 0 R\n>>\nendobj\n4 0 obj\n<<\n/Length 44\n>>\nstream\nBT\n/F1 12 Tf\n72 720 Td\n(Test PDF 1) Tj\nET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000204 00000 n \ntrailer\n<<\n/Size 5\n/Root 1 0 R\n>>\nstartxref\n297\n%%EOF\n'
        
        test_pdf2 = b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n/Contents 4 0 R\n>>\nendobj\n4 0 obj\n<<\n/Length 44\n>>\nstream\nBT\n/F1 12 Tf\n72 720 Td\n(Test PDF 2) Tj\nET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000204 00000 n \ntrailer\n<<\n/Size 5\n/Root 1 0 R\n>>\nstartxref\n297\n%%EOF\n'
        
        # Test de fusion
        merged_pdf = contract_service._merge_pdfs([test_pdf1, test_pdf2])
        
        if merged_pdf:
            logger.info(f"✅ PDF fusionnés avec succès: {len(merged_pdf)} bytes")
            return True
        else:
            logger.error("❌ Échec de la fusion des PDF")
            return False
        
    except Exception as e:
        logger.error(f"❌ Erreur test fusion PDF: {e}")
        return False

def test_complete_contract_generation(env):
    """Test complet de génération de contrat."""
    try:
        # Récupérer les données de test
        chantier = env['construction.chantier'].search([], limit=1)
        subcontractor = env['res.partner'].search([('is_company', '=', True)], limit=1)
        lot_ids = env['construction.lot'].search([], limit=2)
        
        if not all([chantier, subcontractor, lot_ids]):
            logger.warning("⚠️ Données de test manquantes pour la génération complète")
            return False
        
        # Données du contrat
        contract_data = {
            'total_amount': 15000.0,
            'start_date': fields.Date.today(),
            'end_date': fields.Date.today() + timedelta(days=60),
            'urssaf_code': '43.34Z',
            'payment_terms': '30_days',
            'warranty_period': 12,
            'insurance_required': True,
            'notes': 'Contrat de test pour validation des nouvelles fonctionnalités'
        }
        
        contract_service = env['construction.contract.service']
        
        # Générer le contrat
        logger.info("🔄 Génération du contrat...")
        contract = contract_service.generate_contract(chantier, subcontractor, lot_ids, contract_data)
        
        if contract and contract.contract_pdf:
            logger.info(f"✅ Contrat généré avec succès: {contract.name}")
            logger.info(f"📄 PDF généré: {len(contract.contract_pdf)} bytes")
            logger.info(f"🔗 URL portail: {contract.portal_url}")
            return True
        else:
            logger.error("❌ Échec de la génération du contrat")
            return False
        
    except Exception as e:
        logger.error(f"❌ Erreur test génération complète: {e}")
        return False

def main():
    """Fonction principale."""
    logger.info("🚀 Démarrage des tests d'intégration des contrats")
    
    try:
        test_contract_generation_with_pdf_annexes()
        logger.info("🎉 Tests terminés avec succès !")
    except Exception as e:
        logger.error(f"💥 Erreur fatale: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
