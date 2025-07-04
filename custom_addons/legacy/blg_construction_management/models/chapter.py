# -*- coding: utf-8 -*-
"""
blg_construction_management.models.chapter
-----------------------------------------

Defines the BlgChapter model, representing workflow chapters (phases) for construction projects in BLG Groupe.

Features:
---------
- Represents a major phase or chapter in the project workflow.
- Supports ordering via a sequence field.
- Each chapter can have multiple stages (see blg.stage).
- Ensures unique codes for chapters.

Class:
------
BlgChapter (models.Model)
    Main entity for project chapters/phases.

Fields:
-------
- name: Name of the chapter/phase.
- code: Unique code for the chapter.
- sequence: Ordering index for workflow.
- active: Active/inactive flag.
- stage_ids: One2many link to stages within this chapter.

Author: BLG IT Team
"""

from odoo import models, fields, api


class BlgChapter(models.Model):
    """
    Defines project chapters/phases for the workflow
    """
    _name = 'blg.chapter'
    _description = 'Project Chapter'
    _order = 'sequence'

    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True)
    sequence = fields.Integer('Sequence', default=10)
    active = fields.Boolean('Active', default=True)
    
    stage_ids = fields.One2many('blg.stage', 'chapter_id', string='Stages')

    _sql_constraints = [
        ('code_uniq', 'unique (code)', 'Chapter code must be unique!')
    ]

    @api.model
    def get_chapters_with_stages_data(self):
        """Return chapters with their stages and project counts for kanban view"""
        chapters = self.search([], order='sequence')
        result = []
        
        for chapter in chapters:
            stages = self.env['blg.stage'].search([('chapter_id', '=', chapter.id)], order='sequence')
            stage_data = []
            total_count = 0
            
            for stage in stages:
                count = self.env['blg.chantier'].search_count([('stage_id', '=', stage.id)])
                stage_data.append({
                    'id': stage.id,
                    'name': stage.name,
                    'code': stage.code,
                    'sequence': stage.sequence,
                    'count': count,
                    'fold': stage.fold
                })
                total_count += count
            
            result.append({
                'id': chapter.id,
                'name': chapter.name,
                'code': chapter.code,
                'sequence': chapter.sequence,
                'stages': stage_data,
                'total_count': total_count
            })
        
        return result

    @api.model
    def get_chapters_with_stages_and_chantiers(self):
        """Return complete structure for double kanban: chapters > stages > chantiers"""
        chapters = self.search([], order='sequence')
        result = []
        
        for chapter in chapters:
            stages = self.env['blg.stage'].search([('chapter_id', '=', chapter.id)], order='sequence')
            chapter_data = {
                'id': chapter.id,
                'name': chapter.name,
                'code': chapter.code,
                'sequence': chapter.sequence,
                'stages': [],
                'total_chantiers': 0
            }
            
            for stage in stages:
                chantiers_count = self.env['blg.chantier'].search_count([('stage_id', '=', stage.id)])
                stage_data = {
                    'id': stage.id,
                    'name': stage.name,
                    'code': stage.code,
                    'sequence': stage.sequence,
                    'fold': stage.fold,
                    'chantiers_count': chantiers_count,
                    'full_name': f"{chapter.name} - {stage.name}"
                }
                chapter_data['stages'].append(stage_data)
                chapter_data['total_chantiers'] += chantiers_count
            
            result.append(chapter_data)
        
        return result
