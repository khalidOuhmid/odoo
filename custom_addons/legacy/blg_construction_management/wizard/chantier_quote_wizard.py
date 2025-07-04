# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta


class BlgChantierQuoteWizard(models.TransientModel):
    """Wizard pour créer un devis à partir d'un chantier avec ses lots"""
    _name = 'blg.chantier.quote.wizard'
    _description = 'Assistant Création Devis Chantier'

    chantier_id = fields.Many2one('blg.chantier', string='Chantier', required=True, readonly=True)
    client_id = fields.Many2one('res.partner', string='Client', required=True)
    
    # FIX: Simplify the lots relationship to avoid errors
    available_lot_ids = fields.Many2many(
        'blg_contacts_extension.lot', 
        'wizard_available_lot_rel',
        string='Lots disponibles', 
        readonly=True,
        help="Lots définis pour ce chantier"
    )
    selected_lot_ids = fields.Many2many(
        'blg_contacts_extension.lot', 
        'wizard_selected_lot_rel',
        string='Lots à inclure dans le devis',
        help="Sélectionnez les lots pour lesquels vous voulez créer le devis"
    )
    
    # Informations du devis
    quote_name = fields.Char('Nom du devis', compute='_compute_quote_name', store=True)
    validity_days = fields.Integer('Validité (jours)', default=30)
    note = fields.Html('Conditions particulières')
    
    # Options
    create_sections = fields.Boolean('Créer des sections par lot', default=True,
                                   help="Organiser le devis avec une section par lot")
    open_product_selection = fields.Boolean('Ouvrir la sélection de produits', default=True,
                                          help="Ouvrir directement l'assistant de sélection de produits")

    @api.depends('chantier_id', 'client_id')
    def _compute_quote_name(self):
        for wizard in self:
            if wizard.chantier_id and wizard.client_id:
                wizard.quote_name = f"Devis {wizard.chantier_id.name} - {wizard.client_id.name}"
            else:
                wizard.quote_name = "Nouveau devis"

    @api.onchange('chantier_id')
    def _onchange_chantier_id(self):
        """Remplir automatiquement les lots disponibles"""
        if self.chantier_id:
            # Get client from chantier
            if self.chantier_id.client_id:
                self.client_id = self.chantier_id.client_id.id
            
            # Get lots from chantier lot_ids - SAFER APPROACH
            lot_ids = []
            try:
                if hasattr(self.chantier_id, 'lot_ids') and self.chantier_id.lot_ids:
                    lot_ids = self.chantier_id.lot_ids.mapped('lot_id').filtered(lambda x: x).ids
                
                if lot_ids:
                    self.available_lot_ids = [(6, 0, lot_ids)]
                    self.selected_lot_ids = [(6, 0, lot_ids)]  # Sélectionner tous par défaut
                else:
                    # If no lots defined, get all active lots
                    all_lots = self.env['blg_contacts_extension.lot'].search([('active', '=', True)])
                    self.available_lot_ids = [(6, 0, all_lots.ids)]
                    
            except Exception as e:
                # Fallback: get all lots
                all_lots = self.env['blg_contacts_extension.lot'].search([('active', '=', True)])
                self.available_lot_ids = [(6, 0, all_lots.ids)]

    def action_create_quote(self):
        """Créer le devis avec les lots sélectionnés"""
        if not self.selected_lot_ids:
            raise ValidationError("Veuillez sélectionner au moins un lot pour le devis.")

        # Créer le devis
        quote_vals = {
            'partner_id': self.client_id.id,
            'blg_chantier_id': self.chantier_id.id,
            'lot_selection_ids': [(6, 0, self.selected_lot_ids.ids)],
            'validity_date': fields.Date.today() + timedelta(days=self.validity_days),
            'note': self.note or '',
        }
        
        quote = self.env['sale.order'].create(quote_vals)
        
        # Créer les sections par lot si demandé
        if self.create_sections:
            sequence = 10
            for lot in self.selected_lot_ids.sorted('sequence'):
                section_vals = {
                    'order_id': quote.id,
                    'display_type': 'line_section',
                    'name': f"📋 {lot.name} ({lot.code or ''})",
                    'sequence': sequence,
                }
                self.env['sale.order.line'].create(section_vals)
                sequence += 10

        # Retourner vers la sélection de produits ou le devis
        if self.open_product_selection and self.selected_lot_ids:
            # Ouvrir la sélection pour le premier lot
            first_lot = self.selected_lot_ids.sorted('sequence')[0]
            return {
                'name': f'Sélection de produits - {first_lot.name}',
                'type': 'ir.actions.act_window',
                'res_model': 'blg.product.selection.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_lot_id': first_lot.id,
                    'default_order_id': quote.id,
                    'chantier_lot_ids': self.selected_lot_ids.ids,
                    'current_lot_index': 0,
                }
            }
        else:
            # Ouvrir directement le devis
            return {
                'name': 'Nouveau devis',
                'type': 'ir.actions.act_window',
                'res_model': 'sale.order',
                'res_id': quote.id,
                'view_mode': 'form',
                'target': 'current',
            }
