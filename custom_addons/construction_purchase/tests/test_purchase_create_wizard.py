# -*- coding: utf-8 -*-
"""
AAA Test Suite: ConstructionPurchaseCreateWizard
=================================================
Couvre la generation groupee de bons de commande par sous-traitant,
l'exclusion des lots en regie, les lots sans sous-traitant, le montant
zero, et les scenarios multi-lots/multi-sous-traitants.

Pattern : Arrange -> Act -> Assert (AAA)
"""
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import UserError


@tagged('post_install', '-at_install')
class TestPurchaseCreateWizard(TransactionCase):
    """Tests pour construction.purchase.create.wizard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.supplier_a = cls.env['res.partner'].create({
            'name': 'Sous-traitant A', 'supplier_rank': 1,
        })
        cls.supplier_b = cls.env['res.partner'].create({
            'name': 'Sous-traitant B', 'supplier_rank': 1,
        })
        cls.client = cls.env['res.partner'].create({
            'name': 'Client Create Wiz', 'is_company': True,
        })
        cls.chantier = cls.env['construction.chantier'].create({
            'name': 'Chantier Create Wiz', 'client': cls.client.id,
        })
        # Chaque lot utilise une categorie distincte pour respecter la contrainte
        # d'unicite construction_lot_unique_category_per_chantier.
        cls.cat_a = cls.env['construction.lot.category'].create({
            'name': 'Elec CW A', 'code': 'ELEC_CWA',
        })
        cls.cat_b = cls.env['construction.lot.category'].create({
            'name': 'Elec CW B', 'code': 'ELEC_CWB',
        })
        cls.cat_int = cls.env['construction.lot.category'].create({
            'name': 'Regie CW', 'code': 'REG_CW',
        })
        cls.cat_nosub = cls.env['construction.lot.category'].create({
            'name': 'NoSub CW', 'code': 'NSUB_CW',
        })
        cls.lot_external_a = cls.env['construction.lot'].create({
            'category_id': cls.cat_a.id,
            'chantier_id': cls.chantier.id,
            'price': 8000.0,
            'execution_type': 'external',
            'subcontractor_id': cls.supplier_a.id,
            'subcontractor_ids': [(4, cls.supplier_a.id)],
        })
        cls.lot_external_b = cls.env['construction.lot'].create({
            'category_id': cls.cat_b.id,
            'chantier_id': cls.chantier.id,
            'price': 5000.0,
            'execution_type': 'external',
            'subcontractor_id': cls.supplier_b.id,
            'subcontractor_ids': [(4, cls.supplier_b.id)],
        })
        cls.lot_internal = cls.env['construction.lot'].create({
            'category_id': cls.cat_int.id,
            'chantier_id': cls.chantier.id,
            'price': 3000.0,
            'execution_type': 'internal',
        })
        cls.lot_no_sub = cls.env['construction.lot'].create({
            'category_id': cls.cat_nosub.id,
            'chantier_id': cls.chantier.id,
            'price': 2000.0,
            'execution_type': 'external',
        })

    def _make_wizard(self, lot_ids):
        return self.env['construction.purchase.create.wizard'].create({
            'chantier_id': self.chantier.id,
            'lot_ids': [(6, 0, lot_ids)],
        })

    # =================== Cas sans lots ===================

    def test_no_lots_raises_user_error(self):
        """Arrange: wizard sans lots. Act/Assert: UserError."""
        wizard = self.env['construction.purchase.create.wizard'].create({
            'chantier_id': self.chantier.id,
        })
        with self.assertRaises(UserError):
            wizard.action_create_purchase_orders()

    # =================== Lots sans sous-traitant ===================

    def test_only_lot_without_subcontractor_raises_user_error(self):
        """Si tous les lots n'ont pas de sous-traitant, une UserError est levee."""
        wizard = self._make_wizard([self.lot_no_sub.id])
        with self.assertRaises(UserError):
            wizard.action_create_purchase_orders()

    def test_lot_without_subcontractor_is_skipped_when_others_valid(self):
        """Un lot sans sous-traitant est ignore : seuls les lots valides generent un BC."""
        wizard = self._make_wizard([self.lot_external_a.id, self.lot_no_sub.id])
        result = wizard.action_create_purchase_orders()
        created_pos = self.env['purchase.order'].search([
            ('id', 'in', result.get('domain', [('id', 'in', [])])[0][2]),
        ])
        # Un seul BC cree (pour supplier_a), le lot sans sous-traitant a ete saute
        for po in created_pos:
            self.assertEqual(po.partner_id.id, self.supplier_a.id)

    # =================== Groupement par sous-traitant ===================

    def test_two_lots_two_subcontractors_creates_two_pos(self):
        """Deux lots avec deux sous-traitants differents doivent generer deux BCs."""
        wizard = self._make_wizard([self.lot_external_a.id, self.lot_external_b.id])
        result = wizard.action_create_purchase_orders()
        domain = result.get('domain', [])
        ids = next((d[2] for d in domain if d[0] == 'id'), [])
        created_pos = self.env['purchase.order'].browse(ids)
        self.assertEqual(len(created_pos), 2)
        partners = set(created_pos.mapped('partner_id.id'))
        self.assertIn(self.supplier_a.id, partners)
        self.assertIn(self.supplier_b.id, partners)

    def test_one_lot_one_subcontractor_creates_one_po(self):
        """Un lot avec un sous-traitant cree exactement un BC."""
        wizard = self._make_wizard([self.lot_external_a.id])
        result = wizard.action_create_purchase_orders()
        domain = result.get('domain', [])
        ids = next((d[2] for d in domain if d[0] == 'id'), [])
        created_pos = self.env['purchase.order'].browse(ids)
        self.assertEqual(len(created_pos), 1)
        self.assertEqual(created_pos.partner_id.id, self.supplier_a.id)

    # =================== BC lie au chantier ===================

    def test_created_po_linked_to_chantier(self):
        """Le BC cree doit etre rattache au chantier du wizard."""
        wizard = self._make_wizard([self.lot_external_a.id])
        result = wizard.action_create_purchase_orders()
        domain = result.get('domain', [])
        ids = next((d[2] for d in domain if d[0] == 'id'), [])
        po = self.env['purchase.order'].browse(ids[0])
        self.assertEqual(po.chantier_id.id, self.chantier.id)

    # =================== Montant zero ===================

    def test_lot_with_zero_price_creates_po_with_zero_line(self):
        """Un lot avec price=0 doit quand meme generer un BC (ligne a 0 EUR)."""
        cat_zero = self.env['construction.lot.category'].create({
            'name': 'Zero Price Cat', 'code': 'ZERO_CW',
        })
        lot_zero = self.env['construction.lot'].create({
            'category_id': cat_zero.id,
            'chantier_id': self.chantier.id,
            'price': 0.0,
            'execution_type': 'external',
            'subcontractor_id': self.supplier_a.id,
            'subcontractor_ids': [(4, self.supplier_a.id)],
        })
        wizard = self._make_wizard([lot_zero.id])
        result = wizard.action_create_purchase_orders()
        domain = result.get('domain', [])
        ids = next((d[2] for d in domain if d[0] == 'id'), [])
        po = self.env['purchase.order'].browse(ids[0])
        self.assertTrue(po.exists())
        product_lines = po.order_line.filtered(lambda l: not l.display_type)
        self.assertTrue(product_lines)
        self.assertEqual(product_lines[0].price_unit, 0.0)

    # =================== Multi-lots meme sous-traitant ===================

    def test_two_lots_same_subcontractor_creates_one_po_with_two_lines(self):
        """Deux lots du meme sous-traitant -> un seul BC avec deux lignes."""
        cat_extra = self.env['construction.lot.category'].create({
            'name': 'Extra Cat CW', 'code': 'EXTR_CW',
        })
        lot_extra = self.env['construction.lot'].create({
            'category_id': cat_extra.id,
            'chantier_id': self.chantier.id,
            'price': 4000.0,
            'execution_type': 'external',
            'subcontractor_id': self.supplier_a.id,
            'subcontractor_ids': [(4, self.supplier_a.id)],
        })
        wizard = self._make_wizard([self.lot_external_a.id, lot_extra.id])
        result = wizard.action_create_purchase_orders()
        domain = result.get('domain', [])
        ids = next((d[2] for d in domain if d[0] == 'id'), [])
        created_pos = self.env['purchase.order'].browse(ids)
        self.assertEqual(len(created_pos), 1)
        product_lines = created_pos.order_line.filtered(lambda l: not l.display_type)
        self.assertEqual(len(product_lines), 2)

    # =================== Lot en regie exclu de default_get ===================

    def test_default_get_excludes_internal_lots(self):
        """default_get ne doit pas proposer les lots en regie (execution_type=internal)."""
        wizard_ctx = self.env['construction.purchase.create.wizard'].with_context(
            active_model='construction.chantier',
            active_id=self.chantier.id,
        )
        result = wizard_ctx.default_get(['lot_ids', 'chantier_id'])
        proposed_lot_ids = result.get('lot_ids', [])
        # lot_internal ne doit pas etre propose
        self.assertNotIn(self.lot_internal.id, proposed_lot_ids)

    # =================== Retour action act_window ===================

    def test_action_returns_act_window(self):
        """La methode action_create_purchase_orders retourne toujours une act_window."""
        wizard = self._make_wizard([self.lot_external_a.id])
        result = wizard.action_create_purchase_orders()
        self.assertEqual(result.get('type'), 'ir.actions.act_window')
        self.assertEqual(result.get('res_model'), 'purchase.order')
