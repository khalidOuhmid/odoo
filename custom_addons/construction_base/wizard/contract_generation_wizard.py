# -*- coding: utf-8 -*-
"""
Wizard de génération de contrats de sous-traitance.
Interface utilisateur pour configurer et générer les contrats.
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class ContractGenerationWizard(models.TransientModel):
    """Wizard de génération de contrats de sous-traitance."""
    
    _name = 'construction.contract.generation.wizard'
    _description = 'Génération de contrats de sous-traitance'

    # =================== CHAMPS PRINCIPAUX ===================
    
    chantier_id = fields.Many2one(
        'construction.chantier',
        string='Chantier',
        required=True,
        readonly=True,
        help="Chantier concerné"
    )
    
    subcontractor_id = fields.Many2one(
        'res.partner',
        string='Sous-traitant',
        required=True,
        domain="[('is_subcontractor', '=', True)]",
        help="Sous-traitant pour lequel générer le contrat"
    )
    
    lot_ids = fields.Many2many(
        'construction.lot',
        string='Lots concernés',
        required=True,
        domain="[('chantier_id', '=', chantier_id)]",
        help="Lots de travaux à inclure dans le contrat"
    )
    
    # =================== CONDITIONS CONTRACTUELLES ===================
    
    start_date = fields.Date(
        string='Date de début',
        required=True,
        default=fields.Date.today,
        help="Date de début des travaux"
    )
    
    end_date = fields.Date(
        string='Date de fin',
        help="Date de fin prévue des travaux"
    )
    
    total_amount = fields.Monetary(
        string='Montant total',
        currency_field='currency_id',
        required=True,
        help="Montant total du contrat"
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Devise',
        default=lambda self: self.env.company.currency_id
    )
    
    payment_terms = fields.Selection([
        ('30_days', '30 jours'),
        ('45_days', '45 jours'),
        ('60_days', '60 jours'),
        ('end_of_work', 'Fin des travaux'),
        ('custom', 'Personnalisé')
    ], string='Conditions de paiement', default='30_days')
    
    payment_terms_custom = fields.Text(
        string='Conditions personnalisées',
        help="Conditions de paiement personnalisées"
    )
    
    warranty_period = fields.Integer(
        string='Garantie (mois)',
        default=12,
        help="Période de garantie en mois"
    )
    
    insurance_required = fields.Boolean(
        string='Assurance requise',
        default=True,
        help="Assurance décennale requise"
    )
    
    # =================== OPTIONS DE GÉNÉRATION ===================
    
    generate_pdf = fields.Boolean(
        string='Générer PDF',
        default=True,
        help="Générer le fichier PDF du contrat"
    )
    
    send_email = fields.Boolean(
        string='Envoyer par email',
        default=True,
        help="Envoyer le contrat par email au sous-traitant"
    )
    
    create_portal_link = fields.Boolean(
        string='Créer lien portail',
        default=True,
        help="Créer un lien vers le portail pour signature"
    )
    
    notes = fields.Text(
        string='Notes',
        help="Notes additionnelles pour le contrat"
    )
    
    # =================== COMPUTED FIELDS ===================
    
    @api.depends('lot_ids')
    def _compute_total_amount(self):
        """Calculer automatiquement le montant total basé sur les lots."""
        for wizard in self:
            if wizard.lot_ids:
                total = sum(lot.price for lot in wizard.lot_ids)
                wizard.total_amount = total
            else:
                wizard.total_amount = 0.0
    
    # =================== ACTIONS ===================
    
    def action_generate_contract(self):
        """Générer le contrat de sous-traitance."""
        self.ensure_one()
        
        # Validation
        if not self.subcontractor_id:
            raise ValidationError(_("Veuillez sélectionner un sous-traitant."))
        
        if not self.lot_ids:
            raise ValidationError(_("Veuillez sélectionner au moins un lot."))
        
        if not self.total_amount or self.total_amount <= 0:
            raise ValidationError(_("Le montant total doit être supérieur à 0."))
        
        # Préparer les données du contrat
        contract_data = {
            'start_date': self.start_date,
            'end_date': self.end_date,
            'total_amount': self.total_amount,
            'payment_terms': self.payment_terms_custom if self.payment_terms == 'custom' else self.payment_terms,
            'warranty_period': self.warranty_period,
            'insurance_required': self.insurance_required,
            'notes': self.notes,
        }
        
        # Générer le contrat via le service
        contract_service = self.env['construction.contract.service']
        contract = contract_service.generate_subcontractor_contract(
            self.chantier_id,
            self.subcontractor_id,
            self.lot_ids,
            contract_data
        )
        
        # Envoyer par email si demandé
        if self.send_email:
            contract.action_send_contract()
        
        # Afficher une notification de succès
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Succès'),
                'message': _('Contrat généré avec succès pour {}').format(self.subcontractor_id.name),
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window',
                    'name': f'Contrat - {self.subcontractor_id.name}',
                    'res_model': 'construction.subcontractor.contract',
                    'res_id': contract.id,
                    'view_mode': 'form',
                    'target': 'current',
                }
            }
        }
    
    @api.model
    def default_get(self, fields_list):
        """Valeurs par défaut depuis le contexte."""
        defaults = super().default_get(fields_list)
        
        # Récupérer les valeurs du contexte
        for field in ['chantier_id', 'subcontractor_id', 'lot_ids']:
            context_key = f'default_{field}'
            if context_key in self.env.context:
                defaults[field] = self.env.context[context_key]
        
        return defaults 