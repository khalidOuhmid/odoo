# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class ConstructionChantier(models.Model):
    """
    Construction Site (Chantier) - Aggregate Root.
    
    This is the central entity of the system.
    It manages the lifecycle of a construction project from Design to Delivery.
    
    Inherits:
    - mail.thread: Messaging and Chatter.
    - mail.activity.mixin: Activity tracking.
    - construction.date.mixin: Date management (Start/End/Duration).
    """
    _name = 'construction.chantier'
    _description = 'Construction Site'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'construction.date.mixin', 'construction.notification.mixin']
    _order = 'code desc'

    # ==============================================================================================
    #                                      IDENTIFICATION
    # ==============================================================================================
    
    code = fields.Char(
        string='Métré / Référence',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('Nouveau'),
        index=True
    )
    
    name = fields.Char(string='Nom du Chantier', required=True, tracking=True)
    
    active = fields.Boolean(default=True)
    
    user_id = fields.Many2one(
        'res.users',
        string='Conducteur de Travaux',
        default=lambda self: self.env.user,
        tracking=True
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Société',
        required=True,
        default=lambda self: self.env.company
    )

    # ==============================================================================================
    #                                      RELATIONS (PARTNERS)
    # ==============================================================================================
    
    partner_id = fields.Many2one(
        'res.partner',
        string='Client',
        required=True,
        tracking=True
    )

    address_id = fields.Many2one(
        'res.partner',
        string='Adresse du Chantier',
        help="Lieu physique d'exécution des travaux."
    )

    # ==============================================================================================
    #                                      LIFECYCLE (STATE MACHINE)
    # ==============================================================================================
    
    state = fields.Selection(
        selection=[
            ('draft', 'Brouillon'),
            ('study', 'Étude'),
            ('prep', 'Préparation'),
            ('execution', 'Exécution'),
            ('acceptance', 'Réception'),
            ('done', 'Terminé'),
            ('cancel', 'Annulé'),
        ],
        string='État',
        default='draft',
        required=True,
        tracking=True,
        group_expand='_expand_states',
        index=True
    )

    # ==============================================================================================
    #                                      METRICS & KPIs
    # ==============================================================================================

    # Financial Summary
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', string="Devise")
    
    budget_total = fields.Monetary(string='Budget Total', compute='_compute_financials', store=True)
    cost_committed = fields.Monetary(string='Engagé', compute='_compute_financials', help="Total des commandes validées")
    cost_actual = fields.Monetary(string='Réalisé', compute='_compute_financials', help="Total des factures fournisseurs validées")
    
    progress_technical = fields.Float(string='Avancement (%)', tracking=True)

    # ==============================================================================================
    #                                      RELATIONS (COMPONENTS)
    # ==============================================================================================

    lot_ids = fields.One2many(
        'construction.lot',
        'chantier_id',
        string='Lots'
    )

    # ==============================================================================================
    #                                      METHODS
    # ==============================================================================================

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code', _('New')) == _('New'):
                vals['code'] = self.env['ir.sequence'].next_by_code('construction.chantier') or _('New')
        return super().create(vals_list)

    @api.depends('lot_ids.budget_amount', 'lot_ids.cost_committed', 'lot_ids.cost_actual')
    def _compute_financials(self):
        """Aggregate financial data from Lots."""
        for chantier in self:
            chantier.budget_total = sum(chantier.lot_ids.mapped('budget_amount'))
            chantier.cost_committed = sum(chantier.lot_ids.mapped('cost_committed'))
            chantier.cost_actual = sum(chantier.lot_ids.mapped('cost_actual'))

    def action_confirm_study(self):
        self.ensure_one()
        if not self.partner_id:
            raise ValidationError(_("Please define a customer before starting the study."))
        self.state = 'study'

    def action_start_prep(self):
        self.ensure_one()
        self.state = 'prep'

    def action_start_execution(self):
        self.ensure_one()
        # Enforce rule: Must have at least one defined Lot
        if not self.lot_ids:
            raise ValidationError(_("Cannot start execution without defined Work Packages (Lots)."))
        self.state = 'execution'

    def action_close(self):
        self.state = 'done'

    def _expand_states(self, states, domain, order):
        return [key for key, val in type(self).state.selection]
