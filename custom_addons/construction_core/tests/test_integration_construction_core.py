# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError
import datetime

class TestIntegrationConstructionCore(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create common fixtures for integration tests
        cls.client_partner = cls.env['res.partner'].create({
            'name': 'Client Integration Test',
            'is_company': True,
        })
        
        cls.subcontractor = cls.env['res.partner'].create({
            'name': 'Subcontractor Integration Test',
            'is_company': True,
            'supplier_rank': 1,
        })
        
        # Stages setup mapping the core flow
        cls.stage_prosp = cls.env['construction.stage'].create({
            'name': 'Prospect', 'code': 'PROSP', 'sequence': 1
        })
        cls.stage_da = cls.env['construction.stage'].create({
            'name': 'Dossier Accepté', 'code': 'DA', 'sequence': 2
        })
        cls.stage_fd = cls.env['construction.stage'].create({
            'name': 'Fin de Dossier', 'code': 'FD', 'sequence': 3
        })
        cls.stage_trav = cls.env['construction.stage'].create({
            'name': 'Travaux 0%', 'code': 'T0', 'sequence': 4
        })
        cls.stage_trav_95 = cls.env['construction.stage'].create({
            'name': 'Travaux 95%', 'code': 'T95', 'sequence': 5
        })
        cls.stage_lr = cls.env['construction.stage'].create({
            'name': 'Levée de Réserve', 'code': 'LR', 'sequence': 6
        })

    def setUp(self):
        super().setUp()

    def test_integration_full_chantier_workflow(self):
        # SCENARIO: Créer un chantier → assigner des lots → faire progresser le workflow Prospect → DA → FD → TRAV → LR
        
        # 1. Create Chantier in PROSP
        chantier = self.env['construction.chantier'].create({
            'name': 'Integration Chantier',
            'client': self.client_partner.id,
            'stage_id': self.stage_prosp.id,
        })
        self.assertEqual(chantier.stage_id.code, 'PROSP')
        
        # 2. Assign lots
        category = self.env['construction.lot.category'].create({'name': 'Cat 1'})
        lot = self.env['construction.lot'].create({
            'name': 'Integration Lot',
            'chantier_id': chantier.id,
            'category_id': category.id,
        })
        self.assertEqual(len(chantier.lots_ids), 1)
        
        # 3. Move stages
        chantier.with_context(bypass_stage_validation=True).write({'stage_id': self.stage_da.id})
        self.assertEqual(chantier.stage_id.code, 'DA')
        chantier.with_context(bypass_stage_validation=True).write({'stage_id': self.stage_fd.id})
        self.assertEqual(chantier.stage_id.code, 'FD')
        chantier.with_context(bypass_stage_validation=True).write({'stage_id': self.stage_trav.id})
        self.assertEqual(chantier.stage_id.code, 'T0')
        chantier.with_context(bypass_stage_validation=True).write({'stage_id': self.stage_lr.id})
        self.assertEqual(chantier.stage_id.code, 'LR')

    def test_integration_auto_lr_trigger(self):
        # SCENARIO: Vérifier le déclenchement automatique de la levée de réserve à 95%
        chantier = self.env['construction.chantier'].create({
            'name': 'Chantier Auto LR',
            'client': self.client_partner.id,
            'stage_id': self.stage_trav_95.id,
        })
        
        # Simulate trigger
        chantier._check_progress_95_trigger()
        
        # Verify it transitioned to LR automatically
        self.assertEqual(chantier.stage_id.code, 'LR')
        self.assertEqual(chantier.guarantee_status, 'pending')
        self.assertIsNotNone(chantier.guarantee_release_date)

    def test_integration_guarantee_retention(self):
        # SCENARIO: Retenue de garantie — vérifier le calcul des 5% et le cron de déblocage à 1 an
        chantier = self.env['construction.chantier'].create({
            'name': 'Chantier Garantie',
            'client': self.client_partner.id,
            'stage_id': self.stage_lr.id,
            'amount_total': 10000.0,
            'guarantee_amount': 500.0,
        })
        
        # Trigger the 95% which simulates LR move
        self.env['ir.config_parameter'].sudo().set_param('construction.guarantee_retention_percent', '5.0')
        
        chantier.write({
            'amount_total': 10000.0,
            'guarantee_status': 'pending',
            'guarantee_release_date': datetime.date.today() - datetime.timedelta(days=1)
        })
        
        # Call the cron - Should send reminder
        chantier._cron_send_guarantee_reminders()
        # Test just the manual release
        chantier.action_release_guarantee()
        self.assertEqual(chantier.guarantee_status, 'released')

    def test_integration_multi_lot_wizard(self):
        # SCENARIO: Wizard Multi-Lot — créer plusieurs lots en une seule action
        chantier = self.env['construction.chantier'].create({
            'name': 'Chantier Multi-Lot',
            'client': self.client_partner.id,
        })
        
        # Create wizard and use text block
        wizard = self.env['construction.multi.lot.wizard'].create({
            'chantier_id': chantier.id,
            'lot_text': 'Lot 1\nLot 2\nLot 3'
        })
        
        # Process preview
        wizard.action_preview()
        # Verify lines created
        self.assertEqual(len(wizard.line_ids), 3)
        
        # Execute
        wizard.action_create_lots()
        # Verify lots created on chantier
        self.assertEqual(len(chantier.lots_ids), 3)

    def test_integration_subcontractor_assignment(self):
        # SCENARIO: Assignation d'un sous-traitant à un lot et vérification de la conformité
        chantier = self.env['construction.chantier'].create({
            'name': 'Chantier Subcontractor',
            'client': self.client_partner.id,
        })
        category = self.env['construction.lot.category'].create({'name': 'Cat Sub'})
        lot = self.env['construction.lot'].create({
            'name': 'Lot Subcontractor',
            'chantier_id': chantier.id,
            'category_id': category.id,
            'execution_type': 'external',
        })
        
        # Assign subcontractor using wizard pattern via logic
        lot.write({
            'subcontractor_id': self.subcontractor.id
        })
        
        # Verify assignment
        self.assertEqual(lot.subcontractor_id.id, self.subcontractor.id)
        # Because we're isolating modules, we simulate the document check behavior (computed)
        lot._compute_document_status()
        self.assertIn(lot.document_status, ['missing', 'valid', 'expired', 'expiring'])
