# -*- coding: utf-8 -*-
"""
Wizard pour sélectionner le devis principal d'un chantier
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ConstructionQuoteSelectionWizard(models.TransientModel):
    """Wizard pour sélectionner le devis principal d'un chantier"""
    
    _name = 'construction.quote.selection.wizard'
    _description = 'Sélection du devis principal'

    chantier_id = fields.Many2one(
        'construction.chantier',
        string='Chantier',
        required=True,
        readonly=True
    )
    
    quote_ids = fields.Many2many(
        'sale.order',
        string='Devis disponibles',
        readonly=True,
        help="Liste des devis disponibles pour ce chantier"
    )
    
    selected_quote_id = fields.Many2one(
        'sale.order',
        string='Devis principal',
        required=True,
        help="Sélectionnez le devis qui servira de référence pour le calcul des prix des lots"
    )

    @api.onchange('chantier_id')
    def _onchange_chantier_id(self):
        """Filtrer les devis selon le chantier"""
        if self.chantier_id:
            quotes = self.env['sale.order'].search([
                ('chantier_id', '=', self.chantier_id.id),
                ('state', 'in', ['draft', 'sent', 'sale'])
            ])
            self.quote_ids = [(6, 0, quotes.ids)]
            
            # Domaine pour selected_quote_id
            return {
                'domain': {
                    'selected_quote_id': [('id', 'in', quotes.ids)]
                }
            }

    def action_validate_selection(self):
        """Valider la sélection du devis principal"""
        self.ensure_one()
        
        if not self.selected_quote_id:
            raise ValidationError(_("Veuillez sélectionner un devis."))
        
        # Définir le devis principal
        self.chantier_id.main_quote_id = self.selected_quote_id
        
        # Mettre à jour les prix des lots
        self.chantier_id._update_lots_prices_from_quote()
        
        # Message de confirmation
        self.chantier_id.message_post(
            body=_("📋 Devis principal sélectionné: %s<br/>💰 Prix des lots mis à jour automatiquement.") % self.selected_quote_id.name,
            message_type='notification'
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Devis principal sélectionné'),
                'message': _('Le devis %s a été défini comme devis principal et les prix des lots ont été mis à jour.') % self.selected_quote_id.name,
                'type': 'success'
            }
        }
