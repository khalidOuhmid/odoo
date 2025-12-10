# -*- coding: utf-8 -*-
"""
Invoice Type and Schedule Models

Migrated and cleaned from construction_base.
Implements billing cycles for construction projects.
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class InvoiceType(models.Model):
    """
    Invoice Type (Billing Cycle).
    
    Defines a pattern for invoicing construction projects, e.g. "30/30/40"
    means 30% at signature, 30% at 50% progress, 40% at completion.
    """
    _name = 'construction.invoice_type'
    _description = 'Cycle de facturation'
    _order = 'sequence, name'

    name = fields.Char(string='Nom du cycle', required=True)
    code = fields.Char(string='Code', required=True)
    description = fields.Text(string='Description')
    sequence = fields.Integer(string='Séquence', default=10)
    active = fields.Boolean(string='Actif', default=True)
    
    # Lines
    line_ids = fields.One2many(
        'construction.invoice_type.line',
        'invoice_type_id',
        string='Étapes de facturation',
        copy=True
    )
    
    # Computed
    total_percentage = fields.Float(
        string='Total %',
        compute='_compute_total_percentage',
        store=True
    )
    line_count = fields.Integer(
        string='Nombre d\'étapes',
        compute='_compute_line_count'
    )
    
    _sql_constraints = [
        ('unique_code', 'UNIQUE(code)', 'Le code du cycle doit être unique.'),
    ]

    @api.depends('line_ids.percentage')
    def _compute_total_percentage(self):
        for record in self:
            record.total_percentage = sum(record.line_ids.mapped('percentage'))

    @api.depends('line_ids')
    def _compute_line_count(self):
        for record in self:
            record.line_count = len(record.line_ids)

    @api.constrains('line_ids')
    def _check_total_percentage(self):
        for record in self:
            if record.line_ids:
                total = sum(record.line_ids.mapped('percentage'))
                if abs(total - 100.0) > 0.01:
                    raise ValidationError(_(
                        "Le total des pourcentages doit être 100%% (actuellement %.1f%%)"
                    ) % total)


class InvoiceTypeLine(models.Model):
    """
    Invoice Type Line (Billing Step).
    
    Each line defines when and how much to invoice.
    """
    _name = 'construction.invoice_type.line'
    _description = 'Étape de facturation'
    _order = 'invoice_type_id, sequence, trigger_percentage'

    invoice_type_id = fields.Many2one(
        'construction.invoice_type',
        string='Cycle',
        required=True,
        ondelete='cascade'
    )
    name = fields.Char(string='Description', required=True)
    sequence = fields.Integer(string='Séquence', default=10)
    
    # Trigger
    trigger_percentage = fields.Float(
        string='Déclenchement (%)',
        required=True,
        help="Pourcentage d'avancement qui déclenche cette facture"
    )
    
    # Amount
    percentage = fields.Float(
        string='Montant (%)',
        required=True,
        help="Pourcentage du montant total à facturer"
    )
    
    # Options
    is_advance_payment = fields.Boolean(
        string='Acompte signature',
        help="Facture émise à la signature (avant travaux)"
    )
    
    notes = fields.Text(string='Notes')
    
    _sql_constraints = [
        ('positive_trigger', 'CHECK(trigger_percentage >= 0 AND trigger_percentage <= 100)',
         'Le déclenchement doit être entre 0 et 100%.'),
        ('positive_amount', 'CHECK(percentage >= 0 AND percentage <= 100)',
         'Le montant doit être entre 0 et 100%.'),
    ]

    @api.constrains('trigger_percentage', 'is_advance_payment')
    def _check_advance_payment(self):
        for record in self:
            if record.is_advance_payment and record.trigger_percentage != 0:
                raise ValidationError(_(
                    "Un acompte de signature doit avoir un déclenchement à 0%%"
                ))
