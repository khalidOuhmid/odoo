# -*- coding: utf-8 -*-
"""
Contract Builder

Builder pattern implementation for constructing contracts step by step.
Handles validation, configuration, and document generation in a clean way.
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class ContractBuilder(models.AbstractModel):
    """
    Builder for constructing contracts step by step.
    
    This builder provides a fluent interface for creating contracts:
    - Set basic information
    - Add lots
    - Configure terms
    - Generate documents
    - Finalize contract
    """
    _name = 'construction.contract.builder'
    _description = 'Contract Builder'

    def __init__(self, env):
        super().__init__(env)
        self._contract_data = {}
        self._lots = []
        self._validation_errors = []

    def set_basic_info(self, chantier_id, subcontractor_id, name=None):
        """Set basic contract information."""
        self._contract_data.update({
            'chantier_id': chantier_id,
            'subcontractor_id': subcontractor_id,
            'name': name or self._generate_contract_name(chantier_id, subcontractor_id),
        })
        return self

    def add_lots(self, lot_ids):
        """Add lots to the contract."""
        if isinstance(lot_ids, (list, tuple)):
            self._lots.extend(lot_ids)
        else:
            self._lots.append(lot_ids)
        return self

    def set_dates(self, start_date, end_date=None):
        """Set contract dates."""
        self._contract_data.update({
            'start_date': start_date,
            'end_date': end_date,
        })
        return self

    def set_financial_terms(self, total_amount, payment_terms='30_days', currency_id=None):
        """Set financial terms."""
        self._contract_data.update({
            'total_amount': total_amount,
            'payment_terms': payment_terms,
            'currency_id': currency_id or self.env.company.currency_id.id,
        })
        return self

    def set_legal_terms(self, warranty_period=12, insurance_required=True, urssaf_code='43.34Z'):
        """Set legal terms."""
        self._contract_data.update({
            'warranty_period': warranty_period,
            'insurance_required': insurance_required,
            'urssaf_code': urssaf_code,
        })
        return self

    def set_additional_info(self, notes=''):
        """Set additional information."""
        self._contract_data.update({
            'notes': notes,
        })
        return self

    def validate(self):
        """Validate the contract configuration."""
        self._validation_errors = []
        
        # Validate required fields
        required_fields = ['chantier_id', 'subcontractor_id', 'start_date', 'total_amount']
        for field in required_fields:
            if not self._contract_data.get(field):
                self._validation_errors.append(_("Field %s is required") % field)
        
        # Validate lots
        if not self._lots:
            self._validation_errors.append(_("At least one lot must be specified"))
        
        # Validate subcontractor assignment
        for lot_id in self._lots:
            lot = self.env['construction.lot'].browse(lot_id)
            subcontractor = self.env['res.partner'].browse(self._contract_data['subcontractor_id'])
            if subcontractor not in lot.subcontractor_ids:
                self._validation_errors.append(
                    _("Lot '%s' is not assigned to subcontractor '%s'") % (lot.name, subcontractor.name)
                )
        
        if self._validation_errors:
            raise ValidationError('\n'.join(self._validation_errors))
        
        return True

    def build(self):
        """Build and return the contract."""
        self.validate()
        
        contract_data = self._contract_data.copy()
        contract_data['lot_ids'] = [(6, 0, self._lots)]
        
        contract = self.env['construction.subcontractor.contract'].create(contract_data)
        
        # Generate documents
        self._generate_contract_documents(contract)
        
        return contract

    def _generate_contract_name(self, chantier_id, subcontractor_id):
        """Generate contract name based on chantier and subcontractor."""
        chantier = self.env['construction.chantier'].browse(chantier_id)
        subcontractor = self.env['res.partner'].browse(subcontractor_id)
        
        if len(self._lots) > 1:
            lot_names = ", ".join([lot.name for lot in self.env['construction.lot'].browse(self._lots)])
            return f'Grouped Contract {subcontractor.name} - {chantier.name} ({lot_names})'
        else:
            lot = self.env['construction.lot'].browse(self._lots[0])
            return f'Contract {subcontractor.name} - {chantier.name} - {lot.name}'

    def _generate_contract_documents(self, contract):
        """Generate contract documents."""
        try:
            document_generator = self.env['construction.document.generator']
            pdf_content = document_generator.generate_contract_pdf(contract)
            
            access_token = contract._generate_access_token()
            portal_url = self._create_portal_link(contract, access_token)
            
            filename = self._generate_filename(contract)
            
            contract.write({
                'contract_pdf': pdf_content,
                'filename': filename,
                'portal_url': portal_url,
                'access_token': access_token
            })
            
        except Exception as e:
            _logger.error(f"Error generating contract documents: {e}")
            raise ValidationError(_("Error generating contract documents: %s") % str(e))

    def _create_portal_link(self, contract, access_token):
        """Create portal link for contract."""
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return f"{base_url}/portal/contract/{contract.id}/sign?access_token={access_token}"

    def _generate_filename(self, contract):
        """Generate filename for contract."""
        from datetime import datetime
        lot_names = "_".join([lot.name.replace(" ", "_") for lot in contract.lot_ids])
        return f"Contract_{contract.subcontractor_id.name}_{lot_names}_{datetime.now().strftime('%Y%m%d')}.pdf"
