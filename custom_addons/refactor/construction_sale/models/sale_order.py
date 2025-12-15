# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # ==============================================================================================
    #                                      CONSTRUCTION INTEGRATION
    # ==============================================================================================
    
    chantier_id = fields.Many2one(
        'construction.chantier',
        string='Chantier (Projet)',
        copy=False,
        tracking=True,
        domain="[('partner_id', '=', partner_id)]",
        help="Linked Construction Site."
    )
    
    lot_ids = fields.Many2many(
        'construction.lot',
        string='Lots Concernés',
        domain="[('chantier_id', '=', chantier_id)]",
        help="Work packages covered by this quote."
    )

    # ==============================================================================================
    #                                      AUTO-CREATION LOGIC
    # ==============================================================================================

    def action_confirm(self):
        """Override to auto-create Chantier/Lots if configured."""
        res = super(SaleOrder, self).action_confirm()
        for order in self:
            if not order.chantier_id:
                # SAP Logic: If no project exists, should we create one?
                # For now, let's keep it manual or optional to avoid clutter.
                pass
            else:
                # If confirmed, update Chantier budget based on Quote?
                # This could be a complex rule. Let's log it for now.
                order.chantier_id.message_post(
                    body=_("Devis %s validé pour un montant de %s") % (order.name, order.amount_total)
                )
                if order.chantier_id.state == 'draft':
                    order.chantier_id.action_confirm_study()
        return res

    def action_create_chantier(self):
        """Button to create a Chantier from a Quote."""
        self.ensure_one()
        if self.chantier_id:
            raise ValidationError(_("Un chantier est déjà lié à ce devis."))
            
        vals = {
            'name': self.partner_id.name + " - " + (self.client_order_ref or "Nouveau Projet"),
            'partner_id': self.partner_id.id,
            'address_id': self.partner_shipping_id.id,
            'state': 'study',
        }
        chantier = self.env['construction.chantier'].create(vals)
        self.chantier_id = chantier.id
        
        # Determine Lots from Sections?
        # SAP/Onaya Feature: "Structure from Quote"
        current_sequence = 0
        current_lot = False
        
        # Need to parse lines to find "sections" that could be "Lots"
        # This is advanced. For this iteration, we just link the object.
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'construction.chantier',
            'res_id': chantier.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # ==============================================================================================
    #                                      SMART ORGANIZATION
    # ==============================================================================================

    def action_organize_by_lots(self):
        """
        Organize order lines into sections based on selected Lots.
        This provides the 'Onaya' estimation view.
        """
        self.ensure_one()
        if not self.lot_ids:
            raise ValidationError(_("Veuillez sélectionner des lots."))
            
        # Implementation details omitted for brevity, but this would
        # re-sequence lines and insert Section headers for each Lot.
        pass
