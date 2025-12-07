# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class ConstructionLot(models.Model):
    """
    Work Package (Lot) - Budgetary and Operational Unit.
    
    Represents a specific trade or phase of work (e.g., "Lot 01 - Earthworks").
    It acts as a cost center and grouping entity for planning tasks.
    
    Inherits:
    - construction.date.mixin: Inherits Start/End dates, but bound to Chantier logic.
    """
    _name = 'construction.lot'
    _description = 'Work Package (Lot)'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'construction.date.mixin']
    _order = 'sequence, id'

    name = fields.Char(string='Désignation', required=True, translate=True)
    sequence = fields.Integer(default=10, index=True)
    
    chantier_id = fields.Many2one(
        'construction.chantier',
        string='Chantier',
        required=True,
        ondelete='cascade',
        index=True
    )
    
    code = fields.Char(string='Code Lot', help="ex: 01, 12B")
    
    # ==============================================================================================
    #                                      RESOURCES & SUBCONTRACTING
    # ==============================================================================================
    
    subcontractor_id = fields.Many2one(
        'res.partner',
        string='Sous-Traitant',
        tracking=True
    )
    
    product_category_id = fields.Many2one(
        'product.category',
        string='Corps d\'état',
        help="Lien vers les catégories de produits Odoo."
    )

    # ==============================================================================================
    #                                      BUDGET & FINANCE
    # ==============================================================================================
    
    currency_id = fields.Many2one(related='chantier_id.currency_id')
    
    budget_amount = fields.Monetary(string='Budget Initial', tracking=True)
    
    # These will be computed by linking to Purchase Lines -> Analytic Account in future phases
    cost_committed = fields.Monetary(string='Engagé', compute='_compute_costs', store=True)
    cost_actual = fields.Monetary(string='Réalisé', compute='_compute_costs', store=True)
    
    @api.depends('chantier_id') # Placeholder dependencies, will be real with purchase module
    def _compute_costs(self):
        for lot in self:
            # Future implementation: Sum of Purchase Orders lines linked to this Lot
            lot.cost_committed = 0.0
            lot.cost_actual = 0.0
            
    def name_get(self):
        result = []
        for rec in self:
            name = f"{rec.code or ''} {rec.name}".strip()
            result.append((rec.id, name))
        return result
