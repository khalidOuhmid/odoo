# -*- coding: utf-8 -*-
"""
Tests pour le rendu du template de contrat
"""

from odoo.tests.common import TransactionCase
import logging

_logger = logging.getLogger(__name__)


class TestTemplateRendering(TransactionCase):
    """Tests pour le rendu du template de contrat."""

    def setUp(self):
        """Configuration initiale pour les tests."""
        super().setUp()
        
        # Créer un chantier de test
        self.chantier = self.env['construction.chantier'].create({
            'name': 'Chantier Test Template',
            'description': 'Description du chantier test',
            'address': 'Adresse du chantier test',
        })
        
        # Créer un sous-traitant de test
        self.subcontractor = self.env['res.partner'].create({
            'name': 'Sous-traitant Test Template',
            'is_subcontractor': True,
            'email': 'test@example.com',
        })
        
        # Créer un lot de test
        self.lot = self.env['construction.lot'].create({
            'name': 'Lot Test Template',
            'chantier_id': self.chantier.id,
            'price': 1000.0,
        })

    def test_template_exists(self):
        """Test que le template existe."""
        try:
            template = self.env.ref('construction_base.contrat_sous_traitance_template', raise_if_not_found=False)
            self.assertTrue(template, "Le template contrat_sous_traitance_template n'existe pas")
            _logger.info("✅ Template contrat_sous_traitance_template trouvé")
        except Exception as e:
            _logger.error(f"❌ Erreur lors de l'accès au template: {e}")
            self.fail(f"Impossible d'accéder au template: {e}")

    def test_report_exists(self):
        """Test que le report existe."""
        try:
            report = self.env.ref('construction_base.report_subcontractor_contract', raise_if_not_found=False)
            self.assertTrue(report, "Le report report_subcontractor_contract n'existe pas")
            _logger.info("✅ Report report_subcontractor_contract trouvé")
        except Exception as e:
            _logger.error(f"❌ Erreur lors de l'accès au report: {e}")
            self.fail(f"Impossible d'accéder au report: {e}")

    def test_contract_creation_for_template(self):
        """Test de création d'un contrat pour le template."""
        try:
            contract = self.env['construction.subcontractor.contract'].create({
                'name': 'Contrat Test Template',
                'chantier_id': self.chantier.id,
                'subcontractor_id': self.subcontractor.id,
                'lot_ids': [(6, 0, [self.lot.id])],
                'total_amount': 1000.0,
                'start_date': '2024-01-01',
                'end_date': '2024-12-31',
            })
            
            self.assertTrue(contract.id)
            self.assertEqual(contract.chantier_id, self.chantier)
            self.assertEqual(contract.subcontractor_id, self.subcontractor)
            self.assertEqual(contract.total_amount, 1000.0)
            
            _logger.info("✅ Contrat créé avec succès pour le test de template")
            return contract
            
        except Exception as e:
            _logger.error(f"❌ Erreur lors de la création du contrat: {e}")
            self.fail(f"Impossible de créer un contrat: {e}")

    def test_template_rendering_with_valid_data(self):
        """Test du rendu du template avec des données valides."""
        try:
            # Créer un contrat
            contract = self.test_contract_creation_for_template()
            
            # Vérifier que le template peut être rendu
            template = self.env.ref('construction_base.contrat_sous_traitance_template')
            
            # Tester le rendu du template
            rendered_content = template._render({'docs': contract})
            
            self.assertTrue(rendered_content)
            self.assertIn('Contrat de sous-traitance', rendered_content)
            self.assertIn('BLG GROUPE', rendered_content)
            
            _logger.info("✅ Template rendu avec succès")
            
        except Exception as e:
            _logger.error(f"❌ Erreur lors du rendu du template: {e}")
            self.fail(f"Impossible de rendre le template: {e}")

    def test_pdf_generation_with_template(self):
        """Test de génération de PDF avec le template."""
        try:
            # Créer un contrat
            contract = self.test_contract_creation_for_template()
            
            # Tester la génération de PDF
            service = self.env['construction.contract.service']
            pdf_content = service._generate_contract_pdf(contract)
            
            self.assertTrue(pdf_content)
            self.assertGreater(len(pdf_content), 0)
            
            _logger.info(f"✅ PDF généré avec succès: {len(pdf_content)} bytes")
            
        except Exception as e:
            _logger.error(f"❌ Erreur lors de la génération de PDF: {e}")
            self.fail(f"Impossible de générer le PDF: {e}")

    def test_template_with_missing_data(self):
        """Test du template avec des données manquantes."""
        try:
            # Créer un contrat avec des données minimales
            contract = self.env['construction.subcontractor.contract'].create({
                'name': 'Contrat Test Minimal',
                'total_amount': 0.0,
            })
            
            # Le template devrait gérer les données manquantes
            template = self.env.ref('construction_base.contrat_sous_traitance_template')
            rendered_content = template._render({'docs': contract})
            
            self.assertTrue(rendered_content)
            self.assertIn('Non défini', rendered_content)
            
            _logger.info("✅ Template gère correctement les données manquantes")
            
        except Exception as e:
            _logger.error(f"❌ Erreur lors du test avec données manquantes: {e}")
            self.fail(f"Le template ne gère pas les données manquantes: {e}") 