# -*- coding: utf-8 -*-
"""
Module: Construction Product Wizard
Description: Assistant moderne pour l'ajout de produits dans les devis construction
Author: BLG Groupe
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class ConstructionProductWizard(models.TransientModel):
    """Assistant moderne pour l'ajout de produits par lot"""
    
    _name = 'construction.product.wizard'
    _description = 'Assistant d\'ajout de produits construction'

    # ================== INFORMATIONS DE BASE ==================
    
    sale_order_id = fields.Many2one(
        'sale.order', 
        string='Devis', 
        required=True,
        readonly=True
    )
    
    selected_lot_id = fields.Many2one(
        'lot', 
        string='Lot sélectionné',
        help="Choisissez le lot pour lequel ajouter des produits"
    )
    
    available_lots = fields.Many2many(
        'lot',
        string='Lots disponibles',
        compute='_compute_available_lots'
    )

    # ================== RECHERCHE ET FILTRES ==================
    
    search_term = fields.Char(
        string='Rechercher un produit',
        placeholder="Nom, référence ou description..."
    )
    
    category_filter = fields.Many2one(
        'product.category',
        string='Filtrer par catégorie'
    )
    
    show_only_lot_products = fields.Boolean(
        string='Produits spécifiques au lot',
        default=True,
        help="Afficher uniquement les produits recommandés pour ce lot"
    )

    # ================== PRODUITS ET SÉLECTION ==================
    
    available_products = fields.Many2many(
        'product.product',
        'wizard_available_products_rel',
        string='Produits disponibles',
        compute='_compute_available_products'
    )
    
    selected_products = fields.One2many(
        'construction.product.line',
        'wizard_id',
        string='Produits sélectionnés'
    )

    # ================== STATISTIQUES ==================
    
    total_amount = fields.Monetary(
        string='Montant total',
        compute='_compute_totals',
        currency_field='currency_id'
    )
    
    total_items = fields.Integer(
        string='Nombre d\'articles',
        compute='_compute_totals'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        related='sale_order_id.currency_id'
    )

    # ================== MÉTHODES CALCULÉES ==================

    @api.depends('sale_order_id.lot_ids')
    def _compute_available_lots(self):
        """Calcule les lots disponibles depuis le chantier"""
        for wizard in self:
            if wizard.sale_order_id.chantier_id:
                wizard.available_lots = wizard.sale_order_id.chantier_id.lots_ids
            else:
                wizard.available_lots = wizard.sale_order_id.lot_ids

    @api.depends('search_term', 'category_filter', 'selected_lot_id', 'show_only_lot_products')
    def _compute_available_products(self):
        """Calcule les produits disponibles selon les filtres avec relation aux lots"""
        for wizard in self:
            domain = [('sale_ok', '=', True), ('active', '=', True)]
            
            # Filtre par terme de recherche
            if wizard.search_term:
                domain.extend([
                    '|', '|', '|',
                    ('name', 'ilike', wizard.search_term),
                    ('default_code', 'ilike', wizard.search_term),
                    ('description_sale', 'ilike', wizard.search_term),
                    ('barcode', 'ilike', wizard.search_term)
                ])
            
            # Filtre par catégorie
            if wizard.category_filter:
                domain.append(('categ_id', 'child_of', wizard.category_filter.id))
            
            # Filtre par lot spécifique - RELATION DIRECTE AVEC LOT
            if wizard.show_only_lot_products and wizard.selected_lot_id:
                domain.append(('lot_ids', 'in', wizard.selected_lot_id.id))
            
            # RECHERCHE AVEC CACHE REFRESH FORCÉ
            products = self.env['product.product'].search(domain, limit=100, order='create_date desc')
            wizard.available_products = products
            
            # Debug log pour vérifier les produits trouvés
            if wizard.selected_lot_id:
                lot_products = products.filtered(lambda p: wizard.selected_lot_id.id in p.lot_ids.ids)
                if lot_products:
                    _logger.debug(f"Produits trouvés pour lot {wizard.selected_lot_id.name}: {lot_products.mapped('name')}")

    @api.depends('selected_products.quantity', 'selected_products.price_unit')
    def _compute_totals(self):
        """Calcule les totaux de la sélection"""
        for wizard in self:
            wizard.total_amount = sum(
                line.quantity * line.price_unit for line in wizard.selected_products
            )
            wizard.total_items = len(wizard.selected_products.filtered('quantity'))

    # ================== ACTIONS ==================

    def action_add_product(self):
        """Ajouter un produit à la sélection depuis le contexte"""
        product_id = self.env.context.get('product_id')
        if not product_id:
            return self._reload_wizard()
        
        existing_line = self.selected_products.filtered(
            lambda l: l.product_id.id == product_id
        )
        
        if existing_line:
            existing_line.quantity += 1
        else:
            product = self.env['product.product'].browse(product_id)
            self.env['construction.product.line'].create({
                'wizard_id': self.id,
                'product_id': product_id,
                'quantity': 1.0,
                'price_unit': product.list_price,
                'lot_id': self.selected_lot_id.id if self.selected_lot_id else False,
            })
        
        return self._reload_wizard()

    def action_create_quick_product(self):
        """Ouvrir le wizard de création rapide de produit"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Créer un nouveau produit',
            'res_model': 'construction.quick.product.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_wizard_id': self.id,
                'default_lot_id': self.selected_lot_id.id if self.selected_lot_id else False,
            }
        }

    def action_confirm_selection(self):
        """Confirmer la sélection et ajouter au devis"""
        if not self.selected_products.filtered('quantity'):
            raise ValidationError("Veuillez sélectionner au moins un produit.")
        
        self._add_products_to_order()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Produits ajoutés',
                'message': f'{self.total_items} produit(s) ajouté(s) au devis.',
                'type': 'success'
            }
        }

    def action_clear_selection(self):
        """Vider la sélection"""
        self.selected_products.unlink()
        return self._reload_wizard()

    # ================== MÉTHODES PRIVÉES ==================

    def _add_products_to_order(self):
        """Ajoute les produits sélectionnés au devis"""
        # Créer une section pour le lot si nécessaire
        if self.selected_lot_id:
            self._ensure_lot_section()
        
        # Obtenir la prochaine séquence
        last_line = self.sale_order_id.order_line.sorted('sequence', reverse=True)
        sequence = (last_line[0].sequence + 10) if last_line else 10
        
        # Ajouter chaque produit
        for line in self.selected_products.filtered('quantity'):
            self._create_order_line(line, sequence)
            sequence += 10

    def _ensure_lot_section(self):
        """Assure qu'une section existe pour le lot sélectionné"""
        section_name = f"📋 {self.selected_lot_id.name}"
        existing_section = self.sale_order_id.order_line.filtered(
            lambda l: l.display_type == 'line_section' and section_name in (l.name or '')
        )
        
        if not existing_section:
            # Obtenir la séquence avant les produits
            last_line = self.sale_order_id.order_line.sorted('sequence', reverse=True)
            sequence = (last_line[0].sequence + 5) if last_line else 5
            
            self.env['sale.order.line'].create({
                'order_id': self.sale_order_id.id,
                'display_type': 'line_section',
                'name': section_name,
                'sequence': sequence,
            })

    def _create_order_line(self, product_line, sequence):
        """Crée une ligne de commande depuis une ligne de produit"""
        line_vals = {
            'order_id': self.sale_order_id.id,
            'product_id': product_line.product_id.id,
            'product_uom_qty': product_line.quantity,
            'price_unit': product_line.price_unit,
            'sequence': sequence,
        }
        
        # Ajouter les informations de localisation
        if product_line.room_location:
            line_vals['room_location'] = product_line.room_location
        if product_line.floor_level:
            line_vals['floor_level'] = product_line.floor_level
        if product_line.notes:
            line_vals['construction_notes'] = product_line.notes
        
        self.env['sale.order.line'].create(line_vals)

    def _reload_wizard(self):
        """Recharge le wizard avec refresh des produits"""
        # Forcer le recalcul des produits disponibles
        self._invalidate_cache(['available_products'])
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
    
    def action_refresh_products(self):
        """Action pour forcer le refresh des produits disponibles"""
        self._invalidate_cache(['available_products'])
        # Trigger recomputation
        self._compute_available_products()
        return self._reload_wizard()


class ConstructionProductLine(models.TransientModel):
    """Ligne de produit sélectionné dans le wizard"""
    
    _name = 'construction.product.line'
    _description = 'Ligne de produit construction'
    _order = 'sequence, product_id'

    # ================== RELATIONS ==================
    
    wizard_id = fields.Many2one(
        'construction.product.wizard',
        required=True,
        ondelete='cascade'
    )
    
    product_id = fields.Many2one(
        'product.product',
        string='Produit',
        required=True
    )
    
    lot_id = fields.Many2one(
        'lot',
        string='Lot'
    )

    # ================== QUANTITÉS ET PRIX ==================
    
    sequence = fields.Integer(string='Séquence', default=10)
    
    quantity = fields.Float(
        string='Quantité',
        default=1.0,
        required=True
    )
    
    price_unit = fields.Float(
        string='Prix unitaire',
        related='product_id.list_price',
        readonly=True
    )
    
    subtotal = fields.Float(
        string='Sous-total',
        compute='_compute_subtotal'
    )

    # ================== LOCALISATION ==================
    
    room_location = fields.Char(
        string='Localisation',
        placeholder="Ex: Salon, Cuisine, Chambre 1..."
    )
    
    floor_level = fields.Selection([
        ('basement', 'Sous-sol'),
        ('ground', 'Rez-de-chaussée'),
        ('floor_1', 'Étage 1'),
        ('floor_2', 'Étage 2'),
        ('floor_3', 'Étage 3'),
        ('attic', 'Combles'),
    ], string='Niveau')
    
    notes = fields.Text(
        string='Notes',
        placeholder="Notes techniques ou commentaires..."
    )

    # ================== INFORMATIONS PRODUIT ==================
    
    product_code = fields.Char(
        string='Référence',
        related='product_id.default_code',
        readonly=True
    )
    
    product_category = fields.Char(
        string='Catégorie',
        related='product_id.categ_id.name',
        readonly=True
    )

    # ================== MÉTHODES CALCULÉES ==================

    @api.depends('quantity', 'price_unit')
    def _compute_subtotal(self):
        """Calcule le sous-total"""
        for line in self:
            line.subtotal = line.quantity * line.price_unit

    # ================== ACTIONS ==================

    def action_remove_line(self):
        """Supprimer cette ligne"""
        self.unlink()
        return self.wizard_id._reload_wizard() 