# -*- coding: utf-8 -*-
"""
Wizard Assignment Sous-traitant aux Lots
Inspired by SAP: Strict validation, hierarchical workflow
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class LotSubcontractorAssignWizard(models.TransientModel):
    _name = 'construction.lot.subcontractor.assign.wizard'
    _description = 'Assigner Sous-traitant aux Lots'

    # ============= Selection Mode ============= #
    selection_mode = fields.Selection([
        ('single', 'Lot Unique'),
        ('multiple', 'Lots Multiples'),
        ('category', 'Par Catégorie')
    ], string='Mode de Sélection', default='single', required=True)

    # ============= Lot Selection ============= #
    lot_id = fields.Many2one('construction.lot', string='Lot', 
                             help="Sélection d'un lot unique")
    # ARCHITECTURAL FIX: Explicit relation table name (PostgreSQL 63-char limit)
    lot_ids = fields.Many2many(
        'construction.lot',
        'wizard_lot_selection_rel',  # Explicit: 24 chars
        'wizard_id',
        'lot_id',
        string='Lots',
        help="Sélection de plusieurs lots"
    )
    category_id = fields.Many2one('construction.lot.category', string='Catégorie',
                                  help="Tous les lots de cette catégorie")
    
    # ============= Chantier Context ============= #
    chantier_id = fields.Many2one('construction.chantier', string='Chantier', required=True)
    
    # ============= Subcontractor ============= #
    subcontractor_id = fields.Many2one('res.partner', string='Sous-traitant', required=True,
                                       domain="[('supplier_rank', '>', 0)]")
    
    # ============= Assignment Details ============= #
    assignment_date = fields.Date(string='Date d\'Assignment', default=fields.Date.today, required=True)
    notes = fields.Text(string='Notes Internes')
    
    # ============= Computed Fields ============= #
    # ARCHITECTURAL FIX: Explicit relation table names to respect PostgreSQL 63-char limit
    affected_lot_count = fields.Integer(string='Nombre de Lots', compute='_compute_affected_lots')
    affected_lot_ids = fields.Many2many(
        'construction.lot', 
        'lot_subcontractor_wizard_rel',  # Explicit: 28 chars (was 67!)
        'wizard_id', 
        'lot_id',
        string='Lots Affectés', 
        compute='_compute_affected_lots'
    )

    # ============= SAP-like Validation ============= #
    warning_message = fields.Html(string='Avertissements', compute='_compute_warnings')
    has_warnings = fields.Boolean(compute='_compute_warnings')

    @api.model
    def default_get(self, fields):
        """Initialize wizard with context."""
        res = super().default_get(fields)
        
        # Get chantier from context
        if self.env.context.get('active_model') == 'construction.chantier':
            res['chantier_id'] = self.env.context.get('active_id')
        elif self.env.context.get('active_model') == 'construction.lot':
            lot = self.env['construction.lot'].browse(self.env.context.get('active_id'))
            res['chantier_id'] = lot.chantier_id.id
            res['lot_id'] = lot.id
            res['selection_mode'] = 'single'
            
        return res

    @api.depends('selection_mode', 'lot_id', 'lot_ids', 'category_id', 'chantier_id')
    def _compute_affected_lots(self):
        """Compute which lots will be affected."""
        for wizard in self:
            lots = self.env['construction.lot']
            
            if wizard.selection_mode == 'single' and wizard.lot_id:
                lots = wizard.lot_id
            elif wizard.selection_mode == 'multiple' and wizard.lot_ids:
                lots = wizard.lot_ids
            elif wizard.selection_mode == 'category' and wizard.category_id:
                lots = self.env['construction.lot'].search([
                    ('chantier_id', '=', wizard.chantier_id.id),
                    ('category_id', '=', wizard.category_id.id)
                ])
            
            wizard.affected_lot_ids = lots
            wizard.affected_lot_count = len(lots)

    @api.depends('affected_lot_ids', 'subcontractor_id')
    def _compute_warnings(self):
        """SAP-like: Compute warnings for user validation."""
        for wizard in self:
            warnings = []
            
            # Check if lots already have subcontractors
            lots_with_subcontractors = wizard.affected_lot_ids.filtered(lambda l: l.subcontractor_ids)
            if lots_with_subcontractors:
                warnings.append(f"<li><b>{len(lots_with_subcontractors)}</b> lot(s) ont déjà des sous-traitants assignés. Ils seront remplacés.</li>")
            
            # Check if subcontractor is already assigned to chantier
            if wizard.subcontractor_id in wizard.chantier_id.subcontractor_ids:
                warnings.append(f"<li>Le sous-traitant <b>{wizard.subcontractor_id.name}</b> est déjà assigné au chantier.</li>")
            
            # Check if subcontractor has SIREN
            if not wizard.subcontractor_id.siren:
                warnings.append(f"<li>⚠️ Le sous-traitant n'a pas de SIREN renseigné (requis pour conformité légale).</li>")
            
            if warnings:
                wizard.warning_message = "<ul>" + "".join(warnings) + "</ul>"
                wizard.has_warnings = True
            else:
                wizard.warning_message = False
                wizard.has_warnings = False

    @api.onchange('selection_mode')
    def _onchange_selection_mode(self):
        """Clear selections when mode changes."""
        self.lot_id = False
        self.lot_ids = False
        self.category_id = False

    def action_assign(self):
        """Assign subcontractor to selected lots."""
        self.ensure_one()
        
        if not self.affected_lot_ids:
            raise UserError(_("Aucun lot sélectionné."))
        
        # Log assignment for audit trail
        assignment_message = _(
            "<b>Sous-traitant assigné:</b> %s<br/>"
            "<b>Date:</b> %s<br/>"
            "<b>Lots affectés:</b> %s<br/>"
            "<b>Assigné par:</b> %s"
        ) % (
            self.subcontractor_id.name,
            self.assignment_date,
            ', '.join(self.affected_lot_ids.mapped('name')),
            self.env.user.name
        )
        
        if self.notes:
            assignment_message += f"<br/><b>Notes:</b> {self.notes}"
        
        # Assign subcontractor to lots
        for lot in self.affected_lot_ids:
            # Replace existing subcontractors
            lot.subcontractor_ids = [(6, 0, [self.subcontractor_id.id])]
            
            # Post message on lot
            lot.message_post(
                body=assignment_message,
                subject="Assignment Sous-traitant"
            )
        
        # Add subcontractor to chantier if not already there
        if self.subcontractor_id not in self.chantier_id.subcontractor_ids:
            self.chantier_id.subcontractor_ids = [(4, self.subcontractor_id.id)]
        
        # Post message on chantier
        self.chantier_id.message_post(
            body=assignment_message,
            subject="Assignment Sous-traitant"
        )
        
        return {'type': 'ir.actions.act_window_close'}
