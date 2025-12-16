# -*- coding: utf-8 -*-
"""
Lot Extension for Subcontractor Compliance

Extends construction.lot with subcontractor compliance fields and computed warnings.
These fields depend on res_partner fields defined in this module.
"""

from odoo import models, fields, api


class ConstructionLot(models.Model):
    """Extend construction.lot with subcontractor compliance fields."""
    _inherit = 'construction.lot'
    
    # ============= SUBCONTRACTOR SELECTION ============= #
    subcontractor_id = fields.Many2one(
        'res.partner',
        domain="['|', ('is_subcontractor', '=', True), ('supplier_rank', '>', 0)]"
    )

    # ============= SUBCONTRACTOR COMPLIANCE (Computed) ============= #
    subcontractor_compliance_state = fields.Selection(
        related='subcontractor_id.compliance_state',
        string='État Conformité S/T',
        readonly=True,
        help="État de conformité documentaire du sous-traitant"
    )
    
    subcontractor_alert_level = fields.Selection(
        related='subcontractor_id.alert_level',
        string='Niveau Alerte S/T',
        readonly=True,
        help="Niveau d'alerte documents du sous-traitant"
    )
    
    subcontractor_doc_warning = fields.Html(
        compute='_compute_subcontractor_doc_warning',
        string='Alerte Documents S/T',
        help="Avertissement si les documents du sous-traitant expirent avant la fin du chantier"
    )
    
    # ============= COMPUTE METHODS ============= #
    @api.depends('subcontractor_id', 'chantier_id.date_end_contract', 'chantier_id.date_end_internal')
    def _compute_subcontractor_doc_warning(self):
        """Check if subcontractor documents will expire before chantier deadline.
        
        State Machine Logic (SAP-style):
        - No subcontractor or no deadline = No warning
        - Document expires before deadline = Warning displayed
        - All documents valid through deadline = No warning
        """
        # Document types config (consistent with res_partner)
        DOCUMENT_TYPES = {
            'kbis': {'name': 'KBIS', 'expiry_field': 'doc_kbis_expiry', 'required': True},
            'urssaf': {'name': 'Attestation URSSAF', 'expiry_field': 'doc_urssaf_expiry', 'required': True},
            'insurance_dec': {'name': 'Assurance Décennale', 'expiry_field': 'doc_insurance_dec_expiry', 'required': True},
            'cni': {'name': 'Carte d\'Identité', 'expiry_field': 'doc_cni_expiry', 'required': True},
        }
        
        for lot in self:
            # STATE: Guard conditions
            if not lot.subcontractor_id or lot.execution_type != 'external':
                lot.subcontractor_doc_warning = False
                continue
            
            if not lot.chantier_id:
                lot.subcontractor_doc_warning = False
                continue
            
            # Get chantier deadline (contract date takes priority)
            deadline = lot.chantier_id.date_end_contract or lot.chantier_id.date_end_internal
            if not deadline:
                lot.subcontractor_doc_warning = False
                continue
            
            # STATE: Evaluate each document against deadline
            warnings = []
            partner = lot.subcontractor_id
            
            for doc_key, config in DOCUMENT_TYPES.items():
                if not config.get('required'):
                    continue
                    
                expiry_field = config.get('expiry_field')
                if not expiry_field:
                    continue
                    
                expiry = getattr(partner, expiry_field, None)
                if expiry and expiry < deadline:
                    days_until_expiry = (expiry - fields.Date.today()).days
                    if days_until_expiry < 0:
                        warnings.append(
                            f"🔴 <b>{config['name']}</b> expiré depuis {abs(days_until_expiry)} jours"
                        )
                    else:
                        warnings.append(
                            f"⚠️ <b>{config['name']}</b> expire le {expiry.strftime('%d/%m/%Y')} "
                            f"(avant fin chantier {deadline.strftime('%d/%m/%Y')})"
                        )
            
            # STATE: Build warning HTML
            if warnings:
                lot.subcontractor_doc_warning = '<br/>'.join(warnings)
            else:
                lot.subcontractor_doc_warning = False
