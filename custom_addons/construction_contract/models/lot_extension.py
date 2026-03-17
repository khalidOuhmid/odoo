# -*- coding: utf-8 -*-
"""
Lot Extension for Contract Module
=================================
Extends ``construction.lot`` to add contract linking and
purchase-order generation from validated sale-order lines.
"""
from odoo import models, fields, api, _


class Lot(models.Model):
    """Extend construction.lot with contract and purchase-order capabilities."""

    _inherit = 'construction.lot'

    # Un lot appartient à UN SEUL contrat (Many2one)
    # Le contrat a PLUSIEURS lots (One2many inverse)
    contract_id = fields.Many2one(
        'construction.contract',
        string='Contrat',
        ondelete='set null',
        tracking=True,
        help="Contrat de sous-traitance lié à ce lot"
    )
    
    has_contract = fields.Boolean(
        compute='_compute_has_contract',
        store=True,
        string='A un Contrat'
    )

    # TASK-008: Purchase orders linked to this lot
    purchase_order_ids = fields.Many2many(
        'purchase.order',
        compute='_compute_purchase_orders',
        string='Bons de Commande',
        help="Purchase orders linked to this lot via lot_ids",
    )

    purchase_order_count = fields.Integer(
        compute='_compute_purchase_orders',
        string='Nb BC',
    )

    purchase_order_state = fields.Selection([
        ('none', 'Aucun BC'),
        ('pending', 'BC en attente de validation'),
        ('validated', 'BC Validé')
    ], string='État BC', compute='_compute_purchase_order_state', store=False)

    contract_status = fields.Selection([
        ('none', 'Non généré'),
        ('draft', 'Brouillon'),
        ('sent', 'Envoyé'),
        ('signed', 'Signé')
    ], string='État Contrat', compute='_compute_contract_status', store=False)

    contract_name = fields.Char(related='contract_id.name', string='Nom du Contrat', readonly=True)
    contract_date = fields.Date(related='contract_id.date', string='Date de Génération', readonly=True)

    # Prerequisite Checklist Fields
    has_subcontractor = fields.Boolean(compute='_compute_contract_prerequisites')
    has_validated_po = fields.Boolean(compute='_compute_contract_prerequisites')
    is_external_execution = fields.Boolean(compute='_compute_contract_prerequisites')
    all_prerequisites_met = fields.Boolean(compute='_compute_contract_prerequisites')

    @api.depends('contract_id')
    def _compute_has_contract(self):
        for record in self:
            record.has_contract = bool(record.contract_id)

    def _compute_purchase_orders(self):
        """TASK-008: Compute purchase orders related to each lot."""
        for lot in self:
            pos = self.env['purchase.order'].search([
                ('lot_ids', 'in', lot.ids),
            ])
            lot.purchase_order_ids = pos
            lot.purchase_order_count = len(pos)

    @api.depends('purchase_order_ids', 'purchase_order_ids.state')
    def _compute_purchase_order_state(self):
        for lot in self:
            if not lot.purchase_order_ids:
                lot.purchase_order_state = 'none'
            elif any(po.state in ('purchase', 'done') for po in lot.purchase_order_ids):
                lot.purchase_order_state = 'validated'
            else:
                lot.purchase_order_state = 'pending'

    @api.depends('contract_id', 'contract_id.state')
    def _compute_contract_status(self):
        for lot in self:
            if not lot.contract_id:
                lot.contract_status = 'none'
            else:
                lot.contract_status = lot.contract_id.state

    @api.depends('subcontractor_id', 'execution_type', 'purchase_order_ids.state')
    def _compute_contract_prerequisites(self):
        for lot in self:
            lot.has_subcontractor = bool(lot.subcontractor_id)
            lot.is_external_execution = lot.execution_type == 'external'
            lot.has_validated_po = any(po.state in ('purchase', 'done') for po in lot.purchase_order_ids)
            
            lot.all_prerequisites_met = (
                lot.has_subcontractor and 
                lot.is_external_execution and 
                lot.has_validated_po
            )

    def action_view_purchase_orders(self):
        """TASK-008: Smart button action to view related purchase orders."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bons de Commande — %s') % self.name,
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.purchase_order_ids.ids)],
            'context': {'default_lot_ids': [(6, 0, [self.id])]},
        }

    def action_generate_contract_wizard(self):
        """
        Create contract directly (no wizard) and open GrapeJS editor.
        Uses sensible defaults from the lot data.
        
        CRITICAL: Validates prerequisites BEFORE creating contract to avoid orphans.
        """
        self.ensure_one()
        
        if self.contract_id:
            # Already has contract - just open editor
            return self.contract_id.action_open_contract_editor()
        
        if not self.subcontractor_id:
            raise models.UserError(_( 
                "Ce lot n'a pas de sous-traitant assigné. "
                "Veuillez d'abord sélectionner un sous-traitant."
            ))
        
        # Get default template
        template = self.env.ref(
            'construction_contract.default_contract_template',
            raise_if_not_found=False
        ) or self.env['construction.contract.template'].search([('is_default', '=', True)], limit=1)
        
        if not template:
            raise models.UserError(_("Aucun modèle de contrat par défaut configuré."))
        
        # Auto-detect related lots for same subcontractor on this chantier
        related_lots = self.env['construction.lot'].search([
            ('chantier_id', '=', self.chantier_id.id),
            ('subcontractor_id', '=', self.subcontractor_id.id),
            ('execution_type', '=', 'external'),
            ('contract_id', '=', False),
        ])
        
        # Assign ALL related lots to this contract (multi-lot aggregation)
        all_lots = related_lots | self
        
        # =====================================================
        # VALIDATION BEFORE CONTRACT CREATION (no orphans!)
        # =====================================================
        if not self.env.context.get('force_contract_validation'):
            missing = []
            
            # PO Validated per lot
            for lot in all_lots:
                po = self.env['purchase.order'].search([
                    ('lot_ids', 'in', lot.id),
                    ('state', 'in', ['purchase', 'done'])
                ], limit=1)
                if not po:
                    missing.append(f"• Bon de Commande validé pour le lot {lot.code}")

            if missing:
                # Return validation wizard WITHOUT creating contract
                return {
                    'name': _('Documents Manquants'),
                    'type': 'ir.actions.act_window',
                    'res_model': 'construction.contract.validation.wizard',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {
                        'default_lot_id': self.id,
                        'default_missing_items': '<br/>'.join(missing)
                    }
                }
        
        # =====================================================
        # ALL VALIDATIONS PASSED - CREATE CONTRACT
        # =====================================================
        contract = self.env['construction.contract'].create({
            'chantier_id': self.chantier_id.id,
            'subcontractor_id': self.subcontractor_id.id,
            'template_id': template.id,
            'start_date': self.date_start_planned or fields.Date.today(),
            'end_date': self.date_end_planned or fields.Date.today(),
            'retention_rate': 5.0,  # Default 5%
        })
        
        # Assign lots to contract
        all_lots.write({'contract_id': contract.id})

        # AGGREGATION: Collect Purchase Orders from all related lots
        linked_pos = self.env['purchase.order'].search([
            ('lot_ids', 'in', all_lots.ids),
            ('partner_id', '=', self.subcontractor_id.id),
            ('state', 'in', ['purchase', 'done'])
        ])
        if linked_pos and 'purchase_order_ids' in contract._fields:
            contract.write({'purchase_order_ids': [(6, 0, linked_pos.ids)]})
        
        # Generate contract HTML (prefill template)
        contract.action_generate_contract_html()
        
        # Open GrapeJS editor directly
        return contract.action_open_contract_editor()

    def action_view_contract(self):
        """Smart button to view the related contract."""
        self.ensure_one()
        if not self.contract_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'name': _('Contrat - %s') % self.name,
            'res_model': 'construction.contract',
            'res_id': self.contract_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_contract_editor(self):
        """Wrapper to open the contract editor from the lot view."""
        self.ensure_one()
        if not self.contract_id:
            raise UserError(_("Aucun contrat n'est encore lié à ce lot."))
        return self.contract_id.action_open_contract_editor()


    def action_generate_purchase_order(self):
        """
        Generate Purchase Order for Lot(s) subcontractor based on validated quotes.
        
        Bug Fix #7:
        - Handle multiple lots selected (Grouped PO)
        - Filter quote lines strictly by Lot ID
        - Validate total BC amount <= Lot Margin
        """
        from odoo.tools import float_compare, float_is_zero
        
        # self contains 1 or more lots
        if not self:
            return

        # INTERCEPTION: Check for Multi-Lot Grouping Opportunity (Fix 3)
        # Only check if triggered for a single lot and not already forced
        if len(self) == 1 and not self.env.context.get('force_grouping'):
            current_lot = self[0]
            if current_lot.execution_type == 'external' and current_lot.subcontractor_id:
                # Find other lots for same subcontractor on same chantier
                other_lots = self.search([
                    ('chantier_id', '=', current_lot.chantier_id.id),
                    ('subcontractor_id', '=', current_lot.subcontractor_id.id),
                    ('execution_type', '=', 'external'),
                    ('id', '!=', current_lot.id),
                    # Optimization: logic check if PO already exists? 
                    # User says "Intercepte... existe-t-il d'autres lots". 
                    # Assuming we should flag even if they have POs? No, "Générer BC" implies new ones.
                    # But checking PO existence is complex (many2many). 
                    # Let's keep it simple: any other lot for this sub.
                ])
                if other_lots:
                    # Open Wizard
                    return {
                        'name': _('Regroupement de Lots'),
                        'type': 'ir.actions.act_window',
                        'res_model': 'construction.lot.grouping.wizard',
                        'view_mode': 'form',
                        'target': 'new',
                        'context': {
                            'default_target_lot_id': current_lot.id,
                            'default_lot_ids': (current_lot | other_lots).ids,
                        }
                    }

        first_lot = self[0]
        # Validate consistencies strictly
        subcontractor = first_lot.subcontractor_id
        if not subcontractor:
            raise models.UserError(_("Le premier lot sélectionné n'a pas de sous-traitant."))
            
        chantier = first_lot.chantier_id
        
        for lot in self:
            if lot.execution_type == 'internal':
                raise models.UserError(_("Impossible de générer un BC pour le lot '%s' (Régie Interne).") % lot.name)
            if lot.subcontractor_id != subcontractor:
                raise models.UserError(_("Tous les lots sélectionnés doivent avoir le même sous-traitant (%s).") % subcontractor.name)
            if lot.chantier_id != chantier:
                raise models.UserError(_("Tous les lots doivent appartenir au même chantier."))

        # 2. Source Quotes Selection (Validated quotes for this chantier)
        source_orders = self.env['sale.order'].search([
            ('chantier_id', '=', chantier.id),
            ('state', '=', 'sale')
        ])
        if not source_orders:
            raise models.UserError(_("Aucun devis validé trouvé pour ce chantier."))

        # Atomic Transaction
        PurchaseOrder = self.env['purchase.order']
        PurchaseOrderLine = self.env['purchase.order.line']
        currency = first_lot.currency_id
        
        created_po = False
        
        with self.env.cr.savepoint():
            # US-COR-012: Generate PO Name following nomenclature
            # Format: [CHANTIER]-[LOT1+LOT2]-[SOUS_TRAITANT]
            chantier_name = (chantier.name or 'CHANTIER').replace(' ', '-').upper()[:15]
            lot_codes = '+'.join(self.mapped('code'))
            st_name = (subcontractor.name or 'ST').replace(' ', '-').upper()[:10]
            po_name = f"{chantier_name}-{lot_codes}-{st_name}"
            
            # Create PO Header
            po_vals = {
                'name': po_name,  # US-COR-012 Nomenclature
                'partner_id': subcontractor.id,
                'origin': _("Chantier %s - Lots: %s") % (chantier.name, ', '.join(self.mapped('code'))),
                'chantier_id': chantier.id,
                'lot_ids': [(6, 0, self.ids)],
                'date_order': fields.Date.today(),
                'company_id': self.env.company.id,
                'currency_id': currency.id,
            }
            created_po = PurchaseOrder.create(po_vals)
            
            total_po_amount = 0.0
            
            # Iterate lots to group lines
            for lot in self:
                # Filter lines strictly for this lot
                source_lines = self.env['sale.order.line'].search([
                    ('order_id', 'in', source_orders.ids),
                    ('lot_id', '=', lot.id),
                    ('display_type', '=', False),
                    ('product_uom_qty', '>', 0)
                ])
                
                if not source_lines:
                    # Skip or Warn? Warn better
                    # raise models.UserError(_("Aucune ligne de vente trouvée pour le lot '%s'.") % lot.name)
                    continue
                
                # Add Section Header (display_type lines still need product_qty in Odoo 18)
                PurchaseOrderLine.create({
                    'order_id': created_po.id,
                    'display_type': 'line_section',
                    'name': f"=== Lot {lot.code} : {lot.name} ===",
                    'product_qty': 0.0,  # Required even for section lines
                })
                
                lot_cost_accumulated = 0.0
                
                for sol in source_lines:
                    price_unit = sol.price_buy
                    qty = sol.product_uom_qty or 1.0  # Ensure never None or 0
                    
                    # Sanity: if price_buy is 0, maybe use standard_price?
                    if float_is_zero(price_unit, precision_digits=currency.decimal_places):
                         price_unit = sol.product_id.standard_price
                    
                    # Ensure qty is at least 1.0 (mandatory field validation)
                    if not qty or qty <= 0:
                        qty = 1.0
                    
                    # Create PO Line
                    pol_vals = {
                        'order_id': created_po.id,
                        'name': sol.name or sol.product_id.name or 'Produit',
                        'product_id': sol.product_id.id,
                        'product_qty': qty,  # CRITICAL: Must be > 0
                        'product_uom': sol.product_uom.id,
                        'price_unit': price_unit,
                        'taxes_id': [(6, 0, sol.product_id.supplier_taxes_id.ids)],
                        'lot_id': lot.id,
                    }
                    PurchaseOrderLine.create(pol_vals)
                    lot_cost_accumulated += (price_unit * qty)

                # Validate: PO amount must not exceed the lot sell price
                # (guaranteed-loss detection).
                if lot.price and lot_cost_accumulated > lot.price:
                     raise models.UserError(
                         _("CRITIQUE: Le montant du BC pour le lot '%(lot)s' (%(cost)s) dépasse le prix de vente (%(price)s) !") 
                         % {'lot': lot.name, 'cost': lot_cost_accumulated, 'price': lot.price}
                     )
                     
            
            # Recompute totals for PO
            # created_po.button_dummy() 

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'res_id': created_po.id,
            'view_mode': 'form',
            'target': 'current',
        }
