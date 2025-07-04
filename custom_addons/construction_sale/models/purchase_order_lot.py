# -*- coding: utf-8 -*-
"""
Module: Purchase Order Lot Extension
Description: Gestion des bons de commande par lots pour les sous-traitants
Author: BLG Groupe
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PurchaseOrderLot(models.Model):
    """Bon de commande spécifique pour un lot et un sous-traitant"""
    
    _name = 'purchase.order.lot'
    _description = 'Bon de commande par lot'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_order desc, name desc'

    # ================== CHAMPS PRINCIPAUX ==================
    
    name = fields.Char(
        string='Référence',
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: _('New')
    )
    
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('sent', 'Envoyé'),
        ('confirmed', 'Confirmé'),
        ('done', 'Terminé'),
        ('cancel', 'Annulé')
    ], string='État', default='draft', tracking=True)
    
    # ================== RELATIONS ==================
    
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Devis d\'origine',
        required=True,
        ondelete='cascade',
        help="Devis principal d'où provient ce bon de commande"
    )
    
    chantier_id = fields.Many2one(
        'construction.chantier',
        string='Chantier',
        related='sale_order_id.chantier_id',
        store=True
    )
    
    lot_id = fields.Many2one(
        'lot',
        string='Lot',
        required=True,
        help="Lot de travaux pour ce bon de commande"
    )
    
    partner_id = fields.Many2one(
        'res.partner',
        string='Sous-traitant',
        required=True,
        domain="[('is_company', '=', True), ('supplier_rank', '>', 0)]",
        help="Sous-traitant qui exécutera les travaux"
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Entreprise',
        default=lambda self: self.env.company
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Devise',
        related='company_id.currency_id'
    )
    
    # ================== DATES ==================
    
    date_order = fields.Datetime(
        string='Date de commande',
        required=True,
        default=fields.Datetime.now
    )
    
    date_planned = fields.Date(
        string='Date prévue',
        required=True,
        default=fields.Date.today,
        help="Date prévue de début des travaux"
    )
    
    date_delivery = fields.Date(
        string='Date de livraison',
        help="Date prévue de fin des travaux"
    )
    
    # ================== LIGNES DE COMMANDE ==================
    
    order_line = fields.One2many(
        'purchase.order.lot.line',
        'order_id',
        string='Lignes de commande',
        copy=True
    )
    
    # ================== MONTANTS ==================
    
    amount_untaxed = fields.Monetary(
        string='Total HT',
        store=True,
        readonly=True,
        compute='_compute_amount_all',
        tracking=True
    )
    
    amount_tax = fields.Monetary(
        string='Taxes',
        store=True,
        readonly=True,
        compute='_compute_amount_all'
    )
    
    amount_total = fields.Monetary(
        string='Total TTC',
        store=True,
        readonly=True,
        compute='_compute_amount_all',
        tracking=True
    )
    
    # ================== INFORMATIONS COMPLÉMENTAIRES ==================
    
    notes = fields.Text(string='Conditions et notes')
    
    payment_term_id = fields.Many2one(
        'account.payment.term',
        string='Conditions de paiement'
    )
    
    # ================== STATISTIQUES ==================
    
    line_count = fields.Integer(
        string='Nombre de lignes',
        compute='_compute_line_count'
    )
    
    @api.depends('order_line.price_total')
    def _compute_amount_all(self):
        """Calcule les montants totaux"""
        for order in self:
            amount_untaxed = amount_tax = 0.0
            for line in order.order_line:
                amount_untaxed += line.price_subtotal
                amount_tax += line.price_tax
            order.update({
                'amount_untaxed': amount_untaxed,
                'amount_tax': amount_tax,
                'amount_total': amount_untaxed + amount_tax,
            })
    
    @api.depends('order_line')
    def _compute_line_count(self):
        """Calcule le nombre de lignes"""
        for order in self:
            order.line_count = len(order.order_line)
    
    @api.model
    def create(self, vals):
        """Générer la séquence lors de la création"""
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('purchase.order.lot') or _('New')
        return super(PurchaseOrderLot, self).create(vals)
    
    def action_send_subcontractor(self):
        """Envoyer le bon de commande au sous-traitant"""
        self.ensure_one()
        self.write({'state': 'sent'})
        
        # Envoyer par email
        template = self.env.ref('construction_sale.email_template_purchase_order_lot', raise_if_not_found=False)
        if template:
            template.send_mail(self.id, force_send=True)
        
        return self._show_success_notification(
            "Bon de commande envoyé",
            f"Le bon de commande {self.name} a été envoyé à {self.partner_id.name}"
        )
    
    def action_confirm(self):
        """Confirmer le bon de commande"""
        self.ensure_one()
        self.write({'state': 'confirmed'})
        
        return self._show_success_notification(
            "Bon de commande confirmé",
            f"Le bon de commande {self.name} a été confirmé"
        )
    
    def action_mark_done(self):
        """Marquer comme terminé"""
        self.ensure_one()
        self.write({'state': 'done'})
        
        return self._show_success_notification(
            "Travaux terminés",
            f"Les travaux du lot {self.lot_id.name} sont terminés"
        )
    
    def action_cancel(self):
        """Annuler le bon de commande"""
        self.ensure_one()
        self.write({'state': 'cancel'})
        
        return self._show_success_notification(
            "Bon de commande annulé",
            f"Le bon de commande {self.name} a été annulé"
        )
    
    def _show_success_notification(self, title, message):
        """Afficher une notification de succès"""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'title': title,
                'message': message,
                'sticky': False,
            }
        }


class PurchaseOrderLotLine(models.Model):
    """Ligne de bon de commande par lot"""
    
    _name = 'purchase.order.lot.line'
    _description = 'Ligne de bon de commande par lot'
    _order = 'order_id, sequence, id'

    # ================== RELATIONS ==================
    
    order_id = fields.Many2one(
        'purchase.order.lot',
        string='Bon de commande',
        required=True,
        ondelete='cascade',
        index=True
    )
    
    sale_line_id = fields.Many2one(
        'sale.order.line',
        string='Ligne de devis d\'origine',
        help="Ligne du devis principal d'où provient cette ligne"
    )
    
    product_id = fields.Many2one(
        'product.product',
        string='Produit',
        domain="[('purchase_ok', '=', True)]",
        change_default=True
    )
    
    # ================== DÉTAILS ==================
    
    sequence = fields.Integer(string='Séquence', default=10)
    
    name = fields.Text(string='Description', required=True)
    
    product_qty = fields.Float(
        string='Quantité',
        digits='Product Unit of Measure',
        required=True,
        default=1.0
    )
    
    product_uom = fields.Many2one(
        'uom.uom',
        string='Unité de mesure',
        domain="[('category_id', '=', product_uom_category_id)]"
    )
    
    product_uom_category_id = fields.Many2one(
        related='product_id.uom_id.category_id'
    )
    
    # ================== PRIX ==================
    
    price_unit = fields.Float(
        string='Prix unitaire',
        required=True,
        digits='Product Price',
        default=0.0
    )
    
    price_subtotal = fields.Monetary(
        compute='_compute_amount',
        string='Sous-total',
        readonly=True,
        store=True
    )
    
    price_total = fields.Monetary(
        compute='_compute_amount',
        string='Total',
        readonly=True,
        store=True
    )
    
    price_tax = fields.Float(
        compute='_compute_amount',
        string='Taxes',
        readonly=True,
        store=True
    )
    
    # ================== TAXES ==================
    
    taxes_id = fields.Many2many(
        'account.tax',
        string='Taxes',
        domain="[('type_tax_use', '=', 'purchase')]",
        default=lambda self: self._default_taxes()
    )
    
    currency_id = fields.Many2one(
        related='order_id.currency_id',
        store=True,
        string='Devise',
        readonly=True
    )
    
    # ================== INFORMATIONS SPÉCIFIQUES ==================
    
    room = fields.Char(string='Pièce', help="Pièce où sera réalisé le travail")
    floor = fields.Char(string='Étage', help="Étage de la pièce")
    notes = fields.Text(string='Notes techniques')
    
    @api.depends('product_qty', 'price_unit', 'taxes_id')
    def _compute_amount(self):
        """Calcule les montants des lignes"""
        for line in self:
            vals = line._prepare_compute_all_values()
            taxes = line.taxes_id.compute_all(
                vals['price_unit'],
                vals['currency_id'],
                vals['product_qty'],
                product=vals['product_id'],
                partner=vals['partner_id']
            )
            line.update({
                'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                'price_total': taxes['total_included'],
                'price_subtotal': taxes['total_excluded'],
            })
    
    def _prepare_compute_all_values(self):
        """Prépare les valeurs pour le calcul des taxes"""
        self.ensure_one()
        return {
            'price_unit': self.price_unit,
            'currency_id': self.order_id.currency_id,
            'product_qty': self.product_qty,
            'product_id': self.product_id,
            'partner_id': self.order_id.partner_id,
        }
    
    def _default_taxes(self):
        """Taxes par défaut pour les achats"""
        return self.env['account.tax'].search([
            ('type_tax_use', '=', 'purchase'),
            ('company_id', '=', self.env.company.id)
        ], limit=1)
    
    @api.onchange('product_id')
    def onchange_product_id(self):
        """Mise à jour automatique lors du changement de produit"""
        if not self.product_id:
            return
        
        # Mise à jour du nom
        self.name = self.product_id.display_name
        
        # Mise à jour de l'unité de mesure
        if self.product_id.uom_po_id:
            self.product_uom = self.product_id.uom_po_id
        
        # Mise à jour du prix
        if self.product_id.seller_ids:
            seller = self.product_id.seller_ids[0]
            self.price_unit = seller.price
        else:
            self.price_unit = self.product_id.standard_price
        
        # Mise à jour des taxes
        taxes = self.product_id.supplier_taxes_id.filtered(
            lambda r: not self.order_id.company_id or r.company_id == self.order_id.company_id
        )
        self.taxes_id = taxes 