# -*- coding: utf-8 -*-
"""Extension du modèle construction.chantier pour les achats."""

from odoo import api, fields, models, _


class ChantierPurchaseExtension(models.Model):
    """Extension pour ajouter les fonctionnalités d'achat au chantier."""
    
    _inherit = 'construction.chantier'

    # =================== COMPUTED FIELDS ===================
    # Note: We do NOT use One2many here because the inverse field 'chantier_id'
    # on 'purchase.order' is defined in the same module and may not be registered
    # at the time Odoo sets up the One2many field. Instead, we use computed fields
    # with search methods which are more robust.
    
    purchase_order_count = fields.Integer(
        string='Nombre de commandes',
        compute='_compute_purchase_stats'
    )
    
    purchase_total = fields.Monetary(
        string='Total Achats',
        compute='_compute_purchase_stats',
        currency_field='currency_id'
    )
    
    purchase_margin = fields.Monetary(
        string='Marge Globale',
        compute='_compute_purchase_stats',
        currency_field='currency_id',
        help="Différence entre prix de vente lots et achats"
    )

    def _compute_purchase_stats(self):
        """Calcule les statistiques d'achat du chantier.
        
        Uses direct search to avoid dependency on One2many field.
        """
        PurchaseOrder = self.env['purchase.order']
        for record in self:
            # Search for purchase orders linked to this chantier
            all_orders = PurchaseOrder.search([('chantier_id', '=', record.id)])
            confirmed_orders = all_orders.filtered(
                lambda o: o.state in ['purchase', 'done']
            )
            record.purchase_order_count = len(all_orders)
            record.purchase_total = sum(confirmed_orders.mapped('amount_total'))
            
            # Marge = Prix lots - Achats
            if record.total_cost and record.purchase_total:
                record.purchase_margin = record.total_cost - record.purchase_total
            else:
                record.purchase_margin = 0

    # =================== HELPER METHODS ===================

    def _get_purchase_orders(self):
        """Helper method to get purchase orders for this chantier.
        
        Returns:
            recordset: All purchase orders linked to this chantier
        """
        self.ensure_one()
        return self.env['purchase.order'].search([('chantier_id', '=', self.id)])

    # =================== ACTIONS ===================

    def action_view_purchase_orders(self):
        """Smart button: Voir les commandes fournisseur."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Commandes - %s') % self.name,
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('chantier_id', '=', self.id)],
            'context': {
                'default_chantier_id': self.id,
            },
        }

    def action_create_purchase_orders(self):
        """Ouvrir le wizard de création groupée de commandes."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Créer Commandes Fournisseur'),
            'res_model': 'construction.purchase.grouped.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_chantier_id': self.id,
                'default_lot_ids': [(6, 0, self.lots_ids.ids)],
            },
        }
