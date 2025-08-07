# -*- coding: utf-8 -*-
"""
Tests pour le wizard de génération de contrats
"""

from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class TestWizardContract(TransactionCase):
    """Tests pour le wizard de génération de contrats."""

    def setUp(self):
        """Configuration initiale pour les tests."""
        super().setUp()
        
        # Créer un chantier de test
        self.chantier = self.env['construction.chantier'].create({
            'name': 'Chantier Test Wizard',
            'description': 'Description du chantier test',
            'address': 'Adresse du chantier test',
        })
        
        # Créer un sous-traitant de test
        self.subcontractor = self.env['res.partner'].create({
            'name': 'Sous-traitant Test Wizard',
            'is_subcontractor': True,
            'email': 'test@example.com',
        })
        
        # Créer un lot de test
        self.lot = self.env['construction.lot'].create({
            'name': 'Lot Test Wizard',
            'chantier_id': self.chantier.id,
            'price': 1000.0,
        })

    def test_wizard_creation(self):
        """Test de création du wizard."""
        try:
            wizard = self.env['construction.contract.preview.wizard'].create({
                'chantier_id': self.chantier.id,
                'subcontractor_id': self.subcontractor.id,
                'lot_ids': [(6, 0, [self.lot.id])],
                'total_amount': 1000.0,
                'start_date': '2024-01-01',
                'end_date': '2024-12-31',
            })
            
            self.assertTrue(wizard.id)
            self.assertEqual(wizard.chantier_id, self.chantier)
            self.assertEqual(wizard.subcontractor_id, self.subcontractor)
            self.assertEqual(wizard.total_amount, 1000.0)
            
            _logger.info("✅ Wizard créé avec succès")
            
        except Exception as e:
            _logger.error(f"❌ Erreur lors de la création du wizard: {e}")
            self.fail(f"Impossible de créer le wizard: {e}")

    def test_wizard_load_default_values(self):
        """Test du chargement des valeurs par défaut."""
        try:
            wizard = self.env['construction.contract.preview.wizard'].create({
                'chantier_id': self.chantier.id,
                'subcontractor_id': self.subcontractor.id,
                'lot_ids': [(6, 0, [self.lot.id])],
                'total_amount': 1000.0,
            })
            
            # Appeler la méthode onchange
            wizard._onchange_load_default_values()
            
            # Vérifier que les valeurs sont chargées
            self.assertTrue(wizard.company_name)
            self.assertTrue(wizard.subcontractor_name)
            self.assertTrue(wizard.chantier_name)
            
            _logger.info("✅ Valeurs par défaut chargées avec succès")
            
        except Exception as e:
            _logger.error(f"❌ Erreur lors du chargement des valeurs par défaut: {e}")
            self.fail(f"Impossible de charger les valeurs par défaut: {e}")

    def test_wizard_preview_generation(self):
        """Test de génération de preview."""
        try:
            wizard = self.env['construction.contract.preview.wizard'].create({
                'chantier_id': self.chantier.id,
                'subcontractor_id': self.subcontractor.id,
                'lot_ids': [(6, 0, [self.lot.id])],
                'total_amount': 1000.0,
                'start_date': '2024-01-01',
                'end_date': '2024-12-31',
            })
            
            # Charger les valeurs par défaut
            wizard._onchange_load_default_values()
            
            # Générer la preview
            result = wizard.action_preview_contract()
            
            # Vérifier que la preview a été générée
            self.assertTrue(wizard.preview_pdf)
            self.assertTrue(wizard.preview_filename)
            
            _logger.info("✅ Preview générée avec succès")
            
        except Exception as e:
            _logger.error(f"❌ Erreur lors de la génération de preview: {e}")
            self.fail(f"Impossible de générer la preview: {e}")

    def test_wizard_final_contract_generation(self):
        """Test de génération du contrat final."""
        try:
            wizard = self.env['construction.contract.preview.wizard'].create({
                'chantier_id': self.chantier.id,
                'subcontractor_id': self.subcontractor.id,
                'lot_ids': [(6, 0, [self.lot.id])],
                'total_amount': 1000.0,
                'start_date': '2024-01-01',
                'end_date': '2024-12-31',
            })
            
            # Charger les valeurs par défaut
            wizard._onchange_load_default_values()
            
            # Générer le contrat final
            result = wizard.action_generate_final_contract()
            
            # Vérifier que le contrat a été créé
            contracts = self.env['construction.subcontractor.contract'].search([
                ('chantier_id', '=', self.chantier.id),
                ('subcontractor_id', '=', self.subcontractor.id)
            ])
            
            self.assertTrue(contracts)
            self.assertEqual(len(contracts), 1)
            
            _logger.info("✅ Contrat final généré avec succès")
            
        except Exception as e:
            _logger.error(f"❌ Erreur lors de la génération du contrat final: {e}")
            self.fail(f"Impossible de générer le contrat final: {e}")

    def test_wizard_with_missing_data(self):
        """Test du wizard avec des données manquantes."""
        try:
            # Créer un wizard avec des données minimales
            wizard = self.env['construction.contract.preview.wizard'].create({
                'total_amount': 1000.0,
            })
            
            # Vérifier que les validations fonctionnent
            with self.assertRaises(ValidationError):
                wizard.action_preview_contract()
            
            _logger.info("✅ Validation des données manquantes fonctionne")
            
        except Exception as e:
            _logger.error(f"❌ Erreur lors du test avec données manquantes: {e}")
            self.fail(f"Le test avec données manquantes a échoué: {e}") 