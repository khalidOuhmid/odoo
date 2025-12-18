# Copyright 2021 Creu Blanca
# Copyright 2024 BLG Groupe - Odoo 18 Migration
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from markupsafe import Markup

from odoo import api, models


class MailComposeMessage(models.TransientModel):
    _inherit = "mail.compose.message"

    @api.model
    def default_get(self, fields_list):
        """Override to handle quoted reply body from context.
        
        In Odoo 18, body is a computed field but can be set via default_body
        context key. We ensure the Markup is properly handled.
        """
        result = super().default_get(fields_list)
        
        # Handle default_body from reply_message context
        if self.env.context.get('default_body') and 'body' in fields_list:
            default_body = self.env.context['default_body']
            # Ensure Markup is preserved for HTML content
            if isinstance(default_body, str):
                default_body = Markup(default_body)
            result['body'] = default_body
            
        return result

