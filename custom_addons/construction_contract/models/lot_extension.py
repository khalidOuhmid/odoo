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
        
        # Generate contract HTML (prefill template)
        contract.action_generate_contract()
        
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

