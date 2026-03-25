# -*- coding: utf-8 -*-
"""
Construction Site (Chantier) Model - Core
Enterprise-grade refactoring: Robust, modular, scalable.
Includes State Machine pattern for stage transitions (SAP/Odoo philosophy).
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import timedelta
import logging

from odoo.addons.construction_core.utils.logger import get_logger

_logger = get_logger(__name__)


# ============= STATE MACHINE CONFIGURATION ============= #
STAGE_TRANSITIONS = {
    'REC': {'next': 'VT', 'validator': 'check_reception_stage'},
    'VT': {'next': 'DE', 'validator': 'check_visit_stage'},
    'DE': {'next': 'DA', 'validator': 'check_quotation_sent_stage'},
    'DA': {'next': 'FD', 'validator': 'check_quotation_accepted_stage'},
    'FD': {'next': 'T25', 'validator': 'check_dossier_finalization_stage'},
    'T25': {'next': 'T50', 'validator': 'check_construction_percentage_stage'},
    'T50': {'next': 'T75', 'validator': 'check_construction_percentage_stage'},
    'T75': {'next': 'T100', 'validator': 'check_construction_percentage_stage'},
    'T100': {'next': 'LR', 'validator': 'check_construction_percentage_stage'},
    'LR': {'next': 'AP', 'validator': 'check_warranty_stage'},
    'AP': {'next': 'RET', 'validator': None},
    'RET': {'next': 'DC', 'validator': 'check_warranty_retention_stage'},
    'DC': {'next': None, 'validator': None},
    'SS': {'next': None, 'validator': None},
}

# Progress thresholds for TRAV chapter
PROGRESS_THRESHOLDS = {
    'T25': 25,
    'T50': 50,
    'T75': 75,
    'T100': 100,
}

# Blocking rules for backward transitions
BACKWARD_BLOCKED_CHAPTERS = ['ARCH', 'RET']


class Chantier(models.Model):
    """
    Construction Site Model (Core).
    
    Represents a construction project with workflow stages, budget tracking,
    and subcontractor management. Refactored for SOLID principles.
    
    State Machine Pattern implemented for strict stage transitions.
    
    Mail Integration:
    - Supports chantier creation via email (catchall_domain)
    - Email subject becomes chantier name
    - Email body becomes description
    """
    _name = 'construction.chantier'
    _description = 'Gestion de Chantier'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'
    
    # ============= Mail Alias Configuration ============= #
    _mail_post_access = 'read'

    # ============= Archive / Active ============= #
    active = fields.Boolean(string='Actif', default=True,
                            help="Décocher pour archiver le chantier (Sans Suite, Abandonné)")

    # ============= Identification ============= #
    name = fields.Char(string='Nom du Chantier', required=True, tracking=True)
    reference = fields.Char(string='Référence', copy=False, readonly=True, default='/')
    client = fields.Many2one('res.partner', string='Client', required=True, tracking=True)
    description = fields.Text(string='Description des Travaux')
    notes = fields.Text(string='Notes')
    
    # ============= Location ============= #
    address = fields.Text(string='Adresse')
    city = fields.Char(string='Ville')
    zip_code = fields.Char(string='Code Postal')
    country_id = fields.Many2one('res.country', string='Pays')
    phone = fields.Char(string='Téléphone du chantier')
    
    # ============= Technical Specs ============= #
    surface_m2 = fields.Float(string='Surface (m²)')
    nb_levels = fields.Integer(string='Nombre d\'étages')
    permit_number = fields.Char(string='Numéro de Permis')
    permit_date = fields.Date(string='Date du Permis')
    
    # ============= Workflow & Status ============= #
    state = fields.Selection([
        ('active', 'Actif'),
        ('suspended', 'Suspendu'),
        ('completed', 'Terminé'),
        ('abandoned', 'Abandonné')
    ], string='État', default='active', tracking=True)
    
    color = fields.Integer(string='Couleur', default=0)
    tag_ids = fields.Many2many('construction.tag', string='Étiquettes')
    
    stage_id = fields.Many2one(
        'construction.stage',
        string='Étape',
        group_expand='_read_group_stage_id',
        tracking=True
    )
    
    chapter_name = fields.Char(
        string='Chapitre',
        compute='_compute_chapter_name',
        store=True
    )
    
    stage_validation_info = fields.Text(
        string='Info Validation',
        compute='_compute_stage_validation_info',
        help="Conditions pour passer à l'étape suivante"
    )
    
    # ============= Dates ============= #
    date_start_contract = fields.Date(string='Date début contrat', tracking=True)
    date_end_contract = fields.Date(string='Date fin contrat', tracking=True)
    date_start_internal = fields.Date(string='Début Interne', tracking=True)
    date_end_internal = fields.Date(string='Fin Interne', tracking=True)
    date_start_estimated = fields.Date(string='Début Estimé', tracking=True)
    date_end_estimated = fields.Date(string='Fin Estimée', tracking=True)
    
    duration_planned = fields.Integer(
        string='Durée Prévue (jours)',
        compute='_compute_duration_planned',
        store=True
    )
    duration_actual = fields.Integer(
        string='Durée Réelle (jours)',
        compute='_compute_duration_actual',
        store=True
    )
    
    # ============= Progress ============= #
    progress = fields.Float(
        string='Progression (%)',
        compute='_compute_progress',
        store=True,
        default=0.0
    )

    progress_display = fields.Char(
        string='Avancement',
        compute='_compute_progress_display',
        store=False,
    )

    is_ready_for_next_stage = fields.Boolean(
        string='Prêt pour l\'étape suivante',
        compute='_compute_is_ready_for_next_stage',
        store=False,
    )
    
    # ============= Budget ============= #
    budget_previsionnel = fields.Monetary(
        string='Budget Prévisionnel',
        currency_field='currency_id',
        tracking=True,
        help="Budget prévisionnel du chantier (utilisé pour la validation hiérarchique Sans Suite)"
    )

    # ============= Financial ============= #
    company_id = fields.Many2one(
        'res.company', 'Company', required=True,
        index=True, default=lambda self: self.env.company
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Devise',
        default=lambda self: self.env.company.currency_id
    )
    total_cost = fields.Monetary(
        string='Coût Total',
        compute='_compute_total_cost',
        store=True,
        currency_field='currency_id',
        groups='construction_core.group_construction_admin,construction_core.group_construction_accountant'
    )
    
    # ============= Guarantee Retention (US-COR-006) ============= #
    guarantee_retention_rate = fields.Float(
        string='Taux Rétention Garantie (%)',
        default=5.0,
        help="Pourcentage de retenue de garantie (standard: 5%)"
    )
    guarantee_retention_amount = fields.Monetary(
        string='Montant Rétention',
        compute='_compute_guarantee_amounts',
        store=True,
        currency_field='currency_id',
        groups='construction_core.group_construction_admin,construction_core.group_construction_accountant',
        help="Calculé depuis le total des lots × taux de rétention"
    )
    guarantee_release_date = fields.Date(
        string='Date Libération Garantie',
        tracking=True,
        help="Date prévue de libération de la retenue de garantie"
    )
    guarantee_reminder_sent_j7 = fields.Boolean(
        string='Rappel J-7 Envoyé',
        default=False,
        help="Rappel envoyé 7 jours avant la date de libération"
    )
    guarantee_reminder_sent_j0 = fields.Boolean(
        string='Rappel J-0 Envoyé',
        default=False,
        help="Rappel envoyé le jour de la libération"
    )
    guarantee_status = fields.Selection([
        ('pending', 'En cours'),
        ('released', 'Libérée'),
        ('expired', 'Expirée')
    ], string='Statut Garantie', default='pending', tracking=True)
    
    # ============= Relations ============= #
    user_ids = fields.Many2many('res.users', string='Responsables')
    
    # NOTE: quotation_ids is added by construction_sale module via _inherit
    # Defining One2many here causes KeyError because sale_order.py loads after chantier.py
    quotation_count = fields.Integer(compute='_compute_quotation_count')

    # Explicit selection of validated quotes for PO generation
    devis_ids = fields.Many2many(
        'sale.order',
        string='Devis Validés',
        domain="[('state', '=', 'sale')]",
        help="Sélectionner les devis validés pour la génération des commandes"
    )
    
    subcontractor_ids = fields.Many2many(
        'res.partner',
        'construction_core_chantier_subcontractor_rel',
        'chantier_id',
        'partner_id',
        string='Sous-traitants',
        domain="[('supplier_rank', '>', 0)]"
    )
    subcontractor_count = fields.Integer(compute='_compute_subcontractor_count')
    
    lots_ids = fields.One2many('construction.lot', 'chantier_id', string='Lots')
    lots_count = fields.Integer(compute='_compute_lots_count')
    
    # ============= Project Team (Computed from Lots) ============= #
    project_subcontractor_ids = fields.Many2many(
        'res.partner',
        compute='_compute_project_subcontractors',
        string='Sous-traitants du Projet',
        help="Sous-traitants assignés aux lots de ce chantier"
    )
    
    # ============= Sans Suite Tracking (US-COR-008) ============= #
    sans_suite_reason = fields.Selection([
        ('client_cancelled', 'Client a renoncé'),
        ('budget_insufficient', 'Budget insuffisant'),
        ('delays_incompatible', 'Délais incompatibles'),
        ('technical_impossible', 'Impossibilité technique'),
        ('competition', 'Concurrence'),
        ('other', 'Autre raison')
    ], string='Raison Sans Suite', tracking=True)
    
    sans_suite_details = fields.Text(
        string='Détails Sans Suite',
        help="Précisions sur la raison de l'abandon"
    )
    
    sans_suite_date = fields.Date(
        string='Date Sans Suite',
        tracking=True
    )
    
    # ============= Contract Generation Visibility ============= #
    show_contract_generation = fields.Boolean(
        compute='_compute_show_contract_generation',
        string='Afficher Génération Contrat',
        help="Visible à partir de finalisation dossier"
    )
    
    # ============= Stage-Based Visibility (SAP/Salesforce UX) ============= #
    show_visits = fields.Boolean(
        compute='_compute_stage_visibility',
        string='Afficher Visites',
        help="Visible uniquement à partir de la visite technique"
    )
    show_quotes = fields.Boolean(
        compute='_compute_stage_visibility',
        string='Afficher Devis',
        help="Visible à partir de devis envoyé"
    )
    show_lots_selection = fields.Boolean(
        compute='_compute_stage_visibility',
        string='Afficher Sélection Lots',
        help="Visible à partir de devis envoyé"
    )
    show_invoicing = fields.Boolean(
        compute='_compute_stage_visibility',
        string='Afficher Facturation',
        help="Visible à partir de finalisation dossier"
    )
    show_subcontractors = fields.Boolean(
        compute='_compute_stage_visibility',
        string='Afficher Sous-traitants',
        help="Visible à partir de devis accepté"
    )
    
    # ============= Validation Conditions Display ============= #
    validation_conditions_html = fields.Html(
        compute='_compute_validation_conditions_html',
        string='Conditions de Validation'
    )
    next_stage_name = fields.Char(
        string='Prochaine Étape',
        compute='_compute_next_stage_name',
        store=False,
    )
    next_stage_requirements = fields.Html(
        string='Conditions manquantes',
        compute='_compute_next_stage_requirements',
        store=False,
        sanitize=False,
    )

    # ============= Team Resources Display (US-COR-010) ============= #
    team_resources_html = fields.Html(
        compute='_compute_team_resources_html',
        string='Ressources du Chantier'
    )

    # ============= Documents Centralization (GED) ============= #
    documents_summary_html = fields.Html(
        compute='_compute_documents_summary_html',
        string='Documents du Chantier',
    )
    document_ids = fields.One2many(
        'construction.document',
        'chantier_id',
        string='Documents GED',
    )
    document_count = fields.Integer(
        string='Documents',
        compute='_compute_document_count',
    )

    # NOTE: visit_ids is added by construction_visit via _inherit

    
    # ============= Constraints ============= #
    _sql_constraints = [
        ('positive_surface', 'CHECK(surface_m2 >= 0)', 'La surface doit être positive.'),
        ('progress_range', 'CHECK(progress >= 0 AND progress <= 100)', 'La progression doit être entre 0 et 100%.'),
    ]

    # ============= Computed Fields ============= #
    @api.depends('stage_id', 'stage_id.chapter_id')
    def _compute_chapter_name(self):
        """Compute the name of the chapter associated with the current stage."""
        for record in self:
            record.chapter_name = record.stage_id.chapter_id.name if record.stage_id and record.stage_id.chapter_id else False

    @api.depends('date_start_contract', 'date_end_contract')
    def _compute_duration_planned(self):
        """Compute the planned duration in days based on contract dates."""
        for record in self:
            if record.date_start_contract and record.date_end_contract:
                delta = record.date_end_contract - record.date_start_contract
                record.duration_planned = delta.days + 1
            else:
                record.duration_planned = 0

    @api.depends('date_start_internal', 'date_end_internal', 'state')
    def _compute_duration_actual(self):
        """Compute the actual duration in days. Uses state to determine if ongoing."""
        today = fields.Date.today()
        for record in self:
            if record.date_start_internal and record.date_end_internal:
                delta = record.date_end_internal - record.date_start_internal
                record.duration_actual = delta.days + 1
            elif record.date_start_internal and record.state == 'active':
                delta = today - record.date_start_internal
                record.duration_actual = delta.days + 1
            else:
                record.duration_actual = 0

    @api.depends('lots_ids.completion_percentage', 'lots_ids.price', 'lots_ids.weighted_value')
    def _compute_progress(self):
        """Calculate progress based on weighted lot completion.
        
        Progress = (Sum of weighted_values) / (Total price) × 100
        where weighted_value = lot_price × (completion_percentage / 100)
        
        Example:
        - Lot A: 100€ at 100% = 100€ weighted
        - Lot B: 100€ at 50% = 50€ weighted
        - Total: 200€
        - Progress = (100 + 50) / 200 × 100 = 75%
        
        TASK-013: Also triggers auto-LR transition when >= 95%.
        """
        for record in self:
            total_price = sum(record.lots_ids.mapped('price'))
            weighted_sum = sum(record.lots_ids.mapped('weighted_value'))
            new_progress = (weighted_sum / total_price * 100) if total_price > 0 else 0.0
            old_progress = record.progress
            record.progress = new_progress
            
            # TASK-013: Auto-trigger LR stage at 95%
            if old_progress < 95.0 and new_progress >= 95.0:
                record._check_progress_95_trigger()

    @api.depends('progress')
    def _compute_progress_display(self):
        for record in self:
            record.progress_display = f"{record.progress:.0f}%"

    @api.depends(
        'stage_id',
        'client', 'address', 'description', 'phone',
        'lots_ids', 'quotation_ids.state',
        'subcontractor_ids', 'date_start_contract', 'date_end_contract',
        'date_start_internal', 'date_end_internal',
        'date_start_estimated', 'date_end_estimated',
        'progress',
    )
    def _compute_is_ready_for_next_stage(self):
        for record in self:
            try:
                with record.env.cr.savepoint():
                    can_proceed, _msg = record._can_move_to_next_stage()
                record.is_ready_for_next_stage = can_proceed
            except Exception:
                record.is_ready_for_next_stage = False

    @api.depends('lots_ids.price', 'quotation_ids.state', 'quotation_ids.amount_total')
    def _compute_total_cost(self):
        """
        Compute total chantier value from validated sale orders (devis).
        Falls back to lot prices if no validated quotes exist.
        """
        for record in self:
            # Priority: Use validated sale orders
            validated_quotes = record.quotation_ids.filtered(lambda q: q.state == 'sale')
            if validated_quotes:
                record.total_cost = sum(validated_quotes.mapped('amount_total'))
            else:
                # Fallback: Sum lot prices
                record.total_cost = sum(record.lots_ids.mapped('price'))

    def _compute_quotation_count(self):
        """Compute the number of associated quotations."""
        for record in self:
            record.quotation_count = len(record.quotation_ids)

    @api.depends('document_ids')
    def _compute_document_count(self):
        """Compute the number of GED documents attached to this chantier."""
        for record in self:
            record.document_count = len(record.document_ids)

    @api.depends('lots_ids.subcontractor_id', 'lots_ids.execution_type')
    def _compute_subcontractor_count(self):
        """Count unique subcontractors assigned to lots (not the direct M2M field)."""
        for record in self:
            # Count subcontractors from lots, not the direct M2M field
            external_lots = record.lots_ids.filtered(
                lambda l: l.execution_type == 'external' and l.subcontractor_id
            )
            record.subcontractor_count = len(external_lots.mapped('subcontractor_id'))
    def _compute_lots_count(self):
        """Compute the number of associated lots."""
        for record in self:
            record.lots_count = len(record.lots_ids)

    @api.depends('lots_ids.price', 'guarantee_retention_rate')
    def _compute_guarantee_amounts(self):
        """US-COR-006: Compute 5% retention amount from total lot prices."""
        for record in self:
            total_lots_price = sum(record.lots_ids.mapped('price'))
            rate = record.guarantee_retention_rate or 5.0
            record.guarantee_retention_amount = total_lots_price * (rate / 100.0)

    @api.model
    def _cron_send_guarantee_reminders(self):
        """
        US-COR-006: Cron job to send guarantee reminders.
        Runs daily, checks for chantiers with release dates J-7 or J-0.
        """
        from datetime import timedelta
        today = fields.Date.today()
        j7_date = today + timedelta(days=7)
        
        _logger.info('[CORE][CRON] Starting guarantee reminder check for %s', today)
        
        # Find chantiers with J-7 reminder needed
        chantiers_j7 = self.search([
            ('guarantee_release_date', '=', j7_date),
            ('guarantee_reminder_sent_j7', '=', False),
            ('guarantee_status', '=', 'pending'),
        ])
        
        for chantier in chantiers_j7:
            _logger.info('[CORE][GUARANTEE] J-7 reminder sent for chantier %s', chantier.reference)
            self._send_guarantee_reminder(chantier, 'j7')
            chantier.guarantee_reminder_sent_j7 = True
        
        # Find chantiers with J-0 reminder needed
        chantiers_j0 = self.search([
            ('guarantee_release_date', '=', today),
            ('guarantee_reminder_sent_j0', '=', False),
            ('guarantee_status', '=', 'pending'),
        ])
        
        for chantier in chantiers_j0:
            _logger.info('[CORE][GUARANTEE] J-0 reminder sent for chantier %s', chantier.reference)
            self._send_guarantee_reminder(chantier, 'j0')
            chantier.guarantee_reminder_sent_j0 = True
            chantier.guarantee_status = 'expired'
        
        _logger.info('[CORE][CRON] Guarantee check complete. J-7: %d, J-0: %d', 
                    len(chantiers_j7), len(chantiers_j0))
        return True

    def _send_guarantee_reminder(self, chantier, reminder_type):
        """Send guarantee reminder email using template."""
        template_ref = f'construction_core.email_template_guarantee_{reminder_type}'
        template = self.env.ref(template_ref, raise_if_not_found=False)
        
        if template:
            template.send_mail(chantier.id, force_send=True)
            chantier.message_post(
                body=_(f"📧 Rappel garantie {reminder_type.upper()} envoyé automatiquement."),
                message_type='notification'
            )
        else:
            _logger.warning('[CORE][TEMPLATE] Template %s not found, using fallback', template_ref)
            # Fallback: post to chatter
            chantier.message_post(
                body=_(
                    f"⏰ Rappel garantie ({reminder_type.upper()}): "
                    f"La retenue de garantie de {chantier.guarantee_retention_amount:,.2f} € "
                    f"arrive à échéance le {chantier.guarantee_release_date}."
                ),
                message_type='notification'
            )

    def action_release_guarantee(self):
        """Manually release the guarantee retention."""
        self.ensure_one()
        _logger.info('[CORE][GUARANTEE] Manual release for chantier %s by user %s', 
                    self.reference, self.env.user.name)
        self.guarantee_status = 'released'
        self.message_post(
            body=_("✅ Retenue de garantie libérée manuellement par %s.") % self.env.user.name,
            message_type='notification'
        )
        return True

    # ============= TASK-013: Auto-LR at 95% ============= #
    def _check_progress_95_trigger(self):
        """
        TASK-013: Automatically transitions the chantier to the LR (Levée de Réserve) stage
        when progress reaches or exceeds 95%.
        
        When triggered:
        1. Sets the stage to LR.
        2. Calculates the guarantee release date as exactly 1 year from today.
        3. Posts an informative message to the chatter.
        4. The existing cron job `_cron_send_guarantee_reminders` handles subsequent reminders.
        """
        self.ensure_one()
        
        if not self.stage_id:
            return
        
        stage_code = self.stage_id.code
        
        # Only trigger from TRAV chapter stages (T25, T50, T75, T100)
        trav_stages = ['T25', 'T50', 'T75', 'T100']
        if stage_code not in trav_stages:
            return
        
        # Find the LR stage
        lr_stage = self.env['construction.stage'].search([('code', '=', 'LR')], limit=1)
        if not lr_stage:
            _logger.warning('[CORE][TASK-013] LR stage not found in database')
            return
        
        # Calculate guarantee release date: 1 year from now
        today = fields.Date.today()
        release_date = today + timedelta(days=365)
        
        # Transition to LR stage
        old_stage_name = self.stage_id.name
        self.with_context(bypass_stage_validation=True).write({
            'stage_id': lr_stage.id,
            'guarantee_release_date': release_date,
            'guarantee_status': 'pending',
        })
        
        _logger.info(
            '[CORE][TASK-013] Chantier %s auto-transitioned to LR (progress: %.1f%%). '
            'Guarantee release date: %s',
            self.reference, self.progress, release_date
        )
        
        # Post rich notification to chatter
        self.message_post(
            body=_(
                "🔔 <b>Levée de réserve automatique</b><br/>"
                "La progression du chantier a atteint <b>%.1f%%</b> (≥ 95%%).<br/>"
                "<ul>"
                "<li>Étape précédente : %s</li>"
                "<li>Nouvelle étape : <b>%s</b></li>"
                "<li>Retenue de garantie : <b>%.2f €</b> (%.0f%%)</li>"
                "<li>Date de libération prévue : <b>%s</b></li>"
                "</ul>"
                "Les rappels automatiques seront envoyés à J-7 et J-0."
            ) % (
                self.progress,
                old_stage_name,
                lr_stage.name,
                self.guarantee_retention_amount,
                self.guarantee_retention_rate,
                release_date.strftime('%d/%m/%Y'),
            ),
            message_type='notification',
            subtype_xmlid='mail.mt_note',
        )
        
        return True

    @api.depends('lots_ids.subcontractor_id', 'lots_ids.execution_type')
    def _compute_project_subcontractors(self):
        """Compute all subcontractors from external lots in this project."""
        for record in self:
            external_lots = record.lots_ids.filtered(
                lambda l: l.execution_type == 'external' and l.subcontractor_id
            )
            record.project_subcontractor_ids = external_lots.mapped('subcontractor_id')

    @api.depends('lots_ids', 'lots_ids.subcontractor_id', 'lots_ids.execution_type',
                 'lots_ids.purchase_order_id', 'user_ids')
    def _compute_team_resources_html(self):
        """
        US-COR-010: Generate structured HTML table for Team tab.
        Shows both internal team and subcontractors with conformity status.
        """
        for record in self:
            # Internal Team Section
            internal_rows = ""
            for user in record.user_ids:
                internal_rows += f"""
                    <tr>
                        <td><span class="badge bg-primary">Interne</span></td>
                        <td><strong>{user.name}</strong></td>
                        <td>{user.email or '-'}</td>
                        <td>-</td>
                        <td><span class="badge bg-success">Équipe BLG</span></td>
                    </tr>
                """
            
            # Subcontractors Section
            st_rows = ""
            external_lots = record.lots_ids.filtered(
                lambda l: l.execution_type == 'external' and l.subcontractor_id
            )
            
            # Group lots by subcontractor
            st_lots_map = {}
            for lot in external_lots:
                st_id = lot.subcontractor_id.id
                if st_id not in st_lots_map:
                    st_lots_map[st_id] = {
                        'partner': lot.subcontractor_id,
                        'lots': [],
                        'has_po': False,
                        'has_contract': False,
                    }
                st_lots_map[st_id]['lots'].append(lot)
                if lot.purchase_order_id:
                    st_lots_map[st_id]['has_po'] = True
                if hasattr(lot, 'contract_id') and lot.contract_id:
                    st_lots_map[st_id]['has_contract'] = True
            
            for st_id, data in st_lots_map.items():
                partner = data['partner']
                lots_names = ', '.join([l.code for l in data['lots']])
                
                # Check document conformity from partner if available
                # Fields from blg_contacts_extension: doc_kbis_status, doc_urssaf_status, etc.
                # COMPLIANT statuses: 'valid' or 'expiring' (expiring is still usable)
                conformity_ok = True
                conformity_badge = '<span class="badge bg-secondary">Non vérifié</span>'
                
                compliant_statuses = {'valid', 'expiring'}
                
                if hasattr(partner, 'doc_kbis_status'):
                    kbis_ok = getattr(partner, 'doc_kbis_status', 'missing') in compliant_statuses
                    urssaf_ok = getattr(partner, 'doc_urssaf_status', 'missing') in compliant_statuses
                    insurance_ok = getattr(partner, 'doc_insurance_dec_status', 'missing') in compliant_statuses
                    cni_ok = getattr(partner, 'doc_cni_status', 'missing') in compliant_statuses
                    rib_ok = getattr(partner, 'doc_rib_status', 'missing') in compliant_statuses
                    
                    if kbis_ok and urssaf_ok and insurance_ok and cni_ok and rib_ok:
                        conformity_badge = '<span class="badge bg-success">✅ Conforme</span>'
                    else:
                        missing = []
                        if not kbis_ok: missing.append('KBIS')
                        if not urssaf_ok: missing.append('URSSAF')
                        if not insurance_ok: missing.append('Assurance')
                        if not cni_ok: missing.append('CNI')
                        if not rib_ok: missing.append('RIB')
                        conformity_badge = f'<span class="badge bg-warning text-dark">⚠️ Manque: {", ".join(missing)}</span>'
                
                # Status badges
                status_badges = ""
                if data['has_po']:
                    status_badges += '<span class="badge bg-info me-1">BC ✓</span>'
                else:
                    status_badges += '<span class="badge bg-light text-dark me-1">BC ✗</span>'
                if data['has_contract']:
                    status_badges += '<span class="badge bg-success">Contrat ✓</span>'
                else:
                    status_badges += '<span class="badge bg-light text-dark">Contrat ✗</span>'
                
                st_rows += f"""
                    <tr>
                        <td><span class="badge bg-warning text-dark">Sous-traitant</span></td>
                        <td><strong>{partner.name}</strong></td>
                        <td>{lots_names}</td>
                        <td>{status_badges}</td>
                        <td>{conformity_badge}</td>
                    </tr>
                """
            
            if not internal_rows and not st_rows:
                record.team_resources_html = """
                    <div class="alert alert-info text-center">
                        <i class="fa fa-users fa-2x mb-2"></i>
                        <p class="mb-0">Aucune ressource assignée</p>
                    </div>
                """
                continue
            
            record.team_resources_html = f"""
                <div class="table-responsive">
                    <table class="table table-hover table-sm">
                        <thead class="table-light">
                            <tr>
                                <th style="width: 120px;">Type</th>
                                <th>Nom</th>
                                <th>Lots / Contact</th>
                                <th>BC / Contrat</th>
                                <th>Conformité</th>
                            </tr>
                        </thead>
                        <tbody>
                            {internal_rows}
                            {st_rows}
                        </tbody>
                    </table>
                </div>
            """

    @api.depends(
        'lots_ids.document_cctp', 'lots_ids.document_planning_chantier',
        'lots_ids.document_planning_sous_traitant', 'lots_ids.name',
    )
    def _compute_documents_summary_html(self):
        """Aggregate all lot-level documents into a centralized summary."""
        for record in self:
            rows = ""
            doc_count = 0
            for lot in record.lots_ids:
                docs = []
                if lot.document_cctp:
                    docs.append(('CCTP', getattr(lot, 'document_cctp_filename', None) or 'CCTP'))
                if lot.document_planning_chantier:
                    docs.append(('Planning Chantier', getattr(lot, 'document_planning_chantier_filename', None) or 'Planning'))
                if lot.document_planning_sous_traitant:
                    docs.append(('Planning ST', getattr(lot, 'document_planning_sous_traitant_filename', None) or 'Planning ST'))

                if not docs:
                    rows += (
                        f'<tr class="text-muted">'
                        f'<td>{lot.code or ""}</td>'
                        f'<td>{lot.name}</td>'
                        f'<td><span class="badge bg-light text-dark">Aucun document</span></td>'
                        f'<td>-</td>'
                        f'</tr>'
                    )
                    continue

                first = True
                for doc_type, doc_name in docs:
                    doc_count += 1
                    if first:
                        rows += (
                            f'<tr>'
                            f'<td rowspan="{len(docs)}">{lot.code or ""}</td>'
                            f'<td rowspan="{len(docs)}">{lot.name}</td>'
                            f'<td><span class="badge bg-success me-1">✓</span> {doc_type}</td>'
                            f'<td class="text-muted small">{doc_name}</td>'
                            f'</tr>'
                        )
                        first = False
                    else:
                        rows += (
                            f'<tr>'
                            f'<td><span class="badge bg-success me-1">✓</span> {doc_type}</td>'
                            f'<td class="text-muted small">{doc_name}</td>'
                            f'</tr>'
                        )

            # Attachments on chantier (manual uploads, emails, generated reports)
            attachments = self.env['ir.attachment'].search([
                ('res_model', '=', 'construction.chantier'),
                ('res_id', '=', record.id),
            ])
            # Attachments linked to chatter messages (emails received/sent)
            msg_att_ids = set(self.env['mail.message'].search([
                ('model', '=', 'construction.chantier'),
                ('res_id', '=', record.id),
                ('attachment_ids', '!=', False),
            ]).mapped('attachment_ids').ids)

            for att in attachments:
                doc_count += 1
                # Determine origin
                if att.id in msg_att_ids:
                    source_badge = '<span class="badge bg-secondary me-1">Email</span>'
                elif 'Visite_' in (att.name or '') or att.mimetype == 'application/pdf':
                    source_badge = '<span class="badge bg-warning text-dark me-1">Généré</span>'
                else:
                    source_badge = '<span class="badge bg-info me-1">Manuel</span>'
                download_url = f'/web/content/{att.id}?download=true'
                rows += (
                    f'<tr>'
                    f'<td>—</td>'
                    f'<td>Chantier</td>'
                    f'<td>{source_badge} {att.mimetype or "Fichier"}</td>'
                    f'<td class="text-muted small">'
                    f'{att.name}'
                    f'&nbsp;<a href="{download_url}" target="_blank" title="Télécharger">'
                    f'<i class="fa fa-download text-primary"/></a>'
                    f'</td>'
                    f'</tr>'
                )

            # Visit reports linked to this chantier
            if 'construction.visit' in self.env:
                visits = self.env['construction.visit'].search([
                    ('chantier_id', '=', record.id),
                    ('report_generated', '=', True),
                ])
                for visit in visits:
                    visit_atts = self.env['ir.attachment'].search([
                        ('res_model', '=', 'construction.visit'),
                        ('res_id', '=', visit.id),
                        ('mimetype', '=', 'application/pdf'),
                    ], limit=1)
                    if visit_atts:
                        att = visit_atts[0]
                        doc_count += 1
                        download_url = f'/web/content/{att.id}?download=true'
                        rows += (
                            f'<tr>'
                            f'<td>—</td>'
                            f'<td>Visite — {visit.date.strftime("%d/%m/%Y") if visit.date else ""}</td>'
                            f'<td><span class="badge bg-success me-1">CR Visite</span></td>'
                            f'<td class="text-muted small">'
                            f'{att.name}'
                            f'&nbsp;<a href="{download_url}" target="_blank" title="Télécharger">'
                            f'<i class="fa fa-download text-primary"/></a>'
                            f'</td>'
                            f'</tr>'
                        )

            if not rows:
                record.documents_summary_html = (
                    '<div class="alert alert-secondary text-center">'
                    '<i class="fa fa-folder-open fa-2x mb-2"></i>'
                    '<p class="mb-0">Aucun document sur ce chantier</p>'
                    '</div>'
                )
                continue

            record.documents_summary_html = f"""
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <span class="badge bg-primary">{doc_count} document(s)</span>
                </div>
                <div class="table-responsive">
                    <table class="table table-hover table-sm">
                        <thead class="table-light">
                            <tr>
                                <th style="width:80px">Code</th>
                                <th>Source</th>
                                <th>Type</th>
                                <th>Fichier</th>
                            </tr>
                        </thead>
                        <tbody>{rows}</tbody>
                    </table>
                </div>
            """

    @api.depends('stage_id')
    def _compute_show_contract_generation(self):
        """Show contract generation button from stage FD (Finalisation Dossier)."""
        stage_fd = self.env.ref(
            'construction_core.stage_finalisation_dossier', 
            raise_if_not_found=False
        )
        for record in self:
            if not record.stage_id or not stage_fd:
                record.show_contract_generation = False
                continue
            record.show_contract_generation = record._is_at_or_after_stage(stage_fd)


    @api.depends('stage_id', 'stage_id.code', 'stage_id.chapter_id', 'stage_id.sequence')
    def _compute_stage_visibility(self):
        """Compute visibility of features based on current stage.
        
        Stage codes and their sequence in the workflow:
        - REC (10): Réception - nothing special visible
        - VT (20): Visite technique - visits become visible
        - DE (30): Devis envoyé - quotes and lots selection visible
        - DA (10, ch.PREP): Devis accepté - subcontractors visible
        - FD (20, ch.PREP): Finalisation dossier - invoicing visible
        """
        # Get stage codes from database for comparison
        stage_vt = self.env.ref('construction_core.stage_visite_technique', raise_if_not_found=False)
        stage_de = self.env.ref('construction_core.stage_devis_envoye', raise_if_not_found=False)
        stage_da = self.env.ref('construction_core.stage_devis_accepte', raise_if_not_found=False)
        stage_fd = self.env.ref('construction_core.stage_finalisation_dossier', raise_if_not_found=False)
        
        for record in self:
            if not record.stage_id:
                record.show_visits = False
                record.show_quotes = False
                record.show_lots_selection = False
                record.show_invoicing = False
                record.show_subcontractors = False
                continue
            
            current_stage = record.stage_id
            current_chapter = current_stage.chapter_id
            
            # Helper to compare stages (considering chapter order + stage sequence)
            def is_at_or_after(target_stage):
                """Check if current stage is at or after the target stage."""
                if not target_stage:
                    return False
                target_chapter = target_stage.chapter_id
                if current_chapter.sequence > target_chapter.sequence:
                    return True
                elif current_chapter.sequence == target_chapter.sequence:
                    return current_stage.sequence >= target_stage.sequence
                return False
            
            # Visits visible from VT (Visite technique) onwards
            record.show_visits = is_at_or_after(stage_vt)
            
            # Quotes and lot selection visible from DE (Devis envoyé) onwards
            record.show_quotes = is_at_or_after(stage_de)
            record.show_lots_selection = is_at_or_after(stage_de)
            
            # Subcontractors visible from DA (Devis accepté) onwards
            record.show_subcontractors = is_at_or_after(stage_da)
            
            # Invoicing visible from FD (Finalisation dossier) onwards
            record.show_invoicing = is_at_or_after(stage_fd)

    @api.depends(
        'stage_id', 
        'client', 'address', 'description', 'phone',       # REC
        'lots_ids', 'quotation_ids.state', 'quotation_count', # DE
        'subcontractor_ids', 'date_start_contract', 'date_end_contract', # DA
        'date_start_internal', 'date_end_internal',        # DA
        'progress',                        # TRAV
    )
    def _compute_validation_conditions_html(self):
        """Generate professional SAP/ONAYA style validation cockpit HTML."""
        for record in self:
            if not record.stage_id:
                record.validation_conditions_html = """
                    <div style="padding: 20px; text-align: center; color: #888;">
                        <i class="fa fa-info-circle" style="font-size: 24px;"></i>
                        <p style="margin-top: 10px;">Aucune étape définie</p>
                    </div>
                """
                continue
            
            stage_code = record.stage_id.code
            stage_name = record.stage_id.name
            chapter_name = record.stage_id.chapter_id.name if record.stage_id.chapter_id else ''
            validator_name = STAGE_TRANSITIONS.get(stage_code, {}).get('validator')
            next_stage_code = STAGE_TRANSITIONS.get(stage_code, {}).get('next')
            
            # Get next stage info
            next_stage = None
            if next_stage_code:
                next_stage = record.env['construction.stage'].search([('code', '=', next_stage_code)], limit=1)
            
            next_stage_name = next_stage.name if next_stage else 'Fin du workflow'
            
            # Header with current stage and progress
            header_html = f"""
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                            padding: 16px 20px; margin: -12px -12px 16px -12px; border-radius: 8px 8px 0 0;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <span style="color: rgba(255,255,255,0.8); font-size: 12px; text-transform: uppercase; letter-spacing: 1px;">
                                {chapter_name}
                            </span>
                            <h4 style="color: white; margin: 4px 0 0 0; font-size: 18px; font-weight: 600;">
                                📍 {stage_name}
                            </h4>
                        </div>
                        <div style="text-align: right;">
                            <span style="color: rgba(255,255,255,0.8); font-size: 11px;">PROCHAINE ÉTAPE</span>
                            <div style="color: white; font-size: 14px; font-weight: 500;">
                                ➡️ {next_stage_name}
                            </div>
                        </div>
                    </div>
                </div>
            """
            
            if not validator_name:
                html = header_html + """
                    <div style="padding: 20px; text-align: center;">
                        <div style="display: inline-flex; align-items: center; justify-content: center; 
                                    width: 60px; height: 60px; border-radius: 50%; 
                                    background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); margin-bottom: 12px;">
                            <i class="fa fa-check" style="color: white; font-size: 28px;"></i>
                        </div>
                        <h5 style="color: #38a169; margin: 0;">Prêt à avancer</h5>
                        <p style="color: #718096; font-size: 13px; margin: 8px 0 0 0;">
                            Aucune condition requise pour cette transition
                        </p>
                    </div>
                """
                record.validation_conditions_html = html
                continue
            
            # Call validator
            validator = getattr(record, validator_name, None)
            if validator and callable(validator):
                can_proceed, message = validator()
            else:
                can_proceed, message = True, "OK"
            
            # Build conditions display
            if can_proceed:
                content_html = """
                    <div style="padding: 20px; text-align: center;">
                        <div style="display: inline-flex; align-items: center; justify-content: center; 
                                    width: 70px; height: 70px; border-radius: 50%; 
                                    background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); 
                                    margin-bottom: 16px; box-shadow: 0 4px 15px rgba(56, 239, 125, 0.4);">
                            <i class="fa fa-check" style="color: white; font-size: 32px;"></i>
                        </div>
                        <h5 style="color: #2d3748; margin: 0; font-size: 16px;">
                            ✅ Toutes les conditions sont remplies
                        </h5>
                        <p style="color: #38a169; font-size: 14px; margin: 8px 0 0 0; font-weight: 500;">
                            Vous pouvez passer à l'étape suivante
                        </p>
                    </div>
                """
            else:
                # Parse conditions
                conditions = message.split(", ") if ", " in message else [message]
                conditions_items = ""
                for i, condition in enumerate(conditions):
                    conditions_items += f"""
                        <div style="display: flex; align-items: center; padding: 12px 16px; 
                                    background: #fff5f5; border-left: 3px solid #e53e3e; 
                                    margin-bottom: 8px; border-radius: 0 6px 6px 0;">
                            <div style="width: 28px; height: 28px; border-radius: 50%; 
                                        background: #fed7d7; display: flex; align-items: center; 
                                        justify-content: center; margin-right: 12px; flex-shrink: 0;">
                                <i class="fa fa-times" style="color: #e53e3e; font-size: 12px;"></i>
                            </div>
                            <span style="color: #c53030; font-size: 13px; font-weight: 500;">
                                {condition}
                            </span>
                        </div>
                    """
                
                content_html = f"""
                    <div style="padding: 16px;">
                        <div style="display: flex; align-items: center; margin-bottom: 16px;">
                            <div style="width: 40px; height: 40px; border-radius: 8px; 
                                        background: linear-gradient(135deg, #f6ad55 0%, #ed8936 100%); 
                                        display: flex; align-items: center; justify-content: center; margin-right: 12px;">
                                <i class="fa fa-lock" style="color: white; font-size: 18px;"></i>
                            </div>
                            <div>
                                <h5 style="color: #c05621; margin: 0; font-size: 15px;">Transition bloquée</h5>
                                <span style="color: #975a16; font-size: 12px;">
                                    {len(conditions)} condition{"s" if len(conditions) > 1 else ""} à remplir
                                </span>
                            </div>
                        </div>
                        {conditions_items}
                    </div>
                """
            
            html = f"""
                <div style="background: white; border-radius: 8px; overflow: hidden; 
                            box-shadow: 0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.06);">
                    {header_html}
                    {content_html}
                </div>
            """
            
            record.validation_conditions_html = html

    @api.depends('stage_id')
    def _compute_stage_validation_info(self):
        """Compute validation info for next stage transition."""
        for record in self:
            if not record.stage_id:
                record.stage_validation_info = "Aucune étape définie"
                continue

            can_proceed, message = record._can_move_to_next_stage()
            status = "✅ Prêt" if can_proceed else "⛔ Bloqué"
            record.stage_validation_info = f"{status}\n{message}"

    @api.depends('stage_id')
    def _compute_next_stage_name(self):
        """Retourne le nom de la prochaine étape dans la séquence. Vide si étape terminale."""
        next_codes = {
            STAGE_TRANSITIONS.get(r.stage_id.code, {}).get('next')
            for r in self if r.stage_id
        }
        next_codes.discard(None)
        if next_codes:
            stages = self.env['construction.stage'].search([('code', 'in', list(next_codes))])
            stage_by_code = {s.code: s.name for s in stages}
        else:
            stage_by_code = {}
        for record in self:
            next_code = (
                STAGE_TRANSITIONS.get(record.stage_id.code, {}).get('next')
                if record.stage_id else None
            )
            record.next_stage_name = stage_by_code.get(next_code, '') if next_code else ''

    @api.depends(
        'stage_id',
        'client', 'address', 'description', 'phone',
        'lots_ids', 'quotation_ids.state',
        'subcontractor_ids', 'date_start_contract', 'date_end_contract',
        'date_start_internal', 'date_end_internal',
        'date_start_estimated', 'date_end_estimated',
        'progress',
    )
    def _compute_next_stage_requirements(self):
        """Retourne le HTML des conditions manquantes pour passer à l'étape suivante.

        Retourne une chaîne vide si :
        - l'étape est terminale (SS, DC),
        - toutes les conditions sont remplies,
        - il n'existe pas de validator pour cette étape.
        Le HTML généré contient la liste des conditions manquantes.
        """
        from markupsafe import escape
        # Pré-charger toutes les prochaines étapes en une seule requête
        next_codes = {
            STAGE_TRANSITIONS.get(r.stage_id.code, {}).get('next')
            for r in self if r.stage_id
        }
        next_codes.discard(None)
        if next_codes:
            stages = self.env['construction.stage'].search([('code', 'in', list(next_codes))])
            stage_by_code = {s.code: s.name for s in stages}
        else:
            stage_by_code = {}

        for record in self:
            if not record.stage_id:
                record.next_stage_requirements = ''
                continue
            stage_code = record.stage_id.code
            transition = STAGE_TRANSITIONS.get(stage_code, {})
            next_code = transition.get('next')
            if not next_code:
                record.next_stage_requirements = ''
                continue
            validator_name = transition.get('validator')
            if not validator_name:
                record.next_stage_requirements = ''
                continue
            validator = getattr(record, validator_name, None)
            if not validator or not callable(validator):
                record.next_stage_requirements = ''
                continue
            try:
                can_proceed, message = validator()
            except Exception:
                can_proceed, message = False, "Erreur lors de la vérification des conditions"
            if can_proceed:
                record.next_stage_requirements = ''
                continue
            next_name = escape(stage_by_code.get(next_code, next_code))
            conditions = [c.strip() for c in message.split(', ') if c.strip()]
            items = ''.join(f'<li>{escape(c)}</li>' for c in conditions)
            record.next_stage_requirements = (
                f'<strong class="blg-guidance-title">'
                f'Conditions manquantes pour passer à {next_name}'
                f'</strong>'
                f'<ul class="blg-guidance-list">{items}</ul>'
            )

    # ============= CRUD Methods ============= #
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to generate sequences and set initial stages."""
        for vals in vals_list:
            if not vals.get('reference') or vals.get('reference') == '/':
                vals['reference'] = self.env['ir.sequence'].next_by_code('construction.chantier') or '/'
            
            if not vals.get('stage_id'):
                first_stage = self.env['construction.stage'].search(
                    [], order='chapter_id, sequence', limit=1
                )
                if first_stage:
                    vals['stage_id'] = first_stage.id
                    
        return super().create(vals_list)

    def write(self, vals):
        """Override write to validate stage transitions and dates."""
        if 'stage_id' in vals and not self.env.context.get('bypass_stage_validation'):
            if not self.env.user.has_group('construction_core.group_construction_admin'):
                raise ValidationError(_(
                    "Modification directe de l'étape interdite.\n"
                    "Utilisez les boutons 'Suivant' ou 'Précédent'."
                ))
        
        if vals.get('date_start_contract') and vals.get('date_end_contract'):
            if vals['date_start_contract'] > vals['date_end_contract']:
                raise ValidationError(_("La date de fin ne peut pas être avant la date de début."))

        return super().write(vals)

    # ============= MAIL HANDLING: message_new ============= #
    @api.model
    def message_new(self, msg_dict, custom_values=None):
        """Create a new chantier from an incoming email.
        
        Called when an email is sent to the chantier alias/catchall.
        
        Args:
            msg_dict: Dictionary containing email data:
                - subject: Email subject (becomes chantier name)
                - body: HTML body (becomes description)
                - from: Sender email address
                - author_id: res.partner ID of sender
            custom_values: Additional values to merge
            
        Returns:
            Created chantier record
        """
        # Default stage is the REC (Réception) stage
        first_stage = self.env.ref(
            'construction_core.stage_reception', raise_if_not_found=False
        ) or self.env['construction.stage'].search(
            [], order='chapter_id, sequence', limit=1
        )
        
        # Strip HTML from email body for description
        import re
        body = msg_dict.get('body', '')
        if body:
            # Remove HTML tags for plain text description
            clean_body = re.sub(r'<[^>]+>', '', body)
            clean_body = clean_body.strip()
        else:
            clean_body = ''
        
        # Find or create partner from email
        email_from = msg_dict.get('from', '')
        author_id = msg_dict.get('author_id')
        partner = False
        
        if author_id:
            partner = self.env['res.partner'].browse(author_id)
        elif email_from:
            partner = self.env['res.partner'].search([
                ('email', 'ilike', email_from)
            ], limit=1)
            if not partner:
                # Create partner from email
                partner = self.env['res.partner'].create({
                    'name': email_from.split('@')[0].replace('.', ' ').title(),
                    'email': email_from,
                })
        
        # Prepare chantier values
        defaults = {
            'name': msg_dict.get('subject', '') or _('Nouveau Chantier (via email)'),
            'description': clean_body or _('À REMPLIR'),
            'stage_id': first_stage.id if first_stage else False,
            'address': _('À REMPLIR'),
            'phone': _('À REMPLIR'),
        }
        
        if partner:
            defaults['client'] = partner.id
        
        # Merge with custom values
        if custom_values:
            defaults.update(custom_values)
        
        # Log incoming email creation
        _logger.info(
            "Creating chantier from email. Subject: %s, From: %s",
            msg_dict.get('subject', 'No Subject'),
            email_from
        )
        
        return super().message_new(msg_dict, custom_values=defaults)

    # ============= STATE MACHINE: Validators ============= #
    def check_reception_stage(self):
        """Validate REC stage requirements."""
        missing = []
        if not self.client:
            missing.append("Client")
        if not self.address:
            missing.append("Adresse du chantier")
        if not self.description:
            missing.append("Description des travaux")
        if not self.phone:
            missing.append("Téléphone du chantier")
        
        if missing:
            return False, "Champs manquants : " + ", ".join(missing)
        return True, "OK"

    def check_visit_stage(self):
        """Validate VT stage requirements."""
        if not hasattr(self, 'visit_ids') or not self.visit_ids:
            return False, "Aucune visite technique planifiée"
        
        completed = self.visit_ids.filtered(lambda v: v.state == 'completed')
        if not completed:
            return False, "Visite technique non terminée"
        return True, "OK"

    def check_quotation_sent_stage(self):
        """Validate DE stage requirements."""
        if not self.lots_ids:
            return False, "Aucun lot défini"
        if self.quotation_count <= 0:
            return False, "Aucun devis créé"
        
        accepted = self.quotation_ids.filtered(lambda q: q.state in ['sale', 'done'])
        if not accepted:
            return False, "Aucun devis accepté par le client"
        return True, "OK"

    def check_quotation_accepted_stage(self):
        """Validate DA stage requirements.
        
        Checks that all external lots have a subcontractor assigned.
        Internal lots (régie interne) don't require a subcontractor.
        """
        if not self.lots_ids:
            return False, "Aucun lot défini sur ce chantier"

        # Check that all external lots have proper subcontractor assignment
        lots_missing_assignment = []
        for lot in self.lots_ids:
            _logger.debug("[BLG][COMPLIANCE][CHECK] Lot %s: execution_type=%s ST=%s",
                          lot.name, lot.execution_type,
                          lot.subcontractor_id.name if lot.subcontractor_id else 'None')
            if lot.execution_type == 'external' and not lot.subcontractor_id:
                lots_missing_assignment.append(lot.name)
        
        if lots_missing_assignment:
            names = ", ".join(lots_missing_assignment)
            return False, f"Sous-traitant non assigné sur {len(lots_missing_assignment)} lot(s) : {names}"
        
        if not self.date_start_contract:
            return False, "Date de début contractuelle manquante"
        if not self.date_end_contract:
            return False, "Date de fin contractuelle manquante"
        if not (self.date_start_internal or self.date_start_estimated):
            return False, "Date de début (interne ou estimée) manquante"
        if not (self.date_end_internal or self.date_end_estimated):
            return False, "Date de fin (interne ou estimée) manquante"
        return True, "OK"

    def check_dossier_finalization_stage(self):
        """Validate FD stage prerequisites before allowing transition to T25.

        Returns a tuple (can_proceed, message). If any prerequisite is
        missing the chantier is blocked and the message lists every
        failing condition with the affected lot names.
        """
        missing = []

        if not self.lots_ids:
            return False, "Aucun lot défini sur ce chantier"

        external_lots = self.lots_ids.filtered(lambda l: l.execution_type == 'external')

        lots_no_st = external_lots.filtered(lambda l: not l.subcontractor_id)
        if lots_no_st:
            names = ", ".join(lots_no_st.mapped('name'))
            missing.append(f"Sous-traitant non assigné : {names}")

        if 'construction.contract' in self.env:
            for lot in external_lots.filtered(lambda l: l.subcontractor_id):
                contract = self.env['construction.contract'].search([
                    ('lot_ids', 'in', [lot.id]),
                    ('state', '=', 'signed'),
                ], limit=1)
                if not contract:
                    missing.append(
                        f"Contrat ST non signé : {lot.name} ({lot.subcontractor_id.name})"
                    )

        for lot in external_lots:
            if not lot._has_validated_po():
                missing.append(f"Bon de commande manquant : {lot.name}")

        if hasattr(self, 'invoice_schedule_ids'):
            if not self.invoice_schedule_ids:
                missing.append("Cycle de facturation non créé")
        else:
            _logger.warning(
                '[CORE] invoice_schedule_ids not available — '
                'is construction_invoice module installed?'
            )

        if not self.date_start_contract or not self.date_end_contract:
            missing.append("Dates contractuelles incomplètes (début ou fin)")

        if hasattr(self, 'document_ids'):
            for lot in external_lots:
                if not lot.document_cctp:
                    missing.append(f"CCTP manquant : {lot.name}")

        if missing:
            return False, ", ".join(missing)
        return True, "OK"

    def check_construction_percentage_stage(self):
        """Validate TRAV stages based on progress percentage."""
        stage_code = self.stage_id.code if self.stage_id else ''
        required_progress = PROGRESS_THRESHOLDS.get(stage_code, 0)
        
        if self.progress < required_progress:
            return False, f"Progression insuffisante: {self.progress:.0f}% < {required_progress}%"
        return True, "OK"

    def check_warranty_stage(self):
        """Validate LR stage requirements."""
        if self.progress < 100:
            return False, "Travaux non terminés (progression < 100%)"
        
        if hasattr(self, 'document_ids'):
            reception_docs = self.document_ids.filtered(
                lambda d: hasattr(d, 'document_type') and d.document_type == 'reception'
            )
            if not reception_docs:
                return False, "Document de réception client manquant"
        
        return True, "OK"

    def check_warranty_retention_stage(self):
        """Validate RET stage requirements - 365 days warranty."""
        if not self.date_end_contract:
            return False, "Date de fin contractuelle non définie"
        
        warranty_end = self.date_end_contract + timedelta(days=365)
        today = fields.Date.today()
        
        if today < warranty_end:
            remaining = (warranty_end - today).days
            return False, f"Période de garantie en cours ({remaining} jours restants)"
        return True, "OK"

    # ============= STATE MACHINE: Core Methods ============= #
    def _can_move_to_next_stage(self):
        """Check if chantier can proceed to next stage."""
        self.ensure_one()
        
        if not self.stage_id:
            return False, "Aucune étape définie"
        
        stage_code = self.stage_id.code
        transition = STAGE_TRANSITIONS.get(stage_code, {})
        validator_name = transition.get('validator')
        
        if not validator_name:
            return True, "Pas de validation requise"
        
        validator = getattr(self, validator_name, None)
        if validator and callable(validator):
            return validator()
        
        return True, "OK"

    def _can_move_to_previous_stage(self):
        """Check if chantier can return to previous stage."""
        self.ensure_one()
        
        if not self.stage_id or not self.stage_id.chapter_id:
            return False, "Aucune étape définie"
        
        chapter_code = self.stage_id.chapter_id.code
        
        if chapter_code in BACKWARD_BLOCKED_CHAPTERS:
            return False, f"Retour impossible depuis le chapitre {chapter_code}"
        
        if chapter_code == 'TRAV' and self.progress > 50:
            return False, "Travaux trop avancés (>50%) pour un retour"
        
        return True, "OK"

    def _get_next_stage(self):
        """Get the next stage based on state machine configuration."""
        if not self.stage_id:
            return None
        
        stage_code = self.stage_id.code
        transition = STAGE_TRANSITIONS.get(stage_code, {})
        next_code = transition.get('next')
        
        if not next_code:
            # Try to find next stage in same chapter
            return self.stage_id.get_next_stage()
        
        # Find stage by code
        next_stage = self.env['construction.stage'].search([
            ('code', '=', next_code)
        ], limit=1)
        
        if not next_stage:
            # Fallback: get next stage in sequence
            return self.stage_id.get_next_stage()
        
        return next_stage

    # ============= Business Actions ============= #
    @api.model
    def _read_group_stage_id(self, stages, domain):
        """Expand stages in Kanban view."""
        return self.env['construction.stage'].search([])

    def action_move_to_next_stage(self):
        """Move to next stage with validation (State Machine)."""
        self.ensure_one()
        
        if not self.stage_id:
            raise UserError(_("Ce chantier n'a pas d'étape définie."))
        
        can_proceed, message = self._can_move_to_next_stage()
        
        if can_proceed:
            next_stage = self._get_next_stage()
            
            if not next_stage:
                raise UserError(_("Aucune étape suivante trouvée."))
            
            old_stage = self.stage_id.name
            self.with_context(bypass_stage_validation=True).stage_id = next_stage
            
            self.message_post(
                body=f"✅ Passage de '{old_stage}' à '{next_stage.name}'",
                message_type='notification'
            )
            
            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
            }
        else:
            # Open force wizard for directors
            if self.env.user.has_group('construction_core.group_construction_admin'):
                next_stage = self._get_next_stage()
                return {
                    'name': _('Forcer le Changement d\'Étape'),
                    'type': 'ir.actions.act_window',
                    'res_model': 'construction.force.stage.wizard',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {
                        'default_chantier_id': self.id,
                        'default_current_stage_id': self.stage_id.id,
                        'default_new_stage_id': next_stage.id if next_stage else False,
                    }
                }
            else:
                raise UserError(_(f"Impossible de passer à l'étape suivante :\n{message}"))

    def action_move_to_previous_stage(self):
        """Move to previous stage with safety checks."""
        self.ensure_one()
        
        if not self.stage_id:
            raise UserError(_("Ce chantier n'a pas d'étape définie."))
        
        can_proceed, message = self._can_move_to_previous_stage()
        
        if not can_proceed:
            raise UserError(_(f"Retour impossible :\n{message}"))
        
        prev_stage = self.stage_id.get_previous_stage()
        
        if not prev_stage:
            # Try previous chapter's last stage
            current_chapter = self.stage_id.chapter_id
            prev_chapter = self.env['construction.chapter'].search([
                ('sequence', '<', current_chapter.sequence)
            ], order='sequence desc', limit=1)
            
            if prev_chapter:
                prev_stage = self.env['construction.stage'].search([
                    ('chapter_id', '=', prev_chapter.id)
                ], order='sequence desc', limit=1)
        
        if not prev_stage:
            raise UserError(_("Aucune étape précédente trouvée."))
        
        old_stage = self.stage_id.name
        self.with_context(bypass_stage_validation=True).stage_id = prev_stage
        
        self.message_post(
            body=f"⬅️ Retour de '{old_stage}' à '{prev_stage.name}'",
            message_type='notification'
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Étape mise à jour'),
                'message': _('Chantier rétrogradé à : %s') % prev_stage.name,
                'type': 'warning'
            }
        }

    def action_view_documents(self):
        """Smart button: View GED documents (navigation only)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Documents — %s') % self.name,
            'res_model': 'construction.document',
            'view_mode': 'list,form',
            'domain': [('chantier_id', '=', self.id)],
            'context': {},
        }

    def action_view_lots(self):
        """Smart button: View lots (navigation only, no creation)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Lots - %s') % self.name,
            'res_model': 'construction.lot',
            'view_mode': 'list,form',
            'domain': [('chantier_id', '=', self.id)],
            'context': {},
        }

    def action_view_quotations(self):
        """Smart button: View quotations (navigation only, no creation)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Devis - %s') % self.name,
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'domain': [('chantier_id', '=', self.id)],
            'context': {},
        }

    # ============= TAB ACTION METHODS ============= #
    
    def action_create_visit(self):
        """Create a new visit for this chantier."""
        self.ensure_one()
        if 'construction.visit' not in self.env:
            raise UserError(_("Le module Visites (construction_visit) n'est pas installé."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Nouvelle Visite'),
            'res_model': 'construction.visit',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_chantier_id': self.id,
                'default_visit_type': 'initial',  # Valid values: initial, progress, quality, final
            },
        }

    def action_view_all_visits(self):
        """View all visits for this chantier."""
        self.ensure_one()
        if 'construction.visit' not in self.env:
            raise UserError(_("Le module Visites (construction_visit) n'est pas installé."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Visites - %s') % self.name,
            'res_model': 'construction.visit',
            'view_mode': 'list,calendar,form',
            'domain': [('chantier_id', '=', self.id)],
            'context': {'default_chantier_id': self.id},
        }

    def action_view_planning_visits(self):
        """View global planning of all visits."""
        if 'construction.visit' not in self.env:
            raise UserError(_("Le module Visites (construction_visit) n'est pas installé."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Planning Visites'),
            'res_model': 'construction.visit',
            'view_mode': 'calendar,list,form',
            'context': {'search_default_group_by_chantier': 1},
        }

    def action_add_lot(self):
        """Add a new lot to this chantier."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Ajouter un Lot'),
            'res_model': 'construction.lot',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_chantier_id': self.id,
            },
        }

    def action_create_quotation(self):
        """Create a new quotation for this chantier."""
        self.ensure_one()
        
        # Create draft order immediately
        order = self.env['sale.order'].create({
            'partner_id': self.client.id,
            'chantier_id': self.id,
        })
        
        # Open the Quote Builder
        return {
            'type': 'ir.actions.client',
            'tag': 'construction_sale.quote_builder',
            'name': _('Smart Quote Builder'),
            'context': {
                'default_chantier_id': self.id,
                'default_order_id': order.id,
            },
        }

    def action_create_invoice_schedule(self):
        """Create invoice schedule for this chantier."""
        self.ensure_one()
        # Try to use wizard if available
        wizard_action = self.env.ref('construction_invoice.action_invoice_schedule_wizard', raise_if_not_found=False)
        if wizard_action:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Nouveau Planning de Facturation'),
                'res_model': 'construction.invoice.schedule.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {'default_chantier_id': self.id},
            }
        # Fallback: direct creation
        return {
            'type': 'ir.actions.act_window',
            'name': _('Planning Facturation'),
            'res_model': 'construction.invoice.schedule',
            'view_mode': 'form',
            'context': {'default_chantier_id': self.id},
        }

    def action_view_invoices(self):
        """View all invoices for this chantier."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Factures - %s') % self.name,
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('chantier_id', '=', self.id), ('move_type', '=', 'out_invoice')],
            'context': {'default_chantier_id': self.id},
        }

    # ============= DOCUMENT ACTION METHODS ============= #
    
    def action_upload_document(self):
        """Open wizard to upload a document."""
        self.ensure_one()
        # Try to use wizard if available from construction_document
        wizard_action = self.env.ref('construction_document.action_document_upload_wizard', raise_if_not_found=False)
        if wizard_action:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Ajouter un Document'),
                'res_model': 'construction.document.upload.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {'default_chantier_id': self.id},
            }
        # Fallback: open attachment form
        return {
            'type': 'ir.actions.act_window',
            'name': _('Ajouter un Document'),
            'res_model': 'ir.attachment',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_res_model': 'construction.chantier',
                'default_res_id': self.id,
            },
        }

    def action_view_all_documents(self):
        """View all documents attached to this chantier."""
        self.ensure_one()
        # Check if construction_document model exists
        if 'construction.document' in self.env:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Documents - %s') % self.name,
                'res_model': 'construction.document',
                'view_mode': 'list,kanban,form',
                'domain': [('chantier_id', '=', self.id)],
                'context': {'default_chantier_id': self.id},
            }
        # Fallback: show standard attachments
        return {
            'type': 'ir.actions.act_window',
            'name': _('Documents - %s') % self.name,
            'res_model': 'ir.attachment',
            'view_mode': 'list,form',
            'domain': [
                ('res_model', '=', 'construction.chantier'),
                ('res_id', '=', self.id)
            ],
        }

    # ============= CONTRACT GENERATION GATE ============= #
    
    def _is_at_or_after_stage(self, target_stage):
        """Check if current stage is at or after target stage.
        
        Uses chapter sequence + stage sequence for comparison.
        """
        self.ensure_one()
        if not self.stage_id or not target_stage:
            return False
        
        current = self.stage_id
        current_chapter = current.chapter_id
        target_chapter = target_stage.chapter_id
        
        if current_chapter.sequence > target_chapter.sequence:
            return True
        elif current_chapter.sequence == target_chapter.sequence:
            return current.sequence >= target_stage.sequence
        return False

    def _can_generate_contract(self, partner_id):
        """Validate contract generation conditions for a subcontractor.
        
        Args:
            partner_id: ID of the subcontractor (res.partner)
            
        Returns:
            tuple: (can_generate: bool, message: str)
            
        Validation Rules:
        1. Chantier stage >= stage_finalisation_dossier (FD)
        2. Partner has at least 1 external lot assigned
        3. Every external lot for this partner has a confirmed PO
        """
        self.ensure_one()
        
        # Rule 1: Check stage
        stage_fd = self.env.ref(
            'construction_core.stage_finalisation_dossier', 
            raise_if_not_found=False
        )
        if not stage_fd or not self._is_at_or_after_stage(stage_fd):
            return False, _(
                "Le chantier doit être au stade 'Finalisation Dossier' minimum."
            )
        
        # Rule 2: Check partner has external lots
        partner_lots = self.lots_ids.filtered(
            lambda l: l.execution_type == 'external' and l.subcontractor_id.id == partner_id
        )
        if not partner_lots:
            return False, _(
                "Aucun lot en sous-traitance assigné à ce partenaire."
            )
        
        # Rule 3: Check all lots have validated POs
        lots_without_po = partner_lots.filtered(lambda l: not l._has_validated_po())
        if lots_without_po:
            lot_names = ', '.join(lots_without_po.mapped('name'))
            return False, _(
                "Lots sans bon de commande validé: %s"
            ) % lot_names
        
        return True, _("OK - Toutes les conditions sont remplies")

    def action_generate_contract(self, partner_id=None):
        """Open contract creation form pre-filled with subcontractor data.
        
        Args:
            partner_id: Subcontractor partner ID (can come from context)
        """
        self.ensure_one()
        
        # Get partner_id from context if not provided
        if not partner_id:
            partner_id = self.env.context.get('default_partner_id')
        
        if not partner_id:
            raise UserError(_(
                "Veuillez sélectionner un sous-traitant."
            ))
        
        # Validate conditions
        can_generate, message = self._can_generate_contract(partner_id)
        if not can_generate:
            raise UserError(_(
                "Impossible de générer le contrat:\n%s"
            ) % message)
        
        # Get partner lots
        partner_lots = self.lots_ids.filtered(
            lambda l: l.execution_type == 'external' and l.subcontractor_id.id == partner_id
        )
        
        # Get confirmed POs for these lots
        PurchaseOrder = self.env.get('purchase.order')
        po_ids = []
        if PurchaseOrder:
            pos = PurchaseOrder.search([
                ('lot_ids', 'in', partner_lots.ids),
                ('state', 'in', ['purchase', 'done'])
            ])
            po_ids = pos.ids
        
        # Check if construction.contract model exists
        if 'construction.contract' not in self.env:
            raise UserError(_(
                "Le module 'construction_subcontractor' doit être installé "
                "pour la gestion des contrats."
            ))
        
        # Open contract form pre-filled
        return {
            'type': 'ir.actions.act_window',
            'name': _('Nouveau Contrat - %s') % self.env['res.partner'].browse(partner_id).name,
            'res_model': 'construction.contract',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_partner_id': partner_id,
                'default_chantier_id': self.id,
                'default_lot_ids': [(6, 0, partner_lots.ids)],
                'default_purchase_order_ids': [(6, 0, po_ids)] if po_ids else False,
                'default_date_start': self.date_start_internal or self.date_start_contract,
                'default_date_end': self.date_end_internal or self.date_end_contract,
            },
        }

    def action_check_contract_eligibility(self):
        """Check contract eligibility for all project subcontractors."""
        self.ensure_one()
        results = []
        for partner in self.project_subcontractor_ids:
            can_gen, msg = self._can_generate_contract(partner.id)
            status = "✅" if can_gen else "❌"
            results.append(f"{status} {partner.name}: {msg}")
        
        message = "\n".join(results) if results else _("Aucun sous-traitant sur ce projet")
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Éligibilité Contrats'),
                'message': message,
                'type': 'info',
                'sticky': True,
            }
        }

    # ============= Backward Compatibility (aliases) ============= #
    def action_next_stage(self):
        """Alias for action_move_to_next_stage."""
        return self.action_move_to_next_stage()

    def action_previous_stage(self):
        """Alias for action_move_to_previous_stage."""
        return self.action_move_to_previous_stage()

