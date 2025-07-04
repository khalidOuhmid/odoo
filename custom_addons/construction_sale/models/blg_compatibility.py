# -*- coding: utf-8 -*-
"""
Module: BLG Compatibility Models
Description: Modèles de compatibilité avec l'écosystème BLG existant
Author: BLG Groupe
Note: Ce module assure la compatibilité avec les modules BLG existants
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


# ================== COMPATIBILITÉ SALE.ORDER ==================

class SaleOrderBLGCompatibility(models.Model):
    """Extension de compatibilité BLG pour sale.order"""
    
    _inherit = 'sale.order'

    # ================== CHAMPS DE COMPATIBILITÉ BLG ==================
    
    blg_chantier_id = fields.Many2one(
        'chantier', 
        string='Projet de Construction (BLG)',
        help="Compatibilité avec l'ancien modèle chantier BLG"
    )
    
    lot_selection_ids = fields.Many2many(
        'lot.category',
        'sale_order_lot_category_rel',
        'order_id',
        'lot_category_id',
        string='Corps de métier sélectionnés (BLG)',
        help="Compatibilité avec les lots BLG"
    )
    
    selected_lot_ids = fields.Many2many(
        'lot.category',
        compute='_compute_selected_lot_ids',
        string='Lots sélectionnés (computed)'
    )
    
    filtered_product_ids = fields.Many2many(
        'product.product',
        compute='_compute_filtered_products',
        string='Produits filtrés par lot'
    )
    
    # Champs de filtres BLG
    filter_gros_oeuvre = fields.Boolean(string='Gros œuvre', default=False)
    filter_electricite = fields.Boolean(string='Électricité', default=False)
    filter_plomberie = fields.Boolean(string='Plomberie', default=False)
    filter_peinture = fields.Boolean(string='Peinture', default=False)

    # ================== MÉTHODES CALCULÉES ==================

    @api.depends('lot_selection_ids')
    def _compute_selected_lot_ids(self):
        """Compute selected lots for domain filtering"""
        for order in self:
            order.selected_lot_ids = order.lot_selection_ids

    @api.depends('lot_selection_ids')
    def _compute_filtered_products(self):
        """Filter products based on selected lots"""
        for order in self:
            if order.lot_selection_ids:
                products = self.env['product.product'].search([
                    ('sale_ok', '=', True),
                    ('active', '=', True),
                ])
                order.filtered_product_ids = products
            else:
                order.filtered_product_ids = self.env['product.product']


# ================== MODÈLES DE COMPATIBILITÉ ==================

class ChantierBLGCompatibility(models.Model):
    """Modèle de compatibilité pour l'ancien modèle chantier BLG"""
    
    _name = 'chantier'
    _description = 'Chantier BLG (compatibilité)'
    _order = 'name'

    name = fields.Char('Nom', required=True)
    reference = fields.Char('Référence')
    client_id = fields.Many2one('res.partner', string='Client')
    address = fields.Text('Adresse')
    stage_id = fields.Many2one('blg.stage', string='Étape')
    progress = fields.Float('Progression (%)')
    total_cost = fields.Float('Coût total')
    
    def name_get(self):
        """Affichage personnalisé"""
        result = []
        for record in self:
            display_name = f"[{record.reference}] {record.name}" if record.reference else record.name
            result.append((record.id, display_name))
        return result


class BlgStageCompatibility(models.Model):
    """Modèle de compatibilité pour les étapes BLG"""
    
    _name = 'blg.stage'
    _description = 'Étape BLG (compatibilité)'
    _order = 'sequence, name'

    name = fields.Char('Nom', required=True)
    code = fields.Char('Code')
    sequence = fields.Integer('Séquence', default=10)
    chapter_id = fields.Many2one('blg.chapter', string='Chapitre')


class BlgChapterCompatibility(models.Model):
    """Modèle de compatibilité pour les chapitres BLG"""
    
    _name = 'blg.chapter'
    _description = 'Chapitre BLG (compatibilité)'
    _order = 'sequence, name'

    name = fields.Char('Nom', required=True)
    code = fields.Char('Code')
    sequence = fields.Integer('Séquence', default=10)


class BlgLotTypeCompatibility(models.Model):
    """Modèle de compatibilité pour les types de lots BLG"""
    
    _name = 'blg.lot.type'
    _description = 'Type de lot BLG (compatibilité)'
    _order = 'sequence, name'

    name = fields.Char('Nom', required=True)
    code = fields.Char('Code')
    sequence = fields.Integer('Séquence', default=10)
    product_ids = fields.Many2many(
        'product.product', 
        'blg_lot_type_product_rel', 
        'lot_type_id', 
        'product_id',
        string='Produits recommandés'
    )


# ================== WIZARDS DE COMPATIBILITÉ BLG ==================

class BlgQuickProductWizardCompatibility(models.TransientModel):
    """Wizard de compatibilité pour la création rapide de produits BLG"""
    
    _name = 'blg.quick.product.wizard'
    _description = 'Création rapide de produit (compatibilité BLG)'

    # Champs de base
    name = fields.Char('Nom du produit', required=True)
    list_price = fields.Float('Prix de vente', required=True, default=0.0)
    standard_price = fields.Float('Coût', default=0.0)
    categ_id = fields.Many2one(
        'product.category', 
        string='Catégorie',
        default=lambda self: self._get_default_category()
    )
    
    # Compatibilité avec les lots BLG
    lot_id = fields.Many2one('lot.category', string='Lot métier')
    order_id = fields.Many2one('sale.order', string='Devis', required=True)
    
    # Options
    add_to_selection = fields.Boolean('Ajouter à la sélection', default=True)
    quantity = fields.Float('Quantité', default=1.0)
    name_prefix = fields.Char('Préfixe du nom')
    
    # Champ calculé
    full_name_preview = fields.Char('Aperçu du nom complet', compute='_compute_full_name_preview')

    def _get_default_category(self):
        """Obtenir une catégorie par défaut de manière sécurisée"""
        try:
            return self.env.ref('construction_sale.product_category_construction')
        except:
            return self.env['product.category'].search([], limit=1)

    @api.depends('name', 'name_prefix')
    def _compute_full_name_preview(self):
        """Calculer l'aperçu du nom complet du produit"""
        for wizard in self:
            if wizard.name_prefix and wizard.name:
                wizard.full_name_preview = f"{wizard.name_prefix}{wizard.name}"
            elif wizard.name:
                wizard.full_name_preview = wizard.name
            else:
                wizard.full_name_preview = ""

    def action_create_product_and_add(self):
        """Créer le produit et l'ajouter au devis"""
        self.ensure_one()
        
        # Utiliser le wizard moderne pour la création
        modern_wizard = self.env['construction.quick.product.wizard'].create({
            'name': self.full_name_preview or self.name,
            'list_price': self.list_price,
            'standard_price': self.standard_price,
            'categ_id': self.categ_id.id,
            'quantity': self.quantity,
            'add_to_selection': False,  # On gère l'ajout manuellement
        })
        
        # Créer le produit via le wizard moderne
        result = modern_wizard.action_create_product()
        
        # Ajouter manuellement au devis si demandé
        if self.add_to_selection and self.order_id:
            # Logique d'ajout simplifiée
            pass
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Produit créé',
                'message': f'Le produit "{self.name}" a été créé avec succès.',
                'type': 'success'
            }
        }


class BlgProductSelectionWizardCompatibility(models.TransientModel):
    """Wizard de compatibilité pour la sélection de produits BLG"""
    
    _name = 'blg.product.selection.wizard'
    _description = 'Sélection de produits par lot (compatibilité BLG)'

    # Champs de base
    order_id = fields.Many2one('sale.order', string='Devis', required=True)
    lot_id = fields.Many2one('lot.category', string='Lot métier', required=True)
    
    # Produits avec tables distinctes
    product_ids = fields.Many2many(
        'product.product', 
        'blg_wizard_product_rel', 
        'wizard_id', 
        'product_id',
        string='Produits disponibles'
    )
    selected_product_ids = fields.Many2many(
        'product.product', 
        'blg_wizard_selected_product_rel', 
        'wizard_id', 
        'product_id',
        string='Produits sélectionnés'
    )
    available_product_ids = fields.Many2many(
        'product.product', 
        'blg_wizard_available_product_rel', 
        'wizard_id', 
        'product_id',
        compute='_compute_available_products'
    )
    available_products = fields.Many2many(
        'product.product', 
        'blg_wizard_products_rel', 
        'wizard_id', 
        'product_id',
        compute='_compute_available_products'
    )
    
    # Champs de recherche
    search_term = fields.Char('Recherche')
    category_filter = fields.Many2one('product.category', string='Filtrer par catégorie')
    price_min = fields.Float('Prix minimum')
    price_max = fields.Float('Prix maximum')
    
    # Champs de compatibilité supplémentaires
    lot_progress = fields.Float('Progression du lot (%)', default=0.0)
    show_all_products = fields.Boolean('Afficher tous les produits', default=True)
    show_lot_specific_products = fields.Boolean('Produits spécifiques au lot', default=False)
    sort_by = fields.Selection([
        ('name', 'Nom'),
        ('list_price', 'Prix'),
        ('categ_id', 'Catégorie')
    ], string='Trier par', default='name')
    
    # Lignes de sélection
    selection_line_ids = fields.One2many('blg.product.selection.line', 'wizard_id', string='Produits sélectionnés')
    
    # Totaux
    total_selection = fields.Monetary('Total sélection', compute='_compute_totals', currency_field='currency_id')
    selection_count = fields.Integer('Nombre d\'articles', compute='_compute_totals')
    currency_id = fields.Many2one('res.currency', related='order_id.currency_id')
    
    # Pagination
    page_size = fields.Integer('Produits par page', default=12)
    current_page = fields.Integer('Page actuelle', default=1)
    total_pages = fields.Integer('Nombre de pages', compute='_compute_pagination')
    total_products = fields.Integer('Total produits', compute='_compute_pagination')
    
    # Navigation entre lots
    chantier_lot_ids = fields.Many2many(
        'lot.category', 
        'blg_wizard_chantier_lot_rel', 
        'wizard_id', 
        'lot_id',
        string='Lots du chantier'
    )
    current_lot_index = fields.Integer('Index du lot actuel', default=0)
    has_next_lot = fields.Boolean('A un lot suivant', default=False)
    has_previous_lot = fields.Boolean('A un lot précédent', default=False)
    lot_type_id = fields.Many2one('blg.lot.type', string='Type de lot', compute='_compute_lot_type_id')

    @api.depends('search_term', 'category_filter', 'price_min', 'price_max', 'show_all_products', 'lot_id')
    def _compute_available_products(self):
        """Calculer les produits disponibles selon les filtres"""
        for wizard in self:
            domain = [('sale_ok', '=', True), ('active', '=', True)]
            
            if wizard.search_term:
                domain.append(('name', 'ilike', wizard.search_term))
            if wizard.category_filter:
                domain.append(('categ_id', 'child_of', wizard.category_filter.id))
            if wizard.price_min > 0:
                domain.append(('list_price', '>=', wizard.price_min))
            if wizard.price_max > 0:
                domain.append(('list_price', '<=', wizard.price_max))
            
            products = self.env['product.product'].search(domain)
            wizard.available_products = products
            wizard.available_product_ids = products

    @api.depends('selection_line_ids.quantity', 'selection_line_ids.unit_price')
    def _compute_totals(self):
        """Calculer les totaux de la sélection"""
        for wizard in self:
            total = 0.0
            count = 0
            for line in wizard.selection_line_ids:
                if line.quantity > 0:
                    total += line.quantity * (line.unit_price if hasattr(line, 'unit_price') else 0)
                    count += 1
            wizard.total_selection = total
            wizard.selection_count = count

    @api.depends('available_product_ids', 'page_size')
    def _compute_pagination(self):
        """Calculer la pagination"""
        for wizard in self:
            wizard.total_products = len(wizard.available_product_ids)
            if wizard.page_size > 0:
                wizard.total_pages = max(1, (wizard.total_products + wizard.page_size - 1) // wizard.page_size)
            else:
                wizard.total_pages = 1

    @api.depends('lot_id')
    def _compute_lot_type_id(self):
        """Calculer le type de lot de manière sécurisée"""
        for wizard in self:
            wizard.lot_type_id = False

    def action_add_selected_products(self):
        """Rediriger vers le wizard moderne"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Ajouter des produits',
            'res_model': 'construction.product.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sale_order_id': self.order_id.id,
            }
        }


class BlgProductSelectionLineCompatibility(models.TransientModel):
    """Ligne de sélection de produit BLG"""
    
    _name = 'blg.product.selection.line'
    _description = 'Ligne de sélection de produit (compatibilité BLG)'

    wizard_id = fields.Many2one('blg.product.selection.wizard', string='Wizard')
    product_id = fields.Many2one('product.product', string='Produit', required=True)
    quantity = fields.Float('Quantité', default=1.0)
    selected = fields.Boolean('Sélectionné', default=False)
    
    # Champs supplémentaires
    sequence = fields.Integer('Séquence', default=10)
    unit_price = fields.Float('Prix unitaire', related='product_id.list_price', readonly=True)
    subtotal = fields.Float('Sous-total', compute='_compute_subtotal', store=True)
    description = fields.Text('Description personnalisée')
    
    # Localisation
    room_type = fields.Selection([
        ('salon', 'Salon'),
        ('cuisine', 'Cuisine'),
        ('chambre', 'Chambre'),
        ('salle_bain', 'Salle de bain'),
        ('autre', 'Autre'),
    ], string='Type de salle')
    room_number = fields.Char('Numéro/Nom de salle')
    
    @api.depends('quantity', 'unit_price')
    def _compute_subtotal(self):
        """Calculer le sous-total"""
        for line in self:
            line.subtotal = line.quantity * line.unit_price


# ================== AUTRES WIZARDS DE COMPATIBILITÉ ==================

class BlgCreateQuoteWizardCompatibility(models.TransientModel):
    """Wizard de compatibilité pour la création de devis BLG"""
    
    _name = 'blg.create.quote.wizard'
    _description = 'Création de devis (compatibilité BLG)'

    chantier_id = fields.Many2one('chantier', string='Chantier', required=True)
    partner_id = fields.Many2one('res.partner', string='Client', required=True)
    lot_ids = fields.Many2many(
        'lot.category', 
        'blg_create_quote_wizard_lot_rel', 
        'wizard_id', 
        'lot_id',
        string='Lots sélectionnés'
    )
    
    def action_create_quote(self):
        """Rediriger vers le système moderne"""
        quote = self.env['sale.order'].create({
            'partner_id': self.partner_id.id,
            'blg_chantier_id': self.chantier_id.id,
            'lot_selection_ids': [(6, 0, self.lot_ids.ids)],
        })
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Devis créé',
            'res_model': 'sale.order',
            'res_id': quote.id,
            'view_mode': 'form',
            'target': 'current',
        }


class BlgLotNavigationWizardCompatibility(models.TransientModel):
    """Wizard de compatibilité pour la navigation entre lots BLG"""
    
    _name = 'blg.lot.navigation.wizard'
    _description = 'Navigation entre lots (compatibilité BLG)'

    order_id = fields.Many2one('sale.order', string='Commande', required=True)
    current_lot_id = fields.Many2one('lot.category', string='Lot actuel', required=True)
    
    def action_next_lot(self):
        """Rediriger vers le système moderne"""
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': self.order_id.id,
            'view_mode': 'form',
            'target': 'current',
        } 