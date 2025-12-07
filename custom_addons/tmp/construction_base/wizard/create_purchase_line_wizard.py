# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class CreatePurchaseLineWizard(models.TransientModel):
    _name = 'construction.create.purchase.line.wizard'
    _description = 'Ajouter un article de commande pour le chantier'

    chantier_id = fields.Many2one('construction.chantier', string='Chantier', required=True)
    vendor_id = fields.Many2one('res.partner', string='Fournisseur', domain="[('supplier_rank','>',0)]", required=True)
    product_id = fields.Many2one('product.product', string='Produit', required=True)
    name = fields.Char('Description')
    product_qty = fields.Float('Quantité', default=1.0, required=True)
    price_unit = fields.Float('Prix unitaire', default=0.0)
    lot_id = fields.Many2one('construction.lot', string='Lot', domain="[('chantier_id','=',chantier_id)]")
    expected_delivery_date = fields.Datetime('Date de livraison prévue')
    tracking_link = fields.Char('Lien de tracking')
    delivery_place = fields.Char('Lieu de livraison')

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id and not self.name:
            self.name = self.product_id.get_product_multiline_description_sale()

    def action_create(self):
        self.ensure_one()
        if not self.chantier_id:
            raise ValidationError(_('Chantier requis.'))
        if not self.vendor_id:
            raise ValidationError(_('Fournisseur requis.'))

        # Chercher un bon de commande brouillon existant pour ce chantier et fournisseur
        po = self.env['purchase.order'].search([
            ('state', 'in', ['draft', 'sent']),
            ('chantier_id', '=', self.chantier_id.id),
            ('partner_id', '=', self.vendor_id.id),
        ], limit=1)

        if not po:
            po = self.env['purchase.order'].create({
                'partner_id': self.vendor_id.id,
                'chantier_id': self.chantier_id.id,
                'date_order': fields.Datetime.now(),
            })

        # Créer la ligne
        line_vals = {
            'order_id': po.id,
            'product_id': self.product_id.id,
            'name': self.name or self.product_id.display_name,
            'product_qty': self.product_qty,
            'price_unit': self.price_unit or self.product_id.standard_price,
            'lot_id': self.lot_id.id if self.lot_id else False,
            'expected_delivery_date': self.expected_delivery_date,
            'tracking_link': self.tracking_link,
            'delivery_place': self.delivery_place,
            'product_uom': self.product_id.uom_po_id.id,
        }

        self.env['purchase.order.line'].create(line_vals)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Bon de commande'),
            'res_model': 'purchase.order',
            'res_id': po.id,
            'view_mode': 'form',
            'target': 'current',
        }


