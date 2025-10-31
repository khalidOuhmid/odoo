# -*- coding: utf-8 -*-
"""
Contract Orchestrator

Main orchestrator service that coordinates all contract-related operations.
Provides a single entry point for contract generation and management.
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class ContractOrchestrator(models.AbstractModel):
    """
    Main orchestrator for contract operations.
    
    This service coordinates:
    - Contract creation
    - Multi-lot handling
    - Document generation
    - Validation
    - Preview generation
    """
    _name = 'construction.contract.orchestrator'
    _description = 'Contract Orchestrator'

    def generate_contract(self, contract_data):
        """
        Generate a complete contract.
        
        Args:
            contract_data (dict): Contract configuration data
            
        Returns:
            construction.subcontractor.contract: Generated contract
        """
        try:
            # Validate contract data
            validator = self.env['construction.contract.validator']
            validator.validate_contract_data(contract_data)
            
            # Handle multi-lot validation
            if len(contract_data.get('lot_ids', [])) > 1:
                multi_lot_handler = self.env['construction.multi.lot.handler']
                multi_lot_handler.validate_multi_lot_structure(contract_data)
            
            # Create contract using builder
            contract_builder = self.env['construction.contract.builder'](self.env)
            contract = (contract_builder
                       .set_basic_info(
                           contract_data['chantier_id'],
                           contract_data['subcontractor_id'],
                           contract_data.get('name')
                       )
                       .add_lots(contract_data['lot_ids'])
                       .set_dates(
                           contract_data['start_date'],
                           contract_data.get('end_date')
                       )
                       .set_financial_terms(
                           contract_data['total_amount'],
                           contract_data.get('payment_terms', '30_days'),
                           contract_data.get('currency_id')
                       )
                       .set_legal_terms(
                           contract_data.get('warranty_period', 12),
                           contract_data.get('insurance_required', True),
                           contract_data.get('urssaf_code', '43.34Z')
                       )
                       .set_additional_info(contract_data.get('notes', ''))
                       .build())
            
            _logger.info(f"Contract generated successfully: {contract.contract_number}")
            return contract
            
        except Exception as e:
            _logger.error(f"Error generating contract: {e}")
            raise ValidationError(_("Error generating contract: %s") % str(e))

    def generate_preview(self, contract_data):
        """
        Generate contract preview.
        
        Args:
            contract_data (dict): Contract configuration data
            
        Returns:
            str: HTML preview content
        """
        try:
            # Validate contract data
            validator = self.env['construction.contract.validator']
            validator.validate_contract_data(contract_data)
            
            # Generate preview
            document_generator = self.env['construction.document.generator']
            preview_html = document_generator.generate_preview_html(contract_data)
            
            return preview_html
            
        except Exception as e:
            _logger.error(f"Error generating preview: {e}")
            raise ValidationError(_("Error generating preview: %s") % str(e))

    def validate_contract_configuration(self, contract_data):
        """
        Validate contract configuration.
        
        Args:
            contract_data (dict): Contract configuration data
            
        Returns:
            bool: True if valid
            
        Raises:
            ValidationError: If validation fails
        """
        validator = self.env['construction.contract.validator']
        validator.validate_contract_data(contract_data)
        
        # Validate multi-lot specific rules
        if len(contract_data.get('lot_ids', [])) > 1:
            multi_lot_handler = self.env['construction.multi.lot.handler']
            multi_lot_handler.validate_multi_lot_structure(contract_data)
        
        return True

    def get_multi_lot_info(self, lot_ids, subcontractor_id):
        """
        Get multi-lot contract information.
        
        Args:
            lot_ids (list): List of lot IDs
            subcontractor_id (int): Subcontractor ID
            
        Returns:
            dict: Multi-lot information
        """
        multi_lot_handler = self.env['construction.multi.lot.handler']
        return multi_lot_handler.get_grouped_lots_info(lot_ids, subcontractor_id)

    def can_group_lots(self, lot_ids, subcontractor_id):
        """
        Check if lots can be grouped in a single contract.
        
        Args:
            lot_ids (list): List of lot IDs
            subcontractor_id (int): Subcontractor ID
            
        Returns:
            bool: True if lots can be grouped
        """
        multi_lot_handler = self.env['construction.multi.lot.handler']
        return multi_lot_handler.can_group_lots(lot_ids, subcontractor_id)

    def get_contract_preview_data(self, contract_data):
        """
        Get preview data for contract.
        
        Args:
            contract_data (dict): Contract configuration data
            
        Returns:
            dict: Preview data
        """
        lot_ids = contract_data.get('lot_ids', [])
        subcontractor_id = contract_data.get('subcontractor_id')
        
        if len(lot_ids) > 1 and subcontractor_id:
            multi_lot_handler = self.env['construction.multi.lot.handler']
            return multi_lot_handler.get_multi_lot_contract_preview_data(contract_data)
        
        return {}

    def create_contract_from_wizard(self, wizard_data):
        """
        Create contract from wizard data.
        
        Args:
            wizard_data (dict): Wizard configuration data
            
        Returns:
            construction.subcontractor.contract: Created contract
        """
        contract_data = {
            'chantier_id': wizard_data['chantier_id'],
            'subcontractor_id': wizard_data['subcontractor_id'],
            'lot_ids': wizard_data['lot_ids'],
            'start_date': wizard_data['start_date'],
            'end_date': wizard_data.get('end_date'),
            'total_amount': wizard_data['total_amount'],
            'payment_terms': wizard_data.get('payment_terms', '30_days'),
            'warranty_period': wizard_data.get('warranty_period', 12),
            'insurance_required': wizard_data.get('insurance_required', True),
            'notes': wizard_data.get('notes', ''),
            'urssaf_code': wizard_data.get('urssaf_code', '43.34Z'),
            'currency_id': wizard_data.get('currency_id'),
        }
        
        return self.generate_contract(contract_data)

    def generate_contract_documents(self, contract):
        """
        Generate documents for an existing contract.
        
        Args:
            contract: construction.subcontractor.contract record
            
        Returns:
            bool: True if successful
        """
        try:
            document_generator = self.env['construction.document.generator']
            pdf_content = document_generator.generate_contract_pdf(contract)
            
            # Update contract with generated PDF
            contract.write({
                'contract_pdf': pdf_content,
                'filename': self._generate_filename(contract),
            })
            
            return True
            
        except Exception as e:
            _logger.error(f"Error generating contract documents: {e}")
            raise ValidationError(_("Error generating contract documents: %s") % str(e))

    def _generate_filename(self, contract):
        """Generate filename for contract."""
        from datetime import datetime
        lot_names = "_".join([lot.name.replace(" ", "_") for lot in contract.lot_ids])
        return f"Contract_{contract.subcontractor_id.name}_{lot_names}_{datetime.now().strftime('%Y%m%d')}.pdf"
