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

_logger = logging.getLogger(__name__)


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
    """
    _name = 'construction.chantier'
    _description = 'Gestion de Chantier'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

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
    
    # ============= Financial ============= #
    currency_id = fields.Many2one(
        'res.currency',
        string='Devise',
        default=lambda self: self.env.company.currency_id
    )
    total_cost = fields.Monetary(
        string='Coût Total',
        compute='_compute_total_cost',
        store=True,
        currency_field='currency_id'
    )
    
    # ============= Relations ============= #
    user_ids = fields.Many2many('res.users', string='Responsables')
    
    # NOTE: quotation_ids is added by construction_sale module via _inherit
    # Defining One2many here causes KeyError because sale_order.py loads after chantier.py
    quotation_count = fields.Integer(compute='_compute_quotation_count')
    
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
    
    # NOTE: visit_ids and document_ids are added by construction_visit and 
    # construction_document modules respectively via _inherit

    
    # ============= Constraints ============= #
    _sql_constraints = [
        ('positive_surface', 'CHECK(surface_m2 >= 0)', 'La surface doit être positive.'),
        ('progress_range', 'CHECK(progress >= 0 AND progress <= 100)', 'La progression doit être entre 0 et 100%.'),
    ]

    # ============= Computed Fields ============= #
    @api.depends('stage_id', 'stage_id.chapter_id')
    def _compute_chapter_name(self):
        for record in self:
            record.chapter_name = record.stage_id.chapter_id.name if record.stage_id and record.stage_id.chapter_id else False

    @api.depends('date_start_contract', 'date_end_contract')
    def _compute_duration_planned(self):
        for record in self:
            if record.date_start_contract and record.date_end_contract:
                delta = record.date_end_contract - record.date_start_contract
                record.duration_planned = delta.days + 1
            else:
                record.duration_planned = 0

    @api.depends('date_start_internal', 'date_end_internal', 'state')
    def _compute_duration_actual(self):
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

    @api.depends('lots_ids.is_finished', 'lots_ids.price')
    def _compute_progress(self):
        """Calculate progress based on finished lots."""
        for record in self:
            total_price = sum(record.lots_ids.mapped('price'))
            finished_price = sum(record.lots_ids.filtered('is_finished').mapped('price'))
            record.progress = (finished_price / total_price * 100) if total_price > 0 else 0.0

    @api.depends('lots_ids.price')
    def _compute_total_cost(self):
        for record in self:
            record.total_cost = sum(record.lots_ids.mapped('price'))

    def _compute_quotation_count(self):
        for record in self:
            record.quotation_count = len(record.quotation_ids)

    def _compute_subcontractor_count(self):
        for record in self:
            record.subcontractor_count = len(record.subcontractor_ids)

    def _compute_lots_count(self):
        for record in self:
            record.lots_count = len(record.lots_ids)

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

    # ============= CRUD Methods ============= #
    @api.model_create_multi
    def create(self, vals_list):
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
        if 'stage_id' in vals and not self.env.context.get('bypass_stage_validation'):
            if not self.env.user.has_group('construction_core.group_construction_director'):
                raise ValidationError(_(
                    "Modification directe de l'étape interdite.\n"
                    "Utilisez les boutons 'Suivant' ou 'Précédent'."
                ))
        
        if vals.get('date_start_contract') and vals.get('date_end_contract'):
            if vals['date_start_contract'] > vals['date_end_contract']:
                raise ValidationError(_("La date de fin ne peut pas être avant la date de début."))

        return super().write(vals)

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
        """Validate DA stage requirements."""
        if len(self.subcontractor_ids) != len(self.lots_ids):
            return False, f"Sous-traitants: {len(self.subcontractor_ids)}, Lots: {len(self.lots_ids)}"
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
        """Validate FD stage requirements."""
        if not self.lots_ids:
            return False, "Aucun lot défini"
        
        lots_without_subcontractor = self.lots_ids.filtered(lambda l: not l.subcontractor_ids)
        if lots_without_subcontractor:
            names = ", ".join(lots_without_subcontractor.mapped('name'))
            return False, f"Lots sans sous-traitant: {names}"
        
        if not self.date_start_contract or not self.date_end_contract:
            return False, "Dates contractuelles incomplètes"
        
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
                'tag': 'display_notification',
                'params': {
                    'title': _('Étape mise à jour'),
                    'message': _('Chantier passé à : %s') % next_stage.name,
                    'type': 'success'
                }
            }
        else:
            # Open force wizard for directors
            if self.env.user.has_group('construction_core.group_construction_director'):
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

    def action_view_lots(self):
        """Smart button: View lots."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Lots - %s') % self.name,
            'res_model': 'construction.lot',
            'view_mode': 'list,form',
            'domain': [('chantier_id', '=', self.id)],
            'context': {'default_chantier_id': self.id},
        }

    def action_view_quotations(self):
        """Smart button: View quotations."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Devis - %s') % self.name,
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'domain': [('chantier_id', '=', self.id)],
            'context': {'default_chantier_id': self.id},
        }

    # ============= Backward Compatibility (aliases) ============= #
    def action_next_stage(self):
        """Alias for action_move_to_next_stage."""
        return self.action_move_to_next_stage()

    def action_previous_stage(self):
        """Alias for action_move_to_previous_stage."""
        return self.action_move_to_previous_stage()
