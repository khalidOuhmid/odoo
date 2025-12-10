# -*- coding: utf-8 -*-
"""
Visit Model - Migrated and Cleaned.
"""
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import base64

class Visit(models.Model):
    _name = 'construction.visit'
    _description = 'Visite de Chantier'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc'

    name = fields.Char(string='Titre', required=True, translate=True)
    chantier_id = fields.Many2one('construction.chantier', string='Chantier', required=True, ondelete='cascade')
    date = fields.Datetime(string='Date et Heure', required=True, tracking=True)
    duration = fields.Float(string='Durée (h)', default=2.0)
    
    user_ids = fields.Many2many('res.users', string='Intervenants Internes')
    partner_ids = fields.Many2many('res.partner', string='Participants Externes')
    
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('planned', 'Planifiée'),
        ('confirmed', 'Confirmée'),
        ('in_progress', 'En cours'),
        ('completed', 'Terminée'),
        ('cancelled', 'Annulée')
    ], string='Statut', default='draft', required=True, tracking=True)

    visit_type = fields.Selection([
        ('initial', 'Visite Initiale'),
        ('progress', 'Suivi de Chantier'),
        ('quality', 'Contrôle Qualité'),
        ('final', 'Réception'),
    ], string='Type de Visite', default='progress')
    
    notes = fields.Html(string='Notes et Observations')
    report = fields.Html(string='Compte Rendu')

    # ============= Computes ============= #
    @api.depends('name', 'chantier_id', 'date')
    def _compute_display_name(self):
        for record in self:
            if record.chantier_id and record.date:
                record.display_name = f"{record.name} - {record.chantier_id.name}"
            else:
                record.display_name = record.name

    # ============= Actions ============= #
    def action_confirm(self):
        for rec in self:
            if rec.state not in ['draft', 'planned']:
                raise ValidationError(_("Seules les visites brouillon ou planifiées peuvent être confirmées."))
            rec.state = 'confirmed'

    def action_start(self):
        for rec in self:
             if rec.state != 'confirmed':
                 raise ValidationError(_("Il faut confirmer la visite avant de la démarrer."))
             rec.state = 'in_progress'

    def action_complete(self):
        for rec in self:
            if rec.state != 'in_progress':
                raise ValidationError(_("La visite doit être en cours pour être terminée."))
            rec.state = 'completed'
    
    def action_cancel(self):
        for rec in self:
             if rec.state == 'completed':
                 raise ValidationError(_("Impossible d'annuler une visite terminée."))
             rec.state = 'cancelled'

    def action_reset_to_planned(self):
        for rec in self:
            rec.state = 'planned'

    # Note: Report generation methods (PDF) removed for now as we don't have report XMLs yet.
    # They can be re-added once `report` module is migrated.
