# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class MailMail(models.Model):
    """Extension du modèle mail.mail pour gérer le threading email"""
    _inherit = 'mail.mail'
    
    @api.model
    def create(self, vals):
        """Override create pour ajouter les headers de threading email"""
        mail = super().create(vals)
        
        # Si le mail a un parent_id, ajouter les headers de threading
        if mail.mail_message_id and mail.mail_message_id.parent_id:
            parent_message = mail.mail_message_id.parent_id
            
            # Si le message parent a un message_id (header Message-ID)
            if parent_message.message_id:
                # Récupérer les headers existants
                headers = {}
                if mail.headers:
                    try:
                        import ast
                        headers = ast.literal_eval(mail.headers) if isinstance(mail.headers, str) else mail.headers
                    except:
                        headers = {}
                
                # Ajouter les headers RFC 2822 pour le threading
                headers.update({
                    'In-Reply-To': parent_message.message_id,
                    'References': parent_message.message_id,
                })
                
                # Mettre à jour les headers
                mail.headers = repr(headers)
        
        return mail
    
    def _send_prepare_values(self, partner=None):
        """Override pour s'assurer que les headers de threading sont inclus"""
        res = super()._send_prepare_values(partner=partner)
        
        # Si on a des headers avec threading, s'assurer qu'ils sont correctement formatés
        if self.headers:
            try:
                import ast
                headers_dict = ast.literal_eval(self.headers) if isinstance(self.headers, str) else self.headers
                if isinstance(headers_dict, dict) and ('In-Reply-To' in headers_dict or 'References' in headers_dict):
                    # Les headers sont déjà dans le bon format
                    pass
            except:
                # En cas d'erreur de parsing, laisser les headers tels quels
                pass
        
        return res
