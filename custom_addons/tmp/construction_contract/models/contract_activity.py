# -*- coding: utf-8 -*-
"""
Contract Activity Model
Tracks all activities and events in the contract lifecycle for timeline display
"""

from odoo import models, fields, api, _
import json
import logging

_logger = logging.getLogger(__name__)


class ConstructionContractActivity(models.Model):
    """
    Contract Activity Timeline
    
    Records all significant events in a contract's lifecycle:
    - Creation, generation, sending
    - Portal access and page validations
    - Signature and reminders
    
    Used to display a visual timeline in the contract form view.
    """
    
    _name = 'construction.contract.activity'
    _description = 'Contract Activity Timeline'
    _order = 'create_date desc, id desc'
    _rec_name = 'activity_type'
    
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
    
    activity_type = fields.Selection([
        ('created', 'Création'),
        ('generated', 'PDF généré'),
        ('sent', 'Envoyé'),
        ('viewed', 'Consulté'),
        ('page_validated', 'Page validée'),
        ('signed', 'Signé'),
        ('reminder', 'Relance envoyée'),
        ('state_change', 'Changement de statut'),
        ('modified', 'Modifié'),
        ('archived', 'Archivé'),
    ], string='Activity Type', required=True, index=True)
    
    description = fields.Text(
        string='Description',
        help="Detailed description of the activity"
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
    
    metadata = fields.Text(
        string='Metadata',
        help="Additional JSON data about the activity"
    )
    
    # ============================================================
    # COMPUTED FIELDS
    # ============================================================
    
    icon = fields.Char(
        string='Icon',
        compute='_compute_display_info',
        help="Font Awesome icon class for timeline display"
    )
    
    color = fields.Char(
        string='Color',
        compute='_compute_display_info',
        help="CSS color class for timeline display"
    )
    
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )
    
    # ============================================================
    # COMPUTE METHODS
    # ============================================================
    
    @api.depends('activity_type')
    def _compute_display_info(self):
        """Compute icon and color based on activity type"""
        icon_map = {
            'created': ('fa-plus-circle', 'text-primary'),
            'generated': ('fa-file-pdf-o', 'text-info'),
            'sent': ('fa-paper-plane', 'text-warning'),
            'viewed': ('fa-eye', 'text-muted'),
            'page_validated': ('fa-check', 'text-info'),
            'signed': ('fa-pencil-square-o', 'text-success'),
            'reminder': ('fa-bell', 'text-warning'),
            'state_change': ('fa-exchange', 'text-primary'),
            'modified': ('fa-edit', 'text-muted'),
            'archived': ('fa-archive', 'text-danger'),
        }
        
        for record in self:
            icon, color = icon_map.get(record.activity_type, ('fa-circle', 'text-muted'))
            record.icon = icon
            record.color = color
    
    @api.depends('activity_type', 'description', 'create_date')
    def _compute_display_name(self):
        """Compute display name for the activity"""
        type_labels = dict(self._fields['activity_type'].selection)
        for record in self:
            label = type_labels.get(record.activity_type, record.activity_type)
            if record.description:
                record.display_name = f"{label}: {record.description[:50]}"
            else:
                record.display_name = label
    
    # ============================================================
    # HELPER METHODS
    # ============================================================
    
    def get_metadata_dict(self):
        """Parse metadata JSON and return as dictionary"""
        self.ensure_one()
        if self.metadata:
            try:
                return json.loads(self.metadata)
            except json.JSONDecodeError:
                _logger.warning(f"Invalid JSON metadata for activity {self.id}")
                return {}
        return {}
    
    def set_metadata(self, data):
        """Set metadata from dictionary"""
        self.ensure_one()
        if data:
            self.metadata = json.dumps(data, default=str)
        else:
            self.metadata = False
    
    # ============================================================
    # CLASS METHODS FOR LOGGING
    # ============================================================
    
    @api.model
    def _log_activity(self, contract, activity_type, description=None, user=None, ip_address=None, metadata=None):
        """
        Create an activity log entry for a contract
        
        Args:
            contract: construction.contract record
            activity_type: str - one of the selection values
            description: str - optional description
            user: res.users record - defaults to current user
            ip_address: str - optional IP address
            metadata: dict - optional additional data
            
        Returns:
            construction.contract.activity record
        """
        vals = {
            'contract_id': contract.id,
            'activity_type': activity_type,
            'description': description,
            'user_id': (user or self.env.user).id if user is not False else self.env.user.id,
            'ip_address': ip_address,
        }
        
        if metadata:
            vals['metadata'] = json.dumps(metadata, default=str)
        
        activity = self.sudo().create(vals)
        
        _logger.info(
            f"Activity logged for contract {contract.name}: "
            f"{activity_type} by {vals.get('user_id')} from {ip_address or 'N/A'}"
        )
        
        return activity
    
    @api.model
    def log_contract_created(self, contract):
        """Log contract creation"""
        return self._log_activity(
            contract,
            'created',
            _("Contract created"),
            metadata={
                'chantier': contract.chantier_id.name,
                'subcontractor': contract.subcontractor_id.name,
                'lots': contract.lot_ids.mapped('name'),
            }
        )
    
    @api.model
    def log_pdf_generated(self, contract):
        """Log PDF generation"""
        return self._log_activity(
            contract,
            'generated',
            _("PDF document generated"),
            metadata={
                'template': contract.template_id.name if contract.template_id else None,
                'page_count': contract.pdf_page_count,
            }
        )
    
    @api.model
    def log_contract_sent(self, contract, channel='both'):
        """Log contract sent for signature"""
        channel_labels = {
            'email': _("Email"),
            'sms': _("SMS"),
            'both': _("Email + SMS"),
        }
        return self._log_activity(
            contract,
            'sent',
            _("Contract sent via %s") % channel_labels.get(channel, channel),
            metadata={
                'channel': channel,
                'recipient': contract.subcontractor_id.email,
                'recipient_phone': contract.subcontractor_id.mobile,
            }
        )
    
    @api.model
    def log_portal_viewed(self, contract, ip_address=None):
        """Log portal access"""
        return self._log_activity(
            contract,
            'viewed',
            _("Contract viewed in portal"),
            user=self.env.ref('base.public_user', raise_if_not_found=False) or self.env.user,
            ip_address=ip_address,
        )
    
    @api.model
    def log_page_validated(self, contract, page_number, ip_address=None):
        """Log page validation"""
        return self._log_activity(
            contract,
            'page_validated',
            _("Page %d validated") % page_number,
            user=self.env.ref('base.public_user', raise_if_not_found=False) or self.env.user,
            ip_address=ip_address,
            metadata={'page_number': page_number}
        )
    
    @api.model
    def log_contract_signed(self, contract, ip_address=None, signature_method=None):
        """Log contract signature"""
        return self._log_activity(
            contract,
            'signed',
            _("Contract signed electronically"),
            user=self.env.ref('base.public_user', raise_if_not_found=False) or self.env.user,
            ip_address=ip_address,
            metadata={
                'signature_method': signature_method,
                'signature_date': fields.Datetime.now().isoformat(),
            }
        )
    
    @api.model
    def log_reminder_sent(self, contract, reminder_number=1):
        """Log reminder sent"""
        return self._log_activity(
            contract,
            'reminder',
            _("Reminder #%d sent") % reminder_number,
            metadata={'reminder_number': reminder_number}
        )
    
    @api.model
    def log_state_change(self, contract, old_state, new_state):
        """Log state change"""
        return self._log_activity(
            contract,
            'state_change',
            _("Status changed from '%s' to '%s'") % (old_state, new_state),
            metadata={
                'old_state': old_state,
                'new_state': new_state,
            }
        )
