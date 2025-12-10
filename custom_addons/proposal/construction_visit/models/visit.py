# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import base64

class ConstructionVisit(models.Model):
    _name = 'construction.visit'
    _description = 'Construction Visit'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc'

    # ==========================
    # IDENTIFICATION
    # ==========================
    name = fields.Char(string='Titre', required=True, translate=True, tracking=True)
    chantier_id = fields.Many2one(
        'construction.chantier', 
        string='Chantier', 
        required=True, 
        ondelete='cascade',
        tracking=True
    )
    
    visit_type = fields.Selection([
        ('initial', 'Visite initiale'),
        ('progress', 'Suivi de chantier'),
        ('quality', 'Contrôle qualité'),
        ('final', 'Réception')
    ], string='Type de visite', default='progress', required=True)

    # ==========================
    # PLANNING
    # ==========================
    date = fields.Datetime(string='Date et Heure', required=True, tracking=True, default=fields.Datetime.now)
    duration = fields.Float(string='Durée (h)', default=2.0)
    
    user_ids = fields.Many2many(
        'res.users', 
        string='Intervenants (Interne)',
        default=lambda self: self.env.user
    )
    partner_ids = fields.Many2many(
        'res.partner', 
        string='Participants (Externe)'
    )

    # ==========================
    # CONTENT (Mobile Friendly)
    # ==========================
    notes = fields.Html(string='Observations', help="Notes prises durant la visite")
    report = fields.Html(string='Compte-rendu', help="Rapport formel")

    # ==========================
    # STATUS
    # ==========================
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('planned', 'Planifiée'),
        ('confirmed', 'Confirmée'),
        ('in_progress', 'En cours'),
        ('completed', 'Terminée'),
        ('cancelled', 'Annulée')
    ], string='Statut', default='draft', required=True, tracking=True, group_expand='_expand_states')

    # ==========================
    # UTILS
    # ==========================
    def _expand_states(self, states, domain, order):
        return [key for key, val in type(self).state.selection]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') and vals.get('chantier_id'):
                chantier = self.env['construction.chantier'].browse(vals['chantier_id'])
                seq = self.search_count([('chantier_id', '=', chantier.id)]) + 1
                vals['name'] = f"Visite #{seq} - {chantier.name}"
        return super().create(vals_list)
    
    def action_confirm(self):
        for rec in self:
            rec.state = 'confirmed'

    def action_start(self):
        for rec in self:
            rec.state = 'in_progress'

    def action_complete(self):
        for rec in self:
            rec.state = 'completed'
            # TODO: Generate Report automatically if template exists

    def action_cancel(self):
        for rec in self:
            rec.state = 'cancelled'

    def action_reset_draft(self):
        for rec in self:
            rec.state = 'draft'
