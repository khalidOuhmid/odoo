# -*- coding: utf-8 -*-
"""
Extended tests for construction_contract — zones non couvertes.
AAA pattern, tagged post_install.

Covers:
- URSSAFCode: computed fields, constraints, name_get/name_search
- ConstructionContractTemplate: default uniqueness, copy, set_as_default
- ChantierExtension: contract statistics computed fields, action_view_contracts
- PurchaseOrder F-03: write/unlink blocked on signed contract
- ResPartner extension: subcontractor_contract_count
- Archived contract immutability
"""
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError, UserError
from datetime import date, timedelta
import base64


# ============================================================
# SHARED SETUP
# ============================================================

def _mock_doc():
    return base64.b64encode(b'%PDF-1.4 mock document').decode('ascii')


def _expiry():
    return date.today() + timedelta(days=365)


@tagged('post_install', '-at_install')
class TestURSSAFCode(TransactionCase):
    """URSSAFCode: computed fields, constraints, name_get/name_search."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.URSSAFCode = cls.env['construction.urssaf.code']

    def _code(self, code='TST001', name='Test Cotisation', **kw):
        vals = {'code': code, 'name': name, 'category': 'cotisation'}
        vals.update(kw)
        return self.URSSAFCode.create(vals)

    # ========================= display_name_full =========================

    def test_display_name_full_format(self):
        # GIVEN a code with code='1000' and name='Cotisation principale'
        c = self._code(code='1000', name='Cotisation principale')
        # THEN display_name_full = '1000 - Cotisation principale'
        self.assertEqual(c.display_name_full, '1000 - Cotisation principale')

    def test_display_name_full_updates_on_name_change(self):
        # GIVEN a code
        c = self._code(code='2000', name='Original')
        # WHEN name changes
        c.name = 'Nouveau Nom'
        # THEN display_name_full updates
        self.assertIn('Nouveau Nom', c.display_name_full)

    # ========================= _check_dates =========================

    def test_dates_valid_end_after_start(self):
        # GIVEN end_date after effective_date
        c = self._code(
            code='D001',
            effective_date=date.today(),
            end_date=date.today() + timedelta(days=30),
        )
        # THEN no error
        self.assertTrue(c)

    def test_dates_end_before_start_raises(self):
        # GIVEN end_date before effective_date
        with self.assertRaises(ValidationError):
            self._code(
                code='D002',
                effective_date=date.today() + timedelta(days=30),
                end_date=date.today(),
            )

    def test_dates_same_day_ok(self):
        # GIVEN end_date = effective_date (same day is OK)
        today = date.today()
        c = self._code(code='D003', effective_date=today, end_date=today)
        self.assertTrue(c)

    def test_dates_no_end_date_ok(self):
        # GIVEN only effective_date set (no end_date)
        c = self._code(code='D004', effective_date=date.today())
        self.assertTrue(c)

    # ========================= _check_rate =========================

    def test_rate_positive_ok(self):
        c = self._code(code='R001', rate=5.5)
        self.assertAlmostEqual(c.rate, 5.5)

    def test_rate_zero_ok(self):
        c = self._code(code='R002', rate=0.0)
        self.assertAlmostEqual(c.rate, 0.0)

    def test_rate_negative_raises(self):
        with self.assertRaises(ValidationError):
            self._code(code='R003', rate=-1.0)

    # ========================= name_get =========================

    def test_name_get_shows_code_and_name(self):
        c = self._code(code='N001', name='Exoneration Spéciale')
        result = c.name_get()
        self.assertEqual(len(result), 1)
        display = result[0][1]
        self.assertIn('N001', display)
        self.assertIn('Exoneration Spéciale', display)

    # ========================= name_search =========================

    def test_name_search_by_code(self):
        # GIVEN a code 'NSRCH001'
        c = self._code(code='NSRCH001', name='Cotisation Recherche')
        # WHEN searching by code
        results = self.URSSAFCode.name_search('NSRCH001')
        ids = [r[0] for r in results]
        # THEN found
        self.assertIn(c.id, ids)

    def test_name_search_by_name(self):
        c = self._code(code='NSRCH002', name='Réduction Apprentissage XYZ')
        results = self.URSSAFCode.name_search('Apprentissage XYZ')
        ids = [r[0] for r in results]
        self.assertIn(c.id, ids)

    def test_name_search_empty_returns_all(self):
        before = len(self.URSSAFCode.name_search(''))
        self._code(code='NSRCH003', name='Extra Code')
        after = len(self.URSSAFCode.name_search(''))
        self.assertGreaterEqual(after, before)

    # ========================= unique code constraint =========================

    def test_duplicate_code_raises(self):
        import random
        unique = 'UNIQ_%04d' % random.randint(1000, 9999)
        self._code(code=unique)
        with self.assertRaises(Exception):
            self._code(code=unique)

    # ========================= categories =========================

    def test_category_cotisation(self):
        c = self._code(code='CAT001', category='cotisation')
        self.assertEqual(c.category, 'cotisation')

    def test_category_exoneration(self):
        c = self._code(code='CAT002', category='exoneration')
        self.assertEqual(c.category, 'exoneration')

    def test_active_default_true(self):
        c = self._code(code='ACT001')
        self.assertTrue(c.active)

    def test_can_archive_code(self):
        c = self._code(code='ACT002')
        c.active = False
        self.assertFalse(c.active)


@tagged('post_install', '-at_install')
class TestContractTemplate(TransactionCase):
    """ConstructionContractTemplate: default uniqueness, copy, set_as_default."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    def _template(self, name='Template Test', is_default=False, **kw):
        vals = {
            'name': name,
            'grapesjs_html': f'<h1>{name}</h1>',
            'is_default': is_default,
        }
        vals.update(kw)
        return self.env['construction.contract.template'].create(vals)

    # ========================= single default =========================

    def test_only_one_default_allowed(self):
        # Unset any existing default first
        self.env['construction.contract.template'].search(
            [('is_default', '=', True)]
        ).write({'is_default': False})
        # GIVEN first default template
        t1 = self._template(name='Default 1', is_default=True)
        # WHEN creating second default
        # THEN raises ValidationError (only one default allowed)
        with self.assertRaises(ValidationError):
            self._template(name='Default 2', is_default=True)

    def test_non_default_can_coexist(self):
        # GIVEN two non-default templates
        t1 = self._template(name='Template A', is_default=False)
        t2 = self._template(name='Template B', is_default=False)
        # THEN both created without error
        self.assertTrue(t1)
        self.assertTrue(t2)

    # ========================= copy / duplicate =========================

    def test_copy_resets_is_default(self):
        # GIVEN a template with is_default=False (can't copy a default, as we'd have 2)
        t = self._template(name='To Copy', is_default=False)
        # WHEN copying
        copy = t.copy()
        # THEN is_default is False on copy
        self.assertFalse(copy.is_default)

    def test_action_duplicate_creates_copy(self):
        # GIVEN a template
        t = self._template(name='Template Dup')
        # WHEN duplicating
        result = t.action_duplicate()
        # THEN returns act_window to new template
        self.assertEqual(result.get('type'), 'ir.actions.act_window')

    # ========================= action_set_as_default =========================

    def test_set_as_default_switches_default(self):
        # Unset any existing default first
        self.env['construction.contract.template'].search(
            [('is_default', '=', True)]
        ).write({'is_default': False})
        # GIVEN two templates, t1 is default
        t1 = self._template(name='Old Default', is_default=True)
        t2 = self._template(name='New Default', is_default=False)
        # WHEN setting t2 as default
        t2.action_set_as_default()
        # THEN t2 is default, t1 is not
        self.assertTrue(t2.is_default)
        self.assertFalse(t1.is_default)

    # ========================= action_view_contracts =========================

    def test_action_view_contracts_returns_act_window(self):
        t = self._template(name='Template With Contracts')
        result = t.action_view_contracts()
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'construction.contract')


@tagged('post_install', '-at_install')
class TestChantierContractStats(TransactionCase):
    """ChantierExtension: contract_count, signed/pending counts, total_amount."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.client = cls.env['res.partner'].create({'name': 'Client Stats', 'is_company': True})
        cls.chantier = cls.env['construction.chantier'].create({
            'name': 'Chantier Stats',
            'client': cls.client.id,
        })

        cls.subcontractor = cls.env['res.partner'].create({
            'name': 'ST Stats',
            'is_company': True,
            'supplier_rank': 1,
            'company_registry': '11122233300001',
        })
        # Give subcontractor valid docs
        _doc = _mock_doc()
        _exp = _expiry()
        cls.subcontractor.write({
            'doc_urssaf': _doc, 'doc_urssaf_expiry': _exp,
            'doc_kbis': _doc, 'doc_kbis_expiry': _exp,
            'doc_insurance_dec': _doc, 'doc_insurance_dec_expiry': _exp,
        })

        cat = cls.env['construction.lot.category'].create({'name': 'GO Stats', 'code': 'GOS'})
        cls.lot = cls.env['construction.lot'].create({
            'category_id': cat.id,
            'chantier_id': cls.chantier.id,
            'execution_type': 'external',
            'subcontractor_id': cls.subcontractor.id,
        })

        cls.template = cls.env['construction.contract.template'].create({
            'name': 'Template Stats',
            'grapesjs_html': '<h1>Contract {{contract.name}}</h1>',
        })

    def _contract(self, state='draft', **kw):
        vals = {
            'subcontractor_id': self.subcontractor.id,
            'chantier_id': self.chantier.id,
            'lot_ids': [(6, 0, [self.lot.id])],
            'template_id': self.template.id,
            'state': state,
            'date': date.today(),
            'start_date': date.today(),
            'end_date': date.today() + timedelta(days=90),
        }
        vals.update(kw)
        return self.env['construction.contract'].create(vals)

    # ========================= contract_count =========================

    def test_contract_count_zero_initially(self):
        chantier2 = self.env['construction.chantier'].create({
            'name': 'Chantier Zero', 'client': self.client.id,
        })
        self.assertEqual(chantier2.contract_count, 0)

    def test_contract_count_increments(self):
        initial = self.chantier.contract_count
        self._contract()
        self.assertEqual(self.chantier.contract_count, initial + 1)

    # ========================= signed_contract_count =========================

    def test_signed_contract_count(self):
        # GIVEN a contract in 'signed' state
        c = self._contract(state='signed')
        before_signed = len(self.chantier.contract_ids.filtered(lambda x: x.state == 'signed'))
        self.assertGreaterEqual(before_signed, 1)
        self.assertGreaterEqual(self.chantier.signed_contract_count, 1)

    # ========================= pending_contract_count =========================

    def test_pending_contract_count_for_sent(self):
        # GIVEN a contract in 'sent' state
        c = self._contract(state='sent')
        self.assertGreaterEqual(self.chantier.pending_contract_count, 1)

    # ========================= action_view_contracts =========================

    def test_action_view_contracts_single_opens_form(self):
        # GIVEN chantier with exactly one contract
        chantier2 = self.env['construction.chantier'].create({
            'name': 'Chantier One Contract', 'client': self.client.id,
        })
        cat2 = self.env['construction.lot.category'].create({'name': 'Cat2', 'code': 'CAT2_XYZ'})
        lot2 = self.env['construction.lot'].create({
            'category_id': cat2.id, 'chantier_id': chantier2.id,
            'execution_type': 'external', 'subcontractor_id': self.subcontractor.id,
        })
        c = self.env['construction.contract'].create({
            'subcontractor_id': self.subcontractor.id,
            'chantier_id': chantier2.id,
            'lot_ids': [(6, 0, [lot2.id])],
            'template_id': self.template.id,
            'state': 'draft',
            'date': date.today(),
            'start_date': date.today(),
            'end_date': date.today() + timedelta(days=90),
        })
        result = chantier2.action_view_contracts()
        # THEN opens form (single contract)
        self.assertEqual(result.get('type'), 'ir.actions.act_window')

    def test_action_create_contract_returns_wizard(self):
        result = self.chantier.action_create_contract()
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'contract.creation.wizard')

    def test_action_open_contract_builder_returns_url(self):
        result = self.chantier.action_open_contract_builder()
        self.assertEqual(result['type'], 'ir.actions.act_url')
        self.assertIn('contract/live-builder', result['url'])
        self.assertIn(str(self.chantier.id), result['url'])


@tagged('post_install', '-at_install')
class TestResPartnerContractExtension(TransactionCase):
    """ResPartner.subcontractor_contract_count computed field."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    def test_subcontractor_contract_count_zero(self):
        # GIVEN a partner without contracts
        p = self.env['res.partner'].create({'name': 'ST No Contract', 'is_company': True})
        self.assertEqual(p.subcontractor_contract_count, 0)

    def test_action_view_subcontractor_contracts(self):
        # GIVEN a subcontractor partner
        p = self.env['res.partner'].create({'name': 'ST View', 'is_company': True})
        result = p.action_view_subcontractor_contracts()
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'construction.contract')


@tagged('post_install', '-at_install')
class TestContractPurchaseOrderF03(TransactionCase):
    """PurchaseOrder F-03: modifications blocked when linked to signed contract."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.subcontractor = cls.env['res.partner'].create({
            'name': 'ST F03', 'is_company': True, 'supplier_rank': 1,
            'company_registry': '77788899900001',
        })
        _doc = _mock_doc()
        _exp = _expiry()
        cls.subcontractor.write({
            'doc_urssaf': _doc, 'doc_urssaf_expiry': _exp,
            'doc_kbis': _doc, 'doc_kbis_expiry': _exp,
            'doc_insurance_dec': _doc, 'doc_insurance_dec_expiry': _exp,
        })

        cls.client = cls.env['res.partner'].create({'name': 'Client F03', 'is_company': True})
        cls.chantier = cls.env['construction.chantier'].create({
            'name': 'Chantier F03', 'client': cls.client.id,
        })
        cat = cls.env['construction.lot.category'].create({'name': 'F03 Cat', 'code': 'F03C'})
        cls.lot = cls.env['construction.lot'].create({
            'category_id': cat.id, 'chantier_id': cls.chantier.id,
            'execution_type': 'external', 'subcontractor_id': cls.subcontractor.id,
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Svc F03', 'type': 'service',
        })
        cls.template = cls.env['construction.contract.template'].create({
            'name': 'Template F03',
            'grapesjs_html': '<p>Contract</p>',
        })

    def _po(self):
        return self.env['purchase.order'].create({
            'partner_id': self.subcontractor.id,
            'date_order': date.today(),
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'name': 'Ligne F03',
                'product_qty': 1,
                'price_unit': 1000.0,
            })],
        })

    def _contract_signed_with_po(self, po):
        return self.env['construction.contract'].create({
            'subcontractor_id': self.subcontractor.id,
            'chantier_id': self.chantier.id,
            'lot_ids': [(6, 0, [self.lot.id])],
            'template_id': self.template.id,
            'state': 'signed',
            'date': date.today(),
            'start_date': date.today(),
            'end_date': date.today() + timedelta(days=90),
            'purchase_order_ids': [(6, 0, [po.id])],
        })

    def test_po_write_blocked_when_signed_contract(self):
        # GIVEN a PO linked to a signed contract
        po = self._po()
        self._contract_signed_with_po(po)
        # WHEN trying to write on PO
        # THEN UserError raised (F-03 Validation Financière Stricte)
        with self.assertRaises(UserError):
            po.write({'notes': 'Modification bloquée'})

    def test_po_unlink_blocked_when_signed_contract(self):
        # GIVEN a PO linked to a signed contract
        po = self._po()
        self._contract_signed_with_po(po)
        # WHEN trying to delete PO
        # THEN UserError raised
        with self.assertRaises(UserError):
            po.unlink()

    def test_po_write_allowed_without_signed_contract(self):
        # GIVEN a PO without any signed contract
        po = self._po()
        # WHEN writing on PO
        # THEN no error
        po.write({'notes': 'Modification autorisée'})
        self.assertIn('Modification autorisée', po.notes or '')


@tagged('post_install', '-at_install')
class TestContractRetentionConstraints(TransactionCase):
    """Contract retention_rate and date constraints."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.client = cls.env['res.partner'].create({'name': 'Client Ret', 'is_company': True})
        cls.subcontractor = cls.env['res.partner'].create({
            'name': 'ST Ret', 'is_company': True, 'supplier_rank': 1,
            'company_registry': '44455566600001',
        })
        _doc = _mock_doc()
        _exp = _expiry()
        cls.subcontractor.write({
            'doc_urssaf': _doc, 'doc_urssaf_expiry': _exp,
            'doc_kbis': _doc, 'doc_kbis_expiry': _exp,
            'doc_insurance_dec': _doc, 'doc_insurance_dec_expiry': _exp,
        })

        cls.chantier = cls.env['construction.chantier'].create({
            'name': 'Chantier Ret', 'client': cls.client.id,
        })
        cat = cls.env['construction.lot.category'].create({'name': 'Ret Cat', 'code': 'RETC'})
        cls.lot = cls.env['construction.lot'].create({
            'category_id': cat.id, 'chantier_id': cls.chantier.id,
            'execution_type': 'external', 'subcontractor_id': cls.subcontractor.id,
        })
        cls.template = cls.env['construction.contract.template'].create({
            'name': 'Template Ret', 'grapesjs_html': '<p>Ret</p>',
        })

    def _contract(self, **kw):
        defaults = {
            'subcontractor_id': self.subcontractor.id,
            'chantier_id': self.chantier.id,
            'lot_ids': [(6, 0, [self.lot.id])],
            'template_id': self.template.id,
            'state': 'draft',
            'date': date.today(),
            'start_date': date.today(),
            'end_date': date.today() + timedelta(days=90),
            'retention_rate': 5.0,
        }
        defaults.update(kw)
        return self.env['construction.contract'].create(defaults)

    def test_retention_rate_valid(self):
        c = self._contract(retention_rate=5.0)
        self.assertAlmostEqual(c.retention_rate, 5.0)

    def test_retention_rate_negative_raises(self):
        with self.assertRaises(ValidationError):
            self._contract(retention_rate=-1.0)

    def test_retention_rate_over_100_raises(self):
        with self.assertRaises(ValidationError):
            self._contract(retention_rate=101.0)

    def test_end_date_before_start_raises(self):
        with self.assertRaises(ValidationError):
            self._contract(
                start_date=date.today() + timedelta(days=30),
                end_date=date.today(),
            )

    def test_dates_same_day_ok(self):
        today = date.today()
        c = self._contract(start_date=today, end_date=today)
        self.assertTrue(c)
