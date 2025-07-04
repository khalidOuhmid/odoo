# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class BlgVisite(models.Model):
    """Modèle pour les visites techniques"""
    _name = 'blg.visite'
    _description = 'Visite Technique'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc'

    name = fields.Char('Nom de la visite', required=True, tracking=True)
    chantier_id = fields.Many2one('blg.chantier', string='Chantier', required=True, ondelete='cascade')
    date = fields.Datetime('Date et heure', required=True, tracking=True)
    duration = fields.Float('Durée (heures)', default=2.0)
    
    # Participants
    user_ids = fields.Many2many('res.users', string='Intervenants internes')
    partner_ids = fields.Many2many('res.partner', string='Participants externes')
    
    # Statut - fix state values to match view expectations
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('planned', 'Planifiée'),
        ('confirmed', 'Confirmée'),
        ('in_progress', 'En cours'),
        ('completed', 'Terminée'),
        ('cancelled', 'Annulée')
    ], string='Statut', default='draft', required=True, tracking=True)
    
    # Contenu
    description = fields.Html('Description')
    notes = fields.Html('Notes et observations')
    report = fields.Html('Rapport de visite')
    visit_type = fields.Selection([
        ('initial', 'Visite initiale'),
        ('progress', 'Suivi de chantier'),
        ('quality', 'Contrôle qualité'),
        ('final', 'Réception')
    ], string='Type de visite', default='progress')
    
    # Computed fields
    display_name = fields.Char(compute='_compute_display_name', store=True)
    
    @api.depends('name', 'chantier_id', 'date')
    def _compute_display_name(self):
        for visite in self:
            if visite.chantier_id and visite.date:
                visite.display_name = f"{visite.name} - {visite.chantier_id.name}"
            else:
                visite.display_name = visite.name or 'Nouvelle visite'
    
    @api.model
    def create(self, vals):
        if not vals.get('name'):
            chantier = self.env['blg.chantier'].browse(vals.get('chantier_id'))
            sequence = self.search_count([('chantier_id', '=', vals.get('chantier_id'))]) + 1
            vals['name'] = f"Visite {sequence} - {chantier.name}"
        return super().create(vals)
    
    # State transition methods
    def action_confirm(self):
        """Confirmer la visite"""
        for visite in self:
            if visite.state not in ['draft', 'planned']:
                raise ValidationError(_("Seules les visites en brouillon ou planifiées peuvent être confirmées."))
            visite.state = 'confirmed'
            visite.message_post(body=_("Visite confirmée"))
    
    def action_start(self):
        """Démarrer la visite"""
        for visite in self:
            if visite.state != 'confirmed':
                raise ValidationError(_("Seules les visites confirmées peuvent être démarrées."))
            visite.state = 'in_progress'
            visite.message_post(body=_("Visite démarrée"))
    
    def action_complete(self):
        """Terminer la visite"""
        for visite in self:
            if visite.state != 'in_progress':
                raise ValidationError(_("Seules les visites en cours peuvent être terminées."))
            visite.state = 'completed'
            visite.message_post(body=_("Visite terminée"))
    
    def action_cancel(self):
        """Annuler la visite"""
        for visite in self:
            if visite.state in ['completed', 'cancelled']:
                raise ValidationError(_("Cette visite ne peut pas être annulée."))
            visite.state = 'cancelled'
            visite.message_post(body=_("Visite annulée"))
    
    def action_reset_to_planned(self):
        """Remettre en planifiée"""
        for visite in self:
            visite.state = 'planned'
            visite.message_post(body=_("Visite remise en planification"))
