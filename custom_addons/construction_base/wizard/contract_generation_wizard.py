# -*- coding: utf-8 -*-
"""
Contract Generation Wizard

Clean and modular wizard for generating construction contracts.
Supports single lot and multi-lot contracts with proper validation.
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class ContractGenerationWizard(models.TransientModel):
    """
    Wizard for generating construction contracts.
    
    This wizard provides a clean interface for:
    - Contract configuration
    - Multi-lot support
    - Preview generation
    - Contract creation
    """
    _name = 'construction.contract.generation.wizard'
    _description = 'Contract Generation Wizard'

    # Wizard state
    current_step = fields.Selection([
        ('config', 'Configuration'),
        ('preview', 'Preview'),
        ('finalize', 'Finalization'),
    ], default='config', string='Step')

    # Basic configuration
    chantier_id = fields.Many2one('construction.chantier', 'Construction Site', required=True)
    subcontractor_id = fields.Many2one('res.partner', 'Subcontractor', required=True)
    lot_ids = fields.Many2many('construction.lot', 'Lots', required=True,
                               domain="[('chantier_id', '=', chantier_id)]")

    # Contract terms
    start_date = fields.Date('Start Date', required=True, default=fields.Date.today)
    end_date = fields.Date('End Date')
    total_amount = fields.Monetary('Total Amount', currency_field='currency_id', required=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    
    payment_terms = fields.Selection([
        ('30_days', '30 days'),
        ('45_days', '45 days'),
        ('60_days', '60 days'),
        ('end_of_work', 'End of work'),
    ], default='30_days', string='Payment Terms')
    
    warranty_period = fields.Integer('Warranty Period (months)', default=12)
    insurance_required = fields.Boolean('Insurance Required', default=True)
    notes = fields.Text('Additional Notes')
    
    # URSSAF code
    urssaf_code = fields.Selection([
        ('41.20Z', '41.20Z - Construction of residential and non-residential buildings'),
        ('42.11Z', '42.11Z - Construction of roads and highways'),
        ('43.11Z', '43.11Z - Demolition work'),
        ('43.12A', '43.12A - Common earthworks and preparatory work'),
        ('43.21A', '43.21A - Electrical installation work in all premises'),
        ('43.21B', '43.21B - Electrical installation work on public roads'),
        ('43.22A', '43.22A - Water and gas installation work in all premises'),
        ('43.22B', '43.22B - Thermal and air conditioning equipment installation work'),
        ('43.29A', '43.29A - Insulation work'),
        ('43.31Z', '43.31Z - Plastering work'),
        ('43.32A', '43.32A - Wood and PVC joinery work'),
        ('43.32B', '43.32B - Metal joinery and locksmith work'),
        ('43.33Z', '43.33Z - Floor and wall covering work'),
        ('43.34Z', '43.34Z - Painting and glazing work'),
        ('43.91A', '43.91A - Carpentry work'),
        ('43.91B', '43.91B - Roofing work by elements'),
        ('43.99A', '43.99A - Waterproofing work'),
        ('43.99B', '43.99B - Metal structure assembly work'),
        ('43.99C', '43.99C - General masonry and building construction work'),
        ('43.99D', '43.99D - Other specialized construction work'),
        ('81.22Z', '81.22Z - Other building cleaning and industrial cleaning activities'),
        ('81.30Z', '81.30Z - Landscaping services'),
    ], string='URSSAF Code', default='43.34Z', help="URSSAF code corresponding to the type of work")

    # Preview and options
    preview_html = fields.Html('Preview HTML', readonly=True)
    preview_ready = fields.Boolean('Preview Generated', default=False)
    
    send_email = fields.Boolean('Send by Email', default=True)
    auto_send = fields.Boolean('Auto Send After Signature', default=False)

    # Generated contract
    generated_contract_id = fields.Many2one('construction.subcontractor.contract', 'Generated Contract', readonly=True)
    generated_contract_number = fields.Char(related='generated_contract_id.contract_number', string="Contract Number")
    generated_contract_state = fields.Selection(related='generated_contract_id.state', string="Contract State")

    # Computed fields
    lot_count = fields.Integer('Lot Count', compute='_compute_lot_info', store=True)
    is_multi_lot = fields.Boolean('Multi-Lot Contract', compute='_compute_lot_info', store=True)
    lot_names = fields.Char('Lot Names', compute='_compute_lot_info', store=True)

    @api.depends('lot_ids')
    def _compute_lot_info(self):
        """Compute lot information."""
        for wizard in self:
            wizard.lot_count = len(wizard.lot_ids)
            wizard.is_multi_lot = len(wizard.lot_ids) > 1
            wizard.lot_names = ', '.join(wizard.lot_ids.mapped('name')) if wizard.lot_ids else ''

    @api.onchange('lot_ids')
    def _onchange_lot_ids(self):
        """Update total amount when lots change."""
        if self.lot_ids:
            self.total_amount = sum(self.lot_ids.mapped('price'))

    @api.onchange('chantier_id')
    def _onchange_chantier_id(self):
        """Update lots when chantier changes."""
        if self.chantier_id:
            self.lot_ids = [(6, 0, [])]
            self.subcontractor_id = False

    def action_generate_preview(self):
        """Generate contract preview."""
        try:
            # Validate configuration
            self._validate_configuration()
            
            # Prepare contract data
            contract_data = self._prepare_contract_data()
            
            # Generate preview
            document_generator = self.env['construction.document.generator']
            preview_html = document_generator.generate_preview_html(contract_data)
            
            # Update wizard
            self.write({
                'current_step': 'preview',
                'preview_html': preview_html,
                'preview_ready': True,
            })
            
            return self._reload_wizard()
            
        except Exception as e:
            _logger.error(f"Error generating preview: {e}")
            raise ValidationError(_("Error generating preview: %s") % str(e))

    def action_generate_contract(self):
        """Generate final contract."""
        if not self.preview_ready:
            raise ValidationError(_("Please generate preview first."))
        
        try:
            # Validate configuration
            self._validate_configuration()
            
            # Prepare contract data
            contract_data = self._prepare_contract_data()
            
            # Create contract using builder
            contract_builder = self.env['construction.contract.builder'](self.env)
            contract = (contract_builder
                       .set_basic_info(self.chantier_id.id, self.subcontractor_id.id)
                       .add_lots(self.lot_ids.ids)
                       .set_dates(self.start_date, self.end_date)
                       .set_financial_terms(self.total_amount, self.payment_terms, self.currency_id.id)
                       .set_legal_terms(self.warranty_period, self.insurance_required, self.urssaf_code)
                       .set_additional_info(self.notes)
                       .build())
            
            # Update wizard
            self.write({
                'current_step': 'finalize',
                'generated_contract_id': contract.id,
            })
            
            # Send email if requested
            if self.send_email:
                contract.action_send_contract()
            
            _logger.info(f"Contract generated successfully: {contract.contract_number}")
            
            return {
                'type': 'ir.actions.act_window',
                'name': f'Contract - {self.subcontractor_id.name}',
                'res_model': 'construction.subcontractor.contract',
                'res_id': contract.id,
                'view_mode': 'form',
                'target': 'current',
            }
            
        except Exception as e:
            _logger.error(f"Error generating contract: {e}")
            raise ValidationError(_("Error generating contract: %s") % str(e))

    def action_back_to_config(self):
        """Return to configuration step."""
        self.write({
            'current_step': 'config',
            'preview_ready': False,
            'preview_html': '',
        })
        return self._reload_wizard()

    def action_modify_and_regenerate(self):
        """Modify configuration and regenerate preview."""
        self.write({
            'current_step': 'config',
            'preview_ready': False,
            'preview_html': '',
        })
        return self._reload_wizard()

    def _validate_configuration(self):
        """Validate wizard configuration."""
        validator = self.env['construction.contract.validator']
        
        contract_data = self._prepare_contract_data()
        validator.validate_contract_data(contract_data)
        
        # Validate multi-lot specific rules
        if self.is_multi_lot:
            multi_lot_handler = self.env['construction.multi.lot.handler']
            multi_lot_handler.validate_multi_lot_structure(contract_data)

    def _prepare_contract_data(self):
        """Prepare contract data for creation."""
        return {
            'chantier_id': self.chantier_id.id,
            'subcontractor_id': self.subcontractor_id.id,
            'lot_ids': self.lot_ids.ids,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'total_amount': self.total_amount,
            'payment_terms': self.payment_terms,
            'warranty_period': self.warranty_period,
            'insurance_required': self.insurance_required,
            'notes': self.notes,
            'urssaf_code': self.urssaf_code,
            'currency_id': self.currency_id.id,
        }

    def _reload_wizard(self):
        """Reload wizard view."""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Contract Generation Wizard',
            'res_model': 'construction.contract.generation.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    @api.model
    def default_get(self, fields_list):
        """Set default values."""
        res = super().default_get(fields_list)
        
        # Set context defaults
        if 'default_chantier_id' in self.env.context:
            res['chantier_id'] = self.env.context['default_chantier_id']
        
        if 'default_subcontractor_id' in self.env.context:
            res['subcontractor_id'] = self.env.context['default_subcontractor_id']
        
        if 'default_lot_ids' in self.env.context:
            res['lot_ids'] = self.env.context['default_lot_ids']
        
        if 'default_total_amount' in self.env.context:
            res['total_amount'] = self.env.context['default_total_amount']
        
        return res