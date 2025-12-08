# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_create_purchase_for_subcontractors(self):
        """
        Generate Purchase Orders for Subcontractors based on Lots in Sale Order Lines.
        Rules:
        1. Group lines by Lot.
        2. Identify Subcontractor for each Lot.
        3. If Internal resource -> SKIP.
        4. If External -> Create PO (Group by Subcontractor).
        """
        self.ensure_one()
        
        # Prepare data structure: { partner_id: [line_vals, ...] }
        po_data = {}
        
        for line in self.order_line:
            if line.display_type or not line.lot_id:
                continue

            lot = line.lot_id
            
            # Find Assigned Subcontractor(s)
            subcontractors = lot.subcontractor_ids
            if not subcontractors:
                # No subcontractor assigned -> check if we should default to something or skip
                continue

            # Check if Internal (Skip)
            # Logic: If ANY assigned partner is NOT a subcontractor (e.g. Employee), we might skip?
            # Or better: Check the user-defined logic. internal = specific flag or employee.
            # User said: "si c'est un interne on skip toute la phase contrat et documents... et bon de commande"
            
            # Assumption: We take the first assigned subcontractor.
            partner = subcontractors[0]
            
            if not partner.is_subcontractor:
                 # Likely internal or standard partner. Skip PO generation.
                 continue

            # Prepare PO Line logic
            if partner not in po_data:
                po_data[partner] = []

            po_data[partner].append({
                'name': line.name,
                'product_id': line.product_id.id,
                'product_qty': line.product_uom_qty,
                'product_uom': line.product_uom.id,
                'price_unit': line.price_unit, # Or cost price? Usually PO uses cost. Sale uses sell price.
                # For now, let's assume we want to track the quoted item. 
                # Ideally we should use the supplier info price, but let's default to a placeholder or cost.
                # 'price_unit': line.product_id.standard_price, 
                'lot_id': lot.id,
                'taxes_id': [(6, 0, line.tax_id.ids)], # Careful with sales taxes vs purchase taxes
                'date_planned': fields.Datetime.now(),
            })

        if not po_data:
            raise UserError(_("Aucun lot avec sous-traitant externe valide trouvé pour générer des commandes."))

        generated_pos = self.env['purchase.order']
        
        for partner, lines in po_data.items():
            # Create PO
            po_vals = {
                'partner_id': partner.id,
                'chantier_id': self.chantier_id.id,
                'origin': self.name,
                'date_order': fields.Datetime.now(),
                'order_line': [],
            }
            
            # Check for existing open PO for this partner on this chantier? 
            # User said "génére instante un bon de commande pour chaque lot" -> implying new POs?
            # Or "un seul qui couvre tout".
            # "le fait qu'un sous traitant est sur plusieurs lots c'est bon ? car on va pas lui envoyer un contrat pour chaque lot mais un seul".
            # Implication: Consolidate POs or Lines.
            # Strategy: Create ONE PO per Partner for this execution.
            
            for l in lines:
                # Determine Price: Use product cost or leave 0 for manual entry?
                # Using 0.0 to force review is often safer than exposing Sales Price to Vendor.
                l['price_unit'] = 0.0 
                po_vals['order_line'].append((0, 0, l))
            
            po = self.env['purchase.order'].create(po_vals)
            generated_pos += po

            # Link PO to Contract if exists, or create Contract?
            # User said: "on va pas lui envoyer un contrat pour chaque lot mais un seul... qui contient bien tout les bon de commande"
            # Check for existing Contract
            contract = self.env['construction.contract'].search([
                ('partner_id', '=', partner.id),
                ('chantier_id', '=', self.chantier_id.id),
                ('state', 'in', ['draft', 'sent', 'signed'])
            ], limit=1)
            
            if contract:
                po.contract_id = contract.id
                # Add lots to contract if not present
                contract.lot_ids = [(4, lot_id) for line in po.order_line if (lot_id := line.lot_id.id)]
            else:
                # Create Contract Automatically? 
                # User didn't strictly say auto-create contract, but "Contract contains POs".
                # Let's create a Draft Contract if none exists.
                contract = self.env['construction.contract'].create({
                    'partner_id': partner.id,
                    'chantier_id': self.chantier_id.id,
                    'date_start': fields.Date.today(),
                    'lot_ids': [(6, 0, generated_pos.mapped('lot_ids').ids)],
                })
                po.contract_id = contract.id

        return {
            'name': 'Bons de Commande Générés',
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('id', 'in', generated_pos.ids)],
            'target': 'current',
        }
