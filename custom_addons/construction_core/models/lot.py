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
    """
    _name = 'construction.lot'
    _description = 'Lot de Chantier'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'code, name'

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
        help="Prix du lot"
    )
    
    # ============= Organization ============= #
    sequence = fields.Integer(string='Séquence', default=10)
    color = fields.Integer(string='Couleur', default=0)
    description = fields.Text(string='Description')
    is_finished = fields.Boolean(string='Terminé', default=False, tracking=True)
    
    # ============= Partners ============= #
    subcontractor_ids = fields.Many2many(
        'res.partner',
        string='Sous-traitants',
        domain="[('supplier_rank', '>', 0)]",
        tracking=True
    )

    # ============= Constraints ============= #
    _sql_constraints = [
        ('positive_price', 'CHECK(price >= 0)', 'Le prix doit être positif.'),
        ('unique_lot_per_chantier', 'unique(code, chantier_id)', 'Le code du lot doit être unique par chantier.'),
    ]

    # ============= Methods ============= #
    @api.onchange('category_id')
    def _onchange_category_id(self):
        if self.category_id:
            self.name = self.category_id.name
            self.code = self.category_id.code

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

    def action_assign_subcontractor(self):
        """
        Placeholder for wizard action to assign subcontractor.
        Refactored to check context strictly.
        """
        self.ensure_one()
        # Logic to open wizard (Wizard will be migrated later)
        pass
