# -*- coding: utf-8 -*-
"""
Extension du modèle purchase.order pour la gestion des chantiers de construction
Compatible Odoo 18 - Respecte les conventions de codage officielles
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    # =================== LIENS AVEC LES CHANTIERS ===================

    chantier_id = fields.Many2one(
        'construction.chantier',
        string='Chantier',
        help="Chantier de construction lié à ce bon de commande"
    )

    # =================== CHAMPS MÉTIER CONSTRUCTION ===================

    lot_ids = fields.Many2many(
        'construction.lot',
        'purchase_order_construction_lot_rel',
        'purchase_order_id',
        'lot_id',
        string='Lots concernés',
        help="Lots de construction concernés par ce bon de commande"
    )

    # =================== WORKFLOW CONSTRUCTION ===================

    construction_state = fields.Selection([
        ('draft', 'Brouillon'),
        ('sent', 'Envoyé'),
        ('to_approve', 'À approuver'),
        ('purchase', 'Approuvé'),
        ('done', 'Terminé'),
        ('cancel', 'Annulé')
    ], string='État construction', default='draft', tracking=True)

    # =================== MÉTHODES MÉTIER ===================

    @api.onchange('chantier_id')
    def _onchange_chantier_id(self):
        """Mise à jour automatique du partenaire quand le chantier change"""
        if self.chantier_id:
            # Si le chantier a des sous-traitants, proposer le premier comme fournisseur par défaut
            if self.chantier_id.subcontractor_ids and not self.partner_id:
                self.partner_id = self.chantier_id.subcontractor_ids[0]
                
            # Pré-sélectionner les lots du chantier
            if self.chantier_id.lots_ids:
                self.lot_ids = self.chantier_id.lots_ids

    @api.constrains('chantier_id', 'lot_ids')
    def _check_lots_compatibility(self):
        """Vérifier que les lots sélectionnés appartiennent au chantier"""
        for record in self:
            if record.chantier_id and record.lot_ids:
                invalid_lots = record.lot_ids - record.chantier_id.lots_ids
                if invalid_lots:
                    raise ValidationError(
                        _("Les lots suivants ne sont pas liés au chantier sélectionné : %s")
                        % ', '.join(invalid_lots.mapped('name'))
                    )

    def action_confirm_construction(self):
        """Confirmer le bon de commande pour la construction"""
        self.ensure_one()
        
        if not self.partner_id:
            raise ValidationError(_("Veuillez sélectionner un fournisseur avant de confirmer."))
            
        if not self.order_line:
            raise ValidationError(_("Veuillez ajouter des lignes de commande avant de confirmer."))
        
        # Mettre à jour l'état
        self.write({
            'construction_state': 'sent',
            'state': 'sent'
        })
        
        # Log de la confirmation
        self.message_post(
            body=_("Bon de commande confirmé - Fournisseur: %s") % self.partner_id.name,
            message_type='notification'
        )
        
        return True

    def action_approve_construction(self):
        """Approuver le bon de commande pour la construction"""
        self.ensure_one()
        
        # Vérifications métier
        if not self.chantier_id:
            raise ValidationError(_("Ce bon de commande doit être lié à un chantier."))
            
        # Mettre à jour l'état
        self.write({
            'construction_state': 'purchase',
            'state': 'purchase'
        })
        
        # Log de l'approbation
        self.message_post(
            body=_("Bon de commande approuvé pour le chantier %s") % self.chantier_id.name,
            message_type='notification'
        )
        
        return True

    def action_done_construction(self):
        """Marquer le bon de commande comme terminé"""
        self.ensure_one()
        
        # Mettre à jour l'état
        self.write({
            'construction_state': 'done',
            'state': 'done'
        })
        
        # Log de la finalisation
        self.message_post(
            body=_("Bon de commande terminé"),
            message_type='notification'
        )
        
        return True

    # =================== MÉTHODES DE CALCUL ===================

    @api.depends('order_line.price_total')
    def _compute_amount_total_construction(self):
        """Calculer le montant total pour la construction"""
        for order in self:
            amount_total = sum(order.order_line.mapped('price_total'))
            order.amount_untaxed = amount_total

    # =================== MÉTHODES D'AFFICHAGE ===================

    def action_view_chantier(self):
        """Voir le chantier associé"""
        self.ensure_one()
        
        if not self.chantier_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'warning',
                    'message': 'Aucun chantier associé à ce bon de commande.',
                    'sticky': False,
                }
            }
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'Chantier - {self.chantier_id.name}',
            'res_model': 'construction.chantier',
            'res_id': self.chantier_id.id,
            'view_mode': 'form',
            'target': 'current',
        }