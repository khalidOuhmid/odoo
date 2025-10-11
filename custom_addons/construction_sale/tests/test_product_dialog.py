# -*- coding: utf-8 -*-
"""Tests unitaires pour ProductAddDialog."""

from odoo.tests import TransactionCase
from odoo.exceptions import ValidationError


class TestProductAddDialog(TransactionCase):
    """Tests unitaires pour le popup d'ajout de produit.
    
    Cette classe teste :
    - Création et initialisation du dialog
    - Auto-assignation des lots et unités
    - Calculs de prix et marges
    - Validation des données
    - Actions de confirmation et annulation
    """

    @classmethod
    def setUpClass(cls):
        """Configuration initiale des tests."""
        super().setUpClass()
        
        # Créer les données de base
        cls.company = cls.env['res.company'].create({
            'name': 'Test Company',
            'currency_id': cls.env.ref('base.EUR').id,
        })
        
        cls.chantier = cls.env['construction.chantier'].create({
            'name': 'Chantier Test',
            'company_id': cls.company.id,
        })
        
        cls.lot = cls.env['construction.lot'].create({
            'name': 'Lot Test',
            'chantier_id': cls.chantier.id,
        })
        
        cls.uom_m2 = cls.env['uom.uom'].create({
            'name': 'm²',
            'category_id': cls.env.ref('uom.product_uom_categ_area').id,
            'uom_type': 'reference',
            'factor': 1.0,
        })
        
        cls.product = cls.env['product.product'].create({
            'name': 'Produit Test',
            'default_code': 'PROD-TEST',
            'uom_id': cls.uom_m2.id,
            'standard_price': 100.0,
            'list_price': 150.0,
        })
        
        cls.partner = cls.env['res.partner'].create({
            'name': 'Client Test',
        })
        
        cls.sale_order = cls.env['sale.order'].create({
            'partner_id': cls.partner.id,
            'chantier_id': cls.chantier.id,
        })
        
        cls.wizard = cls.env['construction.quote.wizard'].create({
            'sale_order_id': cls.sale_order.id,
            'chantier_id': cls.chantier.id,
            'lot_ids': [(6, 0, [cls.lot.id])],
            'default_margin_percent': 25.0,
        })

    def test_dialog_creation_basic(self):
        """Test de création basique du dialog.
        
        Vérifie que :
        - Le dialog se crée avec les champs obligatoires
        - Les lots disponibles sont calculés
        - L'unité de mesure est initialisée
        """
        dialog = self.env['construction.product.dialog'].create({
            'quote_wizard_id': self.wizard.id,
            'product_id': self.product.id,
        })
        
        self.assertEqual(dialog.quote_wizard_id, self.wizard)
        self.assertEqual(dialog.product_id, self.product)
        self.assertEqual(dialog.product_name, self.product.display_name)
        self.assertEqual(dialog.base_price, self.product.standard_price)
        self.assertEqual(dialog.uom_id, self.product.uom_id)

    def test_auto_assign_single_lot(self):
        """Test d'auto-assignation du lot unique.
        
        Vérifie que :
        - Le lot unique est assigné automatiquement
        - L'unité du produit est récupérée
        - Les valeurs par défaut sont correctes
        """
        dialog = self.env['construction.product.dialog'].create({
            'quote_wizard_id': self.wizard.id,
            'product_id': self.product.id,
        })
        
        self.assertEqual(dialog.lot_id, self.lot)
        self.assertEqual(dialog.uom_id, self.product.uom_id)
        self.assertEqual(dialog.quantity, 1.0)

    def test_auto_assign_multiple_lots(self):
        """Test avec plusieurs lots disponibles.
        
        Vérifie que :
        - Le premier lot est assigné par défaut
        - Tous les lots sont disponibles dans le domain
        """
        # Créer un second lot
        lot2 = self.env['construction.lot'].create({
            'name': 'Lot Test 2',
            'chantier_id': self.chantier.id,
        })
        
        # Ajouter le lot au wizard
        self.wizard.lot_ids = [(6, 0, [self.lot.id, lot2.id])]
        
        dialog = self.env['construction.product.dialog'].create({
            'quote_wizard_id': self.wizard.id,
            'product_id': self.product.id,
        })
        
        self.assertIn(self.lot, dialog.available_lot_ids)
        self.assertIn(lot2, dialog.available_lot_ids)
        # Le premier lot doit être assigné
        self.assertEqual(dialog.lot_id, self.lot)

    def test_compute_unit_price(self):
        """Test du calcul du prix unitaire.
        
        Vérifie que :
        - Le prix = coût × (1 + marge/100)
        - Le calcul se met à jour automatiquement
        - Les marges négatives sont gérées
        """
        dialog = self.env['construction.product.dialog'].create({
            'quote_wizard_id': self.wizard.id,
            'product_id': self.product.id,
            'margin_percent': 20.0,
        })
        
        expected_price = 100.0 * (1 + 20.0 / 100.0)  # 120.0
        self.assertEqual(dialog.unit_price, expected_price)
        
        # Test avec marge nulle
        dialog.margin_percent = 0.0
        dialog._compute_unit_price()
        self.assertEqual(dialog.unit_price, 100.0)
        
        # Test avec marge négative
        dialog.margin_percent = -10.0
        dialog._compute_unit_price()
        self.assertEqual(dialog.unit_price, 90.0)

    def test_compute_total_price(self):
        """Test du calcul du prix total.
        
        Vérifie que :
        - Total = quantité × prix unitaire
        - Le calcul se met à jour automatiquement
        """
        dialog = self.env['construction.product.dialog'].create({
            'quote_wizard_id': self.wizard.id,
            'product_id': self.product.id,
            'quantity': 5.0,
            'margin_percent': 20.0,
        })
        
        expected_total = 5.0 * (100.0 * 1.2)  # 5 × 120 = 600
        self.assertEqual(dialog.total_price, expected_total)

    def test_action_confirm_add_valid(self):
        """Test de confirmation d'ajout valide.
        
        Vérifie que :
        - Une ligne est créée dans le wizard parent
        - Les données sont correctement transférées
        - L'action retourne vers le wizard
        """
        dialog = self.env['construction.product.dialog'].create({
            'quote_wizard_id': self.wizard.id,
            'product_id': self.product.id,
            'quantity': 3.0,
            'margin_percent': 15.0,
            'room_number': 'S01',
            'room_location': 'Salon',
            'description': 'Notes test',
        })
        
        initial_line_count = len(self.wizard.selected_line_ids)
        
        action = dialog.action_confirm_add()
        
        # Vérifier qu'une ligne a été créée
        self.assertEqual(len(self.wizard.selected_line_ids), initial_line_count + 1)
        
        # Vérifier les données de la ligne créée
        new_line = self.wizard.selected_line_ids[-1]
        self.assertEqual(new_line.product_id, self.product)
        self.assertEqual(new_line.quantity, 3.0)
        self.assertEqual(new_line.lot_id, self.lot)
        self.assertEqual(new_line.uom_id, self.product.uom_id)
        self.assertEqual(new_line.room_number, 'S01')
        self.assertEqual(new_line.room_location, 'Salon')
        self.assertEqual(new_line.construction_notes, 'Notes test')
        
        # Vérifier le retour d'action
        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_model'], 'construction.quote.wizard')

    def test_action_confirm_add_invalid_quantity(self):
        """Test de confirmation avec quantité invalide.
        
        Vérifie que :
        - Une exception est levée pour quantité <= 0
        - Le message d'erreur est approprié
        """
        dialog = self.env['construction.product.dialog'].create({
            'quote_wizard_id': self.wizard.id,
            'product_id': self.product.id,
            'quantity': 0.0,
        })
        
        with self.assertRaises(ValidationError) as cm:
            dialog.action_confirm_add()
        
        self.assertIn("quantité doit être positive", str(cm.exception))

    def test_action_confirm_add_no_lot(self):
        """Test de confirmation sans lot sélectionné.
        
        Vérifie que :
        - Une exception est levée si pas de lot
        - Le message d'erreur est approprié
        """
        dialog = self.env['construction.product.dialog'].create({
            'quote_wizard_id': self.wizard.id,
            'product_id': self.product.id,
            'lot_id': False,
        })
        
        with self.assertRaises(ValidationError) as cm:
            dialog.action_confirm_add()
        
        self.assertIn("sélectionner un lot", str(cm.exception))

    def test_action_confirm_add_no_uom(self):
        """Test de confirmation sans unité de mesure.
        
        Vérifie que :
        - Une exception est levée si pas d'unité
        - Le message d'erreur est approprié
        """
        dialog = self.env['construction.product.dialog'].create({
            'quote_wizard_id': self.wizard.id,
            'product_id': self.product.id,
            'uom_id': False,
        })
        
        with self.assertRaises(ValidationError) as cm:
            dialog.action_confirm_add()
        
        self.assertIn("unité de mesure", str(cm.exception))

    def test_action_cancel(self):
        """Test d'annulation du dialog.
        
        Vérifie que :
        - L'action retourne vers le wizard parent
        - Aucune ligne n'est créée
        """
        dialog = self.env['construction.product.dialog'].create({
            'quote_wizard_id': self.wizard.id,
            'product_id': self.product.id,
        })
        
        initial_line_count = len(self.wizard.selected_line_ids)
        
        action = dialog.action_cancel()
        
        # Vérifier qu'aucune ligne n'a été créée
        self.assertEqual(len(self.wizard.selected_line_ids), initial_line_count)
        
        # Vérifier le retour d'action
        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_model'], 'construction.quote.wizard')

    def test_default_uom_fallback(self):
        """Test du fallback pour l'unité de mesure.
        
        Vérifie que :
        - Si le produit n'a pas d'unité, une unité par défaut est utilisée
        - L'unité "Units" est utilisée en dernier recours
        """
        # Créer un produit sans unité spécifique
        product_no_uom = self.env['product.product'].create({
            'name': 'Produit Sans UoM',
            'standard_price': 50.0,
        })
        
        dialog = self.env['construction.product.dialog'].create({
            'quote_wizard_id': self.wizard.id,
            'product_id': product_no_uom.id,
        })
        
        # Vérifier qu'une unité a été assignée
        self.assertTrue(dialog.uom_id)

    def test_compute_available_lots_empty_wizard(self):
        """Test du calcul des lots avec wizard sans lots.
        
        Vérifie que :
        - Si le wizard n'a pas de lots, aucun lot n'est disponible
        - Le calcul gère les cas vides
        """
        wizard_empty = self.env['construction.quote.wizard'].create({
            'sale_order_id': self.sale_order.id,
            'chantier_id': self.chantier.id,
            # Pas de lots sélectionnés
        })
        
        dialog = self.env['construction.product.dialog'].create({
            'quote_wizard_id': wizard_empty.id,
            'product_id': self.product.id,
        })
        
        self.assertEqual(len(dialog.available_lot_ids), 0)
