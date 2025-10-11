# -*- coding: utf-8 -*-
"""Tests unitaires pour ConstructionLineEditor."""

from odoo.tests import TransactionCase
from odoo.exceptions import ValidationError


class TestConstructionLineEditor(TransactionCase):
    """Tests unitaires pour l'éditeur de ligne de produit.
    
    Cette classe teste :
    - Création et initialisation de l'éditeur
    - Calcul des lots disponibles
    - Validation des modifications
    - Sauvegarde des changements
    - Actions d'annulation
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
        
        cls.quote_line = cls.env['construction.quote.line'].create({
            'wizard_id': cls.wizard.id,
            'product_id': cls.product.id,
            'lot_id': cls.lot1.id,
            'quantity': 5.0,
            'price_unit': 120.0,
            'uom_id': cls.uom_m2.id,
            'margin_percent': 20.0,
            'room_number': 'S01',
            'room_location': 'Salon',
            'construction_notes': 'Notes initiales',
        })

    def test_editor_creation_with_context(self):
        """Test de création de l'éditeur avec contexte.
        
        Vérifie que :
        - L'éditeur se crée avec les bonnes valeurs du contexte
        - Toutes les données de la ligne sont récupérées
        """
        context = {
            'default_quote_line_id': self.quote_line.id,
            'default_product_id': self.product.id,
            'default_quantity': self.quote_line.quantity,
            'default_price_unit': self.quote_line.price_unit,
            'default_uom_id': self.quote_line.uom_id.id,
            'default_lot_id': self.quote_line.lot_id.id,
            'default_room_number': self.quote_line.room_number,
            'default_room_location': self.quote_line.room_location,
            'default_construction_notes': self.quote_line.construction_notes,
            'default_margin_percent': self.quote_line.margin_percent,
        }
        
        editor = self.env['construction.line.editor'].with_context(context).create({
            'quote_line_id': self.quote_line.id,
            'product_id': self.product.id,
            'quantity': 5.0,
            'price_unit': 120.0,
            'uom_id': self.uom_m2.id,
            'lot_id': self.lot1.id,
        })
        
        self.assertEqual(editor.quote_line_id, self.quote_line)
        self.assertEqual(editor.product_id, self.product)
        self.assertEqual(editor.quantity, 5.0)
        self.assertEqual(editor.price_unit, 120.0)
        self.assertEqual(editor.uom_id, self.uom_m2)
        self.assertEqual(editor.lot_id, self.lot1)

    def test_compute_available_lots(self):
        """Test du calcul des lots disponibles.
        
        Vérifie que :
        - Les lots du wizard parent sont disponibles
        - Seuls ces lots sont proposés
        """
        editor = self.env['construction.line.editor'].create({
            'quote_line_id': self.quote_line.id,
            'product_id': self.product.id,
            'quantity': 5.0,
            'price_unit': 120.0,
            'uom_id': self.uom_m2.id,
            'lot_id': self.lot1.id,
        })
        
        self.assertIn(self.lot1, editor.available_lot_ids)
        self.assertIn(self.lot2, editor.available_lot_ids)
        self.assertEqual(len(editor.available_lot_ids), 2)

    def test_action_save_changes_valid(self):
        """Test de sauvegarde de modifications valides.
        
        Vérifie que :
        - Les modifications sont appliquées à la ligne originale
        - L'action retourne vers le wizard
        - Toutes les données sont mises à jour
        """
        editor = self.env['construction.line.editor'].create({
            'quote_line_id': self.quote_line.id,
            'product_id': self.product.id,
            'quantity': 10.0,  # Modification
            'price_unit': 150.0,  # Modification
            'uom_id': self.uom_piece.id,  # Modification
            'lot_id': self.lot2.id,  # Modification
            'room_number': 'S02',  # Modification
            'room_location': 'Cuisine',  # Modification
            'construction_notes': 'Notes modifiées',  # Modification
            'margin_percent': 25.0,  # Modification
        })
        
        action = editor.action_save_changes()
        
        # Vérifier les modifications dans la ligne originale
        self.quote_line.refresh()
        self.assertEqual(self.quote_line.quantity, 10.0)
        self.assertEqual(self.quote_line.price_unit, 150.0)
        self.assertEqual(self.quote_line.uom_id, self.uom_piece)
        self.assertEqual(self.quote_line.lot_id, self.lot2)
        self.assertEqual(self.quote_line.room_number, 'S02')
        self.assertEqual(self.quote_line.room_location, 'Cuisine')
        self.assertEqual(self.quote_line.construction_notes, 'Notes modifiées')
        self.assertEqual(self.quote_line.margin_percent, 25.0)
        
        # Vérifier le retour d'action
        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_model'], 'construction.quote.wizard')

    def test_action_save_changes_invalid_quantity(self):
        """Test de sauvegarde avec quantité invalide.
        
        Vérifie que :
        - Une exception est levée pour quantité <= 0
        - La ligne originale n'est pas modifiée
        """
        original_quantity = self.quote_line.quantity
        
        editor = self.env['construction.line.editor'].create({
            'quote_line_id': self.quote_line.id,
            'product_id': self.product.id,
            'quantity': -5.0,  # Quantité invalide
            'price_unit': 120.0,
            'uom_id': self.uom_m2.id,
            'lot_id': self.lot1.id,
        })
        
        with self.assertRaises(ValidationError) as cm:
            editor.action_save_changes()
        
        self.assertIn("quantité doit être positive", str(cm.exception))
        
        # Vérifier que la ligne originale n'a pas été modifiée
        self.quote_line.refresh()
        self.assertEqual(self.quote_line.quantity, original_quantity)

    def test_action_save_changes_no_lot(self):
        """Test de sauvegarde sans lot sélectionné.
        
        Vérifie que :
        - Une exception est levée si pas de lot
        - La ligne originale n'est pas modifiée
        """
        original_lot = self.quote_line.lot_id
        
        editor = self.env['construction.line.editor'].create({
            'quote_line_id': self.quote_line.id,
            'product_id': self.product.id,
            'quantity': 5.0,
            'price_unit': 120.0,
            'uom_id': self.uom_m2.id,
            'lot_id': False,  # Pas de lot
        })
        
        with self.assertRaises(ValidationError) as cm:
            editor.action_save_changes()
        
        self.assertIn("sélectionner un lot", str(cm.exception))
        
        # Vérifier que la ligne originale n'a pas été modifiée
        self.quote_line.refresh()
        self.assertEqual(self.quote_line.lot_id, original_lot)

    def test_action_save_changes_no_uom(self):
        """Test de sauvegarde sans unité de mesure.
        
        Vérifie que :
        - Une exception est levée si pas d'unité
        - La ligne originale n'est pas modifiée
        """
        original_uom = self.quote_line.uom_id
        
        editor = self.env['construction.line.editor'].create({
            'quote_line_id': self.quote_line.id,
            'product_id': self.product.id,
            'quantity': 5.0,
            'price_unit': 120.0,
            'uom_id': False,  # Pas d'unité
            'lot_id': self.lot1.id,
        })
        
        with self.assertRaises(ValidationError) as cm:
            editor.action_save_changes()
        
        self.assertIn("unité de mesure", str(cm.exception))
        
        # Vérifier que la ligne originale n'a pas été modifiée
        self.quote_line.refresh()
        self.assertEqual(self.quote_line.uom_id, original_uom)

    def test_action_cancel(self):
        """Test d'annulation des modifications.
        
        Vérifie que :
        - L'action retourne vers le wizard
        - La ligne originale n'est pas modifiée
        """
        original_quantity = self.quote_line.quantity
        original_price = self.quote_line.price_unit
        
        editor = self.env['construction.line.editor'].create({
            'quote_line_id': self.quote_line.id,
            'product_id': self.product.id,
            'quantity': 999.0,  # Modification qui ne doit pas être sauvée
            'price_unit': 999.0,  # Modification qui ne doit pas être sauvée
            'uom_id': self.uom_m2.id,
            'lot_id': self.lot1.id,
        })
        
        action = editor.action_cancel()
        
        # Vérifier que la ligne originale n'a pas été modifiée
        self.quote_line.refresh()
        self.assertEqual(self.quote_line.quantity, original_quantity)
        self.assertEqual(self.quote_line.price_unit, original_price)
        
        # Vérifier le retour d'action
        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_model'], 'construction.quote.wizard')

    def test_product_name_readonly(self):
        """Test que le nom du produit est en lecture seule.
        
        Vérifie que :
        - Le nom du produit est affiché correctement
        - Il provient bien du produit lié
        """
        editor = self.env['construction.line.editor'].create({
            'quote_line_id': self.quote_line.id,
            'product_id': self.product.id,
            'quantity': 5.0,
            'price_unit': 120.0,
            'uom_id': self.uom_m2.id,
            'lot_id': self.lot1.id,
        })
        
        self.assertEqual(editor.product_name, self.product.display_name)

    def test_compute_available_lots_empty_wizard(self):
        """Test du calcul des lots avec wizard vide.
        
        Vérifie que :
        - Si le wizard n'a pas de lots, aucun lot n'est disponible
        - Le calcul gère les cas extrêmes
        """
        # Créer un wizard sans lots
        wizard_empty = self.env['construction.quote.wizard'].create({
            'sale_order_id': self.sale_order.id,
            'chantier_id': self.chantier.id,
        })
        
        quote_line_empty = self.env['construction.quote.line'].create({
            'wizard_id': wizard_empty.id,
            'product_id': self.product.id,
            'lot_id': self.lot1.id,
            'quantity': 1.0,
            'price_unit': 100.0,
            'uom_id': self.uom_m2.id,
        })
        
        editor = self.env['construction.line.editor'].create({
            'quote_line_id': quote_line_empty.id,
            'product_id': self.product.id,
            'quantity': 1.0,
            'price_unit': 100.0,
            'uom_id': self.uom_m2.id,
            'lot_id': self.lot1.id,
        })
        
        self.assertEqual(len(editor.available_lot_ids), 0)

    def test_partial_field_modification(self):
        """Test de modification partielle des champs.
        
        Vérifie que :
        - On peut modifier seulement certains champs
        - Les autres champs restent inchangés
        """
        original_room_number = self.quote_line.room_number
        original_construction_notes = self.quote_line.construction_notes
        
        editor = self.env['construction.line.editor'].create({
            'quote_line_id': self.quote_line.id,
            'product_id': self.product.id,
            'quantity': 7.0,  # Seule modification
            'price_unit': self.quote_line.price_unit,  # Inchangé
            'uom_id': self.quote_line.uom_id.id,  # Inchangé
            'lot_id': self.quote_line.lot_id.id,  # Inchangé
            'room_number': self.quote_line.room_number,  # Inchangé
            'room_location': self.quote_line.room_location,  # Inchangé
            'construction_notes': self.quote_line.construction_notes,  # Inchangé
            'margin_percent': self.quote_line.margin_percent,  # Inchangé
        })
        
        editor.action_save_changes()
        
        # Vérifier que seule la quantité a été modifiée
        self.quote_line.refresh()
        self.assertEqual(self.quote_line.quantity, 7.0)
        self.assertEqual(self.quote_line.room_number, original_room_number)
        self.assertEqual(self.quote_line.construction_notes, original_construction_notes)
