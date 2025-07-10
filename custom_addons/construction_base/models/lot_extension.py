from odoo import models, fields, api, _

class ConstructionLot(models.Model):
    """Extension du modèle lot pour la construction avec fonctionnalités avancées"""
    
    _name = 'construction.lot'
    _inherit = ['lot', 'mail.thread', 'mail.activity.mixin']
    _description = 'Lot de construction'
    
    # =================== CHAMPS FINANCIERS ===================
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Devise',
        default=lambda self: self.env.company.currency_id,
        required=True
    )
    
    price = fields.Monetary(
        string='Prix estimé', 
        currency_field='currency_id',
        default=0.0,
        tracking=True,
        help="Prix estimé ou contractuel du lot"
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
    
    # =================== CONTRAINTES ===================
    
    _sql_constraints = [
        ('positive_price', 'CHECK(price >= 0)', 'Le prix doit être positif'),
    ]

    # =================== ACTIONS ===================
    
    def action_assign_subcontractor(self):
        """Assigner automatiquement un sous-traitant spécialisé à ce lot."""
        self.ensure_one()
        
        # Récupérer le chantier depuis le contexte
        chantier = None
        if 'active_model' in self.env.context and self.env.context['active_model'] == 'construction.chantier':
            chantier_id = self.env.context.get('active_id')
            if chantier_id:
                chantier = self.env['construction.chantier'].browse(chantier_id)
        
        if not chantier:
            # Chercher le chantier qui contient ce lot
            chantiers = self.env['construction.chantier'].search([
                ('lots_ids', 'in', self.id)
            ])
            if chantiers:
                chantier = chantiers[0]
        
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

