# -*- coding: utf-8 -*-
"""
AAA Test Suite: construction_invoice — AccountMove Commission
==============================================================
Couvre account_move.py (override action_post + _generate_business_provider_commission).

Pattern : Arrange -> Act -> Assert (AAA)
Author   : BLG Groupe
Version  : 1.0
"""
from odoo.tests.common import TransactionCase, tagged
from odoo import fields


@tagged('post_install', '-at_install')
class TestAccountMoveCommission(TransactionCase):
    """Tests de couverture pour la génération de commissions apporteur d'affaires."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.client = cls.env['res.partner'].create({
            'name': 'Client Commission',
            'is_company': True,
        })
        cls.provider = cls.env['res.partner'].create({
            'name': 'Apporteur Commission',
            'is_company': True,
        })

    def _chantier(self, with_provider=True, commission_type='percentage',
                  commission_value=10.0, total_cost=10000.0):
        """Helper : crée un chantier avec ou sans apporteur d'affaires."""
        vals = {
            'name': 'Chantier Commission',
            'client': self.client.id,
            'total_cost': total_cost,
            'commission_type': commission_type,
            'commission_value': commission_value,
        }
        if with_provider:
            vals['business_provider_id'] = self.provider.id
        return self.env['construction.chantier'].create(vals)

    def _invoice(self, chantier=None, amount=1000.0, move_type='out_invoice'):
        """Helper : crée une facture client (ou avoir) liée optionnellement à un chantier."""
        vals = {
            'move_type': move_type,
            'partner_id': self.client.id,
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': [(0, 0, {
                'name': 'Ligne test',
                'quantity': 1,
                'price_unit': amount,
                'tax_ids': [(6, 0, [])],
            })],
        }
        if chantier:
            vals['chantier_id'] = chantier.id
        return self.env['account.move'].create(vals)

    def _count_vendor_bills(self):
        """Retourne le nombre de vendor bills (in_invoice) liés au provider."""
        return self.env['account.move'].search_count([
            ('partner_id', '=', self.provider.id),
            ('move_type', '=', 'in_invoice'),
        ])

    def _count_vendor_refunds(self):
        """Retourne le nombre de vendor refunds (in_refund) liés au provider."""
        return self.env['account.move'].search_count([
            ('partner_id', '=', self.provider.id),
            ('move_type', '=', 'in_refund'),
        ])

    # ========================= test 7 =========================

    def test_commission_not_created_if_no_provider(self):
        """AAA: pas de vendor bill si business_provider_id est vide sur le chantier."""
        # Arrange
        chantier = self._chantier(with_provider=False)
        invoice = self._invoice(chantier=chantier, amount=1000.0)
        before = self._count_vendor_bills()

        # Act
        invoice.action_post()

        # Assert
        after = self._count_vendor_bills()
        self.assertEqual(
            before, after,
            "Aucune commission ne doit etre creee si business_provider_id est absent"
        )

    # ========================= test 8 =========================

    def test_commission_not_created_if_no_chantier(self):
        """AAA: pas de vendor bill si chantier_id est vide sur la facture."""
        # Arrange
        invoice = self._invoice(chantier=None, amount=1000.0)
        before = self._count_vendor_bills()

        # Act
        invoice.action_post()

        # Assert
        after = self._count_vendor_bills()
        self.assertEqual(
            before, after,
            "Aucune commission ne doit etre creee si la facture n'est pas liee a un chantier"
        )

    # ========================= test 9 =========================

    def test_fixed_commission_zero_value_no_bill(self):
        """AAA: commission=0 sur type fixed -> aucun vendor bill cree."""
        # Arrange — commission_value=0 donc commission_amount=0 -> guard `if <= 0: return`
        chantier = self._chantier(
            commission_type='fixed',
            commission_value=0.0,
            total_cost=10000.0,
        )
        invoice = self._invoice(chantier=chantier, amount=5000.0)
        before = self._count_vendor_bills()

        # Act
        invoice.action_post()

        # Assert
        after = self._count_vendor_bills()
        self.assertEqual(
            before, after,
            "Une commission fixe a 0 ne doit generer aucun vendor bill"
        )

    # ========================= test 10 =========================

    def test_commission_percentage_creates_vendor_bill(self):
        """AAA: commission 10% sur invoice 1000 EUR -> vendor bill de 100 EUR."""
        # Arrange
        chantier = self._chantier(
            commission_type='percentage',
            commission_value=10.0,
        )
        invoice = self._invoice(chantier=chantier, amount=1000.0)

        # Act
        invoice.action_post()

        # Assert
        commission_bill = self.env['account.move'].search([
            ('partner_id', '=', self.provider.id),
            ('move_type', '=', 'in_invoice'),
            ('invoice_origin', 'ilike', invoice.name),
        ])
        self.assertTrue(
            commission_bill,
            "Un vendor bill doit etre cree pour l'apporteur d'affaires"
        )
        self.assertAlmostEqual(
            commission_bill.amount_total, 100.0, places=2,
            msg="10% de 1000 EUR = 100 EUR de commission"
        )

    # ========================= test 11 =========================

    def test_commission_refund_creates_in_refund(self):
        """AAA: un credit note (out_refund) genere un in_refund pour le provider."""
        # Arrange
        chantier = self._chantier(
            commission_type='percentage',
            commission_value=10.0,
        )
        refund = self.env['account.move'].create({
            'move_type': 'out_refund',
            'partner_id': self.client.id,
            'invoice_date': fields.Date.today(),
            'chantier_id': chantier.id,
            'invoice_line_ids': [(0, 0, {
                'name': 'Avoir test',
                'quantity': 1,
                'price_unit': 1000.0,
                'tax_ids': [(6, 0, [])],
            })],
        })
        before = self._count_vendor_refunds()

        # Act
        refund.action_post()

        # Assert
        after = self._count_vendor_refunds()
        self.assertGreater(
            after, before,
            "Un avoir client doit generer un in_refund pour l'apporteur d'affaires"
        )
        commission_refund = self.env['account.move'].search([
            ('partner_id', '=', self.provider.id),
            ('move_type', '=', 'in_refund'),
            ('invoice_origin', 'ilike', refund.name),
        ])
        self.assertTrue(commission_refund, "Le in_refund doit etre lie a l'avoir client")
        self.assertAlmostEqual(
            commission_refund.amount_total, 100.0, places=2,
            msg="10% de 1000 EUR = 100 EUR de commission en avoir"
        )
