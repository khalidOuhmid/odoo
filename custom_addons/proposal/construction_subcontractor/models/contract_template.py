# -*- coding: utf-8 -*-
from odoo import models, fields

class ConstructionContractTemplate(models.Model):
    """
    Modèle de Contrat (Template).
    Permet de définir des modèles HTML réutilisables avec Jinja2/QWeb.
    """
    _name = 'construction.contract.template'
    _description = 'Construction Contract Template'
    _order = 'name asc'

    name = fields.Char(string='Template Name', required=True)
    
    # CONTENT
    body_html = fields.Html(string='Body Content', sanitize=False, required=True, translate=True)
    header_html = fields.Html(string='Header', sanitize=False, translate=True)
    footer_html = fields.Html(string='Footer', sanitize=False, translate=True)
    
    active = fields.Boolean(default=True)
    
    contract_count = fields.Integer(compute='_compute_contract_count')

    def _compute_contract_count(self):
        for template in self:
            template.contract_count = self.env['construction.contract'].search_count([('template_id', '=', template.id)])
