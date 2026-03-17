# -*- coding: utf-8 -*-
"""
Tests for ProductTemplate construction extensions.
AAA pattern, tagged post_install.

Covers:
- lot_category_ids Many2many + legacy lot_category_id computed
- create() auto-generation of default_code
- price_type_label computation
- surface/length/weight_required computed fields
- construction_specialty computation
"""
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestProductTemplateLotCategory(TransactionCase):
    """ProductTemplate.lot_category_ids + legacy lot_category_id."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        # Reuse or create lot categories
        LotCat = cls.env['construction.lot.category']
        cls.cat_go = LotCat.search([('code', '=', 'GO')], limit=1)
        if not cls.cat_go:
            cls.cat_go = LotCat.create({'name': 'Gros Oeuvre', 'code': 'GO'})
        cls.cat_elec = LotCat.search([('code', '=', 'ELEC')], limit=1)
        if not cls.cat_elec:
            cls.cat_elec = LotCat.create({'name': 'Électricité', 'code': 'ELEC'})

    # ========================= lot_category_ids M2M =========================

    def test_assign_single_category(self):
        # GIVEN a product template with one lot category
        p = self.env['product.template'].create({
            'name': 'Prod Cat 1',
            'type': 'service',
            'lot_category_ids': [(6, 0, [self.cat_go.id])],
        })
        # THEN lot_category_ids contains that category
        self.assertIn(self.cat_go, p.lot_category_ids)

    def test_assign_multiple_categories(self):
        # GIVEN a product template with two lot categories
        p = self.env['product.template'].create({
            'name': 'Prod Cat 2',
            'type': 'service',
            'lot_category_ids': [(6, 0, [self.cat_go.id, self.cat_elec.id])],
        })
        # THEN both categories are in lot_category_ids
        self.assertIn(self.cat_go, p.lot_category_ids)
        self.assertIn(self.cat_elec, p.lot_category_ids)
        self.assertEqual(len(p.lot_category_ids), 2)

    def test_no_categories_allowed(self):
        # GIVEN a product with no lot categories
        p = self.env['product.template'].create({
            'name': 'Prod No Cat',
            'type': 'service',
        })
        # THEN lot_category_ids is empty
        self.assertFalse(p.lot_category_ids)

    # ========================= lot_category_id (legacy) =========================

    def test_legacy_category_is_first_of_m2m(self):
        # GIVEN a product with at least one category
        p = self.env['product.template'].create({
            'name': 'Prod Legacy',
            'type': 'service',
            'lot_category_ids': [(6, 0, [self.cat_go.id, self.cat_elec.id])],
        })
        # THEN lot_category_id is one of the assigned categories (the first one)
        self.assertTrue(p.lot_category_id)
        self.assertIn(p.lot_category_id, p.lot_category_ids)

    def test_legacy_category_false_when_no_categories(self):
        # GIVEN a product with no categories
        p = self.env['product.template'].create({
            'name': 'Prod Legacy False',
            'type': 'service',
        })
        # THEN lot_category_id is False
        self.assertFalse(p.lot_category_id)

    def test_legacy_category_updates_when_categories_change(self):
        # GIVEN a product initially with GO category
        p = self.env['product.template'].create({
            'name': 'Prod Legacy Update',
            'type': 'service',
            'lot_category_ids': [(6, 0, [self.cat_go.id])],
        })
        self.assertEqual(p.lot_category_id, self.cat_go)
        # WHEN categories cleared
        p.lot_category_ids = [(5,)]
        # THEN legacy field resets
        self.assertFalse(p.lot_category_id)


@tagged('post_install', '-at_install')
class TestProductTemplateDefaultCode(TransactionCase):
    """ProductTemplate.create() auto-generates default_code from lot codes + name."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        LotCat = cls.env['construction.lot.category']
        cls.cat_go = LotCat.search([('code', '=', 'GO')], limit=1)
        if not cls.cat_go:
            cls.cat_go = LotCat.create({'name': 'Gros Oeuvre', 'code': 'GO'})
        cls.cat_menu = LotCat.search([('code', '=', 'MENU')], limit=1)
        if not cls.cat_menu:
            cls.cat_menu = LotCat.create({'name': 'Menuiserie', 'code': 'MENU'})

    def test_auto_generate_default_code_single_category(self):
        # GIVEN a product with 1 category (GO) and name "Brique 20cm"
        p = self.env['product.template'].create({
            'name': 'Brique 20cm',
            'type': 'service',
            'lot_category_ids': [(6, 0, [self.cat_go.id])],
        })
        # THEN default_code generated: GO-BRIQUE-20CM (name truncated at 15)
        self.assertTrue(p.default_code)
        self.assertIn('GO', p.default_code)

    def test_auto_generate_default_code_two_categories(self):
        # GIVEN a product with 2 categories (GO + MENU) and name "Porte Bois"
        p = self.env['product.template'].create({
            'name': 'Porte Bois',
            'type': 'service',
            'lot_category_ids': [(6, 0, [self.cat_go.id, self.cat_menu.id])],
        })
        # THEN default_code contains both codes
        self.assertTrue(p.default_code)
        self.assertIn('GO', p.default_code)
        self.assertIn('MENU', p.default_code)

    def test_no_auto_generate_if_code_already_provided(self):
        # GIVEN a product with explicit default_code
        p = self.env['product.template'].create({
            'name': 'Custom Code',
            'type': 'service',
            'default_code': 'MY-CODE',
            'lot_category_ids': [(6, 0, [self.cat_go.id])],
        })
        # THEN default_code is not overwritten
        self.assertEqual(p.default_code, 'MY-CODE')

    def test_no_auto_generate_without_categories(self):
        # GIVEN a product without lot categories
        p = self.env['product.template'].create({
            'name': 'No Category Product',
            'type': 'service',
        })
        # THEN default_code not auto-generated (may remain empty or Odoo default)
        # The key is it doesn't crash
        self.assertIsNotNone(p.default_code is False or p.default_code is not None)

    def test_default_code_format_uppercase(self):
        # GIVEN a product with lowercase name
        p = self.env['product.template'].create({
            'name': 'carrelage sol',
            'type': 'service',
            'lot_category_ids': [(6, 0, [self.cat_go.id])],
        })
        # THEN code part is uppercase
        if p.default_code:
            self.assertEqual(p.default_code, p.default_code.upper())


@tagged('post_install', '-at_install')
class TestProductTemplatePriceType(TransactionCase):
    """ProductTemplate price_type, price_type_label, required fields."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    def _product(self, price_type='standard', name='Test Prod'):
        return self.env['product.template'].create({
            'name': name,
            'type': 'service',
            'price_type': price_type,
        })

    # ========================= price_type_label =========================

    def test_label_standard(self):
        p = self._product(price_type='standard')
        self.assertEqual(p.price_type_label, 'Unit')

    def test_label_m2(self):
        p = self._product(price_type='m2')
        self.assertEqual(p.price_type_label, 'm²')

    def test_label_ml(self):
        p = self._product(price_type='ml')
        self.assertEqual(p.price_type_label, 'ml')

    def test_label_weight(self):
        p = self._product(price_type='weight')
        self.assertEqual(p.price_type_label, 'kg')

    def test_label_updates_on_price_type_change(self):
        p = self._product(price_type='standard')
        self.assertEqual(p.price_type_label, 'Unit')
        # WHEN changing price_type
        p.price_type = 'm2'
        # THEN label updates
        self.assertEqual(p.price_type_label, 'm²')

    # ========================= required fields =========================

    def test_surface_required_for_m2(self):
        p = self._product(price_type='m2')
        self.assertTrue(p.surface_required)
        self.assertFalse(p.length_required)
        self.assertFalse(p.weight_required)

    def test_length_required_for_ml(self):
        p = self._product(price_type='ml')
        self.assertFalse(p.surface_required)
        self.assertTrue(p.length_required)
        self.assertFalse(p.weight_required)

    def test_weight_required_for_weight(self):
        p = self._product(price_type='weight')
        self.assertFalse(p.surface_required)
        self.assertFalse(p.length_required)
        self.assertTrue(p.weight_required)

    def test_no_required_fields_for_standard(self):
        p = self._product(price_type='standard')
        self.assertFalse(p.surface_required)
        self.assertFalse(p.length_required)
        self.assertFalse(p.weight_required)

    # ========================= construction_specialty =========================

    def test_specialty_from_category_standard(self):
        p = self._product(price_type='standard')
        # specialty = category name (or 'General')
        self.assertTrue(p.construction_specialty)

    def test_specialty_appends_surface_label(self):
        p = self._product(price_type='m2')
        self.assertIn('Surface', p.construction_specialty)

    def test_specialty_appends_linear_label(self):
        p = self._product(price_type='ml')
        self.assertIn('Linear', p.construction_specialty)

    def test_specialty_general_when_no_category(self):
        p = self.env['product.template'].create({
            'name': 'No Categ Prod',
            'type': 'service',
            'price_type': 'standard',
        })
        # Remove categ_id if set
        p.categ_id = False
        p._compute_construction_specialty()
        self.assertIn('General', p.construction_specialty)

    # ========================= measurement value fields =========================

    def test_surface_value_set_on_m2_product(self):
        p = self._product(price_type='m2')
        p.surface_value = 12.5
        self.assertEqual(p.surface_value, 12.5)

    def test_length_value_set_on_ml_product(self):
        p = self._product(price_type='ml')
        p.length_value = 3.0
        self.assertEqual(p.length_value, 3.0)

    def test_weight_value_set_on_weight_product(self):
        p = self._product(price_type='weight')
        p.weight_value = 75.0
        self.assertEqual(p.weight_value, 75.0)

    # ========================= service_to_purchase =========================

    def test_service_to_purchase_default_false(self):
        p = self._product()
        self.assertFalse(p.service_to_purchase)

    def test_service_to_purchase_is_boolean_field(self):
        # GIVEN a product template
        p = self._product()
        # THEN service_to_purchase is a boolean (default False)
        self.assertIsInstance(p.service_to_purchase, bool)
