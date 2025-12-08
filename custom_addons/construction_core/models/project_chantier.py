# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)

class ConstructionChantier(models.Model):
    """
    Core Entity: Construction Project (Chantier).
    
    Acts as the central aggregate for the construction project lifecycle.
    Integrates:
    - Financial Tracking (Budget vs Realized) via FinancialMixin.
    - Workflow Management (State Machine) via StageMixin.
    - Stakeholder Management (Client, Company, Manager).
    
    This model adheres to the Clean Core principle: it contains business schemas 
    and extensive logic but delegates UI specificities to the Views layer.
    """
    _name = 'construction.chantier'
    _description = 'Construction Project'
    _inherit = ['mail.thread', 'mail.activity.mixin', 
                'construction.financial.mixin', 
                'construction.stage.mixin']
    
    # ==========================
    # IDENTIFICATION
    # ==========================
    name = fields.Char(string='Project Name', required=True, tracking=True)
    priority = fields.Selection([
        ('0', 'Normal'),
        ('1', 'Important'),
    ], default='0', index=True, string="Priorité")
    reference = fields.Char(string='Reference', default='/', readonly=True, copy=False)
    color = fields.Integer(string='Color Index')
    
    client_id = fields.Many2one(
        'res.partner', 
        string='Customer', 
        required=True, 
        tracking=True,
        domain="[('is_company', '=', True)]"
    )

    # ==========================
    # LOCATION & TECHNICAL INFO
    # ==========================
    address = fields.Text(string='Adresse du chantier')
    city = fields.Char(string='Ville')
    zip_code = fields.Char(string='Code postal')
    country_id = fields.Many2one('res.country', string='Pays')
    phone = fields.Char(string='Téléphone du chantier')

    surface_m2 = fields.Float(string='Surface (m²)')
    nb_levels = fields.Integer(string="Nombre d'étages")
    permit_number = fields.Char(string='Numéro de permis')
    permit_date = fields.Date(string='Date du permis')
    
    # ==========================
    # SCOPE & ORGANIZATION
    # ==========================
    lot_ids = fields.One2many('construction.lot', 'chantier_id', string='Work Packages (Lots)')
    
    user_id = fields.Many2one(
        'res.users', 
        string='Project Manager', 
        default=lambda self: self.env.user,
        tracking=True
    )
    
    company_id = fields.Many2one(
        'res.company', 
        string='Company', 
        required=True, 
        default=lambda self: self.env.company
    )

    # ==========================
    # TIMELINE
    # ==========================
    # ==========================
    # TIMELINE
    # ==========================
    date_start = fields.Date(string='Date de début', tracking=True)
    date_end = fields.Date(string='Date de fin', tracking=True)
    
    date_start_contract = fields.Date(string='Date de début contractuelle', tracking=True)
    date_end_contract = fields.Date(string='Date de fin contractuelle', tracking=True)
    date_start_internal = fields.Date(string='Date de début interne', tracking=True)
    date_end_internal = fields.Date(string='Date de fin interne', tracking=True)
    date_start_estimated = fields.Date(string='Date de début estimée', tracking=True)
    date_end_estimated = fields.Date(string='Date de fin estimée ', tracking=True)

    # ==========================
    # COMPUTED FIELDS FOR KANBAN/VIEWS
    # ==========================
    days_remaining = fields.Integer(string='Jours restants', compute='_compute_days_remaining')
    deadline_status = fields.Selection([
        ('on_track', 'Dans les temps'),
        ('risk', 'Attention'),
        ('late', 'En retard')
    ], string='Statut échéance', compute='_compute_days_remaining')
    
    duration_planned = fields.Integer(string='Durée prévue (j)', compute='_compute_duration')
    duration_actual = fields.Integer(string='Durée réelle (j)', compute='_compute_duration')

    # Counters for stat buttons
    # visit_ids moved to construction_visit module
    subcontractor_count = fields.Integer(compute='_compute_counts')
    quotation_count = fields.Integer(compute='_compute_counts')
    invoice_count = fields.Integer(compute='_compute_counts') # Needed for the smart button logic if kept
    lots_count = fields.Integer(compute='_compute_counts')
    
    @api.depends('date_end_contract', 'stage_id')
    def _compute_days_remaining(self):
        today = fields.Date.context_today(self)
        for chantier in self:
            # Check if stage is closed/folded or specific state
            if chantier.stage_id.fold:
                chantier.days_remaining = 0
                chantier.deadline_status = 'on_track'
                continue
                
            if chantier.date_end_contract:
                delta = (chantier.date_end_contract - today).days
                chantier.days_remaining = delta
                if delta < 0:
                    chantier.deadline_status = 'late'
                elif delta < 7:
                    chantier.deadline_status = 'risk'
                else:
                    chantier.deadline_status = 'on_track'
            else:
                chantier.days_remaining = 0
                chantier.deadline_status = 'on_track'

    @api.depends('date_start_contract', 'date_end_contract', 'date_start_internal', 'date_end_internal')
    def _compute_duration(self):
        for chantier in self:
            if chantier.date_start_contract and chantier.date_end_contract:
                chantier.duration_planned = (chantier.date_end_contract - chantier.date_start_contract).days
            else:
                chantier.duration_planned = 0
                
            if chantier.date_start_internal and chantier.date_end_internal:
                chantier.duration_actual = (chantier.date_end_internal - chantier.date_start_internal).days
            else:
                chantier.duration_actual = 0

    def _compute_counts(self):
        for chantier in self:
            # Placeholder implementations - to be extended by specific modules via inherit
            chantier.subcontractor_count = 0
            chantier.quotation_count = 0
            chantier.invoice_count = 0
            chantier.lots_count = len(chantier.lot_ids)

    progress = fields.Float(string='Progression (%)', compute='_compute_progress', store=True, default=0.0)
    
    @api.depends('lot_ids.progress')
    def _compute_progress(self):
        for chantier in self:
            if not chantier.lot_ids:
                chantier.progress = 0.0
            else:
                # Average progress of lots, weighted by budget? For now simple average
                total_progress = sum(chantier.lot_ids.mapped('progress'))
                chantier.progress = total_progress / len(chantier.lot_ids)
    
    # ==========================
    # FINOPS (Mixin Implementation)
    # ==========================
    # Explicit definition to satisfy mixin interface
    revenue_amount = fields.Monetary(string='Revenue', currency_field='currency_id', default=0.0)

    # ==========================
    # FINANCIAL COMPUTATION
    # ==========================
    def _compute_financial_status(self):
        """
        Aggregate financial KPIs from detailed Work Packages (Lots).
        
        Rolls up Budget, Committed, and Realized costs to provide a
        project-level financial overview.
        """
        for chantier in self:
            # Efficient aggregation of child lots
            lots = chantier.lot_ids
            chantier.budget_amount = sum(lots.mapped('budget_amount'))
            chantier.committed_amount = sum(lots.mapped('committed_amount'))
            chantier.realized_amount = sum(lots.mapped('realized_amount'))
            
            chantier.realized_amount = sum(lots.mapped('realized_amount'))
            
            # Revenue logic: For now 0.0, will be extended by construction_sale
            # _logger.debug("Computed Financials for Chantier %s: Budget=%s, Committed=%s", 
            #               chantier.name, chantier.budget_amount, chantier.committed_amount)

    # ==========================
    # LIFECYCLE MANAGEMENT
    # ==========================
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', '/') == '/':
                vals['reference'] = self.env['ir.sequence'].next_by_code('construction.chantier') or '/'
        return super().create(vals_list)

    def write(self, vals):
        res = super().write(vals)
        if 'stage_id' in vals:
            _logger.info("Chantier %s moved to stage %s", self.name, vals.get('stage_id'))
        return res

    def action_force_stage_wizard(self):
        """
        Open the wizard to force a stage change.
        """
        self.ensure_one()
        return {
            'name': _('Force Stage Change'),
            'type': 'ir.actions.act_window',
            'res_model': 'construction.force.stage.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_chantier_id': self.id,
                'default_current_stage_id': self.stage_id.id,
            }
        }
