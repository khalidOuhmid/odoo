"""
Construction Site (Chantier) Model

This module defines the core construction site management model including
workflow, validation, invoicing, and planning functionalities.
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)

# Business Rules and Constants
ACTION_RULES = {
    "show_schedule_visit": lambda rec: rec.state == "active",
    "show_create_quote": lambda rec: rec.state == "active"
                                     and rec.stage_id.chapter_id.name in {"Étude", "Conception", "Devis"},
    "show_assign_subcontractors": lambda rec: rec.state == "active"
                                              and rec.stage_id.chapter_id.name in {"Exécution", "Réalisation",
                                                                                   "Travaux"},
    "show_mark_not_pursued": lambda rec: rec.state in {"active", "abandoned"},
    "show_split_quote": lambda rec: rec.can_split_quote_to_purchase() if hasattr(rec, 'can_split_quote_to_purchase') else False,
    "show_invoice_setup": lambda rec: rec.state == "active" 
                                      and rec.stage_id.chapter_id.code == "PREP" 
                                      and rec.stage_id.code == "FD",
}

STAGE_VALIDATORS = {
    ("AO", "REC"): "check_reception_stage",
    ("AO", "VT"): "check_visit_stage",
    ("AO", "DE"): "check_quotation_sent_stage",
    ("PREP", "DA"): "check_quotation_accepted_stage",
    ("PREP", "FD"): "check_dossier_finalization_stage",
    ("TRAV", "T25"): "check_construction_25_percentage_stage",
    ("TRAV", "T50"): "check_construction_50_percentage_stage",
    ("TRAV", "T75"): "check_construction_75_percentage_stage",
    ("LEVEE", "LR"): "check_warranty_stage",
    ("RET", "RET"): "check_warranty_retention_stage",
}


class Chantier(models.Model):
    """
    Construction Site Model
    
    Manages construction projects from initial reception through completion,
    including workflow stages, budget tracking, invoicing, and subcontractor management.
    
    Inherits:
        mail.thread: Provides messaging and activity tracking
        mail.activity.mixin: Enables activity scheduling
    """
    _name = 'construction.chantier'
    _description = 'Construction Project'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Field Definitions
    name = fields.Char('Project Name', required=True)
    reference = fields.Char('Reference', copy=False, readonly=True, default='/')
    stage_id = fields.Many2one('construction.stage', 'Stage', group_expand='_read_group_stage_id', readonly=True)
    client = fields.Many2one('res.partner', 'Client', required=True)
    lots_ids = fields.One2many('construction.lot', 'chantier_id', string='Lots du chantier')
    chapter_name = fields.Char('Chapter Name', compute='_compute_chapter_name', store=True)
    user_ids = fields.Many2many('res.users', string='Project Users')
    description = fields.Text('Description')
    notes = fields.Text('Notes')
    
    # Indicateur technique pour déclencher la vérification des factures hors du contexte de calcul
    need_invoice_check = fields.Boolean('Vérification facturation nécessaire', default=False, copy=False)

    subcontractor_ids = fields.Many2many(
        'res.partner',
        'construction_chantier_subcontractor_rel',
        'chantier_id', 'partner_id',
        string='Sous-traitants',
        domain="['|', ('supplier_rank', '>', 0), ('contact_type', '=', 'employee')]",
        help="Sous-traitants assignés à ce chantier (inclut internes pour suivi/planning)"
    )

    # Dates contractuelles et internes
    date_start_contract = fields.Date('Date de début contractuelle', tracking=True)
    date_end_contract = fields.Date('Date de fin contractuelle', tracking=True)
    date_start_internal = fields.Date('Date de début interne', tracking=True)
    date_end_internal = fields.Date('Date de fin interne', tracking=True)
    date_start_estimated = fields.Date('Date de début estimée', tracking=True)
    date_end_estimated = fields.Date('Date de fin estimée ', tracking=True)

    progress = fields.Float('Progression (%)', compute='_compute_construction_progression', store=True, default=0.0)
    days_remaining = fields.Integer(
        'Jours restants',
        compute='_compute_days_remaining',
        store=True,
        default=0,
        help="Nombre de jours restants avant la date d'échéance"
    )

    # Timer visuel pour proximité des échéances
    deadline_status = fields.Selection([
        ('on_time', 'Dans les temps'),
        ('warning', 'Attention'),
        ('late', 'En retard'),
        ('critical', 'Critique')
    ], string='Statut échéance', compute='_compute_deadline_status', store=True, default='on_time')

    deadline_color = fields.Integer(
        'Couleur échéance',
        compute='_compute_deadline_status',
        store=True,
        default=10,
        help="Couleur pour l'indicateur visuel: 10=vert, 3=jaune, 2=orange, 1=rouge"
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
    quotation_ids = fields.One2many('sale.order', 'chantier_id', string='Devis')
    quotation_count = fields.Integer('Nombre de devis', compute='_compute_quotation_count')

    # Relations avec la facturation
    invoice_schedule_ids = fields.One2many(
        'construction.invoice.schedule', 
        'chantier_id', 
        string='Planning de facturation'
    )
    
    # Champs calculés pour la facturation
    invoice_schedule_planned_count = fields.Integer(
        'Planifications prévues',
        compute='_compute_invoice_schedule_stats'
    )
    invoice_schedule_ready_count = fields.Integer(
        'Planifications prêtes',
        compute='_compute_invoice_schedule_stats'
    )
    invoice_schedule_invoiced_count = fields.Integer(
        'Planifications facturées',
        compute='_compute_invoice_schedule_stats'
    )
    invoice_schedule_total_amount = fields.Monetary(
        'Montant total planifié',
        compute='_compute_invoice_schedule_stats',
        currency_field='currency_id'
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

    # Cycle de facturation
    invoice_type_id = fields.Many2one(
        'construction.invoice_type',
        string='Cycle de facturation',
        help="Pattern de facturation à appliquer pour ce chantier"
    )
    # Nouveau : devis principal sur lequel baser la facturation
    main_quote_id = fields.Many2one(
        'sale.order',
        string='Devis principal',
        help="Devis client principal servant de référence pour la facturation"
    )
    invoice_schedule_ids = fields.One2many(
        'construction.invoice.schedule',
        'chantier_id',
        string='Planning de facturation',
        help="Planning détaillé des factures pour ce chantier"
    )
    available_subcontractors = fields.Many2many(
        'res.partner',
        string='Sous-traitants disponibles',
        compute='_compute_available_subcontractors'
    )

    visit_ids = fields.One2many('construction.visit', 'chantier_id', string='Visites techniques')
    document_ids = fields.One2many('construction.document', 'chantier_id', string='Documents')
    document_count_by_type = fields.Text('Statistiques documents', compute='_compute_document_count_by_type')
    sale_order_count = fields.Integer('Nombre de devis/commandes', compute='_compute_counts', store=True)
    subcontractor_count = fields.Integer('Nombre de sous-traitants', compute='_compute_counts', store=True)
    lots_count = fields.Integer('Nombre de lots', compute='_compute_counts', store=True)
    
    # =================== CHAMPS CALCULÉS POUR COMMANDES ===================
    
    total_order_lines = fields.Integer(
        string='Total articles',
        compute='_compute_order_stats',
        help="Nombre total d'articles dans tous les lots"
    )
    
    total_ordered_lines = fields.Integer(
        string='Total commandés',
        compute='_compute_order_stats',
        help="Nombre total d'articles commandés"
    )
    
    total_tracking_lines = fields.Integer(
        string='Total avec tracking',
        compute='_compute_order_stats',
        help="Nombre total d'articles avec tracking"
    )
    
    order_progress = fields.Float(
        string='Progression commandes',
        compute='_compute_order_stats',
        help="Pourcentage d'articles commandés"
    )
    
    stage_validation_info = fields.Text(
        'Info de validation',
        compute='_compute_stage_validation_info',
        help="Informations sur les conditions pour passer à l'étape suivante"
    )

    show_schedule_visit = fields.Boolean('Afficher planifier visite', compute='_compute_action_visibility',
                                         default=False)
    show_create_quote = fields.Boolean('Afficher créer devis', compute='_compute_action_visibility', default=False)
    show_assign_subcontractors = fields.Boolean('Afficher assigner sous-traitants',
                                                compute='_compute_action_visibility', default=False)
    show_mark_not_pursued = fields.Boolean('Afficher marquer sans suite', compute='_compute_action_visibility',
                                           default=False)
    show_split_quote = fields.Boolean('Afficher diviser devis', compute='_compute_action_visibility', default=False)
    show_invoice_setup = fields.Boolean('Afficher configuration facturation', compute='_compute_action_visibility', default=False)

    planning_task_ids = fields.One2many('construction.planning.task', 'chantier_id', string='Tâches de planning')
    purchase_order_ids = fields.One2many('purchase.order', 'chantier_id', string="Bons de commande")
    purchase_order_line_ids = fields.One2many(
        'purchase.order.line',
        'chantier_id',
        string='Articles à recevoir'
    )

    _sql_constraints = [
        ('positive_cost', 'CHECK(total_cost >= 0)', 'Le coût total doit être positif'),
        ('positive_surface', 'CHECK(surface_m2 >= 0)', 'La surface doit être positive'),
        ('progress_range', 'CHECK(progress >= 0 AND progress <= 100)',
         'La progression doit être entre 0 et 100%'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        """
        Create construction site records with automatic reference generation.
        
        Args:
            vals_list (list): List of value dictionaries for record creation
            
        Returns:
            recordset: Created chantier records
            
        Note:
            - Generates unique reference if not provided
            - Assigns default initial stage (reception)
        """
        for vals in vals_list:
            # Génération automatique de référence
            if not vals.get('reference') or vals.get('reference') == '/':
                vals['reference'] = self.env['ir.sequence'].next_by_code('construction.chantier') or '/'

            # Assigner automatiquement le stage de départ
            if not vals.get('stage_id'):
                # Utiliser l'external_id défini dans construction_data.xml
                default_stage = self.env.ref('construction_base.stage_reception')
                vals['stage_id'] = default_stage.id

        chantiers = super().create(vals_list)

        return chantiers

    def write(self, vals):
        """
        Override write to control stage modifications and trigger invoice checks.
        
        Args:
            vals (dict): Values to update
            
        Returns:
            bool: True if successful
            
        Raises:
            ValidationError: If non-admin user tries to modify stage directly
            
        Note:
            - Only administrators or workflow methods can modify stage_id
            - Automatically triggers invoice checks when needed
        """
        if 'stage_id' in vals and not self.env.context.get('bypass_stage_validation', False):
            # Vérifier si l'utilisateur a les droits d'administrateur
            if not self.env.user.has_group('base.group_system'):
                raise ValidationError(
                    "Modification directe de l'étape interdite.\n"
                    "Utilisez les boutons 'Étape suivante' ou 'Étape précédente' "
                    "pour respecter le workflow métier.\n\n"
                    "Seuls les administrateurs peuvent forcer un changement d'étape."
                )

        result = super().write(vals)
        
        # Vérifier si certains records ont besoin d'une vérification de facturation
        # et si nous ne sommes pas déjà en train de vérifier les factures
        records_to_check = self.filtered('need_invoice_check')
        if records_to_check and not self.env.context.get('checking_invoices'):
            for record in records_to_check:
                if record.invoice_schedule_ids:
                    # Désactiver l'indicateur technique avant de lancer la vérification
                    record.with_context(checking_invoices=True).write({'need_invoice_check': False})
                    try:
                        # Appeler la méthode avec un contexte spécial pour éviter les problèmes
                        record.with_context(checking_invoices=True)._check_invoice_triggers()
                    except Exception as e:
                        # Log l'erreur mais ne pas bloquer le processus
                        _logger.error(f"Erreur lors de la vérification des factures: {e}")
                    
        return result



    @api.constrains('date_start_contract', 'date_end_contract')
    def _check_contract_dates(self):
        for record in self:
            if record.date_start_contract and record.date_end_contract:
                if record.date_start_contract > record.date_end_contract:
                    raise ValidationError(_("La date de début ne peut pas être postérieure à la date de fin."))

    @api.depends('stage_id', 'stage_id.chapter_id', 'stage_id.chapter_id.name')
    def _compute_chapter_name(self):
        """
        Compute chapter name from current stage.
        
        Sets chapter_name field based on the stage's chapter reference.
        """
        for record in self:
            if record.stage_id and record.stage_id.chapter_id:
                record.chapter_name = record.stage_id.chapter_id.name
            else:
                record.chapter_name = False

    @api.depends('date_start_contract', 'date_end_contract')
    def _compute_duration_planned(self):
        """
        Compute planned duration in days from contract dates.
        
        Calculates the number of days between contract start and end dates.
        """
        for record in self:
            if record.date_start_contract and record.date_end_contract:
                delta = record.date_end_contract - record.date_start_contract
                record.duration_planned = delta.days + 1

    @api.depends('date_start_internal', 'date_end_internal')
    def _compute_duration_actual(self):
        """
        Compute actual duration in days from internal dates.
        
        Calculates duration from internal start/end dates, or from start to today
        if the project is still active.
        """
        for record in self:
            if record.date_start_internal and record.date_end_internal:
                delta = record.date_end_internal - record.date_start_internal
                record.duration_actual = delta.days + 1
            elif record.date_start_internal and record.state == 'active':
                delta = fields.Date.today() - record.date_start_internal
                record.duration_actual = delta.days + 1
            else:
                record.duration_actual = 0

    @api.depends('lots_ids.price', 'lots_ids.price_from_quote', 'lots_ids.is_finished', 'lots_ids.quote_state')
    def _compute_construction_progression(self):
        """Calcule la progression basée sur le coût des lots terminés"""
        for record in self:
            old_progress = record.progress
            # Utiliser price_from_quote comme fallback si price est nul pour refléter le devis accepté
            total_cost = sum((lot.price if lot.price else getattr(lot, 'price_from_quote', 0.0)) for lot in record.lots_ids)
            if total_cost > 0:
                # Considérer un lot « compté » dans la progression s'il est terminé
                # ou si son devis est accepté (validation métier courante)
                completed_lots = record.lots_ids.filtered(
                    lambda l: getattr(l, 'is_finished', False) or getattr(l, 'quote_state', False) == 'accepted'
                )
                completed_cost = sum((lot.price if lot.price else getattr(lot, 'price_from_quote', 0.0)) for lot in completed_lots)
                record.progress = (completed_cost / total_cost) * 100
            else:
                record.progress = 0.0

            # Marquer que les seuils de facturation doivent être vérifiés, mais ne pas le faire pendant le compute
            if old_progress != record.progress and record.invoice_schedule_ids:
                # On active l'indicateur technique qui sera traité lors du write
                record.need_invoice_check = True

    @api.depends('date_end_contract')
    def _compute_days_remaining(self):
        today = fields.Date.context_today(self)
        for record in self:
            if record.date_end_contract:
                delta = record.date_end_contract - today
                record.days_remaining = delta.days if delta.days > 0 else 0
            else:
                record.days_remaining = 0

    @api.depends('days_remaining', 'state')
    def _compute_deadline_status(self):
        """Calculer le statut et la couleur selon la proximité de l'échéance"""
        for record in self:
            if record.state in ('completed', 'abandoned'):
                record.deadline_status = 'on_time'
                record.deadline_color = 10  # Vert
            elif record.days_remaining < 0:
                record.deadline_status = 'critical'
                record.deadline_color = 1  # Rouge
            elif record.days_remaining <= 7:
                record.deadline_status = 'late'
                record.deadline_color = 2  # Orange
            elif record.days_remaining <= 30:
                record.deadline_status = 'warning'
                record.deadline_color = 3  # Jaune
            else:
                record.deadline_status = 'on_time'
                record.deadline_color = 10  # Vert

    @api.depends('lots_ids.price', 'lots_ids.price_from_quote')
    def _compute_total_cost(self):
        for record in self:
            # Total du chantier basé sur le devis principal accepté (fallback sur price_from_quote)
            record.total_cost = sum((lot.price if lot.price else getattr(lot, 'price_from_quote', 0.0)) for lot in record.lots_ids)

    def action_view_all_visits(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Calendrier des visites',
            'res_model': 'construction.visit',
            'view_mode': 'calendar,list,form',
            'domain': [('chantier_id', '=', self.id)],
            'context': {'default_chantier_id': self.id},
            'target': 'current',
        }

    def _compute_available_subcontractors(self):
        subcontractors = self.env['res.partner'].search([('is_subcontractor', '=', True)])
        for record in self:
            record.available_subcontractors = subcontractors

    @api.depends('subcontractor_ids', 'lots_ids', 'quotation_ids')
    def _compute_counts(self):
        """Calcule les différents compteurs du chantier"""
        for record in self:
            # Compter les lots
            record.lots_count = len(record.lots_ids)

            # Compter les sous-traitants (qui viennent des lots via _compute_subcontractors)
            record.subcontractor_count = len(record.subcontractor_ids)

            # Pour sale_order_count, utiliser la relation One2many si elle existe
            if hasattr(record, 'quotation_ids') and record.quotation_ids:
                record.sale_order_count = len(record.quotation_ids)
            else:
                # Sinon, chercher par référence au nom du chantier
                sale_orders = self.env['sale.order'].search([
                    '|',
                    ('origin', 'ilike', record.name),
                    ('client_order_ref', 'ilike', record.name)
                ])
                record.sale_order_count = len(sale_orders)

    @api.depends('lots_ids.order_line_ids', 'lots_ids.order_line_ids.order_date', 'lots_ids.order_line_ids.tracking_link')
    def _compute_order_stats(self):
        """Calcule les statistiques globales de commande pour le chantier"""
        for record in self:
            all_lines = record.lots_ids.mapped('order_line_ids')
            
            record.total_order_lines = len(all_lines)
            record.total_ordered_lines = len(all_lines.filtered('order_date'))
            record.total_tracking_lines = len(all_lines.filtered('tracking_link'))
            
            # Calcul du pourcentage de progression
            if record.total_order_lines > 0:
                record.order_progress = (record.total_ordered_lines * 100.0) / record.total_order_lines
            else:
                record.order_progress = 0.0

    @api.depends('document_ids.document_type')
    def _compute_document_count_by_type(self):
        """Calcule les statistiques de documents par type"""
        for record in self:
            if not record.document_ids:
                record.document_count_by_type = "Aucun document"
            else:
                # Grouper par type
                types_count = {}
                for doc in record.document_ids:
                    doc_type = dict(doc._fields['document_type'].selection).get(doc.document_type, doc.document_type)
                    types_count[doc_type] = types_count.get(doc_type, 0) + 1
                
                # Formatter le résultat
                result_lines = []
                for doc_type, count in types_count.items():
                    result_lines.append(f"• {doc_type}: {count}")
                
                record.document_count_by_type = "\n".join(result_lines)

    def _get_next_progress_threshold(self, current_progress):
        """Retourne le prochain seuil de progression pour le chapitre Travaux"""
        thresholds = [25, 50, 75, 100]
        for threshold in thresholds:
            if current_progress < threshold:
                return threshold
        return None

    @api.depends("state", "stage_id", "stage_id.chapter_id")
    def _compute_action_visibility(self):
        """Active / désactive les boutons en une seule boucle, sans duplication."""
        for rec in self:
            if not rec.stage_id:  # rien à faire tant qu’aucune étape n’est définie
                for field in ACTION_RULES:
                    setattr(rec, field, False)
                continue

            for field, rule in ACTION_RULES.items():
                setattr(rec, field, bool(rule(rec)))

    @api.depends(
        "stage_id", "stage_id.chapter_id", "lots_ids", "document_ids",
        "visit_ids", "progress", "total_cost", "subcontractor_ids",
        "date_start_contract", "date_end_contract",
    )
    def _compute_stage_validation_info(self):
        """Récapitulatif des pré-requis pour l’étape suivante, sans copier-coller."""
        for rec in self:
            # Check if stage is defined
            if not (rec.stage_id and rec.stage_id.chapter_id):
                rec.stage_validation_info = "[ERROR] No stage defined"
                continue

            chap_code, stage_code = rec.stage_id.chapter_id.code, rec.stage_id.code

            # ------------------------------------------------------------------
            # 1️⃣  Exécuter le validateur métier associé (s’il existe)
            # ------------------------------------------------------------------
            ok, details = True, ""
            method_name = STAGE_VALIDATORS.get((chap_code, stage_code))
            if method_name:
                ok, details = getattr(rec, method_name)()

            # ------------------------------------------------------------------
            # 2️⃣  Cas particulier « TRAV » (seuils de progression)
            # ------------------------------------------------------------------
            elif chap_code == "TRAV":
                next_pct = rec._get_next_progress_threshold(rec.progress)
                if next_pct and rec.progress < next_pct:
                    ok, details = False, f"Progression insuffisante ({rec.progress:.1f}% < {next_pct}%)"

            # Build user message
            header = f"Stage: {rec.stage_id.chapter_id.name} - {rec.stage_id.name}"
            footer = "[OK] Ready for next stage" if ok else "[BLOCKED] Conditions not met"
            rec.stage_validation_info = "\n".join(
                filter(None, (header, details, "", footer))
            )

    def _can_move_to_next_stage(self):
        """Ré-utilise exactement le même mapping que ci-dessus."""
        if not (self.stage_id and self.stage_id.chapter_id):
            return False, "Aucune étape définie"

        chap_code, stage_code = self.stage_id.chapter_id.code, self.stage_id.code
        method_name = STAGE_VALIDATORS.get((chap_code, stage_code))

        # 1️⃣  Exécuter le validateur métier associé (s'il existe)
        if method_name:
            return getattr(self, method_name)()  # renvoie (bool, msg)

        # 2️⃣  Cas particulier « TRAV » (seuils de progression)
        elif chap_code == "TRAV":
            next_pct = self._get_next_progress_threshold(self.progress)
            if next_pct and self.progress < next_pct:
                return False, f"Progression insuffisante ({self.progress:.1f}% < {next_pct}%)"
            return True, "Conditions remplies"

        # 3️⃣  Pas de validateur spécifique → conditions remplies par défaut
        return True, "Conditions remplies"

    def check_reception_stage(self):
        """
        Vérifie que toutes les informations indispensables au dossier « Réception »
        sont renseignées :

          • client
          • adresse du chantier
          • description des travaux
          • téléphone du chantier

        Retour :
            (bool, str)
                - True,  ""   → toutes les données sont présentes
                - False, msg → msg liste les champs manquants
        """
        missing = []

        if not self.client:
            missing.append("client")
        if not self.address:
            missing.append("adresse du chantier")
        if not self.description:
            missing.append("description des travaux")
        if not self.phone:
            missing.append("téléphone du chantier")

        if missing:
            # Construction d’un message clair et homogène
            msg = "Champs manquants : " + ", ".join(missing)
            return False, msg

        return True, ""

    def check_warranty_retention_stage(self):
        if self.date_end_contract:
            end_warranty = self.date_end_contract + timedelta(days=365)
        if datetime.now().date() < end_warranty:
            remaining_days = (end_warranty - datetime.now().date()).days
            return False, f"Période de garantie en cours ({remaining_days} jour(s) restant(s))"
        else:
            return True, "OK"

    def check_warranty_stage(self):
        if self.progress < 100:
            return False, "Réserves non traitées"
        reception_docs = self.document_ids.filtered(lambda d: d.document_type == 'schedule')
        if not reception_docs:
            return False, "Réception client non effectuée"
        else:
            return True, "OK"

    def check_visit_stage(self):
        if not self.visit_ids:
            return False, "Aucune visite technique réalisée"
        completed_visits = self.visit_ids.filtered(lambda v: v.state == 'completed')
        if not completed_visits:
            return False, "Visite technique non terminée"
        else:
            return True, "OK"

    def check_quotation_sent_stage(self):
        if not self.lots_ids:
            return False, "Lots de travaux non définis"
        if self.quotation_count <= 0:
            return False, "Devis non établi"

        # Vérifier qu'au moins un devis soit accepté
        accepted_quotations = self.quotation_ids.filtered(lambda q: q.state in ['sale', 'validated'])
        if not accepted_quotations:
            return False, "Aucun devis accepté par le client"
        else:
            return True, "OK"

    def check_quotation_accepted_stage(self):
        if not self.subcontractor_count == self.lots_count:
            return False, "Il manque un ou plusieurs sous-traitants"
        if not self.date_start_contract:
            return False, "Date de début contractuelle non définie"
        if not self.date_end_contract:
            return False, "Date de fin contractuelle non définie"
        # Utiliser les champs existants: réel ou estimé
        if not (self.date_end_internal or self.date_end_estimated):
            return False, "Date de fin (interne ou estimée) non définie"
        if not (self.date_start_internal or self.date_start_estimated):
            return False, "Date de début (interne ou estimée) non définie"
        else:
            return True, "OK"

    def check_dossier_finalization_stage(self):
        """
        Valide que :
          1. Chaque lot possède au moins un sous-traitant.
          2. Au moins un devis du sous-traitant est accepté (état « sale » ou « done »).
          3. Les données de facturation et de planning sont complètes.
          4. Chaque sous-traitant (sauf internes) a un devis signé.

        Retour :
            (bool, str) :
                - True,  ""   → tout est conforme
                - False, msg → msg liste les points bloquants
        """
        # 1️⃣ Vérifier la présence de lots
        if not self.lots_ids:
            return False, "Aucun lot défini"

        incomplete_lots = []

        # 2️⃣ Parcourir les lots
        for lot in self.lots_ids:
            # 2.a Lot sans sous-traitant
            if not lot.subcontractor_ids:
                incomplete_lots.append(f"{lot.name} (pas de sous-traitant)")
                continue  # inutile de poursuivre les contrôles pour ce lot

            # 2.b Rechercher les devis acceptés pour le(s) sous-traitant(s)
            lot_orders = self.env["sale.order"].search([
                ("partner_id", "in", lot.subcontractor_ids.ids),
                ("chantier_id", "=", self.id),
            ])

            accepted_orders = lot_orders.filtered(
                lambda o: o.state in ("sale", "validated")
            )

            if not accepted_orders:
                subcontractor_names = ", ".join(lot.subcontractor_ids.mapped("name"))
                incomplete_lots.append(f"{lot.name} ({subcontractor_names})")

        # 3️⃣ Synthèse des lots incomplets
        if incomplete_lots:
            msg = "Lots sans devis accepté : " + "; ".join(incomplete_lots)
            return False, msg

        # 4️⃣ Vérifier que chaque sous-traitant (sauf internes) a un devis signé
        # Interprétation: un "interne" est un partenaire avec contact_type = 'employee'.
        # On exclut donc les internes de l'exigence de devis signé.
        external_subcontractors = self.subcontractor_ids.filtered(
            lambda p: getattr(p, 'contact_type', False) != 'employee' and getattr(p, 'supplier_rank', 0) > 0
        )
        
        subcontractors_without_signed_quote = []
        for subcontractor in external_subcontractors:
            # Rechercher les devis signés pour ce sous-traitant
            signed_quotes = self.env["sale.order"].search([
                ("partner_id", "=", subcontractor.id),
                ("chantier_id", "=", self.id),
                ("state", "in", ["sale", "done", "validated"])
            ])
            
            if not signed_quotes:
                subcontractors_without_signed_quote.append(subcontractor.name)
        
        if subcontractors_without_signed_quote:
            msg = "Sous-traitants sans devis signé : " + ", ".join(subcontractors_without_signed_quote)
            return False, msg

        # 5️⃣ Autres vérifications globales
        if not self.invoice_type_id:
            return False, "Cycle de facturation non sélectionné"

        if not self.main_quote_id:
            return False, "Devis principal non sélectionné"

        if not self.date_start_contract or not self.date_end_contract:
            return False, "Planning de chantier incomplet"

        # 6️⃣ Tout est conforme
        return True, ""

    def check_construction_25_percentage_stage(self):
        if not self.progress >= 25:
            return False, "Progression insuffisante"
        return True, ""

    def check_construction_50_percentage_stage(self):
        if not self.progress >= 50:
            return False, "Progression insuffisante"
        return True, ""

    def check_construction_75_percentage_stage(self):
        if not self.progress >= 75:
            return False, "Progression insuffisante"
        return True, ""

    def check_construction_100_percentage_stage(self):
        if not self.progress >= 100:
            return False, "Progression insuffisante"
        return True, ""

    def _can_move_to_previous_stage(self):
        """Vérifie si le chantier peut revenir à l'étape précédente"""
        if not self.stage_id:
            return False, "Aucune étape définie"

        # Vérifications de sécurité pour éviter la régression inappropriée
        chapter_code = self.stage_id.chapter_id.code
        stage_code = self.stage_id.code

        # Ne pas permettre le retour depuis certaines étapes critiques
        if chapter_code == 'ARCH':  # Archive
            return False, "Impossible de revenir depuis l'archive sans autorisation spéciale"

        if chapter_code == 'RET':  # Retenue garantie
            return False, "Impossible de revenir depuis la période de garantie"

        if chapter_code == 'TRAV' and self.progress > 50:
            return False, "Travaux trop avancés pour un retour automatique"

        return True, "Retour autorisé"

    def action_move_to_next_stage(self):
        """Passer à l'étape suivante selon le workflow du cahier des charges"""
        self.ensure_one()

        if not self.stage_id:
            raise ValidationError("Aucune étape définie pour ce chantier")

        # Vérifier les conditions avec la logique centralisée
        can_proceed, message = self._can_move_to_next_stage()

        if can_proceed:
            # Trouver l'étape suivante
            next_stage = self._get_next_stage()

            if not next_stage:
                raise ValidationError("Aucune étape suivante trouvée")

            # Effectuer la transition avec bypass de validation
            old_stage = self.stage_id.name
            self.with_context(bypass_stage_validation=True).write({'stage_id': next_stage.id})

            # Log de la transition
            self.message_post(
                body=f"Chantier passé de '{old_stage}' à '{next_stage.name}'",
                message_type='notification'
            )

            # Actions automatiques selon l'étape
            self._trigger_stage_actions()

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Étape mise à jour',
                    'message': f'Chantier passé à : {next_stage.name}',
                    'type': 'success'
                }
            }
        else:
            # Validation échouée : vérifier si admin pour proposer le forçage
            if self.env.user.has_group('base.group_system'):
                # Trouver l'étape suivante pour pré-remplir le wizard
                next_stage = self._get_next_stage()
                default_new_stage_id = next_stage.id if next_stage else False

                # Retourner l'action pour ouvrir le wizard
                return {
                    'name': 'Forcer le Changement d\'Étape',
                    'type': 'ir.actions.act_window',
                    'res_model': 'construction.force.stage.wizard',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {
                        'default_chantier_id': self.id,
                        'default_current_stage_id': self.stage_id.id,
                        'default_new_stage_id': default_new_stage_id,
                    }
                }
            else:
                # Non admin : lever l'erreur standard
                raise ValidationError(f"Impossible de passer à l'étape suivante :\n{message}")

    def _get_next_stage(self):
        """Détermine l'étape suivante selon la logique métier"""
        chapter_code = self.stage_id.chapter_id.code
        stage_code = self.stage_id.code

        # Gestion spéciale pour les travaux (progression par seuils)
        if chapter_code == 'TRAV':
            next_threshold = self._get_next_progress_threshold(self.progress)
            if next_threshold:
                # Chercher l'étape correspondant au seuil
                next_stage = self.env['construction.stage'].search([
                    ('chapter_id.code', '=', 'TRAV'),
                    ('name', 'ilike', f'{next_threshold}%')
                ], limit=1)

                # Génération automatique de facture aux seuils
                if next_threshold in [30, 60, 90]:
                    self._generate_invoice_at_threshold(next_threshold)

                return next_stage
            else:
                # Travaux terminés → Levée de réserves
                return self.env['construction.stage'].search([
                    ('chapter_id.code', '=', 'LEVEE'),
                    ('code', '=', 'LR')
                ], limit=1)
        else:
            # Progression normale dans le même chapitre ou chapitre suivant
            next_stage = self.stage_id.get_next_stage()

            # Si pas d'étape suivante dans le chapitre, passer au chapitre suivant
            if not next_stage:
                current_chapter = self.stage_id.chapter_id
                next_chapter = self.env['construction.chapter'].search([
                    ('sequence', '>', current_chapter.sequence)
                ], order='sequence', limit=1)

                if next_chapter:
                    next_stage = self.env['construction.stage'].search([
                        ('chapter_id', '=', next_chapter.id)
                    ], order='sequence', limit=1)

            return next_stage

    def action_move_to_previous_stage(self):
        """Revenir à l'étape précédente avec vérifications de sécurité"""
        self.ensure_one()

        if not self.stage_id:
            raise ValidationError("Aucune étape définie pour ce chantier")

        # Vérifier les conditions de retour
        can_proceed, message = self._can_move_to_previous_stage()
        if not can_proceed:
            raise ValidationError(f"Impossible de revenir à l'étape précédente :\n{message}")

        # Trouver l'étape précédente
        previous_stage = self.stage_id.get_previous_stage()

        # Si pas d'étape précédente dans le chapitre, revenir au chapitre précédent
        if not previous_stage:
            current_chapter = self.stage_id.chapter_id
            previous_chapter = self.env['construction.chapter'].search([
                ('sequence', '<', current_chapter.sequence)
            ], order='sequence desc', limit=1)

            if previous_chapter:
                previous_stage = self.env['construction.stage'].search([
                    ('chapter_id', '=', previous_chapter.id)
                ], order='sequence desc', limit=1)

        if not previous_stage:
            raise ValidationError("Aucune étape précédente trouvée")

        # Effectuer la transition avec bypass de validation
        old_stage = self.stage_id.name
        self.with_context(bypass_stage_validation=True).write({'stage_id': previous_stage.id})

        # Log de la transition
        self.message_post(
            body=f"Chantier rétrogradé de '{old_stage}' à '{previous_stage.name}'",
            message_type='notification'
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Étape mise à jour',
                'message': f'Chantier rétrogradé à : {previous_stage.name}',
                'type': 'warning'
            }
        }

    def _generate_invoice_at_threshold(self, threshold):
        """Génère automatiquement une facture au seuil donné"""
        # Logique de génération de facture selon le cahier des charges
        # 30%, 60%, 90% d'avancement
        percentage = threshold / 100.0
        amount = self.total_cost * percentage

        # Log de la génération de facture
        self.message_post(
            body=f"Facture automatique générée : {threshold}% = {amount:,.2f} €",
            message_type='notification'
        )

        # Ici on pourrait créer une vraie facture dans le module account
        # Pour l'instant, on se contente du log

    @api.depends('state', 'stage_id', 'stage_id.chapter_id')
    def _compute_show_create_quote(self):
        for rec in self:
            rec.show_create_quote = (
                    rec.state == 'active' and
                    rec.stage_id and
                    rec.stage_id.code in ['DE', 'DA', 'Devis']
            )
        show_create_quote = fields.Boolean(compute='_compute_show_create_quote')

    def _trigger_stage_actions(self):
        """Déclenche les actions automatiques selon l'étape atteinte"""
        chapter_code = self.stage_id.chapter_id.code
        stage_code = self.stage_id.code
        self._compute_stage_validation_info()
        # Actions automatiques selon le cahier des charges
        if chapter_code == 'PREP' and stage_code == 'FD':  # Finalisation dossier
            # Déclencher automatiquement les acomptes de signature si configurés
            if self.invoice_schedule_ids:
                advance_payments = self.invoice_schedule_ids.filtered(
                    lambda s: s.is_advance_payment and s.state == 'planned'
                )
                if advance_payments:
                    for payment in advance_payments:
                        payment.write({
                            'state': 'ready',
                            'is_triggered': True
                        })

                    self.message_post(
                        body=f"Advance payments: {len(advance_payments)} signature advance payment(s) "
                             f"automatically activated (file completion stage reached)",
                        message_type='notification'
                    )

        elif chapter_code == 'RET':  # Retenue garantie
            # Marquer la retenue de 5% pendant 1 an
            self.message_post(
                body="Retenue de garantie activée (5% pendant 1 an)",
                message_type='comment'
            )

        elif chapter_code == 'ARCH' and stage_code == 'CLOT':
            # Archivage automatique
            self.message_post(
                body="Projet archivé automatiquement - Dossier clôturé",
                message_type='comment'
            )

    def action_force_stage_change(self):
        """Action pour forcer un changement d'étape (administrateurs uniquement)"""
        if not self.env.user.has_group('base.group_system'):
            raise ValidationError("Seuls les administrateurs peuvent forcer un changement d'étape.")

        # Temporarily simple message - wizard will be added later
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Admin Function',
                'message': 'This function will be available soon',
                'type': 'info'
            }
        }

    def action_schedule_visit(self):
        """Ouvrir le formulaire de création de visite"""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Planifier une visite',
            'res_model': 'construction.visit',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_chantier_id': self.id,
                'default_name': f'Visite - {self.name}',
            }
        }

    def action_view_subcontractors(self):
        """Action pour voir les sous-traitants du chantier"""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': f'Sous-traitants - {self.name}',
            'res_model': 'res.partner',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.subcontractor_ids.ids)],
            'context': {
                'default_supplier_rank': 1,
                'default_is_company': True,
            },
            'target': 'current',
        }

    def action_view_budget(self):
        """Action pour voir le détail du budget/lots"""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': f'Budget - {self.name}',
            'res_model': 'construction.lot',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.lots_ids.ids)],
            'context': {
                'default_chantier_id': self.id,
                'search_default_chantier': 1,
            },
            'target': 'current',
        }

    @api.depends('quotation_ids')
    def _compute_quotation_count(self):
        for record in self:
            record.quotation_count = len(record.quotation_ids)

    @api.depends('invoice_schedule_ids.state', 'invoice_schedule_ids.amount_fixed')
    def _compute_invoice_schedule_stats(self):
        for record in self:
            schedules = record.invoice_schedule_ids
            record.invoice_schedule_planned_count = len(schedules.filtered(lambda s: s.state == 'planned'))
            record.invoice_schedule_ready_count = len(schedules.filtered(lambda s: s.state == 'ready'))
            record.invoice_schedule_invoiced_count = len(schedules.filtered(lambda s: s.state == 'invoiced'))
            record.invoice_schedule_total_amount = sum(schedules.mapped('amount_fixed'))

    def action_create_intelligent_quote(self):
        """Créer un nouveau devis lié au chantier"""
        self.ensure_one()

        # Vérifier qu'il y a des lots sélectionnés
        if not self.lots_ids:
            raise ValidationError(_(
                "Veuillez d'abord sélectionner des lots pour ce chantier "
                "avant de créer un devis."
            ))

        # Créer le devis directement
        new_quote = self.env['sale.order'].create({
            'partner_id': self.client.id if self.client else False,
            'chantier_id': self.id,
            'lot_ids': [(6, 0, self.lots_ids.ids)],  # Copier les lots du chantier
            'state': 'draft',
        })

        # Ouvrir directement le formulaire sale.order
        return {
            'type': 'ir.actions.act_window',
            'name': f'Devis - {self.name}',
            'res_model': 'sale.order',
            'res_id': new_quote.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_chantier_id': self.id,
                'default_partner_id': self.client.id if self.client else False,
                'form_view_initial_mode': 'edit',
            }
        }

    def action_view_quotations(self):
        """Voir tous les devis du chantier"""
        self.ensure_one()

        # Action simplifiée sans référence externe potentiellement problématique
        return {
            'type': 'ir.actions.act_window',
            'name': f'Devis - {self.name}',
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'domain': [('chantier_id', '=', self.id)] if hasattr(self.env['sale.order'], 'chantier_id') else [],
            'context': {
                'default_chantier_id': self.id,
                'default_partner_id': self.client.id if self.client else False,
            },
            'target': 'current',
        }

    def _create_default_lots(self):
        """Crée les lots par défaut pour un nouveau chantier basés sur les templates"""
        self.ensure_one()
        
        # Récupérer tous les templates de lots actifs
        lot_templates = self.env['construction.lot.template'].search([
            ('active', '=', True)
        ], order='name')
        
        if not lot_templates:
            _logger.warning("Aucun template de lot trouvé. Création d'un lot par défaut.")
            # Créer un lot par défaut si aucun template n'existe
            self.env['construction.lot'].create({
                'name': 'Général',
                'code': 'GEN',
                'color': 0,
                'chantier_id': self.id,
                'price': 0.0,
                'is_finished': False,
                'quote_state': 'draft',
                'description': 'Lot général créé automatiquement',
            })
            return
        
        # Créer un lot spécifique à ce chantier pour chaque template
        for template in lot_templates:
            template.create_lot_for_chantier(self.id)

    def action_select_main_quote(self):
        """Action pour sélectionner le devis principal du chantier"""
        self.ensure_one()
        
        # Vérifier qu'on est au bon stage (stage 3 ou après)
        if not self.stage_id or self.stage_id.sequence < 3:
            raise ValidationError(_(
                "La sélection du devis principal n'est possible qu'à partir de l'étape 3 (Devis)."
            ))
        
        # Récupérer tous les devis du chantier
        quotes = self.env['sale.order'].search([
            ('chantier_id', '=', self.id),
            ('state', 'in', ['draft', 'sent', 'sale'])
        ])
        
        if not quotes:
            raise ValidationError(_(
                "Aucun devis trouvé pour ce chantier. Veuillez d'abord créer un devis."
            ))
        
        # Si un seul devis, le sélectionner automatiquement
        if len(quotes) == 1:
            self.main_quote_id = quotes[0]
            self._update_lots_prices_from_quote()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Devis principal sélectionné'),
                    'message': _('Le devis %s a été défini comme devis principal.') % quotes[0].name,
                    'type': 'success'
                }
            }
        
        # Sinon, ouvrir un wizard de sélection
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sélectionner le devis principal'),
            'res_model': 'construction.quote.selection.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_chantier_id': self.id,
                'default_quote_ids': [(6, 0, quotes.ids)],
            }
        }

    def action_open_select_lots_wizard(self):
        """Ouvre le wizard de sélection des lots à créer depuis les templates."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sélectionner les lots à créer'),
            'res_model': 'construction.lot.select.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_chantier_id': self.id,
            }
        }

    def _update_lots_prices_from_quote(self):
        """Met à jour les prix des lots depuis le devis principal et associe les lignes"""
        self.ensure_one()
        
        if not self.main_quote_id:
            return
        
        # D'abord, désassocier toutes les lignes existantes
        self.main_quote_id.order_line.write({'lot_id': False})
        
        # Associer les lignes aux lots en fonction du nom du produit/ligne
        for lot in self.lots_ids:
            # Rechercher les lignes qui correspondent à ce lot
            matching_lines = self.main_quote_id.order_line.filtered(
                lambda line: (
                    lot.name.lower() in line.name.lower() or 
                    lot.code.lower() in line.name.lower() or
                    (line.product_id and lot.name.lower() in line.product_id.name.lower()) or
                    (line.product_id and lot.code.lower() in line.product_id.name.lower())
                ) and not line.display_type
            )
            
            # Associer ces lignes au lot
            matching_lines.write({'lot_id': lot.id})
            
            # Forcer le recalcul du champ computed price_from_quote
            lot._compute_price_from_quote()
            # Mettre à jour le prix estimé avec le prix calculé si pas encore défini
            if lot.price == 0.0 and lot.price_from_quote > 0.0:
                lot.price = lot.price_from_quote
        
        # Associer les lignes non assignées au lot "Général" s'il existe
        unassigned_lines = self.main_quote_id.order_line.filtered(
            lambda line: not line.lot_id and not line.display_type
        )
        if unassigned_lines:
            general_lot = self.lots_ids.filtered(lambda l: l.code == 'GEN')
            if general_lot:
                unassigned_lines.write({'lot_id': general_lot[0].id})

    def get_quote_lines_by_lot(self):
        """Récupère les lignes du devis principal groupées par lot"""
        self.ensure_one()
        
        if not self.main_quote_id:
            return {}
            
        result = {}
        
        # Récupérer toutes les lignes du devis principal
        quote_lines = self.main_quote_id.order_line
        
        # Grouper par lot
        for lot in self.lots_ids:
            # Récupérer les lignes correspondant à ce lot
            lot_lines = quote_lines.filtered(lambda line: lot.name.lower() in line.name.lower() or 
                                           lot.code.lower() in line.name.lower())
            
            if lot_lines:
                result[lot] = lot_lines
        
        # Ajouter les lignes non associées à un lot spécifique
        unassigned_lines = quote_lines
        for lot, lines in result.items():
            unassigned_lines -= lines
            
        if unassigned_lines:
            # Créer un "lot" virtuel pour les articles non assignés
            general_lot = self.lots_ids.filtered(lambda l: l.code == 'GEN')
            if general_lot:
                if general_lot[0] in result:
                    result[general_lot[0]] |= unassigned_lines
                else:
                    result[general_lot[0]] = unassigned_lines
            else:
                result['Non assigné'] = unassigned_lines
                
        return result

    def action_view_invoice_schedule(self):
        """Voir le planning de facturation du chantier"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Planning de facturation - {self.name}',
            'res_model': 'construction.invoice.schedule',
            'view_mode': 'list,form',
            'domain': [('chantier_id', '=', self.id)],
            'context': {
                'default_chantier_id': self.id,
            },
            'target': 'current',
        }

    def _compute_lot_price_from_main_quote(self, lot):
        """
        Calcule le prix du lot à partir du devis principal (main_quote_id).
        Le prix du lot = somme des sous-totaux des lignes de produits associées à la section du lot.
        La correspondance se fait par le nom du lot et de la section (ligne display_type='line_section').
        """
        self.ensure_one()
        quote = self.main_quote_id
        if not quote:
            return 0.0
        order_lines = quote.order_line.sorted('sequence')
        lot_section_name = f"[{lot.name}]"  # Section name generated by _create_section_for_lot
        in_section = False
        total = 0.0
        for line in order_lines:
            if line.display_type == 'line_section':
                in_section = (line.name.strip() == lot_section_name.strip())
                continue
            if in_section and not line.display_type:
                total += line.price_subtotal
            elif in_section and line.display_type == 'line_section':
                break  # Nouvelle section, on arrête
        return total

    def action_setup_invoice_schedule(self):
        """Configurer le planning de facturation basé sur le cycle choisi et MAJ prix des lots depuis le devis principal."""
        self.ensure_one()

        if not self.invoice_type_id:
            raise ValidationError("Vous devez d'abord sélectionner un cycle de facturation.")

        if not self.main_quote_id:
            raise ValidationError("Vous devez sélectionner un devis principal servant de référence pour la facturation.")

        if not self.total_cost:
            raise ValidationError("Le coût total du chantier doit être défini pour configurer la facturation.")

        # --- NOUVEAU : Mettre à jour le prix des lots à partir du devis principal ---
        for lot in self.lots_ids:
            lot_price = self._compute_lot_price_from_main_quote(lot)
            lot.price = lot_price

        # Supprimer le planning existant si il y en a un
        self.invoice_schedule_ids.unlink()

        # Créer les lignes de planning basées sur le cycle choisi
        schedule_lines = []
        for line in self.invoice_type_id.line_ids:
            schedule_lines.append({
                'chantier_id': self.id,
                'invoice_type_line_id': line.id,
                'quote_id': self.main_quote_id.id,
                'margin_percentage': 0.0,
                'lot_ids': [(6, 0, self.lots_ids.ids)],
                'name': line.name,
                'sequence': line.sequence,
                'trigger_percentage': line.trigger_percentage,
                'amount_percentage': line.percentage,
                'is_advance_payment': line.is_advance_payment,
                'state': 'planned',
                'notes': line.notes or '',
            })

        if schedule_lines:
            self.env['construction.invoice.schedule'].create(schedule_lines)

            self.message_post(
                body=f"Planning de facturation configuré avec le cycle '{self.invoice_type_id.name}' "
                     f"({len(schedule_lines)} étapes créées)",
                message_type='notification'
            )

        return self.action_view_invoice_schedule()

    def action_create_new_invoice_cycle(self):
        """Ouvrir le formulaire de création de nouveau cycle de facturation"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Nouveau cycle de facturation',
            'res_model': 'construction.invoice_type',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_active': True}
        }

    def action_open_invoice_setup_wizard(self):
        """Ouvrir le wizard de configuration de la facturation"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Configuration de la facturation',
            'res_model': 'construction.invoice.setup.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_chantier_id': self.id,
            }
        }

    def action_trigger_advance_payment(self):
        """Déclencher manuellement l'acompte de signature"""
        self.ensure_one()

        # Utiliser le service pour déclencher l'acompte
        result = self.env['construction.invoice.service'].trigger_advance_payment(self.id)
        
        if result['success']:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Acompte déclenché',
                    'message': result['message'],
                    'type': 'success'
                }
            }
        else:
            raise ValidationError(result['message'])

    def action_check_invoice_triggers(self):
        """Vérifier manuellement tous les seuils de facturation"""
        self.ensure_one()

        if not self.invoice_schedule_ids:
            raise ValidationError(
                "Aucun planning de facturation configuré pour ce chantier."
            )

        # Utiliser le service pour vérifier les seuils
        result = self.env['construction.invoice.service'].check_and_trigger_invoices(self.id)
        
        if result['success']:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Vérification des seuils',
                    'message': f'{result["available_count"]} nouvelle(s) facture(s) disponible(s). Avancement: {result["progress"]}%',
                    'type': 'success' if result['available_count'] > 0 else 'info'
                }
            }
        else:
            raise ValidationError(result['message'])

    def action_create_available_invoices(self):
        """Créer manuellement toutes les factures disponibles"""
        self.ensure_one()

        if not self.invoice_schedule_ids:
            raise ValidationError(
                "Aucun planning de facturation configuré pour ce chantier."
            )

        # Récupérer toutes les factures prêtes à être créées
        ready_schedules = self.invoice_schedule_ids.filtered(lambda s: s.state == 'ready')
        
        if not ready_schedules:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Aucune facture disponible',
                    'message': 'Aucune facture n\'est prête à être créée. Vérifiez les seuils d\'avancement.',
                    'type': 'warning'
                }
            }

        # Créer toutes les factures disponibles
        created_count = 0
        errors = []
        
        for schedule in ready_schedules:
            try:
                result = self.env['construction.invoice.service'].create_and_send_invoice(schedule.id)
                if result['success']:
                    created_count += 1
                else:
                    errors.append(f"{schedule.name}: {result['message']}")
            except Exception as e:
                errors.append(f"{schedule.name}: {str(e)}")

        # Result message
        if created_count > 0:
            message = f"Success: {created_count} invoice(s) created and sent successfully."
            if errors:
                message += f"\nErrors: {len(errors)} invoice(s) not created."
            
            self.message_post(
                body=f"Manual invoice creation: {created_count} created, {len(errors)} error(s)",
                message_type='notification'
            )
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Création de factures',
                    'message': message,
                    'type': 'success' if not errors else 'warning'
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Erreur de création',
                    'message': f"Aucune facture n'a pu être créée:\n" + "\n".join(errors),
                    'type': 'danger'
                }
            }

    @api.onchange('invoice_type_id')
    def _onchange_invoice_type_id(self):
        """Proposer de reconfigurer le planning quand le cycle change"""
        if self.invoice_type_id:
            # Avertissement si un planning existe déjà
            if self.invoice_schedule_ids:
                return {
                    'warning': {
                        'title': 'Cycle de facturation modifié',
                        'message': 'Un planning de facturation existe déjà. '
                                  'Vous devez utiliser le bouton "Configurer facturation" '
                                  'pour mettre à jour le planning selon le nouveau cycle.'
                    }
                }
            # Rappel de sélectionner le devis principal si non défini
            elif not self.main_quote_id:
                return {
                    'warning': {
                        'title': 'Devis principal manquant',
                        'message': 'Veuillez sélectionner un devis principal dans la section '
                                  '"Cycle de facturation" pour pouvoir configurer le planning.'
                    }
                }

    def _check_invoice_triggers(self):
        """Vérifier automatiquement les seuils de facturation selon l'avancement"""
        self.ensure_one()
        if not self.invoice_schedule_ids:
            return

        # Utiliser le service pour vérifier et déclencher les factures
        result = self.env['construction.invoice.service'].check_and_trigger_invoices(self.id)
        
        if result['success'] and result['triggered_count'] > 0:
            # Le service a déjà posté le message de notification
            pass
        elif not result['success']:
            _logger.error(f"Erreur lors de la vérification des factures: {result['message']}")

    @api.model
    def _read_group_stage_id(self, stages, domain, order=None):
        """Retourne tous les stages pour le group_expand dans la vue kanban"""
        if not order:
            order = 'chapter_id, sequence'
        return self.env['construction.stage'].search([], order=order)

    # ================================================================
    #                   PURCHASE ORDER SPLITTING FUNCTIONALITY
    # ================================================================

    def can_split_quote_to_purchase(self):
        """Check if quote splitting to purchase orders is available for this chantier."""
        return self.env['purchase.split.service'].can_split_quote_to_purchase(self.id)

    def action_split_quote_to_purchase_orders(self):
        """Split the main quote into purchase orders by lots and assign to subcontractors."""
        self.ensure_one()

        # Utiliser le service de division pour créer des bons de commande
        result = self.env['purchase.split.service'].split_quote_to_purchase_by_lots(self.id)

        if result['success']:
            # Rafraîchir la vue pour montrer les nouveaux bons de commande
            self._compute_purchase_order_count()

            # Ouvrir une vue avec les bons de commande créés
            return self.action_view_purchase_orders(result['created_purchase_orders'])
        else:
            # Afficher l'erreur
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'danger',
                    'title': 'Erreur de division',
                    'message': result['message'],
                    'sticky': True,
                }
            }

    def action_split_quote_to_purchase_wizard(self):
        """Open the quote to purchase order splitting wizard for guided splitting."""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': _('Division de devis en bons de commande par lots'),
            'res_model': 'construction.purchase.split.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_chantier_id': self.id,
            }
        }

    def action_view_purchase_orders(self, purchase_order_ids=None):
        """View purchase orders created from this chantier's quote."""
        self.ensure_one()

        if purchase_order_ids:
            domain = [('id', 'in', purchase_order_ids)]
        else:
            purchase_orders = self.env['purchase.split.service'].get_purchase_orders_for_chantier(self.id)
            domain = [('id', 'in', purchase_orders.ids)]

        return {
            'type': 'ir.actions.act_window',
            'name': f'Bons de commande - {self.name}',
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': domain,
            'context': {
                'default_chantier_id': self.id,
                'search_default_group_by_partner': 1,
            },
            'target': 'current',
        }

    def action_quick_edit_purchase_order(self):
        """Quick access to edit purchase orders via popup."""
        self.ensure_one()

        purchase_orders = self.env['purchase.split.service'].get_purchase_orders_for_chantier(self.id)

        if not purchase_orders:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'warning',
                    'message': 'Aucun bon de commande trouvé. Divisez d\'abord le devis principal en bons de commande.',
                    'sticky': False,
                }
            }

        # Si un seul bon de commande, l'ouvrir directement
        if len(purchase_orders) == 1:
            return self.env['purchase.split.service'].quick_access_purchase_order(purchase_orders[0].id)

        # Sinon, afficher une liste pour sélection
        return {
            'type': 'ir.actions.act_window',
            'name': 'Sélectionner un bon de commande',
            'res_model': 'purchase.order',
            'view_mode': 'list',
            'domain': [('id', 'in', purchase_orders.ids)],
            'context': {
                'default_chantier_id': self.id,
                'create': False,
                'delete': False,
            },
            'target': 'new',
        }

    def get_main_quotation(self):
        """Get the main sale quotation for this chantier."""
        self.ensure_one()
        # Garder la logique du devis principal en sale.order
        main_quote = self.sale_order_ids.filtered(lambda so: so.is_main_quote and so.state in ['draft', 'sent'])
        return main_quote[0] if main_quote else False

    def _compute_purchase_order_count(self):
        """Compute the number of purchase orders created from this chantier's quote."""
        for record in self:
            purchase_orders = self.env['purchase.split.service'].get_purchase_orders_for_chantier(record.id)
            record.purchase_order_count = len(purchase_orders)

    def action_send_contract_to_subcontractor(self):
        """Envoie un email à chaque sous-traitant avec le lien de dépôt du contrat de sous-traitance."""
        self.ensure_one()

        try:
            template = self.env.ref('construction_base.email_template_subcontractor_contract_upload')
        except ValueError:
            raise ValidationError("Le template d'email est introuvable.")

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        if not base_url:
            raise ValidationError("L'URL de base du système n'est pas configurée.")

        sent_count = 0
        errors = []

        # Exclure les internes de l'envoi de lien de dépôt
        for partner in self.subcontractor_ids.filtered(lambda p: getattr(p, 'contact_type', False) != 'employee'):
            try:
                # Générer le token (cela invalidera automatiquement le cache du champ compute)
                token = partner._generate_upload_token()
                if not token:
                    errors.append(f"Impossible de générer un token pour {partner.name}.")
                    continue

                # Envoyer l'email (le champ compute sera automatiquement recalculé)
                template.with_context(
                    lang=partner.lang or 'fr_FR',
                    chantier_name=self.name
                ).send_mail(
                    partner.id,
                    force_send=True,
                    raise_exception=True
                )
                sent_count += 1

            except Exception as e:
                errors.append(f"Erreur pour {partner.name}: {str(e)}")

        # Messages de notification (reste identique)
        if errors:
            error_message = "\n".join(errors)
            self.message_post(
                body=f"Lien de dépôt envoyé à {sent_count} sous-traitant(s).\nErreurs:\n{error_message}",
                message_type='notification'
            )
        else:
            self.message_post(
                body=f"Lien de dépôt envoyé à {sent_count} sous-traitant(s).",
                message_type='notification'
            )

        notification_type = 'success' if sent_count > 0 else 'warning'
        message = f'{sent_count} email(s) envoyé(s) aux sous-traitants.'
        if errors:
            message += f' {len(errors)} erreur(s) détectée(s).'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Envoi des liens',
                'message': message,
                'type': notification_type,
            }
        }

    def action_view_planning(self):
        """Affiche le planning du chantier avec tous les lots initialisés."""
        self.ensure_one()

        # Vérifier si des tâches existent déjà pour ce chantier
        existing_tasks = self.env['construction.planning.task'].search([
            ('chantier_id', '=', self.id)
        ])

        # Si aucune tâche n'existe, initialiser une tâche vide pour chaque lot
        if not existing_tasks and self.lots_ids:
            for lot in self.lots_ids:
                # Vérifier si une tâche existe déjà pour ce lot
                lot_task = self.env['construction.planning.task'].search([
                    ('chantier_id', '=', self.id),
                    ('lot_id', '=', lot.id)
                ], limit=1)

                if not lot_task:
                    # Créer une tâche vide pour ce lot
                    self.env['construction.planning.task'].create({
                        'name': f'Tâche {lot.name}',
                        'chantier_id': self.id,
                        'lot_id': lot.id,
                        'date_start': self.date_start_contract or fields.Datetime.now(),
                        'date_stop': self.date_end_contract or fields.Datetime.now() + timedelta(days=30),
                        'state': 'draft'
                    })

        # Préparer les dates pour limiter l'affichage du Gantt
        initial_date = self.date_start_contract or fields.Date.today()
        final_date = self.date_end_contract or fields.Date.today() + timedelta(days=90)

        # Convertir en datetime pour le format attendu par la vue Gantt
        initial_datetime = fields.Datetime.to_datetime(initial_date)
        final_datetime = fields.Datetime.to_datetime(final_date) + timedelta(days=1) - timedelta(seconds=1)  # Fin de journée

        # Ouvrir la vue Gantt avec les tâches du chantier
        return {
            'type': 'ir.actions.act_window',
            'name': f'Planning - {self.name}',
            'res_model': 'construction.planning.task',
            'view_mode': 'gantt,list,form',
            'domain': [('chantier_id', '=', self.id)],
            'context': {
                'default_chantier_id': self.id,
                'group_by': ['lot_id'],
                'search_default_group_by_lot': 1,
                'lots_ids': self.lots_ids.ids,
                'initial_date': fields.Datetime.to_string(initial_datetime),
                'final_date': fields.Datetime.to_string(final_datetime),
                'view_id': False
            }
        }

    def action_create_planning_task(self):
        """Ouvre le wizard de création de tâche de planning."""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Créer une tâche de planning',
            'res_model': 'construction.planning.task.create',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_chantier_id': self.id,
                'available_lot_ids': self.lots_ids.ids
            }
        }

    def action_manage_order_lines(self):
        """Action pour gérer les commandes des articles du devis principal"""
        self.ensure_one()
        
        if not self.main_quote_id:
            raise ValidationError("Aucun devis principal sélectionné.")
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'Gestion des commandes - {self.name}',
            'res_model': 'sale.order.line',
            'view_mode': 'list,form',
            'domain': [('order_id', '=', self.main_quote_id.id)],
            'context': {
                'default_order_id': self.main_quote_id.id,
                'tree_view_ref': 'construction_base.view_sale_order_line_orders_tree',
                'search_default_group_by_lot': 1,
            },
            'target': 'current',
        }

    def action_generate_subcontractor_contracts(self):
        """Lance le wizard de génération de contrats de sous-traitance."""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Générer contrats de sous-traitance',
            'res_model': 'construction.contract.generation.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_chantier_id': self.id,
                'default_subcontractor_id': self.subcontractor_ids[0].id if self.subcontractor_ids else False,
                'default_lot_ids': [(6, 0, self.lots_ids.ids)]
            }
        }

    def action_generate_grouped_contracts(self):
        """Génère des contrats groupés pour les lots sélectionnés avec le même sous-traitant."""
        self.ensure_one()
        
        # Récupérer les lots sélectionnés
        selected_lots = self.lots_ids.filtered('selected_for_contract')
        
        if not selected_lots:
            raise ValidationError(_("Aucun lot sélectionné. Veuillez sélectionner au moins un lot."))
        
        # Grouper les lots par sous-traitant
        subcontractor_groups = {}
        for lot in selected_lots:
            if not lot.subcontractor_ids:
                raise ValidationError(_("Le lot '%s' n'a pas de sous-traitant assigné.") % lot.name)
            
            # Pour chaque lot, vérifier qu'il n'a qu'un seul sous-traitant
            if len(lot.subcontractor_ids) > 1:
                raise ValidationError(_("Le lot '%s' a plusieurs sous-traitants. Un contrat groupé ne peut être généré que pour un seul sous-traitant par lot.") % lot.name)
            
            subcontractor = lot.subcontractor_ids[0]
            if subcontractor.id not in subcontractor_groups:
                subcontractor_groups[subcontractor.id] = {
                    'subcontractor': subcontractor,
                    'lots': []
                }
            subcontractor_groups[subcontractor.id]['lots'].append(lot)
        
        # Créer un wizard pour chaque groupe de sous-traitant
        wizards = []
        for subcontractor_id, group_data in subcontractor_groups.items():
            wizard = self.env['construction.contract.generation.wizard'].create({
                'chantier_id': self.id,
                'subcontractor_id': subcontractor_id,
                'lot_ids': [(6, 0, [lot.id for lot in group_data['lots']])],
                'start_date': fields.Date.today(),
                'total_amount': sum(lot.price for lot in group_data['lots']),
            })
            wizards.append(wizard)
        
        # Retourner l'action pour ouvrir le premier wizard
        if wizards:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Génération de contrat groupé'),
                'res_model': 'construction.contract.generation.wizard',
                'res_id': wizards[0].id,
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_chantier_id': self.id,
                    'grouped_contract_mode': True,
                    'wizard_ids': [w.id for w in wizards],
                }
            }
        
        return {'type': 'ir.actions.act_window_close'}

    def action_clear_lot_selection(self):
        """Désélectionne tous les lots."""
        self.ensure_one()
        self.lots_ids.write({'selected_for_contract': False})
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
