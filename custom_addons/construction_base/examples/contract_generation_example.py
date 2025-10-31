# -*- coding: utf-8 -*-
"""
Contract Generation Examples

Examples showing how to use the new contract generation architecture.
These examples demonstrate the clean, modular approach to contract generation.
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class ContractGenerationExamples(models.AbstractModel):
    """
    Examples of contract generation using the new architecture.
    
    This class provides practical examples of how to use the contract
    generation system in different scenarios.
    """
    _name = 'construction.contract.examples'
    _description = 'Contract Generation Examples'

    def example_basic_contract_generation(self):
        """
        Example: Basic contract generation for a single lot.
        
        This example shows how to generate a simple contract using
        the orchestrator service.
        """
        try:
            # Get required data
            chantier = self.env['construction.chantier'].search([], limit=1)
            subcontractor = self.env['res.partner'].search([('is_company', '=', True)], limit=1)
            lot = self.env['construction.lot'].search([], limit=1)
            
            if not all([chantier, subcontractor, lot]):
                raise ValidationError(_("Required data not found for example"))
            
            # Prepare contract data
            contract_data = {
                'chantier_id': chantier.id,
                'subcontractor_id': subcontractor.id,
                'lot_ids': [lot.id],
                'start_date': fields.Date.today(),
                'end_date': fields.Date.today() + fields.timedelta(days=30),
                'total_amount': 50000.0,
                'payment_terms': '30_days',
                'warranty_period': 12,
                'insurance_required': True,
                'notes': 'Basic contract example',
                'urssaf_code': '43.34Z',
            }
            
            # Generate contract using orchestrator
            orchestrator = self.env['construction.contract.orchestrator']
            contract = orchestrator.generate_contract(contract_data)
            
            _logger.info(f"Basic contract generated: {contract.contract_number}")
            return contract
            
        except Exception as e:
            _logger.error(f"Error in basic contract generation example: {e}")
            raise ValidationError(_("Error in basic contract generation example: %s") % str(e))

    def example_multi_lot_contract_generation(self):
        """
        Example: Multi-lot contract generation.
        
        This example shows how to generate a contract for multiple lots
        with the same subcontractor.
        """
        try:
            # Get required data
            chantier = self.env['construction.chantier'].search([], limit=1)
            subcontractor = self.env['res.partner'].search([('is_company', '=', True)], limit=1)
            lots = self.env['construction.lot'].search([], limit=3)
            
            if not all([chantier, subcontractor, lots]):
                raise ValidationError(_("Required data not found for example"))
            
            # Check if lots can be grouped
            multi_lot_handler = self.env['construction.multi.lot.handler']
            can_group = multi_lot_handler.can_group_lots(lots.ids, subcontractor.id)
            
            if not can_group:
                raise ValidationError(_("Lots cannot be grouped in a single contract"))
            
            # Get grouped lots information
            grouped_info = multi_lot_handler.get_grouped_lots_info(lots.ids, subcontractor.id)
            
            # Prepare contract data
            contract_data = {
                'chantier_id': chantier.id,
                'subcontractor_id': subcontractor.id,
                'lot_ids': lots.ids,
                'start_date': fields.Date.today(),
                'end_date': fields.Date.today() + fields.timedelta(days=60),
                'total_amount': grouped_info['total_amount'],
                'payment_terms': '45_days',
                'warranty_period': 18,
                'insurance_required': True,
                'notes': f'Multi-lot contract for {grouped_info["lot_count"]} lots',
                'urssaf_code': '43.34Z',
            }
            
            # Generate contract using orchestrator
            orchestrator = self.env['construction.contract.orchestrator']
            contract = orchestrator.generate_contract(contract_data)
            
            _logger.info(f"Multi-lot contract generated: {contract.contract_number}")
            return contract
            
        except Exception as e:
            _logger.error(f"Error in multi-lot contract generation example: {e}")
            raise ValidationError(_("Error in multi-lot contract generation example: %s") % str(e))

    def example_contract_preview_generation(self):
        """
        Example: Contract preview generation.
        
        This example shows how to generate a preview of a contract
        before creating the final contract.
        """
        try:
            # Get required data
            chantier = self.env['construction.chantier'].search([], limit=1)
            subcontractor = self.env['res.partner'].search([('is_company', '=', True)], limit=1)
            lot = self.env['construction.lot'].search([], limit=1)
            
            if not all([chantier, subcontractor, lot]):
                raise ValidationError(_("Required data not found for example"))
            
            # Prepare contract data
            contract_data = {
                'chantier_id': chantier.id,
                'subcontractor_id': subcontractor.id,
                'lot_ids': [lot.id],
                'start_date': fields.Date.today(),
                'end_date': fields.Date.today() + fields.timedelta(days=30),
                'total_amount': 25000.0,
                'payment_terms': '30_days',
                'warranty_period': 12,
                'insurance_required': True,
                'notes': 'Preview contract example',
                'urssaf_code': '43.34Z',
            }
            
            # Generate preview using orchestrator
            orchestrator = self.env['construction.contract.orchestrator']
            preview_html = orchestrator.generate_preview(contract_data)
            
            _logger.info(f"Contract preview generated: {len(preview_html)} characters")
            return preview_html
            
        except Exception as e:
            _logger.error(f"Error in contract preview generation example: {e}")
            raise ValidationError(_("Error in contract preview generation example: %s") % str(e))

    def example_contract_validation(self):
        """
        Example: Contract validation.
        
        This example shows how to validate contract data before
        generating the contract.
        """
        try:
            # Get required data
            chantier = self.env['construction.chantier'].search([], limit=1)
            subcontractor = self.env['res.partner'].search([('is_company', '=', True)], limit=1)
            lot = self.env['construction.lot'].search([], limit=1)
            
            if not all([chantier, subcontractor, lot]):
                raise ValidationError(_("Required data not found for example"))
            
            # Prepare contract data
            contract_data = {
                'chantier_id': chantier.id,
                'subcontractor_id': subcontractor.id,
                'lot_ids': [lot.id],
                'start_date': fields.Date.today(),
                'end_date': fields.Date.today() + fields.timedelta(days=30),
                'total_amount': 15000.0,
                'payment_terms': '30_days',
                'warranty_period': 12,
                'insurance_required': True,
                'notes': 'Validation contract example',
                'urssaf_code': '43.34Z',
            }
            
            # Validate contract data
            orchestrator = self.env['construction.contract.orchestrator']
            is_valid = orchestrator.validate_contract_configuration(contract_data)
            
            _logger.info(f"Contract validation result: {is_valid}")
            return is_valid
            
        except Exception as e:
            _logger.error(f"Error in contract validation example: {e}")
            raise ValidationError(_("Error in contract validation example: %s") % str(e))

    def example_contract_builder_usage(self):
        """
        Example: Using the contract builder directly.
        
        This example shows how to use the contract builder pattern
        for more granular control over contract creation.
        """
        try:
            # Get required data
            chantier = self.env['construction.chantier'].search([], limit=1)
            subcontractor = self.env['res.partner'].search([('is_company', '=', True)], limit=1)
            lot = self.env['construction.lot'].search([], limit=1)
            
            if not all([chantier, subcontractor, lot]):
                raise ValidationError(_("Required data not found for example"))
            
            # Use contract builder directly
            contract_builder = self.env['construction.contract.builder'](self.env)
            contract = (contract_builder
                       .set_basic_info(chantier.id, subcontractor.id, f'Builder Example Contract - {lot.name}')
                       .add_lots([lot.id])
                       .set_dates(fields.Date.today(), fields.Date.today() + fields.timedelta(days=45))
                       .set_financial_terms(30000.0, '45_days', self.env.company.currency_id.id)
                       .set_legal_terms(18, True, '43.34Z')
                       .set_additional_info('Contract created using builder pattern')
                       .build())
            
            _logger.info(f"Contract built using builder pattern: {contract.contract_number}")
            return contract
            
        except Exception as e:
            _logger.error(f"Error in contract builder example: {e}")
            raise ValidationError(_("Error in contract builder example: %s") % str(e))

    def example_document_generation(self):
        """
        Example: Document generation for existing contract.
        
        This example shows how to generate documents for an
        existing contract.
        """
        try:
            # Get existing contract
            contract = self.env['construction.subcontractor.contract'].search([], limit=1)
            
            if not contract:
                raise ValidationError(_("No existing contract found for example"))
            
            # Generate documents using orchestrator
            orchestrator = self.env['construction.contract.orchestrator']
            success = orchestrator.generate_contract_documents(contract)
            
            _logger.info(f"Document generation result: {success}")
            return success
            
        except Exception as e:
            _logger.error(f"Error in document generation example: {e}")
            raise ValidationError(_("Error in document generation example: %s") % str(e))

    def run_all_examples(self):
        """
        Run all contract generation examples.
        
        This method runs all examples in sequence to demonstrate
        the complete contract generation system.
        """
        try:
            _logger.info("Starting contract generation examples...")
            
            # Example 1: Basic contract generation
            _logger.info("Example 1: Basic contract generation")
            basic_contract = self.example_basic_contract_generation()
            
            # Example 2: Multi-lot contract generation
            _logger.info("Example 2: Multi-lot contract generation")
            multi_lot_contract = self.example_multi_lot_contract_generation()
            
            # Example 3: Contract preview generation
            _logger.info("Example 3: Contract preview generation")
            preview_html = self.example_contract_preview_generation()
            
            # Example 4: Contract validation
            _logger.info("Example 4: Contract validation")
            validation_result = self.example_contract_validation()
            
            # Example 5: Contract builder usage
            _logger.info("Example 5: Contract builder usage")
            builder_contract = self.example_contract_builder_usage()
            
            # Example 6: Document generation
            _logger.info("Example 6: Document generation")
            document_result = self.example_document_generation()
            
            _logger.info("All contract generation examples completed successfully")
            
            return {
                'basic_contract': basic_contract,
                'multi_lot_contract': multi_lot_contract,
                'preview_html': preview_html,
                'validation_result': validation_result,
                'builder_contract': builder_contract,
                'document_result': document_result,
            }
            
        except Exception as e:
            _logger.error(f"Error running contract generation examples: {e}")
            raise ValidationError(_("Error running contract generation examples: %s") % str(e))
