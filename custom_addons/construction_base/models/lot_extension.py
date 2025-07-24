from odoo import models, fields, api, _
from datetime import timedelta

class ConstructionLot(models.Model):
    """Extension du modèle lot pour la construction avec fonctionnalités avancées"""

    _name = 'construction.lot'
    _inherit = ['lot', 'mail.thread', 'mail.activity.mixin']
    _description = 'Lot de construction'

    # =================== RELATION AVEC CHANTIER ===================
    
    chantier_id = fields.Many2one(
        'construction.chantier',
        string='Chantier',
        required=True,
        ondelete='cascade',
        help="Chantier auquel appartient ce lot"
    )

    # =================== CHAMPS FINANCIERS ===================

    currency_id = fields.Many2one(
        'res.currency',
        string='Devise',
        related='chantier_id.currency_id',
        store=True,
        help="Devise du chantier"
    )

    price = fields.Monetary(
        string='Prix estimé',
        currency_field='currency_id',
        default=0.0,
        tracking=True,
        help="Prix estimé ou contractuel du lot"
    )
    
    price_from_quote = fields.Monetary(
        string='Prix depuis devis',
        currency_field='currency_id',
        compute='_compute_price_from_quote',
        store=True,
        help="Prix calculé depuis le devis principal du chantier"
    )

    # =================== RELATIONS ===================

    subcontractor_ids = fields.Many2many(
        'res.partner',
        string='Sous-traitants',
        domain="[('supplier_rank', '>', 0)]",
        help="Sous-traitants assignés à ce lot"
    )

    # =================== ÉTAT ET PROGRESSION ===================

    is_finished = fields.Boolean(
        string='Terminé',
        default=False,
        tracking=True,
        help="Indique si le lot est terminé"
    )

    quote_state = fields.Selection([
        ('draft', 'Pas de devis'),
        ('sent', 'Devis envoyé'),
        ('accepted', 'Devis accepté'),
        ('rejected', 'Devis rejeté')
    ], string='Statut devis', default='draft', tracking=True)

    # =================== CHAMPS ADDITIONNELS ===================

    description = fields.Text(
        string='Description',
        help="Description détaillée du lot de travaux"
    )

    notes = fields.Text(
        string='Notes',
        help="Notes internes sur le lot"
    )
    
    # =================== CHAMPS DOCUMENTS ===================
    
    document_cctp = fields.Binary(
        string="CCTP",
        attachment=True,
        help="Cahier des Clauses Techniques Particulières"
    )
    
    document_subcontractor_contract = fields.Binary(
        string="Contrat de sous-traitance",
        attachment=True,
        help="Contrat de sous-traitance pour ce lot"
    )
    
    planning_task_ids = fields.One2many('construction.planning.task', 'lot_id', string='Tâches de planning')

    # =================== CHAMPS CALCULÉS ===================

    lot_date_start = fields.Datetime(
        string='Date de début du lot',
        compute='_compute_lot_dates',
        store=True,
        help="Date de début du lot calculée à partir de la tâche la plus proche"
    )

    lot_date_end = fields.Datetime(
        string='Date de fin du lot',
        compute='_compute_lot_dates',
        store=True,
        help="Date de fin du lot calculée à partir de la tâche la plus lointaine"
    )

    @api.depends('planning_task_ids.date_start', 'planning_task_ids.date_stop')
    def _compute_lot_dates(self):
        """Calcule les dates de début et de fin du lot à partir des tâches associées."""
        for lot in self:
            tasks = lot.planning_task_ids.filtered(lambda t: t.date_start and t.date_stop)
            if tasks:
                # Trouver la date de début la plus proche (minimum)
                lot.lot_date_start = min(tasks.mapped('date_start'))
                # Trouver la date de fin la plus lointaine (maximum)
                lot.lot_date_end = max(tasks.mapped('date_stop'))
            else:
                # Si pas de tâches, utiliser les dates du chantier si disponible
                if lot.chantier_id and lot.chantier_id.date_start_contract:
                    lot.lot_date_start = fields.Datetime.to_datetime(lot.chantier_id.date_start_contract)
                    if lot.chantier_id.date_end_contract:
                        lot.lot_date_end = fields.Datetime.to_datetime(lot.chantier_id.date_end_contract)
                    else:
                        lot.lot_date_end = lot.lot_date_start + timedelta(days=30)
                else:
                    lot.lot_date_start = False
                    lot.lot_date_end = False

    @api.depends('chantier_id.main_quote_id.order_line', 'order_line_ids.price_subtotal')
    def _compute_price_from_quote(self):
        """Calcule le prix du lot à partir du devis principal du chantier"""
        for lot in self:
            lot.price_from_quote = 0.0
            
            if lot.order_line_ids:
                # Utiliser les lignes directement associées au lot
                lot.price_from_quote = sum(lot.order_line_ids.mapped('price_subtotal'))
            elif lot.chantier_id and lot.chantier_id.main_quote_id:
                # Fallback : chercher par nom si pas encore associé
                main_quote = lot.chantier_id.main_quote_id
                
                # Rechercher les lignes du devis qui correspondent à ce lot
                lot_lines = main_quote.order_line.filtered(
                    lambda line: (
                        lot.name.lower() in line.name.lower() or 
                        lot.code.lower() in line.name.lower() or
                        (line.product_id and lot.name.lower() in line.product_id.name.lower()) or
                        (line.product_id and lot.code.lower() in line.product_id.name.lower())
                    ) and not line.display_type
                )
                
                if lot_lines:
                    lot.price_from_quote = sum(lot_lines.mapped('price_subtotal'))

    # =================== RELATIONS POUR COMMANDES ===================
    
    order_line_ids = fields.One2many(
        'sale.order.line',
        'lot_id',
        string='Articles à commander',
        help="Articles du devis principal associés à ce lot"
    )
    
    # =================== CHAMPS CALCULÉS POUR COMMANDES ===================
    
    order_line_count = fields.Integer(
        string='Nombre d\'articles',
        compute='_compute_order_stats',
        help="Nombre total d'articles dans ce lot"
    )
    
    ordered_lines_count = fields.Integer(
        string='Articles commandés',
        compute='_compute_order_stats',
        help="Nombre d'articles avec une date de commande"
    )
    
    tracking_lines_count = fields.Integer(
        string='Articles avec tracking',
        compute='_compute_order_stats',
        help="Nombre d'articles avec un lien de tracking"
    )
    
    @api.depends('order_line_ids', 'order_line_ids.order_date', 'order_line_ids.tracking_link')
    def _compute_order_stats(self):
        """Calcule les statistiques de commande pour ce lot"""
        for lot in self:
            lines = lot.order_line_ids
            lot.order_line_count = len(lines)
            lot.ordered_lines_count = len(lines.filtered('order_date'))
            lot.tracking_lines_count = len(lines.filtered('tracking_link'))

    # =================== MÉTHODES UTILITAIRES ===================

    def get_chantier(self):
        """Récupère le chantier associé à ce lot via la relation directe"""
        self.ensure_one()
        return self.chantier_id

    # =================== CONTRAINTES ===================

    _sql_constraints = [
        ('positive_price', 'CHECK(price >= 0)', 'Le prix doit être positif'),
    ]

    # =================== ACTIONS ===================

    def action_assign_subcontractor(self):
        """Assigner automatiquement un sous-traitant spécialisé à ce lot."""
        self.ensure_one()

        # Récupérer le chantier depuis le contexte ou via la relation directe
        chantier = None
        if 'active_model' in self.env.context and self.env.context['active_model'] == 'construction.chantier':
            chantier_id = self.env.context.get('active_id')
            if chantier_id:
                chantier = self.env['construction.chantier'].browse(chantier_id)

        if not chantier:
            # Utiliser la relation directe
            chantier = self.chantier_id

        if not chantier:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Erreur',
                    'message': 'Impossible de déterminer le chantier pour ce lot.',
                    'type': 'danger'
                }
            }

        # Chercher les sous-traitants spécialisés dans ce lot
        # D'abord parmi ceux déjà assignés au chantier
        specialists_in_chantier = chantier.subcontractor_ids.filtered(
            lambda s: self.name in s.lot_ids.mapped('name')
        )

        if specialists_in_chantier:
            # S'il y en a un seul, l'assigner directement
            if len(specialists_in_chantier) == 1:
                self.subcontractor_ids = [(4, specialists_in_chantier[0].id)]
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Assignation réussie',
                        'message': f'{specialists_in_chantier[0].name} a été assigné au lot "{self.name}".',
                        'type': 'success'
                    }
                }
            else:
                # S'il y en a plusieurs, ouvrir un wizard de sélection
                return self._open_subcontractor_selection_wizard(specialists_in_chantier, chantier)

        # Si aucun spécialiste dans le chantier, chercher dans tous les sous-traitants
        all_specialists = self.env['res.partner'].search([
            ('is_subcontractor', '=', True),
            ('lot_ids.name', '=', self.name)
        ])

        if not all_specialists:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Aucun spécialiste',
                    'message': f'Aucun sous-traitant spécialisé en "{self.name}" n\'a été trouvé dans la base.',
                    'type': 'warning'
                }
            }

        # Proposer d'ajouter un spécialiste au chantier
        return self._open_subcontractor_selection_wizard(all_specialists, chantier, add_to_chantier=True)

    def _open_subcontractor_selection_wizard(self, subcontractors, chantier, add_to_chantier=False):
        """Ouvrir un wizard pour sélectionner un sous-traitant parmi plusieurs."""
        # Si un seul choix et on doit l'ajouter au chantier
        if len(subcontractors) == 1 and add_to_chantier:
            subcontractor = subcontractors[0]
            # Ajouter au chantier
            chantier.subcontractor_ids = [(4, subcontractor.id)]
            # Assigner au lot
            self.subcontractor_ids = [(4, subcontractor.id)]

            chantier.message_post(
                body=f"🔗 Sous-traitant {subcontractor.name} ajouté au chantier et assigné au lot '{self.name}'",
                message_type='notification'
            )

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Assignation réussie',
                    'message': f'{subcontractor.name} a été ajouté au chantier et assigné au lot "{self.name}".',
                    'type': 'success'
                }
            }

        # Ouvrir le wizard de sélection
        return {
            'type': 'ir.actions.act_window',
            'name': f'Sélectionner un sous-traitant pour {self.name}',
            'res_model': 'lot.subcontractor.assign.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_lot_id': self.id,
                'default_chantier_id': chantier.id,
                'default_available_subcontractor_ids': [(6, 0, subcontractors.ids)],
                'default_add_to_chantier': add_to_chantier,
            }
        }

    def action_create_subquote_for_lot(self):
        """Créer un sous-devis spécifique pour ce lot avec sélection de devis."""
        self.ensure_one()

        # Vérifier qu'un sous-traitant est assigné
        if not self.subcontractor_ids:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sous-traitant requis',
                    'message': f'Veuillez d\'abord assigner un sous-traitant au lot "{self.name}".',
                    'type': 'warning'
                }
            }

        # D'abord essayer de récupérer le chantier depuis le contexte
        chantier_from_context = None
        if 'active_model' in self.env.context and self.env.context['active_model'] == 'construction.chantier':
            chantier_id = self.env.context.get('active_id')
            if chantier_id:
                chantier_from_context = self.env['construction.chantier'].browse(chantier_id)
                # Vérifier que ce chantier contient bien notre lot
                if self.id in chantier_from_context.lots_ids.ids:
                    return self._open_quote_selection_wizard(chantier_from_context)

        # Sinon, chercher les chantiers utilisant ce lot
        chantiers = self.env['construction.chantier'].search([
            ('lots_ids', 'in', self.id)
        ])

        if not chantiers:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Aucun chantier',
                    'message': f'Le lot "{self.name}" n\'est associé à aucun chantier.',
                    'type': 'warning'
                }
            }

        # Si un seul chantier, ouvrir directement le wizard de sélection de devis
        if len(chantiers) == 1:
            return self._open_quote_selection_wizard(chantiers[0])

        # Si plusieurs chantiers, ouvrir wizard de sélection
        return self._open_chantier_selection_wizard(chantiers)

    def check_has_subquote(self):
        """Vérifie si ce lot a au moins un sous-devis pour ses sous-traitants sur le chantier associé."""
        self.ensure_one()

        if not self.subcontractor_ids:
            return False

        if not self.chantier_id:
            return False

        subquote_count = self.env['sale.order'].search_count([
            ('lot_ids', 'in', self.id),  # Lié à ce lot
            ('partner_id', 'in', self.subcontractor_ids.ids),  # Sous-traitants du lot
            ('chantier_id', '=', self.chantier_id.id),  # Chantier spécifique
            ('state', 'in', ['draft', 'sent', 'sale'])  # États pertinents (ajustable)
        ])

        return subquote_count > 0

    def action_display_subquotation(self):
        """Afficher le ou les sous-devis pour ce lot et ses sous-traitants."""
        self.ensure_one()

        # Vérifier qu'un sous-traitant est assigné
        if not self.subcontractor_ids:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sous-traitant requis',
                    'message': f'Veuillez d\'abord assigner un sous-traitant au lot "{self.name}".',
                    'type': 'warning'
                }
            }

        # Rechercher les sous-devis associés à ce lot et à ses sous-traitants
        sub_quotes = self.env['sale.order'].search([
            ('lot_ids', 'in', self.id),  # Le devis doit être lié à ce lot
            ('partner_id', 'in', self.subcontractor_ids.ids),  # Limité aux sous-traitants du lot
            ('state', 'in', ['draft', 'sent', 'sale'])  # Filtre optionnel sur les états pertinents
        ])

        if not sub_quotes:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Aucun sous-devis',
                    'message': f'Aucun sous-devis trouvé pour le lot "{self.name}" et ses sous-traitants.',
                    'type': 'info'
                }
            }

        # Si un seul sous-devis, ouvrir en vue formulaire
        if len(sub_quotes) == 1:
            return {
                'name': f'Sous-devis pour {self.name}',
                'type': 'ir.actions.act_window',
                'res_model': 'sale.order',
                'res_id': sub_quotes.id,
                'view_mode': 'form',
                'target': 'current'
            }

        # Si plusieurs, ouvrir en vue liste avec domaine
        return {
            'name': f'Sous-devis pour {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'domain': [('id', 'in', sub_quotes.ids)],
            'target': 'current'
        }

    def _open_chantier_selection_wizard(self, chantiers):
        """Ouvrir un wizard pour sélectionner le chantier."""
        return {
            'type': 'ir.actions.act_window',
            'name': f'Sélectionner le chantier pour le lot {self.name}',
            'res_model': 'construction.chantier',
            'view_mode': 'list',
            'domain': [('id', 'in', chantiers.ids)],
            'target': 'new',
            'context': {
                'create': False,
                'edit': False,
                'lot_id': self.id,
                'action_type': 'select_chantier_for_subquote'
            }
        }

    def _open_quote_selection_wizard(self, chantier):
        """Ouvrir le wizard de sélection de devis pour créer le sous-devis."""
        return {
            'type': 'ir.actions.act_window',
            'name': f'Créer sous-devis pour {self.name}',
            'res_model': 'lot.subquote.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_lot_id': self.id,
                'default_chantier_id': chantier.id,
                'default_subcontractor_id': self.subcontractor_ids[0].id if self.subcontractor_ids else False
            }
        }

    def action_open_lot_document_wizard(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Gérer les documents du lot',
            'res_model': 'lot.document.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_lot_id': self.id,
                'default_chantier_id': self.chantier_id.id if self.chantier_id else False,
                'default_subcontractor_id': self.subcontractor_ids and self.subcontractor_ids[0].id or False,
                'active_id': self.id,
            },
        }
