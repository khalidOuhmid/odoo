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
        """Synchronize lot_ids with lot_selection_ids for compatibility"""
        if self.lot_ids and not getattr(self, '_syncing', False):
            self._syncing = True
            self.lot_selection_ids = self.lot_ids
            self._syncing = False

    @api.onchange('lot_selection_ids') 
    def _onchange_lot_selection_ids_sync(self):
        """Synchronize lot_selection_ids with lot_ids for compatibility"""
        if self.lot_selection_ids and not getattr(self, '_syncing', False):
            self._syncing = True
            self.lot_ids = self.lot_selection_ids
            self._syncing = False

    # =================== ACTIONS PRINCIPALES ===================

    def action_add_product_wizard(self):
        """Open the product selection assistant"""
        self.ensure_one()
        
        if not self.chantier_id:
            raise ValidationError(_(
                "Veuillez d'abord sélectionner un chantier pour utiliser l'assistant."
            ))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Assistant de Création de Devis'),
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
        """Organize the quote by lot sections"""
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
                'title': _('Devis Organisé'),
                'message': _('%d section(s) créée(s) pour les lots.') % len(self.lot_ids),
                'type': 'success'
            }
        }

    def action_validate_quote(self):
        """Validate the quote and update the construction site"""
        self.ensure_one()
        
        # Business validation
        if not self.order_line.filtered(lambda l: not l.display_type):
            raise ValidationError(_(
                "Impossible de valider un devis sans ligne de produit."
            ))
        
        # Confirm the order
        self.action_confirm()
        
        # Update the construction site
        if self.chantier_id:
            self._update_chantier_on_validation()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Devis Validé'),
                'message': _('Le devis %s a été validé avec succès.') % self.name,
                'type': 'success'
            }
        }

    # =================== MÉTHODES PRIVÉES ===================

    def _create_lot_sections(self):
        """Create sections for each lot in the quote"""
        sequence = self._get_next_sequence()
        
        for lot in self.lot_ids:
            self._create_section_for_lot(lot, sequence)
            sequence += 10

    def _create_section_for_lot(self, lot, sequence):
        """Create a section for a given lot"""
        section_vals = {
            'order_id': self.id,
            'display_type': 'line_section',
            'name': _('Lot : %s') % lot.name,
            'sequence': sequence,
        }
        
        self.env['sale.order.line'].create(section_vals)

    def _get_next_sequence(self):
        """Return the next available sequence"""
        if self.order_line:
            return max(self.order_line.mapped('sequence')) + 10
        return 10

    def _update_chantier_on_validation(self):
        """Update the construction site when validating the quote"""
        try:
            # Move the construction site to the next stage
            if hasattr(self.chantier_id, 'action_move_to_next_stage'):
                self.chantier_id.action_move_to_next_stage()
                
            # Log the validation
            self.chantier_id.message_post(
                body=_("Devis %s validé - Montant : %s") % (
                    self.name, 
                    f"{self.amount_total:,.2f} {self.currency_id.symbol}"
                ),
                message_type='notification'
            )
        except AttributeError as e:
            # Method not available on construction site
            _logger.warning(f"Method not available on construction site: {e}")
        except Exception as e:
            # Don't block validation if construction site update fails
            _logger.error(f"Error updating construction site: {e}")
            # Re-raise the exception to ensure it's logged properly
            raise

    @api.onchange('chantier_id')
    def _onchange_chantier_id(self):
        """Automatic update when changing construction site"""
        if self.chantier_id:
            # Update partner if necessary
            if self.chantier_id.client and not self.partner_id:
                self.partner_id = self.chantier_id.client
                
            # Pre-select construction site lots
            if self.chantier_id.lots_ids:
                self.lot_ids = self.chantier_id.lots_ids
                self.lot_selection_ids = self.chantier_id.lots_ids  # Sync for compatibility
            
            # Inject construction site name into quote name
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