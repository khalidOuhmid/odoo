# -*- coding: utf-8 -*-
"""
Lot Management Wizard

Production-grade wizard for centralized lot management with dynamic UX
adapting to execution mode (Régie Interne / Sous-traitant).
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging

from odoo.addons.construction_core.utils.logger import get_logger

_logger = get_logger(__name__)


class LotManagementWizard(models.TransientModel):
    """
    Wizard de Gestion de Lot
    
    Provides a centralized interface for lot management:
    - Dynamic UX based on execution mode
    - Financial KPIs from sale.order
    - Document management with prerequisites
    - Progress tracking affecting chantier advancement
    """
    _name = 'construction.lot.management.wizard'
    _description = 'Wizard de Gestion de Lot'

    # ============================================================
    # LOT REFERENCE
    # ============================================================
    
    lot_id = fields.Many2one(
        'construction.lot',
        string='Lot',
        required=True,
        readonly=True,
        ondelete='cascade'
    )
    
    chantier_id = fields.Many2one(
        'construction.chantier',
        string='Chantier',
        related='lot_id.chantier_id',
        readonly=True
    )
    
    # ============================================================
    # EXECUTION MODE (KEY UX DRIVER)
    # ============================================================
    
    execution_type = fields.Selection([
        ('internal', 'Régie Interne'),
        ('external', 'Sous-Traitance')
    ], string="Mode de Gestion", required=True,
       help="Conditionne la visibilité des champs du wizard")
    
    # ============================================================
    # ASSIGNMENT SECTION
    # ============================================================
    
    # External mode
    subcontractor_id = fields.Many2one(
        'res.partner',
        string='Sous-traitant',
        domain="[('supplier_rank', '>', 0)]",
        help="Entreprise sous-traitante pour ce lot"
    )
    
    # US-COR-001: Alert for already assigned subcontractor
    is_subcontractor_already_assigned = fields.Boolean(
        compute='_compute_subcontractor_status',
        string='ST déjà assigné'
    )
    
    subcontractor_warning = fields.Html(
        compute='_compute_subcontractor_status',
        string='Avertissement ST'
    )
    
    # Internal mode
    internal_user_id = fields.Many2one(
        'res.users',
        string='Responsable Interne',
        domain="[('share', '=', False)]",
        help="Responsable BLG pour ce lot en régie"
    )
    
    # ============================================================
    # PLANNING SECTION
    # ============================================================
    
    date_start = fields.Date(
        string='Début d\'exécution',
        help="Date de début prévue (doit être dans les bornes du chantier)"
    )
    
    date_end = fields.Date(
        string='Fin d\'exécution',
        help="Date de fin prévue (doit être dans les bornes du chantier)"
    )
    
    # ============================================================
    # FINANCIAL KPIs (Read-Only, Computed from sale.order)
    # ============================================================
    
    currency_id = fields.Many2one(
        'res.currency',
        related='lot_id.currency_id'
    )
    
    lot_sale_price = fields.Monetary(
        string='Prix de Vente',
        compute='_compute_financial_kpis',
        currency_field='currency_id',
        help="Montant total de la section du devis correspondant à ce lot"
    )
    
    lot_cost = fields.Monetary(
        string='Coût de Revient',
        compute='_compute_financial_kpis',
        currency_field='currency_id',
        help="Coût calculé depuis les produits du devis"
    )
    
    lot_margin = fields.Monetary(
        string='Marge Brute',
        compute='_compute_financial_kpis',
        currency_field='currency_id',
        help="Prix de vente - Coût de revient"
    )
    
    lot_margin_percent = fields.Float(
        string='Marge (%)',
        compute='_compute_financial_kpis',
        digits=(5, 2),
        help="(Marge / Prix Vente) × 100"
    )
    
    # ============================================================
    # DOCUMENTS SECTION
    # ============================================================
    
    cctp_file = fields.Binary(
        string='CCTP',
        help="Cahier des Clauses Techniques Particulières"
    )
    cctp_file_filename = fields.Char(string='Nom CCTP')
    
    project_planning_file = fields.Binary(
        string='Planning Chantier',
        help="Planning général du chantier"
    )
    project_planning_filename = fields.Char(string='Nom Planning Chantier')
    
    subcontractor_planning_file = fields.Binary(
        string='Planning Sous-Traitant',
        help="Planning spécifique du sous-traitant"
    )
    subcontractor_planning_filename = fields.Char(string='Nom Planning ST')
    
    other_files = fields.Many2many(
        'ir.attachment',
        string='Autres Documents',
        help="Documents complémentaires"
    )
    
    # ============================================================
    # PURCHASE ORDER & CONTRACT
    # ============================================================
    
    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Bon de Commande',
        compute='_compute_related_records',
        help="Bon de commande généré pour ce lot"
    )
    
    contract_id = fields.Many2one(
        'construction.contract',
        string='Contrat',
        compute='_compute_related_records',
        help="Contrat de sous-traitance généré"
    )
    
    prerequisites_html = fields.Html(
        string='Prérequis Contrat',
        compute='_compute_prerequisites',
        help="Liste des conditions à remplir pour générer le contrat"
    )
    
    can_generate_contract = fields.Boolean(
        string='Peut Générer Contrat',
        compute='_compute_prerequisites',
        help="Indique si toutes les conditions sont remplies"
    )
    
    # ============================================================
    # PROGRESS SECTION
    # ============================================================
    
    progress_percentage = fields.Float(
        string='Avancement (%)',
        help="Pourcentage de réalisation indexé sur la valeur facturable"
    )
    
    completed_value = fields.Monetary(
        string='Valeur Réalisée',
        compute='_compute_progress_values',
        currency_field='currency_id',
        help="lot_sale_price × progress / 100"
    )
    
    remaining_value = fields.Monetary(
        string='Valeur Restante',
        compute='_compute_progress_values',
        currency_field='currency_id',
        help="Valeur restante à réaliser"
    )
    
    # US-COR-005: Over-billing detection
    is_over_billed = fields.Boolean(
        string='Surfacturation',
        compute='_compute_progress_values',
        help="True si avancement > 100%"
    )
    
    # ============================================================
    # NOTES
    # ============================================================
    
    notes = fields.Html(
        string='Notes',
        help="Notes et commentaires structurés concernant le lot"
    )
    
    # ============================================================
    # DEFAULT VALUES
    # ============================================================
    
    @api.model
    def default_get(self, fields_list):
        """Load current lot values into wizard."""
        res = super().default_get(fields_list)
        
        lot_id = self.env.context.get('active_id')
        if lot_id and self.env.context.get('active_model') == 'construction.lot':
            lot = self.env['construction.lot'].browse(lot_id)
            res.update({
                'lot_id': lot.id,
                'execution_type': lot.execution_type,
                'subcontractor_id': lot.subcontractor_id.id if lot.subcontractor_id else False,
                'internal_user_id': lot.internal_team_user_ids[0].id if lot.internal_team_user_ids else False,
                'date_start': lot.date_start_planned,
                'date_end': lot.date_end_planned,
                'progress_percentage': lot.completion_percentage,
                'cctp_file': lot.document_cctp,
                'cctp_file_filename': lot.document_cctp_filename,
                'project_planning_file': lot.document_planning_chantier,
                'project_planning_filename': lot.document_planning_chantier_filename,
                'subcontractor_planning_file': lot.document_planning_sous_traitant,
                'subcontractor_planning_filename': lot.document_planning_sous_traitant_filename,
                'notes': lot.description,
            })
        
        return res
    
    # ============================================================
    # COMPUTED METHODS
    # ============================================================
    
    @api.depends('lot_id')
    def _compute_financial_kpis(self):
        """
        Compute financial KPIs from sale.order lines.
        
        Revenue: Sum of sale.order.line linked to this lot
        Cost: Sum of cost prices from sale.order.line products
        Margin: Revenue - Cost
        """
        for wizard in self:
            lot = wizard.lot_id
            if not lot:
                wizard.lot_sale_price = 0.0
                wizard.lot_cost = 0.0
                wizard.lot_margin = 0.0
                continue
            
            # Get validated sale orders for this chantier
            sale_orders = self.env['sale.order'].search([
                ('chantier_id', '=', lot.chantier_id.id),
                ('state', '=', 'sale')
            ])
            
            sale_price = 0.0
            cost = 0.0
            
            # Search for sale order lines linked to this lot
            if sale_orders:
                # Try to find lines by lot_id first
                sol_domain = [
                    ('order_id', 'in', sale_orders.ids),
                ]
                
                # Check if lot_id field exists on sale.order.line
                SaleOrderLine = self.env['sale.order.line']
                if 'lot_id' in SaleOrderLine._fields:
                    sol_domain.append(('lot_id', '=', lot.id))
                    lines = SaleOrderLine.search(sol_domain)
                else:
                    # Fallback: use lot name matching in description or product
                    lines = SaleOrderLine.search(sol_domain)
                    lines = lines.filtered(
                        lambda l: lot.name.lower() in (l.name or '').lower() or
                                  lot.code in (l.name or '')
                    )
                
                for line in lines:
                    sale_price += line.price_subtotal
                    # Cost from product standard_price
                    if line.product_id:
                        cost += line.product_id.standard_price * line.product_uom_qty
            
            # Fallback to lot.price if no sale order lines found
            if sale_price == 0.0:
                sale_price = lot.price or 0.0
            
            wizard.lot_sale_price = sale_price
            wizard.lot_cost = cost
            wizard.lot_margin = sale_price - cost
            
            # Calculate margin percentage
            if sale_price > 0:
                wizard.lot_margin_percent = ((sale_price - cost) / sale_price) * 100
            else:
                wizard.lot_margin_percent = 0.0
            
            # US-COR-011: Log critical if negative margin
            if wizard.lot_margin < 0:
                _logger.critical(
                    "[LOGGER][CRITICAL][construction.lot] Lot %s: MARGE NEGATIVE %.2f EUR (%.1f%%)",
                    lot.code if lot else "N/A", wizard.lot_margin, wizard.lot_margin_percent
                )
    
    @api.depends('lot_id', 'subcontractor_id')
    def _compute_subcontractor_status(self):
        """
        US-COR-001: Check if subcontractor is already assigned.
        Generates warning HTML if reassignment attempted.
        """
        for wizard in self:
            lot = wizard.lot_id
            original_st = lot.subcontractor_id if lot else False
            
            # Check if there's already an assigned ST on the lot
            if original_st and wizard.subcontractor_id != original_st:
                wizard.is_subcontractor_already_assigned = True
                wizard.subcontractor_warning = _(
                    '<div class="alert alert-warning">'
                    '<i class="fa fa-exclamation-triangle me-2"></i>'
                    '<strong>Attention:</strong> Le sous-traitant <b>%s</b> est déjà assigné. '
                    'Modifier cette assignation peut impacter les BC et contrats existants.'
                    '</div>'
                ) % original_st.name
            elif original_st:
                wizard.is_subcontractor_already_assigned = True
                wizard.subcontractor_warning = False
            else:
                wizard.is_subcontractor_already_assigned = False
                wizard.subcontractor_warning = False

    @api.depends('lot_id')
    def _compute_related_records(self):
        """Find related PO and Contract for this lot."""
        PurchaseOrder = self.env['purchase.order']
        
        for wizard in self:
            # Initialize with empty recordsets
            wizard.purchase_order_id = PurchaseOrder.browse()
            wizard.contract_id = False
            
            lot = wizard.lot_id
            if not lot:
                continue
            
            # Find PO linked to this lot
            try:
                if 'lot_id' in PurchaseOrder._fields:
                    po = PurchaseOrder.search([
                        ('lot_id', '=', lot.id),
                        ('state', 'in', ['purchase', 'done'])
                    ], limit=1)
                    if po:
                        wizard.purchase_order_id = po
                else:
                    # Search via PO lines
                    POLine = self.env['purchase.order.line']
                    if 'lot_id' in POLine._fields:
                        po_lines = POLine.search([('lot_id', '=', lot.id)])
                        if po_lines:
                            po = po_lines.mapped('order_id').filtered(
                                lambda p: p.state in ['purchase', 'done']
                            )
                            if po:
                                wizard.purchase_order_id = po[0]
            except Exception as e:
                _logger.warning("Error finding PO for lot %s: %s", lot.id, e)
            
            # Find Contract linked to this lot (if module installed)
            try:
                if 'construction.contract' in self.env:
                    Contract = self.env['construction.contract']
                    if 'lot_ids' in Contract._fields:
                        contract = Contract.search([
                            ('lot_ids', 'in', [lot.id])
                        ], limit=1)
                        if contract:
                            wizard.contract_id = contract.id
            except Exception as e:
                _logger.warning("Error finding contract for lot %s: %s", lot.id, e)
    
    @api.depends('lot_id', 'subcontractor_id', 'cctp_file', 'purchase_order_id')
    def _compute_prerequisites(self):
        """
        Compute prerequisites checklist HTML and enabled state.
        
        Conditions:
        - Subcontractor assigned (✓/✗)
        - PO generated (✓/✗)
        - CCTP uploaded (✓/✗)
        - Planning uploaded (✓/✗)
        """
        for wizard in self:
            if wizard.execution_type != 'external':
                wizard.prerequisites_html = ''
                wizard.can_generate_contract = False
                continue
            
            checks = []
            all_passed = True
            
            # 1. Subcontractor
            if wizard.subcontractor_id:
                checks.append('✅ Sous-traitant assigné')
            else:
                checks.append('❌ Sous-traitant assigné')
                all_passed = False
            
            # 2. PO generated
            if wizard.purchase_order_id:
                checks.append('✅ Bon de commande généré')
            else:
                checks.append('❌ Bon de commande généré')
                all_passed = False
            
            # 3. CCTP uploaded
            if wizard.cctp_file:
                checks.append('✅ CCTP chargé')
            else:
                checks.append('❌ CCTP chargé')
                all_passed = False
            
            # 4. Planning uploaded
            if wizard.project_planning_file or wizard.subcontractor_planning_file:
                checks.append('✅ Planning chargé')
            else:
                checks.append('⚠️ Planning non chargé (optionnel)')
            
            wizard.prerequisites_html = '<br/>'.join(checks)
            wizard.can_generate_contract = all_passed
    
    @api.depends('lot_sale_price', 'progress_percentage')
    def _compute_progress_values(self):
        """Compute realized and remaining values based on progress.
        
        US-COR-005: Also detect over-billing (>100%) with CRITICAL logging.
        """
        for wizard in self:
            progress = wizard.progress_percentage or 0.0
            sale_price = wizard.lot_sale_price or 0.0
            
            wizard.completed_value = sale_price * progress / 100.0
            wizard.remaining_value = sale_price - wizard.completed_value
            
            # US-COR-005: Over-billing detection
            wizard.is_over_billed = progress > 100.0
            if wizard.is_over_billed and wizard.lot_id:
                _logger.critical(
                    "[LOGGER][CRITICAL][construction.progress] Lot %s: SURFACTURATION %.1f%% (>100%%)",
                    wizard.lot_id.code, progress
                )
    
    # ============================================================
    # CONSTRAINTS
    # ============================================================
    
    @api.constrains('date_start', 'date_end')
    def _check_dates_within_chantier(self):
        """Validate dates are within chantier bounds."""
        for wizard in self:
            if not wizard.chantier_id:
                continue
            
            chantier = wizard.chantier_id
            chantier_start = getattr(chantier, 'date_start_internal', None) or getattr(chantier, 'date_start', None)
            chantier_end = getattr(chantier, 'date_end_internal', None) or getattr(chantier, 'date_end', None)
            
            if wizard.date_start and chantier_start and wizard.date_start < chantier_start:
                raise ValidationError(_(
                    "La date de début du lot (%s) ne peut pas être antérieure "
                    "à la date de début du chantier (%s)."
                ) % (wizard.date_start, chantier_start))
            
            if wizard.date_end and chantier_end and wizard.date_end > chantier_end:
                raise ValidationError(_(
                    "La date de fin du lot (%s) ne peut pas être postérieure "
                    "à la date de fin du chantier (%s)."
                ) % (wizard.date_end, chantier_end))
            
            if wizard.date_start and wizard.date_end and wizard.date_start > wizard.date_end:
                raise ValidationError(_(
                    "La date de début (%s) doit être antérieure à la date de fin (%s)."
                ) % (wizard.date_start, wizard.date_end))
    
    # ============================================================
    # ACTIONS
    # ============================================================
    
    def action_save(self):
        """Save wizard values back to the lot."""
        self.ensure_one()
        
        lot = self.lot_id
        vals = {
            'execution_type': self.execution_type,
            'date_start_planned': self.date_start,
            'date_end_planned': self.date_end,
            'completion_percentage': self.progress_percentage,
            'description': self.notes,
        }
        
        # Execution-specific fields
        if self.execution_type == 'external':
            vals['subcontractor_id'] = self.subcontractor_id.id if self.subcontractor_id else False
            vals['internal_team_user_ids'] = [(5, 0, 0)]  # Clear internal team
        else:
            vals['subcontractor_id'] = False
            if self.internal_user_id:
                vals['internal_team_user_ids'] = [(6, 0, [self.internal_user_id.id])]
        
        # Documents
        if self.cctp_file:
            vals['document_cctp'] = self.cctp_file
            vals['document_cctp_filename'] = self.cctp_file_filename
        if self.project_planning_file:
            vals['document_planning_chantier'] = self.project_planning_file
            vals['document_planning_chantier_filename'] = self.project_planning_filename
        if self.subcontractor_planning_file:
            vals['document_planning_sous_traitant'] = self.subcontractor_planning_file
            vals['document_planning_sous_traitant_filename'] = self.subcontractor_planning_filename
        
        lot.write(vals)
        
        # Log in chatter
        lot.message_post(
            body=_("📋 Lot mis à jour via le wizard de gestion (Avancement: %s%%)") % int(self.progress_percentage),
            message_type='notification'
        )
        
        return {'type': 'ir.actions.act_window_close'}
    
    def action_generate_po(self):
        """Generate Purchase Order for external lot.
        
        MULTI-LOT INTELLIGENCE: If other lots on the same chantier have the same
        subcontractor, offer to group them into a single PO.
        """
        self.ensure_one()
        
        if self.execution_type != 'external':
            raise UserError(_("La génération de bon de commande n'est disponible que pour les lots en sous-traitance."))
        
        if not self.subcontractor_id:
            raise UserError(_("Veuillez d'abord assigner un sous-traitant."))
        
        # Save current values first
        self.action_save()
        
        lot = self.lot_id
        
        # MULTI-LOT DETECTION: Check for other lots with same subcontractor
        if not self.env.context.get('force_grouping'):
            other_lots = self.env['construction.lot'].search([
                ('chantier_id', '=', lot.chantier_id.id),
                ('subcontractor_id', '=', self.subcontractor_id.id),
                ('execution_type', '=', 'external'),
                ('id', '!=', lot.id)
            ])
            
            if other_lots:
                # Open grouping wizard
                all_lot_ids = (lot | other_lots).ids
                return {
                    'name': _('Lots Multiples Détectés'),
                    'type': 'ir.actions.act_window',
                    'res_model': 'construction.lot.grouping.wizard',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {
                        'default_target_lot_id': lot.id,
                        'default_lot_ids': [(6, 0, all_lot_ids)],
                    }
                }
        
        # No other lots or forced - proceed with single lot generation
        if hasattr(lot, 'action_generate_purchase_order'):
            return lot.with_context(force_grouping=True).action_generate_purchase_order()
        else:
            raise UserError(_("La méthode de génération de bon de commande n'est pas disponible."))
    
    def action_generate_contract(self):
        """Delegate contract generation to construction_contract module."""
        self.ensure_one()
        
        if not self.can_generate_contract:
            raise UserError(_("Toutes les conditions préalables ne sont pas remplies."))
        
        # Save current values first
        self.action_save()
        
        # Call lot's contract generation method if available
        lot = self.lot_id
        if hasattr(lot, 'action_generate_contract_wizard'):
            return lot.action_generate_contract_wizard()
        else:
            # Fallback: open contract creation wizard
            return {
                'type': 'ir.actions.act_window',
                'name': _('Créer Contrat'),
                'res_model': 'contract.creation.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_lot_ids': [(4, lot.id)],
                    'default_chantier_id': lot.chantier_id.id,
                    'default_subcontractor_id': self.subcontractor_id.id,
                },
            }
