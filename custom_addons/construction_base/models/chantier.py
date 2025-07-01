from numpy.testing._private.utils import origin

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta

class Chantier(models.Model):
    _name = 'construction.chantier'
    _description = 'Construction Project'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    #===========Attributes==========#
    name = fields.Char('Project Name', required=True)
    stage = fields.Many2one('construction.stage', 'Stage')
    lots_ids = fields.Many2many('lot')
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
    total_cost = fields.Monetary('Coût total', compute='_compute_total_cost', store=True)
    address = fields.Text('Adresse du chantier')
    city = fields.Char('Ville')
    zip_code = fields.Char('Code postal')
    country_id = fields.Many2one('res.country', string='Pays')
    phone = fields.Char('Téléphone du chantier')
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  default=lambda self: self.env.company.currency_id)
    surface_m2 = fields.Float('Surface (m²)')
    nb_levels = fields.Integer('Nombre d\'étages')
    permit_number = fields.Char('Numéro de permis')
    permit_date = fields.Date('Date du permis')

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

    @api.constrains('date_start_contract', 'date_end_contract')
    def _check_contract_dates(self):
        for record in self:
            if record.date_start_contract and record.date_end_contract:
                if record.date_start_contract > record.date_end_contract:
                    raise ValidationError(_("La date de début ne peut pas être postérieure à la date de fin."))

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
            elif record.date_start_actual and record.state == 'active':
                delta = fields.Date.today() - record.date_start_actual
                record.duration_actual = delta.days + 1
            else:
                record.duration_actual = 0

    @api.depends('lots_ids.subcontractor_ids')
    def _compute_subcontractors(self):
        for record in self:
            all_subcontractors = record.lots_ids.mapped('subcontractor_ids')
            record.subcontractors = all_subcontractors

    @api.depends('lots_ids.price', 'lots_ids.is_finished')

    def _compute_construction_progression(self ):
        """
        """
        for record in self:
            total_cost = 0
            total_progress = 0
            for lot in record.lots_ids:
                total_cost += lot.price
                if lot.is_finished:
                    total_progress += lot.price
            record.progress = total_progress / len(record.lots_ids) if record.lots_ids else 0
            record.total_cost = total_cost

    @api.depends('date_end_contract')
    def _compute_days_remaining(self):
        today = fields.Date.context_today(self)
        for record in self:
            if record.date_end_contract:
                delta = record.date_end_contract - today
                record.days_remaining = delta.days if delta.days > 0 else 0
            else:
                record.days_remaining = 0

    @api.depends('lots_ids.price')
    def _compute_total_cost(self):
        for record in self:
            record.total_cost = sum(record.lots_ids.mapped('price'))

    @api.depends('state', 'stage', 'stage.chapter_id')
    def _compute_action_visibility(self):
        """Détermine quelles actions sont visibles selon l'état et l'étape du chantier"""
        for record in self:
            # Par défaut, masquer toutes les actions
            record.show_schedule_visit = False
            record.show_create_quote = False
            record.show_assign_subcontractors = False
            record.show_mark_not_pursued = False

            if not record.stage:
                continue

            # Logique basée sur l'état du chantier
            if record.state in ['active']:
                # Planifier une visite - toujours disponible pour les chantiers actifs
                record.show_schedule_visit = True

                # Créer un devis - selon l'étape
                if record.stage and record.stage.chapter_id:
                    chapter_name = record.stage.chapter_id.name
                    if chapter_name in ['Étude', 'Conception', 'Devis']:
                        record.show_create_quote = True

                # Assigner des sous-traitants - pour les phases d'exécution
                if record.stage and record.stage.chapter_id:
                    chapter_name = record.stage.chapter_id.name
                    if chapter_name in ['Exécution', 'Réalisation', 'Travaux']:
                        record.show_assign_subcontractors = True

            # Marquer sans suite - disponible pour les états draft et active
            if record.state in ['abandoned', 'active']:
                record.show_mark_not_pursued = True

    @api.depends('stage', 'stage.chapter_id', 'lots_ids', 'document_ids', 'visit_ids')
    def _compute_stage_validation_info(self):
        """Calcule les informations de validation pour passer à l'étape suivante"""
        for record in self:
            info_lines = []

            chapter_name = record.chapter_id.name
            stage_name = record.stage.name
            # TODO

    @api.depends('lots_ids', 'subcontractors')
    def _compute_available_subcontractors(self):
        for record in self:
            if not record.lots_ids:
                record.available_subcontractors = self.env['res.partner']
                continue

            # Utiliser les méthodes existantes de votre modèle res.partner
            available_subcontractors = self.env['res.partner']

            for lot in record.lots_ids:
                # Utiliser la méthode filter_subcontractors de votre modèle
                lot_subcontractors = self.env['res.partner'].get_subcontractors_by_lot(lot.id)
                available_subcontractors |= lot_subcontractors

            # Exclure ceux déjà assignés
            available_subcontractors = available_subcontractors - record.subcontractors

            record.available_subcontractors = available_subcontractors

    @api.depends('subcontractors', 'lots_ids')
    def _compute_counts(self):
        """Calcule les différents compteurs du chantier"""
        for record in self:
            # Compter les sous-traitants (qui viennent des lots via _compute_subcontractors)
            record.subcontractor_count = len(record.subcontractors) if record.subcontractors else 0

            # Pour sale_order_count, chercher les devis liés à ce chantier
            # Méthode 1: Par référence au nom du chantier dans sale.order
            sale_orders = self.env['sale.order'].search([
                '|',
                ('origin', 'ilike', record.name),
                ('client_order_ref', 'ilike', record.name)
            ])
            record.sale_order_count = len(sale_orders)



