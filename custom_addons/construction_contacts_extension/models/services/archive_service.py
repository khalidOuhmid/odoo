# -*- coding: utf-8 -*-
"""
Archive Service

This service handles document archiving operations including version management,
cleanup, and restoration of archived documents.
"""

from odoo import models, api
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


class ArchiveService(models.AbstractModel):
    """
    Service for managing document archives and version history.
    
    This service provides centralized functionality for:
    - Creating document archives when documents are replaced
    - Managing archive cleanup and retention policies
    - Handling document restoration from archives
    - Maintaining audit trails for document changes
    """
    _name = 'archive.service'
    _description = 'Document Archive Management Service'

    @api.model
    def archive_document_version(self, partner_id, doc_type, content, filename, action_type, **kwargs):
        """
        Archive a document version with proper metadata.
        
        Args:
            partner_id (int): Partner ID
            doc_type (str): Document type key
            content (binary): Document binary content
            filename (str): Original filename
            action_type (str): Type of action that triggered archiving
            **kwargs: Additional metadata
            
        Returns:
            recordset: Created archive record
        """
        try:
            partner = self.env['res.partner'].browse(partner_id)
            if not partner.exists():
                _logger.error("Cannot archive document: Partner %s not found", partner_id)
                return self.env['document.archive']

            # Get current document status and expiry if available
            from ..document_config import DOCUMENT_TYPES
            doc_config = DOCUMENT_TYPES.get(doc_type)
            
            if not doc_config:
                _logger.error("Cannot archive document: Invalid document type %s", doc_type)
                return self.env['document.archive']

            # Collect document metadata
            archive_data = {
                'name': filename or f'{doc_type}_{partner.name}.pdf',
                'document': content,
                'document_type': doc_type,
                'partner_id': partner_id,
                'archive_reason': self._map_action_to_reason(action_type),
                'original_status': kwargs.get('original_status'),
            }

            # Add expiry date if document type supports it
            if doc_config.get('has_expiry'):
                expiry_field = doc_config['expiry_field']
                expiry_date = getattr(partner, expiry_field, None)
                if expiry_date:
                    archive_data['original_expiry_date'] = expiry_date

            # Create archive record
            archive = self.env['document.archive'].create(archive_data)
            
            _logger.info(
                "Document archived: %s for partner %s (ID: %s), reason: %s",
                doc_type, partner.name, partner_id, action_type
            )
            
            return archive

        except Exception as e:
            _logger.error(
                "Failed to archive document %s for partner %s: %s",
                doc_type, partner_id, str(e), exc_info=True
            )
            return self.env['document.archive']

    @api.model
    def cleanup_old_archives(self, retention_days=365, batch_size=100):
        """
        Clean up old archive records beyond retention period.
        
        Args:
            retention_days (int): Number of days to retain archives
            batch_size (int): Number of records to process in each batch
            
        Returns:
            dict: Cleanup statistics
        """
        from datetime import timedelta
        
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        
        # Find archives to clean up (excluding migration archives)
        domain = [
            ('archive_date', '<', cutoff_date),
            ('archive_reason', '!=', 'migration')
        ]
        
        total_count = self.env['document.archive'].search_count(domain)
        
        if total_count == 0:
            return {
                'total_found': 0,
                'total_deleted': 0,
                'batches_processed': 0,
                'status': 'success'
            }

        _logger.info(
            "Starting archive cleanup: %s records older than %s days",
            total_count, retention_days
        )

        deleted_count = 0
        batches_processed = 0
        
        try:
            # Process in batches to avoid memory issues
            while True:
                batch = self.env['document.archive'].search(domain, limit=batch_size)
                if not batch:
                    break
                
                batch_size_actual = len(batch)
                batch.unlink()
                deleted_count += batch_size_actual
                batches_processed += 1
                
                # Commit after each batch
                self.env.cr.commit()
                
                _logger.info(
                    "Archive cleanup batch %s completed: %s records deleted",
                    batches_processed, batch_size_actual
                )
                
                # Break if we deleted fewer records than batch size (last batch)
                if batch_size_actual < batch_size:
                    break

            return {
                'total_found': total_count,
                'total_deleted': deleted_count,
                'batches_processed': batches_processed,
                'status': 'success'
            }

        except Exception as e:
            _logger.error("Archive cleanup failed: %s", str(e), exc_info=True)
            return {
                'total_found': total_count,
                'total_deleted': deleted_count,
                'batches_processed': batches_processed,
                'status': 'error',
                'error_message': str(e)
            }

    @api.model
    def get_archive_statistics(self, partner_id=None, days=30):
        """
        Get archive statistics for reporting.
        
        Args:
            partner_id (int, optional): Specific partner ID to analyze
            days (int): Number of days to analyze
            
        Returns:
            dict: Archive statistics
        """
        from datetime import timedelta
        
        cutoff_date = datetime.now() - timedelta(days=days)
        domain = [('archive_date', '>=', cutoff_date)]
        
        if partner_id:
            domain.append(('partner_id', '=', partner_id))

        archives = self.env['document.archive'].search(domain)
        
        # Group by document type
        stats_by_type = {}
        stats_by_reason = {}
        
        for archive in archives:
            # Count by document type
            doc_type = archive.document_type
            if doc_type not in stats_by_type:
                stats_by_type[doc_type] = 0
            stats_by_type[doc_type] += 1
            
            # Count by archive reason
            reason = archive.archive_reason
            if reason not in stats_by_reason:
                stats_by_reason[reason] = 0
            stats_by_reason[reason] += 1

        return {
            'period_days': days,
            'total_archives': len(archives),
            'by_document_type': stats_by_type,
            'by_archive_reason': stats_by_reason,
            'partner_id': partner_id,
        }

    @api.model
    def find_duplicate_archives(self):
        """
        Find potential duplicate archive entries.
        
        Returns:
            list: List of potential duplicate groups
        """
        # Find archives with same partner, document type, and similar dates
        duplicates = []
        
        archives = self.env['document.archive'].search([])
        processed = set()
        
        for archive in archives:
            if archive.id in processed:
                continue
                
            # Find similar archives
            similar_domain = [
                ('partner_id', '=', archive.partner_id.id),
                ('document_type', '=', archive.document_type),
                ('id', '!=', archive.id),
            ]
            
            # Look for archives within 1 hour of each other
            if archive.archive_date:
                from datetime import timedelta
                start_time = archive.archive_date - timedelta(hours=1)
                end_time = archive.archive_date + timedelta(hours=1)
                similar_domain.extend([
                    ('archive_date', '>=', start_time),
                    ('archive_date', '<=', end_time),
                ])
            
            similar_archives = self.env['document.archive'].search(similar_domain)
            
            if similar_archives:
                duplicate_group = [archive] + similar_archives
                duplicates.append(duplicate_group)
                
                # Mark all as processed
                for dup in duplicate_group:
                    processed.add(dup.id)

        return duplicates

    @api.model
    def export_archive_report(self, partner_ids=None, document_types=None, date_from=None, date_to=None):
        """
        Export archive report data for external analysis.
        
        Args:
            partner_ids (list, optional): Partner IDs to include
            document_types (list, optional): Document types to include
            date_from (date, optional): Start date filter
            date_to (date, optional): End date filter
            
        Returns:
            list: List of archive data dictionaries
        """
        domain = []
        
        if partner_ids:
            domain.append(('partner_id', 'in', partner_ids))
        if document_types:
            domain.append(('document_type', 'in', document_types))
        if date_from:
            domain.append(('archive_date', '>=', date_from))
        if date_to:
            domain.append(('archive_date', '<=', date_to))

        archives = self.env['document.archive'].search(domain, order='archive_date desc')
        
        report_data = []
        for archive in archives:
            report_data.append({
                'archive_id': archive.id,
                'partner_name': archive.partner_id.name,
                'partner_id': archive.partner_id.id,
                'document_type': archive.document_type,
                'document_type_label': dict(archive._fields['document_type'].selection)[archive.document_type],
                'archive_date': archive.archive_date.isoformat() if archive.archive_date else None,
                'archive_reason': archive.archive_reason,
                'archived_by': archive.archived_by.name,
                'file_size': archive.file_size,
                'original_filename': archive.name,
                'original_expiry_date': archive.original_expiry_date.isoformat() if archive.original_expiry_date else None,
                'original_status': archive.original_status,
            })
        
        return report_data

    def _map_action_to_reason(self, action_type):
        """
        Map action type to archive reason.
        
        Args:
            action_type (str): Action that triggered archiving
            
        Returns:
            str: Archive reason
        """
        mapping = {
            'replacement': 'replacement',
            'validation': 'validation',
            'rejection': 'rejection',
            'upload': 'replacement',
            'manual': 'manual',
            'migration': 'migration',
        }
        
        return mapping.get(action_type, 'replacement') 