from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta

# -------------------------------------------------
#  CONSTANTES / RÈGLES MÉTIER
# -------------------------------------------------
ACTION_RULES = {
    "show_schedule_visit": lambda rec: rec.state == "active",
    "show_create_quote": lambda rec: rec.state == "active"
                                     and rec.stage_id.chapter_id.name in {"Étude", "Conception", "Devis"},
    "show_assign_subcontractors": lambda rec: rec.state == "active"
                                              and rec.stage_id.chapter_id.name in {"Exécution", "Réalisation",
                                                                                   "Travaux"},
    "show_mark_not_pursued": lambda rec: rec.state in {"active", "abandoned"},
    "show_split_quote": lambda rec: rec.can_split_quote() if hasattr(rec, 'can_split_quote') else False,
}

STAGE_VALIDATORS = {
    ("AO", "REC"): "check_reception_stage",
    ("AO", "VT"): "check_visit_stage",
    ("AO", "DE"): "check_quotation_sent_stage",
    ("PREP", "DA"): "check_quotation_accepted_stage",
    ("PREP", "FD"): "check_dossier_finalization_stage",
    ("LEVEE", "LR"): "check_warranty_stage",
    ("RET", "RET"): "check_warranty_retention_stage",
}

class Chantier(models.Model):
    _name = 'construction.chantier'
    _description = 'Construction Project'
    _inherit = ['mail.thread', 'mail.activity.mixin']



    # ===========Attributes==========#
    name = fields.Char('Project Name', required=True)
    reference = fields.Char('Reference', copy=False, readonly=True, default='/')
    stage_id = fields.Many2one('construction.stage', 'Stage', group_expand='_read_group_stage_id', readonly=True)
    client = fields.Many2one('res.partner', 'Client', required=True)
    lots_ids = fields.Many2many('construction.lot')
    chapter_name = fields.Char('Chapter Name', compute='_compute_chapter_name', store=True)
    user_ids = fields.Many2many('res.users', string='Project Users')
    tag_ids = fields.Many2many('construction.tag', string='Tags')
    description = fields.Text('Description')
    notes = fields.Text('Notes')

    subcontractor_ids = fields.Many2many(
        'res.partner',
        'construction_chantier_subcontractor_rel',
        'chantier_id', 'partner_id',
        string='Sous-traitants',
        domain="[('supplier_rank', '>', 0)]",
        help="Sous-traitants assignés à ce chantier"
    )

    # Dates contractuelles et internes
    date_start_contract = fields.Date('Date de début contractuelle', tracking=True)
    date_end_contract = fields.Date('Date de fin contractuelle', tracking=True)
    date_start_actual = fields.Date('Date de début réelle', tracking=True)
    date_end_actual = fields.Date('Date de fin réelle', tracking=True)
    date_start_internal = fields.Date('Date de début interne', tracking=True)
    date_end_internal = fields.Date('Date de fin interne', tracking=True)
    client_approval_date = fields.Date('Date d\'approbation client', tracking=True,
                                       help="Date à laquelle le client a accepté le devis")

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
    sale_order_count = fields.Integer('Nombre de devis/commandes', compute='_compute_counts', store=True)
    subcontractor_count = fields.Integer('Nombre de sous-traitants', compute='_compute_counts', store=True)
    lots_count = fields.Integer('Nombre de lots', compute='_compute_counts', store=True)
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

    _sql_constraints = [
        ('positive_cost', 'CHECK(total_cost >= 0)', 'Le coût total doit être positif'),
        ('positive_surface', 'CHECK(surface_m2 >= 0)', 'La surface doit être positive'),
        ('progress_range', 'CHECK(progress >= 0 AND progress <= 100)',
         'La progression doit être entre 0 et 100%'),
    ]

    @api.model
    def create(self, vals):
        """Créer le chantier avec génération automatique de référence et stage initial"""
        # Génération automatique de référence
        if not vals.get('reference') or vals.get('reference') == '/':
            vals['reference'] = self.env['ir.sequence'].next_by_code('construction.chantier') or '/'

        # Assigner automatiquement le stage de départ
        if not vals.get('stage_id'):
            # Utiliser l'external_id défini dans construction_data.xml
            default_stage = self.env.ref('construction_base.stage_reception')
            vals['stage_id'] = default_stage.id

        return super().create(vals)

    def write(self, vals):
        """Empêcher la modification directe du stage_id sauf par workflow ou admin"""
        if 'stage_id' in vals and not self.env.context.get('bypass_stage_validation', False):
            # Vérifier si l'utilisateur a les droits d'administrateur
            if not self.env.user.has_group('base.group_system'):
                raise ValidationError(
                    "Modification directe de l'étape interdite.\n"
                    "Utilisez les boutons 'Étape suivante' ou 'Étape précédente' "
                    "pour respecter le workflow métier.\n\n"
                    "Seuls les administrateurs peuvent forcer un changement d'étape."
                )

        return super().write(vals)

    @api.constrains('date_start_contract', 'date_end_contract')
    def _check_contract_dates(self):
        for record in self:
            if record.date_start_contract and record.date_end_contract:
                if record.date_start_contract > record.date_end_contract:
                    raise ValidationError(_("La date de début ne peut pas être postérieure à la date de fin."))

    @api.depends('stage_id', 'stage_id.chapter_id', 'stage_id.chapter_id.name')
    def _compute_chapter_name(self):
        for record in self:
            if record.stage_id and record.stage_id.chapter_id:
                record.chapter_name = record.stage_id.chapter_id.name
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

    @api.depends('lots_ids.price', 'lots_ids.is_finished')
    def _compute_construction_progression(self):
        """Calcule la progression basée sur le coût des lots terminés"""
        for record in self:
            old_progress = record.progress
            total_cost = sum(record.lots_ids.mapped('price'))
            if total_cost > 0:
                completed_cost = sum(record.lots_ids.filtered('is_finished').mapped('price'))
                record.progress = (completed_cost / total_cost) * 100
            else:
                record.progress = 0.0

            # Déclencher la vérification des seuils de facturation si la progression a changé
            if old_progress != record.progress and record.invoice_schedule_ids:
                record._check_invoice_triggers()

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

    @api.depends('lots_ids.price')
    def _compute_total_cost(self):
        for record in self:
            record.total_cost = sum(record.lots_ids.mapped('price'))

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
            # ───── Étape absente → on sort ─────
            if not (rec.stage_id and rec.stage_id.chapter_id):
                rec.stage_validation_info = "❌ Aucune étape définie"
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

            # ------------------------------------------------------------------
            # 3️⃣  Message unique à l’utilisateur
            # ------------------------------------------------------------------
            header = f"📍 Étape : {rec.stage_id.chapter_id.name} – {rec.stage_id.name}"
            footer = "✅ PRÊT POUR L’ÉTAPE SUIVANTE" if ok else "❌ CONDITIONS NON REMPLIES"
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
        if not self.date_end_internal:
            return False, "Date de fin interne non définie"
        if not self.date_start_internal:
            return False, "Date de début interne non définie"
        else:
            return True, "OK"

    def check_dossier_finalization_stage(self):
        """
        Valide que :
          1. Chaque lot possède au moins un sous-traitant.
          2. Au moins un devis du sous-traitant est accepté (état « sale » ou « done »).
          3. Les données de facturation et de planning sont complètes.

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

        # 4️⃣ Autres vérifications globales
        if not self.invoice_type_id:
            return False, "Cycle de facturation non sélectionné"

        if not self.main_quote_id:
            return False, "Devis principal non sélectionné"

        if not self.date_start_contract or not self.date_end_contract:
            return False, "Planning de chantier incomplet"

        # 5️⃣ Tout est conforme
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
        if not can_proceed:
            raise ValidationError(f"Impossible de passer à l'étape suivante :\n{message}")

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
                        body=f"💰 {len(advance_payments)} acompte(s) de signature automatiquement activé(s) "
                             f"(étape finalisation dossier atteinte)",
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

        # Temporairement simple message - wizard sera ajouté plus tard
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': '⚠️ Fonction admin',
                'message': 'Cette fonction sera disponible prochainement',
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


    def action_setup_invoice_schedule(self):
        """Configurer le planning de facturation basé sur le cycle choisi"""
        self.ensure_one()

        if not self.invoice_type_id:
            raise ValidationError("Vous devez d'abord sélectionner un cycle de facturation.")

        if not self.total_cost:
            raise ValidationError("Le coût total du chantier doit être défini pour configurer la facturation.")

        # Supprimer le planning existant si il y en a un
        self.invoice_schedule_ids.unlink()

        # Créer les lignes de planning basées sur le cycle choisi
        schedule_lines = []
        for line in self.invoice_type_id.line_ids:
            schedule_lines.append({
                'chantier_id': self.id,
                'invoice_type_line_id': line.id,
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


    def action_trigger_advance_payment(self):
        """Déclencher manuellement l'acompte de signature"""
        self.ensure_one()

        advance_payments = self.invoice_schedule_ids.filtered(
            lambda s: s.is_advance_payment and s.state == 'planned'
        )

        if not advance_payments:
            raise ValidationError(
                "Aucun acompte de signature en attente pour ce chantier."
            )

        for payment in advance_payments:
            payment.write({
                'state': 'ready',
                'is_triggered': True
            })

        self.message_post(
            body=f"📝 {len(advance_payments)} acompte(s) de signature déclenché(s) manuellement",
            message_type='notification'
        )

        return self.action_view_invoice_schedule()


    def action_check_invoice_triggers(self):
        """Vérifier manuellement tous les seuils de facturation"""
        self.ensure_one()

        if not self.invoice_schedule_ids:
            raise ValidationError(
                "Aucun planning de facturation configuré pour ce chantier."
            )

        old_ready_count = len(self.invoice_schedule_ids.filtered(lambda s: s.state == 'ready'))
        self._check_invoice_triggers()
        new_ready_count = len(self.invoice_schedule_ids.filtered(lambda s: s.state == 'ready'))

        triggered_count = new_ready_count - old_ready_count

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Vérification des seuils',
                'message': f'{triggered_count} nouvelle(s) facture(s) déclenchée(s). Avancement: {self.progress}%',
                'type': 'success' if triggered_count > 0 else 'info'
            }
        }


    @api.onchange('invoice_type_id')
    def _onchange_invoice_type_id(self):
        """Proposer de reconfigurer le planning quand le cycle change"""
        if self.invoice_type_id and self.invoice_schedule_ids:
            return {
                'warning': {
                    'title': 'Cycle de facturation modifié',
                    'message': 'Un planning de facturation existe déjà. '
                               'Vous devez utiliser le bouton "Configurer facturation" '
                               'pour mettre à jour le planning selon le nouveau cycle.'
                }
            }


    def _check_invoice_triggers(self):
        """Vérifier automatiquement les seuils de facturation selon l'avancement"""
        self.ensure_one()
        if not self.invoice_schedule_ids:
            return

        # Vérifier tous les seuils de facturation
        for schedule_line in self.invoice_schedule_ids:
            schedule_line.check_progress_trigger()

        # Compter les nouvelles factures prêtes
        ready_invoices = self.invoice_schedule_ids.filtered(
            lambda s: s.state == 'ready' and s.is_triggered
        )

        if ready_invoices:
            self.message_post(
                body=f"💰 {len(ready_invoices)} facture(s) prête(s) à émettre suite à l'avancement du chantier",
                message_type='comment'
            )


    @api.model
    def _read_group_stage_id(self, stages, domain, order=None):
        """Retourne tous les stages pour le group_expand dans la vue kanban"""
        if not order:
            order = 'chapter_id, sequence'
        return self.env['construction.stage'].search([], order=order)

    # ================================================================
    #                   QUOTE SPLITTING FUNCTIONALITY
    # ================================================================

    def can_split_quote(self):
        """Check if quote splitting is available for this chantier."""
        return self.env['quote.split.service'].can_split_quote(self.id)

    def action_split_quote_by_lots(self):
        """Split the main quote into sub-quotes by lots and assign to subcontractors."""
        self.ensure_one()
        
        # Utiliser le service de division
        result = self.env['quote.split.service'].split_quote_by_lots(self.id)
        
        if result['success']:
            # Rafraîchir la vue pour montrer les nouveaux sous-devis
            self._compute_quotation_count()
            
            # Ouvrir une vue avec les sous-devis créés
            return self.action_view_subquotes(result['created_subquotes'])
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

    def action_split_quote_wizard(self):
        """Open the quote splitting wizard for guided splitting."""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Division de devis par lots'),
            'res_model': 'construction.quote.split.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_chantier_id': self.id,
            }
        }

    def action_view_subquotes(self, subquote_ids=None):
        """View sub-quotes for this chantier."""
        self.ensure_one()
        
        if subquote_ids:
            domain = [('id', 'in', subquote_ids)]
        else:
            subquotes = self.env['quote.split.service'].get_subquotes_for_chantier(self.id)
            domain = [('id', 'in', subquotes.ids)]
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'Sous-devis - {self.name}',
            'res_model': 'sale.order',
            'view_mode': 'tree,form',
            'domain': domain,
            'context': {
                'default_chantier_id': self.id,
                'search_default_group_by_partner': 1,
            },
            'target': 'current',
        }

    def action_quick_edit_subquote(self):
        """Quick access to edit sub-quotes via popup."""
        self.ensure_one()
        
        subquotes = self.env['quote.split.service'].get_subquotes_for_chantier(self.id)
        
        if not subquotes:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'warning',
                    'message': 'Aucun sous-devis trouvé. Divisez d\'abord le devis principal.',
                    'sticky': False,
                }
            }
        
        # Si un seul sous-devis, l'ouvrir directement
        if len(subquotes) == 1:
            return self.env['quote.split.service'].quick_access_subquote(subquotes[0].id)
        
        # Sinon, afficher une liste pour sélection
        return {
            'type': 'ir.actions.act_window',
            'name': 'Sélectionner un sous-devis',
            'res_model': 'sale.order',
            'view_mode': 'list',
            'domain': [('id', 'in', subquotes.ids)],
            'context': {
                'default_chantier_id': self.id,
                'create': False,
                'delete': False,
            },
            'target': 'new',
        }


