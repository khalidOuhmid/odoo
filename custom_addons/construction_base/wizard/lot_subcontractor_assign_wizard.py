# -*- coding: utf-8 -*-
"""
Wizard simple pour assigner un sous-traitant à un lot.
Ce wizard est utilisé quand plusieurs sous-traitants spécialisés sont disponibles.
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class LotSubcontractorAssignWizard(models.TransientModel):
    """Wizard pour assigner un sous-traitant à un lot."""
    
    _name = 'lot.subcontractor.assign.wizard'
    _description = 'Assignation de sous-traitant à un lot'

    # =================== CHAMPS PRINCIPAUX ===================
    
    lot_id = fields.Many2one(
        'construction.lot',
        string='Lot',
        required=True,
        readonly=True,
        help="Lot auquel assigner un sous-traitant"
    )
    
    chantier_id = fields.Many2one(
        'construction.chantier',
        string='Chantier',
        required=True,
        readonly=True,
        help="Chantier concerné"
    )
    
    available_subcontractor_ids = fields.Many2many(
        'res.partner',
        'wizard_available_subcontractors_rel',
        string='Sous-traitants disponibles',
        readonly=True,
        help="Sous-traitants spécialisés disponibles"
    )
    
    selected_subcontractor_id = fields.Many2one(
        'res.partner',
        string='Sous-traitant sélectionné',
        required=True,
        domain="[('id', 'in', available_subcontractor_ids)]",
        help="Choisissez le sous-traitant à assigner"
    )
    
    add_to_chantier = fields.Boolean(
        string='Ajouter au chantier',
        default=False,
        help="Ajouter également ce sous-traitant au chantier"
    )
    
    # =================== CHAMPS D'INFORMATION ===================
    
    subcontractor_info = fields.Html(
        string='Informations',
        compute='_compute_subcontractor_info',
        help="Informations sur le sous-traitant sélectionné"
    )
    
    # =================== COMPUTED FIELDS ===================

    @api.depends('selected_subcontractor_id')
    def _compute_subcontractor_info(self):
        """Calculer les informations du sous-traitant sélectionné."""
        for wizard in self:
            if wizard.selected_subcontractor_id:
                sub = wizard.selected_subcontractor_id
                
                # Construire le HTML d'information
                html = ["<div class='subcontractor_info'>"]
                
                # Spécialités
                if sub.speciality_ids:
                    html.append("<p><strong>🏗️ Spécialités :</strong> ")
                    html.append(", ".join(sub.speciality_ids.mapped('name')))
                    html.append("</p>")
                
                # Contact
                if sub.phone or sub.email:
                    html.append("<p><strong>📞 Contact :</strong> ")
                    if sub.phone:
                        html.append(f"{sub.phone}")
                    if sub.email:
                        html.append(f" - {sub.email}")
                    html.append("</p>")
                
                # Statut documents
                if hasattr(sub, 'documents_complete'):
                    if sub.documents_complete:
                        html.append("<p class='text-success'><strong>✅ Documents :</strong> Complets</p>")
                    else:
                        html.append("<p class='text-warning'><strong>⚠️ Documents :</strong> Incomplets</p>")
                
                # Autres chantiers
                other_chantiers = self.env['construction.chantier'].search([
                    ('subcontractor_ids', 'in', sub.id),
                    ('id', '!=', wizard.chantier_id.id)
                ])
                if other_chantiers:
                    html.append(f"<p><strong>🏗️ Autres chantiers :</strong> {len(other_chantiers)} chantier(s)</p>")
                
                html.append("</div>")
                wizard.subcontractor_info = "".join(html)
            else:
                wizard.subcontractor_info = "<p>Sélectionnez un sous-traitant pour voir ses informations.</p>"

    # =================== ACTIONS ===================

    def action_assign_subcontractor(self):
        """Assigner le sous-traitant sélectionné au lot."""
        self.ensure_one()
        
        if not self.selected_subcontractor_id:
            raise ValidationError(_("Veuillez sélectionner un sous-traitant."))
        
        # Ajouter au chantier si demandé
        if self.add_to_chantier:
            self.chantier_id.subcontractor_ids = [(4, self.selected_subcontractor_id.id)]
            
            self.chantier_id.message_post(
                body=f"🔗 Sous-traitant {self.selected_subcontractor_id.name} ajouté au chantier",
                message_type='notification'
            )
        
        # Assigner au lot
        self.lot_id.subcontractor_ids = [(4, self.selected_subcontractor_id.id)]
        
        # Log sur le chantier
        self.chantier_id.message_post(
            body=f"👷 Sous-traitant {self.selected_subcontractor_id.name} assigné au lot '{self.lot_id.name}'",
            message_type='notification'
        )
        
        # Notification de succès
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Assignation réussie',
                'message': f'{self.selected_subcontractor_id.name} a été assigné au lot "{self.lot_id.name}".',
                'type': 'success',
                'next': {'type': 'ir.actions.act_window_close'}
            }
        }

    @api.model
    def default_get(self, fields_list):
        """Valeurs par défaut depuis le contexte."""
        defaults = super().default_get(fields_list)
        
        # Récupérer les valeurs du contexte
        for field in ['lot_id', 'chantier_id', 'add_to_chantier']:
            context_key = f'default_{field}'
            if context_key in self.env.context:
                defaults[field] = self.env.context[context_key]
        
        # Gérer le Many2many spécialement
        if 'default_available_subcontractor_ids' in self.env.context:
            defaults['available_subcontractor_ids'] = self.env.context['default_available_subcontractor_ids']
        
        return defaults 