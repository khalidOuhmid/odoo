# -*- coding: utf-8 -*-
from odoo import models, fields, api


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    @api.model
    def message_route(self, message, message_dict, model=None, thread_id=None, custom_values=None):
        """
        Override to handle project creation from emails to a specific address
        """
        # Check if this is an email to the project creation address
        if message_dict.get('to') and 'chantier@blg-groupe.com' in message_dict.get('to'):
            # Create a new project from this email
            project_model = self.env['blg.chantier']

            # Extract basic info
            subject = message_dict.get('subject', 'New Project')
            body = message_dict.get('body', '')

            # Try to find partner from email
            email_from = message_dict.get('email_from')
            partner = False
            if email_from:
                partner = self.env['res.partner'].search([('email', '=', email_from)], limit=1)

            if partner:
                # If partner found, create project directly
                chapter = self.env['blg.chapter'].search([('code', '=', '1')], limit=1)
                stage = self.env['blg.stage'].search([('code', '=', '1_1')], limit=1)

                project_vals = {
                    'name': subject,
                    'client_id': partner.id,
                    'description': body,
                    'chapter_id': chapter.id if chapter else False,
                    'stage_id': stage.id if stage else False,
                }

                project = project_model.create(project_vals)

                # Add the original email as an attachment
                if message_dict.get('attachments'):
                    for attachment in message_dict.get('attachments'):
                        name = attachment[0] if isinstance(attachment, tuple) else attachment.fname
                        content = attachment[1] if isinstance(attachment, tuple) else attachment.content
                        self.env['ir.attachment'].create({
                            'name': name,
                            'datas': content,
                            'res_model': 'blg.chantier',
                            'res_id': project.id,
                        })

                # Post a message about the creation
                project.message_post(
                    body=f"Project created automatically from email: {subject}",
                    subject="Project Creation",
                )

                # Return empty to avoid standard processing
                return []
            else:
                # If no partner found, save the email for manual processing
                # You could create a queue model for pending emails
                pass

        # Default behavior for other emails
        return super(MailThread, self).message_route(
            message, message_dict, model, thread_id, custom_values)
