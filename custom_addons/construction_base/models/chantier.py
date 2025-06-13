from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta

class Chantier:
    _name = 'construction.chantier'
    _description = 'Construction Project'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    #===========Attributes==========#
    name = fields.Char('Project Name', required=True)
    stage = fields.Many2one('construction.stage', 'Stage')
    lots_ids = fields.Many2many('construction.lot.extension')
    chapter_name = fields.Char('Chapter Name', compute='_compute_chapter_name')
    user_ids = fields.Many2many('res.users', string='Project Users')
    description = fields.Text('Description')
    notes = fields.Text('Notes')
    subcontractors = fields.Many2many('res.partner', string='Subcontractors',compute='_compute_subcontractors')
    date_start_contract = fields.Date('Date de début contractuelle', tracking=True)
    date_end_contract = fields.Date('Date de fin contractuelle', tracking=True)
    date_start_actual = fields.Date('Date de début réelle', tracking=True)
    date_end_actual = fields.Date('Date de fin réelle', tracking=True)

    progress = fields.Float('Progression (%)',compute='_compute_construction_progression',default=0.0)
    days_remaining = fields.Integer(
        'Jours restants',
        compute='_compute_days_remaining',
        store=True,
        help="Nombre de jours restants avant la date d'échéance"
    )
    state = fields.Selection([
        ('active', 'Actif'),
        ('suspended', 'Suspendu'),
        ('completed', 'Terminé'),
        ('abandoned', 'Abandonné')
    ])
    duration_planned = fields.Integer(
        'Durée prévue (jours)',
        compute='_compute_duration_planned',
        store=True
    )
    duration_actual = fields.Integer(
        'Durée réelle (jours)',
        compute='_compute_duration_actual',
        store=True
    )

    address = fields.Text('Adresse du chantier')
    city = fields.Char('Ville')
    zip_code = fields.Char('Code postal')
    country_id = fields.Many2one('res.country', string='Pays')
    phone = fields.Char('Téléphone du chantier')

    surface_m2 = fields.Float('Surface (m²)')
    nb_levels = fields.Integer('Nombre d\'étages')
    permit_number = fields.Char('Numéro de permis')
    permit_date = fields.Date('Date du permis')

    user_ids = fields.Many2many('res.users', string='Équipe interne')
    available_subcontractors = fields.Many2many(
        'res.partner',
        string='Sous-traitants disponibles',
        compute='_compute_available_subcontractors'
    )

    visit_ids = fields.One2many('construction.visit', 'chantier_id', string='Visites techniques')
    document_ids = fields.One2many('construction.document', 'chantier_id', string='Documents')
    sale_order_count = fields.Integer('Nombre de devis/commandes', compute='_compute_counts', store=True)
    subcontractor_count = fields.Integer('Nombre de sous-traitants', compute='_compute_counts', store=True)
    stage_validation_info = fields.Text(
        'Info de validation',
        compute='_compute_stage_validation_info',
        help="Informations sur les conditions pour passer à l'étape suivante"
    )

    show_schedule_visit = fields.Boolean('Afficher planifier visite', compute='_compute_action_visibility')
    show_create_quote = fields.Boolean('Afficher créer devis', compute='_compute_action_visibility')
    show_assign_subcontractors = fields.Boolean('Afficher assigner sous-traitants',
                                                compute='_compute_action_visibility')
    show_mark_not_pursued = fields.Boolean('Afficher marquer sans suite', compute='_compute_action_visibility')

    _sql_constraints = [
        ('positive_cost', 'CHECK(total_cost >= 0)', 'Le coût total doit être positif'),
        ('positive_surface', 'CHECK(surface_m2 >= 0)', 'La surface doit être positive'),
        ('progress_range', 'CHECK(progress >= 0 AND progress <= 100)',
         'La progression doit être entre 0 et 100%'),
    ]

    @api.depends('stage', 'stage.chapter_id', 'stage.chapter_id.name')
    def _compute_chapter_name(self):
        for record in self:
            if record.stage and record.stage.chapter_id:
                record.chapter_name = record.stage.chapter_id.name
            else:
                record.chapter_name = False

    @api.depends('date_start_contract', 'date_end_contract')
    def _compute_duration_planned(self):
        """
        """
        for record in self:
            if record.date_start_contract and record.date_end_contract:
                delta = record.date_end_contract - record.date_start_contract
                record.duration_planned = delta.days + 1

    @api.depends('date_start_actual', 'date_end_actual')

    def _compute_duration_actual(self):
        """
        """
        for record in self:
            if record.date_start_actual and record.date_end_actual:
                delta = record.date_end_actual - record.date_start_actual
                record.duration_actual = delta.days + 1
            elif record.date_start_actual and record.state == 'in_progress':
                delta = fields.Date.today() - record.date_start_actual
                record.duration_actual = delta.days + 1
            else:
                record.duration_actual = 0

    @api.depends('lots_ids.subcontractor_ids')
    def _compute_subcontractors(self):
        for record in self:
            subcontractors = []
            for lot in record.lots_ids:
                for subcontractor in lot.subcontractor_ids:
                    subcontractors.append(subcontractor)
        return list(set(subcontractors))

    @api.depends('lots_ids.cost', 'lots_ids.is_finished')

    def _compute_construction_progression(self ):
        """
        """
        for record in self:
            total_cost = 0
            total_progress = 0
            for lot in record.lots_ids:
                total_cost += lot.cost
                if lot.is_finished:
                    total_progress += lot.progress
            record.progress = total_progress / len(record.lots_ids) if record.lots_ids else 0
            record.total_cost = total_cost


