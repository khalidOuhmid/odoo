# -*- coding: utf-8 -*-
"""
Module: Construction Sale Order Extension
Description: Extension intelligente du modèle sale.order pour la construction avec découpage
Author: BLG Groupe
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SaleOrderConstruction(models.Model):
    """Extension du modèle sale.order pour la gestion des devis construction"""
    
    _inherit = 'sale.order'

    # ================== CHAMPS PRINCIPAUX ==================
    
    chantier_id = fields.Many2one(
        'construction.chantier', 
        string='Chantier',
        help="Projet de construction associé à ce devis"
    )
    
    lot_ids = fields.Many2many(
        'lot', 
        string='Lots concernés',
        help="Lots de construction pour ce devis"
    )

    # ================== CHAMPS POUR LE DÉCOUPAGE ==================
    
    is_split = fields.Boolean(
        string='Devis découpé',
        default=False,
        help="Indique si ce devis a été découpé en bons de commande"
    )
    
    purchase_order_lot_ids = fields.One2many(
        'purchase.order.lot',
        'sale_order_id',
        string='Bons de commande par lot',
        help="Bons de commande générés à partir de ce devis"
    )
    
    purchase_order_count = fields.Integer(
        string='Nombre de bons de commande',
        compute='_compute_purchase_order_count'
    )

    # ================== CHAMPS CALCULÉS ==================
    
    order_line_count = fields.Integer(
        string='Nombre de lignes',
        compute='_compute_order_stats',
        store=True,
        help="Nombre de lignes de produits (hors sections/notes)"
    )
    
    total_quantity = fields.Float(
        string='Quantité totale',
        compute='_compute_order_stats',
        store=True,
        help="Quantité totale de tous les produits"
    )

    # ================== ÉTATS PERSONNALISÉS ==================
    
    state = fields.Selection(
        selection_add=[
            ('validated', 'Devis validé'),
            ('split', 'Découpé'),
            ('no_follow', 'Sans suite'),
            ('draft',)
        ],
        ondelete={'validated': 'cascade', 'split': 'cascade', 'no_follow': 'cascade'}
    )

    # ================== MÉTHODES CALCULÉES ==================

    @api.depends('order_line')
    def _compute_order_stats(self):
        """Calcule les statistiques des lignes de commande"""
        for order in self:
            product_lines = order.order_line.filtered(lambda l: not l.display_type)
            order.order_line_count = len(product_lines)
            order.total_quantity = sum(product_lines.mapped('product_uom_qty'))

    @api.depends('purchase_order_lot_ids')
    def _compute_purchase_order_count(self):
        """Calcule le nombre de bons de commande générés"""
        for order in self:
            order.purchase_order_count = len(order.purchase_order_lot_ids)

    # ================== ACTIONS MÉTIER ==================

    def action_validate_quote(self):
        """Valide le devis et fait progresser le chantier"""
        self.ensure_one()
        self.write({'state': 'validated'})
        
        if self.chantier_id:
            self._update_chantier_stage('stage_devis_accepte')
        
        return self._show_success_notification(
            "Devis validé",
            f"Le devis {self.name} a été validé avec succès."
        )

    def action_mark_no_follow(self):
        """Marque le devis sans suite"""
        self.ensure_one()
        self.write({'state': 'no_follow'})
        
        if self.chantier_id:
            self._update_chantier_stage('stage_sans_suite', abandon=True)
        
        return self._show_success_notification(
            "Devis marqué sans suite",
            f"Le devis {self.name} a été marqué sans suite."
        )

    def action_organize_by_lots(self):
        """Organise le devis par sections de lots"""
        self.ensure_one()
        
        if not self.lot_ids:
            return self._show_warning_notification(
                "Aucun lot sélectionné",
                "Veuillez d'abord sélectionner des lots pour ce devis."
            )
        
        self._create_lot_sections()
        
        return self._show_success_notification(
            "Devis organisé",
            f"{len(self.lot_ids)} section(s) créée(s) pour les lots."
        )

    def action_add_product_wizard(self):
        """Ouvre le wizard d'ajout de produit intelligent"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Ajouter des produits',
            'res_model': 'construction.product.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sale_order_id': self.id,
                'default_lot_ids': [(6, 0, self.lot_ids.ids)],
            }
        }

    # ================== ACTIONS DÉCOUPAGE ==================

    def action_split_quote(self):
        """Ouvrir l'assistant de découpage du devis"""
        self.ensure_one()
        
        # Vérifications préliminaires
        if not self.chantier_id:
            raise ValidationError(
                "Ce devis doit être associé à un chantier pour pouvoir être découpé."
            )
        
        if not self.order_line.filtered(lambda l: not l.display_type):
            raise ValidationError(
                "Ce devis ne contient aucune ligne de produit à découper."
            )
        
        if self.state not in ['draft', 'sent', 'sale', 'validated']:
            raise ValidationError(
                "Seuls les devis en brouillon, envoyés, confirmés ou validés peuvent être découpés."
            )
        
        # Ouvrir le wizard de découpage
        return {
            'type': 'ir.actions.act_window',
            'name': 'Découper le devis',
            'res_model': 'split.quote.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sale_order_id': self.id,
                'active_id': self.id,
            }
        }
    
    def action_view_purchase_orders(self):
        """Voir les bons de commande générés"""
        self.ensure_one()
        
        if not self.purchase_order_lot_ids:
            return self._show_warning_notification(
                "Aucun bon de commande",
                "Ce devis n'a pas encore été découpé en bons de commande."
            )
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'Bons de commande - {self.name}',
            'res_model': 'purchase.order.lot',
            'view_mode': 'kanban,tree,form',
            'domain': [('sale_order_id', '=', self.id)],
            'context': {
                'default_sale_order_id': self.id,
                'create': False,
            },
            'target': 'current',
        }

    def mark_as_split(self):
        """Marquer le devis comme découpé"""
        self.ensure_one()
        self.write({
            'state': 'split',
            'is_split': True
        })

    # ================== MÉTHODES PRIVÉES ==================
    
    def _create_lot_sections(self):
        """Créer des sections pour chaque lot dans le devis"""
        sequence = 10
        
        for lot in self.lot_ids:
            # Vérifier si une section pour ce lot existe déjà
            existing_section = self.order_line.filtered(
                lambda l: l.display_type == 'line_section' and lot.name in (l.name or '')
            )
            
            if not existing_section:
                # Créer une nouvelle section
                self.env['sale.order.line'].create({
                    'order_id': self.id,
                    'display_type': 'line_section',
                    'name': f"🏗️ {lot.name}",
                    'sequence': sequence,
                })
                sequence += 10

    def _update_chantier_stage(self, stage_code, abandon=False):
        """Mettre à jour l'étape du chantier"""
        if not self.chantier_id:
            return
        
        # Rechercher l'étape par son code
        stage = self.env['stage'].search([('code', '=', stage_code)], limit=1)
        if stage:
            values = {'stage_id': stage.id}
            
            if abandon:
                values['state'] = 'abandoned'
            elif stage_code == 'stage_devis_accepte':
                values['total_cost'] = self.amount_total
            
            self.chantier_id.write(values)

    def _show_success_notification(self, title, message):
        """Afficher une notification de succès"""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'title': title,
                'message': message,
                'sticky': False,
            }
        }

    def _show_warning_notification(self, title, message):
        """Afficher une notification d'avertissement"""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'warning',
                'title': title,
                'message': message,
                'sticky': True,
            }
        }

    # ================== SURCHARGES ODOO ==================

    def action_confirm(self):
        """Surcharge pour gérer la validation avec lots"""
        for order in self:
            if order.lot_ids and not order.order_line.filtered(lambda l: not l.display_type):
                raise ValidationError(
                    "Vous avez sélectionné des lots mais aucun produit n'a été ajouté au devis. "
                    "Veuillez ajouter des produits ou retirer la sélection de lots."
                )
        
        res = super().action_confirm()
        
        # Mettre à jour les chantiers liés
        for order in self:
            if order.chantier_id:
                order._update_chantier_stage('stage_devis_accepte')
        
        return res

    def action_cancel(self):
        """Surcharge pour gérer l'annulation"""
        res = super().action_cancel()
        
        # Annuler les bons de commande liés si nécessaire
        for order in self:
            if order.purchase_order_lot_ids:
                draft_pos = order.purchase_order_lot_ids.filtered(lambda po: po.state == 'draft')
                if draft_pos:
                    draft_pos.action_cancel()
        
        return res


class SaleOrderLineConstruction(models.Model):
    """Extension des lignes de commande pour la construction"""
    
    _inherit = 'sale.order.line'

    # ================== CHAMPS SPÉCIALISÉS CONSTRUCTION ==================
    
    room_location = fields.Char(
        string='Localisation',
        help="Ex: Salon, Cuisine, Chambre 1, etc."
    )
    
    floor_level = fields.Selection([
        ('basement', 'Sous-sol'),
        ('ground', 'Rez-de-chaussée'),
        ('floor_1', 'Étage 1'),
        ('floor_2', 'Étage 2'),
        ('floor_3', 'Étage 3'),
        ('attic', 'Combles'),
    ], string='Niveau')
    
    construction_notes = fields.Text(
        string='Notes techniques',
        help="Notes spécifiques pour l'installation/réalisation"
    ) 