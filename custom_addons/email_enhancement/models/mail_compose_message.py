# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MailComposeMessage(models.TransientModel):
    """Extension du wizard de composition pour améliorer les réponses avec threading email"""
    _inherit = 'mail.compose.message'

    parent_message_id = fields.Many2one(
        'mail.message', 
        string='Parent Message',
        help="Message auquel on répond"
    )
    
    # Redéfinir message_type avec une valeur par défaut forcée
    message_type = fields.Selection(
        selection=[
            ('auto_comment', 'Automated Targeted Notification'),
            ('comment', 'Comment'),
            ('notification', 'System notification')
        ],
        string='Type',
        required=True,
        default='comment',
        help="Message type: comment for user replies"
    )
    
    @api.model
    def default_get(self, fields_list):
        """Initialise le wizard avec les données du message parent"""
        result = super().default_get(fields_list)
        
        # Forcer message_type à 'comment' pour éviter les erreurs
        result['message_type'] = 'comment'
        
        parent_message_id = self.env.context.get('default_parent_id')
        if parent_message_id:
            try:
                parent_message = self.env['mail.message'].browse(parent_message_id)
                if parent_message.exists():
                    result.update({
                        'parent_message_id': parent_message_id,
                    })
                    
                    # Ajouter l'auteur comme destinataire si c'est un partenaire
                    if parent_message.author_id and not result.get('partner_ids'):
                        result['partner_ids'] = [(6, 0, [parent_message.author_id.id])]
                        
                    # Préparer le sujet avec le bon format Re:
                    if not result.get('subject') and parent_message.subject:
                        subject = parent_message.subject
                        if not subject.startswith('Re:'):
                            subject = f'Re: {subject}'
                        result['subject'] = subject
                        
            except Exception as e:
                # Log l'erreur mais ne pas faire échouer la création du wizard
                import logging
                _logger = logging.getLogger(__name__)
                _logger.warning("Email Enhancement: Erreur lors de l'initialisation du contexte de réponse: %s", e)
                
        return result
    
    def _prepare_mail_values(self, res_ids):
        """Override pour gérer le threading des réponses"""
        mail_values = super()._prepare_mail_values(res_ids)
        
        # Si c'est une réponse via notre module, s'assurer que parent_id est bien défini
        if self.parent_message_id:
            for res_id in res_ids:
                if res_id in mail_values:
                    mail_vals = mail_values[res_id]
                    # S'assurer que le parent_id est défini pour le threading
                    mail_vals['parent_id'] = self.parent_message_id.id
        
        return mail_values
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create pour s'assurer que message_type est valide"""
        for vals in vals_list:
            # Forcer message_type à 'comment' si une valeur invalide est fournie
            if 'message_type' in vals and vals['message_type'] not in ['auto_comment', 'comment', 'notification']:
                vals['message_type'] = 'comment'
            elif 'message_type' not in vals:
                vals['message_type'] = 'comment'
            
        return super().create(vals_list)
    
    def write(self, vals):
        """Override write pour s'assurer que message_type reste valide"""
        if 'message_type' in vals and vals['message_type'] not in ['auto_comment', 'comment', 'notification']:
            vals['message_type'] = 'comment'
        
        return super().write(vals)
