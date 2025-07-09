# -*- coding: utf-8 -*-
"""
Quote Split Wizard

This wizard helps users split construction quotes by lots and assign them to subcontractors
with a user-friendly interface.
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class QuoteSplitWizard(models.TransientModel):
    """
    Wizard for splitting construction quotes by lots.
    
    Provides a user-friendly interface to:
    - Select which quote to split
    - Review lot assignments
    - Preview the splitting results
    - Execute the split operation
    """
    _name = 'construction.quote.split.wizard'
    _description = 'Quote Split Wizard'

    # =================== FIELDS ===================
    
    chantier_id = fields.Many2one(
        'construction.chantier',
        string='Chantier',
        required=True,
        readonly=True,
        help="Construction project for quote splitting"
    )
    
    available_quote_ids = fields.Many2many(
        'sale.order',
        string='Devis disponibles',
        compute='_compute_available_quotes',
        help="Available quotes that can be split"
    )
    
    selected_quote_id = fields.Many2one(
        'sale.order',
        string='Devis à diviser',
        required=True,
        help="Main quote to split into sub-quotes"
    )
    
    lot_ids = fields.Many2many(
        'construction.lot',
        string='Lots',
        compute='_compute_lots',
        help="Construction lots that will generate sub-quotes"
    )
    
    preview_text = fields.Html(
        string='Aperçu de la division',
        compute='_compute_preview',
        help="Preview of how the quote will be split"
    )
    
    subcontractor_assignments = fields.Text(
        string='Assignations prévues',
        compute='_compute_subcontractor_assignments',
        help="Preview of subcontractor assignments"
    )
    
    state = fields.Selection([
        ('select', 'Sélection'),
        ('preview', 'Aperçu'),
        ('done', 'Terminé'),
        ('error', 'Erreur'),
    ], default='select', string='État')
    
    error_message = fields.Text(string='Message d\'erreur')
    result_message = fields.Text(string='Résultat')
    created_subquote_ids = fields.Many2many('sale.order', string='Sous-devis créés')

    # =================== COMPUTED FIELDS ===================

    @api.depends('chantier_id')
    def _compute_available_quotes(self):
        """Compute available quotes that can be split."""
        for wizard in self:
            if wizard.chantier_id:
                quotes = self.env['sale.order'].search([
                    ('chantier_id', '=', wizard.chantier_id.id),
                    ('state', 'in', ['sale', 'done']),
                    ('origin', '=', False),  # Only main quotes, not sub-quotes
                ])
                wizard.available_quote_ids = quotes
            else:
                wizard.available_quote_ids = False

    @api.depends('selected_quote_id')
    def _compute_lots(self):
        """Compute lots from the selected quote."""
        for wizard in self:
            if wizard.selected_quote_id:
                wizard.lot_ids = wizard.selected_quote_id.lot_ids
            else:
                wizard.lot_ids = False

    @api.depends('selected_quote_id', 'lot_ids')
    def _compute_preview(self):
        """Generate preview of quote splitting."""
        for wizard in self:
            if wizard.selected_quote_id and wizard.lot_ids:
                # Simulate the split to generate preview
                preview_html = wizard._generate_split_preview()
                wizard.preview_text = preview_html
            else:
                wizard.preview_text = _("<p>Sélectionnez un devis pour voir l'aperçu.</p>")

    @api.depends('chantier_id', 'lot_ids')
    def _compute_subcontractor_assignments(self):
        """Compute subcontractor assignment preview."""
        for wizard in self:
            if wizard.chantier_id and wizard.lot_ids:
                assignments = []
                for lot in wizard.lot_ids:
                    specialized_subs = wizard.chantier_id.subcontractors.filtered(
                        lambda s: lot in s.lot_ids
                    )
                    if specialized_subs:
                        assignments.append(f"• {lot.name} → {specialized_subs[0].name}")
                    else:
                        assignments.append(f"• {lot.name} → ⚠️ Aucun sous-traitant spécialisé")
                
                wizard.subcontractor_assignments = "\n".join(assignments) if assignments else "Aucune assignation possible"
            else:
                wizard.subcontractor_assignments = ""

    # =================== ACTIONS ===================

    def action_preview_split(self):
        """Preview the quote splitting."""
        self.ensure_one()
        
        if not self.selected_quote_id:
            raise ValidationError(_("Veuillez sélectionner un devis à diviser."))
        
        # Validate prerequisites
        can_split = self.env['quote.split.service'].can_split_quote(self.chantier_id.id)
        if not can_split:
            self.state = 'error'
            self.error_message = _("La division de devis n'est pas disponible pour ce chantier.")
            return self._reload_wizard()
        
        self.state = 'preview'
        return self._reload_wizard()

    def action_execute_split(self):
        """Execute the quote splitting."""
        self.ensure_one()
        
        if self.state != 'preview':
            raise ValidationError(_("Veuillez d'abord prévisualiser la division."))
        
        # Execute the split using the service
        result = self.env['quote.split.service'].split_quote_by_lots(
            self.chantier_id.id, 
            self.selected_quote_id.id
        )
        
        if result['success']:
            self.state = 'done'
            self.result_message = result['message']
            self.created_subquote_ids = [(6, 0, result['created_subquotes'])]
        else:
            self.state = 'error'
            self.error_message = result['message']
        
        return self._reload_wizard()

    def action_view_subquotes(self):
        """View the created sub-quotes."""
        self.ensure_one()
        
        if not self.created_subquote_ids:
            raise ValidationError(_("Aucun sous-devis n'a été créé."))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sous-devis créés'),
            'res_model': 'sale.order',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.created_subquote_ids.ids)],
            'context': {
                'search_default_group_by_partner': 1,
            },
            'target': 'current',
        }

    def action_back_to_select(self):
        """Go back to selection step."""
        self.ensure_one()
        self.state = 'select'
        self.error_message = False
        return self._reload_wizard()

    # =================== PRIVATE METHODS ===================

    def _reload_wizard(self):
        """Reload the wizard to show updated state."""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Division de devis'),
            'res_model': 'construction.quote.split.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }

    def _generate_split_preview(self):
        """Generate HTML preview of the quote split."""
        if not self.selected_quote_id or not self.lot_ids:
            return "<p>Aucun aperçu disponible.</p>"
        
        # Simulate the analysis
        service = self.env['quote.split.service']
        lot_groups = service._analyze_quote_structure(self.selected_quote_id)
        
        html = ["<div class='o_quote_split_preview'>"]
        html.append(f"<h4>📋 Devis : {self.selected_quote_id.name}</h4>")
        html.append(f"<p><strong>Total :</strong> {self.selected_quote_id.amount_total:,.2f} {self.selected_quote_id.currency_id.symbol}</p>")
        
        if lot_groups:
            html.append("<h5>🔀 Division prévue :</h5>")
            html.append("<table class='table table-sm'>")
            html.append("<thead><tr><th>Lot</th><th>Lignes</th><th>Montant</th></tr></thead>")
            html.append("<tbody>")
            
            for lot_id, data in lot_groups.items():
                lot = self.env['construction.lot'].browse(lot_id)
                line_count = len(data.get('lines', []))
                total = data.get('total', 0.0)
                
                html.append(f"<tr>")
                html.append(f"<td><span class='badge badge-info'>{lot.name}</span></td>")
                html.append(f"<td>{line_count} ligne(s)</td>")
                html.append(f"<td>{total:,.2f} {self.selected_quote_id.currency_id.symbol}</td>")
                html.append(f"</tr>")
            
            html.append("</tbody></table>")
        else:
            html.append("<div class='alert alert-warning'>")
            html.append("⚠️ Aucun contenu spécifique aux lots détecté dans le devis.")
            html.append("</div>")
        
        html.append("</div>")
        return "".join(html)

    @api.model
    def default_get(self, fields_list):
        """Set default values from context."""
        defaults = super().default_get(fields_list)
        
        # Get chantier from context
        chantier_id = self.env.context.get('default_chantier_id')
        if chantier_id:
            defaults['chantier_id'] = chantier_id
        
        return defaults 