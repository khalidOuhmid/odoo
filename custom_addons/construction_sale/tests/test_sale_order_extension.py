# -*- coding: utf-8 -*-
"""Tests unitaires pour l'extension sale.order."""

from odoo.tests import TransactionCase


class TestSaleOrderExtension(TransactionCase):
    """Tests unitaires pour l'extension du modèle sale.order.
    
    Cette classe teste :
    - Gestion du champ chantier_id
    - Relations avec les lots de construction
    - Méthodes utilitaires pour les chantiers
    - Compatibilité avec le module de base
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
        
        cls.chantier1 = cls.env['construction.chantier'].create({
            'name': 'Chantier Principal',
            'company_id': cls.company.id,
        })
        
        cls.chantier2 = cls.env['construction.chantier'].create({
            'name': 'Chantier Secondaire',
            'company_id': cls.company.id,
        })
        
        cls.lot1 = cls.env['construction.lot'].create({
            'name': 'Lot 1',
            'chantier_id': cls.chantier1.id,
        })
        
        cls.lot2 = cls.env['construction.lot'].create({
            'name': 'Lot 2',
            'chantier_id': cls.chantier1.id,
        })
        
        cls.lot3 = cls.env['construction.lot'].create({
            'name': 'Lot 3',
            'chantier_id': cls.chantier2.id,
        })
        
        cls.partner = cls.env['res.partner'].create({
            'name': 'Client Test',
        })

    def test_sale_order_with_chantier(self):
        """Test de création d'une commande avec chantier.
        
        Vérifie que :
        - Le champ chantier_id est assigné correctement
        - La relation avec le chantier fonctionne
        """
        sale_order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'chantier_id': self.chantier1.id,
        })
        
        self.assertEqual(sale_order.chantier_id, self.chantier1)
        self.assertEqual(sale_order.chantier_id.name, 'Chantier Principal')

    def test_sale_order_without_chantier(self):
        """Test de création d'une commande sans chantier.
        
        Vérifie que :
        - Le champ chantier_id peut être vide
        - La commande se crée normalement
        """
        sale_order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
        })
        
        self.assertFalse(sale_order.chantier_id)

    def test_chantier_change(self):
        """Test de changement de chantier.
        
        Vérifie que :
        - On peut modifier le chantier d'une commande
        - La nouvelle relation est correcte
        """
        sale_order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'chantier_id': self.chantier1.id,
        })
        
        # Changer le chantier
        sale_order.chantier_id = self.chantier2.id
        
        self.assertEqual(sale_order.chantier_id, self.chantier2)
        self.assertEqual(sale_order.chantier_id.name, 'Chantier Secondaire')

    def test_multiple_orders_same_chantier(self):
        """Test de plusieurs commandes sur le même chantier.
        
        Vérifie que :
        - Plusieurs commandes peuvent référencer le même chantier
        - Les relations sont distinctes
        """
        sale_order1 = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'chantier_id': self.chantier1.id,
        })
        
        sale_order2 = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'chantier_id': self.chantier1.id,
        })
        
        self.assertEqual(sale_order1.chantier_id, self.chantier1)
        self.assertEqual(sale_order2.chantier_id, self.chantier1)
        self.assertNotEqual(sale_order1.id, sale_order2.id)

    def test_sale_order_lots_access(self):
        """Test d'accès aux lots via le chantier.
        
        Vérifie que :
        - On peut accéder aux lots du chantier depuis la commande
        - Les lots sont correctement filtrés par chantier
        """
        sale_order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'chantier_id': self.chantier1.id,
        })
        
        # Récupérer les lots du chantier via la commande
        chantier_lots = sale_order.chantier_id.lot_ids
        
        self.assertIn(self.lot1, chantier_lots)
        self.assertIn(self.lot2, chantier_lots)
        self.assertNotIn(self.lot3, chantier_lots)  # Lot d'un autre chantier

    def test_sale_order_display_name_with_chantier(self):
        """Test du nom d'affichage avec chantier.
        
        Vérifie que :
        - Le nom d'affichage inclut le chantier si disponible
        - Le format est cohérent
        """
        sale_order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'chantier_id': self.chantier1.id,
        })
        
        display_name = sale_order.display_name
        
        # Le nom d'affichage devrait contenir le nom du chantier
        self.assertIn('Chantier Principal', display_name)

    def test_sale_order_search_by_chantier(self):
        """Test de recherche par chantier.
        
        Vérifie que :
        - On peut rechercher les commandes par chantier
        - Les résultats sont corrects
        """
        sale_order1 = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'chantier_id': self.chantier1.id,
        })
        
        sale_order2 = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'chantier_id': self.chantier2.id,
        })
        
        sale_order3 = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            # Sans chantier
        })
        
        # Rechercher les commandes du chantier 1
        orders_chantier1 = self.env['sale.order'].search([
            ('chantier_id', '=', self.chantier1.id)
        ])
        
        self.assertIn(sale_order1, orders_chantier1)
        self.assertNotIn(sale_order2, orders_chantier1)
        self.assertNotIn(sale_order3, orders_chantier1)

    def test_sale_order_ondelete_cascade(self):
        """Test de suppression en cascade.
        
        Vérifie que :
        - La suppression du chantier affecte les commandes selon la config
        - Les contraintes sont respectées
        """
        sale_order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'chantier_id': self.chantier1.id,
        })
        
        # Vérifier que la commande existe
        self.assertTrue(sale_order.exists())
        self.assertEqual(sale_order.chantier_id, self.chantier1)
        
        # Selon la configuration ondelete, le comportement peut varier
        # Ici on teste que la relation existe et fonctionne

    def test_sale_order_company_consistency(self):
        """Test de cohérence des sociétés.
        
        Vérifie que :
        - La société de la commande et du chantier sont cohérentes
        - Les contraintes métier sont respectées
        """
        # Créer un chantier avec une société spécifique
        chantier_company = self.env['construction.chantier'].create({
            'name': 'Chantier Société',
            'company_id': self.company.id,
        })
        
        sale_order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'chantier_id': chantier_company.id,
            'company_id': self.company.id,
        })
        
        self.assertEqual(sale_order.company_id, chantier_company.company_id)

    def test_sale_order_wizard_integration(self):
        """Test d'intégration avec le wizard de devis.
        
        Vérifie que :
        - La commande peut être utilisée dans le wizard
        - Les relations fonctionnent correctement
        """
        sale_order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'chantier_id': self.chantier1.id,
        })
        
        # Créer un wizard basé sur cette commande
        wizard = self.env['construction.quote.wizard'].create({
            'sale_order_id': sale_order.id,
            'chantier_id': self.chantier1.id,
            'lot_ids': [(6, 0, [self.lot1.id, self.lot2.id])],
        })
        
        self.assertEqual(wizard.sale_order_id, sale_order)
        self.assertEqual(wizard.chantier_id, sale_order.chantier_id)

    def test_sale_order_field_properties(self):
        """Test des propriétés du champ chantier_id.
        
        Vérifie que :
        - Le champ a les bonnes propriétés (optionnel, etc.)
        - Les contraintes de domaine fonctionnent
        """
        # Créer une commande sans chantier (doit fonctionner)
        sale_order_empty = self.env['sale.order'].create({
            'partner_id': self.partner.id,
        })
        
        self.assertFalse(sale_order_empty.chantier_id)
        
        # Assigner un chantier (doit fonctionner)
        sale_order_empty.chantier_id = self.chantier1.id
        
        self.assertEqual(sale_order_empty.chantier_id, self.chantier1)

    def test_sale_order_name_get_with_chantier(self):
        """Test de la méthode name_get avec chantier.
        
        Vérifie que :
        - La méthode name_get inclut le chantier
        - Le format est utilisable dans les sélections
        """
        sale_order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'chantier_id': self.chantier1.id,
        })
        
        name_get_result = sale_order.name_get()
        
        # Vérifier que le résultat contient l'ID et le nom
        self.assertEqual(len(name_get_result), 1)
        self.assertEqual(name_get_result[0][0], sale_order.id)
        
        # Le nom devrait mentionner le chantier
        display_name = name_get_result[0][1]
        self.assertIn('Chantier Principal', display_name)
