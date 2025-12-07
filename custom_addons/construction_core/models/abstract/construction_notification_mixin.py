# -*- coding: utf-8 -*-
from odoo import models, api, _

class ConstructionNotificationMixin(models.AbstractModel):
    _name = 'construction.notification.mixin'
    _description = 'Construction Notification Logic'

    def _notify_role(self, group_xml_id, subject, body_markdown):
        """Send notification to all users in a specific group."""
        group = self.env.ref(group_xml_id, raise_if_not_found=False)
        if not group:
            return
            
        recipients = group.users.mapped('partner_id')
        if not recipients:
            return

        # Create a mail.message or activity
        # We prefer activity for "To Do" items, email for information
        for user in group.users:
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=subject,
                note=body_markdown,
                user_id=user.id
            )
            
    def notify_director(self, subject, body):
        self._notify_role('construction_core.group_construction_manager', subject, body)

    def notify_site_managers(self, subject, body):
        self._notify_role('construction_core.group_construction_user', subject, body)
