# -*- coding: utf-8 -*-
"""
Module: Quick Product Creation Wizard
Description: Assistant simplifié pour la création rapide de produits
Author: BLG Groupe
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ConstructionQuickProductWizard(models.TransientModel):
    """Assistant de création rapide de produits"""
    
    _name = 'construction.quick.product.wizard'
    _description = 'Création rapide de produit construction'

    # ================== INFORMATIONS DE BASE ==================
    
    wizard_id = fields.Many2one(
        'construction.product.wizard',
        string='Assistant parent'
    )
    
    lot_id = fields.Many2one(
        'lot',
        string='Lot associé'
    )

    # ================== INFORMATIONS PRODUIT ==================
    
    name = fields.Char(
        string='Nom du produit',
        required=True,
        placeholder="Ex: Prise électrique simple"
    )
    
    default_code = fields.Char(
        string='Référence',
        placeholder="Ex: ELEC-001"
    )
    
    list_price = fields.Float(
        string='Prix de vente',
        required=True,
        default=0.0
    )
    
    standard_price = fields.Float(
        string='Coût',
        default=0.0
    )
    
    categ_id = fields.Many2one(
        'product.category',
        string='Catégorie',
        required=True,
        default=lambda self: self._get_default_category()
    )

    # ================== OPTIONS ==================
    
    description_sale = fields.Text(
        string='Description pour devis',
        placeholder="Description qui apparaîtra sur le devis..."
    )
    
    add_to_selection = fields.Boolean(
        string='Ajouter à la sélection',
        default=True,
        help="Ajouter automatiquement ce produit à la sélection"
    )
    
    quantity = fields.Float(
        string='Quantité',
        default=1.0
    )

    # ================== APERÇU ==================
    
    product_preview = fields.Char(
        string='Aperçu',
        compute='_compute_product_preview'
    )

    # ================== MÉTHODES CALCULÉES ==================

    @api.depends('name', 'default_code', 'list_price', 'lot_id')
    def _compute_product_preview(self):
        """Calcule l'aperçu du produit avec info lot"""
        for wizard in self:
            parts = []
            if wizard.lot_id:
                parts.append(f"[{wizard.lot_id.code}]")
            if wizard.default_code:
                parts.append(f"[{wizard.default_code}]")
            elif wizard.lot_id and wizard.name:
                # Génération automatique de code basée sur le lot
                auto_code = wizard._generate_auto_code()
                if auto_code:
                    parts.append(f"[{auto_code}]")
            if wizard.name:
                parts.append(wizard.name)
            if wizard.list_price:
                parts.append(f"- {wizard.list_price:.2f} €")
            
            preview = " ".join(parts) if parts else "Nouveau produit"
            if wizard.lot_id:
                preview += f" (Lot: {wizard.lot_id.name})"
            wizard.product_preview = preview

    # ================== MÉTHODES DE BASE ==================

    @api.model
    def default_get(self, fields_list):
        """Préremplir le wizard avec les valeurs par défaut intelligentes"""
        res = super().default_get(fields_list)
        
        # Récupérer le lot depuis le contexte
        if 'lot_id' in self.env.context:
            res['lot_id'] = self.env.context['lot_id']
            
            # Mettre à jour la catégorie selon le lot
            if 'categ_id' in fields_list:
                lot = self.env['lot'].browse(self.env.context['lot_id'])
                if lot.exists():
                    category = self._get_default_category_for_lot(lot)
                    if category:
                        res['categ_id'] = category.id
        
        return res

    # ================== MÉTHODES PRIVÉES ==================

    def _generate_auto_code(self):
        """Génère un code automatique basé sur le lot et le nom"""
        if not self.lot_id or not self.name:
            return False
        
        # Extraire les premières lettres du nom pour créer un code
        name_parts = self.name.upper().split()
        if len(name_parts) == 1:
            name_code = name_parts[0][:4]  # 4 premières lettres
        else:
            # Première lettre de chaque mot
            name_code = ''.join([part[0] for part in name_parts[:3]])
        
        # Compter les produits existants pour ce lot pour avoir un numéro séquentiel
        existing_count = len(self.env['product.product'].search([('lot_ids', 'in', self.lot_id.id)]))
        
        return f"{self.lot_id.code}-{name_code}-{existing_count + 1:03d}"

    def _get_default_category_for_lot(self, lot):
        """Obtient une catégorie par défaut pour un lot donné"""
        if not lot:
            return self.env['product.category'].search([], limit=1)
            
        # Mapper selon le lot
        category_mapping = {
            'DEM': 'construction_sale.product_category_demolition',
            'MAC': 'construction_sale.product_category_masonry', 
            'CVC': 'construction_sale.product_category_plumbing',
            'ELE': 'construction_sale.product_category_electrical',
            'MEX': 'construction_sale.product_category_joinery_ext',
            'MIN': 'construction_sale.product_category_joinery_int',
            'PEI': 'construction_sale.product_category_painting',
            'SOL': 'construction_sale.product_category_flooring',
            'CAR': 'construction_sale.product_category_tiling',
        }
        
        category_ref = category_mapping.get(lot.code)
        if category_ref:
            try:
                return self.env.ref(category_ref)
            except:
                pass
        
        # Fallback : première catégorie disponible
        return self.env['product.category'].search([], limit=1)

    def _get_default_category(self):
        """Obtient une catégorie par défaut intelligente"""
        return self._get_default_category_for_lot(self.lot_id)

    # ================== ACTIONS ==================

    def action_create_product(self):
        """Créer le produit avec dénomination automatique et liaison au lot"""
        self.ensure_one()
        
        # Valider les données
        if not self.categ_id:
            raise ValidationError("Une catégorie est requise pour créer le produit.")
        
        # Générer la référence automatiquement si non fournie
        if not self.default_code and self.lot_id:
            # Essayer d'utiliser la séquence d'abord
            sequence_code = f"PROD.{self.lot_id.code}"
            auto_code = self.env['ir.sequence'].next_by_code(sequence_code)
            self.default_code = auto_code or self._generate_auto_code()
        
        # Créer le produit avec liaison automatique au lot
        product_vals = {
            'name': self.name,
            'default_code': self.default_code,
            'list_price': self.list_price,
            'standard_price': self.standard_price,
            'categ_id': self.categ_id.id,
            'sale_ok': True,
            'purchase_ok': True,
            # LIAISON AUTOMATIQUE AU LOT
            'lot_ids': [(6, 0, [self.lot_id.id])] if self.lot_id else False,
        }
        
        if self.description_sale:
            product_vals['description_sale'] = self.description_sale
        
        try:
            product = self.env['product.product'].create(product_vals)
            
            # Message de liaison au lot
            if self.lot_id:
                product.message_post(
                    body=f"Produit automatiquement lié au lot : {self.lot_id.name}",
                    message_type='comment'
                )
            
        except Exception as e:
            raise ValidationError(f"Erreur lors de la création du produit : {str(e)}")
        
        # Ajouter à la sélection si demandé
        if self.add_to_selection and self.wizard_id:
            self.env['construction.product.line'].create({
                'wizard_id': self.wizard_id.id,
                'product_id': product.id,
                'quantity': self.quantity,
                'price_unit': product.list_price,
                'lot_id': self.lot_id.id if self.lot_id else False,
            })
            
            # FORCER LE RECALCUL DES PRODUITS DISPONIBLES
            # Vider le cache pour forcer la recomputation
            self.wizard_id._invalidate_cache(['available_products'])
            
            # Retourner au wizard principal avec notification
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'construction.product.wizard',
                'res_id': self.wizard_id.id,
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'product_just_created': product.id,
                    'message': f'Produit "{self.name}" créé et ajouté à la sélection !',
                }
            }
        
        # Notification de succès avec info lot
        lot_info = f" et lié au lot {self.lot_id.name}" if self.lot_id else ""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Produit créé',
                'message': f'Le produit "{self.name}" a été créé avec succès{lot_info}.',
                'type': 'success'
            }
        }

    @api.onchange('lot_id')
    def _onchange_lot_id(self):
        """Met à jour la catégorie et le code selon le lot sélectionné"""
        if self.lot_id:
            new_category = self._get_default_category()
            if new_category:
                self.categ_id = new_category
            
            # Générer le code automatiquement TOUJOURS quand le lot change
            # (pour avoir un code de base même sans nom)
            if not self.default_code:
                # Utiliser la séquence d'abord
                sequence_code = f"PROD.{self.lot_id.code}"
                auto_code = self.env['ir.sequence'].next_by_code(sequence_code)
                if auto_code:
                    self.default_code = auto_code
                elif self.name:
                    self.default_code = self._generate_auto_code()

    @api.onchange('name')
    def _onchange_name(self):
        """Met à jour le code automatiquement quand le nom change"""
        if self.name and self.lot_id:
            # Régénérer uniquement si le code actuel est générique ou vide
            if not self.default_code or (self.default_code and not self.name.lower().replace(' ', '') in self.default_code.lower()):
                self.default_code = self._generate_auto_code()
    
 