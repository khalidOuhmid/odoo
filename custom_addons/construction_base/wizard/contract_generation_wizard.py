# -*- coding: utf-8 -*-
"""
Wizard de génération avec preview utilisant le template complet
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class ContractGenerationWizard(models.TransientModel):
    _name = 'construction.contract.generation.wizard'
    _description = 'Générateur de contrats avec preview'

    # État du wizard
    current_step = fields.Selection([
        ('config', 'Configuration'),
        ('preview', 'Aperçu'),
        ('finalize', 'Finalisation'),
    ], default='config', string='Étape')

    # Configuration de base
    chantier_id = fields.Many2one('construction.chantier', 'Chantier', required=True)
    subcontractor_id = fields.Many2one('res.partner', 'Sous-traitant', required=True)
    lot_ids = fields.Many2many('construction.lot', 'Lots', required=True,
                               domain="[('chantier_id', '=', chantier_id)]")

    # Conditions contractuelles
    start_date = fields.Date('Date de début', required=True, default=fields.Date.today)
    end_date = fields.Date('Date de fin')
    total_amount = fields.Monetary(
        'Montant total',
        compute='_compute_total_amount',
        store=True,
        readonly=False,
        help="Montant injecté automatiquement depuis le(s) bon(s) d'achat du sous-traitant pour ce chantier et ces lots"
    )
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    payment_terms = fields.Selection([
        ('30_days', '30 jours'),
        ('45_days', '45 jours'),
        ('60_days', '60 jours'),
        ('end_of_work', 'Fin des travaux'),
    ], default='30_days', string='Conditions de paiement')

    warranty_period = fields.Integer('Garantie (mois)', default=12)
    insurance_required = fields.Boolean('Assurance requise', default=True)
    notes = fields.Text('Notes additionnelles')
    
    # Code URSSAF sélectionnable
    urssaf_code = fields.Selection([
        ('41.20Z', '41.20Z - Construction de bâtiments résidentiels et non résidentiels'),
        ('42.11Z', '42.11Z - Construction de routes et autoroutes'),
        ('43.11Z', '43.11Z - Travaux de démolition'),
        ('43.12A', '43.12A - Travaux de terrassement courants et travaux préparatoires'),
        ('43.21A', '43.21A - Travaux d\'installation électrique dans tous locaux'),
        ('43.21B', '43.21B - Travaux d\'installation électrique sur la voie publique'),
        ('43.22A', '43.22A - Travaux d\'installation d\'eau et de gaz en tous locaux'),
        ('43.22B', '43.22B - Travaux d\'installation d\'équipements thermiques et de climatisation'),
        ('43.29A', '43.29A - Travaux d\'isolation'),
        ('43.31Z', '43.31Z - Travaux de plâtrerie'),
        ('43.32A', '43.32A - Travaux de menuiserie bois et PVC'),
        ('43.32B', '43.32B - Travaux de menuiserie métallique et serrurerie'),
        ('43.33Z', '43.33Z - Travaux de revêtement des sols et des murs'),
        ('43.34Z', '43.34Z - Travaux de peinture et vitrerie'),
        ('43.91A', '43.91A - Travaux de charpente'),
        ('43.91B', '43.91B - Travaux de couverture par éléments'),
        ('43.99A', '43.99A - Travaux d\'étanchéification'),
        ('43.99B', '43.99B - Travaux de montage de structures métalliques'),
        ('43.99C', '43.99C - Travaux de maçonnerie générale et gros œuvre de bâtiment'),
        ('43.99D', '43.99D - Autres travaux de construction spécialisés'),
        ('81.22Z', '81.22Z - Autres activités de nettoyage des bâtiments et nettoyage industriel'),
        ('81.30Z', '81.30Z - Services d\'aménagement paysager'),
    ], string='Code URSSAF', default='43.34Z', help="Code URSSAF correspondant au type de travaux")

    # Preview et options
    preview_html = fields.Html('Aperçu HTML', readonly=True)
    preview_ready = fields.Boolean('Aperçu généré', default=False)

    send_email = fields.Boolean('Envoyer par email', default=True)
    auto_send = fields.Boolean('Envoi automatique après signature', default=False)

    # Contrat généré
    generated_contract_id = fields.Many2one('construction.subcontractor.contract',
                                            'Contrat généré', readonly=True)
    generated_contract_number = fields.Char(related='generated_contract_id.contract_number', string="Numéro du contrat")
    generated_contract_state = fields.Selection(related='generated_contract_id.state', string="État du contrat")
    generated_contract_create_date = fields.Datetime(related='generated_contract_id.create_date', string="Date de création")


    @api.depends('chantier_id', 'subcontractor_id', 'lot_ids')
    def _compute_total_amount(self):
        """Calcule automatiquement le montant total pour un ou plusieurs lots.

        Priorité:
        1) Somme des montants des bons d'achat (purchase.order.amount_total)
           liés au chantier, au sous-traitant et aux lots sélectionnés.
        2) Fallback: somme des prix des lots (avec fallback sur price_from_quote si price est nul).
        """
        PurchaseOrder = self.env['purchase.order']
        for wizard in self:
            total = 0.0
            if wizard.chantier_id and wizard.subcontractor_id:
                domain = [
                    ('chantier_id', '=', wizard.chantier_id.id),
                    ('partner_id', '=', wizard.subcontractor_id.id),
                    ('state', 'in', ['purchase', 'done']),
                ]
                purchase_orders = PurchaseOrder.search(domain)
                if wizard.lot_ids:
                    purchase_orders = purchase_orders.filtered(lambda po: bool(po.lot_ids & wizard.lot_ids))

                if purchase_orders:
                    total = sum(purchase_orders.mapped('amount_total'))

            if not total:
                # Fallback sur les lots sélectionnés
                total = 0.0
                for lot in wizard.lot_ids:
                    lot_amount = lot.price if lot.price else getattr(lot, 'price_from_quote', 0.0)
                    total += (lot_amount or 0.0)

            wizard.total_amount = total

    @api.onchange('lot_ids')
    def _onchange_lot_ids(self):
        """Met à jour automatiquement le code URSSAF selon les lots sélectionnés."""
        if self.lot_ids:
            # Pour les lots multiples, essayer de trouver un code URSSAF commun
            urssaf_codes = set()
            for lot in self.lot_ids:
                if hasattr(lot, 'urssaf_code') and lot.urssaf_code:
                    # Extraire juste le code (ex: "43.34Z" depuis "43.34Z - Description")
                    urssaf_code = lot.urssaf_code.split(' - ')[0]
                    urssaf_codes.add(urssaf_code)
            
            if len(urssaf_codes) == 1:
                # Tous les lots ont le même code URSSAF
                self.urssaf_code = list(urssaf_codes)[0]
            elif len(urssaf_codes) > 1:
                # Codes différents - garder le premier ou laisser l'utilisateur choisir
                self.urssaf_code = list(urssaf_codes)[0]
            else:
                # Aucun code trouvé, garder la valeur par défaut
                pass

    @api.onchange('chantier_id')
    def _onchange_chantier_id(self):
        """RAZ des lots quand le chantier change."""
        if self.chantier_id:
            self.lot_ids = [(5, 0, 0)]

    def action_generate_preview(self):
        """Génère l'aperçu HTML avec le template complet."""
        self._validate_configuration()

        try:
            # Utiliser le service pour générer la preview
            contract_service = self.env['construction.contract.service']
            contract_data = self._prepare_contract_data()

            preview_html = contract_service.generate_preview_html(
                self.chantier_id,
                self.subcontractor_id,
                self.lot_ids,
                contract_data
            )

            self.write({
                'current_step': 'preview',
                'preview_html': preview_html,
                'preview_ready': True,
            })

            _logger.info(f"✅ Preview généré pour {self.subcontractor_id.name}")

        except Exception as e:
            _logger.error(f"❌ Erreur génération preview: {e}")
            raise ValidationError(_("Erreur lors de la génération de l'aperçu: %s") % str(e))

        return self._reload_wizard()

    def action_generate_final_contract(self):
        """Génère le contrat final."""
        if not self.preview_ready:
            raise ValidationError(_("Veuillez d'abord générer l'aperçu."))

        try:
            # Générer le contrat via le service
            contract_service = self.env['construction.contract.service']
            contract_data = self._prepare_contract_data()

            contract = contract_service.generate_contract(
                self.chantier_id,
                self.subcontractor_id,
                self.lot_ids,
                contract_data
            )

            self.write({
                'current_step': 'finalize',
                'generated_contract_id': contract.id,
            })

            # Envoyer par email si demandé
            if self.send_email:
                contract.action_send_contract()

            _logger.info(f"✅ Contrat final généré: {contract.contract_number}")

            return {
                'type': 'ir.actions.act_window',
                'name': f'Contrat - {self.subcontractor_id.name}',
                'res_model': 'construction.subcontractor.contract',
                'res_id': contract.id,
                'view_mode': 'form',
                'target': 'current',
            }

        except Exception as e:
            _logger.error(f"❌ Erreur génération contrat final: {e}")
            raise ValidationError(_("Erreur lors de la génération: %s") % str(e))

    def action_back_to_config(self):
        """Retourne à la configuration."""
        self.write({
            'current_step': 'config',
            'preview_ready': False,
            'preview_html': '',
        })
        return self._reload_wizard()

    def action_modify_and_regenerate(self):
        """Modifie et régénère l'aperçu."""
        self.write({
            'preview_ready': False,
            'preview_html': '',
        })
        return self.action_generate_preview()

    def _validate_configuration(self):
        """Valide la configuration avant génération pour un ou plusieurs lots."""
        errors = []

        if not self.chantier_id:
            errors.append("Veuillez sélectionner un chantier.")

        if not self.subcontractor_id:
            errors.append("Veuillez sélectionner un sous-traitant.")

        if not self.lot_ids:
            errors.append("Veuillez sélectionner au moins un lot.")

        # Vérifier que tous les lots appartiennent au même sous-traitant
        if self.lot_ids and self.subcontractor_id:
            for lot in self.lot_ids:
                if self.subcontractor_id not in lot.subcontractor_ids:
                    errors.append(f"Le lot '{lot.name}' n'est pas assigné au sous-traitant '{self.subcontractor_id.name}'.")

        if not self.total_amount or self.total_amount <= 0:
            errors.append("Le montant total doit être supérieur à 0.")

        if not self.subcontractor_id.email and self.send_email:
            errors.append("Le sous-traitant doit avoir une adresse email pour l'envoi automatique.")

        if errors:
            raise ValidationError("\n".join([f"• {error}" for error in errors]))

    def _prepare_contract_data(self):
        """Prépare les données pour le service."""
        return {
            'start_date': self.start_date,
            'end_date': self.end_date,
            'total_amount': self.total_amount,
            'payment_terms': self.payment_terms,
            'warranty_period': self.warranty_period,
            'insurance_required': self.insurance_required,
            'notes': self.notes,
            'send_email': self.send_email,
            'auto_send': self.auto_send,
            'urssaf_code': self.urssaf_code,
        }

    def _reload_wizard(self):
        """Recharge le wizard."""
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': dict(self.env.context, dialog_size='extra-large'),
        }

    @api.model
    def default_get(self, fields_list):
        """Valeurs par défaut depuis le contexte."""
        defaults = super().default_get(fields_list)

        # Récupérer depuis le contexte
        for field in ['chantier_id', 'subcontractor_id', 'lot_ids']:
            context_key = f'default_{field}'
            if context_key in self.env.context:
                defaults[field] = self.env.context[context_key]

        return defaults
