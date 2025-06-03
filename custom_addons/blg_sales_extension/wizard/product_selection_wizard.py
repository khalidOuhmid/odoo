# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class BlgProductSelectionWizard(models.TransientModel):
    """
    Assistant de sélection de produits pour un lot spécifique - Interface moderne Odoo 18
    """
    _name = 'blg.product.selection.wizard'
    _description = 'Assistant de Sélection de Produits'

    # Relations
    lot_id = fields.Many2one('blg_contacts_extension.lot', string='Lot', required=True)
    order_id = fields.Many2one('sale.order', string='Commande', required=True)
    
    # Recherche et filtrage moderne
    search_term = fields.Char('Rechercher un produit', placeholder="Tapez le nom, référence ou description...")
    category_filter = fields.Many2one('product.category', string='Catégorie')
    price_min = fields.Float('Prix minimum', default=0.0)
    price_max = fields.Float('Prix maximum', default=999999.0)
    show_all_products = fields.Boolean('Afficher tous les produits', default=False)
    show_stock = fields.Boolean('Afficher le stock', default=True)
    
    # Tri et affichage
    sort_by = fields.Selection([
        ('name', 'Nom'),
        ('default_code', 'Référence'),
        ('list_price', 'Prix croissant'),
        ('list_price desc', 'Prix décroissant'),
        ('categ_id', 'Catégorie'),
    ], string='Trier par', default='name')
    
    view_mode = fields.Selection([
        ('list', 'Liste'),
        ('kanban', 'Cartes'),
    ], string='Mode d\'affichage', default='list')
    
    # Produits et sélection
    available_product_ids = fields.Many2many(
        'product.product',
        compute='_compute_available_products',
        string='Produits disponibles'
    )
    
    filtered_product_ids = fields.Many2many(
        'product.product',
        compute='_compute_filtered_products',
        string='Produits filtrés et paginés'
    )
    
    selection_line_ids = fields.One2many(
        'blg.product.selection.line',
        'wizard_id',
        string='Produits sélectionnés'
    )
    
    # Calculs et statistiques
    total_selection = fields.Monetary('Total sélection', compute='_compute_totals', currency_field='currency_id')
    selection_count = fields.Integer('Nombre d\'articles', compute='_compute_totals')
    total_quantity = fields.Float('Quantité totale', compute='_compute_totals')
    currency_id = fields.Many2one('res.currency', related='order_id.currency_id')
    
    # Pagination moderne
    page_size = fields.Integer('Produits par page', default=12)
    current_page = fields.Integer('Page actuelle', default=1)
    total_pages = fields.Integer('Nombre de pages', compute='_compute_pagination')
    total_products = fields.Integer('Total produits', compute='_compute_pagination')
    
    # Description personnalisée pour l'ensemble
    custom_description = fields.Html('Description personnalisée', placeholder="Ajoutez des notes spécifiques pour cette sélection...")

    @api.depends('search_term', 'category_filter', 'price_min', 'price_max', 'show_all_products', 'lot_id', 'sort_by')
    def _compute_available_products(self):
        """Calculer les produits disponibles selon les filtres avancés"""
        for wizard in self:
            domain = [('sale_ok', '=', True), ('active', '=', True)]
            
            # Filtre par recherche étendue
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
            if wizard.category_filter:
                domain.append(('categ_id', 'child_of', wizard.category_filter.id))
            
            # Filtre par prix
            if wizard.price_min > 0:
                domain.append(('list_price', '>=', wizard.price_min))
            if wizard.price_max < 999999:
                domain.append(('list_price', '<=', wizard.price_max))
            
            # Filtre par lot si pas "tous les produits"
            if not wizard.show_all_products and wizard.lot_id:
                if wizard.lot_id.type_id and wizard.lot_id.type_id.product_ids:
                    lot_product_ids = wizard.lot_id.type_id.product_ids.filtered(
                        lambda p: p.sale_ok and p.active
                    ).ids
                    if lot_product_ids:
                        domain.append(('id', 'in', lot_product_ids))
            
            # Définir l'ordre de tri
            order = 'name'
            if wizard.sort_by:
                if 'desc' in wizard.sort_by:
                    order = wizard.sort_by.replace(' desc', '') + ' desc'
                else:
                    order = wizard.sort_by
            
            wizard.available_product_ids = self.env['product.product'].search(domain, order=order)

    @api.depends('available_product_ids', 'current_page', 'page_size')
    def _compute_filtered_products(self):
        """Calculer la pagination des produits"""
        for wizard in self:
            if wizard.available_product_ids and wizard.page_size > 0:
                start_index = (wizard.current_page - 1) * wizard.page_size
                end_index = start_index + wizard.page_size
                wizard.filtered_product_ids = wizard.available_product_ids[start_index:end_index]
            else:
                wizard.filtered_product_ids = wizard.available_product_ids

    @api.depends('selection_line_ids.quantity', 'selection_line_ids.unit_price')
    def _compute_totals(self):
        """Calculer les totaux de la sélection"""
        for wizard in self:
            total = 0.0
            count = 0
            qty = 0.0
            for line in wizard.selection_line_ids:
                if line.quantity > 0:
                    total += line.subtotal
                    count += 1
                    qty += line.quantity
            wizard.total_selection = total
            wizard.selection_count = count
            wizard.total_quantity = qty

    @api.depends('available_product_ids', 'page_size')
    def _compute_pagination(self):
        """Calculer la pagination"""
        for wizard in self:
            wizard.total_products = len(wizard.available_product_ids)
            if wizard.page_size > 0:
                wizard.total_pages = max(1, (wizard.total_products + wizard.page_size - 1) // wizard.page_size)
            else:
                wizard.total_pages = 1

    def action_search_products(self):
        """Rechercher des produits - reset pagination"""
        self.current_page = 1
        return self._reload_view()

    def action_clear_filters(self):
        """Vider tous les filtres"""
        self.search_term = False
        self.category_filter = False
        self.price_min = 0.0
        self.price_max = 999999.0
        self.current_page = 1
        return self._reload_view()

    def action_next_page(self):
        """Page suivante"""
        if self.current_page < self.total_pages:
            self.current_page += 1
        return self._reload_view()

    def action_prev_page(self):
        """Page précédente"""
        if self.current_page > 1:
            self.current_page -= 1
        return self._reload_view()

    def action_goto_page(self, page):
        """Aller à une page spécifique"""
        if 1 <= page <= self.total_pages:
            self.current_page = page
        return self._reload_view()

    def _reload_view(self):
        """Recharger la vue avec les nouveaux filtres"""
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }

    def action_add_product_to_selection(self):
        """Ajouter un produit à la sélection - appelé depuis les boutons produit"""
        product_id = self.env.context.get('product_id')
        if not product_id:
            return
            
        existing_line = self.selection_line_ids.filtered(lambda l: l.product_id.id == product_id)
        
        if existing_line:
            existing_line.quantity += 1
        else:
            product = self.env['product.product'].browse(product_id)
            self.env['blg.product.selection.line'].create({
                'wizard_id': self.id,
                'product_id': product_id,
                'quantity': 1.0,
                'description': product.name,
            })
        
        return self._reload_view()

    def action_quick_add_multiple(self):
        """Ajout rapide de plusieurs produits en une fois"""
        product_ids = self.env.context.get('product_ids', [])
        for product_id in product_ids:
            existing_line = self.selection_line_ids.filtered(lambda l: l.product_id.id == product_id)
            if not existing_line:
                self.env['blg.product.selection.line'].create({
                    'wizard_id': self.id,
                    'product_id': product_id,
                    'quantity': 1.0,
                })
        return self._reload_view()

    def action_clear_selection(self):
        """Vider toute la sélection"""
        self.selection_line_ids.unlink()
        return self._reload_view()

    def action_create_quick_product(self):
        """Créer rapidement un nouveau produit"""
        return {
            'name': f'Nouveau produit - {self.lot_id.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'blg.quick.product.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_lot_id': self.lot_id.id,
                'default_order_id': self.order_id.id,
                'default_name_prefix': f'[{self.lot_id.code or ""}] ',
                'default_return_to_selection': True,
                'default_selection_wizard_id': self.id,
                'default_categ_id': self.category_filter.id if self.category_filter else False,
            }
        }

    def action_import_products_from_template(self):
        """Importer des produits depuis un modèle de lot"""
        if self.lot_id.type_id and self.lot_id.type_id.product_ids:
            for product in self.lot_id.type_id.product_ids:
                existing_line = self.selection_line_ids.filtered(lambda l: l.product_id == product)
                if not existing_line:
                    self.env['blg.product.selection.line'].create({
                        'wizard_id': self.id,
                        'product_id': product.id,
                        'quantity': 1.0,
                    })
        return self._reload_view()

    def action_add_selected_products(self):
        """Ajouter les produits sélectionnés dans la vue liste"""
        # Cette méthode sera appelée depuis les boutons de la vue
        # Pour l'instant, on ajoute tous les produits visibles
        return self.action_add_all_visible()

    def action_add_all_visible(self):
        """Ajouter tous les produits visibles à la sélection"""
        for product in self.filtered_product_ids:
            existing_line = self.selection_line_ids.filtered(lambda l: l.product_id.id == product.id)
            if not existing_line:
                self.env['blg.product.selection.line'].create({
                    'wizard_id': self.id,
                    'product_id': product.id,
                    'quantity': 1.0,
                    'description': product.name,
                })
        return self._reload_view()

    def action_confirm_selection(self):
        """Confirmer la sélection et ajouter au devis"""
        if not self.selection_line_ids.filtered(lambda l: l.quantity > 0):
            raise ValidationError(_("Veuillez sélectionner au moins un produit"))

        # Trouver ou créer la section pour ce lot
        section_line = self.order_id.order_line.filtered(
            lambda l: l.display_type == 'line_section' and self.lot_id.name in (l.name or '')
        )

        if not section_line:
            section_vals = {
                'order_id': self.order_id.id,
                'display_type': 'line_section',
                'name': f"📋 {self.lot_id.name} ({self.lot_id.code or ''})",
                'sequence': len(self.order_id.order_line) * 10,
            }
            section_line = self.env['sale.order.line'].create(section_vals)

        # Obtenir la séquence après la section
        sequence = section_line.sequence + 1

        # Ajouter les produits sélectionnés
        lines_added = 0
        for line in self.selection_line_ids.filtered(lambda l: l.quantity > 0):
            product_name = f"[{self.lot_id.code or ''}] {line.product_id.name}"
            
            # Ajouter info localisation si spécifiée
            room_info = ""
            if line.room_type:
                room_display = dict(line._fields['room_type'].selection).get(line.room_type, line.room_type)
                room_info = f" - {room_display}"
                if line.room_number:
                    room_info += f" {line.room_number}"

            line_vals = {
                'order_id': self.order_id.id,
                'product_id': line.product_id.id,
                'name': product_name + room_info,
                'product_uom_qty': line.quantity,
                'price_unit': line.unit_price,
                'sequence': sequence,
            }

            # Ajouter description personnalisée si fournie
            if line.description and line.description != line.product_id.name:
                line_vals['name'] += f"\n{line.description}"

            self.env['sale.order.line'].create(line_vals)
            sequence += 1
            lines_added += 1

        # Ajouter note personnalisée si fournie
        if self.custom_description:
            note_vals = {
                'order_id': self.order_id.id,
                'display_type': 'line_note',
                'name': self.custom_description,
                'sequence': sequence,
            }
            self.env['sale.order.line'].create(note_vals)

        return {
            'type': 'ir.actions.act_window_close',
            'infos': {
                'title': _('Produits ajoutés avec succès'),
                'message': _('%d produits ont été ajoutés au devis pour le lot %s') % (lines_added, self.lot_id.name)
            }
        }


class BlgProductSelectionLine(models.TransientModel):
    """
    Ligne de sélection de produit avec fonctionnalités étendues
    """
    _name = 'blg.product.selection.line'
    _description = 'Ligne de Sélection de Produit'
    _order = 'sequence, product_id'

    wizard_id = fields.Many2one('blg.product.selection.wizard', required=True, ondelete='cascade')
    sequence = fields.Integer('Séquence', default=10)
    product_id = fields.Many2one('product.product', string='Produit', required=True)
    quantity = fields.Float('Quantité', default=1.0, digits='Product Unit of Measure', required=True)
    
    # Localisation étendue
    room_type = fields.Selection([
        ('salon', 'Salon'),
        ('sejour', 'Séjour'),
        ('cuisine', 'Cuisine'),
        ('chambre', 'Chambre'),
        ('chambre_parents', 'Chambre parents'),
        ('chambre_enfant', 'Chambre enfant'),
        ('salle_bain', 'Salle de bain'),
        ('salle_eau', 'Salle d\'eau'),
        ('wc', 'WC'),
        ('wc_suspendu', 'WC suspendu'),
        ('entree', 'Entrée'),
        ('hall', 'Hall'),
        ('couloir', 'Couloir'),
        ('dressing', 'Dressing'),
        ('bureau', 'Bureau'),
        ('bibliotheque', 'Bibliothèque'),
        ('cave', 'Cave'),
        ('garage', 'Garage'),
        ('grenier', 'Grenier'),
        ('combles', 'Combles'),
        ('terrasse', 'Terrasse'),
        ('balcon', 'Balcon'),
        ('jardin', 'Jardin'),
        ('escalier', 'Escalier'),
        ('palier', 'Palier'),
        ('buanderie', 'Buanderie'),
        ('cellier', 'Cellier'),
        ('autre', 'Autre'),
    ], string='Type de salle')
    
    room_number = fields.Char('Numéro/Nom de salle', size=50, help="Ex: 1, 2, A, B, RDC, R+1...")
    floor_level = fields.Selection([
        ('sous_sol', 'Sous-sol'),
        ('rdc', 'Rez-de-chaussée'),
        ('r1', 'R+1'),
        ('r2', 'R+2'),
        ('r3', 'R+3'),
        ('combles', 'Combles'),
    ], string='Niveau')
    
    description = fields.Text('Description personnalisée')
    notes = fields.Text('Notes techniques')
    
    # Calculs
    unit_price = fields.Float('Prix unitaire', related='product_id.list_price', readonly=True)
    subtotal = fields.Float('Sous-total', compute='_compute_subtotal', store=True)
    
    # Informations produit pour affichage
    product_code = fields.Char('Référence', related='product_id.default_code', readonly=True)
    product_category = fields.Char('Catégorie', related='product_id.categ_id.name', readonly=True)

    @api.depends('quantity', 'unit_price')
    def _compute_subtotal(self):
        """Calculer le sous-total de la ligne"""
        for line in self:
            line.subtotal = line.quantity * (line.unit_price or 0.0)

    def action_edit_line(self):
        """Éditer la ligne en détail"""
        return {
            'name': f'Modifier {self.product_id.name}',
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_duplicate_line(self):
        """Dupliquer la ligne"""
        self.copy({'room_number': f"{self.room_number} (copie)" if self.room_number else "Copie"})
        return self.wizard_id._reload_view()

    def action_remove_line(self):
        """Supprimer la ligne"""
        wizard = self.wizard_id
        self.unlink()
        return wizard._reload_view()

    @api.model
    def create(self, vals):
        """Override create pour gérer la séquence automatiquement"""
        if 'sequence' not in vals and 'wizard_id' in vals:
            wizard = self.env['blg.product.selection.wizard'].browse(vals['wizard_id'])
            last_sequence = max(wizard.selection_line_ids.mapped('sequence') or [0])
            vals['sequence'] = last_sequence + 10
        return super().create(vals)
