# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # ==========================
    # CONSTRUCTION FIELDS
    # ==========================
    chantier_id = fields.Many2one(
        'construction.chantier', 
        string='Construction Site',
        tracking=True,
        domain="[('company_id', '=', company_id)]",
        help="Linked Construction Project"
    )
    
    # We allow selecting multiple lots relevant to this quote
    lot_ids = fields.Many2many(
        'construction.lot',
        string='Relevant Work Packages',
        domain="[('chantier_id', '=', chantier_id)]",
        help="Lots included in this estimation"
    )

    # ==========================
    # LOGIC
    # ==========================
    @api.onchange('chantier_id')
    def _onchange_chantier_id(self):
        if self.chantier_id:
            # Auto-set Customer if empty
            if not self.partner_id and self.chantier_id.client_id:
                self.partner_id = self.chantier_id.client_id
            
            # Suggest all lots from chantier
            if not self.lot_ids and self.chantier_id.lot_ids:
                self.lot_ids = self.chantier_id.lot_ids
                
            # Update Title if generic
            if not self.client_order_ref and self.chantier_id.reference:
                self.client_order_ref = f"Ref: {self.chantier_id.reference}"

    def action_organize_by_lots(self):
        """
        Organize order lines into Sections based on Lots.
        This provides the 'Onaya' style visual grouping.
        """
        self.ensure_one()
        _logger.info("Organizing Quote %s by Lots", self.id)
        
        lines_to_process = self.order_line.filtered(lambda l: not l.display_type and l.construction_lot_id)
        if not lines_to_process:
            return
            
        # Sort logic could be complex, for now we let user organize manually 
        # or we implement a "Smart Sort" in the Wizard.
        # Here we just ensure Sections exist for selected lots.
        
        current_sequence = 10
        existing_sections = self.order_line.filtered(lambda l: l.display_type == 'line_section').mapped('name')
        
        for lot in self.lot_ids:
            section_name = f"Lot: {lot.name}"
            if section_name not in existing_sections:
                self.env['sale.order.line'].create({
                    'order_id': self.id,
                    'display_type': 'line_section',
                    'name': section_name,
                    'sequence': current_sequence
                })
                # We put the section at the top or bottom? 
                # Ideally we want products under their section.
                # This suggests the "Wizard" approach is better for adding items.
            current_sequence += 100

    def action_open_construction_wizard(self):
        """ Opens the Smart Construction Quote Wizard """
        self.ensure_one()
        return {
            'name': _('Add Construction Items'),
            'type': 'ir.actions.act_window',
            'res_model': 'construction.quote.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sale_order_id': self.id,
                'default_chantier_id': self.chantier_id.id,
                'default_lot_ids': self.lot_ids.ids,
            }
        }
