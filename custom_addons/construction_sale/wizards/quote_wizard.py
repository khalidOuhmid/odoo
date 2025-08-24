# -*- coding: utf-8 -*-
"""
Wizard intelligent pour la création de devis construction
Respecte les standards Odoo 18 et les principes SOLID
"""

import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ConstructionQuoteWizard(models.TransientModel):
    """Assistant intelligent pour la création de devis construction"""
    
    _name = 'construction.quote.wizard'
    _description = 'Assistant de création de devis intelligent'

    # =================== CHAMPS PRINCIPAUX ===================
    
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Devis',
        required=True,
        readonly=True
    )
    
    chantier_id = fields.Many2one(
        'construction.chantier',
        string='Chantier',
        required=True,
        readonly=True
    )
    
    # =================== SÉLECTION DES LOTS ===================
    
    lot_ids = fields.Many2many(
        'construction.lot',
        string='Lots à traiter',
        domain="[('id', 'in', available_lot_ids if available_lot_ids else [0])]",
        help="Sélectionnez les lots du chantier pour lesquels créer des lignes de devis"
    )
    
    available_lot_ids = fields.Many2many(
        'construction.lot',
        compute='_compute_available_lots',
        string='Lots disponibles'
    )

    # =================== RECHERCHE ET FILTRES ===================
    
    search_term = fields.Char(
        string='Rechercher un produit',
        placeholder="Nom, référence, description..."
    )
    
    category_filter_id = fields.Many2one(
        'product.category',
        string='Filtrer par catégorie'
    )
    
    show_lot_products_only = fields.Boolean(
        string='Produits spécifiques aux lots',
        default=True,
        help="Afficher uniquement les produits liés aux lots sélectionnés"
    )
    
    default_margin_percent = fields.Float(
        string='Marge par défaut (%)',
        default=50.0,
        help="Marge commerciale par défaut à appliquer aux nouveaux produits"
    )

    # =================== PRODUITS ===================
    
    available_product_ids = fields.Many2many(
        'product.product',
        compute='_compute_available_products',
        string='Produits disponibles'
    )
    
    selected_line_ids = fields.One2many(
        'construction.quote.line',
        'wizard_id',
        string='Lignes sélectionnées'
    )

    # =================== STATISTIQUES ===================
    
    total_amount = fields.Monetary(
        string='Montant total',
        compute='_compute_totals',
        currency_field='currency_id'
    )
    
    total_quantity = fields.Float(
        string='Quantité totale',
        compute='_compute_totals'
    )
    
    line_count = fields.Integer(
        string='Nombre de lignes',
        compute='_compute_totals'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        compute='_compute_currency',
        readonly=True
    )

    # =================== MÉTHODES CALCULÉES ===================

    @api.depends('sale_order_id.currency_id')
    def _compute_currency(self):
        """Calcule la devise du wizard depuis le devis"""
        for wizard in self:
            if wizard.sale_order_id and wizard.sale_order_id.currency_id:
                wizard.currency_id = wizard.sale_order_id.currency_id
            else:
                # Valeur par défaut : devise de la société
                wizard.currency_id = self.env.company.currency_id

    @api.model
    def default_get(self, fields_list):
        """Initialiser les valeurs par défaut du wizard"""
        res = super().default_get(fields_list)
        
        # Si des lot_ids sont passés dans le contexte, les utiliser
        if 'lot_ids' in fields_list and self.env.context.get('default_lot_ids'):
            res['lot_ids'] = self.env.context['default_lot_ids']
        
        return res

    @api.depends('chantier_id.lots_ids')
    def _compute_available_lots(self):
        """Calcule les lots disponibles depuis le chantier uniquement"""
        for wizard in self:
            # Les lots disponibles sont UNIQUEMENT ceux du chantier
            if wizard.chantier_id and wizard.chantier_id.lots_ids:
                wizard.available_lot_ids = wizard.chantier_id.lots_ids
            else:
                # Aucun lot disponible si pas de chantier ou pas de lots
                wizard.available_lot_ids = self.env['construction.lot']

    @api.depends('search_term', 'category_filter_id', 'lot_ids', 'show_lot_products_only')
    def _compute_available_products(self):
        """Calcule les produits disponibles selon les filtres"""
        for wizard in self:
            domain = [
                ('sale_ok', '=', True),
                ('active', '=', True)
            ]
            
            # Filtre par recherche textuelle
            if wizard.search_term:
                search_domain = [
                    '|', '|', '|',
                    ('name', 'ilike', wizard.search_term),
                    ('default_code', 'ilike', wizard.search_term),
                    ('description_sale', 'ilike', wizard.search_term),
                    ('barcode', 'ilike', wizard.search_term)
                ]
                domain.extend(search_domain)
            
            # Filtre par catégorie
            if wizard.category_filter_id:
                domain.append(('categ_id', 'child_of', wizard.category_filter_id.id))
            
            # Filtre par lots (si produits avec relation aux lots)
            if wizard.show_lot_products_only and wizard.lot_ids:
                # Vérifier si le modèle product.product a une relation avec les lots
                if hasattr(self.env['product.product'], 'lot_ids'):
                    domain.append(('lot_ids', 'in', wizard.lot_ids.ids))
                elif wizard.category_filter_id:
                    # Utiliser la catégorie comme filtre indirect
                    pass
            
            # Rechercher les produits avec limite pour éviter la surcharge
            products = self.env['product.product'].search(
                domain, 
                limit=100, 
                order='name'
            )
            
            wizard.available_product_ids = products

    @api.depends('selected_line_ids.quantity', 'selected_line_ids.price_unit')
    def _compute_totals(self):
        """Calcule les totaux de la sélection"""
        for wizard in self:
            lines = wizard.selected_line_ids.filtered('quantity') if wizard.selected_line_ids else self.env['construction.quote.line']
            
            # Calcul sécurisé du montant total
            wizard.total_amount = sum(
                (line.quantity or 0.0) * (line.price_unit or 0.0) for line in lines
            ) if lines else 0.0
            
            # Calcul sécurisé de la quantité totale
            wizard.total_quantity = sum(
                line.quantity or 0.0 for line in lines
            ) if lines else 0.0
            
            # Calcul du nombre de lignes
            wizard.line_count = len(lines) if lines else 0

    # =================== ACTIONS ===================

    def action_add_product(self):
        """Ouvrir le popup simple d'ajout de produit"""
        product_id = self.env.context.get('product_id')
        if not product_id:
            return self._reload_wizard()
        
        # Vérifier qu'au moins un lot est sélectionné
        if not self.lot_ids:
            raise ValidationError(_(
                "Veuillez d'abord sélectionner au moins un lot "
                "avant d'ajouter des produits."
            ))
        
        # Créer le popup de dialogue
        dialog = self.env['construction.product.dialog'].create({
            'quote_wizard_id': self.id,
            'product_id': product_id,
            'margin_percent': self.default_margin_percent,
        })
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Ajouter : %s') % dialog.product_name,
            'res_model': 'construction.product.dialog',
            'res_id': dialog.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_create_quick_product(self):
        """Ouvrir le popup de création rapide de produit"""
        # Obtenir la catégorie par défaut ou une catégorie construction
        default_category = self.category_filter_id
        if not default_category:
            # Chercher une catégorie "construction" ou similaire
            default_category = self.env['product.category'].search([
                '|', 
                ('name', 'ilike', 'construction'),
                ('name', 'ilike', 'matériau')
            ], limit=1)
            if not default_category:
                # Prendre la première catégorie disponible
                default_category = self.env['product.category'].search([], limit=1)
        
        # Créer le popup de création de produit
        dialog = self.env['construction.product.creator'].create({
            'quote_wizard_id': self.id,
            'categ_id': default_category.id if default_category else False,
            'lot_ids': [(6, 0, self.lot_ids.ids)] if self.lot_ids else False,
            'name': '',  # Valeur par défaut vide mais explicite
        })
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Créer un nouveau produit personnalisé'),
            'res_model': 'construction.product.creator',
            'res_id': dialog.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_confirm_selection(self):
        """Confirmer et ajouter les produits au devis"""
        if not self.selected_line_ids.filtered('quantity'):
            raise ValidationError(_("Veuillez sélectionner au moins un produit."))
        
        # Si aucun lot n'est sélectionné, utiliser tous les lots du chantier
        if not self.lot_ids:
            self.lot_ids = self.chantier_id.lots_ids
        
        self._add_products_to_order()
        
        # Mettre à jour les lots du devis avec ceux traités
        if self.lot_ids:
            self.sale_order_id.write({
                'lot_ids': [(6, 0, self.lot_ids.ids)]
            })
        
        # Vider la sélection pour permettre d'ajouter d'autres produits
        self.selected_line_ids.unlink()
        
        # Retourner sur l'instance du wizard pour continuer la progression
        return {
            'type': 'ir.actions.act_window',
            'name': _('Assistant de création de devis - %s') % self.chantier_id.name,
            'res_model': 'construction.quote.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_chantier_id': self.chantier_id.id,
                'default_sale_order_id': self.sale_order_id.id,
            }
        }

    def action_finalize_quote(self):
        """Finaliser le devis et retourner au devis"""
        # Ajouter les produits sélectionnés s'il y en a
        if self.selected_line_ids.filtered('quantity'):
            self.action_confirm_selection()
        
        # Retourner vers le devis créé pour voir le résultat final
        return {
            'type': 'ir.actions.act_window',
            'name': _('Devis %s') % self.sale_order_id.name,
            'res_model': 'sale.order',
            'res_id': self.sale_order_id.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_chantier_id': self.chantier_id.id,
                'form_view_initial_mode': 'edit',
            }
        }

    def action_view_selection(self):
        """Afficher la sélection dans un popup"""
        if not self.selected_line_ids:
            raise ValidationError(_("Aucun produit sélectionné à afficher."))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Ma sélection - %s') % self.chantier_id.name,
            'res_model': 'construction.quote.line',
            'view_mode': 'list,form',
            'domain': [('wizard_id', '=', self.id)],
            'target': 'new',
            'context': {
                'default_wizard_id': self.id,
            }
        }

    def action_clear_selection(self):
        """Vider la sélection"""
        self.selected_line_ids.unlink()
        return self._reload_wizard()

    def action_refresh_products(self):
        """Actualiser la liste des produits"""
        self._compute_available_products()
        return self._reload_wizard()

    # =================== MÉTHODES PRIVÉES ===================

    def _add_products_to_order(self):
        """Ajoute les produits sélectionnés au devis organisés par lots"""
        # Tous les produits sont maintenant obligatoirement assignés à un lot
        # donc on organise TOUJOURS par lots
        self._add_products_by_lots()

    def _add_products_by_lots(self):
        """Ajouter les produits organisés par sections de lots sans dupliquer les sections existantes"""
        order = self.sale_order_id
        SaleOrderLine = self.env['sale.order.line']
        
        lots_with_products = self.selected_line_ids.mapped('lot_id')
        for lot in self.lot_ids:
            if lot in lots_with_products:
                lot_lines = self.selected_line_ids.filtered(lambda l: l.lot_id == lot)
                # Chercher la section existante pour ce lot
                section_line = order.order_line.filtered(lambda l: l.display_type == 'line_section' and l.name.strip() == f"📋 {lot.name}")
                if section_line:
                    section = section_line[0]
                    # Trouver la séquence max des lignes de ce lot après la section
                    section_seq = section.sequence
                    # On place les produits juste après la dernière ligne du lot (ou la section si aucune)
                    # On récupère toutes les lignes (produits) de ce lot après la section
                    lot_product_lines = order.order_line.filtered(lambda l: l.lot_id == lot and not l.display_type and l.sequence > section_seq)
                    if lot_product_lines:
                        next_seq = max(lot_product_lines.mapped('sequence')) + 10
                    else:
                        next_seq = section_seq + 10
                else:
                    # Créer la section si elle n'existe pas
                    section = self._create_lot_section(lot, self._get_next_sequence())
                    next_seq = section.sequence + 10 if hasattr(section, 'sequence') else self._get_next_sequence() + 10
                # Ajouter les produits de ce lot triés par nom
                sorted_lines = sorted(lot_lines, key=lambda l: l.product_id.name or '')
                for line in sorted_lines:
                    self._create_order_line(line, next_seq)
                    next_seq += 10

    def _add_products_simple(self):
        """Ajouter les produits sans organisation par lots"""
        sequence = self._get_next_sequence()
        
        for line in self.selected_line_ids.filtered('quantity'):
            self._create_order_line(line, sequence)
            sequence += 10

    def _create_lot_section(self, lot, sequence):
        """Crée une section pour un lot et retourne la ligne créée"""
        return self.env['sale.order.line'].create({
            'order_id': self.sale_order_id.id,
            'display_type': 'line_section',
            'name': f"📋 {lot.name}",
            'sequence': sequence,
        })

    def _create_order_line(self, quote_line, sequence):
        """Crée une ligne de commande à partir d'une ligne du wizard"""
        values = {
            'order_id': self.sale_order_id.id,
            'product_id': quote_line.product_id.id,
            'product_uom_qty': quote_line.quantity,
            'price_unit': quote_line.price_unit,
            'sequence': sequence,
        }
        
        # Ajouter le lot de construction
        if quote_line.lot_id:
            values['lot_id'] = quote_line.lot_id.id
        
        # Ajouter les informations de localisation
        if quote_line.room_location:
            values['room_location'] = quote_line.room_location
        if quote_line.room_number:
            # Combiner numéro de salle et localisation
            room_info = f"[{quote_line.room_number}]"
            if quote_line.room_location:
                room_info += f" {quote_line.room_location}"
            values['room_location'] = room_info
        if quote_line.floor_level:
            values['floor_level'] = quote_line.floor_level
        if quote_line.construction_notes:
            values['construction_notes'] = quote_line.construction_notes
        
        # Personnaliser le nom du produit avec les informations de localisation
        product_name = quote_line.product_id.name
        name_parts = [product_name]
        
        if quote_line.room_number or quote_line.room_location:
            location_info = []
            if quote_line.room_location:
                location_info.append(quote_line.room_location)
            if quote_line.room_number:
                location_info.append(f"Salle {quote_line.room_number}")
            name_parts.append(f"({' - '.join(location_info)})")
        
        if quote_line.construction_notes:
            name_parts.append(f"\nNotes: {quote_line.construction_notes}")
        
        values['name'] = ' '.join(name_parts)
        
        self.env['sale.order.line'].create(values)

    def _get_next_sequence(self):
        """Retourne la prochaine séquence disponible dans le devis"""
        last_line = self.sale_order_id.order_line.sorted('sequence', reverse=True)
        return (last_line[0].sequence + 10) if last_line else 10

    def unlink(self):
        """Suppression sécurisée du wizard avec nettoyage des enregistrements liés"""
        # Supprimer toutes les lignes liées avant de supprimer le wizard
        for wizard in self:
            if wizard.selected_line_ids:
                wizard.selected_line_ids.unlink()
        
        # Supprimer le wizard lui-même
        return super().unlink()

    def _reload_wizard(self):
        """Recharge le wizard"""
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }


class ProductAddDialog(models.TransientModel):
    """Popup simple pour ajouter un produit"""
    
    _name = 'construction.product.dialog'
    _description = 'Popup d\'ajout de produit'

    # =================== CHAMPS PRINCIPAUX ===================
    
    quote_wizard_id = fields.Many2one(
        'construction.quote.wizard',
        required=True,
        ondelete='cascade'
    )
    
    product_id = fields.Many2one(
        'product.product',
        string='Produit',
        required=True,
        readonly=True
    )
    
    product_name = fields.Char(
        related='product_id.display_name',
        readonly=True
    )
    
    base_price = fields.Float(
        related='product_id.standard_price',
        readonly=True
    )

    # =================== CHAMPS D'AJOUT ===================
    
    quantity = fields.Float(
        string='Quantité',
        default=1.0,
        required=True
    )
    
    margin_percent = fields.Float(
        string='Marge (%)',
        default=20.0,
        help="Marge commerciale à appliquer"
    )
    
    unit_price = fields.Float(
        string='Prix unitaire final',
        compute='_compute_unit_price'
    )
    
    total_price = fields.Float(
        string='Total',
        compute='_compute_total_price'
    )
    
    room_number = fields.Char(
        string='N° Salle',
        placeholder="Ex: S01, C12..."
    )
    
    room_location = fields.Char(
        string='Localisation',
        placeholder="Ex: Salon, Cuisine..."
    )
    
    description = fields.Text(
        string='Description/Notes',
        placeholder="Notes techniques..."
    )
    
    lot_id = fields.Many2one(
        'construction.lot',
        string='Lot',
        required=False,
        help="Lot de construction auquel assigner ce produit"
    )
    
    # Champ pour les lots disponibles
    available_lot_ids = fields.Many2many(
        'construction.lot',
        compute='_compute_available_lots_for_dialog',
        string='Lots disponibles'
    )

    # =================== MÉTHODES CALCULÉES ===================
    
    @api.depends('quote_wizard_id.lot_ids')
    def _compute_available_lots_for_dialog(self):
        """Calcule les lots disponibles depuis le wizard parent"""
        for dialog in self:
            if dialog.quote_wizard_id and dialog.quote_wizard_id.lot_ids:
                dialog.available_lot_ids = dialog.quote_wizard_id.lot_ids
            else:
                dialog.available_lot_ids = self.env['construction.lot']
    
    @api.depends('base_price', 'margin_percent')
    def _compute_unit_price(self):
        """Calcule le prix unitaire final = coût * (1 + marge)."""
        for dialog in self:
            cost = dialog.base_price or 0.0
            margin = dialog.margin_percent or 0.0
            dialog.unit_price = cost * (1 + margin / 100.0)
    
    @api.depends('unit_price', 'quantity')
    def _compute_total_price(self):
        """Calcule le prix total"""
        for dialog in self:
            dialog.total_price = dialog.unit_price * dialog.quantity

    # =================== SURCHARGES ===================
    
    @api.model
    def create(self, vals):
        """Créer le dialog avec initialisation correcte"""
        dialog = super().create(vals)
        
        # S'assurer que les lots disponibles sont calculés
        if dialog.quote_wizard_id:
            dialog._compute_available_lots_for_dialog()
            # Si un seul lot disponible et pas de lot assigné, l'assigner automatiquement
            if len(dialog.available_lot_ids) == 1 and not dialog.lot_id:
                dialog.lot_id = dialog.available_lot_ids[0]
        
        return dialog
    
    # =================== ACTIONS ===================
    
    def action_confirm_add(self):
        """Confirmer l'ajout du produit"""
        if self.quantity <= 0:
            raise ValidationError(_("La quantité doit être positive."))
        
        if not self.lot_id:
            raise ValidationError(_("Veuillez sélectionner un lot pour ce produit."))
        
        # Créer la ligne dans le wizard principal
        line_vals = {
            'wizard_id': self.quote_wizard_id.id,
            'product_id': self.product_id.id,
            'quantity': self.quantity,
            'price_unit': self.unit_price,
            'lot_id': self.lot_id.id,
            'room_number': self.room_number,
            'room_location': self.room_location,
            'construction_notes': self.description,
            'margin_percent': self.margin_percent,
        }
        
        self.env['construction.quote.line'].create(line_vals)
        
        # Retourner vers le wizard avec le produit ajouté
        return {
            'type': 'ir.actions.act_window',
            'name': _('Assistant de création de devis - %s') % self.quote_wizard_id.chantier_id.name,
            'res_model': 'construction.quote.wizard',
            'res_id': self.quote_wizard_id.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_cancel(self):
        """Annuler l'ajout et retourner au wizard principal"""
        # Retourner à la même instance du wizard principal (popup)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Assistant de création de devis - %s') % self.quote_wizard_id.chantier_id.name,
            'res_model': 'construction.quote.wizard',
            'res_id': self.quote_wizard_id.id,
            'view_mode': 'form',
            'target': 'new',
        }


class ConstructionQuoteLine(models.TransientModel):
    """Ligne de produit dans le wizard de devis"""
    
    _name = 'construction.quote.line'
    _description = 'Ligne de produit pour devis construction'
    _order = 'sequence, id'

    # =================== RELATIONS ===================
    
    wizard_id = fields.Many2one(
        'construction.quote.wizard',
        required=True,
        ondelete='cascade'
    )
    
    product_id = fields.Many2one(
        'product.product',
        string='Produit',
        required=True
    )
    
    lot_id = fields.Many2one(
        'construction.lot',
        string='Lot',
        required=True,
        help="Lot de construction auquel ce produit est assigné"
    )

    # =================== QUANTITÉS ET PRIX ===================
    
    sequence = fields.Integer(
        string='Séquence',
        default=10
    )
    
    quantity = fields.Float(
        string='Quantité',
        default=1.0,
        required=True
    )
    
    price_unit = fields.Float(
        string='Prix unitaire',
        default=0.0
    )
    
    subtotal = fields.Float(
        string='Sous-total',
        compute='_compute_subtotal'
    )

    # =================== INFORMATIONS PRODUIT ===================
    
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

    # =================== LOCALISATION (OPTIONNELLE) ===================
    
    room_number = fields.Char(
        string='N° Salle',
        placeholder="Ex: S01, C12..."
    )
    
    room_location = fields.Char(
        string='Localisation',
        placeholder="Ex: Salon, Cuisine..."
    )
    
    floor_level = fields.Selection([
        ('basement', 'Sous-sol'),
        ('ground', 'Rez-de-chaussée'),
        ('floor_1', 'Étage 1'),
        ('floor_2', 'Étage 2'),
        ('floor_3', 'Étage 3'),
        ('floor_4', 'Étage 4'),
        ('attic', 'Combles'),
        ('other', 'Autre'),
    ], string='Niveau')
    
    construction_notes = fields.Text(
        string='Notes',
        placeholder="Notes techniques..."
    )
    
    # =================== TARIFICATION ===================
    
    margin_percent = fields.Float(
        string='Marge (%)',
        default=0.0,
        help="Marge appliquée sur ce produit"
    )

    # =================== MÉTHODES CALCULÉES ===================

    @api.depends('quantity', 'price_unit')
    def _compute_subtotal(self):
        """Calcule le sous-total de la ligne"""
        for line in self:
            line.subtotal = (line.quantity or 0.0) * (line.price_unit or 0.0)

    # =================== ACTIONS ===================

    def action_remove_line(self):
        """Supprimer cette ligne"""
        wizard = self.wizard_id
        self.unlink()
        return wizard._reload_wizard()


class ProductCreator(models.TransientModel):
    """Popup pour créer rapidement un nouveau produit"""
    
    _name = 'construction.product.creator'
    _description = 'Créateur de produit rapide'

    # =================== CHAMPS PRINCIPAUX ===================
    
    quote_wizard_id = fields.Many2one(
        'construction.quote.wizard',
        required=True,
        ondelete='cascade'
    )
    
    name = fields.Char(
        string='Nom du produit',
        required=False,
        placeholder="Ex: Peinture satinée blanche..."
    )
    
    default_code = fields.Char(
        string='Référence',
        placeholder="Ex: PEIN-SAT-BL"
    )
    
    categ_id = fields.Many2one(
        'product.category',
        string='Catégorie',
        required=False,
        default=lambda self: self._get_default_category_id()
    )
    
    uom_id = fields.Many2one(
        'uom.uom',
        string='Unité de mesure',
        required=False,
        default=lambda self: self._get_default_uom_id(),
        domain="[('category_id.name', 'in', ['Unit', 'Surface', 'Length / Distance', 'Volume', 'Weight', 'Surface BTP', 'Longueur BTP', 'Volume BTP', 'Poids BTP', 'Working Time'])]",
        help="Unité de mesure pour ce produit (m², m, kg, pièce, h, jour, etc.)"
    )
    
    list_price = fields.Float(
        string='Prix de vente',
        default=0.0,
        required=False
    )
    
    standard_price = fields.Float(
        string='Coût',
        default=0.0
    )

    computed_sale_price = fields.Float(
        string='Prix de vente (calculé)',
        compute='_compute_computed_sale_price'
    )
    
    description_sale = fields.Text(
        string='Description',
        placeholder="Description pour les devis et factures..."
    )
    
    lot_ids = fields.Many2many(
        'construction.lot',
        string='Lots associés',
        help="Lots pour lesquels ce produit est utilisé"
    )

    # =================== ACTIONS ===================
    
    def action_create_product(self):
        """Créer le produit et optionnellement l'ajouter au devis"""
        if not self.name:
            raise ValidationError(_("Le nom du produit est obligatoire."))
        
        if not self.categ_id:
            raise ValidationError(_("Veuillez sélectionner une catégorie pour ce produit."))
        
        if not self.uom_id:
            raise ValidationError(_("Veuillez sélectionner une unité de mesure pour ce produit."))
        
        if self.list_price < 0:
            raise ValidationError(_("Le prix de vente doit être positif."))
        
        # Créer le produit
        # Calculer le code produit automatiquement si non renseigné: "<lot>-<index>"
        generated_code = self.default_code
        if not generated_code:
            generated_code = self._generate_default_code_from_lot()

        # Calculer un prix de vente dérivé du coût et de la marge par défaut du wizard si non fourni
        computed_list_price = self.list_price
        if (not computed_list_price or computed_list_price <= 0) and self.standard_price and self.quote_wizard_id:
            default_margin = self.quote_wizard_id.default_margin_percent or 0.0
            computed_list_price = self.standard_price * (1 + default_margin / 100.0)

        product_vals = {
            'name': self.name,
            'default_code': generated_code,
            'categ_id': self.categ_id.id,
            'uom_id': self.uom_id.id,
            'list_price': computed_list_price or 0.0,
            'standard_price': self.standard_price,
            'description_sale': self.description_sale,
            'sale_ok': True,
            'purchase_ok': False,
            'type': 'consu',  # Consommable par défaut
        }
        
        # Ajouter les lots si le modèle product.product supporte cette relation
        if hasattr(self.env['product.product'], 'lot_ids') and self.lot_ids:
            product_vals['lot_ids'] = [(6, 0, self.lot_ids.ids)]
        
        new_product = self.env['product.product'].create(product_vals)
        
        # Actualiser la liste des produits du wizard
        self.quote_wizard_id.action_refresh_products()
        
        # Retourner vers le wizard avec les produits actualisés
        return {
            'type': 'ir.actions.act_window',
            'name': _('Assistant de création de devis - %s') % self.quote_wizard_id.chantier_id.name,
            'res_model': 'construction.quote.wizard',
            'res_id': self.quote_wizard_id.id,
            'view_mode': 'form',
            'target': 'new',
        }
    
    def action_cancel(self):
        """Annuler la création et retourner au wizard principal"""
        # Retourner à la même instance du wizard principal (popup)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Assistant de création de devis - %s') % self.quote_wizard_id.chantier_id.name,
            'res_model': 'construction.quote.wizard',
            'res_id': self.quote_wizard_id.id,
            'view_mode': 'form',
            'target': 'new',
        }

    # =================== CALCULS ===================
    @api.depends('standard_price', 'quote_wizard_id.default_margin_percent')
    def _compute_computed_sale_price(self):
        """Prévisualisation du prix de vente calculé = coût × (1 + marge)."""
        for rec in self:
            margin = rec.quote_wizard_id.default_margin_percent or 0.0
            cost = rec.standard_price or 0.0
            rec.computed_sale_price = cost * (1 + margin / 100.0)

    # =================== OUTILS INTERNES ===================
    def _generate_default_code_from_lot(self):
        """Génère un code produit basé sur le nom du lot sélectionné et un index unique.
        Format: <LOTNAME>-<NNN>
        Si plusieurs lots, utilise le premier. Si aucun lot, retourne None.
        """
        lot = self.lot_ids[:1]
        if not lot:
            # Essayer d'utiliser un lot du wizard parent si unique
            parent_lots = self.quote_wizard_id.lot_ids[:1] if self.quote_wizard_id else self.env['construction.lot']
            lot = parent_lots
        if not lot:
            return None

        def slugify(name):
            # Simplification: majuscules, remplacer espaces par '-', garder alphanum et '-'
            import re
            base = (name or '').upper().strip()
            base = re.sub(r'\s+', '-', base)
            base = re.sub(r'[^A-Z0-9\-]', '', base)
            return base

        prefix = slugify(lot.name)
        # Eviter les préfixes vides
        if not prefix:
            prefix = 'PROD'

        Product = self.env['product.product']
        index = 1
        # Boucle pour trouver un code unique
        while True:
            candidate = f"{prefix}-{index:03d}"
            exists = Product.search_count([('default_code', '=', candidate)])
            if not exists:
                return candidate
            index += 1

    def _get_default_uom_id(self):
        """Retourne l'unité de mesure par défaut pour les produits de construction."""
        # Chercher l'unité de mesure m² BTP par défaut
        default_uom = self.env['uom.uom'].search([
            ('name', '=', 'm²'),
            ('category_id.name', 'in', ['Surface', 'Surface BTP'])
        ], limit=1)
        if default_uom:
            return default_uom.id
        # Sinon, chercher une unité de surface BTP
        surface_uom = self.env['uom.uom'].search([
            ('category_id.name', 'in', ['Surface', 'Surface BTP'])
        ], limit=1)
        if surface_uom:
            return surface_uom[0].id
        # En dernier recours, unité standard
        return self.env['uom.uom'].search([('name', '=', 'Units')], limit=1).id

    def _get_default_category_id(self):
        """Retourne la catégorie par défaut pour les produits de construction."""
        # Chercher la catégorie Construction BTP
        construction_category = self.env['product.category'].search([
            ('name', '=', 'Construction BTP')
        ], limit=1)
        if construction_category:
            return construction_category.id
        # Sinon, chercher une catégorie construction
        construction_category = self.env['product.category'].search([
            ('name', 'ilike', 'construction')
        ], limit=1)
        if construction_category:
            return construction_category.id
        # En dernier recours, première catégorie disponible
        return self.env['product.category'].search([], limit=1).id


