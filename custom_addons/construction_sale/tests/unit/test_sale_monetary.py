# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError

class TestSaleMonetary(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # ARRANGE GLOBAL
        cls.backend_user = cls.env['res.users'].create({
            'name': 'Backend User',
            'login': 'backend_user',
            'groups_id': [(6, 0, [cls.env.ref('sales_team.group_sale_salesman').id])]
        })
        cls.client_a = cls.env['res.partner'].create({'name': 'Client A'})
        cls.client_b = cls.env['res.partner'].create({'name': 'Client B'})
        cls.chantier_a = cls.env['construction.chantier'].create({
            'name': 'Chantier ALPHA',
            'client': cls.client_a.id
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Béton Armé',
            'list_price': 150.00,
            'type': 'service'
        })
        cls.lot = cls.env['construction.lot'].create({
            'name': 'Gros Oeuvre',
            'chantier_id': cls.chantier_a.id
        })

    def test_chantier_partner_consistency(self):
        """ ARRANGE / ACT / ASSERT: Un devis ne peut cibler Client B si le chantier appartient à Client A. """
        # ARRANGE & ACT & ASSERT
        with self.assertRaisesRegex(ValidationError, "differs from chantier client"):
            self.env['sale.order'].create({
                'partner_id': self.client_b.id,
                'chantier_id': self.chantier_a.id
            })

    def test_negative_price_raises_error(self):
        """ ARRANGE / ACT / ASSERT: Impossible de valider une ligne de construction avec un montant négatif. """
        # ARRANGE
        order = self.env['sale.order'].create({
            'partner_id': self.client_a.id,
            'chantier_id': self.chantier_a.id
        })
        
        # ACT & ASSERT
        with self.assertRaisesRegex(ValidationError, "cannot be negative|ne peut pas être négatif|cannot be negative"):
            self.env['sale.order.line'].create({
                'order_id': order.id,
                'product_id': self.product.id,
                'lot_id': self.lot.id,
                'price_unit': -50.00
            })

    def test_price_lock_on_confirmed_order(self):
        """ ARRANGE / ACT / ASSERT: Impossible de modifier le prix d'une ligne d'un devis validé. """
        # ARRANGE
        order = self.env['sale.order'].create({
            'partner_id': self.client_a.id,
            'chantier_id': self.chantier_a.id
        })
        line = self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': self.product.id,
            'lot_id': self.lot.id,
            'price_unit': 100.00,
            'product_uom_qty': 1
        })
        order.action_confirm()

        # ACT & ASSERT
        with self.assertRaisesRegex(ValidationError, "Vous ne pouvez pas modifier le prix unitaire"):
            line.write({'price_unit': 80.00})
