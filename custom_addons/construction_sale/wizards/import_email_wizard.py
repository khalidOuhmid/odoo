# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import re
import logging

_logger = logging.getLogger(__name__)


class ImportEmailWizard(models.TransientModel):
    """
    Wizard pour importer un chantier depuis un email.
    Le titre du mail devient le nom du chantier et le corps est importé dans la description.
    """
    _name = 'construction.import.email.wizard'
    _description = 'Import Chantier depuis Email'

    email_subject = fields.Char(
        string='Objet de l\'email',
        required=True,
        help="L'objet de l'email deviendra le nom du chantier"
    )
    
    email_body = fields.Html(
        string='Corps de l\'email',
        help="Le corps de l'email sera importé dans la description du chantier"
    )
    
    client_id = fields.Many2one(
        'res.partner',
        string='Client',
        domain=[('is_company', '=', True)],
        help="Client associé au chantier"
    )
    
    # Champs optionnels extraits de l'email
    phone = fields.Char(string='Téléphone')
    address = fields.Text(string='Adresse du chantier')
    
    @api.model
    def default_get(self, fields_list):
        """
        Pré-remplir les champs si l'email contient des informations structurées
        """
        res = super().default_get(fields_list)
        
        # Si appelé depuis un contexte email, extraire les informations
        if self.env.context.get('default_email_body'):
            body = self.env.context.get('default_email_body', '')
            
            # Essayer d'extraire le téléphone
            phone_match = re.search(r'(?:Tél|Tel|Téléphone|Phone)[\s:]*([+\d\s\-\(\)]+)', body)
            if phone_match:
                res['phone'] = phone_match.group(1).strip()
            
            # Essayer d'extraire l'adresse
            address_match = re.search(r'(?:Adresse|Address)[\s:]*([^\n]+)', body)
            if address_match:
                res['address'] = address_match.group(1).strip()
        
        return res
    
    def action_create_chantier(self):
        """
        Créer le chantier à partir des informations de l'email
        """
        self.ensure_one()
        
        if not self.email_subject:
            raise UserError("L'objet de l'email est requis pour créer un chantier")
        
        # Préparer les valeurs du chantier
        chantier_vals = {
            'name': self.email_subject,
            'description': self.email_body,
            'client': self.client_id.id if self.client_id else False,
            'phone': self.phone,
            'address': self.address,
        }
        
        # Créer le chantier
        chantier = self.env['construction.chantier'].create(chantier_vals)
        
        # Message de confirmation
        chantier.message_post(
            body=f"Chantier créé depuis un email avec l'objet : {self.email_subject}",
            message_type='notification'
        )
        
        # Retourner l'action pour afficher le nouveau chantier
        return {
            'type': 'ir.actions.act_window',
            'name': 'Chantier',
            'res_model': 'construction.chantier',
            'res_id': chantier.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    @api.model
    def create_chantier_from_email(self, email_vals):
        """
        Méthode API pour créer un chantier directement depuis un email
        Utilisé par l'intégration email
        
        :param email_vals: dict contenant 'subject', 'body', 'from', etc.
        :return: ID du chantier créé
        """
        # Extraire le client depuis l'adresse email si possible
        client_id = False
        if email_vals.get('from'):
            email_from = email_vals['from']
            # Extraire l'email
            email_match = re.search(r'[\w\.-]+@[\w\.-]+', email_from)
            if email_match:
                email = email_match.group(0)
                # Chercher un partenaire avec cet email
                partner = self.env['res.partner'].search([('email', '=', email)], limit=1)
                if partner:
                    client_id = partner.id
        
        # Créer le wizard avec les valeurs
        wizard = self.create({
            'email_subject': email_vals.get('subject', 'Sans objet'),
            'email_body': email_vals.get('body', ''),
            'client_id': client_id,
        })
        
        # Extraire les informations supplémentaires
        wizard.default_get(['phone', 'address'])
        
        # Créer le chantier
        result = wizard.action_create_chantier()
        
        return result.get('res_id') 