# -*- coding: utf-8 -*-
"""
AAA Test Suite: construction_invoice — Wizards
=================================================
Couvre BillingCycleWizard et InvoiceScheduleWizard (couverture 0% avant ce fichier).

Pattern : Arrange -> Act -> Assert (AAA)
Author   : BLG Groupe
Version  : 1.0
"""
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import UserError


@tagged('post_install', '-at_install')
class TestBillingCycleWizard(TransactionCase):
    """Tests pour construction.billing.cycle.wizard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.client = cls.env['res.partner'].create({
            'name': 'Client Wizard BC',
            'is_company': True,
        })
        cls.chantier = cls.env['construction.chantier'].create({
            'name': 'Chantier Wizard BC',
            'client': cls.client.id,
            'total_cost': 12000.0,
        })

    def _make_wizard(self, chantier=None, cycle_type='standard'):
        return self.env['construction.billing.cycle.wizard'].create({
            'chantier_id': (chantier or self.chantier).id,
            'cycle_type': cycle_type,
        })

    # ========================= test 1 =========================

    def test_wizard_creates_standard_30_30_40_cycle(self):
        """AAA: le wizard crée un cycle avec 3 étapes à 30/30/40%."""
        # Arrange
        wizard = self._make_wizard(cycle_type='standard')

        # Act
        wizard.action_apply_cycle()

        # Assert
        cycle = self.chantier.billing_cycle_id
        self.assertTrue(cycle, "Le cycle doit être lié au chantier")
        steps = cycle.step_ids.sorted('sequence')
        self.assertEqual(len(steps), 3, "Le cycle standard doit avoir 3 étapes")
        percentages = steps.mapped('percentage')
        self.assertAlmostEqual(percentages[0], 30.0, places=2)
        self.assertAlmostEqual(percentages[1], 30.0, places=2)
        self.assertAlmostEqual(percentages[2], 40.0, places=2)

    # ========================= test 2 =========================

    def test_wizard_raises_if_no_chantier(self):
        """AAA: UserError si chantier_id manquant (champ required=True sur le modèle)."""
        # Arrange — le champ chantier_id est required=True donc on vérifie
        # qu'Odoo lève bien une erreur si on tente de créer le wizard sans chantier
        with self.assertRaises(Exception):
            self.env['construction.billing.cycle.wizard'].create({
                'cycle_type': 'standard',
                # chantier_id volontairement absent
            })

    # ========================= test 3 =========================

    def test_wizard_replaces_existing_draft_cycle(self):
        """AAA: le wizard remplace le cycle draft existant en créant un nouveau cycle."""
        # Arrange — créer un premier cycle sur un nouveau chantier
        chantier2 = self.env['construction.chantier'].create({
            'name': 'Chantier Replace Cycle',
            'client': self.client.id,
            'total_cost': 5000.0,
        })
        first_wizard = self._make_wizard(chantier=chantier2, cycle_type='standard')
        first_wizard.action_apply_cycle()
        first_cycle_id = chantier2.billing_cycle_id.id
        self.assertTrue(first_cycle_id, "Un premier cycle doit exister")

        # Act — relancer le wizard sur le même chantier
        second_wizard = self._make_wizard(chantier=chantier2, cycle_type='progress')
        second_wizard.action_apply_cycle()

        # Assert — un nouveau cycle est lié au chantier (le wizard ne supprime pas l'ancien
        # mais en crée un nouveau et le lie au chantier via billing_cycle_id)
        new_cycle_id = chantier2.billing_cycle_id.id
        self.assertNotEqual(
            new_cycle_id, first_cycle_id,
            "Le chantier doit pointer vers le nouveau cycle après relance du wizard"
        )


@tagged('post_install', '-at_install')
class TestInvoiceScheduleWizard(TransactionCase):
    """Tests pour construction.invoice.schedule.wizard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.client = cls.env['res.partner'].create({
            'name': 'Client Wizard IS',
            'is_company': True,
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Service Wizard',
            'type': 'service',
            'list_price': 100.0,
        })
        cls.chantier = cls.env['construction.chantier'].create({
            'name': 'Chantier Wizard IS',
            'client': cls.client.id,
            'total_cost': 20000.0,
        })
        # Cycle de facturation de référence avec lignes sumant à 100%
        cls.invoice_type = cls.env['construction.invoice_type'].create({
            'name': 'Cycle Wizard Test',
            'code': 'WIZ_TEST',
            'line_ids': [
                (0, 0, {
                    'name': 'Acompte Signature',
                    'sequence': 1,
                    'trigger_percentage': 0.0,
                    'percentage': 30.0,
                    'is_advance_payment': True,
                }),
                (0, 0, {
                    'name': 'Situation mi-chantier',
                    'sequence': 2,
                    'trigger_percentage': 50.0,
                    'percentage': 30.0,
                }),
                (0, 0, {
                    'name': 'Solde Réception',
                    'sequence': 3,
                    'trigger_percentage': 100.0,
                    'percentage': 40.0,
                }),
            ],
        })

    def _make_wizard(self, chantier=None, invoice_type=None):
        return self.env['construction.invoice.schedule.wizard'].create({
            'chantier_id': (chantier or self.chantier).id,
            'invoice_type_id': (invoice_type or self.invoice_type).id,
        })

    # ========================= test 4 =========================

    def test_wizard_generates_schedules_from_invoice_type(self):
        """AAA: action_generate_schedule crée les schedules depuis invoice_type_id."""
        # Arrange
        chantier2 = self.env['construction.chantier'].create({
            'name': 'Chantier Gen Sched',
            'client': self.client.id,
            'total_cost': 10000.0,
        })
        wizard = self._make_wizard(chantier=chantier2)

        # Act
        wizard.action_generate_schedule()

        # Assert — 3 lignes créées (une par ligne du cycle)
        schedules = self.env['construction.invoice.schedule'].search([
            ('chantier_id', '=', chantier2.id),
        ])
        self.assertEqual(len(schedules), 3)
        # Vérifier que les pourcentages correspondent aux lignes du cycle
        percentages = sorted(schedules.mapped('amount_percentage'))
        self.assertEqual(percentages, [30.0, 30.0, 40.0])
        # Vérifier que chaque schedule est en état 'planned'
        for s in schedules:
            self.assertEqual(s.state, 'planned')

    # ========================= test 5 =========================

    def test_wizard_prefills_quote_if_single_available(self):
        """AAA: _onchange_chantier_id pré-remplit quote_id si un seul SO confirmé."""
        # Arrange — créer un devis confirmé sur le chantier
        # A lot is required on each SO line when the SO is linked to a chantier
        lot_category = self.env['construction.lot.category'].create({
            'name': 'Cat Wizard IS', 'code': 'CATWIZIS',
        })
        lot = self.env['construction.lot'].create({
            'category_id': lot_category.id,
            'chantier_id': self.chantier.id,
        })
        so = self.env['sale.order'].create({
            'partner_id': self.client.id,
            'chantier_id': self.chantier.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'price_unit': 20000.0,
                'lot_id': lot.id,
            })],
        })
        so.action_confirm()

        # Créer le wizard sans quote_id et simuler le onchange
        wizard = self.env['construction.invoice.schedule.wizard'].new({
            'chantier_id': self.chantier.id,
            'invoice_type_id': self.invoice_type.id,
        })

        # Act
        wizard._onchange_chantier_id()

        # Assert — quote_id est pré-rempli avec le seul SO confirmé
        self.assertEqual(
            wizard.quote_id.id, so.id,
            "Le wizard doit pré-remplir quote_id avec l'unique SO confirmé"
        )

    # ========================= test 6 =========================

    def test_wizard_raises_if_no_invoice_type(self):
        """AAA: UserError si invoice_type_id manquant (champ required=True)."""
        # Arrange — invoice_type_id est required=True sur le modèle,
        # donc Odoo lève une erreur à la création sans ce champ
        with self.assertRaises(Exception):
            self.env['construction.invoice.schedule.wizard'].create({
                'chantier_id': self.chantier.id,
                # invoice_type_id volontairement absent
            })
