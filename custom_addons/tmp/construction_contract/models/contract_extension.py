# -*- coding: utf-8 -*-
"""
Contract Extension for Timeline and Audit
Extends construction.contract with activity logging and audit trail
"""

from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class ConstructionContractExtension(models.Model):
    """
    Extension of Construction Contract for BTPVision
    
    Adds:
    - Link to unified template system (construction.document.template)
    - Communication channel preference
    - Activity timeline (One2many to construction.contract.activity)
    - Audit trail (One2many to construction.contract.audit)
    - Automatic logging on state changes
    """
    
    _inherit = 'construction.contract'
    
    # ============================================================
    # NEW FIELDS - Template System
    # ============================================================
    
    document_template_id = fields.Many2one(
        'construction.document.template',
        string='Document Template',
        domain="[('template_type', '=', 'contract'), ('is_active', '=', True)]",
        help="Unified document template from construction_templates module"
    )
    
    # ============================================================
    # NEW FIELDS - Communication
    # ============================================================
    
    communication_channel = fields.Selection([
        ('email', 'Email uniquement'),
        ('sms', 'SMS uniquement'),
        ('both', 'Email + SMS'),
    ], string='Canal de communication', default='both',
       help="Preferred communication channel for sending contracts")
    
    # ============================================================
    # NEW FIELDS - Activity Timeline
    # ============================================================
    
    activity_log_ids = fields.One2many(
        'construction.contract.activity',
        'contract_id',
        string='Activity Timeline',
        help="Timeline of all activities on this contract"
    )
    
    activity_count = fields.Integer(
        string='Activity Count',
        compute='_compute_activity_count',
        help="Number of activities logged"
    )
    
    # ============================================================
    # NEW FIELDS - Audit Trail
    # ============================================================
    
    audit_log_ids = fields.One2many(
        'construction.contract.audit',
        'contract_id',
        string='Audit Trail',
        help="Complete audit trail for compliance"
    )
    
    audit_count = fields.Integer(
        string='Audit Count',
        compute='_compute_audit_count',
        help="Number of audit entries"
    )
    
    # ============================================================
    # COMPUTED FIELDS
    # ============================================================
    
    @api.depends('activity_log_ids')
    def _compute_activity_count(self):
        """Compute number of activities"""
        for contract in self:
            contract.activity_count = len(contract.activity_log_ids)
    
    @api.depends('audit_log_ids')
    def _compute_audit_count(self):
        """Compute number of audit entries"""
        for contract in self:
            contract.audit_count = len(contract.audit_log_ids)
    
    # ============================================================
    # CRUD OVERRIDES
    # ============================================================
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to log activity and audit"""
        contracts = super().create(vals_list)
        
        ActivityLog = self.env['construction.contract.activity']
        AuditLog = self.env['construction.contract.audit']
        
        for contract in contracts:
            # Log activity
            ActivityLog.log_contract_created(contract)
            # Log audit
            AuditLog.log_contract_created(contract)
        
        return contracts
    
    def write(self, vals):
        """Override write to log state changes and modifications"""
        # Track old states before write
        old_states = {}
        tracked_fields = ['state', 'subcontractor_id', 'chantier_id', 'lot_ids', 
                          'total_amount_ttc', 'template_id', 'document_template_id']
        old_values = {}
        
        if 'state' in vals:
            for contract in self:
                old_states[contract.id] = contract.state
        
        # Track other important field changes for audit
        changed_fields = [f for f in tracked_fields if f in vals]
        if changed_fields:
            for contract in self:
                old_values[contract.id] = {
                    f: self._get_field_value_for_audit(contract, f) 
                    for f in changed_fields
                }
        
        # Perform the write
        result = super().write(vals)
        
        # Log state changes
        if 'state' in vals:
            ActivityLog = self.env['construction.contract.activity']
            AuditLog = self.env['construction.contract.audit']
            
            for contract in self:
                old_state = old_states.get(contract.id)
                new_state = vals['state']
                
                if old_state and old_state != new_state:
                    # Log activity
                    ActivityLog.log_state_change(contract, old_state, new_state)
                    # Log audit
                    AuditLog.log_state_change(contract, old_state, new_state)
        
        # Log other modifications to audit trail
        if changed_fields and 'state' not in changed_fields:
            AuditLog = self.env['construction.contract.audit']
            for contract in self:
                if contract.id in old_values:
                    new_values = {
                        f: self._get_field_value_for_audit(contract, f) 
                        for f in changed_fields
                    }
                    AuditLog.log_modification(
                        contract, 
                        changed_fields, 
                        old_values[contract.id], 
                        new_values
                    )
        
        return result
    
    def _get_field_value_for_audit(self, contract, field_name):
        """Get field value in a format suitable for audit logging"""
        field = contract._fields.get(field_name)
        if not field:
            return None
        
        value = getattr(contract, field_name)
        
        if field.type == 'many2one':
            return value.name if value else None
        elif field.type == 'many2many':
            return value.mapped('name') if value else []
        elif field.type == 'one2many':
            return len(value) if value else 0
        elif field.type == 'selection':
            return value
        elif field.type in ('monetary', 'float'):
            return float(value) if value else 0.0
        else:
            return str(value) if value else None
    
    # ============================================================
    # BUSINESS METHODS - Enhanced with logging
    # ============================================================
    
    def action_generate_pdf(self):
        """Override to log PDF generation"""
        result = super().action_generate_pdf()
        
        ActivityLog = self.env['construction.contract.activity']
        AuditLog = self.env['construction.contract.audit']
        
        for contract in self:
            ActivityLog.log_pdf_generated(contract)
            AuditLog.log_pdf_generated(contract)
        
        return result
    
    def action_send_for_signature(self):
        """Override to log sending with channel info"""
        result = super().action_send_for_signature()
        
        ActivityLog = self.env['construction.contract.activity']
        AuditLog = self.env['construction.contract.audit']
        
        for contract in self:
            channel = contract.communication_channel or 'both'
            ActivityLog.log_contract_sent(contract, channel)
            AuditLog.log_contract_sent(contract, channel)
        
        return result
    
    def action_send_reminder(self):
        """Override to log reminder"""
        result = super().action_send_reminder()
        
        ActivityLog = self.env['construction.contract.activity']
        
        for contract in self:
            # Count existing reminders to get reminder number
            reminder_count = len(contract.activity_log_ids.filtered(
                lambda a: a.activity_type == 'reminder'
            ))
            ActivityLog.log_reminder_sent(contract, reminder_count + 1)
        
        return result
    
    # ============================================================
    # PORTAL LOGGING METHODS
    # ============================================================
    
    def log_portal_access(self, ip_address=None, user_agent=None):
        """Log portal access from signature portal controller"""
        self.ensure_one()
        
        ActivityLog = self.env['construction.contract.activity']
        AuditLog = self.env['construction.contract.audit']
        
        ActivityLog.log_portal_viewed(self, ip_address)
        AuditLog.log_portal_view(self, ip_address, user_agent)
    
    def log_page_validation(self, page_number, ip_address=None):
        """Log page validation from signature portal"""
        self.ensure_one()
        
        ActivityLog = self.env['construction.contract.activity']
        ActivityLog.log_page_validated(self, page_number, ip_address)
    
    def log_signature_completed(self, ip_address=None, user_agent=None, signature_method=None):
        """Log signature completion from signature portal"""
        self.ensure_one()
        
        ActivityLog = self.env['construction.contract.activity']
        AuditLog = self.env['construction.contract.audit']
        
        ActivityLog.log_contract_signed(self, ip_address, signature_method)
        AuditLog.log_signature(
            self, 
            signature_data={'method': signature_method},
            ip_address=ip_address, 
            user_agent=user_agent
        )
    
    # ============================================================
    # INTEGRITY VERIFICATION
    # ============================================================
    
    def action_verify_integrity(self):
        """Verify PDF document integrity"""
        self.ensure_one()
        
        AuditLog = self.env['construction.contract.audit']
        
        # Create a temporary audit entry for verification
        audit = AuditLog.create({
            'contract_id': self.id,
            'action': 'integrity_check',
        })
        
        result = audit.verify_document_integrity(self)
        
        # Log the result
        AuditLog.log_integrity_check(self, result)
        
        # Return notification
        notification_type = 'success' if result.get('status') == 'valid' else 'danger'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Integrity Check'),
                'message': result.get('message', _('Check completed')),
                'type': notification_type,
                'sticky': result.get('status') != 'valid',
            }
        }
    
    # ============================================================
    # VIEW ACTIONS
    # ============================================================
    
    def action_view_activity_timeline(self):
        """Open activity timeline view"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Activity Timeline'),
            'res_model': 'construction.contract.activity',
            'view_mode': 'tree,form',
            'domain': [('contract_id', '=', self.id)],
            'context': {'default_contract_id': self.id},
        }
    
    def action_view_audit_trail(self):
        """Open audit trail view"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Audit Trail'),
            'res_model': 'construction.contract.audit',
            'view_mode': 'tree,form',
            'domain': [('contract_id', '=', self.id)],
            'context': {'default_contract_id': self.id},
        }
