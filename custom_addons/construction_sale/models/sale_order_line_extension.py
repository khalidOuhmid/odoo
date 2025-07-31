# -*- coding: utf-8 -*-
"""
Extension du modèle sale.order.line pour les types de prix construction
Compatible Odoo 18 - Respecte les conventions de codage officielles
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # =================== CHAMPS DE TYPE DE PRIX ===================

    # Hériter du type de prix du produit
    price_type = fields.Selection(related='product_id.price_type', readonly=True)
    price_type_label = fields.Char(related='product_id.price_type_label', readonly=True)
    
    # Champs pour les calculs spécifiques
    surface_value = fields.Float(
        string='Surface (m²)',
        help="Surface pour le calcul du prix au m²",
        digits=(10, 2)
    )
    
    length_value = fields.Float(
        string='Longueur (m)',
        help="Longueur pour le calcul du prix au mètre linéaire",
        digits=(10, 2)
    )
    
    weight_value = fields.Float(
        string='Poids (kg)',
        help="Poids pour le calcul du prix au kg",
        digits=(10, 2)
    )
    
    # Champ calculé pour le prix unitaire selon le type
    calculated_price_unit = fields.Float(
        string='Prix unitaire calculé',
        compute='_compute_calculated_price_unit',
        store=True,
        help="Prix unitaire calculé selon le type de prix"
    )
    
    # Champ pour l'affichage du libellé de quantité
    quantity_label = fields.Char(
        string='Libellé quantité',
        compute='_compute_quantity_label',
        help="Libellé adapté selon le type de prix"
    )

    # =================== MÉTHODES DE CALCUL ===================

    @api.depends('product_id', 'price_type', 'surface_value', 'length_value', 'weight_value')
    def _compute_calculated_price_unit(self):
        """Calcule le prix unitaire selon le type de prix"""
        for line in self:
            if line.product_id and line.price_type:
                line.calculated_price_unit = line.product_id.calculate_price_with_type(
                    quantity=line.product_uom_qty,
                    surface=line.surface_value,
                    length=line.length_value,
                    weight=line.weight_value
                )
            else:
                line.calculated_price_unit = line.price_unit

    @api.depends('product_id', 'price_type')
    def _compute_quantity_label(self):
        """Calcule le libellé de quantité selon le type de prix"""
        for line in self:
            if line.product_id and line.price_type:
                line.quantity_label = line.product_id.get_quantity_label()
            else:
                line.quantity_label = 'Quantité'

    @api.onchange('product_id')
    def _onchange_product_id_price_type(self):
        """Mise à jour automatique des champs selon le type de prix du produit"""
        if self.product_id:
            # Réinitialiser les valeurs
            self.surface_value = 0.0
            self.length_value = 0.0
            self.weight_value = 0.0
            
            # Mettre à jour le prix unitaire
            self.price_unit = self.product_id.list_price

    @api.onchange('surface_value', 'length_value', 'weight_value')
    def _onchange_calculation_values(self):
        """Recalculer le prix quand les valeurs de calcul changent"""
        if self.product_id and self.price_type:
            # Mettre à jour le prix unitaire selon le type
            new_price = self.product_id.calculate_price_with_type(
                quantity=1.0,  # Prix unitaire
                surface=self.surface_value,
                length=self.length_value,
                weight=self.weight_value
            )
            self.price_unit = new_price

    # =================== MÉTHODES DE VALIDATION ===================

    @api.constrains('surface_value', 'length_value', 'weight_value')
    def _check_calculation_values(self):
        """Vérifier que les valeurs de calcul sont cohérentes"""
        for line in self:
            if line.product_id and line.price_type:
                if line.price_type == 'm2' and line.surface_value <= 0:
                    raise ValidationError(_(
                        "La surface doit être supérieure à 0 pour un produit au m²."
                    ))
                elif line.price_type in ['ml', 'tube'] and line.length_value <= 0:
                    raise ValidationError(_(
                        "La longueur doit être supérieure à 0 pour un produit au mètre linéaire."
                    ))
                elif line.price_type in ['kg', 'tonne'] and line.weight_value <= 0:
                    raise ValidationError(_(
                        "Le poids doit être supérieur à 0 pour un produit au kg."
                    ))

    # =================== MÉTHODES D'AFFICHAGE ===================

    def get_display_name_with_type(self):
        """Retourne le nom d'affichage avec le type de prix"""
        self.ensure_one()
        
        base_name = self.name or self.product_id.name
        if self.product_id and self.product_id.price_type:
            type_display = self.product_id.get_price_type_display()
            return f"{base_name} ({type_display})"
        
        return base_name

    def get_quantity_display(self):
        """Retourne l'affichage de la quantité selon le type de prix"""
        self.ensure_one()
        
        if self.product_id and self.product_id.price_type:
            unit_label = self.product_id.get_unit_label()
            
            if self.product_id.price_type == 'm2':
                return f"{self.surface_value} m²"
            elif self.product_id.price_type in ['ml', 'tube']:
                return f"{self.length_value} m"
            elif self.product_id.price_type in ['kg', 'tonne']:
                return f"{self.weight_value} kg"
            else:
                return f"{self.product_uom_qty} {unit_label}"
        
        return f"{self.product_uom_qty} {self.product_uom.name}"

    # =================== MÉTHODES DE CALCUL ÉTENDUES ===================

    @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_id')
    def _compute_amount(self):
        """Étendre le calcul du montant pour les types de prix spéciaux"""
        super()._compute_amount()
        
        for line in self:
            if line.product_id and line.price_type:
                # Recalculer le montant selon le type de prix
                if line.price_type in ['m2', 'ml', 'tube', 'kg', 'tonne']:
                    # Utiliser les valeurs spécifiques pour le calcul
                    calculated_price = line.product_id.calculate_price_with_type(
                        quantity=line.product_uom_qty,
                        surface=line.surface_value,
                        length=line.length_value,
                        weight=line.weight_value
                    )
                    
                    # Appliquer la remise
                    if line.discount:
                        calculated_price = calculated_price * (1 - line.discount / 100.0)
                    
                    line.price_subtotal = calculated_price
                    line.price_total = calculated_price