# -*- coding: utf-8 -*-
"""
Multi-Lot Management Wizard (US-COR-002)

Allows selection of multiple lots from the same subcontractor
to generate consolidated Purchase Orders and redirect to contract module.
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class MultiLotWizard(models.TransientModel):
    """
    US-COR-002: Wizard for managing multiple lots simultaneously.
    
    Validates that all selected lots have the same subcontractor
    before allowing BC generation or contract delegation.
    """
    _name = 'construction.multi.lot.wizard'
    _description = 'Wizard Gestion Multi-Lots'

    # ============================================================
    # REFERENCE FIELDS
    # ============================================================
    
    chantier_id = fields.Many2one(
        'construction.chantier',
        string='Chantier',
        required=True,
        readonly=True
    )
    
    lot_ids = fields.Many2many(
        'construction.lot',
        string='Lots Sélectionnés',
        required=True,
        domain="[('chantier_id', '=', chantier_id)]"
    )
    
    # ============================================================
    # COMPUTED FIELDS
    # ============================================================
    
    subcontractor_id = fields.Many2one(
        'res.partner',
        string='Sous-Traitant Commun',
        compute='_compute_subcontractor',
        store=True
    )
    
    is_same_subcontractor = fields.Boolean(
        string='Même ST',
        compute='_compute_subcontractor'
    )
    
    validation_message = fields.Html(
        string='Message de Validation',
        compute='_compute_subcontractor'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id
    )
    
    # Financial Summary
    total_sale_price = fields.Monetary(
        string='Total Prix de Vente',
        compute='_compute_totals',
        currency_field='currency_id'
    )
    
    total_cost = fields.Monetary(
        string='Total Coût',
        compute='_compute_totals',
        currency_field='currency_id'
    )
    
    total_margin = fields.Monetary(
        string='Total Marge',
        compute='_compute_totals',
        currency_field='currency_id'
    )
    
    lots_summary_html = fields.Html(
        string='Résumé des Lots',
        compute='_compute_lots_summary'
    )
    
    # ============================================================
    # DEFAULT VALUES
    # ============================================================
    
    @api.model
    def default_get(self, fields_list):
        """Load from context: chantier and preselected lots."""
        res = super().default_get(fields_list)
        
        chantier_id = self.env.context.get('default_chantier_id')
        if chantier_id:
            res['chantier_id'] = chantier_id
        
        # Support selection from tree view
        active_ids = self.env.context.get('active_ids', [])
        active_model = self.env.context.get('active_model')
        
        if active_model == 'construction.lot' and active_ids:
            lots = self.env['construction.lot'].browse(active_ids)
            res['lot_ids'] = [(6, 0, lots.ids)]
            if lots:
                res['chantier_id'] = lots[0].chantier_id.id
        
        return res
    
    # ============================================================
    # COMPUTED METHODS
    # ============================================================
    
    @api.depends('lot_ids', 'lot_ids.subcontractor_id')
    def _compute_subcontractor(self):
        """
        US-COR-002: Validate all lots have same subcontractor.
        """
        for wizard in self:
            lots = wizard.lot_ids
            
            if not lots:
                wizard.subcontractor_id = False
                wizard.is_same_subcontractor = False
                wizard.validation_message = _(
                    '<div class="alert alert-info">'
                    '<i class="fa fa-info-circle me-2"></i>'
                    'Sélectionnez au moins un lot pour continuer.'
                    '</div>'
                )
                continue
            
            # Get unique subcontractors
            subcontractors = lots.mapped('subcontractor_id')
            unique_st = subcontractors.filtered(lambda s: s)  # Remove False
            
            if len(unique_st) == 0:
                wizard.subcontractor_id = False
                wizard.is_same_subcontractor = False
                wizard.validation_message = _(
                    '<div class="alert alert-danger">'
                    '<i class="fa fa-times-circle me-2"></i>'
                    '<strong>Erreur:</strong> Aucun sous-traitant assigné aux lots sélectionnés.'
                    '</div>'
                )
            elif len(unique_st) == 1:
                wizard.subcontractor_id = unique_st[0]
                wizard.is_same_subcontractor = True
                wizard.validation_message = _(
                    '<div class="alert alert-success">'
                    '<i class="fa fa-check-circle me-2"></i>'
                    '<strong>Validé:</strong> Tous les lots ont le même sous-traitant: <b>%s</b>'
                    '</div>'
                ) % unique_st[0].name
            else:
                wizard.subcontractor_id = False
                wizard.is_same_subcontractor = False
                st_names = ', '.join(unique_st.mapped('name'))
                wizard.validation_message = _(
                    '<div class="alert alert-danger">'
                    '<i class="fa fa-times-circle me-2"></i>'
                    '<strong>Erreur:</strong> Les lots sélectionnés ont des sous-traitants différents: '
                    '<b>%s</b>. Veuillez sélectionner des lots avec le même sous-traitant.'
                    '</div>'
                ) % st_names
    
    @api.depends('lot_ids')
    def _compute_totals(self):
        """Compute financial totals from selected lots."""
        for wizard in self:
            sale_price = 0.0
            cost = 0.0
            
            for lot in wizard.lot_ids:
                # Use lot.price if available
                lot_price = getattr(lot, 'price', 0.0) or 0.0
                lot_cost = getattr(lot, 'cost', 0.0) or 0.0
                sale_price += lot_price
                cost += lot_cost
            
            wizard.total_sale_price = sale_price
            wizard.total_cost = cost
            wizard.total_margin = sale_price - cost
    
    @api.depends('lot_ids')
    def _compute_lots_summary(self):
        """Generate HTML summary table of selected lots."""
        for wizard in self:
            if not wizard.lot_ids:
                wizard.lots_summary_html = ''
                continue
            
            rows = []
            for lot in wizard.lot_ids:
                st_name = lot.subcontractor_id.name if lot.subcontractor_id else '-'
                lot_price = getattr(lot, 'price', 0.0) or 0.0
                rows.append(f'''
                    <tr>
                        <td><strong>{lot.code}</strong></td>
                        <td>{lot.name}</td>
                        <td>{st_name}</td>
                        <td class="text-end">{lot_price:,.2f} €</td>
                    </tr>
                ''')
            
            wizard.lots_summary_html = f'''
                <table class="table table-sm table-striped">
                    <thead>
                        <tr>
                            <th>Code</th>
                            <th>Nom</th>
                            <th>Sous-Traitant</th>
                            <th class="text-end">Prix</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join(rows)}
                    </tbody>
                </table>
            '''
    
    # ============================================================
    # ACTIONS
    # ============================================================
    
    def action_generate_consolidated_po(self):
        """
        US-COR-002: Generate consolidated Purchase Order for all selected lots.
        """
        self.ensure_one()
        
        if not self.is_same_subcontractor:
            raise UserError(_("Impossible de générer un BC: les lots n'ont pas le même sous-traitant."))
        
        if not self.subcontractor_id:
            raise UserError(_("Aucun sous-traitant assigné aux lots sélectionnés."))
        
        # Build reference: [CHANTIER]-[LOT1+LOT2+...]-[SOUS_TRAITANT]
        lot_codes = '+'.join(self.lot_ids.mapped('code'))
        chantier_name = self.chantier_id.name or 'CHANTIER'
        st_name = self.subcontractor_id.name[:15] if self.subcontractor_id else 'ST'
        po_reference = f"{chantier_name[:20]}-{lot_codes}-{st_name}"
        
        # Collect all sale order lines from these lots
        po_lines = []
        for lot in self.lot_ids:
            # Get SOLs linked to this lot
            sol_domain = [
                ('order_id.chantier_id', '=', self.chantier_id.id),
                ('order_id.state', '=', 'sale'),
            ]
            
            SOL = self.env['sale.order.line']
            if 'lot_id' in SOL._fields:
                sol_domain.append(('lot_id', '=', lot.id))
                lines = SOL.search(sol_domain)
            else:
                lines = SOL.search(sol_domain).filtered(
                    lambda l: lot.code in (l.name or '') or lot.name.lower() in (l.name or '').lower()
                )
            
            for sol in lines:
                po_lines.append((0, 0, {
                    'product_id': sol.product_id.id,
                    'name': f"[{lot.code}] {sol.name}",
                    'product_qty': sol.product_uom_qty,
                    'product_uom': sol.product_uom.id,
                    'price_unit': sol.product_id.standard_price,  # Cost, not sale price
                    'date_planned': fields.Date.today(),
                }))
        
        if not po_lines:
            raise UserError(_("Aucune ligne de devis trouvée pour les lots sélectionnés."))
        
        # Create Purchase Order
        PO = self.env['purchase.order']
        po = PO.create({
            'partner_id': self.subcontractor_id.id,
            'origin': po_reference,
            'order_line': po_lines,
        })
        
        # Link PO to lots if field exists
        if 'lot_ids' in PO._fields:
            po.lot_ids = [(6, 0, self.lot_ids.ids)]
        
        _logger.info(
            "[LOGGER][INFO][construction.multi_lot_wizard] Generated consolidated PO %s for lots %s",
            po.name, lot_codes
        )
        
        # Return action to view PO
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bon de Commande'),
            'res_model': 'purchase.order',
            'res_id': po.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_open_contract_wizard(self):
        """
        US-COR-002: Redirect to construction_contract module with lot data.
        """
        self.ensure_one()
        
        if not self.is_same_subcontractor:
            raise UserError(_("Impossible de générer un contrat: les lots n'ont pas le même sous-traitant."))
        
        # Check if construction_contract module is installed
        if 'construction.contract' not in self.env:
            raise UserError(_("Le module construction_contract n'est pas installé."))
        
        # Check for contract creation wizard
        wizard_model = 'contract.creation.wizard'
        if wizard_model not in self.env:
            # Fallback: create contract directly
            return self._create_contract_directly()
        
        # Open contract creation wizard with context
        return {
            'type': 'ir.actions.act_window',
            'name': _('Créer Contrat Multi-Lots'),
            'res_model': wizard_model,
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_chantier_id': self.chantier_id.id,
                'default_lot_ids': [(6, 0, self.lot_ids.ids)],
                'default_subcontractor_id': self.subcontractor_id.id,
            },
        }
    
    def _create_contract_directly(self):
        """Fallback: Create contract directly if no wizard available."""
        Contract = self.env['construction.contract']
        
        contract = Contract.create({
            'chantier_id': self.chantier_id.id,
            'subcontractor_id': self.subcontractor_id.id,
            'lot_ids': [(6, 0, self.lot_ids.ids)],
        })
        
        _logger.info(
            "[LOGGER][INFO][construction.multi_lot_wizard] Created contract %s for lots %s",
            contract.name, self.lot_ids.mapped('code')
        )
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Contrat'),
            'res_model': 'construction.contract',
            'res_id': contract.id,
            'view_mode': 'form',
            'target': 'current',
        }
