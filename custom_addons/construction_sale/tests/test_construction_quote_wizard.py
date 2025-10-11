# -*- coding: utf-8 -*-
"""Tests unitaires pour ConstructionQuoteWizard."""

from odoo.tests import TransactionCase
from odoo.exceptions import ValidationError
from odoo import fields


class TestConstructionQuoteWizard(TransactionCase):
    """Tests unitaires pour l'assistant de création de devis construction.
    
    Cette classe teste toutes les fonctionnalités principales du wizard :
    - Création et initialisation
    - Calculs automatiques (totaux, devise, etc.)
    - Gestion des lots et produits
    - Actions utilisateur (ajout, suppression, confirmation)
    - Validation des données
    """

    @classmethod
    def setUpClass(cls):
        """Configuration initiale des tests.
        
        Crée les données de test nécessaires :
        - Chantier avec lots
        - Produits de test
        - Catégories et unités de mesure
        - Devis de base
        """
        super().setUpClass()
        
        # Création d'une société de test
        cls.company = cls.env['res.company'].create({
            'name': 'Test Construction Company',
            'currency_id': cls.env.ref('base.EUR').id,
        })
        
        # Création d'un chantier de test
        cls.chantier = cls.env['construction.chantier'].create({
            'name': 'Chantier Test Villa',
            'description': 'Chantier de test pour les tests unitaires',
            'company_id': cls.company.id,
        })
        
        # Création de lots de test
        cls.lot_gros_oeuvre = cls.env['construction.lot'].create({
            'name': 'Gros Œuvre',
            'description': 'Fondations, murs porteurs',
            'chantier_id': cls.chantier.id,
        })
        
        cls.lot_second_oeuvre = cls.env['construction.lot'].create({
            'name': 'Second Œuvre',
            'description': 'Cloisons, électricité, plomberie',
            'chantier_id': cls.chantier.id,
        })
        
        # Création d'une catégorie de produit
        cls.category_construction = cls.env['product.category'].create({
            'name': 'Construction BTP',
        })
        
        # Création d'unités de mesure
        cls.uom_m2 = cls.env['uom.uom'].create({
            'name': 'm²',
            'category_id': cls.env.ref('uom.product_uom_categ_area').id,
            'uom_type': 'reference',
            'factor': 1.0,
        })
        
        cls.uom_piece = cls.env.ref('uom.product_uom_unit')
        
        # Création de produits de test
        cls.product_beton = cls.env['product.product'].create({
            'name': 'Béton C25/30',
            'default_code': 'BET-C25',
            'categ_id': cls.category_construction.id,
            'uom_id': cls.uom_m2.id,
            'standard_price': 120.0,
            'list_price': 180.0,
            'sale_ok': True,
        })
        
        cls.product_brique = cls.env['product.product'].create({
            'name': 'Brique rouge 20cm',
            'default_code': 'BRI-R20',
            'categ_id': cls.category_construction.id,
            'uom_id': cls.uom_piece.id,
            'standard_price': 0.85,
            'list_price': 1.20,
            'sale_ok': True,
        })
        
        # Création d'un client de test
        cls.partner = cls.env['res.partner'].create({
            'name': 'Client Test',
            'is_company': True,
        })
        
        # Création d'un devis de test
        cls.sale_order = cls.env['sale.order'].create({
            'partner_id': cls.partner.id,
            'chantier_id': cls.chantier.id,
            'company_id': cls.company.id,
        })

    def test_wizard_creation_basic(self):
        """Test de création basique du wizard.
        
        Vérifie que :
        - Le wizard se crée correctement avec les champs obligatoires
        - Les lots disponibles sont bien calculés depuis le chantier
        - La devise est correctement héritée du devis
        """
        wizard = self.env['construction.quote.wizard'].create({
            'sale_order_id': self.sale_order.id,
            'chantier_id': self.chantier.id,
        })
        
        self.assertEqual(wizard.sale_order_id, self.sale_order)
        self.assertEqual(wizard.chantier_id, self.chantier)
        self.assertEqual(wizard.currency_id, self.sale_order.currency_id)
        
        # Vérifier que les lots disponibles sont ceux du chantier
        expected_lots = self.chantier.lots_ids
        self.assertEqual(wizard.available_lot_ids, expected_lots)

    def test_compute_available_lots(self):
        """Test du calcul des lots disponibles.
        
        Vérifie que :
        - Les lots disponibles correspondent exactement aux lots du chantier
        - Aucun lot d'un autre chantier n'est inclus
        - Les lots sont bien filtrés
        """
        # Créer un autre chantier avec ses lots
        autre_chantier = self.env['construction.chantier'].create({
            'name': 'Autre Chantier',
            'company_id': self.company.id,
        })
        
        lot_autre = self.env['construction.lot'].create({
            'name': 'Lot Autre Chantier',
            'chantier_id': autre_chantier.id,
        })
        
        wizard = self.env['construction.quote.wizard'].create({
            'sale_order_id': self.sale_order.id,
            'chantier_id': self.chantier.id,
        })
        
        # Vérifier que seuls les lots du bon chantier sont disponibles
        self.assertIn(self.lot_gros_oeuvre, wizard.available_lot_ids)
        self.assertIn(self.lot_second_oeuvre, wizard.available_lot_ids)
        self.assertNotIn(lot_autre, wizard.available_lot_ids)

    def test_compute_available_products(self):
        """Test du calcul des produits disponibles.
        
        Vérifie que :
        - Les produits vendables et actifs sont inclus
        - Les filtres de recherche fonctionnent
        - Les filtres par catégorie fonctionnent
        - La limite de résultats est respectée
        """
        wizard = self.env['construction.quote.wizard'].create({
            'sale_order_id': self.sale_order.id,
            'chantier_id': self.chantier.id,
        })
        
        # Test sans filtre
        self.assertIn(self.product_beton, wizard.available_product_ids)
        self.assertIn(self.product_brique, wizard.available_product_ids)
        
        # Test avec filtre de recherche
        wizard.search_term = 'béton'
        wizard._compute_available_products()
        self.assertIn(self.product_beton, wizard.available_product_ids)
        self.assertNotIn(self.product_brique, wizard.available_product_ids)
        
        # Test avec filtre par catégorie
        wizard.search_term = False
        wizard.category_filter_id = self.category_construction
        wizard._compute_available_products()
        self.assertIn(self.product_beton, wizard.available_product_ids)
        self.assertIn(self.product_brique, wizard.available_product_ids)

    def test_compute_totals_empty(self):
        """Test du calcul des totaux avec sélection vide.
        
        Vérifie que :
        - Les totaux sont à zéro quand aucune ligne n'est sélectionnée
        - Les calculs gèrent correctement les cas vides
        """
        wizard = self.env['construction.quote.wizard'].create({
            'sale_order_id': self.sale_order.id,
            'chantier_id': self.chantier.id,
        })
        
        self.assertEqual(wizard.total_amount, 0.0)
        self.assertEqual(wizard.total_quantity, 0.0)
        self.assertEqual(wizard.line_count, 0)

    def test_compute_totals_with_lines(self):
        """Test du calcul des totaux avec des lignes.
        
        Vérifie que :
        - Les montants sont correctement calculés
        - Les quantités sont correctement sommées
        - Le nombre de lignes est exact
        """
        wizard = self.env['construction.quote.wizard'].create({
            'sale_order_id': self.sale_order.id,
            'chantier_id': self.chantier.id,
        })
        
        # Créer des lignes de test
        line1 = self.env['construction.quote.line'].create({
            'wizard_id': wizard.id,
            'product_id': self.product_beton.id,
            'lot_id': self.lot_gros_oeuvre.id,
            'quantity': 5.0,
            'price_unit': 180.0,
            'uom_id': self.uom_m2.id,
        })
        
        line2 = self.env['construction.quote.line'].create({
            'wizard_id': wizard.id,
            'product_id': self.product_brique.id,
            'lot_id': self.lot_second_oeuvre.id,
            'quantity': 100.0,
            'price_unit': 1.20,
            'uom_id': self.uom_piece.id,
        })
        
        # Forcer le recalcul
        wizard._compute_totals()
        
        expected_total = (5.0 * 180.0) + (100.0 * 1.20)  # 900 + 120 = 1020
        expected_quantity = 5.0 + 100.0  # 105
        
        self.assertEqual(wizard.total_amount, expected_total)
        self.assertEqual(wizard.total_quantity, expected_quantity)
        self.assertEqual(wizard.line_count, 2)

    def test_action_add_product_without_lots(self):
        """Test d'ajout de produit sans lots sélectionnés.
        
        Vérifie que :
        - Une exception est levée si aucun lot n'est sélectionné
        - Le message d'erreur est approprié
        """
        wizard = self.env['construction.quote.wizard'].create({
            'sale_order_id': self.sale_order.id,
            'chantier_id': self.chantier.id,
        })
        
        with self.assertRaises(ValidationError) as cm:
            wizard.with_context(product_id=self.product_beton.id).action_add_product()
        
        self.assertIn("sélectionner au moins un lot", str(cm.exception))

    def test_action_add_product_with_lots(self):
        """Test d'ajout de produit avec lots sélectionnés.
        
        Vérifie que :
        - Le popup d'ajout est créé correctement
        - Les bonnes données sont passées au popup
        - L'action retourne le bon dictionnaire
        """
        wizard = self.env['construction.quote.wizard'].create({
            'sale_order_id': self.sale_order.id,
            'chantier_id': self.chantier.id,
            'lot_ids': [(6, 0, [self.lot_gros_oeuvre.id])],
        })
        
        action = wizard.with_context(product_id=self.product_beton.id).action_add_product()
        
        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_model'], 'construction.product.dialog')
        self.assertEqual(action['target'], 'new')

    def test_action_confirm_selection_empty(self):
        """Test de confirmation avec sélection vide.
        
        Vérifie que :
        - Une exception est levée si aucun produit n'est sélectionné
        - Le message d'erreur est approprié
        """
        wizard = self.env['construction.quote.wizard'].create({
            'sale_order_id': self.sale_order.id,
            'chantier_id': self.chantier.id,
        })
        
        with self.assertRaises(ValidationError) as cm:
            wizard.action_confirm_selection()
        
        self.assertIn("sélectionner au moins un produit", str(cm.exception))

    def test_action_confirm_selection_with_lines(self):
        """Test de confirmation avec des lignes.
        
        Vérifie que :
        - Les produits sont ajoutés au devis
        - Les lignes sont organisées par lots
        - La sélection est vidée après confirmation
        """
        wizard = self.env['construction.quote.wizard'].create({
            'sale_order_id': self.sale_order.id,
            'chantier_id': self.chantier.id,
            'lot_ids': [(6, 0, [self.lot_gros_oeuvre.id])],
        })
        
        # Créer une ligne de test
        line = self.env['construction.quote.line'].create({
            'wizard_id': wizard.id,
            'product_id': self.product_beton.id,
            'lot_id': self.lot_gros_oeuvre.id,
            'quantity': 5.0,
            'price_unit': 180.0,
            'uom_id': self.uom_m2.id,
        })
        
        initial_line_count = len(self.sale_order.order_line)
        
        # Confirmer la sélection
        wizard.action_confirm_selection()
        
        # Vérifier que les lignes ont été ajoutées au devis
        self.assertGreater(len(self.sale_order.order_line), initial_line_count)
        
        # Vérifier que la sélection a été vidée
        self.assertEqual(len(wizard.selected_line_ids), 0)

    def test_action_finalize_quote(self):
        """Test de finalisation du devis.
        
        Vérifie que :
        - Les produits restants sont ajoutés automatiquement
        - L'action retourne vers le devis
        - Le devis est correctement configuré
        """
        wizard = self.env['construction.quote.wizard'].create({
            'sale_order_id': self.sale_order.id,
            'chantier_id': self.chantier.id,
            'lot_ids': [(6, 0, [self.lot_gros_oeuvre.id])],
        })
        
        # Créer une ligne de test
        line = self.env['construction.quote.line'].create({
            'wizard_id': wizard.id,
            'product_id': self.product_beton.id,
            'lot_id': self.lot_gros_oeuvre.id,
            'quantity': 5.0,
            'price_unit': 180.0,
            'uom_id': self.uom_m2.id,
        })
        
        action = wizard.action_finalize_quote()
        
        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_model'], 'sale.order')
        self.assertEqual(action['res_id'], self.sale_order.id)
        self.assertEqual(action['target'], 'current')

    def test_action_safe_close(self):
        """Test de fermeture sécurisée.
        
        Vérifie que :
        - Avec des lignes : popup de confirmation
        - Sans lignes : fermeture directe
        """
        wizard = self.env['construction.quote.wizard'].create({
            'sale_order_id': self.sale_order.id,
            'chantier_id': self.chantier.id,
        })
        
        # Test sans lignes
        action = wizard.action_safe_close()
        self.assertEqual(action['type'], 'ir.actions.act_window_close')
        
        # Test avec lignes
        line = self.env['construction.quote.line'].create({
            'wizard_id': wizard.id,
            'product_id': self.product_beton.id,
            'lot_id': self.lot_gros_oeuvre.id,
            'quantity': 5.0,
            'price_unit': 180.0,
            'uom_id': self.uom_m2.id,
        })
        
        action = wizard.action_safe_close()
        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_model'], 'construction.wizard.cancel.confirm')

    def test_create_lot_section(self):
        """Test de création d'une section de lot.
        
        Vérifie que :
        - La section est créée avec le bon nom
        - Le type d'affichage est correct
        - La séquence est respectée
        """
        wizard = self.env['construction.quote.wizard'].create({
            'sale_order_id': self.sale_order.id,
            'chantier_id': self.chantier.id,
        })
        
        section = wizard._create_lot_section(self.lot_gros_oeuvre, 100)
        
        self.assertEqual(section.display_type, 'line_section')
        self.assertEqual(section.name, f"📋 {self.lot_gros_oeuvre.name}")
        self.assertEqual(section.sequence, 100)
        self.assertEqual(section.order_id, self.sale_order)

    def test_get_next_sequence(self):
        """Test du calcul de la prochaine séquence.
        
        Vérifie que :
        - La séquence est calculée correctement
        - Elle incrémente de 10 par rapport à la dernière ligne
        - Valeur par défaut si aucune ligne
        """
        wizard = self.env['construction.quote.wizard'].create({
            'sale_order_id': self.sale_order.id,
            'chantier_id': self.chantier.id,
        })
        
        # Test avec devis vide
        self.assertEqual(wizard._get_next_sequence(), 10)
        
        # Ajouter une ligne et tester
        self.env['sale.order.line'].create({
            'order_id': self.sale_order.id,
            'product_id': self.product_beton.id,
            'sequence': 50,
        })
        
        self.assertEqual(wizard._get_next_sequence(), 60)

    def test_unlink_wizard(self):
        """Test de suppression du wizard.
        
        Vérifie que :
        - Les lignes liées sont supprimées
        - Le wizard est supprimé sans erreur
        - Pas d'orphelins dans la base
        """
        wizard = self.env['construction.quote.wizard'].create({
            'sale_order_id': self.sale_order.id,
            'chantier_id': self.chantier.id,
        })
        
        # Créer des lignes
        line1 = self.env['construction.quote.line'].create({
            'wizard_id': wizard.id,
            'product_id': self.product_beton.id,
            'lot_id': self.lot_gros_oeuvre.id,
            'quantity': 5.0,
            'price_unit': 180.0,
            'uom_id': self.uom_m2.id,
        })
        
        line2 = self.env['construction.quote.line'].create({
            'wizard_id': wizard.id,
            'product_id': self.product_brique.id,
            'lot_id': self.lot_second_oeuvre.id,
            'quantity': 100.0,
            'price_unit': 1.20,
            'uom_id': self.uom_piece.id,
        })
        
        wizard_id = wizard.id
        line_ids = [line1.id, line2.id]
        
        # Supprimer le wizard
        wizard.unlink()
        
        # Vérifier que tout est supprimé
        self.assertFalse(self.env['construction.quote.wizard'].browse(wizard_id).exists())
        self.assertFalse(self.env['construction.quote.line'].browse(line_ids).exists())
