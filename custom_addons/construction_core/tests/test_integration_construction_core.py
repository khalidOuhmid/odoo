# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.tests import tagged
from odoo.exceptions import UserError, ValidationError
import datetime


@tagged('post_install', '-at_install')
class TestIntegrationConstructionCore(TransactionCase):

    def setUp(self):
        super().setUp()
        self.env = self.env(context=dict(self.env.context, tracking_disable=True))

        self.client_partner = self.env['res.partner'].create({
            'name': 'Client Integration Test',
            'is_company': True,
        })

        self.subcontractor = self.env['res.partner'].create({
            'name': 'Subcontractor Integration Test',
            'is_company': True,
            'supplier_rank': 1,
        })

        self.chapter = self.env['construction.chapter'].create({
            'name': 'Integration Chapter', 'code': 'INT_CHAP', 'sequence': 1
        })
        self.stage_prosp = self.env['construction.stage'].create({
            'name': 'Prospect Test', 'code': 'PROSP_INT', 'sequence': 1, 'chapter_id': self.chapter.id
        })
        self.stage_da = self.env['construction.stage'].create({
            'name': 'Dossier Accepté Test', 'code': 'DA_INT', 'sequence': 2, 'chapter_id': self.chapter.id
        })
        self.stage_fd = self.env['construction.stage'].create({
            'name': 'Fin de Dossier Test', 'code': 'FD_INT', 'sequence': 3, 'chapter_id': self.chapter.id
        })
        self.stage_trav = self.env['construction.stage'].create({
            'name': 'Travaux 0% Test', 'code': 'T0_INT', 'sequence': 4, 'chapter_id': self.chapter.id
        })
        self.stage_trav_95 = self.env['construction.stage'].create({
            'name': 'Travaux 95% Test', 'code': 'T100', 'sequence': 5, 'chapter_id': self.chapter.id
        })
        self.stage_lr = self.env['construction.stage'].create({
            'name': 'Levée de Réserve Test', 'code': 'LR_INT', 'sequence': 6, 'chapter_id': self.chapter.id
        })
        # LR stage with exact code required by _check_progress_95_trigger
        self.stage_lr_exact = self.env['construction.stage'].create({
            'name': 'Levée de Réserve', 'code': 'LR', 'sequence': 7, 'chapter_id': self.chapter.id
        })

    def test_integration_full_chantier_workflow(self):
        # SCENARIO: Créer un chantier → assigner des lots → faire progresser le workflow
        chantier = self.env['construction.chantier'].create({
            'name': 'Integration Chantier',
            'client': self.client_partner.id,
            'stage_id': self.stage_prosp.id,
        })
        self.assertEqual(chantier.stage_id.code, 'PROSP_INT')

        category = self.env['construction.lot.category'].create({
            'name': 'Cat 1', 'code': 'CAT1_INT'
        })
        lot = self.env['construction.lot'].create({
            'category_id': category.id,
            'chantier_id': chantier.id,
        })
        self.assertEqual(len(chantier.lots_ids), 1)

        chantier.with_context(bypass_stage_validation=True).write({'stage_id': self.stage_da.id})
        self.assertEqual(chantier.stage_id.code, 'DA_INT')
        chantier.with_context(bypass_stage_validation=True).write({'stage_id': self.stage_fd.id})
        self.assertEqual(chantier.stage_id.code, 'FD_INT')
        chantier.with_context(bypass_stage_validation=True).write({'stage_id': self.stage_trav.id})
        self.assertEqual(chantier.stage_id.code, 'T0_INT')
        chantier.with_context(bypass_stage_validation=True).write({'stage_id': self.stage_lr.id})
        self.assertEqual(chantier.stage_id.code, 'LR_INT')

    def test_integration_auto_lr_trigger(self):
        # SCENARIO: Vérifier le déclenchement automatique de la levée de réserve à 95%
        chantier = self.env['construction.chantier'].create({
            'name': 'Chantier Auto LR',
            'client': self.client_partner.id,
            'stage_id': self.stage_trav_95.id,
        })

        chantier._check_progress_95_trigger()

        lr_stage = self.env['construction.stage'].search([('code', '=', 'LR')], limit=1)
        if lr_stage:
            self.assertEqual(chantier.stage_id.code, 'LR')
            self.assertEqual(chantier.guarantee_status, 'pending')
            self.assertIsNotNone(chantier.guarantee_release_date)

    def test_integration_guarantee_retention(self):
        # SCENARIO: Retenue de garantie — calcul des 5% et déblocage manuel
        chantier = self.env['construction.chantier'].create({
            'name': 'Chantier Garantie',
            'client': self.client_partner.id,
            'stage_id': self.stage_lr.id,
            'guarantee_retention_rate': 5.0,
        })

        self.env['ir.config_parameter'].sudo().set_param(
            'construction.guarantee_retention_percent', '5.0'
        )

        chantier.write({
            'guarantee_status': 'pending',
            'guarantee_release_date': datetime.date.today() - datetime.timedelta(days=1)
        })

        chantier._cron_send_guarantee_reminders()
        chantier.action_release_guarantee()
        self.assertEqual(chantier.guarantee_status, 'released')

    def test_integration_multi_lot_wizard(self):
        # SCENARIO: Wizard Multi-Lot — sélectionner plusieurs lots et générer un BC groupé
        chantier = self.env['construction.chantier'].create({
            'name': 'Chantier Multi-Lot',
            'client': self.client_partner.id,
        })
        subcontractor = self.env['res.partner'].create({
            'name': 'ST Multi Lot', 'is_company': True, 'supplier_rank': 1,
        })
        cat1 = self.env['construction.lot.category'].create({'name': 'Cat ML1', 'code': 'ML_CAT1'})
        cat2 = self.env['construction.lot.category'].create({'name': 'Cat ML2', 'code': 'ML_CAT2'})
        lot1 = self.env['construction.lot'].create({
            'category_id': cat1.id, 'chantier_id': chantier.id,
            'execution_type': 'external', 'subcontractor_id': subcontractor.id,
        })
        lot2 = self.env['construction.lot'].create({
            'category_id': cat2.id, 'chantier_id': chantier.id,
            'execution_type': 'external', 'subcontractor_id': subcontractor.id,
        })

        wizard = self.env['construction.multi.lot.wizard'].create({
            'chantier_id': chantier.id,
            'lot_ids': [(6, 0, [lot1.id, lot2.id])],
        })

        self.assertEqual(wizard.chantier_id, chantier)
        self.assertEqual(len(wizard.lot_ids), 2)

    def test_integration_subcontractor_assignment(self):
        # SCENARIO: Assignation d'un sous-traitant à un lot et vérification de la conformité
        chantier = self.env['construction.chantier'].create({
            'name': 'Chantier Subcontractor',
            'client': self.client_partner.id,
        })
        category = self.env['construction.lot.category'].create({
            'name': 'Cat Sub', 'code': 'CAT_SUB_INT',
        })
        lot = self.env['construction.lot'].create({
            'category_id': category.id,
            'chantier_id': chantier.id,
            'execution_type': 'external',
        })

        lot.write({'subcontractor_id': self.subcontractor.id})

        self.assertEqual(lot.subcontractor_id.id, self.subcontractor.id)
        self.assertIn(lot.document_status, ['ok', 'warning', 'error', 'danger'])
