# -*- coding: utf-8 -*-
"""
blg_construction_management.models.stage
---------------------------------------

Defines the BlgStage model, representing workflow stages within chapters for construction projects in BLG Groupe.

Features:
---------
- Represents a specific stage within a project chapter.
- Supports ordering and grouping via sequence and chapter.
- Each stage can be folded in Kanban views.
- Ensures unique codes for stages.
- Provides progress tracking for each stage.

Class:
------
BlgStage (models.Model)
    Main entity for project workflow stages.

Fields:
-------
- name: Name of the stage.
- code: Unique code for the stage.
- chapter_id: Many2one to blg.chapter (parent chapter).
- sequence: Ordering index within the chapter.
- active: Active/inactive flag.
- progress: Integer progress percentage for the stage.
- fold: Boolean for Kanban folding.

Methods:
--------
- _group_by_full: Used for grouping in Kanban and views.

Author: BLG IT Team
"""

from odoo import models, fields, api


class BlgStage(models.Model):
    """
    Defines project stages within chapters
    """
    _name = 'blg.stage'
    _description = 'Project Stage'
    _order = 'chapter_id, sequence'

    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True)
    chapter_id = fields.Many2one('blg.chapter', string='Chapter', required=True)
    sequence = fields.Integer('Sequence', default=10)
    active = fields.Boolean('Active', default=True)
    progress = fields.Integer('Progress (%)', default=0)
    fold = fields.Boolean('Folded in Kanban', default=False)

    _sql_constraints = [
        ('code_uniq', 'unique (code)', 'Stage code must be unique!')
    ]

    @api.model
    def _group_by_full(self, field, **kwargs):
        if field == 'stage_id':
            stages = self.search([])
            return ([(stage.id, stage.name) for stage in stages],
                    {stage.id: stage.fold for stage in stages})
        return super()._group_by_full(field, **kwargs)

    def name_get(self):
        """Return stage name with chapter prefix for better identification"""
        result = []
        for record in self:
            if record.chapter_id:
                name = f"{record.chapter_id.name} - {record.name}"
            else:
                name = record.name
            result.append((record.id, name))
        return result

    @api.model
    def _read_group_stage_ids(self, stages, domain, order=None):
        """Retourne tous les stages pour le group_expand, groupés par chapitre"""
        return self.search([], order=order or 'chapter_id, sequence')
    
    @api.model
    def get_stages_with_chapter_info(self):
        """Return stages with chapter information for kanban grouping"""
        stages = self.search([], order='chapter_id, sequence')
        result = []
        
        for stage in stages:
            result.append({
                'id': stage.id,
                'name': stage.name,
                'code': stage.code,
                'sequence': stage.sequence,
                'chapter_id': stage.chapter_id.id,
                'chapter_name': stage.chapter_id.name,
                'chapter_code': stage.chapter_id.code,
                'chapter_sequence': stage.chapter_id.sequence,
                'full_name': f"{stage.chapter_id.name} - {stage.name}",
                'fold': stage.fold
            })
        
        return result
