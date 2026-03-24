# -*- coding: utf-8 -*-
"""
Tests AAA pour la machine d'états du contrat (construction.contract).

Couvre :
- action_generate_pdf ne transite PAS vers 'sent'
- action_send_for_signature exige l'état 'generated'
- action_send_for_signature depuis 'generated' réussit
- action_cancel sur contrat signé lève UserError
- action_reset_to_draft depuis 'cancelled' fonctionne
- action_reset_to_draft depuis un état non-annulé lève UserError
- _compute_amounts exclut les POs brouillon
- _compute_amounts n'utilise pas write() (pas de RecursionError)
"""

from odoo.tests.common import TransactionCase
from odoo.tests import tagged
from odoo.exceptions import UserError
from unittest.mock import patch
from datetime import date, timedelta
import base64


@tagged('post_install', '-at_install')
class TestContractStateMachine(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # ── Company ──────────────────────────────────────────────
        cls.company = cls.env.company
        cls.company.write({
            'name': 'BLG GROUPE TEST',
            'city': 'Bordeaux',
        })

        # ── Subcontractor partner ─────────────────────────────────
        _mock_doc = base64.b64encode(b'%PDF-1.4 mock document').decode('ascii')
        _expiry = date.today() + timedelta(days=365)
        cls.subcontractor = cls.env['res.partner'].create({
            'name': 'SARL SM Test',
            'is_company': True,
            'email': 'sm-test@example.com',
            'supplier_rank': 1,
            'company_registry': '98765432100099',
        })
        cls.subcontractor.write({
            'doc_urssaf': _mock_doc,
            'doc_urssaf_expiry': _expiry,
            'doc_kbis': _mock_doc,
            'doc_kbis_expiry': _expiry,
            'doc_insurance_dec': _mock_doc,
            'doc_insurance_dec_expiry': _expiry,
        })

        # ── Chantier ──────────────────────────────────────────────
        cls.client = cls.env['res.partner'].create({'name': 'Client SM Test'})
        cls.chantier = cls.env['construction.chantier'].create({
            'name': 'Chantier SM Test',
            'client': cls.client.id,
        })

        # ── Lot ───────────────────────────────────────────────────
        cls.category = cls.env['construction.lot.category'].create({
            'name': 'GO SM',
            'code': 'GO_SM',
        })
        cls.lot = cls.env['construction.lot'].create({
            'category_id': cls.category.id,
            'chantier_id': cls.chantier.id,
            'execution_type': 'external',
            'subcontractor_id': cls.subcontractor.id,
        })

        # ── Template minimal ──────────────────────────────────────
        cls.template = cls.env['construction.contract.template'].create({
            'name': 'Template SM Test',
            'grapesjs_html': '<h1>Contrat {{partner_name}}</h1>',
            'grapesjs_css': '',
        })

        # ── Produit ───────────────────────────────────────────────
        cls.product = cls.env['product.product'].create({
            'name': 'Prestation SM',
            'type': 'service',
        })

    # ─────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────

    def _make_contract(self, state='draft', with_confirmed_po=False, with_pdf=False):
        """Crée un contrat de test dans l'état demandé."""
        contract = self.env['construction.contract'].create({
            'subcontractor_id': self.subcontractor.id,
            'chantier_id': self.chantier.id,
            'lot_ids': [(6, 0, [self.lot.id])],
            'template_id': self.template.id,
            'date': date.today(),
            'start_date': date.today(),
            'end_date': date.today() + timedelta(days=90),
            'retention_rate': 5.0,
        })

        if with_confirmed_po:
            po = self.env['purchase.order'].create({
                'partner_id': self.subcontractor.id,
                'date_order': date.today(),
                'order_line': [(0, 0, {
                    'product_id': self.product.id,
                    'name': 'Prestation SM',
                    'product_qty': 1,
                    'price_unit': 5000.0,
                })],
            })
            po.button_confirm()
            contract.write({'purchase_order_ids': [(4, po.id)]})

        if with_pdf:
            pdf_b64 = base64.b64encode(b'%PDF-1.4 mock').decode()
            contract.write({'pdf_document': pdf_b64})

        if state != 'draft':
            # Forçage direct de l'état pour les tests d'état machine
            contract.write({'state': state})

        return contract

    # ─────────────────────────────────────────────────────────────
    # Test 1 — action_generate_pdf ne transite PAS vers 'sent'
    # ─────────────────────────────────────────────────────────────

    def test_generate_pdf_does_not_transition_to_sent(self):
        """
        Arrange : contrat en état 'generated' avec HTML.
        Act     : appeler action_generate_pdf (QWeb mocké).
        Assert  : state == 'generated' (PAS 'sent').
        """
        # Arrange
        contract = self._make_contract(state='generated')
        html_content = '<h1>Contrat Test</h1><p>Contenu minimal pour PDF</p>'
        contract.write({'contract_template_html': html_content})

        mock_pdf = b'%PDF-1.4 mock-pdf-content'

        # Act
        with patch.object(
            type(self.env['ir.actions.report']),
            '_render_qweb_pdf',
            return_value=(mock_pdf, 'application/pdf'),
        ):
            contract.action_generate_pdf()

        # Assert
        self.assertEqual(
            contract.state,
            'generated',
            "action_generate_pdf ne doit PAS faire transiter le contrat vers 'sent'.",
        )
        self.assertTrue(contract.pdf_document, "Le PDF doit être stocké.")
        self.assertTrue(
            contract.pdf_hash_before_signature,
            "Le hash SHA-256 doit être calculé.",
        )

    # ─────────────────────────────────────────────────────────────
    # Test 2 — action_send_for_signature exige l'état 'generated'
    # ─────────────────────────────────────────────────────────────

    def test_send_for_signature_requires_generated_state(self):
        """
        Arrange : contrat en état 'draft'.
        Act     : appeler action_send_for_signature.
        Assert  : UserError levée (état incorrect).
        """
        # Arrange
        contract = self._make_contract(state='draft')

        # Act + Assert
        with self.assertRaises(UserError):
            contract.action_send_for_signature()

    # ─────────────────────────────────────────────────────────────
    # Test 3 — action_send_for_signature depuis 'generated' réussit
    # ─────────────────────────────────────────────────────────────

    def test_send_for_signature_from_generated_succeeds(self):
        """
        Arrange : contrat en état 'generated' avec PDF et PO confirmé.
        Act     : action_send_for_signature (notification service mocké).
        Assert  : state == 'sent', sent_date défini.
        """
        # Arrange
        contract = self._make_contract(
            state='generated',
            with_confirmed_po=True,
            with_pdf=True,
        )

        # Act
        with patch.object(
            type(self.env['construction.contract.notification']),
            'send_contract_invitation',
            return_value=None,
        ):
            contract.action_send_for_signature()

        # Assert
        self.assertEqual(contract.state, 'sent')
        self.assertTrue(
            contract.sent_date,
            "sent_date doit être défini après envoi.",
        )

    # ─────────────────────────────────────────────────────────────
    # Test 4 — action_cancel sur contrat signé lève UserError
    # ─────────────────────────────────────────────────────────────

    def test_cancel_signed_contract_raises(self):
        """
        Arrange : contrat en état 'signed'.
        Act     : action_cancel.
        Assert  : UserError levée.
        """
        # Arrange
        contract = self._make_contract(state='signed')

        # Act + Assert
        with self.assertRaises(UserError):
            contract.action_cancel()

    # ─────────────────────────────────────────────────────────────
    # Test 5 — action_reset_to_draft depuis 'cancelled'
    # ─────────────────────────────────────────────────────────────

    def test_reset_to_draft_from_cancelled(self):
        """
        Arrange : contrat en état 'cancelled'.
        Act     : action_reset_to_draft.
        Assert  : state == 'draft'.
        """
        # Arrange
        contract = self._make_contract(state='cancelled')

        # Act
        contract.action_reset_to_draft()

        # Assert
        self.assertEqual(contract.state, 'draft')

    # ─────────────────────────────────────────────────────────────
    # Test 6 — action_reset_to_draft depuis un état non-annulé lève UserError
    # ─────────────────────────────────────────────────────────────

    def test_reset_to_draft_from_non_cancelled_raises(self):
        """
        Arrange : contrat en état 'sent'.
        Act     : action_reset_to_draft.
        Assert  : UserError levée.
        """
        # Arrange
        contract = self._make_contract(state='sent')

        # Act + Assert
        with self.assertRaises(UserError):
            contract.action_reset_to_draft()

    # ─────────────────────────────────────────────────────────────
    # Test 7 — _compute_amounts exclut les POs brouillon
    # ─────────────────────────────────────────────────────────────

    def test_compute_amounts_excludes_draft_pos(self):
        """
        Arrange : contrat avec 1 PO confirmé (5 000 €) + 1 PO brouillon (3 000 €).
        Act     : recomputer _compute_amounts (via invalidation de cache).
        Assert  : total_amount_ht == 5 000 (PO brouillon exclu).
        """
        # Arrange
        contract = self._make_contract()

        # PO confirmé : 5 000 €
        po_confirmed = self.env['purchase.order'].create({
            'partner_id': self.subcontractor.id,
            'date_order': date.today(),
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'name': 'Prestation confirmée',
                'product_qty': 1,
                'price_unit': 5000.0,
            })],
        })
        po_confirmed.button_confirm()

        # PO brouillon : 3 000 €
        po_draft = self.env['purchase.order'].create({
            'partner_id': self.subcontractor.id,
            'date_order': date.today(),
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'name': 'Prestation brouillon',
                'product_qty': 1,
                'price_unit': 3000.0,
            })],
        })
        # po_draft reste en état 'draft'

        contract.write({
            'purchase_order_ids': [(6, 0, [po_confirmed.id, po_draft.id])],
        })

        # Act : forcer le recalcul
        contract.invalidate_recordset()
        _ = contract.total_amount_ht

        # Assert
        self.assertAlmostEqual(
            contract.total_amount_ht,
            5000.0,
            places=2,
            msg="Seul le PO confirmé doit contribuer au montant HT.",
        )
        self.assertAlmostEqual(
            contract.total_amount_ht + contract.total_amount_tva,
            contract.total_amount_ttc,
            places=2,
            msg="HT + TVA doit être égal au TTC.",
        )

    # ─────────────────────────────────────────────────────────────
    # Test 8 — _compute_amounts n'utilise pas write() (pas de RecursionError)
    # ─────────────────────────────────────────────────────────────

    def test_compute_amounts_uses_direct_assignment_not_write(self):
        """
        Arrange : contrat avec 1 PO confirmé.
        Act     : déclencher le recalcul de _compute_amounts.
        Assert  : pas de RecursionError, valeurs cohérentes.
        """
        # Arrange
        contract = self._make_contract()

        po = self.env['purchase.order'].create({
            'partner_id': self.subcontractor.id,
            'date_order': date.today(),
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'name': 'Prestation test',
                'product_qty': 2,
                'price_unit': 1000.0,
            })],
        })
        po.button_confirm()
        contract.write({'purchase_order_ids': [(4, po.id)]})

        # Act : pas d'exception RecursionError attendu
        try:
            contract.invalidate_recordset()
            ht = contract.total_amount_ht
            ttc = contract.total_amount_ttc
            retention = contract.retention_amount
        except RecursionError as exc:
            self.fail(
                f"_compute_amounts a déclenché une RecursionError (write() interdit dans depends) : {exc}"
            )

        # Assert : valeurs cohérentes
        self.assertGreaterEqual(ht, 0.0)
        self.assertGreaterEqual(ttc, ht)
        self.assertAlmostEqual(
            retention,
            ttc * (contract.retention_rate / 100.0),
            places=2,
        )
