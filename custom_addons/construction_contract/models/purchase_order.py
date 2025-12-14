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

    def action_generate_pdf(self):
        """
        Generate PDF from the HTML content using the PDF Service.
        """
        self.ensure_one()
        # Create a temporary contract object or use the service directly
        # For now, we delegate to the existing construction.contract logic
        if not self.contract_id:
            # Auto-create contract if missing
             vals = {
                'subcontractor_id': self.partner_id.id,
                'chantier_id': self.chantier_id.id,
                'sale_order_ids': [(6, 0, [])], # TODO: Link to Sales?
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
