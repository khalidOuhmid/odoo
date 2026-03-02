# -*- coding: utf-8 -*-
"""
Construction Lot — Sale Price Extension
========================================
Extends construction.lot with sale-order-driven price computation.
When a Sale Order is confirmed, the lot's price is recomputed
from the sum of confirmed line subtotals.
"""

from odoo import models, fields, api


class Lot(models.Model):
    """Extend construction.lot with sale-driven price computation.

    Adds:
        sale_line_ids: reverse One2many to sale.order.line via lot_id
        price: recomputed from confirmed SO lines (state in sale/done)
    """
    _inherit = 'construction.lot'

    sale_line_ids = fields.One2many(
        'sale.order.line',
        'lot_id',
        string='Quote Lines',
        help="Sale order lines linked to this technical lot.",
    )

    price = fields.Monetary(
        compute='_compute_price_from_so',
        store=True,
        readonly=False,
        tracking=True,
        help="Total untaxed amount from confirmed sale order lines (state: sale or done).",
    )

    @api.depends('sale_line_ids.price_subtotal', 'sale_line_ids.state', 'sale_line_ids.order_id.state')
    def _compute_price_from_so(self):
        """Compute lot revenue from confirmed Sale Orders.

        Business rules:
            - Only lines belonging to orders in state 'sale' or 'done' are summed.
            - Draft, sent and cancelled orders are ignored.
            - If no confirmed lines exist, price defaults to 0.0.
        """
        for lot in self:
            confirmed_lines = lot.sale_line_ids.filtered(
                lambda l: l.state in ('sale', 'done')
            )
            lot.price = sum(confirmed_lines.mapped('price_subtotal')) if confirmed_lines else 0.0
