# -*- coding: utf-8 -*-
"""
Visit Model - BLG Groupe Production Module
Enterprise-grade: RFC 5545 ICS calendar integration, strict validation

Author: Khalid Ouhmid for BLGGROUPE
Version: 1.1
Odoo Version: 18.0

Changelog:
    1.1 - TASK-001: Fixed notification bugs (race condition, error handling, cron)
"""
from odoo import models, fields, api, _
from markupsafe import Markup
from odoo.exceptions import ValidationError, UserError
from datetime import timedelta, date
import base64
import uuid
import logging

_logger = logging.getLogger(__name__)


class Visit(models.Model):
    # Construction Site Visit with BLG workflow
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
    
    # ============= UNIFIED PARTICIPANTS ============= #
    participant_ids = fields.Many2many(
        'res.partner',
        'construction_visit_participant_rel',
        'visit_id', 'partner_id',
        string='Participants',
        tracking=True,
        help="Tous les participants: clients, sous-traitants, architectes, etc."
    )
    
    # ============= Visit Details ============= #
    visit_type = fields.Selection([
        ('initial', 'Visite Initiale'),
        ('follow_up', 'Suivi de Chantier'),
        ('technical', 'Visite Technique'),
        ('final', 'Réception Finale'),
    ], string='Type de Visite', default='initial', required=True)
    
    motif = fields.Text(string='Motif de la visite')
    description = fields.Html(string='Description', help="Description détaillée de la visite")
    notes = fields.Html(string='Notes de visite')
    report = fields.Html(string='Compte-rendu')
    report_html = fields.Html(string='Rapport HTML', readonly=True)
    report_pdf = fields.Binary(string='Rapport PDF', readonly=True, attachment=True)
    
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'construction_visit_generic_attach_rel',
        'visit_id', 'attachment_id',
        string='Pièces jointes'
    )
    
    # ============= Media Attachments ============= #
    photo_ids = fields.Many2many(
        'ir.attachment',
        'construction_visit_photo_v2_rel',
        'visit_id', 'ir_attachment_id',
        string='Photos',
        domain=[('mimetype', 'ilike', 'image/')],
        help="Photos prises pendant la visite"
    )
    
    video_ids = fields.Many2many(
        'ir.attachment',
        'construction_visit_video_v2_rel',
        'visit_id', 'ir_attachment_id',
        string='Vidéos',
        domain=[('mimetype', 'ilike', 'video/')],
        help="Vidéos de la visite"
    )
    
    document_ids = fields.Many2many(
        'ir.attachment',
        'construction_visit_doc_v2_rel',
        'visit_id', 'ir_attachment_id',
        string='Documents',
        domain=[('mimetype', 'not ilike', 'image/'), ('mimetype', 'not ilike', 'video/')],
        help="Documents techniques (PDF, Word, etc.)"
    )
    
    # ============= State Machine ============= #
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('planned', 'Planifiée'),
        ('confirmed', 'Confirmée'),
        ('in_progress', 'En Cours'),
        ('completed', 'Terminée'),
        ('cancelled', 'Annulée'),
    ], string='État', default='draft', required=True, tracking=True)
    
    # ============= Workflow Flags ============= #
    notification_sent = fields.Boolean(string='Notification Envoyée', default=False, copy=False)
    report_generated = fields.Boolean(string='Rapport Généré', default=False, copy=False)
    report_sent = fields.Boolean(string='Rapport Envoyé', default=False, copy=False)
    date_finished = fields.Datetime(string='Date de fin', readonly=True, copy=False)
    
    # ============= ICS Calendar Data ============= #
    ics_data = fields.Binary(string='Fichier ICS', compute='_compute_ics_data', store=False)
    ics_filename = fields.Char(string='Nom fichier ICS', compute='_compute_ics_data', store=False)
    
    # ============= Button Visibility ============= #
    show_send_notification = fields.Boolean(compute='_compute_button_visibility')
    show_generate_report = fields.Boolean(compute='_compute_button_visibility')
    show_send_report = fields.Boolean(compute='_compute_button_visibility')
    
    # ============= Related Fields (for easy access) ============= #
    chantier_name = fields.Char(related='chantier_id.name', string='Nom Chantier', readonly=True, store=True)
    chantier_reference = fields.Char(related='chantier_id.reference', string='Référence', readonly=True)
    chantier_address = fields.Text(related='chantier_id.address', string='Adresse', readonly=True)
    chantier_city = fields.Char(related='chantier_id.city', string='Ville', readonly=True)

    @api.depends('state', 'notification_sent', 'report_generated', 'report_sent')
    def _compute_button_visibility(self):
        # Compute visibility of workflow buttons
        for visit in self:
            visit.show_send_notification = (visit.state == 'confirmed' and not visit.notification_sent)
            visit.show_generate_report = (visit.state == 'completed' and not visit.report_generated)
            visit.show_send_report = (visit.state == 'completed' and visit.report_generated and not visit.report_sent)

    @api.depends('name', 'date', 'chantier_id')
    def _compute_ics_data(self):
        # Generate ICS calendar file data
        for visit in self:
            if visit.date and visit.chantier_id:
                ics_content = visit._generate_ics_content()
                visit.ics_data = base64.b64encode(ics_content.encode('utf-8'))
                visit.ics_filename = f"visite_{visit.name.replace(' ', '_')}.ics"
            else:
                visit.ics_data = False
                visit.ics_filename = False

    def _generate_ics_content(self):
        # Generate RFC 5545 compliant ICS content
        self.ensure_one()
        
        uid = str(uuid.uuid4())
        start_date = self.date.strftime('%Y%m%dT%H%M%SZ')
        end_date = (self.date + timedelta(hours=self.duration)).strftime('%Y%m%dT%H%M%SZ')
        now = fields.Datetime.now().strftime('%Y%m%dT%H%M%SZ')
        
        location = f"{self.chantier_address or ''}, {self.chantier_city or ''}".strip()
        
        ics_template = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//BLG Groupe//Odoo Construction//FR
CALSCALE:GREGORIAN
METHOD:REQUEST
BEGIN:VEVENT
UID:{uid}@blggroupe.com
DTSTAMP:{now}
DTSTART:{start_date}
DTEND:{end_date}
SUMMARY:Visite - {self.name}
DESCRIPTION:{self.motif or 'Visite de chantier'}
LOCATION:{location}
STATUS:CONFIRMED
SEQUENCE:0
ORGANIZER:mailto:contact@blggroupe.com
END:VEVENT
END:VCALENDAR"""
        
        return ics_template

    @api.onchange('date')
    def _onchange_date_buffer(self):
        # Warn if visit is scheduled with less than 24h notice
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
        # Move to planned state
        for rec in self:
            if rec.state != 'draft':
                raise ValidationError(_("Seules les visites brouillon peuvent être planifiées."))
            rec.state = 'planned'
        return True

    def action_confirm(self):
        # Confirm visit and prepare for notification
        for rec in self:
            if rec.state not in ['draft', 'planned']:
                raise ValidationError(_("Seules les visites brouillon ou planifiées peuvent être confirmées."))
            if not rec.participant_ids:
                raise ValidationError(_("Ajoutez au moins un participant avant de confirmer."))
            rec.state = 'confirmed'
        return True

    def action_start(self):
        # Start the visit
        for rec in self:
            if rec.state != 'confirmed':
                raise ValidationError(_("Il faut confirmer la visite avant de la démarrer."))
            rec.state = 'in_progress'
        return True

    def action_complete(self):
        # Mark visit as completed
        for rec in self:
            if rec.state != 'in_progress':
                raise ValidationError(_("Seule une visite en cours peut être terminée."))
            rec.state = 'completed'
            rec.date_finished = fields.Datetime.now()
        
        # Return a reload action to update the UI immediately
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
    
    def action_cancel(self):
        # Cancel the visit
        for rec in self:
            if rec.state == 'completed':
                raise ValidationError(_("Impossible d'annuler une visite terminée."))
            rec.state = 'cancelled'
        return True

    def action_reset_to_draft(self):
        # Reset to draft
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
        """
        Sends an email notification with an ICS calendar file to all participants.
        
        This method ensures that:
        - Errors per participant are handled individually without blocking others.
        - `force_send=True` is used to send immediately and avoid race conditions.
        - A notification trace is posted to the associated Chantier's chatter.
        
        Returns:
            dict: Client action to display a success or warning notification.
        """
        self.ensure_one()
        
        if not self.participant_ids:
            raise UserError(_("Aucun participant à notifier."))
        
        template = self.env.ref(
            'construction_visit.email_template_visit_notification',
            raise_if_not_found=False
        )
        
        if not template:
            self.message_post(body=_("Template email non trouvé — pas de notification envoyée."))
            return
        
        # Generate ICS attachment (once for all participants)
        ics_content = self._generate_ics_content()
        ics_filename = f"invitation_{self.name.replace(' ', '_')}.ics"
        
        ics_attachment = self.env['ir.attachment'].create({
            'name': ics_filename,
            'datas': base64.b64encode(ics_content.encode('utf-8')),
            'type': 'binary',
            'mimetype': 'text/calendar',
            'res_model': 'construction.chantier',
            'res_id': self.chantier_id.id,
        })
        
        sent_count = 0
        failed_participants = []
        last_mail_id = False
        
        for participant in self.participant_ids:
            if not participant.email:
                _logger.warning(
                    "Visit %s: participant '%s' has no email — skipped",
                    self.name, participant.name
                )
                continue
            
            try:
                email_values = {
                    'email_to': participant.email,
                    'email_from': self.env.user.email_formatted,
                    'model': 'construction.chantier',
                    'res_id': self.chantier_id.id,
                }
                
                if ics_attachment:
                    email_values['attachment_ids'] = [(4, ics_attachment.id)]
                
                # Use force_send=True — single atomic send, no race condition
                mail_id = template.send_mail(
                    self.id, force_send=True, email_values=email_values
                )
                if mail_id:
                    last_mail_id = mail_id
                
                sent_count += 1
                _logger.info("Visit notification sent to %s", participant.email)
                
            except Exception as e:
                _logger.error(
                    "Visit %s: failed to notify %s — %s",
                    self.name, participant.email, str(e)
                )
                failed_participants.append(participant.name)
        
        # Mark as sent even if some failed (partial success)
        if sent_count > 0:
            self.notification_sent = True
        
        # Build chatter message
        body_parts = [_("Notification de visite envoyée à %d participant(s)") % sent_count]
        if failed_participants:
            body_parts.append(
                _("⚠️ Échec d'envoi pour : %s") % ', '.join(failed_participants)
            )
        
        self.message_post(
            body='<br/>'.join(body_parts),
            message_type='notification'
        )
        
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Notification Envoyée'),
                'message': _('%d participant(s) notifié(s)') % sent_count,
                'type': 'success' if not failed_participants else 'warning',
            }
        }

    # ============= Report Generation ============= #
    def action_generate_report(self):
        """Generate a PDF report and attach it to both the visit and chantier chatters."""
        self.ensure_one()

        if self.state != 'completed':
            raise UserError(_("La visite doit etre terminee pour generer le rapport."))

        try:
            pdf_content, _content_type = self.env['ir.actions.report']._render_qweb_pdf(
                'construction_visit.action_report_visit',
                [self.id]
            )
            html_content, _html_content_type = self.env['ir.actions.report']._render_qweb_html(
                'construction_visit.action_report_visit',
                [self.id]
            )
        except Exception as e:
            _logger.error('Report generation failed: %s', e)
            raise UserError(_("Erreur lors de la generation du rapport: %s") % str(e))

        filename = f"Visite_{self.chantier_id.reference or 'REF'}_{self.date.strftime('%Y%m%d')}.pdf"
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'datas': base64.b64encode(pdf_content),
            'res_model': 'construction.chantier',
            'res_id': self.chantier_id.id,
            'type': 'binary',
            'mimetype': 'application/pdf',
        })

        self.write({
            'report_generated': True,
            'report_pdf': base64.b64encode(pdf_content),
            'report_html': html_content,
        })

        self.message_post(
            body=_("Rapport genere: %s") % filename,
            message_type='notification',
            attachment_ids=[attachment.id]
        )

        if self.chantier_id:
            self.chantier_id.message_post(
                body=_(
                    "📋 <b>Rapport de visite</b> — %s<br/>"
                    "Type: %s | Date: %s"
                ) % (
                    self.name,
                    dict(self._fields['visit_type'].selection).get(self.visit_type, ''),
                    self.date.strftime('%d/%m/%Y'),
                ),
                message_type='comment',
                subtype_xmlid='mail.mt_note',
                attachment_ids=[attachment.id],
            )

        _logger.info('Report generated for visit %s', self.name)

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

    def action_download_report_pdf(self):
        """Open the generated PDF report in a new tab for download/preview."""
        self.ensure_one()
        if not self.report_generated:
            raise UserError(_("Générez d'abord le rapport."))
        attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'construction.visit'),
            ('res_id', '=', self.id),
            ('mimetype', '=', 'application/pdf'),
        ], limit=1, order='id desc')
        if not attachment:
            # Fallback: use the binary field directly
            filename = f"Visite_{self.chantier_id.reference or 'REF'}_{self.date.strftime('%Y%m%d')}.pdf"
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/construction.visit/{self.id}/report_pdf/{filename}?download=true',
                'target': 'new',
            }
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }

    def action_send_report(self):
        """
        Sends the generated PDF report to all participants via email.
        
        Raises:
            UserError: If the report hasn't been generated or there are no participants.
            
        Returns:
            dict: Client action returning a success notification.
        """
        self.ensure_one()
        
        if not self.report_generated:
            raise UserError(_("Générez d'abord le rapport."))
        
        if not self.participant_ids:
            raise UserError(_("Aucun participant à qui envoyer le rapport."))
        
        # Find the report attachment on Chantier
        attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'construction.chantier'),
            ('res_id', '=', self.chantier_id.id),
            ('name', 'ilike', f"Visite_%_{self.date.strftime('%Y%m%d')}.pdf"),
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
                    'model': 'construction.chantier',
                    'res_id': self.chantier_id.id,
                }).send()
        else:
            for participant in self.participant_ids.filtered(lambda p: p.email):
                template.send_mail(self.id, force_send=True, email_values={
                    'email_to': participant.email,
                    'attachment_ids': [(4, attachment.id)],
                    'model': 'construction.chantier',
                    'res_id': self.chantier_id.id,
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

    # ============= CRON: Automated Notifications (TASK-001) ============= #
    @api.model
    def _cron_send_visit_notifications(self):
        """
        Cron job: Automatically sends notifications for confirmed visits approaching within 48h.
        
        Runs daily. Finds visits that are:
        - In 'confirmed' state.
        - Not yet notified (`notification_sent` is False).
        - Scheduled within the next 48 hours.
        
        Sends notifications and logs the results.
        
        Returns:
            bool: True if successful.
        """
        now = fields.Datetime.now()
        deadline = now + timedelta(hours=48)
        
        visits_to_notify = self.search([
            ('state', '=', 'confirmed'),
            ('notification_sent', '=', False),
            ('date', '>=', now),
            ('date', '<=', deadline),
            ('participant_ids', '!=', False),
        ])
        
        _logger.info(
            "Cron visit notifications: %d visit(s) to notify", len(visits_to_notify)
        )
        
        for visit in visits_to_notify:
            try:
                visit.action_send_notification()
                _logger.info(
                    "Cron: notification sent for visit '%s' (ID: %d)",
                    visit.name, visit.id
                )
            except Exception as e:
                _logger.error(
                    "Cron: failed to notify visit '%s' (ID: %d) — %s",
                    visit.name, visit.id, str(e)
                )
        
        return True

    # ============= DYNAMIC REFRESH ============= #
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
