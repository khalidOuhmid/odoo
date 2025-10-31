# -*- coding: utf-8 -*-
"""
Contract Factory

Factory pattern implementation for creating different types of construction contracts.
Supports single lot and multi-lot contracts with proper validation and configuration.
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class ContractFactory(models.AbstractModel):
    """
    Factory for creating construction contracts.
    
    This factory handles the creation of different types of contracts:
    - Single lot contracts
    - Multi-lot contracts
    - Grouped contracts for same subcontractor
    """
    _name = 'construction.contract.factory'
    _description = 'Contract Factory'

    @api.model
    def create_contract(self, contract_type, **kwargs):
        """
        Create a contract based on the specified type.
        
        Args:
            contract_type (str): Type of contract to create
            **kwargs: Contract configuration parameters
            
        Returns:
            construction.subcontractor.contract: Created contract record
        """
        factory_methods = {
            'single_lot': self._create_single_lot_contract,
            'multi_lot': self._create_multi_lot_contract,
            'grouped': self._create_grouped_contract,
        }
        
        if contract_type not in factory_methods:
            raise ValidationError(_("Invalid contract type: %s") % contract_type)
        
        return factory_methods[contract_type](**kwargs)

    def _create_single_lot_contract(self, **kwargs):
        """Create a single lot contract."""
        return self._create_contract_record(**kwargs)

    def _create_multi_lot_contract(self, **kwargs):
        """Create a multi-lot contract."""
        return self._create_contract_record(**kwargs)

    def _create_grouped_contract(self, **kwargs):
        """Create a grouped contract for multiple lots with same subcontractor."""
        return self._create_contract_record(**kwargs)

    def _create_contract_record(self, **kwargs):
        """Create the actual contract record."""
        contract_vals = self._prepare_contract_values(**kwargs)
        return self.env['construction.subcontractor.contract'].create(contract_vals)

    def _prepare_contract_values(self, **kwargs):
        """Prepare contract values for creation."""
        return {
            'name': kwargs.get('name'),
            'chantier_id': kwargs.get('chantier_id'),
            'subcontractor_id': kwargs.get('subcontractor_id'),
            'lot_ids': [(6, 0, kwargs.get('lot_ids', []))],
            'start_date': kwargs.get('start_date'),
            'end_date': kwargs.get('end_date'),
            'total_amount': kwargs.get('total_amount', 0.0),
            'payment_terms': kwargs.get('payment_terms', '30_days'),
            'warranty_period': kwargs.get('warranty_period', 12),
            'insurance_required': kwargs.get('insurance_required', True),
            'notes': kwargs.get('notes', ''),
            'urssaf_code': kwargs.get('urssaf_code'),
            'state': 'draft',
            'company_id': self.env.company.id,
        }
