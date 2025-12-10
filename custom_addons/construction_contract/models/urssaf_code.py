# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class URSSAFCode(models.Model):
    """URSSAF Code Repository for contract management"""
    
    _name = 'construction.urssaf.code'
    _description = 'URSSAF Code Repository'
    _order = 'category, code'
    
    code = fields.Char(
        string='Code URSSAF',
        required=True,
        index=True,
        help='Code URSSAF unique'
    )
    
    name = fields.Char(
        string='Libellé',
        required=True,
        translate=True,
        help='Nom du code URSSAF'
    )
    
    description = fields.Text(
        string='Description',
        translate=True,
        help='Description détaillée du code URSSAF'
    )
    
    category = fields.Selection([
        ('cotisation', 'Cotisation'),
        ('exoneration', 'Exonération'),
        ('reduction', 'Réduction'),
        ('autre', 'Autre'),
    ], string='Catégorie', required=True, index=True, default='cotisation',
       help='Catégorie du code URSSAF')
    
    rate = fields.Float(
        string='Taux (%)',
        digits=(5, 2),
        help='Taux applicable si pertinent'
    )
    
    active = fields.Boolean(
        string='Actif',
        default=True,
        help='Si décoché, le code ne sera plus visible dans les sélections'
    )
    
    legal_reference = fields.Char(
        string='Référence légale',
        help='Référence au texte de loi ou règlement'
    )
    
    effective_date = fields.Date(
        string='Date d\'effet',
        help='Date à partir de laquelle le code est applicable'
    )
    
    end_date = fields.Date(
        string='Date de fin',
        help='Date de fin de validité du code'
    )
    
    # Computed field for display
    display_name_full = fields.Char(
        string='Nom complet',
        compute='_compute_display_name_full',
        store=True
    )
    
    _sql_constraints = [
        ('code_unique', 'unique(code)', _('Ce code URSSAF existe déjà!'))
    ]
    
    @api.depends('code', 'name')
    def _compute_display_name_full(self):
        """Compute full display name with code and name"""
        for record in self:
            record.display_name_full = f"{record.code} - {record.name}"
    
    @api.constrains('effective_date', 'end_date')
    def _check_dates(self):
        """Validate that end_date is after effective_date"""
        for record in self:
            if record.effective_date and record.end_date:
                if record.end_date < record.effective_date:
                    raise ValidationError(_(
                        "La date de fin doit être postérieure à la date d'effet."
                    ))
    
    @api.constrains('rate')
    def _check_rate(self):
        """Validate that rate is positive"""
        for record in self:
            if record.rate < 0:
                raise ValidationError(_(
                    "Le taux ne peut pas être négatif."
                ))
    
    def name_get(self):
        """Override name_get to show code and name"""
        result = []
        for record in self:
            name = f"{record.code} - {record.name}"
            result.append((record.id, name))
        return result
    
    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        """Override name_search to search in code and name"""
        args = args or []
        domain = []
        if name:
            domain = ['|', ('code', operator, name), ('name', operator, name)]
        records = self.search(domain + args, limit=limit)
        return records.name_get()
