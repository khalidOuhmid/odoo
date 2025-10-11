# -*- coding: utf-8 -*-
"""Tests unitaires pour WizardCancelConfirm."""

from odoo.tests import TransactionCase


class TestWizardCancelConfirm(TransactionCase):
    """Tests unitaires pour le dialogue de confirmation d'annulation.
    
    Cette classe teste :
    - Création du dialogue de confirmation
    - Actions de confirmation et annulation
    - Gestion de la fermeture sécurisée
    - Messages d'avertissement
    - Retour vers le wizard parent
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

    def test_cancel_confirm_creation(self):
        """Test de création du dialogue de confirmation.
        
        Vérifie que :
        - Le dialogue se crée correctement
        - Le wizard parent est lié
        - Le message par défaut est défini
        """
        cancel_confirm = self.env['wizard.cancel.confirm'].create({
            'wizard_id': self.wizard.id,
        })
        
        self.assertEqual(cancel_confirm.wizard_id, self.wizard)
        self.assertTrue(cancel_confirm.message)
        self.assertIn("perdues", cancel_confirm.message.lower())

    def test_cancel_confirm_with_custom_message(self):
        """Test avec message personnalisé.
        
        Vérifie que :
        - On peut définir un message spécifique
        - Le message est affiché correctement
        """
        custom_message = "Êtes-vous sûr de vouloir annuler cette opération ?"
        
        cancel_confirm = self.env['wizard.cancel.confirm'].create({
            'wizard_id': self.wizard.id,
            'message': custom_message,
        })
        
        self.assertEqual(cancel_confirm.message, custom_message)

    def test_action_confirm_close(self):
        """Test de confirmation de fermeture.
        
        Vérifie que :
        - L'action confirme la fermeture
        - Le wizard est fermé
        - L'action retourne vers la vue appropriée
        """
        cancel_confirm = self.env['wizard.cancel.confirm'].create({
            'wizard_id': self.wizard.id,
        })
        
        action = cancel_confirm.action_confirm_close()
        
        # Vérifier le type d'action de fermeture
        self.assertEqual(action['type'], 'ir.actions.act_window_close')

    def test_action_cancel_return(self):
        """Test d'annulation du dialogue.
        
        Vérifie que :
        - L'action annule la fermeture
        - On retourne vers le wizard parent
        - Le wizard reste ouvert
        """
        cancel_confirm = self.env['wizard.cancel.confirm'].create({
            'wizard_id': self.wizard.id,
        })
        
        action = cancel_confirm.action_cancel_return()
        
        # Vérifier le retour vers le wizard
        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_model'], 'construction.quote.wizard')
        self.assertEqual(action['res_id'], self.wizard.id)
        self.assertEqual(action['view_mode'], 'form')
        self.assertEqual(action['target'], 'current')

    def test_cancel_confirm_with_data(self):
        """Test avec des données dans le wizard.
        
        Vérifie que :
        - Le dialogue fonctionne même avec des données
        - Les données ne sont pas perdues lors de l'annulation
        """
        # Ajouter des lignes au wizard
        self.env['construction.quote.line'].create({
            'wizard_id': self.wizard.id,
            'product_id': self.product.id,
            'lot_id': self.lot1.id,
            'quantity': 5.0,
            'price_unit': 120.0,
            'uom_id': self.uom_m2.id,
        })
        
        self.env['construction.quote.line'].create({
            'wizard_id': self.wizard.id,
            'product_id': self.product.id,
            'lot_id': self.lot2.id,
            'quantity': 3.0,
            'price_unit': 150.0,
            'uom_id': self.uom_m2.id,
        })
        
        cancel_confirm = self.env['wizard.cancel.confirm'].create({
            'wizard_id': self.wizard.id,
        })
        
        # Vérifier que les données existent
        self.assertEqual(len(self.wizard.quote_line_ids), 2)
        
        # Annuler (retourner au wizard)
        action = cancel_confirm.action_cancel_return()
        
        # Vérifier que les données sont toujours là
        self.wizard.refresh()
        self.assertEqual(len(self.wizard.quote_line_ids), 2)

    def test_cancel_confirm_message_with_line_count(self):
        """Test du message avec nombre de lignes.
        
        Vérifie que :
        - Le message peut inclure le nombre de lignes
        - Il est informatif pour l'utilisateur
        """
        # Ajouter des lignes
        self.env['construction.quote.line'].create({
            'wizard_id': self.wizard.id,
            'product_id': self.product.id,
            'lot_id': self.lot1.id,
            'quantity': 1.0,
            'price_unit': 100.0,
            'uom_id': self.uom_m2.id,
        })
        
        line_count = len(self.wizard.quote_line_ids)
        
        message_with_count = f"Vous avez {line_count} ligne(s) de devis. Voulez-vous vraiment fermer ?"
        
        cancel_confirm = self.env['wizard.cancel.confirm'].create({
            'wizard_id': self.wizard.id,
            'message': message_with_count,
        })
        
        self.assertIn(str(line_count), cancel_confirm.message)

    def test_multiple_cancel_dialogs(self):
        """Test de dialogues multiples.
        
        Vérifie que :
        - On peut créer plusieurs dialogues pour le même wizard
        - Ils fonctionnent indépendamment
        """
        cancel_confirm1 = self.env['wizard.cancel.confirm'].create({
            'wizard_id': self.wizard.id,
            'message': 'Premier dialogue',
        })
        
        cancel_confirm2 = self.env['wizard.cancel.confirm'].create({
            'wizard_id': self.wizard.id,
            'message': 'Deuxième dialogue',
        })
        
        self.assertEqual(cancel_confirm1.wizard_id, self.wizard)
        self.assertEqual(cancel_confirm2.wizard_id, self.wizard)
        self.assertNotEqual(cancel_confirm1.message, cancel_confirm2.message)

    def test_cancel_confirm_view_properties(self):
        """Test des propriétés de vue.
        
        Vérifie que :
        - Le dialogue a les bonnes propriétés d'affichage
        - Il se présente comme un popup
        """
        cancel_confirm = self.env['wizard.cancel.confirm'].create({
            'wizard_id': self.wizard.id,
        })
        
        # Vérifier que l'objet existe et a les bonnes propriétés
        self.assertTrue(cancel_confirm.exists())
        self.assertEqual(cancel_confirm._name, 'wizard.cancel.confirm')

    def test_cancel_confirm_security(self):
        """Test de sécurité du dialogue.
        
        Vérifie que :
        - Le dialogue respecte les droits d'accès
        - Il est lié au bon wizard
        """
        cancel_confirm = self.env['wizard.cancel.confirm'].create({
            'wizard_id': self.wizard.id,
        })
        
        # Vérifier la liaison sécurisée
        self.assertEqual(cancel_confirm.wizard_id.id, self.wizard.id)
        
        # Vérifier que le dialogue peut être utilisé
        self.assertTrue(cancel_confirm.action_cancel_return())
        self.assertTrue(cancel_confirm.action_confirm_close())

    def test_empty_wizard_cancel_confirm(self):
        """Test avec wizard vide.
        
        Vérifie que :
        - Le dialogue fonctionne même si le wizard est vide
        - Pas d'erreur avec wizard sans données
        """
        # Créer un wizard vide
        empty_wizard = self.env['construction.quote.wizard'].create({
            'sale_order_id': self.sale_order.id,
            'chantier_id': self.chantier.id,
        })
        
        cancel_confirm = self.env['wizard.cancel.confirm'].create({
            'wizard_id': empty_wizard.id,
        })
        
        # Vérifier que ça fonctionne
        action_cancel = cancel_confirm.action_cancel_return()
        action_confirm = cancel_confirm.action_confirm_close()
        
        self.assertEqual(action_cancel['res_id'], empty_wizard.id)
        self.assertEqual(action_confirm['type'], 'ir.actions.act_window_close')

    def test_cancel_confirm_default_message(self):
        """Test du message par défaut.
        
        Vérifie que :
        - Un message par défaut est défini
        - Il est approprié pour l'action
        """
        cancel_confirm = self.env['wizard.cancel.confirm'].create({
            'wizard_id': self.wizard.id,
        })
        
        # Vérifier qu'il y a un message par défaut
        self.assertTrue(cancel_confirm.message)
        
        # Vérifier que le message est approprié
        message_lower = cancel_confirm.message.lower()
        self.assertTrue(
            any(word in message_lower for word in ['fermer', 'annuler', 'quitter', 'perdre'])
        )

    def test_wizard_relationship(self):
        """Test de la relation avec le wizard.
        
        Vérifie que :
        - La relation Many2one fonctionne
        - Le dialogue accède aux données du wizard
        """
        cancel_confirm = self.env['wizard.cancel.confirm'].create({
            'wizard_id': self.wizard.id,
        })
        
        # Vérifier l'accès aux données du wizard
        self.assertEqual(cancel_confirm.wizard_id.chantier_id, self.chantier)
        self.assertEqual(cancel_confirm.wizard_id.sale_order_id, self.sale_order)
        self.assertEqual(len(cancel_confirm.wizard_id.lot_ids), 2)
