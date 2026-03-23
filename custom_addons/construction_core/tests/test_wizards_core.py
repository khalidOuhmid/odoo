# -*- coding: utf-8 -*-
"""
Tests for construction_core wizards:
- SansSuiteWizard
- ForceStageWizard
- LotSubcontractorAssignWizard
- MultiLotWizard
"""
from odoo.tests.common import TransactionCase
from odoo.tests import tagged
from odoo.exceptions import UserError, ValidationError


@tagged('post_install', '-at_install')
class TestSansSuiteWizard(TransactionCase):

    def setUp(self):
        super().setUp()
        self.env = self.env(context=dict(self.env.context, tracking_disable=True))

        self.partner = self.env['res.partner'].create({'name': 'SS Client'})
        self.chapter = self.env['construction.chapter'].create({
            'name': 'SS Chapter', 'code': 'SS_CHAP', 'sequence': 80,
        })
        self.stage = self.env['construction.stage'].create({
            'name': 'SS Test Stage', 'code': 'SS_STAG', 'sequence': 10, 'chapter_id': self.chapter.id,
        })
        # Create SS stage required by action_confirm
        self.stage_ss = self.env['construction.stage'].create({
            'name': 'Sans Suite', 'code': 'SS', 'sequence': 99, 'chapter_id': self.chapter.id,
        })
        self.chantier = self.env['construction.chantier'].create({
            'name': 'Chantier Sans Suite Test',
            'client': self.partner.id,
            'stage_id': self.stage.id,
        })

    def test_action_confirm_classifies_chantier(self):
        # GIVEN a wizard with a valid reason
        wizard = self.env['construction.sans.suite.wizard'].create({
            'chantier_id': self.chantier.id,
            'reason': 'client_cancelled',
        })
        # WHEN confirming the wizard
        result = wizard.action_confirm()
        # THEN chantier is in SS stage and archived
        self.chantier.invalidate_recordset()
        self.assertEqual(self.chantier.with_context(active_test=False).stage_id.code, 'SS')
        self.assertFalse(self.chantier.with_context(active_test=False).active)
        self.assertEqual(self.chantier.with_context(active_test=False).sans_suite_reason, 'client_cancelled')

    def test_action_confirm_returns_notification(self):
        # GIVEN a wizard
        wizard = self.env['construction.sans.suite.wizard'].create({
            'chantier_id': self.chantier.id,
            'reason': 'budget_insufficient',
        })
        # WHEN confirming
        result = wizard.action_confirm()
        # THEN returns a display_notification action
        self.assertEqual(result['type'], 'ir.actions.client')
        self.assertEqual(result['tag'], 'display_notification')

    def test_action_confirm_with_details(self):
        # GIVEN a wizard with reason_details
        wizard = self.env['construction.sans.suite.wizard'].create({
            'chantier_id': self.chantier.id,
            'reason': 'competition',
            'reason_details': 'Concurrent moins cher',
        })
        # WHEN confirming
        wizard.action_confirm()
        # THEN sans_suite_details is stored
        self.assertEqual(
            self.chantier.with_context(active_test=False).sans_suite_details, 'Concurrent moins cher'
        )

    def test_reason_details_too_long(self):
        # GIVEN a wizard with reason_details exceeding 500 chars
        long_text = 'x' * 501
        # WHEN creating the wizard (constraint fires on create)
        # THEN UserError is raised
        with self.assertRaises(UserError):
            self.env['construction.sans.suite.wizard'].create({
                'chantier_id': self.chantier.id,
                'reason': 'other',
                'reason_details': long_text,
            })

    def test_reason_details_exactly_500_ok(self):
        # GIVEN reason_details of exactly 500 characters
        text_500 = 'y' * 500
        # WHEN creating
        wizard = self.env['construction.sans.suite.wizard'].create({
            'chantier_id': self.chantier.id,
            'reason': 'other',
            'reason_details': text_500,
        })
        # THEN no error
        self.assertTrue(wizard.id)

    def test_require_approval_high_value(self):
        # GIVEN a chantier with budget > 50000
        self.chantier.with_context(bypass_stage_validation=True).write({'budget_previsionnel': 60000.0})
        # WHEN creating wizard
        wizard = self.env['construction.sans.suite.wizard'].create({
            'chantier_id': self.chantier.id,
            'reason': 'other',
        })
        # THEN require_approval is True
        self.assertTrue(wizard.require_approval)

    def test_require_approval_low_value(self):
        # GIVEN a chantier with budget <= 50000
        self.chantier.with_context(bypass_stage_validation=True).write({'budget_previsionnel': 10000.0})
        wizard = self.env['construction.sans.suite.wizard'].create({
            'chantier_id': self.chantier.id,
            'reason': 'other',
        })
        # THEN require_approval is False
        self.assertFalse(wizard.require_approval)

    def test_action_cancel_closes_wizard(self):
        # GIVEN a wizard
        wizard = self.env['construction.sans.suite.wizard'].create({
            'chantier_id': self.chantier.id,
            'reason': 'other',
        })
        # WHEN cancelling
        result = wizard.action_cancel()
        # THEN returns window close action
        self.assertEqual(result['type'], 'ir.actions.act_window_close')


@tagged('post_install', '-at_install')
class TestForceStageWizard(TransactionCase):

    def setUp(self):
        super().setUp()
        self.env = self.env(context=dict(self.env.context, tracking_disable=True))

        self.chapter = self.env['construction.chapter'].create({
            'name': 'Force Stage Chapter', 'code': 'FS_CHAP', 'sequence': 90,
        })
        self.stage1 = self.env['construction.stage'].create({
            'name': 'Stage Force 1', 'code': 'FS_S1', 'sequence': 10, 'chapter_id': self.chapter.id,
        })
        self.stage2 = self.env['construction.stage'].create({
            'name': 'Stage Force 2', 'code': 'FS_S2', 'sequence': 20, 'chapter_id': self.chapter.id,
        })
        self.partner = self.env['res.partner'].create({'name': 'Force Stage Client'})
        self.chantier = self.env['construction.chantier'].create({
            'name': 'Chantier Force Stage',
            'client': self.partner.id,
            'stage_id': self.stage1.id,
        })

    def test_force_stage_with_admin_group(self):
        # GIVEN the current user has admin group
        admin_group = self.env.ref('construction_core.group_construction_admin', raise_if_not_found=False)
        if admin_group:
            self.env.user.sudo().write({'groups_id': [(4, admin_group.id)]})

        wizard = self.env['construction.force.stage.wizard'].create({
            'chantier_id': self.chantier.id,
            'current_stage_id': self.stage1.id,
            'new_stage_id': self.stage2.id,
            'reason': 'Urgent change for test purposes',
        })
        # WHEN forcing stage
        try:
            result = wizard.action_force_stage()
        except ValueError as e:
            if 'unsupported format character' in str(e):
                self.fail("MarkupSafe formatting bug: " + str(e))
            raise

        # THEN chantier is in new stage
        self.assertEqual(self.chantier.stage_id.id, self.stage2.id)

    def test_force_stage_without_admin_raises(self):
        # GIVEN the current user does NOT have admin group
        admin_group = self.env.ref('construction_core.group_construction_admin', raise_if_not_found=False)
        if admin_group and self.env.user.has_group('construction_core.group_construction_admin'):
            self.skipTest("User already has admin — cannot test the restriction")

        wizard = self.env['construction.force.stage.wizard'].create({
            'chantier_id': self.chantier.id,
            'current_stage_id': self.stage1.id,
            'new_stage_id': self.stage2.id,
            'reason': 'Should fail',
        })
        # WHEN forcing stage without admin
        # THEN UserError is raised
        with self.assertRaises(UserError):
            wizard.action_force_stage()


@tagged('post_install', '-at_install')
class TestLotSubcontractorAssignWizard(TransactionCase):

    def setUp(self):
        super().setUp()
        self.env = self.env(context=dict(self.env.context, tracking_disable=True))

        self.chapter = self.env['construction.chapter'].create({
            'name': 'LSA Chapter', 'code': 'LSA_CH', 'sequence': 95,
        })
        self.stage = self.env['construction.stage'].create({
            'name': 'LSA Stage', 'code': 'LSA_ST', 'sequence': 10, 'chapter_id': self.chapter.id,
        })
        self.category = self.env['construction.lot.category'].create({
            'name': 'Électricité LSA', 'code': 'LSA_ELEC',
        })
        self.partner = self.env['res.partner'].create({'name': 'LSA Client'})
        self.subcontractor = self.env['res.partner'].create({
            'name': 'LSA Subcontractor', 'supplier_rank': 1,
        })
        self.chantier = self.env['construction.chantier'].create({
            'name': 'Chantier LSA', 'client': self.partner.id, 'stage_id': self.stage.id,
        })

    def test_wizard_creates_new_lot(self):
        # GIVEN a wizard set to create a new lot
        wizard = self.env['construction.lot.subcontractor.assign.wizard'].create({
            'chantier_id': self.chantier.id,
            'lot_category_id': self.category.id,
            'subcontractor_id': self.subcontractor.id,
            'create_new_lot': True,
            'lot_price': 5000.0,
        })
        # WHEN assigning
        wizard.action_assign()
        # THEN lot is created with correct category and subcontractor
        lot = self.env['construction.lot'].search([
            ('chantier_id', '=', self.chantier.id),
            ('category_id', '=', self.category.id),
        ])
        self.assertEqual(len(lot), 1)
        self.assertEqual(lot.subcontractor_id.id, self.subcontractor.id)
        self.assertEqual(lot.price, 5000.0)

    def test_wizard_updates_existing_lot(self):
        # GIVEN an existing lot without subcontractor
        existing_lot = self.env['construction.lot'].create({
            'category_id': self.category.id,
            'chantier_id': self.chantier.id,
            'execution_type': 'external',
            'price': 1000.0,
        })
        wizard = self.env['construction.lot.subcontractor.assign.wizard'].create({
            'chantier_id': self.chantier.id,
            'lot_category_id': self.category.id,
            'existing_lot_id': existing_lot.id,
            'subcontractor_id': self.subcontractor.id,
            'create_new_lot': False,
        })
        # WHEN assigning
        wizard.action_assign()
        # THEN existing lot is updated (not a new one created)
        self.assertEqual(existing_lot.subcontractor_id.id, self.subcontractor.id)
        total_lots = self.env['construction.lot'].search_count([
            ('chantier_id', '=', self.chantier.id),
            ('category_id', '=', self.category.id),
        ])
        self.assertEqual(total_lots, 1)

    def test_wizard_adds_subcontractor_to_chantier(self):
        # GIVEN a wizard for a new lot
        wizard = self.env['construction.lot.subcontractor.assign.wizard'].create({
            'chantier_id': self.chantier.id,
            'lot_category_id': self.category.id,
            'subcontractor_id': self.subcontractor.id,
            'create_new_lot': True,
        })
        # WHEN assigning
        wizard.action_assign()
        # THEN subcontractor is added to chantier.subcontractor_ids
        self.assertIn(self.subcontractor, self.chantier.subcontractor_ids)

    def test_wizard_compute_warnings_duplicate_category(self):
        # GIVEN an existing lot with same category on chantier
        self.env['construction.lot'].create({
            'category_id': self.category.id,
            'chantier_id': self.chantier.id,
        })
        wizard = self.env['construction.lot.subcontractor.assign.wizard'].create({
            'chantier_id': self.chantier.id,
            'lot_category_id': self.category.id,
            'subcontractor_id': self.subcontractor.id,
            'create_new_lot': True,
        })
        # THEN wizard has a warning about duplicate category
        self.assertTrue(wizard.has_warnings)


@tagged('post_install', '-at_install')
class TestMultiLotWizard(TransactionCase):

    def setUp(self):
        super().setUp()
        self.env = self.env(context=dict(self.env.context, tracking_disable=True))

        self.partner = self.env['res.partner'].create({'name': 'ML Client'})
        self.subcontractor = self.env['res.partner'].create({
            'name': 'ML Subcontractor', 'supplier_rank': 1,
        })
        self.chantier = self.env['construction.chantier'].create({
            'name': 'Chantier Multi Lot', 'client': self.partner.id,
        })
        cat1 = self.env['construction.lot.category'].create({'name': 'ML Cat1', 'code': 'ML_C1'})
        cat2 = self.env['construction.lot.category'].create({'name': 'ML Cat2', 'code': 'ML_C2'})
        self.lot1 = self.env['construction.lot'].create({
            'category_id': cat1.id, 'chantier_id': self.chantier.id,
            'execution_type': 'external', 'subcontractor_id': self.subcontractor.id,
        })
        self.lot2 = self.env['construction.lot'].create({
            'category_id': cat2.id, 'chantier_id': self.chantier.id,
            'execution_type': 'external', 'subcontractor_id': self.subcontractor.id,
        })

    def test_multi_lot_wizard_creation(self):
        # GIVEN two lots to group
        wizard = self.env['construction.multi.lot.wizard'].create({
            'chantier_id': self.chantier.id,
            'lot_ids': [(6, 0, [self.lot1.id, self.lot2.id])],
        })
        # THEN wizard holds both lots
        self.assertEqual(wizard.chantier_id, self.chantier)
        self.assertEqual(len(wizard.lot_ids), 2)
        self.assertIn(self.lot1, wizard.lot_ids)
        self.assertIn(self.lot2, wizard.lot_ids)


# ================================================================
# ForceStageWizard — default_get
# ================================================================

@tagged('post_install', '-at_install')
class TestForceStageWizardDefaultGet(TransactionCase):

    def setUp(self):
        super().setUp()
        self.env = self.env(context=dict(self.env.context, tracking_disable=True))

        chapter = self.env['construction.chapter'].create({
            'name': 'DefaultGet Chapter', 'code': 'DGT_CH', 'sequence': 91,
        })
        self.stage = self.env['construction.stage'].create({
            'name': 'DGT Stage 1', 'code': 'DGT_S1',
            'chapter_id': chapter.id, 'sequence': 10,
        })
        partner = self.env['res.partner'].create({'name': 'DGT Client'})
        self.chantier = self.env['construction.chantier'].create({
            'name': 'Chantier DefaultGet Test',
            'client': partner.id,
            'stage_id': self.stage.id,
        })

    def test_default_get_loads_chantier_and_stage_from_context(self):
        # ARRANGE — active_model/active_id context mimics opening from the chantier form
        wizard_env = self.env['construction.force.stage.wizard'].with_context(
            active_model='construction.chantier',
            active_id=self.chantier.id,
        )
        # ACT
        defaults = wizard_env.default_get(['chantier_id', 'current_stage_id', 'new_stage_id'])
        # ASSERT — wizard pre-filled with current chantier and its stage
        self.assertEqual(defaults.get('chantier_id'), self.chantier.id)
        self.assertEqual(defaults.get('current_stage_id'), self.stage.id)

    def test_default_get_without_active_context_returns_no_chantier(self):
        # ARRANGE — no active_model in context
        wizard_env = self.env['construction.force.stage.wizard']
        # ACT
        defaults = wizard_env.default_get(['chantier_id', 'current_stage_id'])
        # ASSERT — chantier_id is absent or falsy
        self.assertFalse(defaults.get('chantier_id'))


# ================================================================
# SansSuiteWizard — _send_client_notification
# ================================================================

@tagged('post_install', '-at_install')
class TestSansSuiteClientNotification(TransactionCase):

    def setUp(self):
        super().setUp()
        self.env = self.env(context=dict(self.env.context, tracking_disable=True))

        chapter = self.env['construction.chapter'].create({
            'name': 'SS Notif Chapter', 'code': 'SSN_CH', 'sequence': 92,
        })
        self.stage = self.env['construction.stage'].create({
            'name': 'SSN Stage', 'code': 'SSN_ST', 'sequence': 10, 'chapter_id': chapter.id,
        })
        self.stage_ss = self.env['construction.stage'].create({
            'name': 'Sans Suite', 'code': 'SS', 'sequence': 99, 'chapter_id': chapter.id,
        })
        self.client = self.env['res.partner'].create({
            'name': 'Client Notification Test',
            'is_company': True,
            'email': 'client@test.com',
        })
        self.chantier = self.env['construction.chantier'].create({
            'name': 'Chantier SS Notification',
            'client': self.client.id,
            'stage_id': self.stage.id,
        })

    def test_send_client_notification_posts_message_on_chantier(self):
        # ARRANGE
        wizard = self.env['construction.sans.suite.wizard'].create({
            'chantier_id': self.chantier.id,
            'reason': 'client_cancelled',
            'client_email_template': 'Votre projet [CHANTIER] ne sera pas poursuivi.',
        })
        msg_count_before = len(self.chantier.message_ids)
        # ACT — call directly
        wizard._send_client_notification(self.chantier)
        # ASSERT — a new message was posted on the chantier thread
        self.assertGreater(len(self.chantier.message_ids), msg_count_before)

    def test_send_client_notification_replaces_chantier_placeholder(self):
        # ARRANGE
        wizard = self.env['construction.sans.suite.wizard'].create({
            'chantier_id': self.chantier.id,
            'reason': 'other',
            'client_email_template': 'Le projet [CHANTIER] est annulé.',
        })
        # ACT
        wizard._send_client_notification(self.chantier)
        # ASSERT — the last message body contains the actual chantier name
        last_msg = self.chantier.message_ids[0]
        self.assertIn(self.chantier.name, last_msg.body)

    def test_action_confirm_with_notify_client_skips_when_no_partner_email(self):
        # ARRANGE — client has no email, notify_client=True
        client_no_email = self.env['res.partner'].create({
            'name': 'No Email Client', 'is_company': True,
        })
        chantier_no_email = self.env['construction.chantier'].create({
            'name': 'Chantier No Email',
            'client': client_no_email.id,
            'stage_id': self.stage.id,
        })
        wizard = self.env['construction.sans.suite.wizard'].create({
            'chantier_id': chantier_no_email.id,
            'reason': 'budget_insufficient',
            'notify_client': True,
        })
        # ACT — should not raise even with notify_client=True and no partner email
        result = wizard.action_confirm()
        # ASSERT — action returned normally
        self.assertEqual(result.get('type'), 'ir.actions.client')
