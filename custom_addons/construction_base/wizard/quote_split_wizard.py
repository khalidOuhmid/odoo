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

    # =================== NOUVEAUX CHAMPS ===================
    
    suggested_subcontractors = fields.Many2many(
        'res.partner',
        'split_wizard_suggested_subcontractors_rel',
        string='Sous-traitants suggérés',
        help="Sous-traitants spécialisés disponibles mais non assignés au chantier"
    )
    
    assignment_warnings = fields.Html(
        string='Avertissements d\'assignation',
        compute='_compute_assignment_warnings',
        help="Avertissements sur les assignations automatiques"
    )
    
    show_suggestions = fields.Boolean(
        string='Afficher les suggestions',
        default=False,
        help="Afficher la section des sous-traitants suggérés"
    )
    
    auto_assign_suggested = fields.Boolean(
        string='Assigner automatiquement les suggérés',
        default=True,
        help="Assigner automatiquement les sous-traitants suggérés au chantier"
    )

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

    @api.depends('chantier_id', 'lot_ids')
    def _compute_assignment_warnings(self):
        """Calcule les avertissements d'assignation."""
        for wizard in self:
            if not wizard.chantier_id or not wizard.lot_ids:
                wizard.assignment_warnings = ""
                continue
                
            warnings = []
            suggestions = []
            
            for lot in wizard.lot_ids:
                # Vérifier si des spécialistes sont assignés au chantier
                chantier_specialists = wizard.chantier_id.subcontractor_ids.filtered(
                    lambda s: lot in s.speciality_ids
                )
                
                if not chantier_specialists:
                    # Chercher des spécialistes disponibles
                    available_specialists = wizard.env['res.partner'].search([
                        ('is_subcontractor', '=', True),
                        ('speciality_ids', 'in', lot.id)
                    ])
                    
                    if available_specialists:
                        suggestions.extend(available_specialists)
                        warnings.append(
                            f"⚠️ <strong>{lot.name}</strong> : Aucun spécialiste assigné au chantier. "
                            f"{len(available_specialists)} spécialiste(s) disponible(s)."
                        )
                    else:
                        warnings.append(
                            f"❌ <strong>{lot.name}</strong> : Aucun spécialiste trouvé dans la base."
                        )
                else:
                    warnings.append(
                        f"✅ <strong>{lot.name}</strong> : "
                        f"{len(chantier_specialists)} spécialiste(s) assigné(s)."
                    )
            
            # Mettre à jour les suggestions
            wizard.suggested_subcontractors = [(6, 0, list(set([s.id for s in suggestions])))]
            wizard.show_suggestions = bool(suggestions)
            
            # Générer le HTML d'avertissement
            if warnings:
                wizard.assignment_warnings = "<div class='alert alert-info'>" + "<br/>".join(warnings) + "</div>"
            else:
                wizard.assignment_warnings = ""

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

    def action_assign_suggested_subcontractors(self):
        """Assigner automatiquement les sous-traitants suggérés au chantier."""
        self.ensure_one()
        
        if not self.suggested_subcontractors:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Information',
                    'message': 'Aucun sous-traitant suggéré à assigner.',
                    'type': 'info'
                }
            }
        
        # Ajouter les sous-traitants suggérés au chantier
        self.chantier_id.write({
            'subcontractor_ids': [(4, sub.id) for sub in self.suggested_subcontractors]
        })
        
        # Log de l'action
        self.chantier_id.message_post(
            body=f"🔗 {len(self.suggested_subcontractors)} sous-traitant(s) spécialisé(s) "
                 f"automatiquement assigné(s) au chantier : "
                 f"{', '.join(self.suggested_subcontractors.mapped('name'))}",
            message_type='notification'
        )
        
        # Recalculer les avertissements
        self._compute_assignment_warnings()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Assignation réussie',
                'message': f'{len(self.suggested_subcontractors)} sous-traitant(s) assigné(s) au chantier.',
                'type': 'success'
            }
        }

    def action_execute_split(self):
        """Execute the quote splitting with improved logic."""
        self.ensure_one()
        
        if self.state != 'preview':
            raise ValidationError(_("Veuillez d'abord prévisualiser la division."))
        
        # 1. Auto-assigner les sous-traitants suggérés si demandé
        if self.auto_assign_suggested and self.suggested_subcontractors:
            self.action_assign_suggested_subcontractors()
        
        # 2. Exécuter la division en utilisant le service amélioré
        result = self.env['quote.split.service'].split_quote_by_lots(
            self.chantier_id.id, 
            self.selected_quote_id.id
        )
        
        if result['success']:
            self.state = 'done'
            
            # 3. Analyser les résultats d'assignation
            assignment_summary = self._generate_assignment_summary(result)
            self.result_message = result['message'] + "\n\n" + assignment_summary
            self.created_subquote_ids = [(6, 0, result['created_subquotes'])]
            
            # 4. Log détaillé sur le chantier
            self.chantier_id.message_post(
                body=f"📋 Division de devis terminée avec succès :\n"
                     f"• Devis principal : {self.selected_quote_id.name}\n"
                     f"• {len(result['created_subquotes'])} sous-devis créés\n"
                     f"• Assignations automatiques : {assignment_summary}",
                message_type='comment'
            )
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

    def _generate_assignment_summary(self, split_result):
        """Génère un résumé des assignations."""
        if 'assignment_results' not in split_result:
            return "Aucune information d'assignation disponible."
        
        assigned_count = 0
        unassigned_count = 0
        suggestions_count = 0
        
        for assignment in split_result['assignment_results']:
            if assignment.get('assigned'):
                assigned_count += 1
            else:
                unassigned_count += 1
                if assignment.get('suggested_subcontractors'):
                    suggestions_count += len(assignment['suggested_subcontractors'])
        
        summary = []
        if assigned_count > 0:
            summary.append(f"✅ {assigned_count} assigné(s) automatiquement")
        if unassigned_count > 0:
            summary.append(f"⚠️ {unassigned_count} non assigné(s)")
        if suggestions_count > 0:
            summary.append(f"💡 {suggestions_count} suggestion(s) disponible(s)")
        
        return " • ".join(summary) if summary else "Aucune assignation effectuée"

    @api.model
    def default_get(self, fields_list):
        """Set default values from context."""
        defaults = super().default_get(fields_list)
        
        # Get chantier from context
        chantier_id = self.env.context.get('default_chantier_id')
        if chantier_id:
            defaults['chantier_id'] = chantier_id
        
        return defaults 