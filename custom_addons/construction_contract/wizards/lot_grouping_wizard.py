# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class LotGroupingWizard(models.TransientModel):
    _name = 'construction.lot.grouping.wizard'
    _description = 'Wizard de regroupement des lots pour BC'

    target_lot_id = fields.Many2one('construction.lot', string="Lot Initiateur", required=True, readonly=True)
    lot_ids = fields.Many2many('construction.lot', string="Lots à Grouper")
    
    def action_group_po(self):
        """Grouper : Générer un seul BC pour tous les lots sélectionnés."""
        self.ensure_one()
        # On appelle la méthode de génération sur tous les lots avec force_grouping pour éviter la récursion
        return self.lot_ids.with_context(force_grouping=True).action_generate_purchase_order()

    def action_separate_po_only(self):
        """Séparer : Générer le BC uniquement pour le lot actuel (et ignorer les autres)."""
        self.ensure_one()
        # On appelle la méthode uniquement sur le lot cible avec force_grouping
        return self.target_lot_id.with_context(force_grouping=True).action_generate_purchase_order()
