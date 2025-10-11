# -*- coding: utf-8 -*-
"""Tests unitaires pour ProductCreator."""

from odoo.tests import TransactionCase
from odoo.exceptions import ValidationError


class TestProductCreator(TransactionCase):
    """Tests unitaires pour le créateur de produit avec auto-assignation.
    
    Cette classe teste :
    - Création de nouveaux produits
    - Auto-assignation aux lots du chantier
    - Validation des données produit
    - Retour vers le wizard parent
    - Gestion des erreurs
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
        
        cls.lot1 = cls.env['construction.lot'].create({
            'name': 'Lot 1',
            'chantier_id': cls.chantier.id,
        })
        
        cls.lot2 = cls.env['construction.lot'].create({
            'name': 'Lot 2',
            'chantier_id': cls.chantier.id,
        })
        
        cls.lot3 = cls.env['construction.lot'].create({
            'name': 'Lot 3',
            'chantier_id': cls.chantier.id,
        })
        
        cls.uom_m2 = cls.env['uom.uom'].create({
            'name': 'm²',
            'category_id': cls.env.ref('uom.product_uom_categ_area').id,
            'uom_type': 'reference',
            'factor': 1.0,
        })
        
        cls.uom_piece = cls.env.ref('uom.product_uom_unit')
        
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
            'lot_ids': [(6, 0, [cls.lot1.id, cls.lot2.id, cls.lot3.id])],
        })

    def test_product_creator_creation(self):
        """Test de création du ProductCreator.
        
        Vérifie que :
        - Le créateur se crée avec les bonnes valeurs
        - Le wizard parent est lié correctement
        """
        creator = self.env['product.creator'].create({
            'wizard_id': self.wizard.id,
            'name': 'Nouveau Produit',
            'default_code': 'NP-001',
            'standard_price': 50.0,
            'uom_id': self.uom_m2.id,
        })
        
        self.assertEqual(creator.wizard_id, self.wizard)
        self.assertEqual(creator.name, 'Nouveau Produit')
        self.assertEqual(creator.default_code, 'NP-001')
        self.assertEqual(creator.standard_price, 50.0)
        self.assertEqual(creator.uom_id, self.uom_m2)

    def test_action_create_product_success(self):
        """Test de création réussie d'un produit.
        
        Vérifie que :
        - Le produit est créé avec les bonnes données
        - Il est auto-assigné à tous les lots du wizard
        - L'action retourne vers le wizard
        """
        creator = self.env['product.creator'].create({
            'wizard_id': self.wizard.id,
            'name': 'Produit Auto-Assigné',
            'default_code': 'PAA-001',
            'standard_price': 75.0,
            'uom_id': self.uom_m2.id,
        })
        
        # Compter les produits avant création
        initial_product_count = self.env['product.product'].search_count([])
        initial_line_count = len(self.wizard.quote_line_ids)
        
        action = creator.action_create_product()
        
        # Vérifier qu'un nouveau produit a été créé
        final_product_count = self.env['product.product'].search_count([])
        self.assertEqual(final_product_count, initial_product_count + 1)
        
        # Trouver le nouveau produit
        new_product = self.env['product.product'].search([
            ('default_code', '=', 'PAA-001')
        ], limit=1)
        
        self.assertTrue(new_product.exists())
        self.assertEqual(new_product.name, 'Produit Auto-Assigné')
        self.assertEqual(new_product.standard_price, 75.0)
        self.assertEqual(new_product.uom_id, self.uom_m2)
        
        # Vérifier l'auto-assignation aux lots
        final_line_count = len(self.wizard.quote_line_ids)
        self.assertEqual(final_line_count, initial_line_count + 3)  # 3 lots
        
        # Vérifier que chaque lot a une ligne avec le nouveau produit
        for lot in [self.lot1, self.lot2, self.lot3]:
            line = self.wizard.quote_line_ids.filtered(
                lambda l: l.product_id == new_product and l.lot_id == lot
            )
            self.assertTrue(line.exists())
            self.assertEqual(line.quantity, 1.0)
            self.assertEqual(line.price_unit, 75.0)
            self.assertEqual(line.uom_id, self.uom_m2)
        
        # Vérifier le retour d'action
        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_model'], 'construction.quote.wizard')

    def test_action_create_product_no_name(self):
        """Test de création avec nom manquant.
        
        Vérifie que :
        - Une exception est levée si le nom est vide
        - Aucun produit n'est créé
        """
        creator = self.env['product.creator'].create({
            'wizard_id': self.wizard.id,
            'name': '',  # Nom vide
            'default_code': 'NP-EMPTY',
            'standard_price': 50.0,
            'uom_id': self.uom_m2.id,
        })
        
        initial_product_count = self.env['product.product'].search_count([])
        
        with self.assertRaises(ValidationError) as cm:
            creator.action_create_product()
        
        self.assertIn("nom du produit", str(cm.exception))
        
        # Vérifier qu'aucun produit n'a été créé
        final_product_count = self.env['product.product'].search_count([])
        self.assertEqual(final_product_count, initial_product_count)

    def test_action_create_product_no_uom(self):
        """Test de création sans unité de mesure.
        
        Vérifie que :
        - Une exception est levée si pas d'unité
        - Aucun produit n'est créé
        """
        creator = self.env['product.creator'].create({
            'wizard_id': self.wizard.id,
            'name': 'Produit Sans UoM',
            'default_code': 'PSU-001',
            'standard_price': 50.0,
            'uom_id': False,  # Pas d'unité
        })
        
        initial_product_count = self.env['product.product'].search_count([])
        
        with self.assertRaises(ValidationError) as cm:
            creator.action_create_product()
        
        self.assertIn("unité de mesure", str(cm.exception))
        
        # Vérifier qu'aucun produit n'a été créé
        final_product_count = self.env['product.product'].search_count([])
        self.assertEqual(final_product_count, initial_product_count)

    def test_action_create_product_negative_price(self):
        """Test de création avec prix négatif.
        
        Vérifie que :
        - Une exception est levée pour prix < 0
        - Aucun produit n'est créé
        """
        creator = self.env['product.creator'].create({
            'wizard_id': self.wizard.id,
            'name': 'Produit Prix Négatif',
            'default_code': 'PPN-001',
            'standard_price': -25.0,  # Prix négatif
            'uom_id': self.uom_m2.id,
        })
        
        initial_product_count = self.env['product.product'].search_count([])
        
        with self.assertRaises(ValidationError) as cm:
            creator.action_create_product()
        
        self.assertIn("prix doit être positif", str(cm.exception))
        
        # Vérifier qu'aucun produit n'a été créé
        final_product_count = self.env['product.product'].search_count([])
        self.assertEqual(final_product_count, initial_product_count)

    def test_action_create_product_duplicate_code(self):
        """Test de création avec code existant.
        
        Vérifie que :
        - Une exception est levée pour code dupliqué
        - Aucun nouveau produit n'est créé
        """
        # Créer un produit existant
        existing_product = self.env['product.product'].create({
            'name': 'Produit Existant',
            'default_code': 'EXIST-001',
            'uom_id': self.uom_piece.id,
        })
        
        creator = self.env['product.creator'].create({
            'wizard_id': self.wizard.id,
            'name': 'Nouveau Produit',
            'default_code': 'EXIST-001',  # Code déjà utilisé
            'standard_price': 50.0,
            'uom_id': self.uom_m2.id,
        })
        
        initial_product_count = self.env['product.product'].search_count([])
        
        with self.assertRaises(ValidationError) as cm:
            creator.action_create_product()
        
        self.assertIn("code déjà utilisé", str(cm.exception))
        
        # Vérifier qu'aucun nouveau produit n'a été créé
        final_product_count = self.env['product.product'].search_count([])
        self.assertEqual(final_product_count, initial_product_count)

    def test_action_cancel(self):
        """Test d'annulation de la création.
        
        Vérifie que :
        - L'action retourne vers le wizard
        - Aucun produit n'est créé
        """
        creator = self.env['product.creator'].create({
            'wizard_id': self.wizard.id,
            'name': 'Produit Annulé',
            'default_code': 'PA-001',
            'standard_price': 50.0,
            'uom_id': self.uom_m2.id,
        })
        
        initial_product_count = self.env['product.product'].search_count([])
        
        action = creator.action_cancel()
        
        # Vérifier qu'aucun produit n'a été créé
        final_product_count = self.env['product.product'].search_count([])
        self.assertEqual(final_product_count, initial_product_count)
        
        # Vérifier le retour d'action
        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_model'], 'construction.quote.wizard')

    def test_auto_assign_empty_wizard_lots(self):
        """Test d'auto-assignation avec wizard sans lots.
        
        Vérifie que :
        - Si le wizard n'a pas de lots, aucune ligne n'est créée
        - Le produit est quand même créé
        """
        # Créer un wizard sans lots
        wizard_empty = self.env['construction.quote.wizard'].create({
            'sale_order_id': self.sale_order.id,
            'chantier_id': self.chantier.id,
        })
        
        creator = self.env['product.creator'].create({
            'wizard_id': wizard_empty.id,
            'name': 'Produit Sans Lots',
            'default_code': 'PSL-001',
            'standard_price': 100.0,
            'uom_id': self.uom_piece.id,
        })
        
        initial_line_count = len(wizard_empty.quote_line_ids)
        
        action = creator.action_create_product()
        
        # Vérifier que le produit a été créé
        new_product = self.env['product.product'].search([
            ('default_code', '=', 'PSL-001')
        ], limit=1)
        self.assertTrue(new_product.exists())
        
        # Vérifier qu'aucune ligne n'a été ajoutée
        final_line_count = len(wizard_empty.quote_line_ids)
        self.assertEqual(final_line_count, initial_line_count)

    def test_auto_assign_with_different_uoms(self):
        """Test d'auto-assignation avec différentes unités.
        
        Vérifie que :
        - Le produit est créé avec la bonne unité
        - Toutes les lignes héritent de cette unité
        """
        creator = self.env['product.creator'].create({
            'wizard_id': self.wizard.id,
            'name': 'Produit Pièce',
            'default_code': 'PP-001',
            'standard_price': 25.0,
            'uom_id': self.uom_piece.id,  # Unité différente
        })
        
        action = creator.action_create_product()
        
        # Trouver le nouveau produit
        new_product = self.env['product.product'].search([
            ('default_code', '=', 'PP-001')
        ], limit=1)
        
        # Vérifier que toutes les lignes ont la bonne unité
        new_lines = self.wizard.quote_line_ids.filtered(
            lambda l: l.product_id == new_product
        )
        
        for line in new_lines:
            self.assertEqual(line.uom_id, self.uom_piece)

    def test_product_creation_with_optional_fields(self):
        """Test de création avec champs optionnels.
        
        Vérifie que :
        - Les champs optionnels sont gérés correctement
        - Le produit se crée même avec des champs vides
        """
        creator = self.env['product.creator'].create({
            'wizard_id': self.wizard.id,
            'name': 'Produit Minimal',
            'default_code': '',  # Code optionnel vide
            'standard_price': 0.0,  # Prix à zéro
            'uom_id': self.uom_piece.id,
        })
        
        action = creator.action_create_product()
        
        # Vérifier que le produit a été créé
        new_product = self.env['product.product'].search([
            ('name', '=', 'Produit Minimal')
        ], limit=1)
        
        self.assertTrue(new_product.exists())
        self.assertEqual(new_product.standard_price, 0.0)
        self.assertFalse(new_product.default_code)  # Code vide OK
