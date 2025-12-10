# -*- coding: utf-8 -*-
"""
Lot management for Construction Projects.
Includes Master Data (Category) and Project Instances (Lot).
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class LotCategory(models.Model):
    """
    Standard definitions of Lots (Master Data).
    Example: 01 - Gros Oeuvre, 02 - Electricité.
    """
    _name = 'construction.lot.category'
    _description = 'Catégorie de Lot'
    _order = 'code, name'

    name = fields.Char(string='Nom', required=True, translate=True)
    code = fields.Char(string='Code', required=True, help="Code unique (ex: 01)")
    urssaf_code = fields.Char(string='Code URSSAF', help="Code URSSAF pour les contrats")
    color = fields.Integer(string='Couleur', default=0)
    
    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Le code de catégorie doit être unique.'),
    ]


class Lot(models.Model):
    """
    A specific Lot instance on a Construction Site (Chantier).
    Links a Lot Category to a Site with specific Subcontractors.
    
    Completion is percentage-based (0-100%) and contributes to overall
    chantier progress weighted by lot price.
    """
    _name = 'construction.lot'
    _description = 'Lot de Chantier'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, code, name'

    # ============= Identity ============= #
    category_id = fields.Many2one('construction.lot.category', string='Catégorie Standard')
    name = fields.Char(string='Nom du Lot', required=True, tracking=True)
    code = fields.Char(string='Code', required=True, tracking=True)
    
    chantier_id = fields.Many2one(
        'construction.chantier',
        string='Chantier',
        required=True,
        ondelete='cascade',
        tracking=True
    )

    # ============= Financials ============= #
    currency_id = fields.Many2one(
        'res.currency',
        string='Devise',
        default=lambda self: self.env.company.currency_id,
        required=True
    )
    price = fields.Monetary(
        string='Prix',
        currency_field='currency_id',
        tracking=True,
        help="Prix du lot (calculé à partir des articles du devis)"
    )
    
    # ============= Completion (NEW) ============= #
    completion_percentage = fields.Float(
        string='Avancement (%)',
        default=0.0,
        tracking=True,
        help="Pourcentage d'avancement du lot (0-100%)"
    )
    is_finished = fields.Boolean(
        string='Terminé',
        compute='_compute_is_finished',
        store=True,
        readonly=False,  # Allow manual override
        tracking=True
    )
    weighted_value = fields.Monetary(
        string='Valeur pondérée',
        compute='_compute_weighted_value',
        store=True,
        currency_field='currency_id',
        help="Prix × % avancement"
    )
    
    # ============= Organization ============= #
    sequence = fields.Integer(string='Séquence', default=10)
    color = fields.Integer(string='Couleur', default=0)
    description = fields.Text(string='Description')
    
    # ============= Partners ============= #
    subcontractor_ids = fields.Many2many(
        'res.partner',
        'construction_lot_subcontractor_rel',
        'lot_id', 'partner_id',
        string='Sous-traitants',
        domain="[('supplier_rank', '>', 0)]",
        tracking=True
    )

    # ============= Constraints ============= #
    _sql_constraints = [
        ('positive_price', 'CHECK(price >= 0)', 'Le prix doit être positif.'),
        ('completion_range', 'CHECK(completion_percentage >= 0 AND completion_percentage <= 100)', 
         'Le pourcentage doit être entre 0 et 100.'),
        ('unique_lot_per_chantier', 'unique(code, chantier_id)', 'Le code du lot doit être unique par chantier.'),
    ]

    # ============= Computes ============= #
    @api.depends('completion_percentage')
    def _compute_is_finished(self):
        for record in self:
            record.is_finished = record.completion_percentage >= 100.0

    @api.depends('price', 'completion_percentage')
    def _compute_weighted_value(self):
        for record in self:
            record.weighted_value = record.price * (record.completion_percentage / 100.0)

    # ============= Onchange ============= #
    @api.onchange('category_id')
    def _onchange_category_id(self):
        if self.category_id:
            self.name = self.category_id.name
            self.code = self.category_id.code

    @api.onchange('is_finished')
    def _onchange_is_finished(self):
        """When manually set to finished, set completion to 100%."""
        if self.is_finished and self.completion_percentage < 100:
            self.completion_percentage = 100.0

    # ============= Constraints ============= #
    @api.constrains('chantier_id', 'code')
    def _check_unique_lot_code(self):
        for record in self:
            existing = self.search([
                ('chantier_id', '=', record.chantier_id.id),
                ('code', '=', record.code),
                ('id', '!=', record.id)
            ])
            if existing:
                raise ValidationError(_("Un lot avec le code '%s' existe déjà sur ce chantier.") % record.code)

    @api.constrains('completion_percentage')
    def _check_completion_percentage(self):
        for record in self:
            if record.completion_percentage < 0 or record.completion_percentage > 100:
                raise ValidationError(_("Le pourcentage d'avancement doit être entre 0% et 100%."))

    # ============= Actions ============= #
    def action_mark_complete(self):
        """Mark lot as 100% complete."""
        self.ensure_one()
        self.completion_percentage = 100.0
        return True

    def action_assign_subcontractor(self):
        """
        Placeholder for wizard action to assign subcontractor.
        Refactored to check context strictly.
        """
        self.ensure_one()
        # Logic to open wizard (Wizard will be migrated later)
        pass

