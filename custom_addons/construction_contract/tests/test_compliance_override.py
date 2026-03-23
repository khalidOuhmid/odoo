# -*- coding: utf-8 -*-
"""
Tests du wizard de dérogation conformité documentaire.

Scénarios couverts :
- TC-CO-01 : wizard ouvert pour admin (succès)
- TC-CO-02 : wizard bloqué pour group_construction_user (blocage total)
- TC-CO-03 : raison trop courte → UserError
- TC-CO-04 : log créé après confirmation admin
- TC-CO-05 : message_post posté sur le chantier après confirmation
"""

from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError, AccessError
from .common import ContractTestMixin
import base64
from datetime import date, timedelta


@tagged('post_install', '-at_install', 'construction_contract_compliance')
class TestComplianceOverride(TransactionCase, ContractTestMixin):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.setUpContractData()

        # Sous-traitant NON conforme (documents expirés / manquants)
        cls.subcontractor_nc = cls.env['res.partner'].create({
            'name': 'SARL Non Conforme Test',
            'is_company': True,
            'email': 'nc@example.com',
            'supplier_rank': 1,
            'company_registry': '99999999999999',
        })
        # Pas de documents → statuts = 'missing'

        # Contrat lié au sous-traitant non conforme avec bypass pour pouvoir créer
        cls.contract_nc = cls.env['construction.contract'].create({
            'subcontractor_id': cls.subcontractor_nc.id,
            'chantier_id': cls.chantier.id,
            'lot_ids': [(6, 0, [cls.lot2.id])],
            'template_id': cls.template.id,
            'state': 'draft',
            'date': date.today(),
            'start_date': date.today(),
            'end_date': date.today() + timedelta(days=180),
            'retention_rate': 5.0,
            'bypass_compliance_check': True,   # Bypass pour permettre la création en test
        })

        # Utilisateurs de test
        cls.group_admin = cls.env.ref('construction_core.group_construction_admin')
        cls.group_user = cls.env.ref('construction_core.group_construction_user')
        cls.group_pilote = cls.env.ref('construction_contract.group_construction_pilote')

        cls.user_admin = cls.env['res.users'].create({
            'name': 'Admin Test CO',
            'login': 'admin_co_test@blg.com',
            'email': 'admin_co_test@blg.com',
            'groups_id': [(4, cls.group_admin.id)],
        })
        cls.user_regular = cls.env['res.users'].create({
            'name': 'User Test CO',
            'login': 'user_co_test@blg.com',
            'email': 'user_co_test@blg.com',
            'groups_id': [(4, cls.group_user.id)],
        })

    # ─── TC-CO-01 : wizard ouvert pour admin ─────────────────────────

    def test_co_01_wizard_open_for_admin(self):
        """TC-CO-01 — L'admin peut créer le wizard sans erreur."""
        with self.with_user('admin_co_test@blg.com'):
            wiz = self.env['construction.compliance.override.wizard'].create({
                'contract_id': self.contract_nc.id,
                'partner_id': self.subcontractor_nc.id,
                'non_compliant_docs': 'URSSAF manquant\nKBIS manquant',
                'override_reason': 'Raison suffisante pour la dérogation admin test',
            })
            self.assertTrue(wiz.id, "Le wizard doit être créé")
            self.assertEqual(wiz.override_by_id, self.user_admin)

    # ─── TC-CO-02 : blocage total pour group_construction_user ────────

    def test_co_02_user_cannot_confirm(self):
        """TC-CO-02 — group_construction_user ne peut pas confirmer la dérogation."""
        wiz = self.env['construction.compliance.override.wizard'].sudo().create({
            'contract_id': self.contract_nc.id,
            'partner_id': self.subcontractor_nc.id,
            'non_compliant_docs': 'KBIS manquant',
            'override_reason': 'Raison suffisante pour la dérogation test utilisateur',
        })
        # L'utilisateur standard tente de confirmer
        with self.with_user('user_co_test@blg.com'):
            with self.assertRaises(UserError, msg="Un utilisateur standard doit être bloqué"):
                wiz.with_user(self.user_regular).action_confirm_override()

    # ─── TC-CO-03 : raison trop courte → UserError ────────────────────

    def test_co_03_short_reason_raises_error(self):
        """TC-CO-03 — Override_reason < 20 caractères lève UserError."""
        with self.assertRaises((UserError, ValidationError)):
            self.env['construction.compliance.override.wizard'].create({
                'contract_id': self.contract_nc.id,
                'partner_id': self.subcontractor_nc.id,
                'non_compliant_docs': 'URSSAF',
                'override_reason': 'Trop court',   # < 20 chars
            })

    # ─── TC-CO-04 : log créé après confirmation admin ─────────────────

    def test_co_04_log_created_after_confirmation(self):
        """TC-CO-04 — Un enregistrement ComplianceOverrideLog est créé à la confirmation."""
        count_before = self.env['construction.compliance.override.log'].search_count([])

        wiz = self.env['construction.compliance.override.wizard'].sudo().create({
            'contract_id': self.contract_nc.id,
            'partner_id': self.subcontractor_nc.id,
            'non_compliant_docs': 'URSSAF manquant',
            'override_reason': 'Urgence chantier — documents en cours de renouvellement',
            'override_by_id': self.user_admin.id,
        })
        # Confirmer en tant qu'admin
        wiz.with_user(self.user_admin).action_confirm_override()

        count_after = self.env['construction.compliance.override.log'].search_count([])
        self.assertEqual(count_after, count_before + 1, "Un log doit être créé")

        log = self.env['construction.compliance.override.log'].search(
            [('contract_id', '=', self.contract_nc.id)], limit=1
        )
        self.assertTrue(log, "Le log doit être lié au contrat")
        self.assertEqual(log.partner_id, self.subcontractor_nc)
        self.assertIn('URSSAF', log.non_compliant_docs)

    # ─── TC-CO-05 : message_post sur chantier ─────────────────────────

    def test_co_05_message_posted_on_chantier(self):
        """TC-CO-05 — Un message est posté sur le chantier après confirmation."""
        messages_before = self.env['mail.message'].search_count([
            ('res_id', '=', self.chantier.id),
            ('model', '=', 'construction.chantier'),
            ('body', 'ilike', 'Dérogation'),
        ])

        wiz = self.env['construction.compliance.override.wizard'].sudo().create({
            'contract_id': self.contract_nc.id,
            'partner_id': self.subcontractor_nc.id,
            'non_compliant_docs': 'Assurance Décennale expirée',
            'override_reason': 'Renouvellement assurance en cours, attestation provisoire fournie',
            'override_by_id': self.user_admin.id,
        })
        wiz.with_user(self.user_admin).action_confirm_override()

        messages_after = self.env['mail.message'].search_count([
            ('res_id', '=', self.chantier.id),
            ('model', '=', 'construction.chantier'),
            ('body', 'ilike', 'Dérogation'),
        ])
        self.assertGreater(messages_after, messages_before,
                           "Un message de dérogation doit être posté sur le chantier")

    # ─── TC-CO-06 : log ne peut pas être supprimé ─────────────────────

    def test_co_06_log_cannot_be_deleted(self):
        """TC-CO-06 — Le journal de dérogation est immuable (unlink interdit)."""
        log = self.env['construction.compliance.override.log'].sudo().create({
            'partner_id': self.subcontractor_nc.id,
            'chantier_id': self.chantier.id,
            'non_compliant_docs': 'Test immuabilité',
            'override_reason': 'Raison de test de suppression interdite ici',
            'override_by_id': self.user_admin.id,
        })
        from odoo.exceptions import AccessError
        with self.assertRaises(AccessError):
            log.unlink()
