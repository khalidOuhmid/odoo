# -*- coding: utf-8 -*-
"""
Module: Split Quote Wizard
Description: Assistant pour découper un devis en bons de commande par lots
Author: BLG Groupe
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class SplitQuoteWizard(models.TransientModel):
    """Assistant pour découper un devis en bons de commande par lots et sous-traitants"""
    
    _name = 'split.quote.wizard'
    _description = 'Assistant découpage devis'

    # ================== CHAMPS PRINCIPAUX ==================
    
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Devis à découper',
        required=True,
        default=lambda self: self.env.context.get('active_id')
    )
    
    chantier_id = fields.Many2one(
        'construction.chantier',
        string='Chantier',
        related='sale_order_id.chantier_id',
        readonly=True
    )
    
    state = fields.Selection([
        ('step1', 'Sélection des lots'),
        ('step2', 'Attribution des sous-traitants'),
        ('step3', 'Validation et création')
    ], default='step1', string='Étape')
    
    # ================== INFORMATIONS DU DEVIS ==================
    
    order_amount_total = fields.Monetary(
        string='Montant total du devis',
        related='sale_order_id.amount_total',
        readonly=True
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        related='sale_order_id.currency_id',
        readonly=True
    )
    
    # ================== LIGNES DE DÉCOUPAGE ==================
    
    split_line_ids = fields.One2many(
        'split.quote.line',
        'wizard_id',
        string='Lignes de découpage'
    )
    
    # ================== STATISTIQUES ==================
    
    total_split_amount = fields.Monetary(
        string='Montant total découpé',
        compute='_compute_split_totals',
        currency_field='currency_id'
    )
    
    remaining_amount = fields.Monetary(
        string='Montant restant',
        compute='_compute_split_totals',
        currency_field='currency_id'
    )
    
    split_line_count = fields.Integer(
        string='Nombre de lots',
        compute='_compute_split_totals'
    )
    
    subcontractor_count = fields.Integer(
        string='Nombre de sous-traitants',
        compute='_compute_split_totals'
    )
    
    @api.depends('split_line_ids.amount_assigned', 'sale_order_id.amount_total')
    def _compute_split_totals(self):
        """Calcule les totaux et statistiques"""
        for wizard in self:
            total_split = sum(wizard.split_line_ids.mapped('amount_assigned'))
            wizard.total_split_amount = total_split
            wizard.remaining_amount = wizard.sale_order_id.amount_total - total_split
            wizard.split_line_count = len(wizard.split_line_ids)
            wizard.subcontractor_count = len(wizard.split_line_ids.mapped('subcontractor_id'))
    
    @api.model
    def default_get(self, fields_list):
        """Initialiser le wizard avec les lots du devis"""
        defaults = super().default_get(fields_list)
        
        if 'sale_order_id' in defaults and defaults['sale_order_id']:
            sale_order = self.env['sale.order'].browse(defaults['sale_order_id'])
            
            # Créer automatiquement les lignes pour chaque lot du devis
            if sale_order.lot_selection_ids:
                split_lines = []
                for lot_category in sale_order.lot_selection_ids:
                    # Trouver les lots du chantier correspondant à cette catégorie
                    lots = sale_order.chantier_id.lots_ids.filtered(
                        lambda l: l.lot_category_id == lot_category
                    )
                    
                    for lot in lots:
                        split_lines.append((0, 0, {
                            'lot_category_id': lot_category.id,
                            'lot_id': lot.id,
                            'subcontractor_id': lot.subcontractor_ids[0].id if lot.subcontractor_ids else False,
                            'amount_assigned': 0.0,
                            'selected': True,
                        }))
                
                defaults['split_line_ids'] = split_lines
        
        return defaults
    
    def action_next_step(self):
        """Passer à l'étape suivante"""
        self.ensure_one()
        
        if self.state == 'step1':
            # Vérifier qu'au moins un lot est sélectionné
            if not self.split_line_ids.filtered('selected'):
                raise UserError("Veuillez sélectionner au moins un lot à découper.")
            
            self.state = 'step2'
            return self._reload_wizard()
        
        elif self.state == 'step2':
            # Vérifier que tous les lots sélectionnés ont un sous-traitant
            selected_lines = self.split_line_ids.filtered('selected')
            missing_subcontractors = selected_lines.filtered(lambda l: not l.subcontractor_id)
            
            if missing_subcontractors:
                raise UserError("Veuillez attribuer un sous-traitant à tous les lots sélectionnés.")
            
            self.state = 'step3'
            return self._reload_wizard()
        
        elif self.state == 'step3':
            return self.action_create_purchase_orders()
    
    def action_previous_step(self):
        """Revenir à l'étape précédente"""
        self.ensure_one()
        
        if self.state == 'step2':
            self.state = 'step1'
        elif self.state == 'step3':
            self.state = 'step2'
        
        return self._reload_wizard()
    
    def action_auto_assign_amounts(self):
        """Répartir automatiquement les montants selon les lots"""
        self.ensure_one()
        
        selected_lines = self.split_line_ids.filtered('selected')
        if not selected_lines:
            return
        
        # Calculer le montant par lot selon les lignes de commande associées
        total_order_amount = self.sale_order_id.amount_total
        
        for line in selected_lines:
            # Trouver les lignes de commande liées à ce lot
            related_lines = self.sale_order_id.order_line.filtered(
                lambda ol: not ol.display_type and line._is_line_related_to_lot(ol)
            )
            
            if related_lines:
                line.amount_assigned = sum(related_lines.mapped('price_total'))
            else:
                # Répartition équitable si pas de correspondance
                line.amount_assigned = total_order_amount / len(selected_lines)
    
    def action_create_purchase_orders(self):
        """Créer les bons de commande pour les sous-traitants"""
        self.ensure_one()
        
        if self.state != 'step3':
            raise UserError("Cette action n'est disponible qu'à la dernière étape.")
        
        selected_lines = self.split_line_ids.filtered('selected')
        if not selected_lines:
            raise UserError("Aucun lot sélectionné.")
        
        purchase_orders = self.env['purchase.order.lot']
        
        # Grouper par sous-traitant
        subcontractors = selected_lines.mapped('subcontractor_id')
        
        for subcontractor in subcontractors:
            subcontractor_lines = selected_lines.filtered(lambda l: l.subcontractor_id == subcontractor)
            
            # Créer le bon de commande pour ce sous-traitant
            purchase_order = self.env['purchase.order.lot'].create({
                'sale_order_id': self.sale_order_id.id,
                'partner_id': subcontractor.id,
                'lot_id': subcontractor_lines[0].lot_id.id,  # Premier lot pour la référence
                'date_planned': fields.Date.today(),
                'notes': f"Bon de commande généré depuis le devis {self.sale_order_id.name}",
            })
            
            # Créer les lignes de commande
            for split_line in subcontractor_lines:
                self._create_purchase_order_lines(purchase_order, split_line)
            
            purchase_orders |= purchase_order
        
        # Marquer le devis comme découpé
        self.sale_order_id.message_post(
            body=f"Devis découpé en {len(purchase_orders)} bon(s) de commande pour {len(subcontractors)} sous-traitant(s).",
            message_type='notification'
        )
        
        # Retourner l'action pour voir les bons de commande créés
        return {
            'type': 'ir.actions.act_window',
            'name': 'Bons de commande créés',
            'res_model': 'purchase.order.lot',
            'view_mode': 'list,form',
            'domain': [('id', 'in', purchase_orders.ids)],
            'context': {'create': False},
            'target': 'current',
        }
    
    def _create_purchase_order_lines(self, purchase_order, split_line):
        """Créer les lignes de commande pour un bon de commande"""
        # Trouver les lignes de devis liées à ce lot
        related_sale_lines = self.sale_order_id.order_line.filtered(
            lambda ol: not ol.display_type and split_line._is_line_related_to_lot(ol)
        )
        
        if related_sale_lines:
            # Créer une ligne pour chaque ligne de devis liée
            for sale_line in related_sale_lines:
                self.env['purchase.order.lot.line'].create({
                    'order_id': purchase_order.id,
                    'sale_line_id': sale_line.id,
                    'product_id': sale_line.product_id.id,
                    'name': sale_line.name,
                    'product_qty': sale_line.product_uom_qty,
                    'product_uom': sale_line.product_uom.id,
                    'price_unit': sale_line.price_unit,
                })
        else:
            # Créer une ligne générique avec le montant assigné
            self.env['purchase.order.lot.line'].create({
                'order_id': purchase_order.id,
                'name': f"Travaux {split_line.lot_category_id.name} - {split_line.lot_id.name}",
                'product_qty': 1.0,
                'price_unit': split_line.amount_assigned,
            })
    
    def _reload_wizard(self):
        """Recharger le wizard avec les nouvelles données"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Découper le devis',
            'res_model': 'split.quote.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }


class SplitQuoteLine(models.TransientModel):
    """Ligne de découpage de devis"""
    
    _name = 'split.quote.line'
    _description = 'Ligne de découpage de devis'

    # ================== RELATIONS ==================
    
    wizard_id = fields.Many2one(
        'split.quote.wizard',
        string='Assistant',
        required=True,
        ondelete='cascade'
    )
    
    lot_category_id = fields.Many2one(
        'lot.category',
        string='Catégorie de lot',
        required=True
    )
    
    lot_id = fields.Many2one(
        'lot',
        string='Lot',
        required=True
    )
    
    subcontractor_id = fields.Many2one(
        'res.partner',
        string='Sous-traitant',
        domain="[('is_company', '=', True), ('supplier_rank', '>', 0)]"
    )
    
    # ================== CONFIGURATION ==================
    
    selected = fields.Boolean(
        string='Sélectionné',
        default=True,
        help="Cocher pour inclure ce lot dans le découpage"
    )
    
    amount_assigned = fields.Monetary(
        string='Montant assigné',
        currency_field='currency_id',
        help="Montant à attribuer à ce lot"
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        related='wizard_id.currency_id',
        readonly=True
    )
    
    # ================== INFORMATIONS ==================
    
    lot_name = fields.Char(
        string='Nom du lot',
        related='lot_id.name',
        readonly=True
    )
    
    lot_cost = fields.Monetary(
        string='Coût prévu du lot',
        related='lot_id.price',
        readonly=True,
        currency_field='currency_id'
    )
    
    has_subcontractor = fields.Boolean(
        string='A un sous-traitant',
        compute='_compute_has_subcontractor'
    )
    
    related_lines_count = fields.Integer(
        string='Lignes liées',
        compute='_compute_related_lines_count',
        help="Nombre de lignes de devis liées à ce lot"
    )
    
    @api.depends('subcontractor_id')
    def _compute_has_subcontractor(self):
        """Vérifier si un sous-traitant est assigné"""
        for line in self:
            line.has_subcontractor = bool(line.subcontractor_id)
    
    @api.depends('wizard_id.sale_order_id.order_line', 'lot_category_id')
    def _compute_related_lines_count(self):
        """Compter les lignes de devis liées à ce lot"""
        for line in self:
            count = 0
            if line.wizard_id.sale_order_id:
                for order_line in line.wizard_id.sale_order_id.order_line:
                    if not order_line.display_type and line._is_line_related_to_lot(order_line):
                        count += 1
            line.related_lines_count = count
    
    def _is_line_related_to_lot(self, order_line):
        """Vérifier si une ligne de commande est liée à ce lot"""
        # Logique pour déterminer si une ligne appartient à ce lot
        # Peut être basée sur le nom, des tags, ou d'autres critères
        
        lot_keywords = [
            self.lot_category_id.name.lower(),
            self.lot_id.name.lower() if self.lot_id.name else ''
        ]
        
        line_text = (order_line.name or '').lower()
        
        # Vérifier si des mots-clés du lot sont dans la description de la ligne
        return any(keyword in line_text for keyword in lot_keywords if keyword)
    
    @api.onchange('lot_id')
    def _onchange_lot_id(self):
        """Mise à jour automatique lors du changement de lot"""
        if self.lot_id:
            # Suggérer le sous-traitant du lot
            if self.lot_id.subcontractor_ids:
                self.subcontractor_id = self.lot_id.subcontractor_ids[0]
            
            # Suggérer le montant basé sur le coût du lot
            if self.lot_id.price:
                self.amount_assigned = self.lot_id.price
    
    def action_view_related_lines(self):
        """Voir les lignes de devis liées à ce lot"""
        self.ensure_one()
        
        if not self.wizard_id.sale_order_id:
            return
        
        related_lines = self.wizard_id.sale_order_id.order_line.filtered(
            lambda ol: not ol.display_type and self._is_line_related_to_lot(ol)
        )
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'Lignes liées au lot {self.lot_category_id.name}',
            'res_model': 'sale.order.line',
            'view_mode': 'list',
            'domain': [('id', 'in', related_lines.ids)],
            'context': {'create': False, 'edit': False},
            'target': 'new',
        } 