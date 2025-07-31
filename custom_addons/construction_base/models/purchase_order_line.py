# -*- coding: utf-8 -*-
"""
Extension du modèle purchase.order.line pour la gestion des chantiers de construction
Compatible Odoo 18 - Respecte les conventions de codage officielles
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    # =================== LIENS AVEC LES LOTS ===================

    lot_id = fields.Many2one(
        'construction.lot',
        string='Lot',
        help="Lot de construction associé à cette ligne"
    )

    # =================== CHAMPS DE LOCALISATION ===================

    room_location = fields.Char(
        string='Localisation',
        help="Localisation dans le bâtiment (ex: Salle de bain, Cuisine...)"
    )

    floor_level = fields.Char(
        string='Étage',
        help="Niveau d'étage (ex: RDC, 1er étage, Sous-sol...)"
    )

    construction_notes = fields.Text(
        string='Notes construction',
        help="Notes spécifiques à la construction pour cette ligne"
    )

    # =================== MÉTHODES MÉTIER ===================

    @api.onchange('product_id')
    def _onchange_product_id_construction(self):
        """Mise à jour automatique lors du changement de produit"""
        if self.product_id:
            # Mettre à jour le nom avec des informations de construction si disponibles
            if self.room_location or self.floor_level:
                construction_info = []
                if self.floor_level:
                    construction_info.append(f"[{self.floor_level}]")
                if self.room_location:
                    construction_info.append(self.room_location)
                
                if construction_info:
                    self.name = f"{self.product_id.name} - {' '.join(construction_info)}"
            else:
                self.name = self.product_id.name

    @api.onchange('lot_id')
    def _onchange_lot_id(self):
        """Mise à jour automatique lors du changement de lot"""
        if self.lot_id and self.order_id.chantier_id:
            # Vérifier que le lot appartient au chantier
            if self.lot_id not in self.order_id.chantier_id.lots_ids:
                return {
                    'warning': {
                        'title': _('Lot invalide'),
                        'message': _('Ce lot n\'appartient pas au chantier sélectionné.')
                    }
                }

    # =================== MÉTHODES DE VALIDATION ===================

    @api.constrains('lot_id', 'order_id')
    def _check_lot_compatibility(self):
        """Vérifier que le lot est compatible avec le chantier du bon de commande"""
        for record in self:
            if record.lot_id and record.order_id.chantier_id:
                if record.lot_id not in record.order_id.chantier_id.lots_ids:
                    raise ValidationError(
                        _("Le lot '%s' n'appartient pas au chantier '%s'")
                        % (record.lot_id.name, record.order_id.chantier_id.name)
                    )

    # =================== MÉTHODES DE CALCUL ===================

    @api.depends('product_uom_qty', 'price_unit', 'discount')
    def _compute_amount_construction(self):
        """Calculer le montant pour la construction avec notes"""
        for line in self:
            # Calcul standard
            price = line.price_unit * (1 - line.discount / 100.0)
            line.price_total = price * line.product_uom_qty
            
            # Ajouter des informations de construction si disponibles
            if line.room_location or line.floor_level or line.construction_notes:
                construction_info = []
                if line.floor_level:
                    construction_info.append(f"Étage: {line.floor_level}")
                if line.room_location:
                    construction_info.append(f"Localisation: {line.room_location}")
                if line.construction_notes:
                    construction_info.append(f"Notes: {line.construction_notes}")
                
                # Stocker les informations de construction dans un champ calculé si nécessaire
                line.construction_info = " | ".join(construction_info)

    # =================== MÉTHODES D'AFFICHAGE ===================

    def action_view_lot(self):
        """Voir le lot associé"""
        self.ensure_one()
        
        if not self.lot_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'warning',
                    'message': 'Aucun lot associé à cette ligne.',
                    'sticky': False,
                }
            }
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'Lot - {self.lot_id.name}',
            'res_model': 'construction.lot',
            'res_id': self.lot_id.id,
            'view_mode': 'form',
            'target': 'current',
        }