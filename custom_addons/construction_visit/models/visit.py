# -*- coding: utf-8 -*-
"""
Visit Model - Refactored for BLG Groupe
FAANG-level: Clean code, unified participants, workflow buttons
"""
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
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
        help="Photos prises pendant la visite"
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
        """Complete the visit."""
        for rec in self:
            if rec.state != 'in_progress':
                raise ValidationError(_("La visite doit être en cours pour être terminée."))
            rec.state = 'completed'
        return True
    
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

    # ============= WORKFLOW ACTIONS (Mission 3) ============= #
    def action_send_notification(self):
        """Send visit notification to all participants."""
        self.ensure_one()
        
        if not self.participant_ids:
            raise UserError(_("Aucun participant à notifier."))
        
        template = self.env.ref(
            'construction_visit.email_template_visit_notification',
            raise_if_not_found=False
        )
        
        if not template:
            raise UserError(_("Template email non trouvé. Installez le module correctement."))
        
        # Send to all participants
        for participant in self.participant_ids.filtered(lambda p: p.email):
            template.send_mail(self.id, force_send=True, email_values={
                'email_to': participant.email
            })
            _logger.info("Visit notification sent to %s", participant.email)
        
        self.notification_sent = True
        
        # Post to visit chatter
        self.message_post(
            body=_("Notification de visite envoyée à %d participants") % len(self.participant_ids),
            message_type='notification'
        )
        
        # Also post to chantier chatter for visibility
        if self.chantier_id:
            participant_names = ', '.join(self.participant_ids.mapped('name')[:5])
            if len(self.participant_ids) > 5:
                participant_names += f" (+{len(self.participant_ids) - 5} autres)"
            self.chantier_id.message_post(
                body=_(
                    "<b>Visite planifiée</b>: %s<br/>"
                    "<b>Date</b>: %s<br/>"
                    "<b>Participants notifiés</b>: %s"
                ) % (self.name, self.date.strftime('%d/%m/%Y à %H:%M'), participant_names),
                message_type='notification',
                subtype_xmlid='mail.mt_note'
            )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Notification Envoyée'),
                'message': _('%d participants notifiés') % len(self.participant_ids),
                'type': 'success'
            }
        }

    def action_generate_report(self):
        """Generate PDF report and attach to visit."""
        self.ensure_one()
        
        if self.state != 'completed':
            raise UserError(_("La visite doit être terminée pour générer le rapport."))
        
        # Get report action
        report_action = self.env.ref('construction_visit.action_report_visit')
        
        # Generate PDF content
        pdf_content, _ = report_action._render_qweb_pdf([self.id])
        
        # Create attachment
        filename = f"Visite_{self.chantier_id.reference}_{self.date.strftime('%Y%m%d')}.pdf"
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'datas': fields.Binary.create(self.env, pdf_content),
            'res_model': 'construction.visit',
            'res_id': self.id,
            'type': 'binary',
            'mimetype': 'application/pdf',
        })
        
        self.report_generated = True
        self.message_post(
            body=_("Rapport généré: %s") % filename,
            message_type='notification',
            attachment_ids=[attachment.id]
        )
        
        _logger.info("Report generated for visit %s", self.name)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Rapport Généré'),
                'message': _('Le rapport PDF a été créé'),
                'type': 'success'
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
        """Refresh computed fields and return updated data.
        
        Called via RPC from JavaScript for dynamic updates.
        """
        self.ensure_one()
        self._compute_button_visibility()
        return {
            'state': self.state,
            'show_send_notification': self.show_send_notification,
            'show_generate_report': self.show_generate_report,
            'show_send_report': self.show_send_report,
        }

    # ============= Maps/Waze Links (for email template) ============= #
    def get_maps_url(self):
        """Get Google Maps URL for chantier address."""
        self.ensure_one()
        address = f"{self.chantier_address or ''} {self.chantier_city or ''}".strip()
        if address:
            from urllib.parse import quote
            return f"https://www.google.com/maps/search/?api=1&query={quote(address)}"
        return ""

    def get_waze_url(self):
        """Get Waze URL for chantier address."""
        self.ensure_one()
        address = f"{self.chantier_address or ''} {self.chantier_city or ''}".strip()
        if address:
            from urllib.parse import quote
            return f"https://waze.com/ul?q={quote(address)}"
        return ""
