# -*- coding: utf-8 -*-
"""
Wizard de configuration de la facturation pour un chantier
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class InvoiceSetupWizard(models.TransientModel):
    _name = 'construction.invoice.setup.wizard'
    _description = 'Configuration de la facturation'

    chantier_id = fields.Many2one(
        'construction.chantier',
        string='Chantier',
        required=True,
        readonly=True
    )
    
    quote_id = fields.Many2one(
        'sale.order',
        string='Devis de référence',
        required=True,
        domain="[('chantier_id', '=', chantier_id), ('state', 'in', ['sale', 'done'])]",
        help="Devis accepté servant de base pour calculer les montants de facturation"
    )
    
    invoice_type_id = fields.Many2one(
        'construction.invoice_type',
        string='Cycle de facturation',
        required=True,
        help="Pattern de facturation à appliquer"
    )
    
    lot_ids = fields.Many2many(
        'construction.lot',
        string='Lots concernés',
        domain="[('chantier_id', '=', chantier_id)]",
        help="Lots du chantier concernés par la facturation (laisser vide pour tous les lots)"
    )
    
    margin_percentage = fields.Float(
        string='Marge à déduire (%)',
        default=0.0,
        help="Pourcentage de marge à déduire des montants du devis"
    )
    
    # Informations de prévisualisation
    quote_amount = fields.Monetary(
        string='Montant du devis',
        compute='_compute_quote_info',
        currency_field='currency_id'
    )
    
    total_schedules = fields.Integer(
        string='Nombre d\'étapes',
        compute='_compute_quote_info'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id
    )

    @api.depends('quote_id', 'invoice_type_id')
    def _compute_quote_info(self):
        for record in self:
            if record.quote_id:
                record.quote_amount = record.quote_id.amount_total
            else:
                record.quote_amount = 0.0
                
            if record.invoice_type_id:
                record.total_schedules = len(record.invoice_type_id.line_ids)
            else:
                record.total_schedules = 0

    @api.onchange('chantier_id')
    def _onchange_chantier_id(self):
        """Réinitialiser les champs quand le chantier change"""
        if self.chantier_id:
            self.quote_id = False
            self.invoice_type_id = False
            self.lot_ids = [(5, 0, 0)]

    @api.onchange('quote_id')
    def _onchange_quote_id(self):
        """Proposer le cycle de facturation par défaut"""
        if self.quote_id and not self.invoice_type_id:
            # Essayer de trouver un cycle par défaut
            default_cycle = self.env['construction.invoice_type'].search([
                ('active', '=', True)
            ], limit=1)
            if default_cycle:
                self.invoice_type_id = default_cycle

    def action_create_invoice_schedule(self):
        """Créer le planning de facturation"""
        self.ensure_one()
        
        # Validations
        if not self.quote_id:
            raise ValidationError(_("Veuillez sélectionner un devis de référence."))
            
        if not self.invoice_type_id:
            raise ValidationError(_("Veuillez sélectionner un cycle de facturation."))
        
        try:
            # Utiliser le service pour créer le planning
            lot_ids = self.lot_ids.ids if self.lot_ids else None
            
            schedules = self.env['construction.invoice.service'].create_invoice_schedule_for_chantier(
                self.chantier_id.id,
                self.quote_id.id,
                self.invoice_type_id.id,
                lot_ids,
                self.margin_percentage
            )
            
            # Mettre à jour le chantier
            self.chantier_id.write({
                'main_quote_id': self.quote_id.id,
                'invoice_type_id': self.invoice_type_id.id
            })
            
            # Message de succès
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Planning créé'),
                    'message': _('Planning de facturation créé avec {} étapes basées sur le devis {}').format(
                        len(schedules), self.quote_id.name
                    ),
                    'type': 'success'
                }
            }
            
        except Exception as e:
            raise ValidationError(_("Erreur lors de la création du planning: %s") % str(e))

    def action_preview_schedule(self):
        """Prévisualiser le planning de facturation"""
        self.ensure_one()
        
        if not self.quote_id or not self.invoice_type_id:
            raise ValidationError(_("Veuillez sélectionner un devis et un cycle de facturation."))
        
        # Créer un planning temporaire pour la prévisualisation
        lot_ids = self.lot_ids.ids if self.lot_ids else self.chantier_id.lots_ids.ids
        
        try:
            schedules = self.env['construction.invoice.service'].create_invoice_schedule_for_chantier(
                self.chantier_id.id,
                self.quote_id.id,
                self.invoice_type_id.id,
                lot_ids,
                self.margin_percentage
            )
            
            # Ouvrir la vue du planning
            return {
                'type': 'ir.actions.act_window',
                'name': _('Prévisualisation du planning'),
                'res_model': 'construction.invoice.schedule',
                'view_mode': 'list,form',
                'domain': [('id', 'in', schedules.ids)],
                'context': {
                    'default_chantier_id': self.chantier_id.id,
                },
                'target': 'current',
            }
            
        except Exception as e:
            raise ValidationError(_("Erreur lors de la prévisualisation: %s") % str(e))

    @api.model
    def default_get(self, fields_list):
        """Valeurs par défaut depuis le contexte"""
        defaults = super().default_get(fields_list)
        
        # Récupérer le chantier depuis le contexte
        chantier_id = self.env.context.get('default_chantier_id')
        if chantier_id:
            chantier = self.env['construction.chantier'].browse(chantier_id)
            defaults['chantier_id'] = chantier_id
            
            # Proposer le devis principal s'il existe
            if chantier.main_quote_id:
                defaults['quote_id'] = chantier.main_quote_id.id
            
            # Proposer le cycle de facturation s'il existe
            if chantier.invoice_type_id:
                defaults['invoice_type_id'] = chantier.invoice_type_id.id
        
        return defaults 