# -*- coding: utf-8 -*-
"""
Wizard de gestion des documents du lot - Version refactorisée
Gère les documents (CCTP, plannings, etc.) associés au lot
"""

from odoo import models, fields, api, _
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
        required=False,
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
