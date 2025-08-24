# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class MailMessage(models.Model):
    _inherit = 'mail.message'

    # Champ pour indiquer si le message a été répondu
    has_reply = fields.Boolean(
        string="A une réponse",
        compute='_compute_has_reply',
        store=True,
        help="Indique si ce message a reçu une réponse"
    )

    # Champ pour le nombre de réponses
    reply_count = fields.Integer(
        string="Nombre de réponses",
        compute='_compute_reply_count',
        store=True,
        help="Nombre de réponses à ce message"
    )

    @api.depends('parent_id')
    def _compute_has_reply(self):
        """Calcule si le message a des réponses"""
        for message in self:
            replies = self.search_count([
                ('parent_id', '=', message.id),
                ('id', '!=', message.id)
            ])
            message.has_reply = replies > 0

    @api.depends('parent_id')
    def _compute_reply_count(self):
        """Calcule le nombre de réponses"""
        for message in self:
            replies = self.search_count([
                ('parent_id', '=', message.id),
                ('id', '!=', message.id)
            ])
            message.reply_count = replies

    def action_reply_enhanced(self):
        """
        Action pour ouvrir le compositeur de mail en réponse.

        :return: Action window pour le compositeur
        :rtype: dict
        """
        self.ensure_one()

        # Préparation du contexte
        context = {
            'default_composition_mode': 'comment',
            'default_res_id': self.res_id,
            'default_model': self.model,
            'default_parent_id': self.id,
            'mail_post_autofollow': True,
        }

        # Préparation du sujet
        subject = self.subject or ''
        if not subject.startswith('Re:'):
            subject = f"Re: {subject}"
        context['default_subject'] = subject

        # Préparation du corps du message
        if self.body:
            # Ajouter le message original en citation
            quoted_body = f"\n\n--- Message original ---\n{self.body}"
            context['default_body'] = quoted_body

        return {
            'type': 'ir.actions.act_window',
            'name': _('Répondre'),
            'res_model': 'mail.compose.message',
            'view_mode': 'form',
            'target': 'new',
            'context': context,
        }

    def action_view_replies(self):
        """
        Action pour voir toutes les réponses à ce message.

        :return: Action window pour la liste des réponses
        :rtype: dict
        """
        self.ensure_one()

        replies = self.search([
            ('parent_id', '=', self.id),
            ('id', '!=', self.id)
        ])

        return {
            'type': 'ir.actions.act_window',
            'name': _('Réponses au message'),
            'res_model': 'mail.message',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', replies.ids)],
            'context': {'default_parent_id': self.id},
        }

    @api.model
    def create(self, vals):
        """Override pour gérer les réponses automatiquement"""
        message = super().create(vals)
        
        # Si c'est une réponse, mettre à jour le message parent
        if message.parent_id:
            message.parent_id._compute_has_reply()
            message.parent_id._compute_reply_count()
        
        return message

    def write(self, vals):
        """Override pour gérer les modifications"""
        result = super().write(vals)
        
        # Si le parent change, mettre à jour les compteurs
        if 'parent_id' in vals:
            for message in self:
                if message.parent_id:
                    message.parent_id._compute_has_reply()
                    message.parent_id._compute_reply_count()
        
        return result


class MailComposeMessage(models.TransientModel):
    _inherit = 'mail.compose.message'

    def action_send_mail_enhanced(self):
        """
        Action améliorée pour l'envoi de mail avec notifications.
        """
        try:
            # Envoyer le mail
            result = self.action_send_mail()
            
            # Notification de succès (utilise le système de notification standard)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Succès"),
                    'message': _("Message envoyé avec succès"),
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            _logger.error("Erreur lors de l'envoi du mail: %s", str(e))
            
            # Notification d'erreur
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Erreur"),
                    'message': _("Erreur lors de l'envoi du message: %s") % str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }
