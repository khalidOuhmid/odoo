# -*- coding: utf-8 -*-
"""
Sans Suite Wizard (US-COR-008)

Wizard for classifying a chantier as "Sans Suite" (closed/abandoned).
Requires mandatory reason and optional hierarchical approval.
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

from odoo.addons.construction_core.utils.logger import get_logger

_logger = get_logger(__name__)


class SansSuiteWizard(models.TransientModel):
    """
    Wizard to classify a Chantier as "Sans Suite" with mandatory reason.
    
    US-COR-008 Requirements:
    - Warning modal: "Cette action est irréversible."
    - Mandatory reason selection from predefined list
    - Optional free text (500 chars max)
    - Hierarchical validation (optional)
    - Email notification to client (optional)
    """
    _name = 'construction.sans.suite.wizard'
    _description = 'Wizard - Classer Sans Suite'

    # ============================================================
    # FIELDS
    # ============================================================
    
    chantier_id = fields.Many2one(
        'construction.chantier',
        string='Chantier',
        required=True,
        readonly=True,
        ondelete='cascade'
    )
    
    chantier_name = fields.Char(
        related='chantier_id.name',
        readonly=True
    )
    
    reason = fields.Selection([
        ('client_cancelled', 'Client a renoncé'),
        ('budget_insufficient', 'Budget insuffisant'),
        ('delays_incompatible', 'Délais incompatibles'),
        ('technical_impossible', 'Impossibilité technique'),
        ('competition', 'Concurrence'),
        ('other', 'Autre raison')
    ], string='Raison d\'abandon', required=True,
       help="Sélectionnez la raison principale de l'abandon")
    
    reason_details = fields.Text(
        string='Détails de la raison',
        help="Précisions optionnelles (500 caractères max)"
    )
    
    notify_client = fields.Boolean(
        string='Notifier le client',
        default=False,
        help="Envoyer un email au client pour l'informer"
    )
    
    client_email_template = fields.Text(
        string='Message au client',
        default="Nous vous informons que le projet [CHANTIER] ne sera malheureusement pas poursuivi. "
                "Nous restons à votre disposition pour tout renseignement complémentaire."
    )
    
    require_approval = fields.Boolean(
        string='Validation hiérarchique requise',
        compute='_compute_require_approval'
    )
    
    approver_id = fields.Many2one(
        'res.users',
        string='Approbateur',
        domain="[('share', '=', False)]",
        help="Responsable devant approuver la décision"
    )

    # ============================================================
    # COMPUTED
    # ============================================================
    
    @api.depends('chantier_id')
    def _compute_require_approval(self):
        """Check if hierarchical approval is required based on chantier value."""
        for wizard in self:
            # Require approval for high-value chantiers (>50k)
            chantier = wizard.chantier_id
            if chantier and chantier.budget_previsionnel and chantier.budget_previsionnel > 50000:
                wizard.require_approval = True
            else:
                wizard.require_approval = False

    # ============================================================
    # CONSTRAINTS
    # ============================================================
    
    @api.constrains('reason_details')
    def _check_reason_details_length(self):
        """Limit reason details to 500 characters."""
        for wizard in self:
            if wizard.reason_details and len(wizard.reason_details) > 500:
                raise UserError(_("Les détails de la raison ne peuvent pas dépasser 500 caractères."))

    # ============================================================
    # ACTIONS
    # ============================================================
    
    def action_confirm(self):
        """Confirm Sans Suite classification."""
        self.ensure_one()
        
        chantier = self.chantier_id
        
        # Log the action
        _logger.info(
            "[LOGGER][INFO][construction.sans_suite] Chantier %s classé Sans Suite - Raison: %s",
            chantier.name, self.reason
        )
        
        # Find Sans Suite stage
        sans_suite_stage = self.env.ref(
            'construction_core.stage_sans_suite', 
            raise_if_not_found=False
        )
        
        if not sans_suite_stage:
            sans_suite_stage = self.env['construction.stage'].search([
                ('code', '=', 'SS')
            ], limit=1)
        
        if not sans_suite_stage:
            raise UserError(_("Stage 'Sans Suite' introuvable dans la configuration."))
        
        # Build reason text
        reason_labels = dict(self._fields['reason'].selection)
        reason_text = reason_labels.get(self.reason, self.reason)
        if self.reason_details:
            reason_text += f"\n\nDétails: {self.reason_details}"
        
        # Update chantier (bypass stage validation — wizard is authorised to do this)
        chantier.with_context(bypass_stage_validation=True).write({
            'stage_id': sans_suite_stage.id,
            'sans_suite_reason': self.reason,
            'sans_suite_details': self.reason_details,
            'sans_suite_date': fields.Date.today(),
            'active': False  # Archive the chantier
        })
        
        # Post message in chatter
        chantier.message_post(
            body=_(
                "<strong>⚠️ Chantier classé Sans Suite</strong><br/>"
                "<strong>Raison:</strong> %s<br/>"
                "<strong>Par:</strong> %s<br/>"
                "<strong>Date:</strong> %s"
            ) % (reason_text, self.env.user.name, fields.Date.today()),
            message_type='notification'
        )
        
        # Send client notification if requested
        if self.notify_client and chantier.partner_id and chantier.partner_id.email:
            self._send_client_notification(chantier)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Chantier Classé Sans Suite"),
                'message': _("Le chantier '%s' a été classé Sans Suite et archivé.") % chantier.name,
                'type': 'warning',
            }
        }
    
    def _send_client_notification(self, chantier):
        """Send notification email to client."""
        try:
            # Replace placeholder in template
            body = self.client_email_template.replace('[CHANTIER]', chantier.name)
            
            chantier.message_post(
                body=body,
                subject=_("Information concernant votre projet %s") % chantier.name,
                partner_ids=chantier.partner_id.ids,
                message_type='email',
                subtype_id=self.env.ref('mail.mt_comment').id
            )
            
            _logger.info(
                "[LOGGER][INFO][construction.sans_suite] Email envoyé au client %s",
                chantier.partner_id.email
            )
        except Exception as e:
            _logger.warning("Failed to send Sans Suite notification: %s", e)

    def action_cancel(self):
        """Cancel the wizard."""
        return {'type': 'ir.actions.act_window_close'}
