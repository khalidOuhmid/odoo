# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class PurchaseOrder(models.Model):
    """
    Extension of Purchase Order to handle Contract Generation.
    Allows defining a contract template directly on the PO or linking to a main Contract.
    """
    _inherit = 'purchase.order'

    # The HTML content editable via GrapeJS
    contract_template_html = fields.Html(
        string='Contract Content',
        sanitize=False,
        help="Full HTML content of the contract, editable via GrapeJS"
    )

    contract_id = fields.Many2one(
        'construction.contract',
        string='Linked Contract',
        readonly=True,
        copy=False
    )

    @api.model
    def create(self, vals):
        po = super().create(vals)
        po._link_to_contracts()
        return po

    def _link_to_contracts(self):
        """Auto-link this PO to matching contracts based on lot_ids + partner."""
        for po in self:
            if not (hasattr(po, 'lot_ids') and po.lot_ids and po.partner_id):
                continue
            contracts = self.env['construction.contract'].search([
                ('lot_ids', 'in', po.lot_ids.ids),
                ('subcontractor_id', '=', po.partner_id.id),
            ])
            for contract in contracts:
                if po not in contract.purchase_order_ids:
                    contract.purchase_order_ids = [(4, po.id)]

    def action_generate_pdf(self):
        """
        Generate PDF from the HTML content using the PDF Service.
        """
        self.ensure_one()
        # Create a temporary contract object or use the service directly
        # For now, we delegate to the existing construction.contract logic
        if not self.contract_id:
            vals = {
                'subcontractor_id': self.partner_id.id,
                'chantier_id': self.chantier_id.id,
                'sale_order_ids': [(6, 0, [])],
                'custom_html_override': self.contract_template_html
            }
            self.contract_id = self.env['construction.contract'].create(vals)
        
        return self.contract_id.action_generate_pdf()

    def action_open_contract_editor(self):
        """
        Opens the GrapeJS editor for this PO.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'construction_contract.grapejs_editor',
            'context': {
                'active_model': 'purchase.order',
                'active_id': self.id,
                'field_name': 'contract_template_html'
            }
        }

    def write(self, vals):
        """
        Override write to trigger lot financial recomputation when PO state changes.
        Also blocks modifications to POs that are linked to signed contracts (F-03).
        """
        # Block critical modifications if PO belongs to a signed contract
        blocked_fields = {'order_line', 'amount_total', 'amount_untaxed', 'state', 'partner_id', 'price_unit', 'product_qty'}
        if any(f in vals for f in blocked_fields) and not self.env.context.get('ignore_signed_contract_lock'):
            for po in self:
                if hasattr(po, 'lot_ids') and po.lot_ids:
                    signed_contracts = self.env['construction.contract'].search([
                        ('state', '=', 'signed'),
                        ('lot_ids', 'in', po.lot_ids.ids),
                        ('subcontractor_id', '=', po.partner_id.id)
                    ])
                    if signed_contracts:
                        raise models.UserError(
                            _("Validation Financière Stricte (F-03): Modification impossible. "
                              "Le bon de commande '%s' est rattaché au contrat signé '%s'.") % 
                            (po.name, ', '.join(signed_contracts.mapped('name')))
                        )

        res = super().write(vals)
        
        # Trigger lot financial recompute if state changed to confirmed
        if 'state' in vals and vals['state'] in ('purchase', 'done'):
            lots_to_update = self.env['construction.lot']
            for po in self:
                # Get lots linked via lot_ids on PO or via PO lines
                if hasattr(po, 'lot_ids') and po.lot_ids:
                    lots_to_update |= po.lot_ids
                for line in po.order_line:
                    if hasattr(line, 'lot_id') and line.lot_id:
                        lots_to_update |= line.lot_id
            
            if lots_to_update:
                lots_to_update._compute_lot_financials()
        
        return res

    def unlink(self):
        """Prevent deletion of POs linked to signed contracts (F-03)"""
        for po in self:
            if hasattr(po, 'lot_ids') and po.lot_ids:
                signed_contracts = self.env['construction.contract'].search([
                    ('state', '=', 'signed'),
                    ('lot_ids', 'in', po.lot_ids.ids),
                    ('subcontractor_id', '=', po.partner_id.id)
                ])
                if signed_contracts:
                    raise models.UserError(
                        _("Validation Financière Stricte (F-03): Suppression impossible. "
                          "Le bon de commande '%s' est rattaché au contrat signé '%s'.") % 
                        (po.name, ', '.join(signed_contracts.mapped('name')))
                    )
        return super().unlink()
