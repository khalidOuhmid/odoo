# -*- coding: utf-8 -*-
"""
Contract Send Wizard

Wizard to send contract to subcontractor via Email/SMS with portal signing link.
Follows construction_subcontractor patterns for token-based portal access.
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import secrets


class ContractSendWizard(models.TransientModel):
    """Wizard to send contract notification to subcontractor."""
    
    _name = 'contract.send.wizard'
    _description = 'Envoi du Contrat au Sous-traitant'
    
    # ============= RELATION ============= #
    contract_id = fields.Many2one(
        'construction.contract',
        string='Contrat',
        required=True,
        readonly=True
    )
    
    subcontractor_id = fields.Many2one(
        'res.partner',
        string='Sous-traitant',
        related='contract_id.subcontractor_id',
        readonly=True
    )
    
    chantier_id = fields.Many2one(
        'construction.chantier',
        string='Chantier',
        related='contract_id.chantier_id',
        readonly=True
    )
    
    # ============= NOTIFICATION OPTIONS ============= #
    send_email = fields.Boolean(
        string='Envoyer par Email',
        default=True
    )
    
    send_sms = fields.Boolean(
        string='Envoyer par SMS',
        default=False
    )
    
    recipient_email = fields.Char(
        string='Email',
        compute='_compute_recipient_info',
        store=True,
        readonly=False
    )
    
    recipient_phone = fields.Char(
        string='Téléphone Mobile',
        compute='_compute_recipient_info',
        store=True,
        readonly=False
    )
    
    portal_url = fields.Char(
        string='Lien du Portail',
        compute='_compute_portal_url'
    )
    
    message_preview = fields.Text(
        string='Aperçu du Message',
        compute='_compute_message_preview'
    )
    
    # ============= COMPUTED METHODS ============= #
    @api.depends('subcontractor_id')
    def _compute_recipient_info(self):
        for wizard in self:
            if wizard.subcontractor_id:
                wizard.recipient_email = wizard.subcontractor_id.email or ''
                wizard.recipient_phone = wizard.subcontractor_id.mobile or wizard.subcontractor_id.phone or ''
            else:
                wizard.recipient_email = ''
                wizard.recipient_phone = ''
    
    @api.depends('contract_id')
    def _compute_portal_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for wizard in self:
            if wizard.contract_id:
                # Ensure contract has signing token
                if not wizard.contract_id.signing_token:
                    wizard.contract_id.sudo()._generate_signing_token()
                wizard.portal_url = f"{base_url}/contract/sign/{wizard.contract_id.signing_token}"
            else:
                wizard.portal_url = ''
    
    @api.depends('contract_id', 'subcontractor_id', 'portal_url')
    def _compute_message_preview(self):
        for wizard in self:
            if wizard.contract_id and wizard.subcontractor_id:
                wizard.message_preview = _(
                    "Bonjour %s,\n\n"
                    "Votre contrat de sous-traitance pour le chantier '%s' est prêt.\n\n"
                    "Veuillez cliquer sur le lien ci-dessous pour consulter et signer le contrat :\n"
                    "%s\n\n"
                    "Cordialement,\n"
                    "BLG Groupe"
                ) % (
                    wizard.subcontractor_id.name,
                    wizard.chantier_id.name if wizard.chantier_id else '',
                    wizard.portal_url or '[Lien du portail]'
                )
            else:
                wizard.message_preview = ''
    
    # ============= ACTIONS ============= #
    def action_send(self):
        """Send contract notification via Email and/or SMS."""
        self.ensure_one()
        
        if not self.send_email and not self.send_sms:
            raise UserError(_("Veuillez sélectionner au moins un mode d'envoi (Email ou SMS)."))
        
        contract = self.contract_id
        partner = self.subcontractor_id
        
        # Validate contact info
        if self.send_email and not self.recipient_email:
            raise UserError(_("L'adresse email du sous-traitant est manquante."))
        
        if self.send_sms and not self.recipient_phone:
            raise UserError(_("Le numéro de téléphone du sous-traitant est manquant."))
        
        # 1. Send Email
        if self.send_email:
            self._send_email(contract, partner)
        
        # 2. Send SMS
        if self.send_sms:
            self._send_sms(contract, partner)
        
        # 3. Update contract state
        contract.write({
            'state': 'sent',
            'sent_date': fields.Datetime.now(),
        })
        
        # 4. Log in contract chatter
        send_methods = ', '.join(filter(None, [
            'Email' if self.send_email else None,
            'SMS' if self.send_sms else None
        ]))
        notification_body = _(
            "📧 Contrat de sous-traitance envoyé à <b>%s</b> par %s.<br/>"
            "<small>Contrat: %s | Lien de signature généré</small>"
        ) % (partner.name, send_methods, contract.name)
        
        contract.message_post(
            body=notification_body,
            message_type='notification'
        )
        
        # 5. Also log in chantier chatter for visibility
        if self.chantier_id:
            chantier_body = _(
                "📄 <b>Contrat envoyé pour signature</b><br/>"
                "Sous-traitant: <b>%s</b><br/>"
                "Contrat: %s<br/>"
                "Envoyé par: %s"
            ) % (partner.name, contract.name, send_methods)
            
            self.chantier_id.message_post(
                body=chantier_body,
                message_type='notification',
                subtype_xmlid='mail.mt_note'
            )
        
        # 5. Return to chantier
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'construction.chantier',
            'res_id': self.chantier_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def _send_email(self, contract, partner):
        """Send contract notification email."""
        template = self.env.ref('construction_contract.email_template_contract_send', raise_if_not_found=False)
        
        if template:
            template.with_context(
                portal_url=self.portal_url,
                recipient_email=self.recipient_email
            ).send_mail(contract.id, force_send=True)
        else:
            # Fallback: direct mail.mail creation
            mail_vals = {
                'subject': _("Contrat de Sous-traitance - %s") % contract.name,
                'body_html': self.message_preview.replace('\n', '<br/>'),
                'email_from': self.env.company.email or 'noreply@blg-groupe.fr',
                'email_to': self.recipient_email,
                'auto_delete': True,
            }
            mail = self.env['mail.mail'].sudo().create(mail_vals)
            mail.send()
    
    def _send_sms(self, contract, partner):
        """Send contract notification SMS using Odoo IAP or partner SMS method."""
        sms_body = _(
            "BLG Groupe: Votre contrat pour le chantier %s est prêt. "
            "Signez ici: %s"
        ) % (
            self.chantier_id.name if self.chantier_id else contract.name,
            self.portal_url
        )
        
        # Try using partner's send_sms method if available (from construction_subcontractor)
        if hasattr(partner, 'send_sms') and callable(getattr(partner, 'send_sms')):
            partner.send_sms(sms_body)
        else:
            # Fallback: Use sms.sms model if available
            SmsModel = self.env.get('sms.sms')
            if SmsModel:
                SmsModel.sudo().create({
                    'number': self.recipient_phone,
                    'body': sms_body,
                    'partner_id': partner.id,
                }).send()
            else:
                # Log warning but don't fail
                import logging
                _logger = logging.getLogger(__name__)
                _logger.warning("SMS module not available, skipping SMS send for contract %s", contract.name)
