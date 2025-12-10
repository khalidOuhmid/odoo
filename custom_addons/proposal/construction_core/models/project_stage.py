# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ConstructionChapter(models.Model):
    _name = 'construction.chapter'
    _description = 'Construction Chapter'
    _order = 'sequence, id'

    name = fields.Char(string='Nom', required=True, translate=True)
    code = fields.Char(string='Code', required=True)
    description = fields.Text(string='Description', translate=True)
    sequence = fields.Integer(default=10)
    color = fields.Integer(string='Couleur')
    is_default = fields.Boolean(default=False)
    active = fields.Boolean(default=True)

class ConstructionStage(models.Model):
    """
    Gestion des étapes de chantier/lot (State Machine).
    Permet de définir des workflows dynamiques avec validation stricte.
    """
    _name = 'construction.stage'
    _description = 'Construction Stage'
    _order = 'sequence, id'

    name = fields.Char(string='Nom de l\'étape', required=True, translate=True)
    code = fields.Char(string='Code Technique', required=True, help="Utilisé pour les références techniques (ex: AO, REC)")
    description = fields.Text(string='Description', translate=True)
    sequence = fields.Integer(default=10)
    
    # UI Logic
    fold = fields.Boolean(string='Replié en Kanban')
    color = fields.Integer(string='Couleur')
    active = fields.Boolean(default=True)
    
    # Hierarchy
    chapter_id = fields.Many2one('construction.chapter', string='Chapitre', ondelete='restrict')
    
    # Workflow Logic
    is_closed = fields.Boolean(string='Marque la clôture', help="Les enregistrements dans cette étape sont considérés comme terminés")
    validation_info = fields.Text(string='Critères de Validation', help="Liste des critères à vérifier pour passer cette étape")
    
    # Strategy Pattern Link
    validator_model = fields.Char(
        string="Modèle de Validation", 
        help="Nom technique du modèle implémentant la validation (ex: construction.validator.reception)"
    )

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Le code de l\'étape doit être unique.')
    ]
