
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta

class Chantier(models.Model):
    _name = 'construction.chantier'
    _description = 'Construction Project'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    #===========Attributes==========#
    name = fields.Char('Project Name', required=True)
    reference = fields.Char('Reference', copy=False, readonly=True, default='/')
    stage_id  = fields.Many2one('construction.stage', 'Stage', group_expand='_read_group_stage_id', readonly=True)
    client = fields.Many2one('res.partner', 'Client', required=True)
    lots_ids = fields.Many2many('lot')
    chapter_name = fields.Char('Chapter Name', compute='_compute_chapter_name', store=True)
    user_ids = fields.Many2many('res.users', string='Project Users')
    tag_ids = fields.Many2many('construction.tag', string='Tags')
    description = fields.Text('Description')
    notes = fields.Text('Notes')
    
    subcontractors = fields.Many2many('res.partner', string='Subcontractors', compute='_compute_subcontractors')
    
    # Dates contractuelles et internes
    date_start_contract = fields.Date('Date de début contractuelle', tracking=True)
    date_end_contract = fields.Date('Date de fin contractuelle', tracking=True)
    date_start_actual = fields.Date('Date de début réelle', tracking=True)
    date_end_actual = fields.Date('Date de fin réelle', tracking=True)
    date_start_internal = fields.Date('Date de début interne', tracking=True)
    date_end_internal = fields.Date('Date de fin interne', tracking=True)
    client_approval_date = fields.Date('Date d\'approbation client', tracking=True, help="Date à laquelle le client a accepté le devis")

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

    show_schedule_visit = fields.Boolean('Afficher planifier visite', compute='_compute_action_visibility', default=False)
    show_create_quote = fields.Boolean('Afficher créer devis', compute='_compute_action_visibility', default=False)
    show_assign_subcontractors = fields.Boolean('Afficher assigner sous-traitants',
                                                compute='_compute_action_visibility', default=False)
    show_mark_not_pursued = fields.Boolean('Afficher marquer sans suite', compute='_compute_action_visibility', default=False)

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

    @api.depends('lots_ids.subcontractor_ids')
    def _compute_subcontractors(self):
        for record in self:
            # Récupérer tous les sous-traitants assignés aux lots de ce chantier
            assigned_subcontractors = self.env['res.partner']
            for lot in record.lots_ids:
                assigned_subcontractors |= lot.subcontractor_ids
            record.subcontractors = assigned_subcontractors

    @api.depends('lots_ids.price', 'lots_ids.is_finished')
    def _compute_construction_progression(self):
        """Calcule la progression basée sur le coût des lots terminés"""
        for record in self:
            total_cost = sum(record.lots_ids.mapped('price'))
            if total_cost > 0:
                completed_cost = sum(record.lots_ids.filtered('is_finished').mapped('price'))
                record.progress = (completed_cost / total_cost) * 100
            else:
                record.progress = 0.0

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

    @api.depends('state', 'stage_id', 'stage_id.chapter_id')
    def _compute_action_visibility(self):
        """Détermine quelles actions sont visibles selon l'état et l'étape du chantier"""
        for record in self:
            # Par défaut, masquer toutes les actions
            record.show_schedule_visit = False
            record.show_create_quote = False
            record.show_assign_subcontractors = False
            record.show_mark_not_pursued = False

            if not record.stage_id:
                continue

            # Logique basée sur l'état du chantier
            if record.state in ['active']:
                # Planifier une visite - toujours disponible pour les chantiers actifs
                record.show_schedule_visit = True

                # Créer un devis - selon l'étape
                if record.stage_id and record.stage_id.chapter_id:
                    chapter_name = record.stage_id.chapter_id.name
                    if chapter_name in ['Étude', 'Conception', 'Devis']:
                        record.show_create_quote = True

                # Assigner des sous-traitants - pour les phases d'exécution
                if record.stage_id and record.stage_id.chapter_id:
                    chapter_name = record.stage_id.chapter_id.name
                    if chapter_name in ['Exécution', 'Réalisation', 'Travaux']:
                        record.show_assign_subcontractors = True

            # Marquer sans suite - disponible pour les états draft et active
            if record.state in ['abandoned', 'active']:
                record.show_mark_not_pursued = True

    @api.depends('stage_id', 'stage_id.chapter_id', 'lots_ids', 'document_ids', 'visit_ids', 'progress', 'total_cost', 'subcontractors', 'date_start_contract', 'date_end_contract')
    def _compute_stage_validation_info(self):
        """Calcule les informations de validation pour passer à l'étape suivante selon le cahier des charges"""
        for record in self:
            info_lines = []
            can_proceed = True

            # ✅ Vérifier que stage_id et chapter_id existent
            if not record.stage_id or not record.stage_id.chapter_id:
                record.stage_validation_info = "❌ Aucune étape définie"
                continue

            chapter_code = record.stage_id.chapter_id.code
            stage_code = record.stage_id.code
            chapter_name = record.stage_id.chapter_id.name
            stage_name = record.stage_id.name

            info_lines.append(f"📍 Étape actuelle : {chapter_name} - {stage_name}")
            info_lines.append("")

            # === CHAPITRE 1: APPEL D'OFFRE ===
            if chapter_code == 'APPEL':
                if stage_code == 'REC':  # Réception
                    info_lines.append("📋 Conditions pour passer à 'Visite technique' :")
                    # Vérifier informations client
                    if not record.client:
                        info_lines.append("❌ Client non défini")
                        can_proceed = False
                    else:
                        info_lines.append("✅ Client défini")
                    
                    if not record.address:
                        info_lines.append("❌ Adresse du chantier manquante")
                        can_proceed = False
                    else:
                        info_lines.append("✅ Adresse du chantier définie")
                    
                    if not record.description:
                        info_lines.append("❌ Description des travaux manquante")
                        can_proceed = False
                    else:
                        info_lines.append("✅ Description des travaux fournie")

                elif stage_code == 'VT':  # Visite technique
                    info_lines.append("🔍 Conditions pour passer à 'Devis envoyé' :")
                    # Vérifier visite technique réalisée
                    if not record.visit_ids:
                        info_lines.append("❌ Aucune visite technique planifiée/réalisée")
                        can_proceed = False
                    else:
                        completed_visits = record.visit_ids.filtered(lambda v: v.state == 'completed')
                        if not completed_visits:
                            info_lines.append("❌ Visite technique non terminée")
                            can_proceed = False
                        else:
                            info_lines.append("✅ Visite technique réalisée")
                    
                    # Vérifier documents techniques
                    technical_docs = record.document_ids.filtered(lambda d: d.document_type in ['photo', 'plan', 'note'])
                    if not technical_docs:
                        info_lines.append("⚠️ Aucun document technique (recommandé)")
                    else:
                        info_lines.append(f"✅ {len(technical_docs)} document(s) technique(s)")

                elif stage_code == 'DE':  # Devis envoyé
                    info_lines.append("💰 Conditions pour passer à 'Devis accepté' :")
                    # Vérifier devis établi
                    if record.total_cost <= 0:
                        info_lines.append("❌ Devis non établi (coût = 0)")
                        can_proceed = False
                    else:
                        info_lines.append(f"✅ Devis établi : {record.total_cost:,.2f} €")
                    
                    if not record.lots_ids:
                        info_lines.append("❌ Lots de travaux non définis")
                        can_proceed = False
                    else:
                        info_lines.append(f"✅ {len(record.lots_ids)} lot(s) défini(s)")
                    
                    info_lines.append("📧 Devis doit être envoyé au client")

            # === CHAPITRE 2: PRÉPARATION CHANTIER ===
            elif chapter_code == 'PREP':
                if stage_code == 'DA':  # Devis accepté
                    info_lines.append("📝 Conditions pour passer à 'Finalisation dossier' :")
                    # Vérifier accord client
                    if not record.client_approval_date:
                        info_lines.append("❌ Accord client non confirmé")
                        can_proceed = False
                    else:
                        info_lines.append("✅ Accord client confirmé")
                    
                    # Vérifier contrat signé (simulation via date de début contractuelle)
                    if not record.date_start_contract:
                        info_lines.append("❌ Date de début contractuelle non définie")
                        can_proceed = False
                    else:
                        info_lines.append("✅ Contrat négocié (dates définies)")

                elif stage_code == 'FD':  # Finalisation dossier
                    info_lines.append("🏗️ Conditions pour passer aux 'Travaux' :")
                    # Vérifier sous-traitants
                    if not record.subcontractors:
                        info_lines.append("❌ Aucun sous-traitant sélectionné")
                        can_proceed = False
                    else:
                        info_lines.append(f"✅ {len(record.subcontractors)} sous-traitant(s) sélectionné(s)")
                    
                    # Vérifier planning
                    if not record.date_start_contract or not record.date_end_contract:
                        info_lines.append("❌ Planning de chantier incomplet")
                        can_proceed = False
                    else:
                        info_lines.append("✅ Planning de chantier établi")
                    
                    # Vérifier documents administratifs
                    admin_docs = record.document_ids.filtered(lambda d: d.document_type in ['permit', 'contract'])
                    if not admin_docs:
                        info_lines.append("⚠️ Documents administratifs recommandés")
                    else:
                        info_lines.append("✅ Documents administratifs présents")

            # === CHAPITRE 3: TRAVAUX ===
            elif chapter_code == 'TRAV':
                next_threshold = self._get_next_progress_threshold(record.progress)
                if next_threshold:
                    info_lines.append(f"🔨 Conditions pour passer au seuil suivant ({next_threshold}%) :")
                    info_lines.append(f"⏳ Progression actuelle : {record.progress:.1f}%")
                    
                    if record.progress < next_threshold:
                        info_lines.append(f"❌ Progression requise : {next_threshold}%")
                        can_proceed = False
                    else:
                        info_lines.append(f"✅ Seuil {next_threshold}% atteint")
                    
                    # Facturation automatique aux seuils
                    if next_threshold in [30, 60, 90]:
                        info_lines.append(f"💰 Génération automatique facture {next_threshold}%")
                else:
                    # Travaux terminés
                    info_lines.append("🏁 Conditions pour passer à 'Levée de réserves' :")
                    if record.progress < 100:
                        info_lines.append(f"❌ Travaux non terminés ({record.progress:.1f}%)")
                        can_proceed = False
                    else:
                        info_lines.append("✅ Travaux terminés (100%)")

            # === CHAPITRE 4: LEVÉE DE RÉSERVES ===
            elif chapter_code == 'LEVEE':
                if stage_code == 'LR':  # Levée de réserves
                    info_lines.append("📋 Conditions pour passer à 'Attente de paiement' :")
                    # Vérifier réception client
                    reception_docs = record.document_ids.filtered(lambda d: d.document_type == 'reception')
                    if not reception_docs:
                        info_lines.append("❌ Réception client non effectuée")
                        can_proceed = False
                    else:
                        info_lines.append("✅ Réception client effectuée")
                    
                    # Vérifier traitement des réserves
                    if record.progress < 100:
                        info_lines.append("❌ Réserves non traitées")
                        can_proceed = False
                    else:
                        info_lines.append("✅ Réserves traitées")

                elif stage_code == 'AP':  # Attente de paiement
                    info_lines.append("💰 Conditions pour passer à 'Retenue garantie' :")
                    info_lines.append("📄 Facture finale doit être émise")
                    info_lines.append("⏳ En attente du paiement client")

            # === CHAPITRE 5: RETENUE GARANTIE ===
            elif chapter_code == 'RET':
                info_lines.append("⏰ Période de garantie (1 an) :")
                info_lines.append("✅ Paiement complet reçu")
                info_lines.append("🛡️ Garantie en cours")
                info_lines.append("📞 Suivi SAV si nécessaire")
                
                # Vérifier fin de période de garantie
                if record.date_end_contract:
                    from datetime import datetime, timedelta
                    end_warranty = record.date_end_contract + timedelta(days=365)
                    if datetime.now().date() >= end_warranty:
                        info_lines.append("✅ Période de garantie terminée - Passage possible à 'Archive'")
                    else:
                        remaining_days = (end_warranty - datetime.now().date()).days
                        info_lines.append(f"⏳ {remaining_days} jour(s) restant(s)")
                        can_proceed = False

            # === CHAPITRE 6: ARCHIVE ===
            elif chapter_code == 'ARCH':
                if stage_code == 'CLOT':
                    info_lines.append("✅ Projet terminé avec succès")
                    info_lines.append("😊 Client satisfait")
                    info_lines.append("📁 Dossier archivé")
                elif stage_code == 'SS':
                    info_lines.append("❌ Projet abandonné")
                    info_lines.append("📁 Archivage pour référence")

            # Résumé final
            info_lines.append("")
            if can_proceed:
                info_lines.append("✅ PRÊT POUR L'ÉTAPE SUIVANTE")
            else:
                info_lines.append("❌ CONDITIONS NON REMPLIES")

            # ✅ ASSIGNATION OBLIGATOIRE
            record.stage_validation_info = '\n'.join(info_lines) if info_lines else "Aucune information disponible"

    @api.depends('lots_ids', 'subcontractors')
    def _compute_available_subcontractors(self):
        for record in self:
            if not record.lots_ids:
                record.available_subcontractors = self.env['res.partner']
                continue

            # Chercher les sous-traitants qui ont des compétences dans les lots de ce chantier
            available_subcontractors = self.env['res.partner']
            
            # Si le module blggroupe_contact_extension est installé, utiliser sa méthode
            if hasattr(self.env['res.partner'], 'get_subcontractors_by_lot'):
                for lot in record.lots_ids:
                    lot_subcontractors = self.env['res.partner'].get_subcontractors_by_lot(lot.id)
                    available_subcontractors |= lot_subcontractors
            else:
                # Sinon, logique de base : tous les fournisseurs
                available_subcontractors = self.env['res.partner'].search([
                    ('supplier_rank', '>', 0)
                ])

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

    def _get_next_progress_threshold(self, current_progress):
        """Retourne le prochain seuil de progression pour le chapitre Travaux"""
        thresholds = [25, 50, 75, 100]
        for threshold in thresholds:
            if current_progress < threshold:
                return threshold
        return None
    
    def _can_move_to_next_stage(self):
        """Vérifie si le chantier peut passer à l'étape suivante"""
        if not self.stage_id:
            return False, "Aucune étape définie"
        
        chapter_code = self.stage_id.chapter_id.code
        stage_code = self.stage_id.code
        
        # Vérifications spécifiques selon le cahier des charges
        if chapter_code == 'APPEL':
            if stage_code == 'REC':  # Réception → Visite technique
                if not self.client:
                    return False, "Client non défini"
                if not self.address:
                    return False, "Adresse du chantier manquante"
                if not self.description:
                    return False, "Description des travaux manquante"
                    
            elif stage_code == 'VT':  # Visite technique → Devis envoyé
                if not self.visit_ids:
                    return False, "Aucune visite technique réalisée"
                completed_visits = self.visit_ids.filtered(lambda v: v.state == 'completed')
                if not completed_visits:
                    return False, "Visite technique non terminée"
                    
            elif stage_code == 'DE':  # Devis envoyé → Devis accepté
                if self.total_cost <= 0:
                    return False, "Devis non établi"
                if not self.lots_ids:
                    return False, "Lots de travaux non définis"
        
        elif chapter_code == 'PREP':
            if stage_code == 'DA':  # Devis accepté → Finalisation dossier
                if not self.date_start_contract:
                    return False, "Date de début contractuelle non définie"
                    
            elif stage_code == 'FD':  # Finalisation dossier → Travaux
                if not self.subcontractors:
                    return False, "Aucun sous-traitant sélectionné"
                if not self.date_start_contract or not self.date_end_contract:
                    return False, "Planning de chantier incomplet"
        
        elif chapter_code == 'TRAV':  # Travaux
            next_threshold = self._get_next_progress_threshold(self.progress)
            if next_threshold and self.progress < next_threshold:
                return False, f"Progression insuffisante ({self.progress:.1f}% < {next_threshold}%)"
        
        elif chapter_code == 'LEVEE':
            if stage_code == 'LR':  # Levée de réserves → Attente paiement
                if self.progress < 100:
                    return False, "Réserves non traitées"
                reception_docs = self.document_ids.filtered(lambda d: d.document_type == 'reception')
                if not reception_docs:
                    return False, "Réception client non effectuée"
        
        elif chapter_code == 'RET':  # Retenue garantie → Archive
            if self.date_end_contract:
                from datetime import datetime, timedelta
                end_warranty = self.date_end_contract + timedelta(days=365)
                if datetime.now().date() < end_warranty:
                    remaining_days = (end_warranty - datetime.now().date()).days
                    return False, f"Période de garantie en cours ({remaining_days} jour(s) restant(s))"
        
        return True, "Conditions remplies"
    
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
        
        # Vérifier les conditions
        can_proceed, message = self._can_move_to_next_stage()
        if not can_proceed:
            raise ValidationError(f"Impossible de passer à l'étape suivante :\n{message}")
        
        # Trouver l'étape suivante
        next_stage = None
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
            else:
                # Travaux terminés → Levée de réserves
                next_stage = self.env['construction.stage'].search([
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
    
    def _trigger_stage_actions(self):
        """Déclenche les actions automatiques selon l'étape atteinte"""
        chapter_code = self.stage_id.chapter_id.code
        stage_code = self.stage_id.code
        
        # Actions automatiques selon le cahier des charges
        if chapter_code == 'RET':  # Retenue garantie
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
            'domain': [('id', 'in', self.subcontractors.ids)],
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
            'res_model': 'lot',  # ou le nom exact de votre modèle lot
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
        """Ouvrir le wizard de création de devis intelligent"""
        self.ensure_one()

        # Temporairement rediriger vers la création de devis standard
        return {
            'type': 'ir.actions.act_window',
            'name': 'Créer un devis',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_partner_id': self.client.id if self.client else False,
                'default_chantier_id': self.id,
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
    
    @api.model
    def _read_group_stage_id(self, stages, domain, order=None):
        """Retourne tous les stages pour le group_expand dans la vue kanban"""
        if not order:
            order = 'chapter_id, sequence'
        return self.env['construction.stage'].search([], order=order)


