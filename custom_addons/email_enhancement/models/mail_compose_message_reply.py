# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MailComposeMessage(models.TransientModel):
    """Extension du wizard de composition pour améliorer les réponses"""
    _inherit = 'mail.compose.message'

    parent_message_id = fields.Many2one(
        'mail.message', 
        string='Parent Message',
        help="Message auquel on répond"
    )
    
    @api.model
    def default_get(self, fields_list):
        """Initialise le wizard avec les données du message parent"""
        result = super().default_get(fields_list)
        
        parent_message_id = self.env.context.get('default_parent_id')
        if parent_message_id:
            parent_message = self.env['mail.message'].browse(parent_message_id)
            if parent_message.exists():
                result.update({
                    'parent_message_id': parent_message_id,
                })
                
                # Ajouter l'auteur comme destinataire si c'est un partenaire
                if parent_message.author and parent_message.author.partner and not result.get('partner_ids'):
                    result['partner_ids'] = [(6, 0, [parent_message.author.partner.id])]
                
        return result
