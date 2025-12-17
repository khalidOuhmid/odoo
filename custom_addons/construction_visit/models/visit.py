# -*- coding: utf-8 -*-
"""
Visit Model - BLG Groupe Production Module
Enterprise-grade: RFC 5545 ICS calendar integration, strict validation

Author: Khalid Ouhmid for BLGGROUPE
Version: 1.0
Odoo Version: 18.0
"""
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import timedelta
import base64
import uuid
import logging

_logger = logging.getLogger(__name__)


class Visit(models.Model):
    """Construction Site Visit with BLG workflow.
    
    Workflow:
    1. Draft → Planned → Confirmed (send notification)
    2. In Progress → Add photos/notes → Generate Report
    3. Completed → Send Report to all participants
    """
    _name = 'construction.visit'
    _description = 'Visite de Chantier'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc'

    # ============= Identity ============= #
    name = fields.Char(string='Titre', required=True, tracking=True)
    chantier_id = fields.Many2one(
        'construction.chantier', 
        string='Chantier', 
        required=True, 
        ondelete='cascade',
        tracking=True
    )
    date = fields.Datetime(string='Date et Heure', required=True, tracking=True)
    duration = fields.Float(string='Durée (h)', default=2.0)
    
    # ============= UNIFIED PARTICIPANTS (Mission 1) ============= #
    participant_ids = fields.Many2many(
        'res.partner',
        'construction_visit_participant_rel',
        'visit_id', 'partner_id',
        string='Participants',
        help="Tous les participants (internes et externes)"
    )
    
    # ============= State Machine ============= #
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('planned', 'Planifiée'),
        ('confirmed', 'Confirmée'),
        ('in_progress', 'En cours'),
        ('completed', 'Terminée'),
        ('cancelled', 'Annulée')
    ], string='Statut', default='draft', required=True, tracking=True)

    visit_type = fields.Selection([
        ('initial', 'Visite Initiale'),
        ('progress', 'Suivi de Chantier'),
        ('quality', 'Contrôle Qualité'),
        ('final', 'Réception'),
    ], string='Type de Visite', default='progress', required=True)
    
    # ============= Content ============= #
    notes = fields.Html(string='Notes et Observations')
    report = fields.Html(string='Compte Rendu')
    
    # ============= Photos & Attachments ============= #
    photo_ids = fields.Many2many(
        'ir.attachment',
        'construction_visit_photo_rel',
        'visit_id', 'attachment_id',
        string='Photos',
        domain=[('mimetype', 'ilike', 'image/')],
        help="Photos prises pendant la visite"
    )
    document_ids = fields.Many2many(
        'ir.attachment',
        'construction_visit_document_rel',
        'visit_id', 'document_attachment_id',
        string='Documents',
        domain=[('mimetype', 'not ilike', 'image/'), ('mimetype', 'not ilike', 'video/')],
        help="Documents joints (PDF, Word, Excel, etc.)"
    )
    video_ids = fields.Many2many(
        'ir.attachment',
        'construction_visit_video_rel',
        'visit_id', 'video_attachment_id',
        string='Videos',
        domain=[('mimetype', 'ilike', 'video/')],
        help="Videos prises pendant la visite"
    )
    
    # ============= Workflow Flags ============= #
    notification_sent = fields.Boolean(
        string='Notification Envoyée',
        default=False,
        copy=False
    )
    report_generated = fields.Boolean(
        string='Rapport Généré',
        default=False,
        copy=False
    )
    report_sent = fields.Boolean(
        string='Rapport Envoyé',
        default=False,
        copy=False
    )
    
    # ============= Computed Visibility ============= #
    show_send_notification = fields.Boolean(
        compute='_compute_button_visibility'
    )
    show_generate_report = fields.Boolean(
        compute='_compute_button_visibility'
    )
    show_send_report = fields.Boolean(
        compute='_compute_button_visibility'
    )

    # ============= Chantier Info (for email template) ============= #
    chantier_address = fields.Text(
        related='chantier_id.address',
        string='Adresse Chantier'
    )
    chantier_city = fields.Char(
        related='chantier_id.city',
        string='Ville'
    )

    # ============= ICS Calendar Integration (RFC 5545) ============= #
    ics_data = fields.Binary(
        string='ICS Calendar Data',
        compute='_compute_ics_data',
        help="RFC 5545 compliant .ics file for calendar integration"
    )
    ics_filename = fields.Char(
        string='ICS Filename',
        compute='_compute_ics_data'
    )

    # ============= Computed Methods ============= #
    @api.depends('state', 'notification_sent', 'report_generated', 'report_sent')
    def _compute_button_visibility(self):
        """Compute visibility of workflow buttons."""
        for visit in self:
            # Show "Send Notification" when confirmed and not yet sent
            visit.show_send_notification = (
                visit.state == 'confirmed' and not visit.notification_sent
            )
            # Show "Generate Report" when completed and has notes/photos
            visit.show_generate_report = (
                visit.state == 'completed' and 
                not visit.report_generated and
                (visit.notes or visit.photo_ids)
            )
            # Show "Send Report" when report is generated
            visit.show_send_report = (
                visit.report_generated and not visit.report_sent
            )

    @api.depends('name', 'chantier_id', 'date')
    def _compute_display_name(self):
        for record in self:
            if record.chantier_id and record.date:
                record.display_name = f"{record.name} - {record.chantier_id.name}"
            else:
                record.display_name = record.name

    @api.depends('date', 'duration', 'name', 'chantier_id', 'chantier_address', 'chantier_city', 'notes')
    def _compute_ics_data(self):
        """Generate RFC 5545 compliant ICS calendar file.
        
        This creates a VCALENDAR with a single VEVENT containing:
        - DTSTART/DTEND: Visit date and duration
        - SUMMARY: Visit title
        - LOCATION: Chantier address
        - DESCRIPTION: Notes (if any)
        - UID: Unique identifier for calendar updates
        
        Compatible with: Outlook, Google Calendar, Apple Calendar, Thunderbird.
        """
        for record in self:
            if not record.date or not record.chantier_id:
                record.ics_data = False
                record.ics_filename = False
                continue
            
            try:
                ics_content = record._generate_ics_content()
                record.ics_data = base64.b64encode(ics_content.encode('utf-8'))
                record.ics_filename = f"visite_{record.id or 'new'}.ics"
            except Exception as e:
                _logger.error("ICS generation failed for visit %s: %s", record.id, str(e))
                record.ics_data = False
                record.ics_filename = False

    def _generate_ics_content(self):
        """Generate RFC 5545 compliant ICS content.
        
        Returns:
            str: Complete VCALENDAR string with VEVENT
            
        Notes:
            - Uses UTC timestamps (DTSTART/DTEND with Z suffix)
            - UID format: visit-{id}@{company_domain}
            - Line folding per RFC 5545 section 3.1
        """
        self.ensure_one()
        
        # Generate timestamps in UTC format (RFC 5545 section 3.3.5)
        start_dt = self.date
        end_dt = start_dt + timedelta(hours=self.duration or 2.0)
        
        dtstamp = fields.Datetime.now().strftime('%Y%m%dT%H%M%SZ')
        dtstart = start_dt.strftime('%Y%m%dT%H%M%SZ')
        dtend = end_dt.strftime('%Y%m%dT%H%M%SZ')
        
        # Build location string
        location_parts = []
        if self.chantier_address:
            location_parts.append(self.chantier_address.replace('\n', ', '))
        if self.chantier_city:
            location_parts.append(self.chantier_city)
        location = ', '.join(location_parts) if location_parts else ''
        
        # Build description
        description_lines = [f"Chantier: {self.chantier_id.name}"]
        if self.notes:
            # Strip HTML tags for plain text
            import re
            clean_notes = re.sub(r'<[^>]+>', '', self.notes)
            description_lines.append(clean_notes[:500])  # Limit length
        description = '\\n'.join(description_lines)
        
        # Generate unique identifier
        company_domain = self.env.company.email or 'blggroupe.com'
        if '@' in company_domain:
            company_domain = company_domain.split('@')[1]
        uid = f"visit-{self.id or uuid.uuid4().hex[:8]}@{company_domain}"
        
        # Build summary
        summary = f"Visite: {self.name}"
        if self.chantier_id:
            summary += f" - {self.chantier_id.name}"
        
        # Escape special characters per RFC 5545
        def escape_ics(text):
            if not text:
                return ''
            return text.replace('\\', '\\\\').replace(',', '\\,').replace(';', '\\;').replace('\n', '\\n')
        
        # Construct VCALENDAR per RFC 5545
        ics_lines = [
            'BEGIN:VCALENDAR',
            'VERSION:2.0',
            'PRODID:-//BLG Groupe//Construction Visit//FR',
            'CALSCALE:GREGORIAN',
            'METHOD:PUBLISH',
            'BEGIN:VEVENT',
            f'UID:{uid}',
            f'DTSTAMP:{dtstamp}',
            f'DTSTART:{dtstart}',
            f'DTEND:{dtend}',
            f'SUMMARY:{escape_ics(summary)}',
        ]
        
        if location:
            ics_lines.append(f'LOCATION:{escape_ics(location)}')
        
        if description:
            ics_lines.append(f'DESCRIPTION:{escape_ics(description)}')
        
        ics_lines.extend([
            'STATUS:CONFIRMED',
            'TRANSP:OPAQUE',
            'END:VEVENT',
            'END:VCALENDAR',
        ])
        
        # Join with CRLF per RFC 5545 section 3.1
        return '\r\n'.join(ics_lines) + '\r\n'

    # ============= Warnings (non-blocking) ============= #
    @api.onchange('date')
    def _onchange_date_warning(self):
        """Show warning if visit is scheduled less than 24 hours in advance.
        
        Business Rule: Visits should ideally be scheduled at least 24 hours in advance
        to allow proper notification of participants and logistics preparation.
        This is a WARNING, not a blocking validation.
        """
        if self.date:
            minimum_date = fields.Datetime.now() + timedelta(hours=24)
            if self.date < minimum_date:
                return {
                    'warning': {
                        'title': _('Attention: Delai court'),
                        'message': _(
                            "La visite est planifiee dans moins de 24 heures. "
                            "Il est recommande de planifier au moins 24h a l'avance "
                            "pour permettre la notification des participants. "
                            "Date minimum recommandee: %s"
                        ) % minimum_date.strftime('%d/%m/%Y %H:%M'),
                        'type': 'notification',
                    }
                }

    # ============= State Actions ============= #
    def action_plan(self):
        """Move to planned state."""
        for rec in self:
            if rec.state != 'draft':
                raise ValidationError(_("Seules les visites brouillon peuvent être planifiées."))
            rec.state = 'planned'
        return True

    def action_confirm(self):
        """Confirm visit and prepare for notification."""
        for rec in self:
            if rec.state not in ['draft', 'planned']:
                raise ValidationError(_("Seules les visites brouillon ou planifiées peuvent être confirmées."))
            if not rec.participant_ids:
                raise ValidationError(_("Ajoutez au moins un participant avant de confirmer."))
            rec.state = 'confirmed'
        return True

    def action_start(self):
        """Start the visit."""
        for rec in self:
            if rec.state != 'confirmed':
                raise ValidationError(_("Il faut confirmer la visite avant de la démarrer."))
            rec.state = 'in_progress'
        return True

    def action_complete(self):
        """Mark visit as completed."""
        for rec in self:
            rec.state = 'completed'
            rec.date_finished = fields.Datetime.now()
        
        # Return a reload action to update the UI immediately
        # This ensures the 'Generate Report' button becomes visible
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    # ============= Report Generation ============= #
    def action_generate_report(self):
        """Generate PDF report and attach to visit."""
        self.ensure_one()
        
        if self.state != 'completed':
            raise UserError(_("La visite doit etre terminee pour generer le rapport."))
        
        # Use the ir.actions.report model to render, passing the XML ID string
        # This avoids the 'unhashable type: list' error seen when calling on instance
        try:
            pdf_content, _ = self.env['ir.actions.report']._render_qweb_pdf(
                'construction_visit.action_report_visit', 
                [self.id]
            )
        except Exception as e:
            _logger.error("Report generation failed: %s", str(e))
            raise UserError(_("Erreur lors de la generation du rapport: %s") % str(e))
        
        # Create attachment
        filename = f"Visite_{self.chantier_id.reference or 'REF'}_{self.date.strftime('%Y%m%d')}.pdf"
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'datas': base64.b64encode(pdf_content),
            'res_model': 'construction.visit',
            'res_id': self.id,
            'type': 'binary',
            'mimetype': 'application/pdf',
        })
        
        self.report_generated = True
        
        # Post to chatter
        self.message_post(
            body=_("Rapport genere: %s") % filename,
            message_type='notification',
            attachment_ids=[attachment.id]
        )
        
        _logger.info("Report generated for visit %s", self.name)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Rapport Genere'),
                'message': _('Le rapport PDF a ete cree et joint a la visite'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_cancel(self):
        """Cancel the visit."""
        for rec in self:
            if rec.state == 'completed':
                raise ValidationError(_("Impossible d'annuler une visite terminée."))
            rec.state = 'cancelled'
        return True

    def action_reset_to_draft(self):
        """Reset to draft."""
        for rec in self:
            rec.write({
                'state': 'draft',
                'notification_sent': False,
                'report_generated': False,
                'report_sent': False,
            })
        return True

    # ============= WORKFLOW ACTIONS ============= #
    def action_send_notification(self):
        """Send visit notification with ICS calendar attachment to all participants.
        
        Workflow:
        1. Validate participants exist
        """Send email notification with ICS calendar file to participants."""
        self.ensure_one()
        
        if not self.participant_ids:
            raise UserError(_("Aucun participant a notifier."))
        
        template = self.env.ref(
            'construction_visit.email_template_visit_notification',
            raise_if_not_found=False
        )
        
        if not template:
            self.message_post(body=_("Template email non trouve - pas de notification envoyee."))
            return
            
        # Generate ICS
        ics_content = self._generate_ics_content()
        ics_filename = f"invitation_{self.name.replace(' ', '_')}.ics"
        
        ics_attachment = self.env['ir.attachment'].create({
            'name': ics_filename,
            'datas': base64.b64encode(ics_content.encode('utf-8')),
            'type': 'binary',
            'mimetype': 'text/calendar',
            'res_model': 'construction.visit',
            'res_id': self.id,
        })
        
        sent_count = 0
        last_mail_id = False
        
        for participant in self.participant_ids:
            if not participant.email:
                continue
                
            email_values = {
                'email_to': participant.email,
                'email_from': self.env.user.email_formatted,
            }
            
            if ics_attachment:
                email_values['attachment_ids'] = [(4, ics_attachment.id)]
            
            # Use force_send=False to ensure the mail object is created and we get an ID
            # Then we send it manually
            mail_id = template.send_mail(self.id, force_send=False, email_values=email_values)
            if mail_id:
                last_mail_id = mail_id
                # Send immediately
                self.env['mail.mail'].browse(mail_id).send()
                
            sent_count += 1
            _logger.info("Visit notification sent to %s", participant.email)
        
        self.notification_sent = True
        
        self.message_post(
            body=_("Notification de visite envoyee a %d participants") % sent_count,
            message_type='notification'
        )
        
        # Post FULL body to Chantier Chatter
        if self.chantier_id and last_mail_id:
            try:
                # Capture accurate body from the sent mail record
                mail = self.env['mail.mail'].browse(last_mail_id)
                email_body = mail.body_html
                
                if email_body:
                    participant_names = ', '.join(self.participant_ids.mapped('name'))
                    header_html = _(
                        "<div style='background:#92564C; color:white; padding:12px 15px; "
                        "margin-bottom:0; border-radius:6px 6px 0 0;'>"
                        "<b><i class='fa fa-envelope'></i> Email envoye aux participants</b><br/>"
                        "<small style='opacity:0.9;'>Destinataires: %s</small>"
                        "</div>"
                    ) % participant_names
                    
                    full_content = header_html + (
                        "<div style='border:1px solid #E5E3E2; border-top:none; "
                        "border-radius:0 0 6px 6px; padding:0; background:#fff;'>"
                        f"{email_body}"
                        "</div>"
                    )
                    
                    self.chantier_id.message_post(
                        body=full_content,
                        message_type='comment',
                        subtype_xmlid='mail.mt_note'
                    )
                else:
                    self._post_fallback_summary()
            except Exception as e:
                _logger.warning("Error posting email body to chatter: %s", str(e))
                self._post_fallback_summary()
        elif self.chantier_id:
             self._post_fallback_summary()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Notification Envoyee'),
                'message': _('%d participants notifies') % sent_count,
                'type': 'success'
            }
        }

    def _post_fallback_summary(self):
        """Post simple summary if full body retrieval fails."""
        participant_names = ', '.join(self.participant_ids.mapped('name')[:5])
        self.chantier_id.message_post(
            body=_(
                "<b>Visite planifiee</b>: %s<br/>"
                "<b>Date</b>: %s<br/>"
                "<b>Participants notifies</b>: %s"
            ) % (self.name, self.date.strftime('%d/%m/%Y a %H:%M'), participant_names),
            message_type='notification',
            subtype_xmlid='mail.mt_note'
        )

    def action_complete(self):
        """Mark visit as completed."""
        for rec in self:
            rec.state = 'completed'
            rec.date_finished = fields.Datetime.now()
        
        # Return a reload action to update the UI immediately
        # This ensures the 'Generate Report' button becomes visible
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    # ============= Report Generation ============= #
    def action_generate_report(self):
        """Generate PDF report and attach to visit."""
        self.ensure_one()
        
        if self.state != 'completed':
            raise UserError(_("La visite doit etre terminee pour generer le rapport."))
        
        # Use the ir.actions.report model to render, passing the XML ID string
        # This avoids the 'unhashable type: list' error seen when calling on instance
        pdf_content, _ = self.env['ir.actions.report']._render_qweb_pdf(
            'construction_visit.action_report_visit', 
            [self.id]
        )
        
        # Create attachment
        filename = f"Visite_{self.chantier_id.reference or 'REF'}_{self.date.strftime('%Y%m%d')}.pdf"
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'datas': base64.b64encode(pdf_content),
            'res_model': 'construction.visit',
            'res_id': self.id,
            'type': 'binary',
            'mimetype': 'application/pdf',
        })
        
        self.report_generated = True
        
        # Post to chatter
        self.message_post(
            body=_("Rapport genere: %s") % filename,
            message_type='notification',
            attachment_ids=[attachment.id]
        )
        
        _logger.info("Report generated for visit %s", self.name)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Rapport Genere'),
                'message': _('Le rapport PDF a ete cree et joint a la visite'),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_send_report(self):
        """Send generated report to all participants."""
        self.ensure_one()
        
        if not self.report_generated:
            raise UserError(_("Générez d'abord le rapport."))
        
        if not self.participant_ids:
            raise UserError(_("Aucun participant à qui envoyer le rapport."))
        
        # Find the report attachment
        attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'construction.visit'),
            ('res_id', '=', self.id),
            ('mimetype', '=', 'application/pdf')
        ], limit=1, order='create_date desc')
        
        if not attachment:
            raise UserError(_("Rapport PDF non trouvé. Régénérez-le."))
        
        template = self.env.ref(
            'construction_visit.email_template_visit_report',
            raise_if_not_found=False
        )
        
        if not template:
            # Fallback: send simple email with attachment
            for participant in self.participant_ids.filtered(lambda p: p.email):
                self.env['mail.mail'].create({
                    'subject': _("Compte-rendu de visite - %s") % self.chantier_id.name,
                    'body_html': _("<p>Veuillez trouver ci-joint le compte-rendu de visite.</p>"),
                    'email_to': participant.email,
                    'attachment_ids': [(4, attachment.id)],
                }).send()
        else:
            for participant in self.participant_ids.filtered(lambda p: p.email):
                template.send_mail(self.id, force_send=True, email_values={
                    'email_to': participant.email,
                    'attachment_ids': [(4, attachment.id)]
                })
        
        self.report_sent = True
        self.message_post(
            body=_("Rapport envoyé à %d participants") % len(self.participant_ids),
            message_type='notification'
        )
        
        _logger.info("Report sent to %d participants for visit %s", 
                     len(self.participant_ids), self.name)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Rapport Envoyé'),
                'message': _('%d participants ont reçu le rapport') % len(self.participant_ids),
                'type': 'success'
            }
        }

    # ============= DYNAMIC REFRESH (Mission 5) ============= #
    def refresh_stages(self):
        # Refresh computed fields and return updated data
        self.ensure_one()
        self._compute_button_visibility()
        return {
            'state': self.state,
            'show_send_notification': self.show_send_notification,
            'show_generate_report': self.show_generate_report,
            'show_send_report': self.show_send_report,
        }

    def get_maps_url(self):
        self.ensure_one()
        address = f"{self.chantier_address or ''} {self.chantier_city or ''}".strip()
        if address:
            from urllib.parse import quote
            return f"https://www.google.com/maps/search/?api=1&query={quote(address)}"
        return ""

    def get_waze_url(self):
        self.ensure_one()
        address = f"{self.chantier_address or ''} {self.chantier_city or ''}".strip()
        if address:
            from urllib.parse import quote
            return f"https://waze.com/ul?q={quote(address)}"
        return ""
