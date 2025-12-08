# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)

class ConstructionLot(models.Model):
    """
    RÉFÉRENTIEL LOT (Work Package).
    Unité de gestion technique et financière.
    """
    _name = 'construction.lot'
    _description = 'Lot de Construction'
    _inherit = ['mail.thread', 'mail.activity.mixin', 
                'construction.financial.mixin']
    
    # ==========================
    # IDENTIFICATION
    # ==========================
    name = fields.Char(string='Intitué du Lot', required=True, tracking=True)
    code = fields.Char(string='Code Lot', required=True) # Ex: ELEC, PLOM
    description = fields.Text(string='Description', help="Description détaillée du lot de travaux")
    notes = fields.Text(string='Notes')
    
    chantier_id = fields.Many2one(
        'construction.chantier', 
        string='Chantier', 
        required=True, 
        ondelete='cascade',
        index=True
    )
    
    # ==========================
    # STATUS
    # ==========================
    # Le lot a son propre cycle de vie, souvent plus simple que le chantier
    state = fields.Selection([
        ('draft', 'Étude'),
        ('defined', 'Défini'),
        ('assigned', 'Attribué'),
        ('in_progress', 'En cours'),
        ('done', 'Réceptionné'),
        ('cancel', 'Annulé')
    ], string='Statut', default='draft', tracking=True)

    progress = fields.Float(
        string='Progress (%)',
        default=0.0,
        tracking=True,
        help="Technical completion percentage (0-100)."
    )

    # ==========================
    # DOCUMENTS
    # ==========================
    document_cctp = fields.Binary(string="CCTP", attachment=True)
    document_general_planning = fields.Binary(string="Planning général", attachment=True)
    document_subcontractor_planning = fields.Binary(string="Planning du sous-traitant", attachment=True)

    # ==========================
    # LOGIC
    # ==========================
    price = fields.Monetary(string='Prix estimé', currency_field='currency_id', default=0.0, tracking=True)
    
    @api.onchange('name')
    def _onchange_name_autocode(self):
        """Génère un code par défaut à partir du nom si aucun code."""
        for lot in self:
            if not lot.code and lot.name:
                cleaned = ''.join(ch for ch in lot.name if ch.isalnum())
                lot.code = cleaned[:3].upper() if cleaned else 'GEN'

    _sql_constraints = [
        ('check_progress_range', 'CHECK(progress >= 0 AND progress <= 100)', 
         'Progress must be between 0 and 100.')
    ]

    # ==========================
    # FINANCIAL COMPUTATION
    # ==========================
    def _compute_financial_status(self):
        """
        Compute financial status for the Lot.
        Currently a placeholder for Purchase/Contract integration.
        """
        for lot in self:
            # Future: Aggregate Purchase Orders / Subcontract Contracts
            # committed = sum(lot.purchase_order_ids.mapped('amount_total'))
            lot.committed_amount = 0.0
            lot.realized_amount = 0.0
            
            # Log mainly for debugging in dev, reduce noise in prod unless error
            # _logger.debug("Computed financials for Lot %s", lot.name)
