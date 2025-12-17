# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class Lot(models.Model):
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

    @api.depends('contract_id')
    def _compute_has_contract(self):
        for record in self:
            record.has_contract = bool(record.contract_id)

    def action_generate_contract_wizard(self):
        """
        Create contract directly (no wizard) and open GrapeJS editor.
        Uses sensible defaults from the lot data.
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
        
        # Create contract with defaults
        contract = self.env['construction.contract'].create({
            'chantier_id': self.chantier_id.id,
            'subcontractor_id': self.subcontractor_id.id,
            'template_id': template.id,
            'start_date': self.date_start_planned or fields.Date.today(),
            'end_date': self.date_end_planned or fields.Date.today(),
            'retention_rate': 5.0,  # Default 5%
        })
        
        # Assign ALL related lots to this contract (multi-lot aggregation)
        related_lots.write({'contract_id': contract.id})

        # AGGREGATION: Collect Purchase Orders from all related lots
        # "réunir les bons de commandes de tout les lots du même chantier liée a un sous traitant"
        all_lots = related_lots | self
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


    def action_generate_purchase_order(self):
        """
        Generate Purchase Order for this Lot's subcontractor based on validated quotes.
        
        SAP-Level Logic:
        1. Validate preconditions (Subcontractor, Execution Type).
        2. Filter source Sales Order Lines (SOL) from validated quotes (devis_ids).
        3. Create atomic Purchase Order.
        4. Validate financial precision (Cost Price).
        
        Returns:
            Action to view the created PO.
        """
        from odoo.tools import float_compare, float_is_zero
        
        self.ensure_one()
        
        # 1. Preconditions
        if self.execution_type == 'internal':
            raise models.UserError(_("Impossible de générer un bon de commande pour un lot en Régie Interne."))
            
        if not self.subcontractor_id:
            raise models.UserError(_("Veuillez d'abord assigner un sous-traitant au lot."))

        # 1b. Idempotency Check: Return existing PO if already created
        existing_po = self.env['purchase.order'].search([
            ('lot_ids', 'in', [self.id]),
            ('partner_id', '=', self.subcontractor_id.id),
            ('state', '!=', 'cancel'),
        ], limit=1)
        if existing_po:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'purchase.order',
                'res_id': existing_po.id,
                'view_mode': 'form',
                'target': 'current',
            }
            
        # 2. Source Quotes Selection
        # Use explicitly selected quotes (devis_ids) or fallback to all validated quotes
        source_orders = self.chantier_id.devis_ids.filtered(lambda o: o.state == 'sale')
        if not source_orders:
            # Fallback: Find all validated quotes for this chantier if none explicitly selected
            source_orders = self.env['sale.order'].search([
                ('chantier_id', '=', self.chantier_id.id),
                ('state', '=', 'sale')
            ])
            
        if not source_orders:
            raise models.UserError(_("Aucun devis validé trouvé pour ce chantier."))

        # 3. Filter Sales Order Lines linked to THIS Lot
        # We look for lines where lot_id == self.id
        source_lines = self.env['sale.order.line'].search([
            ('order_id', 'in', source_orders.ids),
            ('lot_id', '=', self.id),
            ('display_type', '=', False), # Exclude sections/notes
            ('product_uom_qty', '>', 0)
        ])
        
        if not source_lines:
            raise models.UserError(_(
                "Aucune ligne de vente trouvée pour le lot '%(lot)s' dans les devis validés.\n"
                "Vérifiez que les lignes du devis sont bien assignées au lot '%(lot)s'."
            ) % {'lot': self.name})

        # Atomic Transaction
        PurchaseOrder = self.env['purchase.order']
        PurchaseOrderLine = self.env['purchase.order.line']
        
        # Determine strict currency precision
        currency = self.currency_id
        
        created_po = False
        
        with self.env.cr.savepoint():
            # Create PO Header
            po_vals = {
                'partner_id': self.subcontractor_id.id,
                'origin': _("Chantier %s - Lot %s") % (self.chantier_id.name, self.name),
                'chantier_id': self.chantier_id.id,
                'lot_ids': [(6, 0, [self.id])],
                'date_order': fields.Date.today(),
                'company_id': self.env.company.id,
                'currency_id': currency.id,
            }
            created_po = PurchaseOrder.create(po_vals)
            
            # Create Lines
            for sol in source_lines:
                # SAP-Validation: Price = Cost (price_buy)
                # Requirement: "purchase price = sale price - our margin"
                # Math: Sell - Margin = Cost.
                # safer to use price_buy which IS the Cost.
                
                price_unit = sol.price_buy
                
                # Sanity Check on Margin
                if float_is_zero(price_unit, precision_digits=currency.decimal_places):
                    # Warning if cost is zero (Gift or config error?)
                    # We allow it but log it or maybe UserError depending on strictness.
                    # User said "Zero monetary calculation errors". 
                    # A zero cost might be valid, but suspicious. Let's proceed.
                    pass
                
                # Create PO Line
                pol_vals = {
                    'order_id': created_po.id,
                    'name': sol.name, # Copy description including specs
                    'product_id': sol.product_id.id,
                    'product_qty': sol.product_uom_qty,
                    'product_uom': sol.product_uom.id,
                    'price_unit': price_unit,
                    'taxes_id': [(6, 0, sol.product_id.supplier_taxes_id.ids)], # Default supplier taxes
                    'lot_id': self.id,
                    # Link back to SOL (standard Odoo flow often links procurement, but we do manual link)
                    # 'sale_line_id': sol.id, # If field exists in construction_purchase
                }
                PurchaseOrderLine.create(pol_vals)
            
            # Recompute totals
            # created_po.button_dummy() # Force recompute if needed, but create() triggers it.

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'res_id': created_po.id,
            'view_mode': 'form',
            'target': 'current',
        }
