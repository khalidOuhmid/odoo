# -*- coding: utf-8 -*-
"""
Document Archive Model

This model manages the archival and versioning of subcontractor documents,
providing a comprehensive audit trail for document changes and updates.
"""

from odoo import models, fields, api
from odoo.exceptions import AccessError
import logging

_logger = logging.getLogger(__name__)


class DocumentArchive(models.Model):
    """
    Document archive for maintaining document version history.
    
    This model stores historical versions of documents when they are:
    - Replaced with new versions
    - Validated or rejected
    - Modified through any workflow action
    
    It provides a complete audit trail for compliance and tracking purposes.
    """
    _name = 'document.archive'
    _description = 'Document Archive - Version History'
    _order = 'create_date desc'
    _rec_name = 'display_name'

    # Core fields
    name = fields.Char(
        string='Original Filename',
        required=True,
        help="Original filename of the archived document"
    )
    
    display_name = fields.Char(
        string='Archive Entry Name',
        compute='_compute_display_name',
        store=True,
        help="Computed display name for archive entries"
    )
    
    document = fields.Binary(
        string='Archived Document',
        attachment=True,
        required=True,
        help="Binary content of the archived document"
    )
    
    document_type = fields.Selection([
        ('identity_card', "Identity Card"),
        ('urssaf', 'URSSAF Certificate'),
        ('kbis', 'KBIS Extract'),
        ('insurance', 'Insurance Certificate'),
        ('rib', 'Bank Details (RIB)')
    ], string='Document Type', required=True, help="Type of archived document")
    
    # Relationships
    partner_id = fields.Many2one(
        'res.partner',
        string='Partner',
        required=True,
        ondelete='cascade',
        index=True,
        help="Partner this document belongs to"
    )
    
    # Archive metadata
    archive_reason = fields.Selection([
        ('replacement', 'Replaced by new version'),
        ('validation', 'Archived after validation'),
        ('rejection', 'Archived after rejection'),
        ('migration', 'Migrated from old system'),
        ('manual', 'Manual archive'),
    ], string='Archive Reason', default='replacement', help="Reason for archiving")
    
    archive_date = fields.Datetime(
        string='Archive Date',
        default=fields.Datetime.now,
        readonly=True,
        help="Date and time when document was archived"
    )
    
    archived_by = fields.Many2one(
        'res.users',
        string='Archived By',
        default=lambda self: self.env.user,
        readonly=True,
        help="User who triggered the archive action"
    )
    
    # Document metadata at time of archiving
    original_expiry_date = fields.Date(
        string='Original Expiry Date',
        help="Expiry date of the document when it was archived"
    )
    
    original_status = fields.Char(
        string='Original Status',
        help="Document status when archived (valid, expired, etc.)"
    )
    
    # File information
    file_size = fields.Integer(
        string='File Size (bytes)',
        compute='_compute_file_info',
        store=True,
        help="Size of the archived document in bytes"
    )
    
    # Access and security
    access_log_ids = fields.One2many(
        'document.archive.access.log',
        'archive_id',
        string='Access Logs',
        help="Log of access attempts to this archived document"
    )

    # Computed fields
    partner_name = fields.Char(
        related='partner_id.name',
        string='Partner Name',
        store=True,
        help="Name of the partner for easy searching"
    )
    
    is_recent = fields.Boolean(
        string='Is Recent',
        compute='_compute_is_recent',
        help="True if archived within the last 30 days"
    )

    @api.depends('name', 'document_type', 'archive_date', 'partner_id.name')
    def _compute_display_name(self):
        """Compute a meaningful display name for archive entries."""
        for record in self:
            doc_type_label = dict(record._fields['document_type'].selection)[record.document_type]
            date_str = record.archive_date.strftime('%Y-%m-%d %H:%M') if record.archive_date else ''
            record.display_name = f"{doc_type_label} - {record.partner_id.name} ({date_str})"

    @api.depends('document')
    def _compute_file_info(self):
        """Compute file size and other metadata."""
        for record in self:
            if record.document:
                # Calculate approximate file size (base64 encoded size / 1.33)
                import base64
                try:
                    decoded_size = len(base64.b64decode(record.document))
                    record.file_size = decoded_size
                except Exception:
                    record.file_size = 0
            else:
                record.file_size = 0

    @api.depends('archive_date')
    def _compute_is_recent(self):
        """Determine if archive entry is recent (within 30 days)."""
        from datetime import datetime, timedelta
        cutoff_date = datetime.now() - timedelta(days=30)
        
        for record in self:
            record.is_recent = (
                record.archive_date and 
                record.archive_date >= cutoff_date
            )

    def action_view_document(self):
        """
        Action to view/download the archived document.
        
        Returns:
            dict: Action to open document in new tab
        """
        self.ensure_one()
        
        # Log access attempt
        self._log_document_access()
        
        # Generate safe filename
        safe_filename = self._generate_safe_filename()
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content?model={self._name}&field=document&id={self.id}&filename={safe_filename}',
            'target': 'new',
        }

    def action_restore_document(self):
        """
        Action to restore this archived version as the current document.
        
        This replaces the current document with this archived version.
        """
        self.ensure_one()
        
        # Check permissions
        if not self._check_restore_permissions():
            raise AccessError("You don't have permission to restore archived documents.")
        
        # Get document configuration
        from .document_config import DOCUMENT_TYPES
        doc_config = None
        for config in DOCUMENT_TYPES.values():
            if config['key'] == self.document_type:
                doc_config = config
                break
        
        if not doc_config:
            raise ValueError(f"Invalid document type: {self.document_type}")
        
        # Archive current version before restoring
        current_content = getattr(self.partner_id, doc_config['content_field'])
        current_filename = getattr(self.partner_id, doc_config['filename_field'])
        
        if current_content:
            self.create({
                'name': current_filename or f"replaced_{self.document_type}.pdf",
                'document': current_content,
                'document_type': self.document_type,
                'partner_id': self.partner_id.id,
                'archive_reason': 'replacement',
                'original_status': 'replaced_by_restore',
            })
        
        # Restore archived document
        update_vals = {
            doc_config['content_field']: self.document,
            doc_config['filename_field']: self.name,
            doc_config['manual_status_field']: 'to_check',  # Reset to check after restore
        }
        
        # Restore expiry date if available
        if doc_config.get('has_expiry') and self.original_expiry_date:
            update_vals[doc_config['expiry_field']] = self.original_expiry_date
        
        self.partner_id.write(update_vals)
        
        # Log the restore action
        _logger.info(
            "Document restored from archive: %s for partner %s by user %s",
            self.document_type, self.partner_id.name, self.env.user.name
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Document Restored',
                'message': f'Document has been restored successfully. Please review and validate.',
                'type': 'success',
                'sticky': False,
            }
        }

    def _generate_safe_filename(self):
        """Generate a safe filename for download."""
        # Remove special characters and limit length
        import re
        safe_name = re.sub(r'[^\w\-_.]', '_', self.name)
        if len(safe_name) > 100:
            # Keep extension and truncate
            name_part, ext = safe_name.rsplit('.', 1) if '.' in safe_name else (safe_name, '')
            safe_name = name_part[:95] + ('.' + ext if ext else '')
        
        return safe_name

    def _log_document_access(self):
        """Log document access for audit purposes."""
        try:
            self.env['document.archive.access.log'].create({
                'archive_id': self.id,
                'user_id': self.env.user.id,
                'access_type': 'view',
                'access_date': fields.Datetime.now(),
                'ip_address': self._get_client_ip(),
            })
        except Exception as e:
            _logger.warning("Failed to log document access: %s", str(e))

    def _get_client_ip(self):
        """Get client IP address for logging."""
        request = getattr(self.env, 'request', None)
        if request:
            return request.httprequest.environ.get('REMOTE_ADDR', 'Unknown')
        return 'Unknown'

    def _check_restore_permissions(self):
        """Check if current user can restore documents."""
        return self.env.user.has_group('base.group_system') or \
               self.env.user.has_group('blg_contacts_extension.group_directeur_general')

    @api.model
    def cleanup_old_archives(self, days_to_keep=365):
        """
        Clean up old archive entries beyond retention period.
        
        Args:
            days_to_keep (int): Number of days to keep archives
            
        Returns:
            int: Number of records deleted
        """
        from datetime import datetime, timedelta
        
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        old_archives = self.search([
            ('archive_date', '<', cutoff_date),
            ('archive_reason', '!=', 'migration')  # Keep migration archives
        ])
        
        count = len(old_archives)
        if count > 0:
            _logger.info(f"Cleaning up {count} old archive entries older than {days_to_keep} days")
            old_archives.unlink()
        
        return count


class DocumentArchiveAccessLog(models.Model):
    """Log of access attempts to archived documents."""
    
    _name = 'document.archive.access.log'
    _description = 'Document Archive Access Log'
    _order = 'access_date desc'

    archive_id = fields.Many2one(
        'document.archive',
        string='Archive Entry',
        required=True,
        ondelete='cascade'
    )
    
    user_id = fields.Many2one(
        'res.users',
        string='User',
        required=True
    )
    
    access_type = fields.Selection([
        ('view', 'View'),
        ('download', 'Download'),
        ('restore', 'Restore'),
    ], string='Access Type', required=True)
    
    access_date = fields.Datetime(
        string='Access Date',
        required=True
    )
    
    ip_address = fields.Char(
        string='IP Address',
        help="IP address of the client that accessed the document"
    )
    
    # Computed fields for reporting
    partner_id = fields.Many2one(
        related='archive_id.partner_id',
        string='Partner',
        store=True
    )
    
    document_type = fields.Selection(
        related='archive_id.document_type',
        store=True
    )
