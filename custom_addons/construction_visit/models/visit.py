# -*- coding: utf-8 -*-
"""
Visit Model - BLG Groupe Production Module
Enterprise-grade: RFC 5545 ICS calendar integration, strict validation

Author: Khalid Ouhmid for BLGGROUPE
Version: 1.0
Odoo Version: 18.0
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
        # Send email notification with ICS calendar file to participants
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
        
        
        # Post FULL body to Chantier Chatter (As requested: "Voir le mail")
        if self.chantier_id and last_mail_id:
            try:
                # Capture accurate body from the sent mail record
                mail = self.env['mail.mail'].browse(last_mail_id)
                email_body = mail.body_html
                subject = mail.subject or _("Notification de visite")
                
                if email_body:
                    # Provide a simple header to indicate origin, but keep body HTML intact
                    # Use a standard quoting style or just the body
                    
                    self.chantier_id.message_post(
                        body=Markup(email_body),
                        subject=subject,
                        message_type='comment',  # Use comment to look like a message
                        subtype_xmlid='mail.mt_note' # Keep as note to not spam followers? Or mt_comment?
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
        # Post simple summary if full body retrieval fails
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

    # ============= Report Generation ============= #
    def action_generate_report(self):
        # Generate PDF report and attach to visit
        self.ensure_one()
        
        if self.state != 'completed':
            raise UserError(_("La visite doit etre terminee pour generer le rapport."))
        
        # Use the ir.actions.report model to render, passing the XML ID string
        try:
            pdf_content, _content_type = self.env['ir.actions.report']._render_qweb_pdf(
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

    def action_send_report(self):
        # Send generated report to all participants
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
