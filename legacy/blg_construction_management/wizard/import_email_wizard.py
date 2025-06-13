# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import re


class BlgImportEmailWizard(models.TransientModel):
    """Wizard pour importer des projets depuis des emails"""
    _name = 'blg.import.email.wizard'
    _description = 'Assistant d\'import depuis email'

    email_content = fields.Html('Contenu de l\'email', required=True)
    client_name = fields.Char('Nom du client')
    project_name = fields.Char('Nom du projet')
    address = fields.Text('Adresse')

    @api.onchange('email_content')
    def _onchange_email_content(self):
        """Extraire automatiquement les informations de l'email"""
        if self.email_content:
            # Simple extraction patterns - to be improved
            text = self.email_content
            
            # Extract client name (after "De:" or "From:")
            client_match = re.search(r'(?:De|From):\s*([^\n<]+)', text, re.IGNORECASE)
            if client_match:
                self.client_name = client_match.group(1).strip()
            
            # Extract project info
            project_match = re.search(r'(?:projet|project|travaux):\s*([^\n]+)', text, re.IGNORECASE)
            if project_match:
                self.project_name = project_match.group(1).strip()

    def action_create_project(self):
        """Créer le projet à partir des informations extraites"""
        if not self.client_name:
            return {'type': 'ir.actions.act_window_close'}
        
        # Créer ou trouver le client
        partner = self.env['res.partner'].search([('name', 'ilike', self.client_name)], limit=1)
        if not partner:
            partner = self.env['res.partner'].create({
                'name': self.client_name,
                'is_company': True,
            })
        
        # Créer le chantier
        chantier = self.env['blg.chantier'].create({
            'name': self.project_name or f"Projet {self.client_name}",
            'client_id': partner.id,
            'address': self.address or '',
        })
        
        # Retourner vers le chantier créé
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'blg.chantier',
            'res_id': chantier.id,
            'view_mode': 'form',
            'target': 'current',
        }
