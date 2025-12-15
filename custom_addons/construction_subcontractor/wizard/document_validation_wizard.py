# -*- coding: utf-8 -*-
"""
Document Validation Wizard

Provides a preview/validate/reject workflow for documents submitted
by subcontractors. Used by administrators to verify uploaded documents
before marking them as valid or rejecting them with notification.
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class DocumentValidationWizard(models.TransientModel):
    """Wizard to validate or reject a submitted document.
    
    State Machine:
    - to_check: Document awaiting validation
    - valid: Document validated by admin
    - rejected: Document rejected with reason, notification sent
    """
    _name = 'document.validation.wizard'
    _description = 'Validation de Document Sous-traitant'
    
    # ============= WIZARD FIELDS ============= #
    partner_id = fields.Many2one(
        'res.partner',
        string='Sous-traitant',
        required=True,
        readonly=True
    )
    
    doc_type = fields.Selection([
        ('kbis', 'KBIS'),
        ('urssaf', 'Attestation URSSAF'),
        ('insurance_dec', 'Assurance Décennale'),
        ('insurance_pro', 'RC Professionnelle'),
        ('cni', 'Carte d\'Identité (Gérant)'),
        ('rib', 'RIB'),
    ], string='Type de Document', required=True, readonly=True)
    
    # Computed document content for preview
    doc_content = fields.Binary(
        compute='_compute_doc_content',
        string='Document'
    )
    doc_filename = fields.Char(
        compute='_compute_doc_content',
        string='Nom du fichier'
    )
    doc_mimetype = fields.Char(
        compute='_compute_doc_content',
        string='Type MIME'
    )
    
    current_status = fields.Char(
        compute='_compute_doc_content',
        string='Statut Actuel'
    )
    
    # Rejection reason (required when rejecting)
    rejection_reason = fields.Text(
        string='Motif du rejet',
        help="Expliquez pourquoi le document est rejeté (sera notifié au sous-traitant)"
    )
    
    # ============= COMPUTED METHODS ============= #
    @api.depends('partner_id', 'doc_type')
    def _compute_doc_content(self):
        """Load document content from partner record for preview."""
        for wizard in self:
            if not wizard.partner_id or not wizard.doc_type:
                wizard.doc_content = False
                wizard.doc_filename = False
                wizard.doc_mimetype = False
                wizard.current_status = False
                continue
            
            field_name = f'doc_{wizard.doc_type}'
            filename_field = f'{field_name}_filename'
            status_field = f'{field_name}_status'
            
            wizard.doc_content = getattr(wizard.partner_id, field_name, False)
            wizard.doc_filename = getattr(wizard.partner_id, filename_field, False)
            wizard.current_status = getattr(wizard.partner_id, status_field, False)
            
            # Determine MIME type from filename extension
            filename = wizard.doc_filename or ''
            if filename.lower().endswith('.pdf'):
                wizard.doc_mimetype = 'application/pdf'
            elif filename.lower().endswith(('.jpg', '.jpeg')):
                wizard.doc_mimetype = 'image/jpeg'
            elif filename.lower().endswith('.png'):
                wizard.doc_mimetype = 'image/png'
            else:
                wizard.doc_mimetype = 'application/octet-stream'
    
    # ============= ACTIONS ============= #
    def action_validate(self):
        """Mark document as valid.
        
        Sets status to 'valid', logs in chatter, recomputes compliance.
        """
        self.ensure_one()
        
        if not self.doc_content:
            raise UserError(_("Aucun document à valider."))
        
        if self.current_status == 'valid':
            raise UserError(_("Ce document est déjà validé."))
        
        field_name = f'doc_{self.doc_type}'
        status_field = f'{field_name}_status'
        
        # Update status to valid (force it)
        # Note: Status is normally computed, but we can set expiry to force valid
        # For now, we'll add a manual validation field
        self.partner_id.write({
            f'{field_name}_validated': True
        })
        
        # Log in chatter
        doc_name = dict(self._fields['doc_type'].selection).get(self.doc_type)
        self.partner_id.message_post(
            body=_("✅ Document <b>%s</b> validé par %s") % (
                doc_name,
                self.env.user.name
            ),
            message_type='notification'
        )
        
        # Recompute compliance
        self.partner_id._compute_compliance_state()
        
        return {'type': 'ir.actions.act_window_close'}
    
    def action_reject(self):
        """Reject document and notify subcontractor.
        
        Sets status to 'rejected', logs in chatter, sends notification.
        """
        self.ensure_one()
        
        if not self.doc_content:
            raise UserError(_("Aucun document à rejeter."))
        
        if not self.rejection_reason:
            raise UserError(_("Veuillez indiquer un motif de rejet."))
        
        field_name = f'doc_{self.doc_type}'
        
        # Clear the document (forces status to 'missing')
        self.partner_id.write({
            field_name: False,
            f'{field_name}_filename': False,
        })
        
        # Log rejection in chatter
        doc_name = dict(self._fields['doc_type'].selection).get(self.doc_type)
        self.partner_id.message_post(
            body=_("❌ Document <b>%s</b> rejeté par %s<br/><b>Motif:</b> %s") % (
                doc_name,
                self.env.user.name,
                self.rejection_reason
            ),
            message_type='comment',
            subtype_xmlid='mail.mt_note'
        )
        
        # Send notification to subcontractor
        self._send_rejection_notification(doc_name)
        
        # Recompute compliance
        self.partner_id._compute_compliance_state()
        
        return {'type': 'ir.actions.act_window_close'}
    
    def _send_rejection_notification(self, doc_name):
        """Send email notification to subcontractor about rejection.
        
        Args:
            doc_name: Human-readable document name
        """
        if not self.partner_id.email:
            return
        
        template_xmlid = 'construction_subcontractor.email_template_document_rejected'
        template = self.env.ref(template_xmlid, raise_if_not_found=False)
        
        if template:
            template.with_context(
                doc_name=doc_name,
                rejection_reason=self.rejection_reason
            ).send_mail(self.partner_id.id, force_send=True)
        else:
            # Fallback: Create activity for follow-up
            self.env['mail.activity'].create({
                'res_model_id': self.env['ir.model']._get('res.partner').id,
                'res_id': self.partner_id.id,
                'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                'summary': _("Notifier rejet: %s") % doc_name,
                'note': _("Envoyer email manuel au sous-traitant concernant le rejet.<br/>Motif: %s") % self.rejection_reason,
                'user_id': self.env.user.id,
            })
    
    def action_download(self):
        """Download the document for detailed inspection."""
        self.ensure_one()
        
        if not self.doc_content:
            raise UserError(_("Aucun document à télécharger."))
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content?model=res.partner&id={self.partner_id.id}&field=doc_{self.doc_type}&filename={self.doc_filename}&download=true',
            'target': 'new',
        }
