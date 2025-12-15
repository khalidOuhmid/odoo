# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    """
    Extended Partner model for construction management
    """
    _inherit = 'res.partner'

    # Construction fields - use names that match existing database structure
    construction_contact = fields.Boolean(
        'Is Construction Contact',
        compute='_compute_construction_fields',
        store=True,
        help="Automatically determined based on contact type or categories"
    )
    
    # For compatibility, add is_construction_contact as an alias
    is_construction_contact = fields.Boolean(
        'Is Construction Contact (Alias)',
        related='construction_contact',
        store=False,
        help="Alias for construction_contact field"
    )
    
    construction_role = fields.Selection([
        ('client', 'Client'),
        ('subcontractor', 'Subcontractor'),
        ('supplier', 'Supplier'),
        ('other', 'Other')
    ], string='Construction Role', 
       compute='_compute_construction_fields', 
       store=True)

    # Relations
    chantier_ids = fields.Many2many(
        'blg.chantier',
        'blg_chantier_subcontractor_rel',
        'partner_id',
        'chantier_id',
        string='Projects',
        readonly=True
    )

    # Counters
    travaux_count = fields.Integer(
        'Number of Projects',
        compute='_compute_travaux_count'
    )

    @api.depends('category_id')
    def _compute_construction_fields(self):
        """Compute construction-related fields from existing data"""
        for partner in self:
            # Check if contact_type field exists (from blg_contacts_extension)
            contact_type = getattr(partner, 'contact_type', False)
            
            if contact_type:
                # Use contact_type from blg_contacts_extension
                partner.construction_contact = contact_type in ['sous_traitant', 'client', 'fournisseur']
                
                # Map contact_type to construction_role
                role_mapping = {
                    'sous_traitant': 'subcontractor',
                    'client': 'client',
                    'fournisseur': 'supplier'
                }
                partner.construction_role = role_mapping.get(contact_type, 'other')
            else:
                # Fallback to using partner categories
                construction_categories = ['Subcontractor', 'Client', 'Supplier', 'Sous-traitant']
                category_names = partner.category_id.mapped('name')
                partner.construction_contact = any(cat in category_names for cat in construction_categories)
                
                # Determine role from categories
                if any(cat in ['Subcontractor', 'Sous-traitant'] for cat in category_names):
                    partner.construction_role = 'subcontractor'
                elif 'Client' in category_names:
                    partner.construction_role = 'client'
                elif any(cat in ['Supplier', 'Fournisseur'] for cat in category_names):
                    partner.construction_role = 'supplier'
                else:
                    partner.construction_role = 'other'

    @api.depends('chantier_ids')
    def _compute_travaux_count(self):
        """Compute the number of projects for this partner"""
        for partner in self:
            partner.travaux_count = len(partner.chantier_ids)

    @api.model
    def _auto_init(self):
        """Initialize construction fields for existing partners"""
        result = super()._auto_init()
        
        # Only run this during module installation/upgrade
        if self.env.context.get('module_install_from_update_list'):
            try:
                self._init_construction_fields()
            except Exception as e:
                _logger.warning(f"Could not initialize construction fields during _auto_init: {e}")
            
        return result

    def _init_construction_fields(self):
        """Initialize construction fields for existing partners"""
        try:
            # Check if contact_type field exists
            if hasattr(self, 'contact_type'):
                # Update partners that have contact_type field
                construction_partners = self.search([
                    ('contact_type', 'in', ['sous_traitant', 'client', 'fournisseur'])
                ])
                if construction_partners:
                    _logger.info(f"Initializing construction fields for {len(construction_partners)} partners with contact_type")
                    construction_partners._compute_construction_fields()
            
            # Also check for partners with construction-related categories
            construction_categories = self.env['res.partner.category'].search([
                ('name', 'in', ['Subcontractor', 'Client', 'Supplier', 'Sous-traitant'])
            ])
            
            if construction_categories:
                category_partners = self.search([
                    ('category_id', 'in', construction_categories.ids)
                ])
                if category_partners:
                    _logger.info(f"Initializing construction fields for {len(category_partners)} partners with categories")
                    category_partners._compute_construction_fields()
                    
        except Exception as e:
            _logger.warning(f"Could not initialize construction fields: {e}")