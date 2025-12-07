# -*- coding: utf-8 -*-
"""
Contract Audit Model
Provides complete audit trail for contract actions with integrity verification
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import hashlib
import base64
import json
import logging

_logger = logging.getLogger(__name__)


class ConstructionContractAudit(models.Model):
    """
    Contract Audit Log
    
    Records all auditable actions on contracts with:
    - User identification and IP tracking
    - Document integrity verification via SHA-256 hashing
    - Complete change history for compliance
    
    Supports eIDAS compliance requirements for electronic signatures.
    """
    
    _name = 'construction.contract.audit'
    _description = 'Contract Audit Log'
    _order = 'create_date desc, id desc'
    _rec_name = 'action'
    
    # ============================================================
    # FIELDS
    # ============================================================
    
    contract_id = fields.Many2one(
        'construction.contract',
        string='Contract',
        required=True,
        ondelete='cascade',
        index=True,
        help="Related contract"
    )
    
    action = fields.Selection([
        ('create', 'Création'),
        ('state_change', 'Changement état'),
        ('pdf_generate', 'Génération PDF'),
        ('send', 'Envoi'),
        ('view', 'Consultation'),
        ('sign', 'Signature'),
        ('modify', 'Modification'),
        ('archive', 'Archivage'),
        ('integrity_check', 'Vérification intégrité'),
    ], string='Action', required=True, index=True)
    
    old_value = fields.Text(
        string='Old Value',
        help="Previous value before the change (JSON format)"
    )
    
    new_value = fields.Text(
        string='New Value',
        help="New value after the change (JSON format)"
    )
    
    user_id = fields.Many2one(
        'res.users',
        string='User',
        default=lambda self: self.env.user,
        help="User who performed the action"
    )
    
    ip_address = fields.Char(
        string='IP Address',
        help="IP address from which the action was performed"
    )
    
    user_agent = fields.Char(
        string='User Agent',
        help="Browser/client user agent string"
    )
    
    timestamp = fields.Datetime(
        string='Timestamp',
        default=fields.Datetime.now,
        required=True,
        index=True,
        help="Exact time of the action"
    )
    
    # ============================================================
    # INTEGRITY FIELDS
    # ============================================================
    
    hash_before = fields.Char(
        string='Hash Before',
        help="SHA-256 hash of PDF document before the action"
    )
    
    hash_after = fields.Char(
        string='Hash After',
        help="SHA-256 hash of PDF document after the action"
    )
    
    integrity_verified = fields.Boolean(
        string='Integrity Verified',
        default=False,
        help="True if document integrity was verified during this action"
    )
    
    integrity_status = fields.Selection([
        ('valid', 'Valid'),
        ('invalid', 'Invalid'),
        ('not_checked', 'Not Checked'),
    ], string='Integrity Status', default='not_checked')
    
    # ============================================================
    # COMPUTED FIELDS
    # ============================================================
    
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )
    
    action_label = fields.Char(
        string='Action Label',
        compute='_compute_action_label'
    )
    
    # ============================================================
    # COMPUTE METHODS
    # ============================================================
    
    @api.depends('action', 'timestamp', 'contract_id')
    def _compute_display_name(self):
        """Compute display name for the audit entry"""
        action_labels = dict(self._fields['action'].selection)
        for record in self:
            label = action_labels.get(record.action, record.action)
            contract_name = record.contract_id.name if record.contract_id else 'N/A'
            record.display_name = f"{contract_name} - {label}"
    
    @api.depends('action')
    def _compute_action_label(self):
        """Get human-readable action label"""
        action_labels = dict(self._fields['action'].selection)
        for record in self:
            record.action_label = action_labels.get(record.action, record.action)
    
    # ============================================================
    # INTEGRITY METHODS
    # ============================================================
    
    @api.model
    def _compute_pdf_hash(self, pdf_data):
        """
        Compute SHA-256 hash of PDF document
        
        Args:
            pdf_data: bytes or base64 encoded string of PDF content
            
        Returns:
            str: SHA-256 hash in hexadecimal format
        """
        if not pdf_data:
            return False
        
        try:
            # Handle base64 encoded data
            if isinstance(pdf_data, str):
                pdf_bytes = base64.b64decode(pdf_data)
            else:
                pdf_bytes = pdf_data
            
            # Compute SHA-256 hash
            hash_obj = hashlib.sha256(pdf_bytes)
            return hash_obj.hexdigest()
            
        except Exception as e:
            _logger.error(f"Error computing PDF hash: {e}")
            return False
    
    def verify_document_integrity(self, contract):
        """
        Verify the integrity of a contract's PDF document
        
        Args:
            contract: construction.contract record
            
        Returns:
            dict: Verification result with status and details
        """
        self.ensure_one()
        
        if not contract.pdf_document:
            return {
                'status': 'error',
                'message': _("No PDF document to verify"),
            }
        
        current_hash = self._compute_pdf_hash(contract.pdf_document)
        
        # Compare with stored hash
        if contract.pdf_hash_before_signature:
            expected_hash = contract.pdf_hash_before_signature
        elif contract.pdf_hash_after_signature:
            expected_hash = contract.pdf_hash_after_signature
        else:
            return {
                'status': 'warning',
                'message': _("No reference hash stored for comparison"),
                'current_hash': current_hash,
            }
        
        is_valid = current_hash == expected_hash
        
        # Log the verification
        self.write({
            'integrity_verified': True,
            'integrity_status': 'valid' if is_valid else 'invalid',
        })
        
        return {
            'status': 'valid' if is_valid else 'invalid',
            'message': _("Document integrity verified") if is_valid else _("Document integrity compromised!"),
            'expected_hash': expected_hash,
            'current_hash': current_hash,
        }
    
    # ============================================================
    # CLASS METHODS FOR LOGGING
    # ============================================================
    
    @api.model
    def _log_audit(self, contract, action, old_value=None, new_value=None, 
                   user=None, ip_address=None, user_agent=None, 
                   compute_hash=False):
        """
        Create an audit log entry for a contract
        
        Args:
            contract: construction.contract record
            action: str - one of the selection values
            old_value: dict - previous values (will be JSON encoded)
            new_value: dict - new values (will be JSON encoded)
            user: res.users record - defaults to current user
            ip_address: str - optional IP address
            user_agent: str - optional user agent
            compute_hash: bool - whether to compute PDF hash
            
        Returns:
            construction.contract.audit record
        """
        vals = {
            'contract_id': contract.id,
            'action': action,
            'user_id': (user or self.env.user).id,
            'ip_address': ip_address,
            'user_agent': user_agent,
            'timestamp': fields.Datetime.now(),
        }
        
        if old_value:
            vals['old_value'] = json.dumps(old_value, default=str)
        
        if new_value:
            vals['new_value'] = json.dumps(new_value, default=str)
        
        # Compute PDF hash if requested
        if compute_hash and contract.pdf_document:
            pdf_hash = self._compute_pdf_hash(contract.pdf_document)
            if action in ['pdf_generate', 'create']:
                vals['hash_after'] = pdf_hash
            elif action == 'sign':
                vals['hash_before'] = contract.pdf_hash_before_signature
                vals['hash_after'] = pdf_hash
            else:
                vals['hash_before'] = pdf_hash
        
        audit = self.sudo().create(vals)
        
        _logger.info(
            f"Audit logged for contract {contract.name}: "
            f"{action} by user {vals.get('user_id')} from {ip_address or 'N/A'}"
        )
        
        return audit
    
    @api.model
    def log_contract_created(self, contract, ip_address=None, user_agent=None):
        """Log contract creation"""
        return self._log_audit(
            contract,
            'create',
            new_value={
                'name': contract.name,
                'chantier': contract.chantier_id.name,
                'subcontractor': contract.subcontractor_id.name,
                'state': contract.state,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )
    
    @api.model
    def log_state_change(self, contract, old_state, new_state, ip_address=None, user_agent=None):
        """Log state change"""
        return self._log_audit(
            contract,
            'state_change',
            old_value={'state': old_state},
            new_value={'state': new_state},
            ip_address=ip_address,
            user_agent=user_agent,
        )
    
    @api.model
    def log_pdf_generated(self, contract, ip_address=None, user_agent=None):
        """Log PDF generation with hash"""
        return self._log_audit(
            contract,
            'pdf_generate',
            new_value={
                'page_count': contract.pdf_page_count,
                'template': contract.template_id.name if contract.template_id else None,
            },
            ip_address=ip_address,
            user_agent=user_agent,
            compute_hash=True,
        )
    
    @api.model
    def log_contract_sent(self, contract, channel='both', ip_address=None, user_agent=None):
        """Log contract sent"""
        return self._log_audit(
            contract,
            'send',
            new_value={
                'channel': channel,
                'recipient_email': contract.subcontractor_id.email,
                'recipient_phone': contract.subcontractor_id.mobile,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )
    
    @api.model
    def log_portal_view(self, contract, ip_address=None, user_agent=None):
        """Log portal access"""
        return self._log_audit(
            contract,
            'view',
            ip_address=ip_address,
            user_agent=user_agent,
        )
    
    @api.model
    def log_signature(self, contract, signature_data=None, ip_address=None, user_agent=None):
        """Log signature with integrity hash"""
        return self._log_audit(
            contract,
            'sign',
            new_value={
                'signature_date': contract.signature_date.isoformat() if contract.signature_date else None,
                'signature_method': signature_data.get('method') if signature_data else None,
            },
            ip_address=ip_address,
            user_agent=user_agent,
            compute_hash=True,
        )
    
    @api.model
    def log_modification(self, contract, changed_fields, old_values, new_values, 
                         ip_address=None, user_agent=None):
        """Log contract modification"""
        return self._log_audit(
            contract,
            'modify',
            old_value={f: old_values.get(f) for f in changed_fields},
            new_value={f: new_values.get(f) for f in changed_fields},
            ip_address=ip_address,
            user_agent=user_agent,
        )
    
    @api.model
    def log_integrity_check(self, contract, result, ip_address=None, user_agent=None):
        """Log integrity verification"""
        audit = self._log_audit(
            contract,
            'integrity_check',
            new_value=result,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        audit.write({
            'integrity_verified': True,
            'integrity_status': result.get('status', 'not_checked'),
        })
        
        return audit
