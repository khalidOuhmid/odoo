# -*- coding: utf-8 -*-
"""
Tests pour la génération de contrats de sous-traitance
"""

from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class TestContractGeneration(TransactionCase):
    """Tests pour la génération de contrats."""

    def setUp(self):
        """Configuration initiale pour les tests."""
        super().setUp()
        
        # Créer un chantier de test
        self.chantier = self.env['construction.chantier'].create({
            'name': 'Chantier Test',
            'description': 'Description du chantier test',
            'address': 'Adresse du chantier test',
        })
        
        # Créer un sous-traitant de test
        self.subcontractor = self.env['res.partner'].create({
            'name': 'Sous-traitant Test',
            'is_subcontractor': True,
            'email': 'test@example.com',
        })
        
        # Créer un lot de test
        self.lot = self.env['construction.lot'].create({
            'name': 'Lot Test',
            'chantier_id': self.chantier.id,
            'price': 1000.0,
        })

    def test_contract_model_exists(self):
        """Test que le modèle contract existe."""
        try:
            contract_model = self.env['construction.subcontractor.contract']
            self.assertTrue(contract_model)
            _logger.info("✅ Modèle construction.subcontractor.contract existe")
        except Exception as e:
            _logger.error(f"❌ Erreur lors de l'accès au modèle: {e}")
            self.fail(f"Le modèle construction.subcontractor.contract n'existe pas: {e}")

    def test_contract_creation(self):
        """Test de création d'un contrat."""
        try:
            contract = self.env['construction.subcontractor.contract'].create({
                'name': 'Contrat Test',
                'chantier_id': self.chantier.id,
                'subcontractor_id': self.subcontractor.id,
                'lot_ids': [(6, 0, [self.lot.id])],
                'total_amount': 1000.0,
                'start_date': '2024-01-01',
                'end_date': '2024-12-31',
            })
            
            self.assertTrue(contract.id)
            self.assertEqual(contract.name, 'Contrat Test')
            self.assertEqual(contract.chantier_id, self.chantier)
            self.assertEqual(contract.subcontractor_id, self.subcontractor)
            self.assertEqual(contract.total_amount, 1000.0)
            self.assertTrue(contract.contract_number)
            
            _logger.info("✅ Contrat créé avec succès")
            
        except Exception as e:
            _logger.error(f"❌ Erreur lors de la création du contrat: {e}")
            self.fail(f"Impossible de créer un contrat: {e}")

    def test_contract_service(self):
        """Test du service de génération de contrats."""
        try:
            service = self.env['construction.contract.service']
            
            contract_data = {
                'total_amount': 1000.0,
                'start_date': '2024-01-01',
                'end_date': '2024-12-31',
            }
            
            contract = service.generate_subcontractor_contract(
                self.chantier, 
                self.subcontractor, 
                self.lot, 
                contract_data
            )
            
            self.assertTrue(contract.id)
            self.assertEqual(contract.chantier_id, self.chantier)
            self.assertEqual(contract.subcontractor_id, self.subcontractor)
            self.assertEqual(contract.total_amount, 1000.0)
            
            _logger.info("✅ Service de génération de contrat fonctionne")
            
        except Exception as e:
            _logger.error(f"❌ Erreur lors du test du service: {e}")
            self.fail(f"Le service de génération de contrat ne fonctionne pas: {e}")

    def test_pdf_generation(self):
        """Test de génération de PDF."""
        try:
            # Créer un contrat
            contract = self.env['construction.subcontractor.contract'].create({
                'name': 'Contrat Test PDF',
                'chantier_id': self.chantier.id,
                'subcontractor_id': self.subcontractor.id,
                'lot_ids': [(6, 0, [self.lot.id])],
                'total_amount': 1000.0,
            })
            
            # Tester la génération de PDF
            service = self.env['construction.contract.service']
            pdf_content = service._generate_contract_pdf(contract)
            
            self.assertTrue(pdf_content)
            self.assertGreater(len(pdf_content), 0)
            
            _logger.info(f"✅ PDF généré avec succès: {len(pdf_content)} bytes")
            
        except Exception as e:
            _logger.error(f"❌ Erreur lors de la génération de PDF: {e}")
            self.fail(f"Impossible de générer le PDF: {e}")

    def test_template_rendering(self):
        """Test du rendu du template QWeb."""
        try:
            # Créer un contrat
            contract = self.env['construction.subcontractor.contract'].create({
                'name': 'Contrat Test Template',
                'chantier_id': self.chantier.id,
                'subcontractor_id': self.subcontractor.id,
                'lot_ids': [(6, 0, [self.lot.id])],
                'total_amount': 1000.0,
            })
            
            # Vérifier que le template existe
            template = self.env.ref('construction_base.contrat_sous_traitance_template', raise_if_not_found=False)
            self.assertTrue(template, "Le template contrat_sous_traitance_template n'existe pas")
            
            # Vérifier que le report existe
            report = self.env.ref('construction_base.report_subcontractor_contract', raise_if_not_found=False)
            self.assertTrue(report, "Le report report_subcontractor_contract n'existe pas")
            
            _logger.info("✅ Template et report existent")
            
        except Exception as e:
            _logger.error(f"❌ Erreur lors du test du template: {e}")
            self.fail(f"Problème avec le template: {e}") 