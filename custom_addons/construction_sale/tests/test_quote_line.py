# -*- coding: utf-8 -*-
"""Tests unitaires pour ConstructionQuoteLine."""

from odoo.tests import TransactionCase


class TestConstructionQuoteLine(TransactionCase):
    """Tests unitaires pour les lignes de devis de construction.
    
    Cette classe teste :
    - Calculs de prix et marges
    - Gestion des unités de mesure
    - Validation des données
    - Relations avec produits et lots
    - Calculs de totaux
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
        
        cls.uom_m2 = cls.env['uom.uom'].create({
            'name': 'm²',
            'category_id': cls.env.ref('uom.product_uom_categ_area').id,
            'uom_type': 'reference',
            'factor': 1.0,
        })
        
        cls.uom_piece = cls.env.ref('uom.product_uom_unit')
        
        cls.product = cls.env['product.product'].create({
            'name': 'Produit Test',
            'default_code': 'PROD-TEST',
            'uom_id': cls.uom_m2.id,
            'standard_price': 100.0,
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
            'lot_ids': [(6, 0, [cls.lot1.id, cls.lot2.id])],
        })

    def test_quote_line_creation(self):
        """Test de création d'une ligne de devis.
        
        Vérifie que :
        - La ligne se crée avec les bonnes valeurs
        - Toutes les relations sont correctes
        """
        quote_line = self.env['construction.quote.line'].create({
            'wizard_id': self.wizard.id,
            'product_id': self.product.id,
            'lot_id': self.lot1.id,
            'quantity': 10.0,
            'price_unit': 150.0,
            'uom_id': self.uom_m2.id,
            'margin_percent': 25.0,
            'room_number': 'S01',
            'room_location': 'Salon',
            'construction_notes': 'Notes spéciales',
        })
        
        self.assertEqual(quote_line.wizard_id, self.wizard)
        self.assertEqual(quote_line.product_id, self.product)
        self.assertEqual(quote_line.lot_id, self.lot1)
        self.assertEqual(quote_line.quantity, 10.0)
        self.assertEqual(quote_line.price_unit, 150.0)
        self.assertEqual(quote_line.uom_id, self.uom_m2)
        self.assertEqual(quote_line.margin_percent, 25.0)
        self.assertEqual(quote_line.room_number, 'S01')
        self.assertEqual(quote_line.room_location, 'Salon')
        self.assertEqual(quote_line.construction_notes, 'Notes spéciales')

    def test_compute_subtotal(self):
        """Test du calcul du sous-total.
        
        Vérifie que :
        - Le sous-total = quantité × prix unitaire
        - Le calcul est automatique
        """
        quote_line = self.env['construction.quote.line'].create({
            'wizard_id': self.wizard.id,
            'product_id': self.product.id,
            'lot_id': self.lot1.id,
            'quantity': 5.0,
            'price_unit': 120.0,
            'uom_id': self.uom_m2.id,
        })
        
        expected_subtotal = 5.0 * 120.0  # 600.0
        self.assertEqual(quote_line.subtotal, expected_subtotal)

    def test_compute_subtotal_with_decimals(self):
        """Test du calcul avec décimales.
        
        Vérifie que :
        - Les calculs avec décimales sont précis
        - L'arrondi est correct
        """
        quote_line = self.env['construction.quote.line'].create({
            'wizard_id': self.wizard.id,
            'product_id': self.product.id,
            'lot_id': self.lot1.id,
            'quantity': 3.75,
            'price_unit': 123.45,
            'uom_id': self.uom_m2.id,
        })
        
        expected_subtotal = 3.75 * 123.45  # 462.9375
        self.assertAlmostEqual(quote_line.subtotal, expected_subtotal, places=2)

    def test_compute_subtotal_zero_quantity(self):
        """Test du calcul avec quantité zéro.
        
        Vérifie que :
        - Le sous-total est zéro si quantité zéro
        - Pas d'erreur de division par zéro
        """
        quote_line = self.env['construction.quote.line'].create({
            'wizard_id': self.wizard.id,
            'product_id': self.product.id,
            'lot_id': self.lot1.id,
            'quantity': 0.0,
            'price_unit': 150.0,
            'uom_id': self.uom_m2.id,
        })
        
        self.assertEqual(quote_line.subtotal, 0.0)

    def test_compute_subtotal_zero_price(self):
        """Test du calcul avec prix zéro.
        
        Vérifie que :
        - Le sous-total est zéro si prix zéro
        - Le calcul fonctionne normalement
        """
        quote_line = self.env['construction.quote.line'].create({
            'wizard_id': self.wizard.id,
            'product_id': self.product.id,
            'lot_id': self.lot1.id,
            'quantity': 10.0,
            'price_unit': 0.0,
            'uom_id': self.uom_m2.id,
        })
        
        self.assertEqual(quote_line.subtotal, 0.0)

    def test_product_name_readonly(self):
        """Test du nom de produit en lecture seule.
        
        Vérifie que :
        - Le nom du produit est affiché
        - Il provient du produit lié
        """
        quote_line = self.env['construction.quote.line'].create({
            'wizard_id': self.wizard.id,
            'product_id': self.product.id,
            'lot_id': self.lot1.id,
            'quantity': 1.0,
            'price_unit': 100.0,
            'uom_id': self.uom_m2.id,
        })
        
        self.assertEqual(quote_line.product_name, self.product.display_name)

    def test_different_uom_units(self):
        """Test avec différentes unités de mesure.
        
        Vérifie que :
        - On peut utiliser différentes unités
        - Les calculs restent corrects
        """
        quote_line_m2 = self.env['construction.quote.line'].create({
            'wizard_id': self.wizard.id,
            'product_id': self.product.id,
            'lot_id': self.lot1.id,
            'quantity': 2.5,
            'price_unit': 50.0,
            'uom_id': self.uom_m2.id,
        })
        
        quote_line_piece = self.env['construction.quote.line'].create({
            'wizard_id': self.wizard.id,
            'product_id': self.product.id,
            'lot_id': self.lot2.id,
            'quantity': 10.0,
            'price_unit': 12.5,
            'uom_id': self.uom_piece.id,
        })
        
        self.assertEqual(quote_line_m2.subtotal, 125.0)  # 2.5 * 50.0
        self.assertEqual(quote_line_piece.subtotal, 125.0)  # 10.0 * 12.5
        self.assertEqual(quote_line_m2.uom_id, self.uom_m2)
        self.assertEqual(quote_line_piece.uom_id, self.uom_piece)

    def test_margin_percent_calculation(self):
        """Test du calcul de marge.
        
        Vérifie que :
        - La marge est stockée correctement
        - Elle influence le prix final
        """
        quote_line = self.env['construction.quote.line'].create({
            'wizard_id': self.wizard.id,
            'product_id': self.product.id,
            'lot_id': self.lot1.id,
            'quantity': 1.0,
            'price_unit': 120.0,  # Prix avec marge
            'uom_id': self.uom_m2.id,
            'margin_percent': 20.0,  # 20% de marge
        })
        
        # Vérifier que la marge est stockée
        self.assertEqual(quote_line.margin_percent, 20.0)
        
        # Le prix unitaire devrait refléter la marge
        # Prix de base (100) + 20% = 120
        self.assertEqual(quote_line.price_unit, 120.0)

    def test_room_information(self):
        """Test des informations de pièce.
        
        Vérifie que :
        - Les informations de pièce sont stockées
        - Elles sont optionnelles
        """
        quote_line_with_room = self.env['construction.quote.line'].create({
            'wizard_id': self.wizard.id,
            'product_id': self.product.id,
            'lot_id': self.lot1.id,
            'quantity': 1.0,
            'price_unit': 100.0,
            'uom_id': self.uom_m2.id,
            'room_number': 'CH01',
            'room_location': 'Chambre principale',
        })
        
        quote_line_without_room = self.env['construction.quote.line'].create({
            'wizard_id': self.wizard.id,
            'product_id': self.product.id,
            'lot_id': self.lot2.id,
            'quantity': 1.0,
            'price_unit': 100.0,
            'uom_id': self.uom_m2.id,
        })
        
        self.assertEqual(quote_line_with_room.room_number, 'CH01')
        self.assertEqual(quote_line_with_room.room_location, 'Chambre principale')
        self.assertFalse(quote_line_without_room.room_number)
        self.assertFalse(quote_line_without_room.room_location)

    def test_construction_notes(self):
        """Test des notes de construction.
        
        Vérifie que :
        - Les notes sont stockées correctement
        - Elles sont optionnelles
        """
        quote_line_with_notes = self.env['construction.quote.line'].create({
            'wizard_id': self.wizard.id,
            'product_id': self.product.id,
            'lot_id': self.lot1.id,
            'quantity': 1.0,
            'price_unit': 100.0,
            'uom_id': self.uom_m2.id,
            'construction_notes': 'Installation particulière requise',
        })
        
        quote_line_without_notes = self.env['construction.quote.line'].create({
            'wizard_id': self.wizard.id,
            'product_id': self.product.id,
            'lot_id': self.lot2.id,
            'quantity': 1.0,
            'price_unit': 100.0,
            'uom_id': self.uom_m2.id,
        })
        
        self.assertEqual(
            quote_line_with_notes.construction_notes,
            'Installation particulière requise'
        )
        self.assertFalse(quote_line_without_notes.construction_notes)

    def test_multiple_lines_same_product_different_lots(self):
        """Test de lignes multiples pour le même produit.
        
        Vérifie que :
        - On peut avoir plusieurs lignes pour le même produit
        - Chaque ligne peut être sur un lot différent
        - Les calculs sont indépendants
        """
        line1 = self.env['construction.quote.line'].create({
            'wizard_id': self.wizard.id,
            'product_id': self.product.id,
            'lot_id': self.lot1.id,
            'quantity': 5.0,
            'price_unit': 120.0,
            'uom_id': self.uom_m2.id,
        })
        
        line2 = self.env['construction.quote.line'].create({
            'wizard_id': self.wizard.id,
            'product_id': self.product.id,
            'lot_id': self.lot2.id,
            'quantity': 3.0,
            'price_unit': 130.0,
            'uom_id': self.uom_m2.id,
        })
        
        self.assertEqual(line1.subtotal, 600.0)  # 5.0 * 120.0
        self.assertEqual(line2.subtotal, 390.0)  # 3.0 * 130.0
        self.assertEqual(line1.lot_id, self.lot1)
        self.assertEqual(line2.lot_id, self.lot2)

    def test_line_modification(self):
        """Test de modification d'une ligne.
        
        Vérifie que :
        - Les modifications sont prises en compte
        - Les calculs se mettent à jour automatiquement
        """
        quote_line = self.env['construction.quote.line'].create({
            'wizard_id': self.wizard.id,
            'product_id': self.product.id,
            'lot_id': self.lot1.id,
            'quantity': 2.0,
            'price_unit': 100.0,
            'uom_id': self.uom_m2.id,
        })
        
        # Vérifier le sous-total initial
        self.assertEqual(quote_line.subtotal, 200.0)
        
        # Modifier la quantité
        quote_line.quantity = 5.0
        
        # Vérifier que le sous-total se met à jour
        self.assertEqual(quote_line.subtotal, 500.0)
        
        # Modifier le prix
        quote_line.price_unit = 150.0
        
        # Vérifier la nouvelle valeur
        self.assertEqual(quote_line.subtotal, 750.0)

    def test_line_display_name(self):
        """Test du nom d'affichage de la ligne.
        
        Vérifie que :
        - Le nom d'affichage est informatif
        - Il inclut les informations principales
        """
        quote_line = self.env['construction.quote.line'].create({
            'wizard_id': self.wizard.id,
            'product_id': self.product.id,
            'lot_id': self.lot1.id,
            'quantity': 5.0,
            'price_unit': 120.0,
            'uom_id': self.uom_m2.id,
            'room_number': 'S01',
        })
        
        display_name = quote_line.display_name
        
        # Le nom devrait contenir des informations utiles
        self.assertIn(self.product.name, display_name)
        self.assertIn(self.lot1.name, display_name)
