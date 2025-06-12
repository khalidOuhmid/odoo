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
        relation='wizard_available_product_rel',
        column1='wizard_id',
        column2='product_id',
        compute='_compute_available_products',
        string='Produits disponibles'
    )
    
    filtered_product_ids = fields.Many2many(
        'product.product',
        relation='wizard_filtered_product_rel',
        column1='wizard_id',
        column2='product_id',
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

    # Enhanced lot-specific filtering - FIX: Make it safer
    lot_type_id = fields.Many2one('blg.lot.type', string='Type de lot', compute='_compute_lot_type_id', store=False)
    lot_filter_ids = fields.Many2many('blg_contacts_extension.lot', string='Filtrer par lots',
                                     related='order_id.lot_selection_ids')
    
    # Show products specific to selected lot
    show_lot_specific_products = fields.Boolean('Produits spécifiques au lot', default=True,
                                               help="Afficher uniquement les produits recommandés pour ce lot")
    
    # Ajout des champs pour la navigation multi-lots
    chantier_lot_ids = fields.Many2many('blg_contacts_extension.lot', string='Lots du chantier')
    current_lot_index = fields.Integer('Index du lot actuel', default=0)
    has_next_lot = fields.Boolean('A un lot suivant', compute='_compute_lot_navigation')
    has_previous_lot = fields.Boolean('A un lot précédent', compute='_compute_lot_navigation')
    lot_progress = fields.Char('Progression', compute='_compute_lot_navigation')
    
    @api.depends('lot_id')
    def _compute_lot_type_id(self):
        """Compute the lot type from lot_id safely"""
        for wizard in self:
            try:
                # Initialize to False first
                wizard.lot_type_id = False
                
                # Check if lot_id exists and has type_id field
                if wizard.lot_id and wizard.lot_id.id:
                    # Check if the lot model has type_id field
                    if hasattr(wizard.lot_id, 'type_id'):
                        lot_type = wizard.lot_id.type_id
                        # Ensure the type_id is valid before assignment
                        if lot_type and lot_type.id:
                            # Verify the record exists in database
                            existing_type = self.env['blg.lot.type'].browse(lot_type.id).exists()
                            if existing_type:
                                wizard.lot_type_id = existing_type.id
            except Exception as e:
                # Log the error but don't break the flow
                _logger = self.env['ir.logging']._logger
                _logger.warning(f"Error computing lot_type_id for wizard {wizard.id}: {str(e)}")
                wizard.lot_type_id = False
    
    @api.onchange('lot_id', 'show_lot_specific_products')
    def _onchange_lot_filter(self):
        """Update filtering when lot changes"""
        if self.lot_id and self.show_lot_specific_products:
            self.show_all_products = False
        self._compute_available_products()

    @api.depends('search_term', 'category_filter', 'price_min', 'price_max', 
                'show_all_products', 'lot_id', 'sort_by', 'show_lot_specific_products')
    def _compute_available_products(self):
        """Calculate available products with enhanced lot filtering"""
        for wizard in self:
            domain = [('sale_ok', '=', True), ('active', '=', True)]
            
            # Enhanced lot-specific product filtering - SAFER VERSION
            if not wizard.show_all_products and wizard.lot_id and wizard.show_lot_specific_products:
                lot_products = []
                
                try:
                    # Check if lot has type_id and it has products
                    if (hasattr(wizard.lot_id, 'type_id') and 
                        wizard.lot_id.type_id and 
                        hasattr(wizard.lot_id.type_id, 'product_ids')):
                        
                        type_products = wizard.lot_id.type_id.product_ids.filtered(
                            lambda p: p.sale_ok and p.active
                        )
                        if type_products:
                            lot_products.extend(type_products.ids)
                    
                    # Check for tagged products if the field exists
                    if hasattr(self.env['product.product'], 'lot_type_ids'):
                        try:
                            lot_type_id = wizard.lot_id.type_id.id if (
                                hasattr(wizard.lot_id, 'type_id') and wizard.lot_id.type_id
                            ) else False
                            
                            if lot_type_id:
                                tagged_products = self.env['product.product'].search([
                                    ('lot_type_ids', 'in', lot_type_id),
                                    ('sale_ok', '=', True),
                                    ('active', '=', True)
                                ])
                                if tagged_products:
                                    lot_products.extend(tagged_products.ids)
                        except Exception:
                            # Field doesn't exist or other error, skip
                            pass
                    
                    if lot_products:
                        # Remove duplicates
                        lot_products = list(set(lot_products))
                        domain.append(('id', 'in', lot_products))
                        
                except Exception as e:
                    # If any error in lot-specific filtering, fall back to all products
                    pass
            
            # Rest of the search logic
            if wizard.search_term:
                search_domain = [
                    '|', '|', '|',
                    ('name', 'ilike', wizard.search_term),
                    ('default_code', 'ilike', wizard.search_term),
                    ('description_sale', 'ilike', wizard.search_term),
                    ('barcode', 'ilike', wizard.search_term)
                ]
                domain.extend(search_domain)
            
            # Category filter with child_of operator - compatible with Odoo 18
            if wizard.category_filter:
                domain.append(('categ_id', 'child_of', wizard.category_filter.id))
            
            # Price range filters
            if wizard.price_min > 0:
                domain.append(('list_price', '>=', wizard.price_min))
            if wizard.price_max < 999999:
                domain.append(('list_price', '<=', wizard.price_max))
            
            # Sort order handling - improved for Odoo 18
            order = 'name ASC'
            if wizard.sort_by:
                if 'desc' in wizard.sort_by:
                    field_name = wizard.sort_by.replace(' desc', '')
                    order = f'{field_name} DESC'
                else:
                    order = f'{wizard.sort_by} ASC'
            
            # Use limit for better performance in large datasets
            wizard.available_product_ids = self.env['product.product'].search(
                domain, 
                order=order,
                limit=10000  # Prevent excessive memory usage
            )

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

    # Nouvelle méthode pour charger les lots liés au chantier
    @api.model
    def default_get(self, fields):
        """Override default_get to initialize chantier_lot_ids"""
        res = super().default_get(fields)
        
        # Get chantier lots from the order if available
        if 'order_id' in res and res['order_id']:
            try:
                order = self.env['sale.order'].browse(res['order_id'])
                if order.exists() and order.blg_chantier_id:
                    chantier = order.blg_chantier_id
                    if hasattr(chantier, 'lot_ids') and chantier.lot_ids:
                        # Get lots from the chantier's lot_ids (which are blg.chantier.lot records)
                        chantier_lots = chantier.lot_ids.mapped('lot_id').filtered(lambda l: l.active)
                        if chantier_lots:
                            res['chantier_lot_ids'] = [(6, 0, chantier_lots.ids)]
            except Exception as e:
                # If there's any error accessing the chantier or lots, just continue
                # This prevents the wizard from breaking if relationships are not properly set up
                pass
        
        return res

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

    def action_add_product_from_kanban(self):
        """Add a product to the selection from kanban view - FIXED METHOD"""
        # Get product_id from context or from the record itself
        product_id = self.env.context.get('product_id')
        
        # If no product_id in context, try to get it from active_id
        if not product_id:
            product_id = self.env.context.get('active_id')
        
        if not product_id:
            # If still no product_id, return without error
            return self._reload_view()
        
        return self._add_product_to_selection(product_id)

    def add_product_from_kanban(self):
        """Alternative method name for kanban button calls"""
        return self.action_add_product_from_kanban()

    def _add_product_to_selection(self, product_id):
        """Helper method to add a product to selection"""
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
                'unit_price': product.list_price,
            })
        
        return self._reload_view()

    def action_add_product_to_selection(self):
        """Add a product to the selection based on product_id from context"""
        product_id = self.env.context.get('product_id')
        if not product_id:
            return self._reload_view()
        
        return self._add_product_to_selection(product_id)

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

        # Ensure lot is linked to the quote
        if self.lot_id not in self.order_id.lot_selection_ids:
            self.order_id.write({
                'lot_selection_ids': [(4, self.lot_id.id)]
            })

        # Obtenir la séquence après la section
        sequence = section_line.sequence + 1

        # Ajouter les produits sélectionnés
        lines_added = 0
        for line in self.selection_line_ids.filtered(lambda l: l.quantity > 0):
            product_name = f"[{self.lot_id.code or ''}] {line.product_id.name}"
            
            # Ajouter info localisation si spécifiée
            room_info = ""
            if line.room_type:
                # Utiliser _description_selection pour obtenir les libellés de sélection
                selection_dict = dict(self.env['blg.product.selection.line']._fields['room_type'].selection)
                room_display = selection_dict.get(line.room_type, line.room_type)
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

        # Confirmer la sélection et gérer la navigation multi-lots
        result = super().action_confirm_selection()
        
        # Si on a des lots suivants, proposer de continuer
        if self.has_next_lot:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'blg.lot.navigation.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_order_id': self.order_id.id,
                    'default_current_lot_id': self.lot_id.id,
                    'chantier_lot_ids': self.chantier_lot_ids.ids,
                    'current_lot_index': self.current_lot_index,
                    'completed_lot_name': self.lot_id.name,
                }
            }
        
        return result

    @api.depends('chantier_lot_ids', 'current_lot_index', 'lot_id')
    def _compute_lot_navigation(self):
        """Calculer la navigation entre les lots"""
        for wizard in self:
            if wizard.chantier_lot_ids:
                wizard.has_previous_lot = wizard.current_lot_index > 0
                wizard.has_next_lot = wizard.current_lot_index < len(wizard.chantier_lot_ids) - 1
                wizard.lot_progress = f"Lot {wizard.current_lot_index + 1} / {len(wizard.chantier_lot_ids)}"
            else:
                wizard.has_previous_lot = False
                wizard.has_next_lot = False
                wizard.lot_progress = ""

    def action_previous_lot(self):
        """Passer au lot précédent"""
        if self.has_previous_lot and self.chantier_lot_ids:
            previous_lot = self.chantier_lot_ids.sorted('sequence')[self.current_lot_index - 1]
            return self._navigate_to_lot(previous_lot, self.current_lot_index - 1)

    def action_next_lot(self):
        """Passer au lot suivant"""
        if self.has_next_lot and self.chantier_lot_ids:
            next_lot = self.chantier_lot_ids.sorted('sequence')[self.current_lot_index + 1]
            return self._navigate_to_lot(next_lot, self.current_lot_index + 1)

    def _navigate_to_lot(self, lot, index):
        """Naviguer vers un lot spécifique"""
        return {
            'name': f'Sélection de produits - {lot.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'blg.product.selection.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_lot_id': lot.id,
                'default_order_id': self.order_id.id,
                'chantier_lot_ids': self.chantier_lot_ids.ids,
                'current_lot_index': index,
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
