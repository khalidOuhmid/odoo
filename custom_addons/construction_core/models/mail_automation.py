# -*- coding: utf-8 -*-
"""
Mail Automation - Automatic Chantier Creation from Emails
Parses emails sent to appel-doffre@blggroupe.com and creates construction projects
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
import re

from odoo.addons.construction_core.utils.logger import get_logger

_logger = get_logger(__name__)


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    @api.model
    def message_process(self, model, message, custom_values=None, save_original=False, strip_attachments=False, thread_id=None):
        """Override to intercept construction project creation emails."""
        # Parse the raw email to extract headers for classification
        try:
            message_dict = self.message_parse(message, save_original=False)
        except Exception:
            message_dict = {}
        # Check if email is for construction project creation
        if self._is_construction_project_email(message_dict):
            try:
                self._handle_construction_project_creation(message_dict)
            except Exception as e:
                _logger.error("[BLG][MAIL][ERROR] Error creating chantier from email: %s", e)

        return super().message_process(model, message, custom_values=custom_values,
                                       save_original=save_original,
                                       strip_attachments=strip_attachments,
                                       thread_id=thread_id)

    def _is_construction_project_email(self, message_dict):
        """Check if email should trigger construction project creation."""
        # Get configured email address
        construction_email = self.env['ir.config_parameter'].sudo().get_param(
            'construction_core.construction_project_email',
            'appel-doffre@blggroupe.com'
        )
        
        # Check recipients
        to_emails = message_dict.get('to', '').lower() if message_dict.get('to') else ''
        cc_emails = message_dict.get('cc', '').lower() if message_dict.get('cc') else ''
        
        if construction_email.lower() in to_emails or construction_email.lower() in cc_emails:
            return True
        
        # Check subject keywords
        subject = message_dict.get('subject', '').lower()
        keywords = ['appel d\'offre', 'appel doffre', 'projet construction', 'nouveau chantier']
        if any(keyword in subject for keyword in keywords):
            return True
        
        return False

    def _handle_construction_project_creation(self, message_dict):
        """Create construction project from email data."""
        # Extract project data
        project_data = self._extract_project_data_from_email(message_dict)
        
        if not project_data or not project_data.get('name'):
            _logger.warning("[BLG][MAIL][WARN] Unable to extract project data from email")
            return
        
        # Create chantier
        chantier = self._create_construction_project(project_data)
        
        if chantier:
            _logger.info("[BLG][MAIL][OK] Chantier created from email: %s (id=%s)", chantier.name, chantier.id)
            
            # Create activity for notification
            self._create_notification_activity(chantier, message_dict)
            
            # Send confirmation email if enabled
            self._send_confirmation_email(chantier)

    def _extract_project_data_from_email(self, message_dict):
        """Extract construction project data from email."""
        project_data = {
            'name': '',
            'client': None,
            'description': '',
            'address': '',
            'city': '',
            'zip_code': '',
            'phone': '',
        }
        
        try:
            # Project name from subject
            subject = message_dict.get('subject', '')
            if subject:
                # Clean subject
                project_data['name'] = subject.strip()
            
            # Description from body — strip HTML with stdlib re (no third-party dep)
            body = message_dict.get('body_html') or message_dict.get('body', '')
            if body:
                plain = re.sub(r'<[^>]+>', ' ', body)
                project_data['description'] = re.sub(r'\s+', ' ', plain).strip()
            
            # Extract client
            email_from = message_dict.get('from', '') or message_dict.get('email_from', '')
            if email_from:
                client = self._get_or_create_client(email_from)
                project_data['client'] = client
            
            # Extract address, phone from body
            if body:
                address_data = self._extract_address_from_content(body)
                project_data.update(address_data)
                
                phone = self._extract_phone_from_content(body)
                if phone:
                    project_data['phone'] = phone
        
        except Exception as e:
            _logger.error("[BLG][MAIL][ERROR] Error extracting project data: %s", e)
        
        return project_data

    def _get_or_create_client(self, email_from):
        """Get existing client or create new one."""
        # Extract email address
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', email_from)
        if not email_match:
            return None
        
        email = email_match.group()
        
        # Search existing partner
        partner = self.env['res.partner'].search([('email', '=', email)], limit=1)
        
        if partner:
            return partner
        
        # Create new partner
        name_match = re.match(r'(.+?)\s*<', email_from)
        name = name_match.group(1).strip() if name_match else email.split('@')[0].replace('.', ' ').title()
        
        partner = self.env['res.partner'].create({
            'name': name,
            'email': email,
            'is_company': True,
        })
        
        return partner

    def _extract_address_from_content(self, content):
        """Extract address information from email content."""
        address_data = {}
        
        try:
            # French postal code pattern
            zip_pattern = r'\b\d{5}\b'
            zip_match = re.search(zip_pattern, content)
            if zip_match:
                address_data['zip_code'] = zip_match.group()
            
            # City (typically after postal code)
            if zip_match:
                after_zip = content[zip_match.end():zip_match.end()+50]
                city_match = re.search(r'([A-ZÀ-Ü][a-zà-ü]+(?:\s+[A-ZÀ-Ü][a-zà-ü]+)*)', after_zip)
                if city_match:
                    address_data['city'] = city_match.group().strip()
            
            # Full address (line with number)
            lines = content.split('\n')
            for line in lines:
                line = line.strip()
                if re.search(r'\d+', line) and len(line.split()) > 2 and not address_data.get('address'):
                    address_data['address'] = line
                    break
        
        except Exception as e:
            _logger.error("[BLG][MAIL][ERROR] Error extracting address: %s", e)
        
        return address_data

    def _extract_phone_from_content(self, content):
        """Extract phone number from email content."""
        try:
            # French phone patterns
            phone_patterns = [
                r'\b0[1-9](?:\s?\d{2}){4}\b',  # 01 23 45 67 89
                r'\b0[1-9]\d{8}\b',  # 0123456789
                r'\+33\s?[1-9](?:\s?\d{2}){4}\b',  # +33 1 23 45 67 89
            ]
            
            for pattern in phone_patterns:
                match = re.search(pattern, content)
                if match:
                    return match.group()
        
        except Exception as e:
            _logger.error("[BLG][MAIL][ERROR] Error extracting phone: %s", e)
        
        return None

    def _create_construction_project(self, project_data):
        """Create a new chantier with extracted data."""
        try:
            if not project_data.get('name'):
                _logger.warning("[BLG][MAIL][WARN] Project name missing — chantier creation skipped")
                return None
            
            if not project_data.get('client'):
                _logger.warning("[BLG][MAIL][WARN] Client missing — chantier creation skipped")
                return None
            
            # Get "Appel d'offre" stage
            stage_ao = self.env['construction.stage'].search([
                ('code', '=', 'AO')
            ], limit=1)
            
            if not stage_ao:
                # Use first stage
                stage_ao = self.env['construction.stage'].search([], order='sequence', limit=1)
            
            # Create chantier
            chantier_vals = {
                'name': project_data['name'],
                'client': project_data['client'].id,
                'description': project_data.get('description', ''),
                'address': project_data.get('address', ''),
                'city': project_data.get('city', ''),
                'zip_code': project_data.get('zip_code', ''),
                'state': 'active',
            }
            
            if stage_ao:
                chantier_vals['stage_id'] = stage_ao.id
            
            chantier = self.env['construction.chantier'].create(chantier_vals)
            return chantier
        
        except Exception as e:
            _logger.error("[BLG][MAIL][ERROR] Error creating chantier: %s", e)
            return None

    def _create_notification_activity(self, chantier, message_dict):
        """Create activity to notify responsible user."""
        try:
            # Find construction manager
            manager_group = self.env.ref('construction_core.group_construction_user', raise_if_not_found=False)
            if not manager_group:
                return
            
            manager = self.env['res.users'].search([
                ('groups_id', 'in', manager_group.id)
            ], limit=1)
            
            if not manager:
                return
            
            # Create activity
            self.env['mail.activity'].create({
                'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                'res_model_id': self.env['ir.model']._get('construction.chantier').id,
                'res_id': chantier.id,
                'user_id': manager.id,
                'summary': f'Nouveau chantier créé depuis email: {chantier.name}',
                'note': f"""
                Chantier créé automatiquement depuis un email.
                
                Nom: {chantier.name}
                Client: {chantier.client.name}
                Email source: {message_dict.get('from', 'Non disponible')}
                
                Veuillez vérifier et compléter les informations du chantier.
                """,
            })
        
        except Exception as e:
            _logger.error("[BLG][MAIL][ERROR] Error creating activity for chantier id=%s: %s", chantier.id, e)

    def _send_confirmation_email(self, chantier):
        """Send confirmation email to client."""
        try:
            # Check if auto-send is enabled
            auto_send = self.env['ir.config_parameter'].sudo().get_param(
                'construction_core.auto_send_confirmation_email',
                'False'
            )
            
            if auto_send != 'True':
                return
            
            # Use email template
            template = self.env.ref('construction_core.email_template_construction_project_created', raise_if_not_found=False)
            if template and chantier.client.email:
                template.send_mail(chantier.id, force_send=True)
                _logger.info("[BLG][MAIL][OK] Confirmation email sent for chantier %s (id=%s)", chantier.name, chantier.id)
        
        except Exception as e:
            _logger.error("[BLG][MAIL][ERROR] Error sending confirmation email: %s", e)
