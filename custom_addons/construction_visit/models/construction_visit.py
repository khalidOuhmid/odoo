# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class ConstructionVisit(models.Model):
    """
    Site Visit (Rapport de Chantier).
    
    Records the occurrences of site supervision.
    Includes rich-text reporting and photo management.
    """
    _name = 'construction.visit'
    _description = 'Rapport de Visite'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc'

    name = fields.Char(string='Titre', required=True, translate=True, default=lambda self: _('Nouvelle Visite'))
    
    chantier_id = fields.Many2one(
        'construction.chantier',
        string='Chantier',
        required=True,
        tracking=True,
        index=True
    )
    
    date = fields.Datetime(string='Date & Heure', default=fields.Datetime.now, required=True, tracking=True)
    duration = fields.Float(string='Durée (h)', default=1.0)
    
    user_id = fields.Many2one('res.users', string='Conducteur', default=lambda self: self.env.user)
    
    attendee_ids = fields.Many2many('res.partner', string='Participants')

    # Content
    observations = fields.Html(string='Observations / Compte-rendu')
    weather = fields.Char(string='Météo', help="Ex: Ensoleillé, Pluvieux")
    
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('done', 'Validé'),
        ('cancel', 'Annulé')
    ], default='draft', string='État', tracking=True)

    # ==============================================================================================
    #                                      ACTIONS
    # ==============================================================================================

    def action_validate(self):
        self.state = 'done'
        # Auto-generate PDF report in future?
        
    def action_print_report(self):
        return self.env.ref('construction_visit.action_report_construction_visit').report_action(self)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('chantier_id'):
                chantier = self.env['construction.chantier'].browse(vals['chantier_id'])
                # Auto-naming if generic
                if vals.get('name', '') == _('Nouvelle Visite'):
                    count = self.search_count([('chantier_id', '=', chantier.id)]) + 1
                    vals['name'] = f"Visite N°{count} - {chantier.name}"
        return super().create(vals_list)
