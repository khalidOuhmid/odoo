# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MailMessage(models.Model):
    """Extension du modèle mail.message pour gérer les réponses"""
    _inherit = 'mail.message'

    @api.model
    def create_reply_message(self, parent_message_id, body, subject=None, partner_ids=None):
        """
        Crée une réponse à un message existant avec le threading approprié
        
        Args:
            parent_message_id (int): ID du message parent
            body (str): Contenu du message de réponse
            subject (str, optional): Sujet du message
            partner_ids (list, optional): Liste des IDs des partenaires destinataires
            
        Returns:
            mail.message: Le message de réponse créé
        """
        parent_message = self.browse(parent_message_id)
        if not parent_message.exists():
            raise UserError(_("Le message parent n'existe pas."))
        
        # Préparer le sujet de la réponse avec le bon format
        if not subject:
            parent_subject = parent_message.subject or _("Message")
            subject = parent_subject if parent_subject.startswith('Re:') else f'Re: {parent_subject}'
        
        # Utiliser message_post pour créer une vraie réponse avec threading
        if parent_message.model and parent_message.res_id:
            record = self.env[parent_message.model].browse(parent_message.res_id)
            if record.exists():
                # Créer la réponse avec message_post (les headers email seront gérés par le wizard)
                reply_message = record.message_post(
                    body=body,
                    subject=subject,
                    partner_ids=partner_ids or [],
                    parent_id=parent_message_id,
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment',
                )
                
                return reply_message
        
        # Fallback : créer un message simple si pas de record
        message_data = {
            'model': parent_message.model,
            'res_id': parent_message.res_id,
            'message_type': 'comment',
            'subtype_id': self.env.ref('mail.mt_comment').id,
            'body': body,
            'subject': subject,
            'parent_id': parent_message_id,
        }
        
        if partner_ids:
            message_data['partner_ids'] = [(6, 0, partner_ids)]
            
        return self.create(message_data)

    def get_reply_context(self):
        """
        Retourne le contexte pour créer une réponse à ce message
        
        Returns:
            dict: Contexte pour le wizard de composition
        """
        self.ensure_one()
        
        # Préparer le contexte pour le full composer
        context = {
            'default_model': self.model,
            'default_res_ids': [self.res_id],
            'default_parent_id': self.id,
            'default_subject': _("Re: %s") % (self.subject or _("Message")),
            'default_message_type': 'comment',
            'default_subtype_id': self.env.ref('mail.mt_comment').id,
        }
        
        # Ajouter les destinataires du message original
        if self.partner_ids:
            context['default_partner_ids'] = [(6, 0, self.partner_ids.ids)]
            
        return context
