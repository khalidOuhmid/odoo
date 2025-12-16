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
    
    # Document content for preview - NOT stored (TransientModel doesn't support stored Binary well)
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
    
    # Preview tracking - must preview before validating
    has_previewed = fields.Boolean(
        string='Document prévisualisé',
        default=False,
        help="Indique si le document a été ouvert en prévisualisation"
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
    
    def action_preview(self):
        """Open document preview and mark as previewed.
        
        This action MUST be called before action_validate to ensure
        the administrator has actually viewed the document.
        """
        self.ensure_one()
        
        if not self.doc_content:
            raise UserError(_("Aucun document à prévisualiser."))
        
        # Mark as previewed
        self.has_previewed = True
        
        # Return download action for preview
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content?model=res.partner&id={self.partner_id.id}&field=doc_{self.doc_type}&filename={self.doc_filename}&download=false',
            'target': 'new',
        }
    
    def action_validate(self):
        """Mark document as valid.
        
        REQUIRES: Document must be previewed first (has_previewed=True)
        Sets validation fields, logs in chatter, recomputes compliance.
        """
        self.ensure_one()
        
        if not self.doc_content:
            raise UserError(_("Aucun document à valider."))
        
        # Only require preview for PDFs (images have inline preview)
        if self.doc_mimetype == 'application/pdf' and not self.has_previewed:
            raise UserError(_(
                "Vous devez d'abord prévisualiser le document PDF avant de le valider.\n"
                "Cliquez sur 'Prévisualiser' pour ouvrir le document."
            ))
        
        if self.current_status == 'valid':
            raise UserError(_("Ce document est déjà validé."))
        
        field_name = f'doc_{self.doc_type}'
        
        # Update validation fields (triggers status recompute)
        self.partner_id.write({
            f'{field_name}_is_validated': True,
            f'{field_name}_validated_by': self.env.user.id,
            f'{field_name}_validated_at': fields.Datetime.now(),
        })
        
        # Log in chatter with audit trail
        doc_name = dict(self._fields['doc_type'].selection).get(self.doc_type)
        self.partner_id.message_post(
            body=_("✅ Document <b>%s</b> validé par %s le %s") % (
                doc_name,
                self.env.user.name,
                fields.Datetime.now().strftime('%d/%m/%Y %H:%M')
            ),
            message_type='notification'
        )
        
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
    
    def action_request(self):
        """Re-request this document from the subcontractor.
        
        Archives the current document with reason='requested',
        clears the document field, and sends notification to subcontractor.
        Used when a validated document needs to be replaced or refreshed.
        """
        self.ensure_one()
        
        if not self.doc_content:
            raise UserError(_("Aucun document à redemander."))
        
        field_name = f'doc_{self.doc_type}'
        doc_name = dict(self._fields['doc_type'].selection).get(self.doc_type)
        
        # Get validation info before clearing
        validation_field = f'{field_name}_is_validated'
        was_validated = getattr(self.partner_id, validation_field, False)
        validated_by = getattr(self.partner_id, f'{field_name}_validated_by', False)
        validated_at = getattr(self.partner_id, f'{field_name}_validated_at', False)
        
        # Archive the current document
        self.env['subcontractor.document.archive'].create({
            'partner_id': self.partner_id.id,
            'document_type': self.doc_type,
            'file_data': self.doc_content,
            'filename': self.doc_filename,
            'expiry_date': getattr(self.partner_id, f'{field_name}_expiry', False),
            'reason': 'requested',
            'notes': _("Document redemandé par %s") % self.env.user.name,
            'was_validated': was_validated,
            'validated_by_name': validated_by.name if validated_by else False,
            'original_validated_at': validated_at,
        })
        
        # Clear the document (this sets status to 'missing')
        self.partner_id.write({
            field_name: False,
            f'{field_name}_filename': False,
            f'{field_name}_is_validated': False,
            f'{field_name}_validated_by': False,
            f'{field_name}_validated_at': False,
        })
        
        # Log in chatter
        self.partner_id.message_post(
            body=_("🔄 Document <b>%s</b> redemandé par %s. En attente de nouveau document.") % (
                doc_name,
                self.env.user.name
            ),
            message_type='notification'
        )
        
        # Send notification to subcontractor
        self._send_request_notification(doc_name)
        
        return {'type': 'ir.actions.act_window_close'}
    
    def _send_request_notification(self, doc_name):
        """Send email notification to subcontractor about document re-request.
        
        Args:
            doc_name: Human-readable document name
        """
        if not self.partner_id.email:
            return
        
        # Try to send email if template exists
        template_xmlid = 'construction_subcontractor.email_template_document_request'
        template = self.env.ref(template_xmlid, raise_if_not_found=False)
        
        if template:
            template.with_context(
                doc_name=doc_name
            ).send_mail(self.partner_id.id, force_send=True)
        else:
            # Fallback: Create activity for manual follow-up
            self.env['mail.activity'].create({
                'res_model_id': self.env['ir.model']._get('res.partner').id,
                'res_id': self.partner_id.id,
                'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                'summary': _("Envoyer demande: %s") % doc_name,
                'note': _("Envoyer email manuel au sous-traitant pour demander le document: %s") % doc_name,
                'user_id': self.env.user.id,
            })
