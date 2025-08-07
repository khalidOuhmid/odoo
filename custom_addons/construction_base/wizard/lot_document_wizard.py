# -*- coding: utf-8 -*-
"""
Wizard de gestion des documents du lot - Version refactorisée
Gère les documents (CCTP, planning) et redirige vers le wizard de génération pour les contrats
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class LotDocumentWizard(models.TransientModel):
    _name = 'lot.document.wizard'
    _description = 'Gestion des documents du lot'

    # =================== CHAMPS PRINCIPAUX ===================

    lot_id = fields.Many2one(
        'construction.lot',
        string='Lot',
        required=True,
        readonly=True
    )

    chantier_id = fields.Many2one(
        'construction.chantier',
        string='Chantier',
        required=True,
        readonly=True
    )

    subcontractor_id = fields.Many2one(
        'res.partner',
        string='Sous-traitant',
        required=True,
        readonly=True
    )

    # =================== DOCUMENTS DU LOT ===================

    document_cctp = fields.Binary(
        string="CCTP",
        attachment=True,
        help="Cahier des Clauses Techniques Particulières"
    )

    document_general_planning = fields.Binary(
        string="Planning général",
        attachment=True,
        help="Planning général du chantier"
    )

    document_subcontractor_planning = fields.Binary(
        string="Planning du sous-traitant",
        attachment=True,
        help="Planning spécifique au sous-traitant"
    )

    # =================== INFORMATIONS COMPUTED ===================

    lot_name = fields.Char(
        string="Nom du lot",
        related="lot_id.name",
        readonly=True
    )

    lot_price = fields.Monetary(
        string="Prix du lot",
        related="lot_id.price",
        currency_field="currency_id",
        readonly=True
    )

    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id
    )

    # =================== ÉTATS DES CONTRATS ===================

    has_active_contract = fields.Boolean(
        string="Contrat actif existant",
        compute="_compute_contract_status",
        help="Indique s'il existe un contrat actif pour ce lot"
    )

    contract_count = fields.Integer(
        string="Nombre de contrats",
        compute="_compute_contract_status",
        help="Nombre total de contrats pour ce lot"
    )

    latest_contract_id = fields.Many2one(
        'construction.subcontractor.contract',
        string="Dernier contrat",
        compute="_compute_contract_status",
        help="Le contrat le plus récent pour ce lot"
    )

    # =================== COMPUTED FIELDS ===================

    @api.depends('lot_id', 'subcontractor_id')
    def _compute_contract_status(self):
        """Calcule le statut des contrats pour ce lot."""
        for wizard in self:
            if wizard.lot_id and wizard.subcontractor_id:
                # Rechercher les contrats existants
                contracts = self.env['construction.subcontractor.contract'].search([
                    ('lot_ids', 'in', [wizard.lot_id.id]),
                    ('subcontractor_id', '=', wizard.subcontractor_id.id),
                ], order='create_date desc')

                wizard.contract_count = len(contracts)
                wizard.latest_contract_id = contracts[0] if contracts else False
                wizard.has_active_contract = any(
                    contract.state in ['signed', 'active'] for contract in contracts
                )
            else:
                wizard.contract_count = 0
                wizard.latest_contract_id = False
                wizard.has_active_contract = False

    # =================== LIFECYCLE ===================

    @api.model
    def default_get(self, fields_list):
        """Initialise les valeurs par défaut du wizard."""
        res = super().default_get(fields_list)

        # Récupérer les IDs depuis le contexte
        lot_id = self.env.context.get('default_lot_id')

        if lot_id:
            lot = self.env['construction.lot'].browse(lot_id)
            subcontractor = lot.subcontractor_ids[0] if lot.subcontractor_ids else False

            res.update({
                'lot_id': lot_id,
                'chantier_id': lot.chantier_id.id,
                'subcontractor_id': subcontractor.id if subcontractor else False,
            })

            # Récupérer les documents existants du lot
            document_fields = [
                'document_cctp',
                'document_general_planning',
                'document_subcontractor_planning'
            ]

            for field in document_fields:
                if hasattr(lot, field) and getattr(lot, field):
                    res[field] = getattr(lot, field)

        return res

    # =================== ACTIONS DOCUMENTS ===================

    def action_save_documents(self):
        """Sauvegarde les documents sur le lot."""
        self.ensure_one()

        vals = {}
        document_fields = [
            'document_cctp',
            'document_general_planning',
            'document_subcontractor_planning'
        ]

        for field in document_fields:
            if getattr(self, field):
                vals[field] = getattr(self, field)

        if vals:
            self.lot_id.write(vals)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Documents sauvegardés'),
                'message': _('Les documents ont été sauvegardés sur le lot.'),
                'type': 'success',
            }
        }

    # =================== ACTIONS CONTRAT - REDIRECTION ===================

    def action_generate_contract_wizard(self):
        """Redirige vers le wizard de génération de contrats."""
        self.ensure_one()

        if not self.subcontractor_id:
            raise ValidationError(_("Aucun sous-traitant assigné à ce lot."))

        # Sauvegarder les documents avant redirection
        self.action_save_documents()

        # Ouvrir le nouveau wizard de génération
        return {
            'type': 'ir.actions.act_window',
            'name': _('Générer contrat pour le lot - %s') % self.lot_id.name,
            'res_model': 'construction.contract.generation.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_chantier_id': self.chantier_id.id,
                'default_subcontractor_id': self.subcontractor_id.id,
                'default_lot_ids': [(6, 0, [self.lot_id.id])],
                'default_total_amount': self.lot_id.price or 0.0,
                'from_lot_wizard': True,
                'source_lot_id': self.lot_id.id,
                'dialog_size': 'extra-large',
            }
        }

    def action_open_contract_generation(self):
        """Alias pour action_generate_contract_wizard."""
        return self.action_generate_contract_wizard()

    # =================== ACTIONS CONTRATS EXISTANTS ===================

    def action_view_contracts(self):
        """Affiche tous les contrats liés à ce lot."""
        self.ensure_one()

        domain = [
            ('lot_ids', 'in', [self.lot_id.id]),
            ('subcontractor_id', '=', self.subcontractor_id.id),
        ]

        return {
            'type': 'ir.actions.act_window',
            'name': _('Contrats pour le lot %s') % self.lot_id.name,
            'res_model': 'construction.subcontractor.contract',
            'view_mode': 'tree,form',
            'domain': domain,
            'context': {
                'default_chantier_id': self.chantier_id.id,
                'default_subcontractor_id': self.subcontractor_id.id,
                'default_lot_ids': [(6, 0, [self.lot_id.id])],
            }
        }

    def action_view_latest_contract(self):
        """Affiche le dernier contrat créé."""
        self.ensure_one()

        if not self.latest_contract_id:
            raise ValidationError(_("Aucun contrat trouvé pour ce lot."))

        return {
            'type': 'ir.actions.act_window',
            'name': f'Contrat - {self.latest_contract_id.contract_number}',
            'res_model': 'construction.subcontractor.contract',
            'res_id': self.latest_contract_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # =================== ACTIONS EMAIL ===================

    def action_send_latest_contract_email(self):
        """Envoie le dernier contrat par email."""
        self.ensure_one()

        if not self.latest_contract_id:
            raise ValidationError(_("Aucun contrat à envoyer."))

        if not self.subcontractor_id.email:
            raise ValidationError(_("Le sous-traitant n'a pas d'adresse email."))

        # Envoyer le contrat via sa propre méthode
        self.latest_contract_id.action_send_contract()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Contrat envoyé'),
                'message': _('Le contrat a été envoyé par email au sous-traitant.'),
                'type': 'success',
            }
        }

    # =================== ACTIONS UTILITY ===================

    def action_view_lot(self):
        """Affiche la fiche du lot."""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': f'Lot - {self.lot_id.name}',
            'res_model': 'construction.lot',
            'res_id': self.lot_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_chantier(self):
        """Affiche la fiche du chantier."""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': f'Chantier - {self.chantier_id.name}',
            'res_model': 'construction.chantier',
            'res_id': self.chantier_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_upload_document(self, doc_type):
        """Action générique pour uploader un document."""
        self.ensure_one()

        # Cette méthode peut être étendue pour gérer l'upload via interface web
        # Pour l'instant, les documents sont gérés via les champs binary
        pass
