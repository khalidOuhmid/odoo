# -*- coding: utf-8 -*-
"""
Lot management for Construction Projects.
Includes Master Data (Category) and Project Instances (Lot).
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class LotCategory(models.Model):
    """
    Standard definitions of Lots (Master Data).
    Example: 01 - Gros Oeuvre, 02 - Electricité.
    """
    _name = 'construction.lot.category'
    _description = 'Catégorie de Lot'
    _order = 'code, name'

    name = fields.Char(string='Nom', required=True, translate=True)
    code = fields.Char(string='Code', required=True, help="Code unique (ex: 01)")
    urssaf_code = fields.Char(string='Code URSSAF', help="Code URSSAF pour les contrats")
    color = fields.Integer(string='Couleur', default=0)
    
    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Le code de catégorie doit être unique.'),
    ]


class Lot(models.Model):
    """
    A specific Lot instance on a Construction Site (Chantier).
    
    Supports hybrid execution model:
    - External: Subcontractor with PO required
    - Internal: BLG employees with timesheet tracking
    
    Completion is percentage-based (0-100%) and contributes to overall
    chantier progress weighted by lot price.
    """
    _name = 'construction.lot'
    _description = 'Lot de Chantier'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, code, name'

    # ============= Identity ============= #
    category_id = fields.Many2one('construction.lot.category', string='Catégorie Standard')
    name = fields.Char(string='Nom du Lot', required=True, tracking=True)
    code = fields.Char(string='Code', required=True, tracking=True)
    
    chantier_id = fields.Many2one(
        'construction.chantier',
        string='Chantier',
        required=True,
        ondelete='cascade',
        tracking=True
    )

    # ============= EXECUTION MODEL ============= #
    execution_type = fields.Selection([
        ('internal', 'Régie Interne'),
        ('external', 'Sous-Traitance')
    ], string='Type d\'Exécution', default='external', required=True, tracking=True,
       help="Régie Interne: Salariés BLG, Sous-Traitance: Entreprise externe")
    
    subcontractor_id = fields.Many2one(
        'res.partner',
        string='Sous-traitant Principal',
        domain="[('supplier_rank', '>', 0)]",
        tracking=True,
        help="Sous-traitant principal pour ce lot (Sous-Traitance uniquement)"
    )
    
    # Note: Subcontractor compliance fields (subcontractor_compliance_state, 
    # subcontractor_alert_level, subcontractor_doc_warning) are defined in 
    # construction_subcontractor module as they depend on fields from that module.
    
    
    # Note: hr.employee requires 'hr' module - use res.users as fallback
    internal_team_user_ids = fields.Many2many(
        'res.users',
        'construction_lot_internal_team_rel',
        'lot_id', 'user_id',
        string='Équipe Interne',
        help="Utilisateurs BLG affectés à ce lot (Régie Interne)"
    )

    # ============= PLANNING DATES ============= #
    date_start_planned = fields.Date(
        string='Début Lot',
        tracking=True,
        help="Date de début prévue (doit être dans les bornes du chantier)"
    )
    date_end_planned = fields.Date(
        string='Fin Lot',
        tracking=True,
        help="Date de fin prévue (doit être dans les bornes du chantier)"
    )

    # ============= Base Financials ============= #
    currency_id = fields.Many2one(
        'res.currency',
        string='Devise',
        default=lambda self: self.env.company.currency_id,
        required=True
    )
    price = fields.Monetary(
        string='Prix',
        currency_field='currency_id',
        tracking=True,
        help="Prix du lot (calculé à partir des articles du devis)"
    )

    # ============= COMPUTED FINANCIALS ============= #
    cost_total = fields.Monetary(
        string='Coût Total',
        compute='_compute_lot_financials',
        store=True,
        currency_field='currency_id',
        help="Somme des bons de commande confirmés (sans marge)"
    )
    revenue_total = fields.Monetary(
        string='Revenu Total',
        compute='_compute_lot_financials',
        store=True,
        currency_field='currency_id',
        help="Prix facturé au client (avec marge)"
    )
    margin_eur = fields.Monetary(
        string='Marge (€)',
        compute='_compute_lot_financials',
        store=True,
        currency_field='currency_id',
        help="Revenu - Coût"
    )
    margin_percent = fields.Float(
        string='Marge (%)',
        compute='_compute_lot_financials',
        store=True,
        help="(Marge / Revenu) × 100"
    )
    
    # ============= Completion ============= #
    completion_percentage = fields.Float(
        string='Avancement (%)',
        default=0.0,
        tracking=True,
        help="Pourcentage d'avancement du lot (0-100%)"
    )
    is_finished = fields.Boolean(
        string='Terminé',
        compute='_compute_is_finished',
        store=True,
        readonly=False,
        tracking=True
    )
    weighted_value = fields.Monetary(
        string='Valeur pondérée',
        compute='_compute_weighted_value',
        store=True,
        currency_field='currency_id',
        help="Prix × % avancement"
    )
    
    # ============= Organization ============= #
    sequence = fields.Integer(string='Séquence', default=10)
    color = fields.Integer(string='Couleur', default=0)
    description = fields.Text(string='Description')

    # ============= DOCUMENTS ============= #
    # Specific documents as requested
    document_cctp = fields.Binary(string='CCTP', attachment=True)
    document_cctp_filename = fields.Char(string='Nom Fichier CCTP')
    
    document_planning_chantier = fields.Binary(string='Planning Chantier', attachment=True)
    document_planning_chantier_filename = fields.Char(string='Nom Fichier Planning Chantier')
    
    document_planning_sous_traitant = fields.Binary(string='Planning Sous-Traitant', attachment=True)
    document_planning_sous_traitant_filename = fields.Char(string='Nom Fichier Planning ST')

    # Generic documents (kept for extras)
    document_ids = fields.Many2many(
        'ir.attachment',
        'construction_lot_attachment_rel',
        'lot_id', 'attachment_id',
        string='Autres Documents',
        help="Documents supplémentaires"
    )
    document_count = fields.Integer(
        compute='_compute_document_count',
        string='Nombre de Documents'
    )
    
    # ============= Partners (Legacy - kept for compatibility) ============= #
    subcontractor_ids = fields.Many2many(
        'res.partner',
        'construction_lot_subcontractor_rel',
        'lot_id', 'partner_id',
        string='Sous-traitants',
        domain="[('supplier_rank', '>', 0)]",
        tracking=True
    )

    # ============= Constraints ============= #
    _sql_constraints = [
        ('positive_price', 'CHECK(price >= 0)', 'Le prix doit être positif.'),
        ('completion_range', 'CHECK(completion_percentage >= 0 AND completion_percentage <= 100)', 
         'Le pourcentage doit être entre 0 et 100.'),
        ('unique_lot_per_chantier', 'unique(code, chantier_id)', 'Le code du lot doit être unique par chantier.'),
    ]

    # ============= Computes ============= #
    @api.depends('completion_percentage')
    def _compute_is_finished(self):
        for record in self:
            record.is_finished = record.completion_percentage >= 100.0

    @api.depends('price', 'completion_percentage')
    def _compute_weighted_value(self):
        for record in self:
            record.weighted_value = record.price * (record.completion_percentage / 100.0)

    @api.depends('price')
    def _compute_lot_financials(self):
        """Compute cost, revenue, and margin for the lot.
        
        Cost: Sum of confirmed PO lines linked to this lot
        Revenue: Lot price (from quote/sale order)
        Margin: Revenue - Cost
        """
        PurchaseOrderLine = self.env.get('purchase.order.line')
        
        for record in self:
            # Revenue is the lot price (what client pays)
            record.revenue_total = record.price or 0.0
            
            # Cost from Purchase Orders (if module installed)
            cost = 0.0
            if PurchaseOrderLine:
                # Search for PO lines linked to this lot
                po_lines = PurchaseOrderLine.search([
                    ('lot_id', '=', record.id),
                    ('order_id.state', 'in', ['purchase', 'done'])
                ])
                cost = sum(po_lines.mapped('price_subtotal'))
            record.cost_total = cost
            
            # Margin calculations
            record.margin_eur = record.revenue_total - record.cost_total
            if record.revenue_total > 0:
                record.margin_percent = (record.margin_eur / record.revenue_total) * 100
            else:
                record.margin_percent = 0.0

    # ============= Cockpit / Wizard Logic Merged ============= #
    
    planned_cost = fields.Monetary(
        string='Coût Prévu',
        compute='_compute_planned_financials',
        currency_field='currency_id',
        help="Coût théorique calculé depuis les produits du devis"
    )
    planned_margin = fields.Monetary(
        string='Marge Prévue',
        compute='_compute_planned_financials',
        currency_field='currency_id'
    )
    
    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Bon de Commande Principal',
        compute='_compute_related_single_records',
        help="Dernier BC validé pour ce lot"
    )
    contract_id = fields.Many2one(
        'construction.contract',
        string='Contrat Actif',
        compute='_compute_related_single_records',
        help="Contrat principal lié à ce lot"
    )
    
    prerequisites_html = fields.Html(
        string='Prérequis Contrat',
        compute='_compute_prerequisites',
        help="Checklist pour la génération du contrat"
    )
    can_generate_contract = fields.Boolean(
        compute='_compute_prerequisites'
    )
    
    @api.depends('price')
    def _compute_planned_financials(self):
        """Compute theoretical cost/margin from Sale Order lines."""
        SaleOrderLine = self.env['sale.order.line']
        for lot in self:
            cost = 0.0
            # Logic from Wizard: Find SO lines for this lot
            if lot.chantier_id:
                # Find confirmed orders
                sale_orders = self.env['sale.order'].search([
                    ('chantier_id', '=', lot.chantier_id.id),
                    ('state', '=', 'sale')
                ])
                if sale_orders:
                    domain = [('order_id', 'in', sale_orders.ids)]
                    # Try to match by name/code if explicit link missing
                    if 'lot_id' in SaleOrderLine._fields:
                        lines = SaleOrderLine.search(domain + [('lot_id', '=', lot.id)])
                    else:
                        all_lines = SaleOrderLine.search(domain)
                        lines = all_lines.filtered(
                            lambda l: lot.name.lower() in (l.name or '').lower() or 
                                      lot.code in (l.name or '')
                        )
                    
                    for line in lines:
                        if line.product_id:
                            cost += line.product_id.standard_price * line.product_uom_qty
            
            lot.planned_cost = cost
            lot.planned_margin = (lot.price or 0.0) - cost

    def _compute_related_single_records(self):
        """Compute single PO/Contract for Cockpit view convenience."""
        for lot in self:
            # PO
            # PO
            po = self.env['purchase.order']
            if hasattr(lot, 'purchase_order_ids') and lot.purchase_order_ids:
                po = lot.purchase_order_ids.filtered(lambda p: p.state in ['purchase', 'done'])
                if not po:
                    po = lot.purchase_order_ids
            elif self.env['ir.module.module'].search_count([('name', '=', 'purchase'), ('state', '=', 'installed')]):
                 # Fallback search
                 po = self.env['purchase.order'].search([
                    ('lot_ids', 'in', [lot.id]),
                    ('state', 'in', ['purchase', 'done'])
                 ], limit=1)
            
            lot.purchase_order_id = po[0] if po else False
            
            # Contract
            contract = False
            if 'construction.contract' in self.env:
                Contract = self.env['construction.contract']
                if 'lot_ids' in Contract._fields:
                    contract = Contract.search([('lot_ids', 'in', [lot.id])], limit=1)
            lot.contract_id = contract.id if contract else False

    @api.depends('subcontractor_id', 'document_cctp')
    def _compute_prerequisites(self):
        """Checklist logic from Wizard."""
        for lot in self:
            if lot.execution_type != 'external':
                lot.prerequisites_html = ''
                lot.can_generate_contract = False
                continue
            
            checks = []
            all_passed = True
            
            # 1. Subcontractor
            if lot.subcontractor_id:
                checks.append('✅ Sous-traitant assigné')
            else:
                checks.append('❌ Sous-traitant assigné')
                all_passed = False
            
            # 2. PO generated
            has_po = False
            if hasattr(lot, 'purchase_order_ids') and lot.purchase_order_ids:
                has_po = True
            else:
                # Fallback search if field not available/visible
                if self.env['ir.module.module'].search_count([('name', '=', 'purchase'), ('state', '=', 'installed')]):
                    has_po = bool(self.env['purchase.order'].search_count([
                        ('lot_ids', 'in', [lot.id]),
                        ('state', 'in', ['purchase', 'done'])
                    ]))
            
            if has_po:
                checks.append('✅ Bon de commande généré')
            else:
                checks.append('❌ Bon de commande généré')
                all_passed = False
            
            # 3. CCTP
            if lot.document_cctp:
                checks.append('✅ CCTP chargé')
            else:
                checks.append('❌ CCTP chargé')
                all_passed = False
            
            # 4. Planning (Optional/Warning)
            if lot.document_planning_chantier or lot.document_planning_sous_traitant:
                checks.append('✅ Planning chargé')
            else:
                checks.append('⚠️ Planning non chargé (optionnel)')
            
            lot.prerequisites_html = '<br/>'.join(checks)
            lot.can_generate_contract = all_passed


    def _compute_document_count(self):
        """Count attached documents."""
        for record in self:
            record.document_count = len(record.document_ids)

    @api.depends('weighted_value', 'price')
    def _compute_remaining_value(self):
        for record in self:
            record.remaining_value = (record.price or 0.0) - (record.weighted_value or 0.0)

    remaining_value = fields.Monetary(
        string='Valeur Restante',
        compute='_compute_remaining_value',
        store=False,
        currency_field='currency_id',
        help="Prix - Valeur pondérée"
    )

    # ============= Safe Actions for View ============= #

    def action_generate_po_safe(self):
        """Call generation method if available."""
        self.ensure_one()
        if hasattr(self, 'action_generate_purchase_order'):
            return self.action_generate_purchase_order()
        else:
            raise UserError(_("La génération de bon de commande nécessite le module d'achats."))

    def action_generate_contract_safe(self):
        """Call generation method or open wizard."""
        self.ensure_one()
        if hasattr(self, 'action_generate_contract_wizard'):
            return self.action_generate_contract_wizard()
        
        # Fallback if method not found but model might exist
        if 'contract.creation.wizard' in self.env:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Créer Contrat'),
                'res_model': 'contract.creation.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_lot_ids': [(4, self.id)],
                    'default_chantier_id': self.chantier_id.id,
                    'default_subcontractor_id': self.subcontractor_id.id,
                },
            }
        raise UserError(_("La génération de contrat nécessite le module de contrats."))


    # Note: _compute_subcontractor_doc_warning is defined in construction_subcontractor module


    # ============= Onchange ============= #
    @api.onchange('category_id')
    def _onchange_category_id(self):
        if self.category_id:
            self.name = self.category_id.name
            self.code = self.category_id.code

    @api.onchange('is_finished')
    def _onchange_is_finished(self):
        """When manually set to finished, set completion to 100%."""
        if self.is_finished and self.completion_percentage < 100:
            self.completion_percentage = 100.0

    @api.onchange('execution_type')
    def _onchange_execution_type(self):
        """Clear incompatible fields when switching execution type."""
        if self.execution_type == 'internal':
            self.subcontractor_id = False
        else:
            self.internal_team_user_ids = [(5, 0, 0)]  # Clear

    # ============= Constraints ============= #
    @api.constrains('chantier_id', 'code')
    def _check_unique_lot_code(self):
        for record in self:
            existing = self.search([
                ('chantier_id', '=', record.chantier_id.id),
                ('code', '=', record.code),
                ('id', '!=', record.id)
            ])
            if existing:
                raise ValidationError(_(
                    "Un lot avec le code '%s' existe déjà sur ce chantier."
                ) % record.code)

    @api.constrains('completion_percentage')
    def _check_completion_percentage(self):
        for record in self:
            if record.completion_percentage < 0 or record.completion_percentage > 100:
                raise ValidationError(_(
                    "Le pourcentage d'avancement doit être entre 0% et 100%."
                ))

    @api.constrains('date_start_planned', 'date_end_planned', 'chantier_id')
    def _check_lot_dates_within_chantier(self):
        """Validate lot dates are within chantier internal dates."""
        for record in self:
            if not record.chantier_id:
                continue
            
            chantier = record.chantier_id
            
            # Check start date
            if record.date_start_planned and chantier.date_start_internal:
                if record.date_start_planned < chantier.date_start_internal:
                    raise UserError(_(
                        "La date de début du lot (%s) ne peut pas être antérieure "
                        "au début interne du chantier (%s)."
                    ) % (record.date_start_planned, chantier.date_start_internal))
            
            # Check end date
            if record.date_end_planned and chantier.date_end_internal:
                if record.date_end_planned > chantier.date_end_internal:
                    raise UserError(_(
                        "La date de fin du lot (%s) ne peut pas être postérieure "
                        "à la fin interne du chantier (%s)."
                    ) % (record.date_end_planned, chantier.date_end_internal))
            
            # Check order
            if record.date_start_planned and record.date_end_planned:
                if record.date_start_planned > record.date_end_planned:
                    raise ValidationError(_(
                        "La date de fin du lot ne peut pas être avant la date de début."
                    ))

    @api.constrains('execution_type', 'subcontractor_id')
    def _check_execution_type_consistency(self):
        """Validate that external lots have a subcontractor."""
        for record in self:
            if record.execution_type == 'external' and not record.subcontractor_id:
                # Warning only - don't block, just log
                pass  # Subcontractor can be assigned later

    # ============= Helper Methods ============= #
    def _has_validated_po(self):
        """Check if this lot has at least one confirmed Purchase Order."""
        self.ensure_one()
        PurchaseOrder = self.env.get('purchase.order')
        if not PurchaseOrder:
            return False
        return bool(PurchaseOrder.search([
            ('lot_ids', 'in', [self.id]),
            ('state', 'in', ['purchase', 'done'])
        ], limit=1))

    def _get_purchase_orders(self):
        """Get all purchase orders linked to this lot."""
        self.ensure_one()
        PurchaseOrder = self.env.get('purchase.order')
        if not PurchaseOrder:
            return self.env['purchase.order'].browse([])
        return PurchaseOrder.search([('lot_ids', 'in', [self.id])])

    # ============= Actions ============= #
    def action_mark_complete(self):
        """Mark lot as 100% complete."""
        self.ensure_one()
        self.completion_percentage = 100.0
        return True

    def action_open_contract(self):
        """Open the related contract form view."""
        self.ensure_one()
        if not self.contract_id:
            raise UserError(_("Aucun contrat lié à ce lot."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Contrat - %s') % self.contract_id.name,
            'res_model': 'construction.contract',
            'res_id': self.contract_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_purchase_orders(self):
        """Smart button: View Purchase Orders for this lot."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bons de Commande - %s') % self.name,
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('lot_ids', 'in', [self.id])],
            'context': {
                'default_chantier_id': self.chantier_id.id,
                'default_lot_ids': [(6, 0, [self.id])],
            },
        }

    def action_view_documents(self):
        """View attached documents."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Documents - %s') % self.name,
            'res_model': 'ir.attachment',
            'view_mode': 'kanban,list,form',
            'domain': [('id', 'in', self.document_ids.ids)],
            'context': {
                'default_res_model': 'construction.lot',
                'default_res_id': self.id,
            },
        }

    def action_open_lot_cockpit(self):
        """Open the lot detail form (cockpit view)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Gestion Lot - %s') % self.name,
            'res_model': 'construction.lot',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }


