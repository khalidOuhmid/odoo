# -*- coding: utf-8 -*-
"""
Tests for the stage guidance computed fields on construction.chantier.

Coverage:
- is_ready_for_next_stage  (Boolean computed, no store)
- next_stage_name          (Char computed, no store)
- next_stage_requirements  (Html computed, no store)

The four scenarios:
1. REC stage with missing required fields → not ready, requirements non-empty
2. REC stage with all required fields set → ready, requirements empty
3. SS terminal stage → not ready, no next stage name, requirements empty
4. DC terminal stage → no next stage name, requirements empty
"""
from odoo.tests import tagged
from odoo.addons.construction_core.tests.common import ConstructionCoreTestBase
from odoo.addons.construction_core.utils.logger import get_logger

_logger = get_logger(__name__)


@tagged('post_install', '-at_install')
class TestStageGuidance(ConstructionCoreTestBase):
    """Tests for is_ready_for_next_stage, next_stage_name, next_stage_requirements."""

    def setUp(self):
        super().setUp()

        # The base fixture creates custom stages (BST_S1 / BST_S2).
        # The compute methods key off stage.code against STAGE_TRANSITIONS.
        # We need real-code stages so the guidance logic can find validators
        # and resolve next-stage names.

        self.chapter_guidance = self.env['construction.chapter'].create({
            'name': 'Guidance Test Chapter',
            'code': 'GDN_CH',
            'sequence': 200,
        })

        # REC stage — has check_reception_stage validator, next = VT
        self.stage_rec = self.env['construction.stage'].create({
            'name': 'Réception (guidance test)',
            'code': 'REC',
            'chapter_id': self.chapter_guidance.id,
            'sequence': 10,
        })
        # VT stage — needed so next_stage_name can resolve to a name string
        self.stage_vt = self.env['construction.stage'].create({
            'name': 'Visite Technique (guidance test)',
            'code': 'VT',
            'chapter_id': self.chapter_guidance.id,
            'sequence': 20,
        })
        # SS stage — terminal (next=None in STAGE_TRANSITIONS)
        self.stage_ss = self.env['construction.stage'].create({
            'name': 'Sans Suite (guidance test)',
            'code': 'SS',
            'chapter_id': self.chapter_guidance.id,
            'sequence': 900,
        })
        # DC stage — terminal (next=None in STAGE_TRANSITIONS)
        self.stage_dc = self.env['construction.stage'].create({
            'name': 'Dossier Clôturé (guidance test)',
            'code': 'DC',
            'chapter_id': self.chapter_guidance.id,
            'sequence': 800,
        })

        # Dedicated chantier for guidance tests; starts at REC
        self.guidance_chantier = self.env['construction.chantier'].create({
            'name': 'Chantier Guidance Test',
            'client': self.client.id,
            'stage_id': self.stage_rec.id,
        })

    # ------------------------------------------------------------------ #
    # Test 1 — REC stage, required fields absent → not ready
    # ------------------------------------------------------------------ #

    def test_ready_false_when_missing_conditions(self):
        """is_ready_for_next_stage is False when required REC fields are absent."""
        # ARRANGE — client is set by fixture; ensure description and phone are absent
        self.guidance_chantier.with_context(bypass_stage_validation=True).write({
            'address': False,
            'description': False,
            'phone': False,
        })
        _logger.wizard_action(
            'TestStageGuidance',
            'test_ready_false_when_missing_conditions',
            record=self.guidance_chantier,
        )

        # ACT
        is_ready = self.guidance_chantier.is_ready_for_next_stage
        requirements = self.guidance_chantier.next_stage_requirements

        # ASSERT
        self.assertFalse(
            is_ready,
            "is_ready_for_next_stage doit être False quand address/description/phone manquent",
        )
        self.assertTrue(
            requirements,
            "next_stage_requirements doit être non-vide quand des conditions manquent",
        )

    # ------------------------------------------------------------------ #
    # Test 2 — REC stage, all required fields present → ready
    # ------------------------------------------------------------------ #

    def test_ready_true_when_all_conditions_met(self):
        """is_ready_for_next_stage is True when all REC required fields are filled."""
        # ARRANGE — fill the three fields checked by check_reception_stage
        self.guidance_chantier.with_context(bypass_stage_validation=True).write({
            'address': '10 Rue de la Paix, 75001 Paris',
            'description': 'Rénovation complète',
            'phone': '0601020304',
        })
        _logger.wizard_action(
            'TestStageGuidance',
            'test_ready_true_when_all_conditions_met',
            record=self.guidance_chantier,
        )

        # ACT
        is_ready = self.guidance_chantier.is_ready_for_next_stage
        requirements = self.guidance_chantier.next_stage_requirements

        # ASSERT
        self.assertTrue(
            is_ready,
            "is_ready_for_next_stage doit être True quand address, description et phone sont renseignés",
        )
        self.assertFalse(
            requirements,
            "next_stage_requirements doit être vide (falsy) quand toutes les conditions sont remplies",
        )

    # ------------------------------------------------------------------ #
    # Test 3 — SS terminal stage
    # ------------------------------------------------------------------ #

    def test_ss_stage_is_terminal_no_requirements(self):
        """Terminal SS stage: no next stage name, no requirements, not ready."""
        # ARRANGE — bypass validation to jump directly to SS
        self.guidance_chantier.with_context(bypass_stage_validation=True).write({
            'stage_id': self.stage_ss.id,
        })
        _logger.wizard_action(
            'TestStageGuidance',
            'test_ss_stage_is_terminal_no_requirements',
            record=self.guidance_chantier,
        )

        # ACT
        next_name = self.guidance_chantier.next_stage_name
        requirements = self.guidance_chantier.next_stage_requirements
        is_ready = self.guidance_chantier.is_ready_for_next_stage

        # ASSERT
        self.assertEqual(
            next_name,
            '',
            "next_stage_name doit être vide pour une étape terminale SS",
        )
        self.assertFalse(
            requirements,
            "next_stage_requirements doit être falsy pour une étape terminale SS",
        )
        self.assertFalse(
            is_ready,
            "is_ready_for_next_stage doit être False pour une étape terminale SS",
        )

    # ------------------------------------------------------------------ #
    # Test 4 — DC terminal stage
    # ------------------------------------------------------------------ #

    def test_dc_stage_is_terminal_no_requirements(self):
        """Terminal DC stage: no next stage name, no requirements."""
        # ARRANGE — bypass validation to jump directly to DC
        self.guidance_chantier.with_context(bypass_stage_validation=True).write({
            'stage_id': self.stage_dc.id,
        })
        _logger.wizard_action(
            'TestStageGuidance',
            'test_dc_stage_is_terminal_no_requirements',
            record=self.guidance_chantier,
        )

        # ACT
        next_name = self.guidance_chantier.next_stage_name
        requirements = self.guidance_chantier.next_stage_requirements

        # ASSERT
        self.assertEqual(
            next_name,
            '',
            "next_stage_name doit être vide pour une étape terminale DC",
        )
        self.assertFalse(
            requirements,
            "next_stage_requirements doit être falsy pour une étape terminale DC",
        )
