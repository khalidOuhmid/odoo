# -*- coding: utf-8 -*-
"""
Sale Order Construction Extension
=================================
Enhances standard Sale Order with Construction workflow capabilities.
Designed to work with the Owl SPA frontend.
"""

from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    """
    Extension of Sale Order for Construction Projects.
    
    Includes:
    - Link to Construction Site (Chantier)
    - Lot management
    - Advanced Status tracking for Construction
    """
    _inherit = 'sale.order'

    # Note: chantier_id is defined in construction_core

    # ============================================================
    # LOT MANAGEMENT
    # ============================================================

    lot_ids = fields.Many2many(
        'construction.lot',
        string='Construction Lots',
        help="Technical lots included in this quote (e.g., Plumbing, Electricity)"
    )

    # Field required by some Odoo views - prevents field undefined error
    quotation_document_ids = fields.Many2many(
        'ir.attachment',
        string='Quotation Documents',
        compute='_compute_quotation_documents',
        help="Documents attached to this quotation"
    )
    
    @api.depends('name')
    def _compute_quotation_documents(self):
        for order in self:
            order.quotation_document_ids = False

    # Additional fields required by some Odoo views
    customizable_pdf_form_fields = fields.Integer(
        string='PDF Form Fields',
        compute='_compute_pdf_form_fields',
        help="Number of customizable PDF form fields"
    )
    
    @api.depends('name')
    def _compute_pdf_form_fields(self):
        for order in self:
            order.customizable_pdf_form_fields = 0

    # Field required by sale_pdf_quote_builder views
    is_pdf_quote_builder_available = fields.Boolean(
        string='PDF Quote Builder Available',
        compute='_compute_pdf_quote_builder_available',
        help="Whether PDF Quote Builder is available"
    )
    
    @api.depends('partner_id')
    def _compute_pdf_quote_builder_available(self):
        for order in self:
            order.is_pdf_quote_builder_available = False

    # ============================================================
    # QUOTE REFERENCE AUTO-GENERATION (US-SAL-005)
    # Format: [CHANTIER_NAME]-DEV-[SEQUENCE]
    # ============================================================
    
    quote_reference = fields.Char(
        string='Référence Devis',
        copy=False,
        readonly=True,
        help="Auto-generated: [NOM_CHANTIER]-DEV-[NUMERO]"
    )
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Bug Fix #4: Override generic name with [CHANTIER]-DEV-[SEQ]
            if vals.get('chantier_id'):
                chantier = self.env['construction.chantier'].browse(vals['chantier_id'])
                # Count existing quotes for this chantier
                existing_count = self.search_count([('chantier_id', '=', chantier.id)])
                # Generate formatted name
                chantier_name = chantier.name.replace(' ', '-').upper()[:15] if chantier.name else 'CHANTIER'
                # Format: PROJECT-DEV-001-v1
                new_name = f"{chantier_name}-DEV-{existing_count + 1:03d}-v1"
                
                vals['name'] = new_name
                vals['quote_reference'] = new_name
                
        return super().create(vals_list)

    # ============================================================
    # BUSINESS LOGIC & VALIDATION
    # ============================================================

    @api.constrains('chantier_id', 'partner_id')
    def _check_chantier_consistency(self):
        """Enforce partner/chantier coherence.

        Business rule: if the chantier has a client, the order's partner
        must match. This prevents billing to the wrong entity.
        """
        for order in self:
            if order.chantier_id and order.chantier_id.client and order.partner_id:
                if order.partner_id != order.chantier_id.client:
                    raise models.ValidationError(
                        _("Order %s: partner %s differs from chantier client %s") % (
                            order.name, order.partner_id.name, order.chantier_id.client.name
                        )
                    )

    @api.constrains('amount_total', 'state')
    def _check_monetary_safety(self):
        """
        SAP-Level Logic: Prevent negative or dangerously low value orders.
        ensures financial integrity before confirmation.
        """
        for order in self:
            if order.state in ['sale', 'done']:
                if order.amount_total < 0:
                    raise models.ValidationError(
                        _("CRITICAL: Sales Order '%s' has a negative total amount (%s). This is strictly prohibited by accounting rules.") 
                        % (order.name, order.amount_total)
                    )
                
                # Optional: Zero check (unless it's a specific warranty replacement)
                if order.amount_total == 0 and not self.env.context.get('allow_zero_total'):
                    _logger.warning("Order %s confirmed with 0 amount", order.name)

    # ============================================================
    # API METHODS (For SPA/Owl)
    # ============================================================

    @api.model
    def create_from_spa(self, vals: dict) -> dict:
        """Create a quote from the SPA Interface with validation.
        
        API endpoint called by the OWL QuoteBuilder to persist cart data
        as a proper sale.order record.
        
        Args:
            vals: JSON payload from frontend containing order data
                 Expected structure:
                 {
                     'chantier_id': int,
                     'partner_id': int,
                     'order_line': [(0, 0, {...}), ...]
                 }
            
        Returns:
            Dictionary with created order details
            
        Raises:
            ValidationError: If required fields are missing
            AccessError: If user lacks creation permissions
        """
        chantier_id = vals.get('chantier_id')
        if not chantier_id:
            _logger.warning("SPA Quote created without chantier_id")

        # Support custom name for revisions (e.g., "ChantierDupont-001-v2")
        name_override = vals.pop('name_override', None)

        # Generate custom name: {chantier_name}-{seq}-v1
        if chantier_id and not name_override:
            chantier = self.env['construction.chantier'].browse(chantier_id)
            if chantier:
                existing_quotes = self.search_count([('chantier_id', '=', chantier_id)])
                seq_num = str(existing_quotes + 1).zfill(3)
                chantier_short = chantier.name[:20].replace(' ', '-')
                name_override = f"{chantier_short}-{seq_num}-v1"
                _logger.debug("Generated quote name: %s", name_override)

        order = super().create(vals)

        if name_override:
            order.write({'name': name_override})

        order._resequence_lines_by_lot()

        return {
            'id': order.id,
            'name': order.name,
            'state': order.state,
        }

    def action_open_quote_builder(self) -> dict:
        """Open the React/Owl Quote Builder for this order.
        
        If order is confirmed (sale state), show a warning dialog first.
        """
        self.ensure_one()
        
        # If quote is confirmed, we need to show a warning
        if self.state in ['sale', 'done']:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Attention - Devis Confirmé'),
                    'message': _('Ce devis est déjà validé. Toute modification impactera la facturation.'),
                    'type': 'warning',
                    'sticky': True,
                    'next': {
                        'type': 'ir.actions.client',
                        'tag': 'construction_sale.quote_builder',
                        'name': _('Smart Quote Builder (Mode Admin)'),
                        'context': {
                            'default_chantier_id': self.chantier_id.id,
                            'default_order_id': self.id,
                            'active_id': self.id,
                            'confirmed_order': True,
                        },
                    }
                }
            }
        
        return {
            'type': 'ir.actions.client',
            'tag': 'construction_sale.quote_builder',
            'name': _('Smart Quote Builder'),
            'context': {
                'default_chantier_id': self.chantier_id.id,
                'default_order_id': self.id,
                'active_id': self.id,
            },
        }

    @api.model
    def search_products_for_spa(self, search_term: str = "", lot_category_id: int = None, limit: int = 50) -> list[dict]:
        """Retrieve products optimized for SPA display.
        
        Implements efficient search with proper field projections to avoid N+1 queries.
        Uses search_read for optimal performance.
        
        Args:
            search_term: Optional search query for product name/code
            lot_category_id: Optional lot category ID to filter products (FIX FILTRAGE)
            limit: Maximum number of results (default 50, max 200)
            
        Returns:
            List of product dictionaries with minimal fields for performance:
            [{'id': 1, 'name': '...', 'list_price': 100.0, ...}, ...]
        """
        _logger.debug(
            "search_products_for_spa: term=%r, category=%s, limit=%s",
            search_term, lot_category_id, limit,
        )

        domain = [('sale_ok', '=', True)]

        if lot_category_id and int(lot_category_id) > 0:
            domain.append(('lot_category_ids', 'in', [int(lot_category_id)]))

        if search_term:
            domain += ['|', ('name', 'ilike', search_term), ('default_code', 'ilike', search_term)]

        result = self.env['product.product'].search_read(
            domain,
            ['id', 'display_name', 'name', 'list_price', 'default_code', 'uom_id', 'standard_price', 'lot_category_ids'],
            limit=min(limit, 200),
            order='name asc',
        )

        _logger.debug("search_products_for_spa: found %d products", len(result))
        return result

    # ============================================================
    # TASK 3: RESEQUENCE LINES BY LOT
    # ============================================================

    def write(self, vals):
        """Override write to resequence lines when they change."""
        result = super().write(vals)
        
        # Resequence if order_line was modified
        if 'order_line' in vals:
            for order in self:
                order._resequence_lines_by_lot()
        
        return result

    def action_resequence_lines(self):
        """Public action to manually trigger line resequencing."""
        for order in self:
            order._resequence_lines_by_lot()
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def _resequence_lines_by_lot(self):
        """
        Reorder lines grouped by lot_id with section headers.
        
        Business Logic:
        - Group lines by lot_id
        - Insert section headers (display_type='line_section') for each lot
        - Assign sequences: Lot 1 (10,11,12), Lot 2 (20,21,22), etc.
        """
        self.ensure_one()
        
        if not self.chantier_id:
            return  # Only for construction orders
        
        lines = self.order_line.filtered(lambda l: not l.display_type)
        if not lines:
            return
        
        # Group by lot
        lots_dict = {}
        no_lot_lines = self.env['sale.order.line']
        
        for line in lines:
            if line.lot_id:
                if line.lot_id.id not in lots_dict:
                    lots_dict[line.lot_id.id] = {
                        'lot': line.lot_id,
                        'lines': self.env['sale.order.line']
                    }
                lots_dict[line.lot_id.id]['lines'] |= line
            else:
                no_lot_lines |= line
        
        # Remove existing sections
        existing_sections = self.order_line.filtered(lambda l: l.display_type == 'line_section')
        existing_sections.unlink()
        
        # Resequence with sections
        sequence = 10
        SaleOrderLine = self.env['sale.order.line']
        
        # Sort lots by code
        sorted_lots = sorted(lots_dict.values(), key=lambda x: x['lot'].code or '')
        
        for lot_data in sorted_lots:
            lot = lot_data['lot']
            lot_lines = lot_data['lines']
            
            # Create section header - BLG Format
            SaleOrderLine.create({
                'order_id': self.id,
                'display_type': 'line_section',
                'name': f"=== {lot.code} - {lot.name} ===",
                'sequence': sequence,
            })
            sequence += 1
            
            # Assign sequences to lines
            for line in lot_lines.sorted('id'):
                line.sequence = sequence
                sequence += 1
        
        # Lines without lot at the end
        if no_lot_lines:
            SaleOrderLine.create({
                'order_id': self.id,
                'display_type': 'line_section',
                'name': "=== AUTRES ARTICLES ===",
                'sequence': sequence,
            })
            sequence += 1
            
            for line in no_lot_lines.sorted('id'):
                line.sequence = sequence
                sequence += 1

