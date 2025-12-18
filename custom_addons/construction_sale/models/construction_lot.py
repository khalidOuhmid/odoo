# -*- coding: utf-8 -*-
from odoo import models, fields, api

class Lot(models.Model):
    _inherit = 'construction.lot'

    sale_line_ids = fields.One2many(
        'sale.order.line',
        'lot_id',
        string='Lignes de Devis',
        help="Lignes de commande liées à ce lot technique"
    )
    
    price = fields.Monetary(
        compute='_compute_price_from_so',
        store=True,
        readonly=False,
        tracking=True,
        help="Montant total HT des lignes de commande validées (État: Vente ou Fait) liées à ce lot."
    )

    @api.depends('sale_line_ids.price_subtotal', 'sale_line_ids.state', 'sale_line_ids.order_id.state')
    def _compute_price_from_so(self):
        """
        Compute the sold price (Revenue) from confirmed Sales Orders.
        
        Logic:
        - Filters lines belonging to 'sale' or 'done' orders (Confirmed).
        - Ignores 'draft', 'sent', 'cancel'.
        - Sums the untaxed amount (price_subtotal).
        """
        for lot in self:
            # We use the relation to lines to handle recomputes efficiently
            # Note: sale.order.line state mirrors order_id.state
            confirmed_lines = lot.sale_line_ids.filtered(
                lambda l: l.state in ['sale', 'done']
            )
            
            # Additional safety: ensure line is not cancelled (though state handles this)
            
            if confirmed_lines:
                lot.price = sum(confirmed_lines.mapped('price_subtotal'))
            else:
                # If no confirmed sales, we check if there are any lines at all.
                # If lines exist (e.g. drafts only), price is 0 (unconfirmed revenue).
                # If NO lines exist, we preserve the user's manual input (Scenario: Budget Plan without Quote)
                if not lot.sale_line_ids:
                    # Keep existing value (do nothing)
                    # Note: Odoo compute methods usually require setting a value.
                    # If we don't set it, it keeps the stored value IF explicitly handled.
                    # But for compute+store, standard behavior defaults to recomputing.
                    # We'll default to 0.0 unless we really want manual fallback which is tricky with compute.
                    # Given the user request "Price is not retrieved", strict sync is preferred.
                    lot.price = 0.0
                else:
                     lot.price = 0.0
