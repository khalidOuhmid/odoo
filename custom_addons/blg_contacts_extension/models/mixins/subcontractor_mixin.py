# -*- coding: utf-8 -*-
"""
Subcontractor Mixin

This mixin provides subcontractor-specific functionality including
integration with construction projects, lot management, and specialized
business logic for subcontractor workflow.
"""

from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class SubcontractorMixin(models.AbstractModel):
    """
    Abstract mixin providing subcontractor-specific functionality.
    
    This mixin handles subcontractor concerns including:
    - Contact type management  
    - Lot (trade specialization) relationships
    - Integration with construction projects
    - Subcontractor-specific business rules
    """
    _name = 'subcontractor.mixin'
    _description = 'Subcontractor Mixin'

    # Contact type field with proper selection options
    contact_type = fields.Selection([
        ('customer', 'Customer'),
        ('supplier', 'Supplier'),
        ('sous_traitant', 'Subcontractor'),
        ('employee', 'Employee'),
        ('other', 'Other')
    ], string="Contact Type", default='other', help="Type of contact relationship")

    # Integration with construction lots (using standardized lot model)
    lot_ids = fields.Many2many(
        'lot',  # Standardized lot model from construction_lots
        'partner_lot_rel',
        'partner_id',
        'lot_id',
        string="Trade Specializations",
        help="Construction trades/lots this subcontractor specializes in"
    )

    # Computed fields for better UX
    is_subcontractor = fields.Boolean(
        string='Is Subcontractor',
        compute='_compute_is_subcontractor',
        store=True,
        help="True if contact type is subcontractor"
    )

    lot_names = fields.Char(
        string='Specializations',
        compute='_compute_lot_names',
        store=False,
        help="Comma-separated list of trade specializations"
    )

    # Performance optimization: count related records
    chantier_count = fields.Integer(
        string='Active Projects Count',
        compute='_compute_related_counts',
        store=False,
        help="Number of active construction projects"
    )

    @api.depends('contact_type')
    def _compute_is_subcontractor(self):
        """Compute if partner is a subcontractor for easy filtering."""
        for record in self:
            record.is_subcontractor = record.contact_type == 'sous_traitant'

    @api.depends('lot_ids.name')
    def _compute_lot_names(self):
        """Compute comma-separated lot names for display purposes."""
        for record in self:
            if record.lot_ids:
                record.lot_names = ', '.join(record.lot_ids.mapped('name'))
            else:
                record.lot_names = ''

    def _compute_related_counts(self):
        """Compute counts of related construction records for performance."""
        for record in self:
            if record.is_subcontractor and hasattr(self.env, 'construction.chantier'):
                # Count active chantiers where this subcontractor is involved
                try:
                    chantier_count = self.env['construction.chantier'].search_count([
                        ('subcontractors', 'in', record.id),
                        ('state', '=', 'active')
                    ])
                    record.chantier_count = chantier_count
                except Exception:
                    # If construction module not available, set to 0
                    record.chantier_count = 0
            else:
                record.chantier_count = 0

    @api.constrains('lot_ids', 'contact_type')
    def _check_lot_assignment_rules(self):
        """Validate lot assignment business rules."""
        for record in self:
            if record.lot_ids and record.contact_type != 'sous_traitant':
                raise ValidationError(
                    "Trade specializations (lots) can only be assigned to subcontractor contacts. "
                    "Please change the contact type to 'Subcontractor' or remove the lot assignments."
                )

    @api.onchange('contact_type')
    def _onchange_contact_type(self):
        """Clear lots when contact type changes from subcontractor."""
        if self.contact_type != 'sous_traitant' and self.lot_ids:
            self.lot_ids = [(5, 0, 0)]  # Clear all lot assignments

    def action_view_related_chantiers(self):
        """Open view of construction projects involving this subcontractor."""
        self.ensure_one()
        
        if not self.is_subcontractor:
            return False

        try:
            chantiers = self.env['construction.chantier'].search([
                ('subcontractors', 'in', self.id)
            ])
            
            return {
                'type': 'ir.actions.act_window',
                'name': f'Projects - {self.name}',
                'res_model': 'construction.chantier',
                'view_mode': 'kanban,list,form',
                'domain': [('id', 'in', chantiers.ids)],
                'context': {
                    'default_subcontractors': [(6, 0, [self.id])],
                    'search_default_subcontractor_filter': 1,
                },
                'target': 'current',
            }
        except Exception as e:
            _logger.warning(
                "Could not open chantiers view for subcontractor %s: %s",
                self.id, str(e)
            )
            return False

    @api.model
    def get_subcontractors_by_lot(self, lot_id=None):
        """
        Get subcontractors filtered by lot specialization.
        
        Args:
            lot_id (int, optional): Specific lot ID to filter by
            
        Returns:
            recordset: Subcontractor partners matching criteria
        """
        domain = [('contact_type', '=', 'sous_traitant')]
        
        if lot_id:
            domain.append(('lot_ids', 'in', lot_id))
            
        return self.search(domain)

    @api.model
    def get_subcontractors_by_document_status(self, status=None):
        """
        Get subcontractors filtered by document status.
        
        Args:
            status (str, optional): Document status to filter by
                ('expired', 'expiring', 'valid', 'missing', 'rejected')
                
        Returns:
            recordset: Subcontractor partners matching criteria
        """
        domain = [('contact_type', '=', 'sous_traitant')]
        
        if status == 'expired':
            domain.append(('has_expired_documents', '=', True))
        elif status == 'expiring':
            domain.append(('has_expiring_documents', '=', True))
        elif status == 'valid':
            domain.extend([
                ('has_expired_documents', '=', False),
                ('has_expiring_documents', '=', False)
            ])
        
        return self.search(domain)

    @api.model
    def get_available_subcontractors_for_chantier(self, chantier_id):
        """
        Get subcontractors available for a specific construction project.
        
        Args:
            chantier_id (int): Construction project ID
            
        Returns:
            recordset: Available subcontractor partners
        """
        try:
            chantier = self.env['construction.chantier'].browse(chantier_id)
            if not chantier.exists():
                return self.env['res.partner']
            
            # Get subcontractors specialized in project's lots
            available_subcontractors = self.env['res.partner']
            
            for lot in chantier.lots_ids:
                lot_subcontractors = self.get_subcontractors_by_lot(lot.id)
                available_subcontractors |= lot_subcontractors
            
            # Exclude already assigned subcontractors
            available_subcontractors -= chantier.subcontractors
            
            return available_subcontractors
            
        except Exception as e:
            _logger.error(
                "Error getting available subcontractors for chantier %s: %s",
                chantier_id, str(e)
            )
            return self.env['res.partner']

    def action_assign_to_chantier(self):
        """Open wizard to assign subcontractor to construction projects."""
        self.ensure_one()
        
        if not self.is_subcontractor:
            return False

        try:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Assign to Project',
                'res_model': 'construction.chantier.assign.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_subcontractor_id': self.id,
                    'default_lot_ids': [(6, 0, self.lot_ids.ids)],
                },
            }
        except Exception:
            # If wizard doesn't exist, return simple message
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Information',
                    'message': 'Project assignment wizard is not available.',
                    'type': 'info'
                }
            }

    def get_document_compliance_status(self):
        """
        Get overall document compliance status for subcontractor.
        
        Returns:
            dict: Compliance status information
        """
        self.ensure_one()
        
        if not self.is_subcontractor:
            return {'status': 'not_applicable', 'message': 'Not a subcontractor'}

        if self.has_expired_documents:
            return {
                'status': 'non_compliant',
                'message': 'Has expired documents',
                'priority': 'high'
            }
        
        if self.has_expiring_documents:
            return {
                'status': 'warning',
                'message': 'Has documents expiring soon',
                'priority': 'medium'
            }
        
        # Check for missing documents
        from ..document_config import DOCUMENT_TYPES
        missing_docs = []
        
        for doc_type, config in DOCUMENT_TYPES.items():
            content = getattr(self, config['content_field'])
            if not content:
                missing_docs.append(config['display_name'])
        
        if missing_docs:
            return {
                'status': 'incomplete',
                'message': f"Missing documents: {', '.join(missing_docs)}",
                'priority': 'medium'
            }
        
        return {
            'status': 'compliant',
            'message': 'All documents are valid and up to date',
            'priority': 'low'
        } 