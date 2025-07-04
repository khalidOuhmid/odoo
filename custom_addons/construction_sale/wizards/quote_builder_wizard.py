# wizards/quote_builder_wizard.py
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta


class QuoteBuilderWizard(models.TransientModel):
    """
    Wizard amélioré pour créer un devis avec sélection rapide par lots
    """
    _name = 'construction.quote.builder.wizard'
    _description = 'Assistant création devis par lots'

    chantier_id = fields.Many2one(
        'construction.chantier',
        string='Chantier',
        required=True,
        default=lambda self: self.env.context.get('active_id')
    )
    
    partner_id = fields.Many2one(
        'res.partner',
        string='Client',
        required=True
    )
    
    lot_ids = fields.Many2many(
        'lot',
        string='Lots sélectionnés',
        help="Lots à inclure dans le devis"
    )
    
    validity_date = fields.Date(
        string='Date de validité',
        default=lambda self: fields.Date.today() + timedelta(days=30)
    )
    
    # Wizard state
    step = fields.Selection([
        ('select_lots', 'Sélection des lots'),
        ('add_products', 'Ajout des produits'),
    ], default='select_lots')
    
    current_lot_id = fields.Many2one('lot', string='Lot en cours')
    
    @api.onchange('chantier_id')
    def _onchange_chantier_id(self):
        """Mettre à jour le client et les lots disponibles"""
        if self.chantier_id:
            self.partner_id = self.chantier_id.client
            # Pré-sélectionner les lots du chantier
            if self.chantier_id.lots_ids:
                self.lot_ids = self.chantier_id.lots_ids
    
    def action_create_quote_native(self):
        """Créer un devis en utilisant le module natif d'Odoo avec redirection"""
        self.ensure_one()
        
        if not self.lot_ids:
            raise UserError("Veuillez sélectionner au moins un lot.")
        
        # Créer le devis avec le module natif
        sale_order = self.env['sale.order'].create({
            'partner_id': self.partner_id.id,
            'chantier_id': self.chantier_id.id,
            'lot_ids': [(6, 0, self.lot_ids.ids)],
            'validity_date': self.validity_date,
            'origin': f"Chantier: {self.chantier_id.name}",
        })
        
        # Créer les sections par lot
        sequence = 10
        for lot in self.lot_ids:
            self.env['sale.order.line'].create({
                'order_id': sale_order.id,
                'display_type': 'line_section',
                'name': f"📋 {lot.name}",
                'sequence': sequence,
            })
            sequence += 10
        
        # Message sur le chantier
        self.chantier_id.message_post(
            body=f"Devis créé : {sale_order.name}",
            message_type='notification'
        )
        
        # Rediriger vers le devis natif d'Odoo pour édition
        return {
            'type': 'ir.actions.act_window',
            'name': 'Devis',
            'res_model': 'sale.order',
            'res_id': sale_order.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_chantier_id': self.chantier_id.id,
                'chantier_lots': self.lot_ids.ids,
                'show_lot_selection': True,
            }
        }


class QuoteProductWizard(models.TransientModel):
    """
    Wizard pour l'ajout rapide de produits par lot
    """
    _name = 'construction.quote.product.wizard'
    _description = 'Ajout rapide de produits par lot'

    sale_order_id = fields.Many2one('sale.order', string='Devis', required=True)
    lot_id = fields.Many2one('lot', string='Lot', required=True)
    
    product_id = fields.Many2one(
        'product.product',
        string='Produit',
        domain="[('sale_ok', '=', True)]"
    )
    
    # Produit à créer si n'existe pas
    create_product = fields.Boolean('Créer un nouveau produit')
    product_name = fields.Char('Nom du produit')
    product_sale_price = fields.Float('Prix de vente')
    
    # Détails de ligne
    quantity = fields.Float('Quantité', default=1.0)
    room = fields.Char('Pièce', placeholder="ex: Chambre, Salon...")
    floor = fields.Char('Étage', placeholder="ex: RDC, 1er étage...")
    room_number = fields.Char('Numéro', placeholder="ex: 1, 2, A, B...")
    comment = fields.Text('Commentaire')
    
    @api.onchange('create_product')
    def _onchange_create_product(self):
        """Vider le produit sélectionné si on veut en créer un nouveau"""
        if self.create_product:
            self.product_id = False
    
    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Vider les champs de création si on sélectionne un produit existant"""
        if self.product_id:
            self.create_product = False
            self.product_name = ''
    
    def action_add_product_to_quote(self):
        """Ajouter le produit au devis"""
        self.ensure_one()
        
        # Créer le produit si nécessaire
        if self.create_product:
            if not self.product_name:
                raise UserError("Le nom du produit est requis.")
            
            # Créer le produit
            product = self.env['product.product'].create({
                'name': self.product_name,
                'list_price': self.product_sale_price or 0.0,
                'sale_ok': True,
                'purchase_ok': True,
                'type': 'consu',  # Consommable par défaut
                'categ_id': self.lot_id.category_id.id if hasattr(self.lot_id, 'category_id') else False,
            })
            self.product_id = product
        
        if not self.product_id:
            raise UserError("Veuillez sélectionner ou créer un produit.")
        
        # Construire la description avec les détails
        description_parts = []
        if self.room:
            description_parts.append(f"Pièce: {self.room}")
        if self.floor:
            description_parts.append(f"Étage: {self.floor}")
        if self.room_number:
            description_parts.append(f"N°: {self.room_number}")
        if self.comment:
            description_parts.append(f"Note: {self.comment}")
        
        name = self.product_id.name
        if description_parts:
            name += f" ({', '.join(description_parts)})"
        
        # Trouver la section du lot pour insérer après
        lot_section = self.sale_order_id.order_line.filtered(
            lambda l: l.display_type == 'line_section' and self.lot_id.name in (l.name or '')
        )
        
        sequence = 999  # Par défaut à la fin
        if lot_section:
            # Trouver les lignes après cette section
            lines_after_section = self.sale_order_id.order_line.filtered(
                lambda l: l.sequence > lot_section[0].sequence
            )
            if lines_after_section:
                # Insérer avant la prochaine section ou à la fin
                next_section = lines_after_section.filtered(lambda l: l.display_type == 'line_section')
                if next_section:
                    sequence = next_section[0].sequence - 1
                else:
                    sequence = max(lines_after_section.mapped('sequence')) + 1
            else:
                sequence = lot_section[0].sequence + 1
        
        # Créer la ligne de commande
        self.env['sale.order.line'].create({
            'order_id': self.sale_order_id.id,
            'product_id': self.product_id.id,
            'name': name,
            'product_uom_qty': self.quantity,
            'price_unit': self.product_id.list_price,
            'sequence': sequence,
        })
        
        # Fermer le wizard et recharger la vue du devis
        return {
            'type': 'ir.actions.act_window_close',
        }
