# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class SubcontractorAssignmentWizard(models.TransientModel):
    _name = 'subcontractor.assignment.wizard'
    _description = 'Assistant d\'Assignation Sous-traitant'
    
    lot_id = fields.Many2one('construction.lot', string='Lot Concerné', required=True, readonly=True)
    partner_id = fields.Many2one('res.partner', string='Sous-traitant', required=True, domain="['|', ('is_subcontractor', '=', True), ('supplier_rank', '>', 0)]")
    
    # Compliance Info
    compliance_state = fields.Selection(related='partner_id.compliance_state', readonly=True)
    alert_level = fields.Selection(related='partner_id.alert_level', readonly=True)
    
    # Validation
    is_blocked = fields.Boolean(compute='_compute_validation', store=True)
    blocking_reasons = fields.Html(string='Raisons du blocage', compute='_compute_validation')
    
    force_assignment = fields.Boolean(string='Forcer l\'assignation')
    force_reason = fields.Text(string='Motif de la dérogation')
    
    @api.depends('partner_id')
    def _compute_validation(self):
        for wiz in self:
            if not wiz.partner_id:
                wiz.is_blocked = False
                wiz.blocking_reasons = False
                continue
                
            reasons = []
            # Check Decennale (Strictly Required)
            if wiz.partner_id.doc_insurance_dec_status not in ['valid', 'expiring']:
                reasons.append(_("❌ Assurance Décennale invalide ou manquante"))
            
            # Check other required docs
            if wiz.partner_id.doc_kbis_status not in ['valid', 'expiring']:
                reasons.append(_("⚠️ KBIS invalide"))
            
            if wiz.partner_id.doc_urssaf_status not in ['valid', 'expiring']:
                reasons.append(_("⚠️ URSSAF invalide"))
                
            wiz.blocking_reasons = '<br/>'.join(reasons) if reasons else False
            wiz.is_blocked = any('❌' in r for r in reasons)

    def action_confirm(self):
        self.ensure_one()
        if self.is_blocked and not self.force_assignment:
            raise UserError(_("Ce sous-traitant est bloqué pour non-conformité. Cochez 'Forcer l'assignation' pour passer outre (Déconseillé)."))
            
        if self.force_assignment and not self.force_reason:
            raise UserError(_("Veuillez indiquer un motif pour forcer l'assignation."))
            
        # Assign
        self.lot_id.subcontractor_id = self.partner_id
        
        # Log
        if self.force_assignment:
            self.lot_id.message_post(
                body=_("⚠️ Sous-traitant %s assigné de force par %s.<br/>Motif: %s") % (
                    self.partner_id.name, self.env.user.name, self.force_reason
                ),
                message_type='comment',
                subtype_xmlid='mail.mt_note'
            )
        else:
            self.lot_id.message_post(
                body=_("✅ Sous-traitant %s assigné (Dossier Conforme)") % self.partner_id.name
            )
            
        return {'type': 'ir.actions.act_window_close'}
