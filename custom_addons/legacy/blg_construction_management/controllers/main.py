# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class ConstructionController(http.Controller):
    """
    Controller for construction management public routes
    """
    
    @http.route(['/construction/projects'], type='http', auth="user", website=True)
    def construction_projects(self, **kwargs):
        """Display construction projects for the current user"""
        projects = request.env['blg.chantier'].search([
            ('user_ids', 'in', request.env.user.id)
        ])
        
        return request.render('blg_construction_management.construction_projects', {
            'projects': projects,
        })
