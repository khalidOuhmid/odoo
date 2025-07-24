from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class Visit(models.Model):
    _name = 'construction.visit'
    _description = 'Construction Visit'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc'
    name = fields.Char('Name', required=True, translate=True)
    description = fields.Text('Description', translate=True)
    chantier_id = fields.Many2one('construction.chantier', string='Chantier', required=True, ondelete='cascade')
    date = fields.Datetime('Date et heure', required=True, tracking=True)
    duration = fields.Float('Durée (heures)', default=2.0)

    user_ids = fields.Many2many('res.users', string='Intervenants internes')
    partner_ids = fields.Many2many('res.partner', string='Participants externes')

    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('planned', 'Planifiée'),
        ('confirmed', 'Confirmée'),
        ('in_progress', 'En cours'),
        ('completed', 'Terminée'),
        ('cancelled', 'Annulée')
    ], string='Statut', default='draft', required=True, tracking=True)

    description = fields.Html('Description')
    notes = fields.Html('Notes et observations')
    report = fields.Html('Rapport de visite')
    visit_type = fields.Selection([
        ('initial', 'Visite initiale'),
        ('progress', 'Suivi de chantier'),
        ('quality', 'Contrôle qualité'),
        ('final', 'Réception')
    ], string='Type de visite', default='progress')

    @api.depends('name', 'chantier_id', 'date')
    def _compute_display_name(self):
        for visite in self:
            if visite.chantier_id and visite.date:
                visite.display_name = f"{visite.name} - {visite.chantier_id.name}"
            else:
                visite.display_name = visite.name or 'Nouvelle visite'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name'):
                chantier = self.env['construction.chantier'].browse(vals.get('chantier_id'))
                sequence = self.search_count([('chantier_id', '=', vals.get('chantier_id'))]) + 1
                vals['name'] = f"Visite {sequence} - {chantier.name}"
        return super().create(vals_list)

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

    def action_view_calendar(self):
        return {
            'name': 'Planning des Visites',
            'type': 'ir.actions.act_window',
            'res_model': 'construction.visit',
            'view_mode': 'calendar',
            'view_id': self.env.ref('construction_base.view_visit_calendar').id,
            'target': 'current',
            'domain': [('id', '=', self.id)],
            'context': {'search_default_id': self.id}
        }