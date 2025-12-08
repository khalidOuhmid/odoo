# -*- coding: utf-8 -*-
from odoo import models, fields, api
import secrets
from datetime import timedelta

class ResPartner(models.Model):
    _inherit = 'res.partner'

    # ==========================
    # SUBCONTRACTOR IDENTIFICATION
    # ==========================
    is_subcontractor = fields.Boolean(
        string='Est un Sous-traitant', 
        help="Cochez cette case pour activer la gestion de conformité et des contrats."
    )
    
    # PORTAL UPLOAD
    upload_token = fields.Char(string='Jeton d\'Upload', copy=False)
    token_expiration = fields.Datetime(string='Expiration du Jeton')
    upload_url = fields.Char(compute='_compute_upload_url')
    
    # ==========================
    # COMPLIANCE MANAGEMENT
    # ==========================
    compliance_document_ids = fields.One2many(
        'construction.compliance.document',
        'partner_id',
        string='Documents de Conformité'
    )
    
    # KPI Conformité (Calculés)
    compliance_state = fields.Selection([
        ('compliant', 'Conforme'),
        ('incomplete', 'Incomplet'),
        ('expired', 'Documents Expirés')
    ], string='État de Conformité', compute='_compute_compliance_state', store=True)

    @api.depends('compliance_document_ids.state', 'compliance_document_ids.document_type')
    def _compute_compliance_state(self):
        REQUIRED_TYPES = ['kbis', 'urssaf', 'insurance_dec', 'insurance_pro']
        
        for partner in self:
            if not partner.is_subcontractor:
                partner.compliance_state = False
                continue
                
            docs = partner.compliance_document_ids
            # Check for validity
            if any(d.state == 'expired' for d in docs):
                partner.compliance_state = 'expired'
                continue
                
            # Check for presence of all required types
            valid_types = docs.filtered(lambda d: d.state == 'valid').mapped('document_type')
            if all(t in valid_types for t in REQUIRED_TYPES):
                partner.compliance_state = 'compliant'
            else:
                partner.compliance_state = 'incomplete'

    # ==========================
    # ACTIONS
    # ==========================
    def action_generate_upload_link(self):
        """ Génère un lien sécurisé d'upload """
        self.ensure_one()
        self.upload_token = secrets.token_urlsafe(32)
        self.token_expiration = fields.Datetime.now() + timedelta(days=7)
        return True

    @api.depends('upload_token')
    def _compute_upload_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for partner in self:
            if partner.upload_token:
                partner.upload_url = f"{base_url}/documents/upload/{partner.upload_token}"
            else:
                partner.upload_url = False
