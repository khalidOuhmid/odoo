# -*- coding: utf-8 -*-
"""
Extension du modèle sale.order pour la gestion de devis construction
Respecte les standards Odoo 18 et les principes SOLID
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class SaleOrderConstruction(models.Model):
    """Extension du modèle sale.order pour la construction"""
    
    _inherit = 'sale.order'

    # =================== CHAMPS MÉTIER ===================
    
    chantier_id = fields.Many2one(
        'construction.chantier', 
        string='Chantier',
        tracking=True,
        help="Projet de construction associé à ce devis"
    )
    
    lot_ids = fields.Many2many(
        'construction.lot',
        string='Lots concernés',
        help="Lots de construction pour ce devis"
    )

    # =================== COMPATIBILITÉ  ===================
    
    # Champ de compatibilité pour éviter les erreurs avec les modules BLG
    lot_selection_ids = fields.Many2many(
        'construction.lot',  # Utiliser construction.lot au lieu de lot.category
        'sale_order_construction_lot_rel',
        'order_id',
        'lot_id',
        string='Sélection de lots (compatibilité)',
        help="Champ de compatibilité avec les modules BLG existants"
    )

    # =================== CHAMPS CALCULÉS ===================
    
    order_line_count = fields.Integer(
        string='Nombre de lignes',
        compute='_compute_order_statistics',
        store=True,
        help="Nombre de lignes de produits (hors sections/notes)"
    )
    
    total_quantity = fields.Float(
        string='Quantité totale',
        compute='_compute_order_statistics',
        store=True,
        help="Quantité totale de tous les produits"
    )

    # =================== CONTRAINTES ===================
    
    @api.constrains('chantier_id', 'lot_ids')
    def _check_lot_coherence(self):
        """Vérifie que les lots sélectionnés appartiennent au chantier"""
        for record in self:
            if record.chantier_id and record.lot_ids:
                chantier_lots = record.chantier_id.lots_ids
                invalid_lots = record.lot_ids - chantier_lots
                if invalid_lots:
                    raise ValidationError(_(
                        "Les lots suivants n'appartiennent pas au chantier '%s' : %s"
                    ) % (record.chantier_id.name, ', '.join(invalid_lots.mapped('name'))))

    # =================== MÉTHODES CALCULÉES ===================

    @api.depends('order_line')
    def _compute_order_statistics(self):
        """Calcule les statistiques du devis"""
        for record in self:
            # Filtrer uniquement les lignes de produits (pas les sections/notes)
            product_lines = record.order_line.filtered(lambda l: not l.display_type)
            record.order_line_count = len(product_lines)
            record.total_quantity = sum(product_lines.mapped('product_uom_qty'))

    @api.model
    def create(self, vals):
        """Injecter le nom du chantier lors de la création d'un devis"""
        # Si un chantier est spécifié et que le nom n'est pas défini
        if vals.get('chantier_id') and (not vals.get('name') or vals.get('name') == '/'):
            chantier = self.env['construction.chantier'].browse(vals['chantier_id'])
            if chantier.exists():
                vals['name'] = f"Devis - {chantier.name}"
        
        return super().create(vals)

    # =================== SYNCHRONISATION  ===================

    @api.onchange('lot_ids')
    def _onchange_lot_ids_sync(self):
        """Synchroniser lot_ids avec lot_selection_ids pour compatibilité"""
        if self.lot_ids:
            self.lot_selection_ids = self.lot_ids

    @api.onchange('lot_selection_ids') 
    def _onchange_lot_selection_ids_sync(self):
        """Synchroniser lot_selection_ids avec lot_ids pour compatibilité"""
        if self.lot_selection_ids:
            self.lot_ids = self.lot_selection_ids

    # =================== ACTIONS PRINCIPALES ===================

    def action_add_product_wizard(self):
        """Ouvrir l'assistant de sélection de produits"""
        self.ensure_one()
        
        if not self.chantier_id:
            raise ValidationError(_(
                "Veuillez d'abord sélectionner un chantier pour utiliser l'assistant."
            ))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Assistant de création de devis'),
            'res_model': 'construction.quote.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sale_order_id': self.id,
                'default_chantier_id': self.chantier_id.id,
                'default_partner_id': self.partner_id.id,
            }
        }

    def action_organize_by_lots(self):
        """Organise le devis par sections de lots"""
        self.ensure_one()
        
        if not self.lot_ids:
            raise ValidationError(_(
                "Veuillez sélectionner des lots pour organiser ce devis."
            ))
        
        self._create_lot_sections()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Devis organisé'),
                'message': _('%d section(s) créée(s) pour les lots.') % len(self.lot_ids),
                'type': 'success'
            }
        }

    def action_validate_quote(self):
        """Valide le devis et met à jour le chantier"""
        self.ensure_one()
        
        # Validation métier
        if not self.order_line.filtered(lambda l: not l.display_type):
            raise ValidationError(_(
                "Impossible de valider un devis sans ligne de produit."
            ))
        
        # Confirmation de la commande
        self.action_confirm()
        
        # Mise à jour du chantier
        if self.chantier_id:
            self._update_chantier_on_validation()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Devis validé'),
                'message': _('Le devis %s a été validé avec succès.') % self.name,
                'type': 'success'
            }
        }

    # =================== MÉTHODES PRIVÉES ===================

    def _create_lot_sections(self):
        """Crée des sections pour chaque lot dans le devis"""
        sequence = self._get_next_sequence()
        
        for lot in self.lot_ids:
            self._create_section_for_lot(lot, sequence)
            sequence += 10

    def _create_section_for_lot(self, lot, sequence):
        """Crée une section pour un lot donné"""
        section_vals = {
            'order_id': self.id,
            'display_type': 'line_section',
            'name': _('📋 %s') % lot.name,
            'sequence': sequence,
        }
        
        self.env['sale.order.line'].create(section_vals)

    def _get_next_sequence(self):
        """Retourne la prochaine séquence disponible"""
        if self.order_line:
            return max(self.order_line.mapped('sequence')) + 10
        return 10

    def _update_chantier_on_validation(self):
        """Met à jour le chantier lors de la validation du devis"""
        try:
            # Faire progresser le chantier vers l'étape "Devis accepté"
            if hasattr(self.chantier_id, 'action_move_to_next_stage'):
                self.chantier_id.action_move_to_next_stage()
                
            # Log de la validation
            self.chantier_id.message_post(
                body=_("Devis %s validé - Montant: %s") % (
                    self.name, 
                    f"{self.amount_total:,.2f} {self.currency_id.symbol}"
                ),
                message_type='notification'
            )
        except Exception as e:
            # Ne pas bloquer la validation si la mise à jour du chantier échoue
            _logger.warning(f"Erreur lors de la mise à jour du chantier: {e}")

    @api.onchange('chantier_id')
    def _onchange_chantier_id(self):
        """Mise à jour automatique lors du changement de chantier"""
        if self.chantier_id:
            # Mettre à jour le partenaire si nécessaire
            if self.chantier_id.client and not self.partner_id:
                self.partner_id = self.chantier_id.client
                
            # Pré-sélectionner les lots du chantier
            if self.chantier_id.lots_ids:
                self.lot_ids = self.chantier_id.lots_ids
                self.lot_selection_ids = self.chantier_id.lots_ids  # Sync pour compatibilité
            
            # Injecter le nom du chantier dans le nom du devis
            if not self.name or self.name == '/':
                self.name = f"Devis - {self.chantier_id.name}"


class SaleOrderLineConstruction(models.Model):
    """Extension des lignes de commande pour la construction"""
    
    _inherit = 'sale.order.line'

    # =================== CHAMPS CONSTRUCTION ===================
    
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
        help="Commentaires ou spécifications techniques"
    ) 