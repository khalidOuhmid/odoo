# -*- coding: utf-8 -*-
"""
Tests pour le modèle construction.subcontractor.contract
"""

from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError


class TestSubcontractorContract(TransactionCase):
    """Tests pour le modèle SubcontractorContract."""

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

    def test_create_contract(self):
        """Test de création d'un contrat."""
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

    def test_contract_has_required_fields(self):
        """Test que le contrat a tous les champs requis."""
        contract = self.env['construction.subcontractor.contract'].create({
            'name': 'Contrat Test',
            'chantier_id': self.chantier.id,
            'subcontractor_id': self.subcontractor.id,
            'lot_ids': [(6, 0, [self.lot.id])],
            'total_amount': 1000.0,
        })
        
        # Vérifier que tous les champs requis existent
        required_fields = [
            'chantier_id', 'subcontractor_id', 'lot_ids', 'total_amount',
            'start_date', 'end_date', 'contract_number', 'state'
        ]
        
        for field in required_fields:
            self.assertTrue(hasattr(contract, field), f"Le champ {field} n'existe pas")

    def test_generate_contract_number(self):
        """Test de génération du numéro de contrat."""
        contract = self.env['construction.subcontractor.contract'].create({
            'name': 'Contrat Test',
            'chantier_id': self.chantier.id,
            'subcontractor_id': self.subcontractor.id,
            'lot_ids': [(6, 0, [self.lot.id])],
            'total_amount': 1000.0,
        })
        
        self.assertTrue(contract.contract_number)
        self.assertTrue(contract.contract_number.startswith('CONTRACT-'))

    def test_contract_service(self):
        """Test du service de génération de contrats."""
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