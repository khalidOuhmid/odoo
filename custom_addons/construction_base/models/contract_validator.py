# -*- coding: utf-8 -*-
"""
Contract Validator

Validation service for contract data and business rules.
Ensures data integrity and business rule compliance.
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class ContractValidator(models.AbstractModel):
    """
    Validator for contract data and business rules.
    
    This service handles:
    - Data validation
    - Business rule validation
    - Cross-field validation
    - Multi-lot validation
    """
    _name = 'construction.contract.validator'
    _description = 'Contract Validator'

    def validate_contract_data(self, contract_data):
        """
        Validate contract data.
        
        Args:
            contract_data (dict): Contract configuration data
            
        Returns:
            bool: True if valid
            
        Raises:
            ValidationError: If validation fails
        """
        self._validate_required_fields(contract_data)
        self._validate_dates(contract_data)
        self._validate_financial_data(contract_data)
        self._validate_lots(contract_data)
        self._validate_subcontractor_assignment(contract_data)
        
        return True

    def validate_multi_lot_contract(self, contract_data):
        """
        Validate multi-lot contract specific rules.
        
        Args:
            contract_data (dict): Contract configuration data
            
        Returns:
            bool: True if valid
            
        Raises:
            ValidationError: If validation fails
        """
        lot_ids = contract_data.get('lot_ids', [])
        
        if len(lot_ids) < 2:
            return True  # Not a multi-lot contract
        
        # Validate all lots belong to same chantier
        self._validate_lots_same_chantier(lot_ids, contract_data.get('chantier_id'))
        
        # Validate all lots assigned to same subcontractor
        self._validate_lots_same_subcontractor(lot_ids, contract_data.get('subcontractor_id'))
        
        # Validate no overlapping contracts
        self._validate_no_overlapping_contracts(contract_data)
        
        return True

    def _validate_required_fields(self, contract_data):
        """Validate required fields are present."""
        required_fields = {
            'chantier_id': _('Chantier is required'),
            'subcontractor_id': _('Subcontractor is required'),
            'start_date': _('Start date is required'),
            'total_amount': _('Total amount is required'),
            'lot_ids': _('At least one lot is required'),
        }
        
        for field, error_message in required_fields.items():
            if not contract_data.get(field):
                raise ValidationError(error_message)

    def _validate_dates(self, contract_data):
        """Validate date fields."""
        start_date = contract_data.get('start_date')
        end_date = contract_data.get('end_date')
        
        if start_date and end_date and end_date < start_date:
            raise ValidationError(_('End date must be after start date'))
        
        if start_date and start_date < fields.Date.today():
            raise ValidationError(_('Start date cannot be in the past'))

    def _validate_financial_data(self, contract_data):
        """Validate financial data."""
        total_amount = contract_data.get('total_amount', 0)
        
        if total_amount <= 0:
            raise ValidationError(_('Total amount must be greater than zero'))
        
        if total_amount > 1000000:  # 1M limit
            raise ValidationError(_('Total amount exceeds maximum limit'))

    def _validate_lots(self, contract_data):
        """Validate lot data."""
        lot_ids = contract_data.get('lot_ids', [])
        
        if not lot_ids:
            raise ValidationError(_('At least one lot must be specified'))
        
        # Validate lots exist
        lots = self.env['construction.lot'].browse(lot_ids)
        if len(lots) != len(lot_ids):
            raise ValidationError(_('Some lots do not exist'))
        
        # Validate lots are active
        inactive_lots = lots.filtered(lambda l: l.state != 'active')
        if inactive_lots:
            raise ValidationError(_('Some lots are not active: %s') % ', '.join(inactive_lots.mapped('name')))

    def _validate_subcontractor_assignment(self, contract_data):
        """Validate subcontractor assignment to lots."""
        lot_ids = contract_data.get('lot_ids', [])
        subcontractor_id = contract_data.get('subcontractor_id')
        
        if not subcontractor_id or not lot_ids:
            return
        
        lots = self.env['construction.lot'].browse(lot_ids)
        subcontractor = self.env['res.partner'].browse(subcontractor_id)
        
        unassigned_lots = lots.filtered(lambda l: subcontractor not in l.subcontractor_ids)
        if unassigned_lots:
            raise ValidationError(
                _('Lots not assigned to subcontractor: %s') % ', '.join(unassigned_lots.mapped('name'))
            )

    def _validate_lots_same_chantier(self, lot_ids, chantier_id):
        """Validate all lots belong to same chantier."""
        if not chantier_id or not lot_ids:
            return
        
        lots = self.env['construction.lot'].browse(lot_ids)
        chantier = self.env['construction.chantier'].browse(chantier_id)
        
        wrong_chantier_lots = lots.filtered(lambda l: l.chantier_id != chantier)
        if wrong_chantier_lots:
            raise ValidationError(
                _('Lots belong to different chantier: %s') % ', '.join(wrong_chantier_lots.mapped('name'))
            )

    def _validate_lots_same_subcontractor(self, lot_ids, subcontractor_id):
        """Validate all lots assigned to same subcontractor."""
        if not subcontractor_id or not lot_ids:
            return
        
        lots = self.env['construction.lot'].browse(lot_ids)
        subcontractor = self.env['res.partner'].browse(subcontractor_id)
        
        wrong_subcontractor_lots = lots.filtered(lambda l: subcontractor not in l.subcontractor_ids)
        if wrong_subcontractor_lots:
            raise ValidationError(
                _('Lots assigned to different subcontractor: %s') % ', '.join(wrong_subcontractor_lots.mapped('name'))
            )

    def _validate_no_overlapping_contracts(self, contract_data):
        """Validate no overlapping contracts exist."""
        lot_ids = contract_data.get('lot_ids', [])
        subcontractor_id = contract_data.get('subcontractor_id')
        start_date = contract_data.get('start_date')
        end_date = contract_data.get('end_date')
        
        if not all([lot_ids, subcontractor_id, start_date]):
            return
        
        # Check for existing active contracts
        existing_contracts = self.env['construction.subcontractor.contract'].search([
            ('lot_ids', 'in', lot_ids),
            ('subcontractor_id', '=', subcontractor_id),
            ('state', 'in', ['sent', 'signed', 'active']),
        ])
        
        if existing_contracts:
            contract_names = existing_contracts.mapped('name')
            raise ValidationError(
                _('Active contracts already exist for these lots: %s') % ', '.join(contract_names)
            )

    def validate_contract_modification(self, contract, new_data):
        """
        Validate contract modification.
        
        Args:
            contract: construction.subcontractor.contract record
            new_data (dict): New contract data
            
        Returns:
            bool: True if valid
            
        Raises:
            ValidationError: If validation fails
        """
        # Cannot modify signed contracts
        if contract.state == 'signed':
            raise ValidationError(_('Cannot modify signed contracts'))
        
        # Validate new data
        self.validate_contract_data(new_data)
        
        # Validate business rules for modification
        self._validate_modification_business_rules(contract, new_data)
        
        return True

    def _validate_modification_business_rules(self, contract, new_data):
        """Validate business rules for contract modification."""
        # Check if changing subcontractor
        if new_data.get('subcontractor_id') != contract.subcontractor_id.id:
            # Validate new subcontractor assignment
            lot_ids = new_data.get('lot_ids', contract.lot_ids.ids)
            subcontractor_id = new_data.get('subcontractor_id')
            
            if subcontractor_id and lot_ids:
                self._validate_subcontractor_assignment({
                    'lot_ids': lot_ids,
                    'subcontractor_id': subcontractor_id
                })
        
        return True
