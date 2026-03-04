# -*- coding: utf-8 -*-
"""
Invoice Schedule Extension
============================
Ajoute les champs de vieillissement (age_days, overdue_bucket) sur
construction.invoice.schedule pour alimenter la Vue 3 Facturation.

Ces champs sont calculés à la volée (store=False) car ils dépendent de la date du jour.
"""
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import date


class InvoiceScheduleFinance(models.Model):
    """Extension de construction.invoice.schedule pour la Tour de Contrôle."""

    _inherit = 'construction.invoice.schedule'

    # ============= VIEILLISSEMENT ============= #
    age_days = fields.Integer(
        string='Âge (jours)',
        compute='_compute_age_bucket',
        help="Nombre de jours depuis la date prévue de facturation"
    )
    overdue_bucket = fields.Selection([
        ('future',   '📅 À venir'),
        ('current',  '✅ Dans les délais'),
        ('d30',      '⚠️ 30 jours'),
        ('d60',      '🟠 60 jours'),
        ('d90plus',  '🔴 90+ jours (Critique)'),
    ], string='Ancienneté', compute='_compute_age_bucket',
       help="Tranche d'âge de la facture planifiée"
    )
    is_overdue = fields.Boolean(
        'En retard', compute='_compute_age_bucket',
        help="Vrai si la date prévue est dépassée et non encore facturée"
    )

    @api.depends('planned_date', 'state')
    def _compute_age_bucket(self):
        """Calcule le vieillissement de chaque échéance planifiée."""
        today = date.today()
        for rec in self:
            if not rec.planned_date or rec.state in ('invoiced', 'paid', 'cancelled'):
                rec.age_days = 0
                rec.overdue_bucket = 'current'
                rec.is_overdue = False
                continue

            delta = (today - rec.planned_date).days
            rec.age_days = delta
            rec.is_overdue = delta > 0

            if delta < 0:
                rec.overdue_bucket = 'future'
            elif delta <= 30:
                rec.overdue_bucket = 'current'
            elif delta <= 60:
                rec.overdue_bucket = 'd30'
            elif delta <= 90:
                rec.overdue_bucket = 'd60'
            else:
                rec.overdue_bucket = 'd90plus'

    # ============= COMPUTED : Pipeline à facturer ============= #
    invoiceable_now = fields.Boolean(
        'Prêt à facturer',
        compute='_compute_invoiceable_now',
        help="Vrai si ce chantier a atteint le seuil d'avancement et n'est pas encore facturé"
    )

    @api.depends('state', 'chantier_id.progress', 'trigger_percentage', 'is_advance_payment')
    def _compute_invoiceable_now(self):
        """Détermine si une facture peut être émise immédiatement."""
        for rec in self:
            if rec.state != 'planned':
                rec.invoiceable_now = False
                continue
            if rec.is_advance_payment:
                rec.invoiceable_now = True
            else:
                rec.invoiceable_now = (rec.chantier_id.progress or 0) >= rec.trigger_percentage
