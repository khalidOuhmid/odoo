# -*- coding: utf-8 -*-
"""
Shared base class for all construction_core test suites.

Eliminates setUp duplication across test files. All test classes
should inherit from ConstructionCoreTestBase instead of TransactionCase.

Available fixtures
------------------
self.chapter        construction.chapter  (code=BST_CH)
self.stage          construction.stage    (code=BST_S1, seq=10)
self.stage2         construction.stage    (code=BST_S2, seq=20)
self.client         res.partner           (is_company=True)
self.subcontractor  res.partner           (supplier_rank=1)
self.chantier       construction.chantier (in self.stage)
self.category       construction.lot.category
self.lot            construction.lot      (external, price=10000)
"""

from odoo.tests.common import TransactionCase


class ConstructionCoreTestBase(TransactionCase):

    def setUp(self):
        super().setUp()
        self.env = self.env(context=dict(self.env.context, tracking_disable=True))

        self.chapter = self.env['construction.chapter'].create({
            'name': 'Base Test Chapter',
            'code': 'BST_CH',
            'sequence': 10,
        })
        self.stage = self.env['construction.stage'].create({
            'name': 'Base Stage 1',
            'code': 'BST_S1',
            'chapter_id': self.chapter.id,
            'sequence': 10,
        })
        self.stage2 = self.env['construction.stage'].create({
            'name': 'Base Stage 2',
            'code': 'BST_S2',
            'chapter_id': self.chapter.id,
            'sequence': 20,
        })
        self.client = self.env['res.partner'].create({
            'name': 'Client Base Test',
            'is_company': True,
        })
        self.subcontractor = self.env['res.partner'].create({
            'name': 'Subcontractor Base Test',
            'is_company': True,
            'supplier_rank': 1,
        })
        self.chantier = self.env['construction.chantier'].create({
            'name': 'Chantier Base Test',
            'client': self.client.id,
            'stage_id': self.stage.id,
        })
        self.category = self.env['construction.lot.category'].create({
            'name': 'Category Base Test',
            'code': 'CAT_BASE',
        })
        self.lot = self.env['construction.lot'].create({
            'category_id': self.category.id,
            'chantier_id': self.chantier.id,
            'execution_type': 'external',
            'subcontractor_id': self.subcontractor.id,
            'price': 10000.0,
        })
