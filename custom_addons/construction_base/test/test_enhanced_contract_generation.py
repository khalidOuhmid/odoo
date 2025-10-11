# -*- coding: utf-8 -*-
"""
Tests pour la génération de contrats améliorée avec CCTP, planning Gantt et bons de commande
"""

from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class TestEnhancedContractGeneration(TransactionCase):
    """Tests pour la génération de contrats améliorée."""

    def setUp(self):
        """Préparation des données de test."""
        super().setUp()
        
        # Créer un chantier de test
        self.chantier = self.env['construction.chantier'].create({
            'name': 'Chantier Test Contrat Amélioré',
            'client': self.env['res.partner'].create({
                'name': 'Client Test',
                'email': 'client@test.com'
            }).id,
            'address': '123 Rue Test, 33000 Bordeaux',
            'date_start_contract': datetime.now().date(),
            'date_end_contract': (datetime.now() + timedelta(days=90)).date(),
            'total_cost': 50000.0,
        })
        
        # Créer un sous-traitant
        self.subcontractor = self.env['res.partner'].create({
            'name': 'Sous-traitant Test',
            'email': 'sous-traitant@test.com',
            'supplier_rank': 1,
            'contact_type': 'sous_traitant'
        })
        
        # Créer un lot
        self.lot = self.env['construction.lot'].create({
            'name': 'Lot Test - Peinture',
            'chantier_id': self.chantier.id,
            'price': 15000.0,
            'urssaf_code': '43.34Z - Travaux de peinture et vitrerie',
            'description': 'Travaux de peinture intérieure et extérieure',
            'subcontractor_ids': [(6, 0, [self.subcontractor.id])]
        })
        
        # Créer des tâches de planning
        self.task1 = self.env['construction.planning.task'].create({
            'name': 'Préparation surfaces',
            'chantier_id': self.chantier.id,
            'lot_id': self.lot.id,
            'subcontractor_id': self.subcontractor.id,
            'date_start': datetime.now() + timedelta(days=1),
            'date_stop': datetime.now() + timedelta(days=5),
            'state': 'planned'
        })
        
        self.task2 = self.env['construction.planning.task'].create({
            'name': 'Application peinture',
            'chantier_id': self.chantier.id,
            'lot_id': self.lot.id,
            'subcontractor_id': self.subcontractor.id,
            'date_start': datetime.now() + timedelta(days=6),
            'date_stop': datetime.now() + timedelta(days=15),
            'state': 'planned'
        })
        
        # Créer un bon de commande
        self.purchase_order = self.env['purchase.order'].create({
            'partner_id': self.subcontractor.id,
            'chantier_id': self.chantier.id,
            'lot_ids': [(6, 0, [self.lot.id])],
            'state': 'purchase',
            'date_order': datetime.now()
        })
        
        # Créer des lignes de commande
        product1 = self.env['product.product'].create({
            'name': 'Peinture blanche',
            'type': 'product',
            'list_price': 25.0
        })
        
        product2 = self.env['product.product'].create({
            'name': 'Rouleaux',
            'type': 'product',
            'list_price': 15.0
        })
        
        self.env['purchase.order.line'].create({
            'order_id': self.purchase_order.id,
            'product_id': product1.id,
            'name': 'Peinture blanche 10L',
            'product_qty': 20,
            'price_unit': 25.0,
            'lot_id': self.lot.id
        })
        
        self.env['purchase.order.line'].create({
            'order_id': self.purchase_order.id,
            'product_id': product2.id,
            'name': 'Rouleaux professionnels',
            'product_qty': 10,
            'price_unit': 15.0,
            'lot_id': self.lot.id
        })

    def test_enhanced_contract_generation(self):
        """Test de la génération de contrat avec toutes les annexes."""
        try:
            # Utiliser le service de génération
            contract_service = self.env['construction.contract.service']
            
            # Préparer les données du contrat
            contract_data = {
                'start_date': datetime.now().date(),
                'end_date': (datetime.now() + timedelta(days=30)).date(),
                'total_amount': 15000.0,
                'payment_terms': '30_days',
                'warranty_period': 12,
                'insurance_required': True,
                'notes': 'Contrat de test avec annexes complètes',
                'urssaf_code': '43.34Z'
            }
            
            # Générer le contrat
            contract = contract_service.generate_contract(
                self.chantier,
                self.subcontractor,
                self.lot,
                contract_data
            )
            
            # Vérifications
            self.assertTrue(contract, "Le contrat doit être créé")
            self.assertEqual(contract.chantier_id, self.chantier)
            self.assertEqual(contract.subcontractor_id, self.subcontractor)
            self.assertIn(self.lot, contract.lot_ids)
            self.assertTrue(contract.contract_pdf, "Le PDF doit être généré")
            
            _logger.info(f"✅ Contrat généré avec succès: {contract.name}")
            _logger.info(f"📄 PDF généré: {len(contract.contract_pdf)} bytes")
            
        except Exception as e:
            _logger.error(f"❌ Erreur lors de la génération du contrat: {e}")
            self.fail(f"Impossible de générer le contrat: {e}")

    def test_cctp_page_generation(self):
        """Test de la génération de la page CCTP."""
        try:
            contract_service = self.env['construction.contract.service']
            
            # Récupérer les images BLG
            blg_images = contract_service._get_blg_images_base64()
            
            # Générer la page CCTP
            cctp_html = contract_service._create_cctp_page(self.lot, blg_images)
            
            # Vérifications
            self.assertTrue(cctp_html, "Le HTML CCTP doit être généré")
            self.assertIn(self.lot.name, cctp_html)
            self.assertIn('CCTP', cctp_html)
            self.assertIn(str(self.lot.price), cctp_html)
            self.assertIn(self.lot.urssaf_code, cctp_html)
            
            _logger.info(f"✅ Page CCTP générée avec succès pour le lot: {self.lot.name}")
            
        except Exception as e:
            _logger.error(f"❌ Erreur lors de la génération de la page CCTP: {e}")
            self.fail(f"Impossible de générer la page CCTP: {e}")

    def test_planning_gantt_page_generation(self):
        """Test de la génération de la page planning Gantt."""
        try:
            contract_service = self.env['construction.contract.service']
            
            # Créer un contrat temporaire pour le test
            temp_contract = self.env['construction.subcontractor.contract'].create({
                'name': 'Contrat Test Planning',
                'chantier_id': self.chantier.id,
                'subcontractor_id': self.subcontractor.id,
                'lot_ids': [(6, 0, [self.lot.id])],
                'start_date': datetime.now().date(),
                'end_date': (datetime.now() + timedelta(days=30)).date(),
                'total_amount': 15000.0
            })
            
            # Récupérer les images BLG
            blg_images = contract_service._get_blg_images_base64()
            
            # Générer la page planning Gantt
            planning_html = contract_service._create_planning_gantt_page(self.lot, temp_contract, blg_images)
            
            # Vérifications
            self.assertTrue(planning_html, "Le HTML planning Gantt doit être généré")
            self.assertIn(self.lot.name, planning_html)
            self.assertIn('Planning Gantt', planning_html)
            self.assertIn(self.task1.name, planning_html)
            self.assertIn(self.task2.name, planning_html)
            self.assertIn(self.subcontractor.name, planning_html)
            
            _logger.info(f"✅ Page Planning Gantt générée avec succès pour le lot: {self.lot.name}")
            
        except Exception as e:
            _logger.error(f"❌ Erreur lors de la génération de la page planning Gantt: {e}")
            self.fail(f"Impossible de générer la page planning Gantt: {e}")

    def test_purchase_orders_page_generation(self):
        """Test de la génération de la page bons de commande."""
        try:
            contract_service = self.env['construction.contract.service']
            
            # Créer un contrat temporaire pour le test
            temp_contract = self.env['construction.subcontractor.contract'].create({
                'name': 'Contrat Test Commandes',
                'chantier_id': self.chantier.id,
                'subcontractor_id': self.subcontractor.id,
                'lot_ids': [(6, 0, [self.lot.id])],
                'start_date': datetime.now().date(),
                'end_date': (datetime.now() + timedelta(days=30)).date(),
                'total_amount': 15000.0
            })
            
            # Récupérer les images BLG
            blg_images = contract_service._get_blg_images_base64()
            
            # Générer la page bons de commande
            orders_html = contract_service._create_purchase_orders_page(self.lot, temp_contract, blg_images)
            
            # Vérifications
            self.assertTrue(orders_html, "Le HTML bons de commande doit être généré")
            self.assertIn(self.lot.name, orders_html)
            self.assertIn('Bons de commande', orders_html)
            self.assertIn(self.purchase_order.name, orders_html)
            self.assertIn('Peinture blanche', orders_html)
            self.assertIn('Rouleaux', orders_html)
            
            _logger.info(f"✅ Page Bons de commande générée avec succès pour le lot: {self.lot.name}")
            
        except Exception as e:
            _logger.error(f"❌ Erreur lors de la génération de la page bons de commande: {e}")
            self.fail(f"Impossible de générer la page bons de commande: {e}")

    def test_enhanced_annexes_generation(self):
        """Test de la génération complète des annexes."""
        try:
            contract_service = self.env['construction.contract.service']
            
            # Créer un contrat temporaire pour le test
            temp_contract = self.env['construction.subcontractor.contract'].create({
                'name': 'Contrat Test Annexes',
                'chantier_id': self.chantier.id,
                'subcontractor_id': self.subcontractor.id,
                'lot_ids': [(6, 0, [self.lot.id])],
                'start_date': datetime.now().date(),
                'end_date': (datetime.now() + timedelta(days=30)).date(),
                'total_amount': 15000.0
            })
            
            # Récupérer les images BLG
            blg_images = contract_service._get_blg_images_base64()
            
            # Générer toutes les annexes
            annexes_html = contract_service._generate_annexes_html(temp_contract, blg_images)
            
            # Vérifications
            self.assertTrue(annexes_html, "Les annexes doivent être générées")
            self.assertIn('CCTP', annexes_html)
            self.assertIn('Planning Gantt', annexes_html)
            self.assertIn('Bons de commande', annexes_html)
            
            _logger.info(f"✅ Toutes les annexes générées avec succès")
            _logger.info(f"📄 Taille des annexes: {len(annexes_html)} caractères")
            
        except Exception as e:
            _logger.error(f"❌ Erreur lors de la génération des annexes: {e}")
            self.fail(f"Impossible de générer les annexes: {e}")

    def test_preview_generation(self):
        """Test de la génération de la prévisualisation complète."""
        try:
            contract_service = self.env['construction.contract.service']
            
            # Préparer les données du contrat
            contract_data = {
                'start_date': datetime.now().date(),
                'end_date': (datetime.now() + timedelta(days=30)).date(),
                'total_amount': 15000.0,
                'payment_terms': '30_days',
                'warranty_period': 12,
                'insurance_required': True,
                'notes': 'Prévisualisation de test',
                'urssaf_code': '43.34Z'
            }
            
            # Générer la prévisualisation
            preview_html = contract_service.generate_preview_html(
                self.chantier,
                self.subcontractor,
                self.lot,
                contract_data
            )
            
            # Vérifications
            self.assertTrue(preview_html, "La prévisualisation doit être générée")
            self.assertIn('Aperçu Contrat', preview_html)
            self.assertIn(self.chantier.name, preview_html)
            self.assertIn(self.subcontractor.name, preview_html)
            
            _logger.info(f"✅ Prévisualisation générée avec succès")
            _logger.info(f"📄 Taille de la prévisualisation: {len(preview_html)} caractères")
            
        except Exception as e:
            _logger.error(f"❌ Erreur lors de la génération de la prévisualisation: {e}")
            self.fail(f"Impossible de générer la prévisualisation: {e}")

    def test_blg_images_loading(self):
        """Test du chargement des images BLG."""
        try:
            contract_service = self.env['construction.contract.service']
            
            # Récupérer les images BLG
            blg_images = contract_service._get_blg_images_base64()
            
            # Vérifications
            self.assertIn('logo', blg_images)
            self.assertIn('signature', blg_images)
            
            # Les images peuvent être vides si les fichiers n'existent pas
            # mais la structure doit être présente
            _logger.info(f"✅ Images BLG chargées avec succès")
            _logger.info(f"🖼️ Logo: {'Présent' if blg_images['logo'] else 'Absent'}")
            _logger.info(f"✍️ Signature: {'Présente' if blg_images['signature'] else 'Absente'}")
            
        except Exception as e:
            _logger.error(f"❌ Erreur lors du chargement des images BLG: {e}")
            self.fail(f"Impossible de charger les images BLG: {e}")

    def test_contract_without_planning_tasks(self):
        """Test de la génération de contrat sans tâches de planning."""
        try:
            # Supprimer les tâches de planning
            self.task1.unlink()
            self.task2.unlink()
            
            contract_service = self.env['construction.contract.service']
            
            # Préparer les données du contrat
            contract_data = {
                'start_date': datetime.now().date(),
                'end_date': (datetime.now() + timedelta(days=30)).date(),
                'total_amount': 15000.0,
                'payment_terms': '30_days',
                'warranty_period': 12,
                'insurance_required': True,
                'notes': 'Contrat sans planning',
                'urssaf_code': '43.34Z'
            }
            
            # Générer le contrat
            contract = contract_service.generate_contract(
                self.chantier,
                self.subcontractor,
                self.lot,
                contract_data
            )
            
            # Vérifications
            self.assertTrue(contract, "Le contrat doit être créé même sans planning")
            self.assertTrue(contract.contract_pdf, "Le PDF doit être généré")
            
            _logger.info(f"✅ Contrat généré avec succès sans tâches de planning")
            
        except Exception as e:
            _logger.error(f"❌ Erreur lors de la génération du contrat sans planning: {e}")
            self.fail(f"Impossible de générer le contrat sans planning: {e}")

    def test_contract_without_purchase_orders(self):
        """Test de la génération de contrat sans bons de commande."""
        try:
            # Supprimer le bon de commande
            self.purchase_order.unlink()
            
            contract_service = self.env['construction.contract.service']
            
            # Préparer les données du contrat
            contract_data = {
                'start_date': datetime.now().date(),
                'end_date': (datetime.now() + timedelta(days=30)).date(),
                'total_amount': 15000.0,
                'payment_terms': '30_days',
                'warranty_period': 12,
                'insurance_required': True,
                'notes': 'Contrat sans commandes',
                'urssaf_code': '43.34Z'
            }
            
            # Générer le contrat
            contract = contract_service.generate_contract(
                self.chantier,
                self.subcontractor,
                self.lot,
                contract_data
            )
            
            # Vérifications
            self.assertTrue(contract, "Le contrat doit être créé même sans commandes")
            self.assertTrue(contract.contract_pdf, "Le PDF doit être généré")
            
            _logger.info(f"✅ Contrat généré avec succès sans bons de commande")
            
        except Exception as e:
            _logger.error(f"❌ Erreur lors de la génération du contrat sans commandes: {e}")
            self.fail(f"Impossible de générer le contrat sans commandes: {e}")


if __name__ == '__main__':
    # Exécution des tests
    print("🧪 Tests de génération de contrats améliorée")
    print("=" * 50)
    
    # Note: Ces tests doivent être exécutés dans un environnement Odoo
    # avec le module construction_base installé
    print("✅ Tests prêts à être exécutés")
    print("📋 Vérifiez que le module construction_base est installé")
    print("🔧 Assurez-vous que les images BLG sont présentes")
