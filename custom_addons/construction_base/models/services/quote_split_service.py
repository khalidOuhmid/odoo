# -*- coding: utf-8 -*-
"""
Quote Split Service

This service handles the division of main quotes into sub-quotes by construction lots
and their assignment to specialized subcontractors.
"""

from odoo import models, api, fields, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class QuoteSplitService(models.AbstractModel):
    """
    Service for splitting construction quotes by lots and assigning to subcontractors.
    
    This service provides functionality to:
    - Analyze main quotes and identify lot-specific content
    - Generate sub-quotes for each lot
    - Assign sub-quotes to appropriate subcontractors
    - Maintain relationships between main and sub-quotes
    """
    _name = 'quote.split.service'
    _description = 'Quote Splitting Service'

    @api.model
    def split_quote_by_lots(self, chantier_id, main_quote_id=None):
        """
        Split the main quote of a chantier into sub-quotes by lots.
        
        Args:
            chantier_id (int): ID of the construction project
            main_quote_id (int, optional): Specific quote to split. If None, uses the latest confirmed quote.
            
        Returns:
            dict: Result with created sub-quotes and assignment information
        """
        try:
            chantier = self.env['construction.chantier'].browse(chantier_id)
            if not chantier.exists():
                raise ValidationError(_("Construction project not found"))

            # Get the main quote to split
            main_quote = self._get_main_quote(chantier, main_quote_id)
            if not main_quote:
                raise ValidationError(_("No valid quote found to split"))

            # Validate prerequisites
            self._validate_split_prerequisites(chantier, main_quote)

            # Analyze quote structure and group by lots
            lot_groups = self._analyze_quote_structure(main_quote)
            
            if not lot_groups:
                raise ValidationError(_("No lot-specific content found in the quote"))

            # Create sub-quotes for each lot
            created_subquotes = []
            assignment_results = []

            for lot_id, quote_data in lot_groups.items():
                lot = self.env['construction.lot'].browse(lot_id)
                
                # Create sub-quote for this lot
                subquote = self._create_lot_subquote(main_quote, lot, quote_data)
                created_subquotes.append(subquote)
                
                # Try to assign to appropriate subcontractor
                assignment_result = self._assign_subquote_to_subcontractor(chantier, subquote, lot)
                assignment_results.append(assignment_result)

            # Update main quote status
            self._update_main_quote_status(main_quote, created_subquotes)

            # Log the operation
            _logger.info(
                "Quote splitting completed for chantier %s: %d sub-quotes created",
                chantier.name, len(created_subquotes)
            )

            return {
                'success': True,
                'main_quote_id': main_quote.id,
                'created_subquotes': created_subquotes.ids,
                'assignment_results': assignment_results,
                'total_subquotes': len(created_subquotes),
                'message': _("%d sub-quotes created successfully") % len(created_subquotes)
            }

        except Exception as e:
            _logger.error("Quote splitting failed for chantier %s: %s", chantier_id, str(e), exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'message': _("Quote splitting failed: %s") % str(e)
            }

    def _get_main_quote(self, chantier, main_quote_id=None):
        """Get the main quote to split."""
        if main_quote_id:
            quote = self.env['sale.order'].browse(main_quote_id)
            if quote.exists() and quote.chantier_id == chantier:
                return quote
        
        # Find the latest confirmed quote for this chantier
        quotes = self.env['sale.order'].search([
            ('chantier_id', '=', chantier.id),
            ('state', 'in', ['sale', 'done']),
        ], order='date_order desc', limit=1)
        
        return quotes[0] if quotes else None

    def _validate_split_prerequisites(self, chantier, main_quote):
        """Validate that all prerequisites for splitting are met."""
        # Check chantier stage
        if not chantier.stage_id or chantier.stage_id.code != 'FD':
            raise ValidationError(_(
                "Quote splitting is only available at the 'Finalisation dossier' stage. "
                "Current stage: %s"
            ) % (chantier.stage_id.name if chantier.stage_id else 'None'))

        # Check quote has lots
        if not main_quote.lot_ids:
            raise ValidationError(_(
                "The quote must have lots assigned before splitting. "
                "Please assign lots to the quote first."
            ))

        # Check quote has order lines
        product_lines = main_quote.order_line.filtered(lambda l: not l.display_type)
        if not product_lines:
            raise ValidationError(_(
                "The quote must have product lines to split."
            ))

        # Check chantier has subcontractors assigned
        if not chantier.subcontractors:
            raise ValidationError(_(
                "Please assign subcontractors to the project before splitting quotes."
            ))

    def _analyze_quote_structure(self, main_quote):
        """
        Analyze quote structure and group content by lots.
        
        Returns:
            dict: {lot_id: {'lines': [...], 'total': float, 'sections': [...]}}
        """
        lot_groups = {}
        current_lot = None
        
        for line in main_quote.order_line.sorted('sequence'):
            
            if line.display_type == 'line_section':
                # Try to identify lot from section name
                current_lot = self._identify_lot_from_section(line.name, main_quote.lot_ids)
                
                if current_lot and current_lot.id not in lot_groups:
                    lot_groups[current_lot.id] = {
                        'lines': [],
                        'sections': [],
                        'total': 0.0,
                        'lot': current_lot
                    }
                
                if current_lot:
                    lot_groups[current_lot.id]['sections'].append(line)
                    
            elif line.display_type == 'line_note':
                # Add notes to current lot if any
                if current_lot and current_lot.id in lot_groups:
                    lot_groups[current_lot.id]['lines'].append(line)
                    
            else:
                # Product line
                assigned_lot = self._determine_line_lot(line, current_lot, main_quote.lot_ids)
                
                if assigned_lot:
                    if assigned_lot.id not in lot_groups:
                        lot_groups[assigned_lot.id] = {
                            'lines': [],
                            'sections': [],
                            'total': 0.0,
                            'lot': assigned_lot
                        }
                    
                    lot_groups[assigned_lot.id]['lines'].append(line)
                    lot_groups[assigned_lot.id]['total'] += line.price_subtotal

        return lot_groups

    def _identify_lot_from_section(self, section_name, available_lots):
        """Try to identify a lot from section name."""
        if not section_name:
            return None
            
        # Remove common prefixes and clean the name
        clean_name = section_name.replace('📋', '').strip()
        
        # Look for exact match first
        for lot in available_lots:
            if lot.name.lower() in clean_name.lower():
                return lot
                
        # Look for code match
        for lot in available_lots:
            if lot.code and lot.code.lower() in clean_name.lower():
                return lot
                
        return None

    def _determine_line_lot(self, line, current_lot, available_lots):
        """Determine which lot a line belongs to."""
        # If line has explicit lot assignment (if such field exists)
        if hasattr(line, 'lot_id') and line.lot_id:
            return line.lot_id
            
        # If we're in a lot section context
        if current_lot:
            return current_lot
            
        # Try to determine from product category or name
        return self._guess_lot_from_product(line.product_id, available_lots)

    def _guess_lot_from_product(self, product, available_lots):
        """Try to guess lot from product characteristics."""
        if not product:
            return None
            
        # Simple keyword matching (can be enhanced)
        product_text = (product.name + ' ' + (product.categ_id.name or '')).lower()
        
        lot_keywords = {
            'général': ['général', 'general', 'divers'],
            'maçonnerie': ['maçon', 'béton', 'ciment', 'parpaing', 'brique'],
            'électricité': ['électr', 'cable', 'prise', 'interrupteur', 'tableau'],
            'plomberie': ['plomb', 'tuyau', 'robinet', 'sanitaire', 'évacuation'],
            'peinture': ['peinture', 'pinceau', 'rouleau', 'enduit'],
        }
        
        for lot in available_lots:
            lot_name_lower = lot.name.lower()
            if lot_name_lower in lot_keywords:
                keywords = lot_keywords[lot_name_lower]
                if any(keyword in product_text for keyword in keywords):
                    return lot
                    
        # If no specific match, return first available lot (général if exists)
        general_lot = available_lots.filtered(lambda l: 'général' in l.name.lower())
        return general_lot[0] if general_lot else available_lots[0]

    def _create_lot_subquote(self, main_quote, lot, quote_data):
        """Create a sub-quote for a specific lot."""
        # Prepare sub-quote values
        subquote_vals = {
            'partner_id': None,  # Will be set when assigned to subcontractor
            'chantier_id': main_quote.chantier_id.id,
            'lot_ids': [(6, 0, [lot.id])],
            'origin': main_quote.name,
            'state': 'draft',
            'validity_date': main_quote.validity_date,
            'payment_term_id': main_quote.payment_term_id.id,
            'pricelist_id': main_quote.pricelist_id.id,
            'company_id': main_quote.company_id.id,
            'currency_id': main_quote.currency_id.id,
            'note': f"Sous-devis généré automatiquement pour le lot : {lot.name}",
        }

        # Create the sub-quote
        subquote = self.env['sale.order'].create(subquote_vals)

        # Add lot section
        self._create_order_line(subquote, {
            'display_type': 'line_section',
            'name': f"📋 {lot.name}",
            'sequence': 10,
        })

        # Add all sections for this lot
        sequence = 20
        for section in quote_data.get('sections', []):
            if section.name != f"📋 {lot.name}":  # Avoid duplicate main section
                self._create_order_line(subquote, {
                    'display_type': 'line_section',
                    'name': section.name,
                    'sequence': sequence,
                })
                sequence += 10

        # Add all product lines for this lot
        for line in quote_data.get('lines', []):
            line_vals = self._prepare_subquote_line(line, sequence)
            self._create_order_line(subquote, line_vals)
            sequence += 10

        return subquote

    def _prepare_subquote_line(self, original_line, sequence):
        """Prepare values for a sub-quote line from the original line."""
        vals = {
            'sequence': sequence,
            'display_type': original_line.display_type,
            'name': original_line.name,
        }

        if not original_line.display_type:
            # Product line
            vals.update({
                'product_id': original_line.product_id.id,
                'product_uom_qty': original_line.product_uom_qty,
                'product_uom': original_line.product_uom.id,
                'price_unit': original_line.price_unit,
                'discount': original_line.discount,
                'tax_id': [(6, 0, original_line.tax_id.ids)],
            })
            
            # Copy construction-specific fields if they exist
            construction_fields = ['room_location', 'floor_level', 'construction_notes']
            for field in construction_fields:
                if hasattr(original_line, field):
                    value = getattr(original_line, field)
                    if value:
                        vals[field] = value

        return vals

    def _create_order_line(self, order, vals):
        """Create an order line with proper defaults."""
        vals['order_id'] = order.id
        return self.env['sale.order.line'].create(vals)

    def _assign_subquote_to_subcontractor(self, chantier, subquote, lot):
        """Assign sub-quote to appropriate subcontractor."""
        # Find subcontractors specialized in this lot
        specialized_subcontractors = chantier.subcontractors.filtered(
            lambda s: lot in s.lot_ids
        )

        if not specialized_subcontractors:
            return {
                'subquote_id': subquote.id,
                'lot_name': lot.name,
                'assigned': False,
                'reason': 'No specialized subcontractor found',
                'available_subcontractors': chantier.subcontractors.ids
            }

        # For now, assign to the first specialized subcontractor
        # In the future, could add logic for workload balancing, preferences, etc.
        selected_subcontractor = specialized_subcontractors[0]
        
        # Update the sub-quote with the subcontractor
        subquote.write({
            'partner_id': selected_subcontractor.id,
        })

        return {
            'subquote_id': subquote.id,
            'lot_name': lot.name,
            'assigned': True,
            'subcontractor_id': selected_subcontractor.id,
            'subcontractor_name': selected_subcontractor.name,
        }

    def _update_main_quote_status(self, main_quote, subquotes):
        """Update main quote to link it with sub-quotes."""
        # Add a note to the main quote
        note = _("This quote has been split into %d sub-quotes:\n") % len(subquotes)
        for subquote in subquotes:
            partner_name = subquote.partner_id.name if subquote.partner_id else _("Unassigned")
            note += f"- {subquote.name} ({partner_name})\n"
        
        if main_quote.note:
            main_quote.note += f"\n\n{note}"
        else:
            main_quote.note = note

    @api.model
    def get_subquotes_for_chantier(self, chantier_id):
        """Get all sub-quotes for a chantier."""
        return self.env['sale.order'].search([
            ('chantier_id', '=', chantier_id),
            ('origin', '!=', False),  # Sub-quotes have origin set
        ])

    @api.model
    def can_split_quote(self, chantier_id):
        """Check if quote splitting is available for a chantier."""
        chantier = self.env['construction.chantier'].browse(chantier_id)
        
        # Check stage
        if not chantier.stage_id or chantier.stage_id.code != 'FD':
            return False
            
        # Check has confirmed quotes
        quotes = self.env['sale.order'].search([
            ('chantier_id', '=', chantier_id),
            ('state', 'in', ['sale', 'done']),
        ])
        
        return bool(quotes)

    @api.model
    def quick_access_subquote(self, subquote_id):
        """Quick access action for sub-quote editing."""
        subquote = self.env['sale.order'].browse(subquote_id)
        if not subquote.exists():
            raise ValidationError(_("Sub-quote not found"))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Sub-quote: %s') % subquote.name,
            'res_model': 'sale.order',
            'res_id': subquote_id,
            'view_mode': 'form',
            'target': 'new',  # Open in popup for quick editing
            'context': {
                'default_chantier_id': subquote.chantier_id.id,
                'form_view_initial_mode': 'edit',
            }
        } 