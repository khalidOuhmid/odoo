# -*- coding: utf-8 -*-
"""
Multi-Lot Handler

Handles multi-lot contract logic and consolidation.
Manages lot grouping, validation, and contract structure for multiple lots.
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class MultiLotHandler(models.AbstractModel):
    """
    Handler for multi-lot contract operations.
    
    This service handles:
    - Lot grouping and validation
    - Multi-lot contract structure
    - Lot consolidation logic
    - Purchase order consolidation
    """
    _name = 'construction.multi.lot.handler'
    _description = 'Multi-Lot Handler'

    def can_group_lots(self, lot_ids, subcontractor_id):
        """
        Check if lots can be grouped in a single contract.
        
        Args:
            lot_ids (list): List of lot IDs
            subcontractor_id (int): Subcontractor ID
            
        Returns:
            bool: True if lots can be grouped
        """
        if not lot_ids or not subcontractor_id:
            return False
        
        lots = self.env['construction.lot'].browse(lot_ids)
        subcontractor = self.env['res.partner'].browse(subcontractor_id)
        
        # Check if all lots belong to same chantier
        chantiers = lots.mapped('chantier_id')
        if len(chantiers) > 1:
            return False
        
        # Check if all lots assigned to same subcontractor
        for lot in lots:
            if subcontractor not in lot.subcontractor_ids:
                return False
        
        # Check if no active contracts exist
        existing_contracts = self.env['construction.subcontractor.contract'].search([
            ('lot_ids', 'in', lot_ids),
            ('subcontractor_id', '=', subcontractor_id),
            ('state', 'in', ['sent', 'signed', 'active']),
        ])
        
        return len(existing_contracts) == 0

    def get_grouped_lots_info(self, lot_ids, subcontractor_id):
        """
        Get information about grouped lots.
        
        Args:
            lot_ids (list): List of lot IDs
            subcontractor_id (int): Subcontractor ID
            
        Returns:
            dict: Grouped lots information
        """
        lots = self.env['construction.lot'].browse(lot_ids)
        subcontractor = self.env['res.partner'].browse(subcontractor_id)
        
        total_amount = sum(lots.mapped('price'))
        chantier = lots[0].chantier_id if lots else False
        
        return {
            'lots': lots,
            'subcontractor': subcontractor,
            'chantier': chantier,
            'total_amount': total_amount,
            'lot_count': len(lots),
            'lot_names': ', '.join(lots.mapped('name')),
        }

    def create_grouped_contract_name(self, lots, subcontractor, chantier):
        """
        Create name for grouped contract.
        
        Args:
            lots: construction.lot recordset
            subcontractor: res.partner record
            chantier: construction.chantier record
            
        Returns:
            str: Contract name
        """
        if len(lots) == 1:
            return f'Contract {subcontractor.name} - {chantier.name} - {lots[0].name}'
        else:
            lot_names = ', '.join(lots.mapped('name'))
            return f'Grouped Contract {subcontractor.name} - {chantier.name} ({lot_names})'

    def consolidate_purchase_orders(self, contract):
        """
        Consolidate purchase orders for multi-lot contract.
        
        Args:
            contract: construction.subcontractor.contract record
            
        Returns:
            list: Consolidated purchase orders
        """
        all_orders = []
        order_totals = {}
        
        for lot in contract.lot_ids:
            lot_orders = self._get_lot_purchase_orders(lot, contract)
            for order in lot_orders:
                if order.id not in order_totals:
                    order_totals[order.id] = {
                        'order': order,
                        'lots': [],
                        'total': 0.0
                    }
                
                # Calculate lot-specific total
                lot_lines = order.order_line.filtered(lambda l: l.lot_id.id == lot.id or not l.lot_id)
                lot_total = sum(lot_lines.mapped('price_subtotal'))
                
                order_totals[order.id]['lots'].append({
                    'lot': lot,
                    'total': lot_total
                })
                order_totals[order.id]['total'] += lot_total
        
        # Convert to list
        for order_data in order_totals.values():
            all_orders.append(order_data)
        
        return all_orders

    def get_consolidated_financial_summary(self, contract):
        """
        Get financial summary for multi-lot contract.
        
        Args:
            contract: construction.subcontractor.contract record
            
        Returns:
            dict: Financial summary
        """
        lot_totals = {}
        total_amount = 0.0
        
        for lot in contract.lot_ids:
            lot_orders = self._get_lot_purchase_orders(lot, contract)
            lot_total = sum(order.order_line.filtered(
                lambda l: l.lot_id.id == lot.id or not l.lot_id
            ).mapped('price_subtotal') for order in lot_orders)
            
            lot_totals[lot.id] = {
                'lot': lot,
                'amount': lot_total,
                'order_count': len(lot_orders)
            }
            total_amount += lot_total
        
        return {
            'lot_totals': lot_totals,
            'total_amount': total_amount,
            'lot_count': len(contract.lot_ids),
            'currency': contract.currency_id,
        }

    def validate_multi_lot_structure(self, contract_data):
        """
        Validate multi-lot contract structure.
        
        Args:
            contract_data (dict): Contract configuration data
            
        Returns:
            bool: True if valid
            
        Raises:
            ValidationError: If validation fails
        """
        lot_ids = contract_data.get('lot_ids', [])
        subcontractor_id = contract_data.get('subcontractor_id')
        
        if len(lot_ids) < 2:
            return True  # Not a multi-lot contract
        
        # Validate grouping possibility
        if not self.can_group_lots(lot_ids, subcontractor_id):
            raise ValidationError(_('Lots cannot be grouped in a single contract'))
        
        # Validate business rules
        self._validate_multi_lot_business_rules(lot_ids, subcontractor_id)
        
        return True

    def _validate_multi_lot_business_rules(self, lot_ids, subcontractor_id):
        """Validate business rules for multi-lot contracts."""
        lots = self.env['construction.lot'].browse(lot_ids)
        
        # Check if lots have compatible work types
        work_types = lots.mapped('work_type')
        if len(work_types) > 1:
            _logger.warning(f'Multi-lot contract with different work types: {work_types}')
        
        # Check if lots have compatible schedules
        start_dates = lots.mapped('planned_start_date')
        end_dates = lots.mapped('planned_end_date')
        
        if start_dates and len(set(start_dates)) > 1:
            _logger.warning(f'Multi-lot contract with different start dates: {start_dates}')
        
        if end_dates and len(set(end_dates)) > 1:
            _logger.warning(f'Multi-lot contract with different end dates: {end_dates}')

    def _get_lot_purchase_orders(self, lot, contract):
        """Get purchase orders for a specific lot."""
        orders_via_lot_ids = self.env['purchase.order'].search([
            ('lot_ids', 'in', [lot.id]),
            ('state', 'in', ['draft', 'sent', 'to_approve', 'purchase', 'done'])
        ])
        
        order_lines_with_lot = self.env['purchase.order.line'].search([
            ('lot_id', '=', lot.id),
            ('order_id.state', 'in', ['draft', 'sent', 'to_approve', 'purchase', 'done'])
        ])
        orders_via_lines = order_lines_with_lot.mapped('order_id')
        
        all_lot_orders = orders_via_lot_ids | orders_via_lines
        
        if contract.subcontractor_id:
            return all_lot_orders.filtered(lambda po: po.partner_id == contract.subcontractor_id)
        
        return all_lot_orders

    def get_multi_lot_contract_preview_data(self, contract_data):
        """
        Get preview data for multi-lot contract.
        
        Args:
            contract_data (dict): Contract configuration data
            
        Returns:
            dict: Preview data
        """
        lot_ids = contract_data.get('lot_ids', [])
        subcontractor_id = contract_data.get('subcontractor_id')
        
        if not lot_ids or not subcontractor_id:
            return {}
        
        lots = self.env['construction.lot'].browse(lot_ids)
        subcontractor = self.env['res.partner'].browse(subcontractor_id)
        chantier = lots[0].chantier_id if lots else False
        
        # Get financial summary
        financial_summary = self.get_consolidated_financial_summary({
            'lot_ids': lots,
            'subcontractor_id': subcontractor,
            'currency_id': contract_data.get('currency_id', self.env.company.currency_id)
        })
        
        # Get purchase orders summary
        purchase_orders = self.consolidate_purchase_orders({
            'lot_ids': lots,
            'subcontractor_id': subcontractor
        })
        
        return {
            'lots': lots,
            'subcontractor': subcontractor,
            'chantier': chantier,
            'financial_summary': financial_summary,
            'purchase_orders': purchase_orders,
            'can_group': self.can_group_lots(lot_ids, subcontractor_id),
        }
