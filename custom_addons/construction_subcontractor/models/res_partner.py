# -*- coding: utf-8 -*-
"""
Subcontractor Partner Extension - Clean Migration

Extends res.partner with comprehensive subcontractor compliance management:
- Document lifecycle (upload, validation, expiry tracking)
- Portal upload functionality
- Automated notifications
- Stage-based compliance requirements
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import date, timedelta
import secrets
import logging

_logger = logging.getLogger(__name__)


# ============= DOCUMENT CONFIGURATION ============= #
DOCUMENT_TYPES = {
    'kbis': {
        'name': 'KBIS',
        'field': 'doc_kbis',
        'expiry_field': 'doc_kbis_expiry',
        'status_field': 'doc_kbis_status',
        'has_expiry': True,
        'required': True,
        'sequence': 10,
    },
    'urssaf': {
        'name': 'Attestation URSSAF',
        'field': 'doc_urssaf',
        'expiry_field': 'doc_urssaf_expiry',
        'status_field': 'doc_urssaf_status',
        'has_expiry': True,
        'required': True,
        'sequence': 20,
    },
    'insurance_dec': {
        'name': 'Assurance Décennale',
        'field': 'doc_insurance_dec',
        'expiry_field': 'doc_insurance_dec_expiry',
        'status_field': 'doc_insurance_dec_status',
        'has_expiry': True,
        'required': True,
        'sequence': 30,
    },
    'insurance_pro': {
        'name': 'Assurance RC Pro',
        'field': 'doc_insurance_pro',
        'expiry_field': 'doc_insurance_pro_expiry',
        'status_field': 'doc_insurance_pro_status',
        'has_expiry': True,
        'required': True,
        'sequence': 40,
    },
    'rib': {
        'name': 'RIB',
        'field': 'doc_rib',
        'expiry_field': False,
        'status_field': 'doc_rib_status',
        'has_expiry': False,
        'required': True,
        'sequence': 50,
    },
}

EXPIRY_WARNING_DAYS = 30


class ResPartner(models.Model):
    """
    Enhanced partner model for subcontractor management.
    
    Provides complete document lifecycle management, compliance tracking,
    and portal upload functionality for construction subcontractors.
    """
    _inherit = 'res.partner'

    # ============= SUBCONTRACTOR IDENTIFICATION ============= #
    is_subcontractor = fields.Boolean(
        string='Est un sous-traitant',
        help="Active la gestion de conformité documentaire"
    )
    subcontractor_type = fields.Selection([
        ('external', 'Sous-traitant externe'),
        ('internal', 'Ressource interne'),
    ], string='Type', default='external')
    
    # ============= DOCUMENTS: KBIS ============= #
    doc_kbis = fields.Binary(string='KBIS', attachment=True)
    doc_kbis_filename = fields.Char(string='Nom fichier KBIS')
    doc_kbis_expiry = fields.Date(string='Expiration KBIS')
    doc_kbis_status = fields.Selection([
        ('missing', 'Manquant'),
        ('to_check', 'À vérifier'),
        ('valid', 'Valide'),
        ('expiring', 'Expire bientôt'),
        ('expired', 'Expiré'),
        ('rejected', 'Rejeté'),
    ], string='Statut KBIS', compute='_compute_doc_statuses', store=True)
    
    # ============= DOCUMENTS: URSSAF ============= #
    doc_urssaf = fields.Binary(string='Attestation URSSAF', attachment=True)
    doc_urssaf_filename = fields.Char(string='Nom fichier URSSAF')
    doc_urssaf_expiry = fields.Date(string='Expiration URSSAF')
    doc_urssaf_status = fields.Selection([
        ('missing', 'Manquant'),
        ('to_check', 'À vérifier'),
        ('valid', 'Valide'),
        ('expiring', 'Expire bientôt'),
        ('expired', 'Expiré'),
        ('rejected', 'Rejeté'),
    ], string='Statut URSSAF', compute='_compute_doc_statuses', store=True)
    
    # ============= DOCUMENTS: ASSURANCE DÉCENNALE ============= #
    doc_insurance_dec = fields.Binary(string='Assurance Décennale', attachment=True)
    doc_insurance_dec_filename = fields.Char(string='Nom fichier Assurance Déc.')
    doc_insurance_dec_expiry = fields.Date(string='Expiration Assurance Déc.')
    doc_insurance_dec_status = fields.Selection([
        ('missing', 'Manquant'),
        ('to_check', 'À vérifier'),
        ('valid', 'Valide'),
        ('expiring', 'Expire bientôt'),
        ('expired', 'Expiré'),
        ('rejected', 'Rejeté'),
    ], string='Statut Assurance Déc.', compute='_compute_doc_statuses', store=True)
    
    # ============= DOCUMENTS: ASSURANCE RC PRO ============= #
    doc_insurance_pro = fields.Binary(string='Assurance RC Pro', attachment=True)
    doc_insurance_pro_filename = fields.Char(string='Nom fichier RC Pro')
    doc_insurance_pro_expiry = fields.Date(string='Expiration RC Pro')
    doc_insurance_pro_status = fields.Selection([
        ('missing', 'Manquant'),
        ('to_check', 'À vérifier'),
        ('valid', 'Valide'),
        ('expiring', 'Expire bientôt'),
        ('expired', 'Expiré'),
        ('rejected', 'Rejeté'),
    ], string='Statut RC Pro', compute='_compute_doc_statuses', store=True)
    
    # ============= DOCUMENTS: RIB ============= #
    doc_rib = fields.Binary(string='RIB', attachment=True)
    doc_rib_filename = fields.Char(string='Nom fichier RIB')
    doc_rib_status = fields.Selection([
        ('missing', 'Manquant'),
        ('to_check', 'À vérifier'),
        ('valid', 'Valide'),
        ('rejected', 'Rejeté'),
    ], string='Statut RIB', compute='_compute_doc_statuses', store=True)
    
    # ============= COMPLIANCE STATE ============= #
    compliance_state = fields.Selection([
        ('compliant', 'Conforme'),
        ('incomplete', 'Incomplet'),
        ('expired', 'Documents expirés'),
    ], string='État de conformité', compute='_compute_compliance_state', store=True)
    
    missing_documents = fields.Text(
        string='Documents manquants',
        compute='_compute_missing_documents'
    )
    
    # ============= PORTAL UPLOAD ============= #
    upload_token = fields.Char(string='Jeton d\'upload', copy=False)
    token_expiration = fields.Datetime(string='Expiration du jeton')
    upload_url = fields.Char(compute='_compute_upload_url', string='Lien d\'upload')
    
    # ============= RELATIONS ============= #
    # NOTE: contract_ids requires construction_contract module to be installed
    # Uncomment when using construction_contract:
    # contract_ids = fields.One2many(
    #     'construction.contract', 'subcontractor_id',
    #     string='Contrats'
    # )
    contract_count = fields.Integer(compute='_compute_contract_count', default=0)
    
    specialty_lot_category_ids = fields.Many2many(
        'construction.lot.category',
        'partner_lot_category_specialty_rel',
        'partner_id', 'category_id',
        string='Spécialités (Lots)',
        help="Types de lots que ce sous-traitant peut réaliser (ex: Gros Œuvre, Électricité)"
    )
    
    # ============= COMPUTED METHODS ============= #
    
    @api.depends(
        'doc_kbis', 'doc_kbis_expiry',
        'doc_urssaf', 'doc_urssaf_expiry',
        'doc_insurance_dec', 'doc_insurance_dec_expiry',
        'doc_insurance_pro', 'doc_insurance_pro_expiry',
        'doc_rib'
    )
    def _compute_doc_statuses(self):
        """Compute individual document statuses based on content and expiry."""
        today = date.today()
        warning_threshold = today + timedelta(days=EXPIRY_WARNING_DAYS)
        
        for partner in self:
            for doc_key, config in DOCUMENT_TYPES.items():
                doc_field = config['field']
                status_field = config['status_field']
                expiry_field = config.get('expiry_field')
                
                doc_content = getattr(partner, doc_field, None)
                
                if not doc_content:
                    setattr(partner, status_field, 'missing')
                    continue
                
                # If document has expiry, check it
                if expiry_field:
                    expiry_date = getattr(partner, expiry_field, None)
                    if not expiry_date:
                        setattr(partner, status_field, 'to_check')
                    elif expiry_date < today:
                        setattr(partner, status_field, 'expired')
                    elif expiry_date <= warning_threshold:
                        setattr(partner, status_field, 'expiring')
                    else:
                        setattr(partner, status_field, 'valid')
                else:
                    # No expiry = valid if present
                    setattr(partner, status_field, 'valid')
    
    @api.depends(
        'doc_kbis_status', 'doc_urssaf_status',
        'doc_insurance_dec_status', 'doc_insurance_pro_status',
        'doc_rib_status', 'is_subcontractor'
    )
    def _compute_compliance_state(self):
        """Compute overall compliance state from document statuses."""
        for partner in self:
            if not partner.is_subcontractor:
                partner.compliance_state = False
                continue
            
            statuses = [
                partner.doc_kbis_status,
                partner.doc_urssaf_status,
                partner.doc_insurance_dec_status,
                partner.doc_insurance_pro_status,
                partner.doc_rib_status,
            ]
            
            if 'expired' in statuses:
                partner.compliance_state = 'expired'
            elif 'missing' in statuses or 'rejected' in statuses or 'to_check' in statuses:
                partner.compliance_state = 'incomplete'
            else:
                partner.compliance_state = 'compliant'
    
    def _compute_missing_documents(self):
        """List missing or invalid documents."""
        for partner in self:
            missing = []
            for doc_key, config in DOCUMENT_TYPES.items():
                status = getattr(partner, config['status_field'], 'missing')
                if status in ('missing', 'expired', 'rejected'):
                    missing.append(f"• {config['name']} ({status})")
            partner.missing_documents = '\n'.join(missing) if missing else ''
    
    @api.depends('upload_token')
    def _compute_upload_url(self):
        """Generate portal upload URL."""
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for partner in self:
            if partner.upload_token:
                partner.upload_url = f"{base_url}/subcontractor/upload/{partner.upload_token}"
            else:
                partner.upload_url = False
    
    def _compute_contract_count(self):
        for partner in self:
            # Only count if construction_contract module is installed
            if hasattr(partner, 'contract_ids'):
                partner.contract_count = len(partner.contract_ids)
            else:
                partner.contract_count = 0
    
    # ============= PORTAL ACTIONS ============= #
    
    def action_generate_upload_link(self):
        """Generate a secure upload link for the subcontractor."""
        self.ensure_one()
        self.upload_token = secrets.token_urlsafe(32)
        self.token_expiration = fields.Datetime.now() + timedelta(days=7)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Lien généré'),
                'message': _('Le lien d\'upload a été généré. Valide 7 jours.'),
                'type': 'success',
            }
        }
    
    def action_send_upload_request(self):
        """Send email with upload link to subcontractor."""
        self.ensure_one()
        
        if not self.email:
            raise UserError(_("Ce partenaire n'a pas d'adresse email."))
        
        # Generate token if not exists
        if not self.upload_token or (self.token_expiration and self.token_expiration < fields.Datetime.now()):
            self.action_generate_upload_link()
        
        # Find and send template
        template = self.env.ref('construction_subcontractor.email_template_upload_request', raise_if_not_found=False)
        if template:
            template.send_mail(self.id, force_send=True)
            self.message_post(body=_("📧 Demande de documents envoyée par email"))
        else:
            # Fallback: post in chatter
            self.message_post(
                body=_("📋 Lien d'upload: %s") % self.upload_url,
                message_type='notification'
            )
        
        return True
    
    # ============= DOCUMENT VALIDATION ACTIONS ============= #
    
    def action_validate_all_documents(self):
        """Mark all 'to_check' documents as valid."""
        self.ensure_one()
        # This is a manual action - just posts notification
        self.message_post(body=_("✅ Documents validés par %s") % self.env.user.name)
        return True
    
    def action_request_missing_documents(self):
        """Send notification for missing documents."""
        self.ensure_one()
        if not self.missing_documents:
            raise UserError(_("Tous les documents sont présents."))
        
        return self.action_send_upload_request()
    
    # ============= CONTRACT ACTIONS ============= #
    
    def action_view_contracts(self):
        """Open contracts for this subcontractor."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Contrats - %s') % self.name,
            'res_model': 'construction.contract',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }
    
    # ============= CRON: EXPIRY CHECK ============= #
    
    @api.model
    def cron_check_document_expiry(self):
        """
        Scheduled action to check document expiry and send notifications.
        
        Strategy: Use chatter activities instead of emails to avoid spam.
        """
        today = date.today()
        warning_threshold = today + timedelta(days=EXPIRY_WARNING_DAYS)
        
        # Find subcontractors with expiring or expired documents
        subcontractors = self.search([
            ('is_subcontractor', '=', True),
            ('compliance_state', 'in', ['expired', 'incomplete']),
        ])
        
        for partner in subcontractors:
            # Check for expired docs
            expired_docs = []
            expiring_docs = []
            
            for doc_key, config in DOCUMENT_TYPES.items():
                status = getattr(partner, config['status_field'], 'missing')
                if status == 'expired':
                    expired_docs.append(config['name'])
                elif status == 'expiring':
                    expiring_docs.append(config['name'])
            
            # Create activity instead of email (less spam)
            if expired_docs:
                self.env['mail.activity'].create({
                    'activity_type_id': self.env.ref('mail.mail_activity_data_warning').id,
                    'res_model_id': self.env['ir.model']._get('res.partner').id,
                    'res_id': partner.id,
                    'summary': _('Documents expirés'),
                    'note': _('Documents expirés: %s') % ', '.join(expired_docs),
                    'date_deadline': today,
                    'user_id': partner.user_id.id if partner.user_id else self.env.user.id,
                })
        
        _logger.info("Document expiry check completed for %d subcontractors", len(subcontractors))
        return True
    
    # ============= HELPER METHODS ============= #
    
    def is_compliant_for_stage(self, stage_code):
        """
        Check if subcontractor is compliant for a specific construction stage.
        
        Args:
            stage_code: The stage code to check compliance for
            
        Returns:
            tuple: (is_compliant: bool, message: str)
        """
        self.ensure_one()
        
        if self.subcontractor_type == 'internal':
            return True, "Ressource interne - pas de contrôle de conformité"
        
        if self.compliance_state == 'compliant':
            return True, "Tous les documents sont valides"
        elif self.compliance_state == 'expired':
            return False, f"Documents expirés: {self.missing_documents}"
        else:
            return False, f"Documents manquants: {self.missing_documents}"
