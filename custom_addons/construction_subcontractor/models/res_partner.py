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
        'validation_field': 'doc_kbis_is_validated',
        'has_expiry': True,
        'required': True,
        'validity_months': 2,  # Validité 2 mois
        'sequence': 10,
    },
    'urssaf': {
        'name': 'Attestation URSSAF',
        'field': 'doc_urssaf',
        'expiry_field': 'doc_urssaf_expiry',
        'status_field': 'doc_urssaf_status',
        'validation_field': 'doc_urssaf_is_validated',
        'has_expiry': True,
        'required': True,
        'validity_months': 2,  # Validité 2 mois
        'sequence': 20,
    },
    'insurance_dec': {
        'name': 'Assurance Décennale',
        'field': 'doc_insurance_dec',
        'expiry_field': 'doc_insurance_dec_expiry',
        'status_field': 'doc_insurance_dec_status',
        'validation_field': 'doc_insurance_dec_is_validated',
        'has_expiry': True,
        'required': True,  # BLOQUANT
        'sequence': 30,
    },
    'cni': {
        'name': 'Carte d\'Identité',
        'field': 'doc_cni',
        'expiry_field': 'doc_cni_expiry',
        'status_field': 'doc_cni_status',
        'validation_field': 'doc_cni_is_validated',
        'has_expiry': True,
        'required': True,
        'sequence': 35,
    },
    'insurance_pro': {
        'name': 'Assurance RC Pro',
        'field': 'doc_insurance_pro',
        'expiry_field': 'doc_insurance_pro_expiry',
        'status_field': 'doc_insurance_pro_status',
        'validation_field': 'doc_insurance_pro_is_validated',
        'has_expiry': True,
        'required': False,  # NON BLOQUANT
        'sequence': 40,
    },
    'rib': {
        'name': 'RIB',
        'field': 'doc_rib',
        'expiry_field': False,
        'status_field': 'doc_rib_status',
        'validation_field': 'doc_rib_is_validated',
        'has_expiry': False,
        'required': False,  # NON BLOQUANT
        'sequence': 50,
    },
}

EXPIRY_WARNING_DAYS = 30
EXPIRY_CRITICAL_DAYS = 7  # Red line threshold


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
    
    # ============= LIFECYCLE (Salesforce Path) ============= #
    subcontractor_stage = fields.Selection([
        ('draft', 'Brouillon'),
        ('invited', 'Invitation Envoyée'),
        ('incomplete', 'Dossier Incomplet'),
        ('compliant', 'Dossier Conforme'),
        ('blocked', 'Bloqué'),
    ], string='Étape', default='draft', tracking=True,
       help="Cycle de vie du dossier sous-traitant")
    
    # ============= ALERT LEVEL (Yellow/Red Lines) ============= #
    alert_level = fields.Selection([
        ('green', 'Conforme'),
        ('yellow', 'Alerte'),
        ('red', 'Critique'),
    ], string='Niveau d\'Alerte', compute='_compute_alert_level', store=True)
    
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
    doc_kbis_is_validated = fields.Boolean(
        string='KBIS Validé', default=False, copy=False,
        help="Coché une fois le document vérifié et validé par un administrateur"
    )
    doc_kbis_validated_by = fields.Many2one(
        'res.users', string='KBIS Validé par', readonly=True, copy=False
    )
    doc_kbis_validated_at = fields.Datetime(
        string='KBIS Validé le', readonly=True, copy=False
    )
    
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
    doc_urssaf_is_validated = fields.Boolean(string='URSSAF Validé', default=False, copy=False)
    doc_urssaf_validated_by = fields.Many2one('res.users', string='URSSAF Validé par', readonly=True, copy=False)
    doc_urssaf_validated_at = fields.Datetime(string='URSSAF Validé le', readonly=True, copy=False)
    
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
    doc_insurance_dec_is_validated = fields.Boolean(string='Assurance Déc. Validée', default=False, copy=False)
    doc_insurance_dec_validated_by = fields.Many2one('res.users', string='Assurance Déc. Validée par', readonly=True, copy=False)
    doc_insurance_dec_validated_at = fields.Datetime(string='Assurance Déc. Validée le', readonly=True, copy=False)
    
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
    doc_insurance_pro_is_validated = fields.Boolean(string='RC Pro Validée', default=False, copy=False)
    doc_insurance_pro_validated_by = fields.Many2one('res.users', string='RC Pro Validée par', readonly=True, copy=False)
    doc_insurance_pro_validated_at = fields.Datetime(string='RC Pro Validée le', readonly=True, copy=False)
    
    # ============= DOCUMENTS: RIB ============= #
    doc_rib = fields.Binary(string='RIB', attachment=True)
    doc_rib_filename = fields.Char(string='Nom fichier RIB')
    doc_rib_status = fields.Selection([
        ('missing', 'Manquant'),
        ('to_check', 'À vérifier'),
        ('valid', 'Valide'),
        ('rejected', 'Rejeté'),
    ], string='Statut RIB', compute='_compute_doc_statuses', store=True)
    doc_rib_is_validated = fields.Boolean(string='RIB Validé', default=False, copy=False)
    doc_rib_validated_by = fields.Many2one('res.users', string='RIB Validé par', readonly=True, copy=False)
    doc_rib_validated_at = fields.Datetime(string='RIB Validé le', readonly=True, copy=False)
    
    # ============= DOCUMENTS: CNI (Carte d'Identité) ============= #
    doc_cni = fields.Binary(string='Carte d\'Identité', attachment=True)
    doc_cni_filename = fields.Char(string='Nom fichier CNI')
    doc_cni_expiry = fields.Date(string='Expiration CNI')
    doc_cni_status = fields.Selection([
        ('missing', 'Manquant'),
        ('to_check', 'À vérifier'),
        ('valid', 'Valide'),
        ('expiring', 'Expire bientôt'),
        ('expired', 'Expiré'),
        ('rejected', 'Rejeté'),
    ], string='Statut CNI', compute='_compute_doc_statuses', store=True)
    doc_cni_is_validated = fields.Boolean(string='CNI Validé', default=False, copy=False)
    doc_cni_validated_by = fields.Many2one('res.users', string='CNI Validé par', readonly=True, copy=False)
    doc_cni_validated_at = fields.Datetime(string='CNI Validé le', readonly=True, copy=False)
    
    # ============= COMPLIANCE STATE ============= #
    compliance_state = fields.Selection([
        ('compliant', 'Conforme'),
        ('incomplete', 'Incomplet'),
        ('expired', 'Documents expirés'),
        ('missing', 'Dossier Vierge'),
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
    
    lot_ids = fields.One2many(
        'construction.lot', 'subcontractor_id',
        string='Lots Assignés'
    )
    
    # ============= DOCUMENT ARCHIVES ============= #
    archive_ids = fields.One2many(
        'subcontractor.document.archive', 'partner_id',
        string='Documents Archivés'
    )
    archive_count = fields.Integer(
        compute='_compute_archive_count',
        string='Nombre d\'archives'
    )
    
    @api.depends('archive_ids')
    def _compute_archive_count(self):
        for partner in self:
            partner.archive_count = len(partner.archive_ids)
    
    # ============= COMPUTED METHODS ============= #
    
    @api.depends(
        'doc_kbis', 'doc_kbis_expiry', 'doc_kbis_is_validated',
        'doc_urssaf', 'doc_urssaf_expiry', 'doc_urssaf_is_validated',
        'doc_insurance_dec', 'doc_insurance_dec_expiry', 'doc_insurance_dec_is_validated',
        'doc_insurance_pro', 'doc_insurance_pro_expiry', 'doc_insurance_pro_is_validated',
        'doc_cni', 'doc_cni_expiry', 'doc_cni_is_validated',
        'doc_rib', 'doc_rib_is_validated'
    )
    def _compute_doc_statuses(self):
        """Compute individual document statuses based on content, expiry, and validation state.
        
        State Machine (SAP-style):
        - missing: No file uploaded
        - to_check: File present but not validated by admin
        - valid: Validated by admin AND not expired
        - expiring: Validated but expiring within 30 days
        - expired: Past expiry date (overrides validation)
        - rejected: Not used in compute, set manually via wizard
        """
        today = date.today()
        warning_threshold = today + timedelta(days=EXPIRY_WARNING_DAYS)
        
        for partner in self:
            for doc_key, config in DOCUMENT_TYPES.items():
                doc_field = config['field']
                status_field = config['status_field']
                expiry_field = config.get('expiry_field')
                validation_field = config.get('validation_field')
                
                doc_content = getattr(partner, doc_field, None)
                
                # STATE: No document = missing
                if not doc_content:
                    setattr(partner, status_field, 'missing')
                    continue
                
                # STATE: Check validation flag first
                is_validated = getattr(partner, validation_field, False) if validation_field else False
                
                # If document has expiry, check it
                if expiry_field:
                    expiry_date = getattr(partner, expiry_field, None)
                    
                    # Expiry checks (override validation if expired)
                    if expiry_date and expiry_date < today:
                        setattr(partner, status_field, 'expired')
                    elif not is_validated:
                        # Not validated yet = to_check
                        setattr(partner, status_field, 'to_check')
                    elif expiry_date and expiry_date <= warning_threshold:
                        setattr(partner, status_field, 'expiring')
                    elif not expiry_date:
                        # Validated but no expiry date = to_check (need date)
                        setattr(partner, status_field, 'to_check')
                    else:
                        setattr(partner, status_field, 'valid')
                else:
                    # No expiry field (e.g., RIB): valid only if validated
                    if is_validated:
                        setattr(partner, status_field, 'valid')
                    else:
                        setattr(partner, status_field, 'to_check')
    
    @api.depends(
        'doc_kbis_status', 'doc_urssaf_status',
        'doc_insurance_dec_status', 'doc_cni_status',
        'is_subcontractor'
    )
    def _compute_compliance_state(self):
        """Compute overall compliance state from REQUIRED document statuses only."""
        required_docs = [k for k, v in DOCUMENT_TYPES.items() if v.get('required')]
        for partner in self:
            if not partner.is_subcontractor:
                partner.compliance_state = False
                continue
            
            # Only check required documents
            statuses = []
            for doc_key in required_docs:
                config = DOCUMENT_TYPES[doc_key]
                status = getattr(partner, config['status_field'], 'missing')
                statuses.append(status)
            
            if 'expired' in statuses:
                partner.compliance_state = 'expired'
            elif all(s == 'missing' for s in statuses):
                partner.compliance_state = 'missing'
            elif 'missing' in statuses or 'rejected' in statuses or 'to_check' in statuses:
                partner.compliance_state = 'incomplete'
            else:
                partner.compliance_state = 'compliant'
    
    @api.depends(
        'doc_kbis_status', 'doc_urssaf_status',
        'doc_insurance_dec_status', 'doc_cni_status',
        'doc_kbis_expiry', 'doc_urssaf_expiry',
        'doc_insurance_dec_expiry', 'doc_cni_expiry'
    )
    def _compute_alert_level(self):
        """Compute alert level based on document status and expiry thresholds.
        
        Alert Level Logic (SAP-style state machine):
        - False: No documents present yet (nothing to alert on)
        - 'green': All OK (documents valid, >30 days remaining)
        - 'yellow': Warning (7-30 days remaining before expiry)
        - 'red': Critical (<7 days remaining or expired)
        
        Note: Missing documents are NOT in alert scope - they are tracked
        via compliance_state. Alert level only applies to existing documents.
        """
        today = date.today()
        yellow_threshold = today + timedelta(days=EXPIRY_WARNING_DAYS)
        red_threshold = today + timedelta(days=EXPIRY_CRITICAL_DAYS)
        
        required_docs = [k for k, v in DOCUMENT_TYPES.items() if v.get('required') and v.get('has_expiry')]
        
        for partner in self:
            if not partner.is_subcontractor:
                partner.alert_level = False
                continue
            
            # STATE: Check if any required documents are missing
            # If missing, alert level is not applicable (use compliance_state instead)
            has_any_doc = False
            has_missing = False
            
            for doc_key in required_docs:
                config = DOCUMENT_TYPES[doc_key]
                status = getattr(partner, config['status_field'], 'missing')
                if status == 'missing':
                    has_missing = True
                else:
                    has_any_doc = True
            
            # No documents at all = no alert level displayed
            if not has_any_doc:
                partner.alert_level = False
                continue
            
            # STATE: Evaluate expiry levels for existing documents
            has_expired = False
            has_critical = False
            has_warning = False
            
            for doc_key in required_docs:
                config = DOCUMENT_TYPES[doc_key]
                status = getattr(partner, config['status_field'], 'missing')
                expiry = getattr(partner, config['expiry_field'], None) if config.get('expiry_field') else None
                
                # Skip missing documents (already handled by compliance_state)
                if status == 'missing':
                    continue
                
                if status == 'expired':
                    has_expired = True
                elif expiry and expiry <= red_threshold:
                    has_critical = True
                elif status == 'expiring' or (expiry and expiry <= yellow_threshold):
                    has_warning = True
            
            # STATE MACHINE: Determine final alert level
            if has_expired or has_critical:
                partner.alert_level = 'red'
            elif has_warning:
                partner.alert_level = 'yellow'
            else:
                partner.alert_level = 'green'
    
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
        """Send the upload link via email."""
        self.ensure_one()
        if not self.upload_token:
            self.action_generate_upload_link()
            
        template = self.env.ref('construction_subcontractor.email_template_subcontractor_compliance_enterprise')
        if template:
            template.send_mail(self.id, force_send=True)
            
            self.message_post(
                body=_("📧 Demande de mise à jour envoyée par email à %s") % self.email,
                message_type='comment'
            )
            
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Succès"),
                'message': _("Email de demande envoyé."),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_send_upload_sms(self):
        """Send the upload link via SMS."""
        self.ensure_one()
        if not self.mobile:
            raise UserError(_("Veuillez renseigner un numéro de mobile pour ce partenaire."))
            
        if not self.upload_token:
            self.action_generate_upload_link()
            
        # Short message for SMS
        message = _("BLG Groupe: Veuillez mettre à jour vos documents de sous-traitance sur votre espace sécurisé: %s") % self.upload_url
        
        # Use Odoo's SMS composer if available, or simpler fallback
        # Here we mimic opening the SMS composer with pre-filled body
        return {
            'type': 'ir.actions.act_window',
            'name': 'Envoyer SMS',
            'res_model': 'sms.composer',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_res_model': 'res.partner',
                'default_res_id': self.id,
                'default_composition_mode': 'comment', # Or 'mass'
                'default_body': message,
                'default_recipient_single_number_itf': self.mobile,
            }
        }
    
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
    
    def action_open_validation_wizard(self, doc_type=None):
        """Open document validation wizard for a specific document type.
        
        Args:
            doc_type: Document type key (kbis, urssaf, etc.)
                     Can also be passed via context as 'default_doc_type'
        
        Returns:
            Action to open validation wizard
        """
        self.ensure_one()
        
        # Get doc_type from parameter or context
        if not doc_type:
            doc_type = self.env.context.get('default_doc_type')
        
        if not doc_type:
            raise UserError(_("Type de document non spécifié."))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Validation Document'),
            'res_model': 'document.validation.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_partner_id': self.id,
                'default_doc_type': doc_type,
            }
        }
    
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
    
    def action_view_archives(self):
        """Open archived documents for this subcontractor."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Documents Archivés - %s') % self.name,
            'res_model': 'subcontractor.document.archive',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }
    
    def action_check_document_expiry(self):
        """Manually trigger document expiration check (admin only)."""
        self.ensure_one()
        # Recompute status fields (they check expiry dates)
        self._compute_document_statuses()
        self._compute_compliance_state()
        
        # Log the manual check
        self.message_post(
            body=_("Verification manuelle des expirations declenchee par %s") % self.env.user.name,
            message_type='notification'
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Verification effectuee'),
                'message': _('Etat de conformite: %s') % dict(self._fields['compliance_state'].selection).get(self.compliance_state, 'Inconnu'),
                'type': 'info',
                'sticky': False,
            }
        }
    
    def action_request_document(self):
        """Re-request a document based on context 'doc_type'.
        
        Archives current document, clears field, and sends notification.
        """
        self.ensure_one()
        doc_type = self.env.context.get('doc_type')
        if not doc_type or doc_type not in DOCUMENT_TYPES:
            raise UserError(_("Type de document non spécifié ou invalide."))
            
        config = DOCUMENT_TYPES[doc_type]
        field_name = config['field']
        doc_name = config['name']
        
        # Archive current document using the helper
        self._archive_document(self, doc_type, config, 'requested', None)
        
        # Clear the document fields
        self.write({
            field_name: False,
            f'{field_name}_filename': False,
            f'{field_name}_is_validated': False,
            f'{field_name}_validated_by': False,
            f'{field_name}_validated_at': False,
        })
        
        # Log in chatter
        self.message_post(
            body=_("🔄 Document <b>%s</b> redemandé par %s. En attente de nouveau document.") % (
                doc_name,
                self.env.user.name
            ),
            message_type='notification'
        )
        
        # Send notification email
        self._send_request_notification(doc_name)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Document Redemandé'),
                'message': _('Le sous-traitant a été notifié.'),
                'type': 'success',
                'sticky': False,
            }
        }

    def _send_request_notification(self, doc_name):
        """Send email notification to subcontractor about document re-request."""
        if not self.email:
            return
        
        template = self.env.ref('construction_subcontractor.email_template_document_request', raise_if_not_found=False)
        if template:
            template.with_context(doc_name=doc_name).send_mail(self.id, force_send=True)
        else:
            # Fallback activity
            self.env['mail.activity'].create({
                'res_model_id': self.env['ir.model']._get('res.partner').id,
                'res_id': self.id,
                'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                'summary': _("Envoyer demande: %s") % doc_name,
                'note': _("Envoyer email manuel pour demander: %s") % doc_name,
                'user_id': self.env.user.id,
            })

    # ============= DOCUMENT ARCHIVING HELPER ============= #
    
    def _archive_document(self, partner, doc_key, config, reason, replaced_by_filename=None):
        """Helper to archive a document.
        
        Args:
            partner: The res.partner record
            doc_key: Document type key (kbis, urssaf, etc.)
            config: Document type configuration from DOCUMENT_TYPES
            reason: Archive reason (replaced, deleted, requested, rejected)
            replaced_by_filename: Filename of replacement doc if applicable
        """
        field_name = config['field']
        validation_field = config.get('validation_field')
        
        current_file = getattr(partner, field_name)
        if not current_file:
            return
        
        filename = getattr(partner, f'{field_name}_filename') or config['name']
        expiry_date = getattr(partner, config['expiry_field']) if config.get('expiry_field') else False
        
        # Capture validation state
        was_validated = getattr(partner, validation_field, False) if validation_field else False
        validated_by = getattr(partner, f'{field_name}_validated_by', False)
        validated_at = getattr(partner, f'{field_name}_validated_at', False)
        
        self.env['subcontractor.document.archive'].create({
            'partner_id': partner.id,
            'document_type': doc_key,
            'file_data': current_file,
            'filename': filename,
            'expiry_date': expiry_date,
            'replaced_by_user_id': self.env.user.id,
            'reason': reason,
            'replaced_by_filename': replaced_by_filename,
            'was_validated': was_validated,
            'validated_by_name': validated_by.name if validated_by else False,
            'original_validated_at': validated_at,
        })
    
    # ============= WRITE OVERRIDE (Archiving & Automation) ============= #
    
    def write(self, vals):
        """
        Override write to:
        1. Archive old documents before they are replaced.
        2. Auto-update stage based on compliance after changes.
        """
        # 1. Archive old documents and RESET VALIDATION on new upload
        if any(cfg['field'] in vals for cfg in DOCUMENT_TYPES.values()):
            for partner in self:
                for doc_key, config in DOCUMENT_TYPES.items():
                    field_name = config['field']
                    validation_field = config.get('validation_field')
                    
                    # Check if this field is being updated
                    if field_name in vals:
                        current_file = getattr(partner, field_name)
                        new_file = vals[field_name]
                        
                        # Case 1: Uploading new file (replace)
                        if new_file:
                            # CRITICAL: Reset validation state for new uploads
                            if validation_field:
                                vals[validation_field] = False
                                vals[f'{field_name}_validated_by'] = False
                                vals[f'{field_name}_validated_at'] = False
                            
                            # Archive old file if exists and different
                            if current_file and current_file != new_file:
                                self._archive_document(partner, doc_key, config, 'replaced', 
                                                       vals.get(f'{field_name}_filename', 'Nouveau document'))
                        
                        # Case 2: Clearing file (delete)
                        elif current_file and not new_file:
                            self._archive_document(partner, doc_key, config, 'deleted', None)


        # 2. Execute Write
        res = super(ResPartner, self).write(vals)
        
        # 3. Stage Automation
        # Trigger if compliance or docs changed
        # Trigger if compliance or docs changed (including validation)
        trigger_fields = ['compliance_state'] 
        for cfg in DOCUMENT_TYPES.values():
            trigger_fields.append(cfg['field'])
            if 'validation_field' in cfg:
                trigger_fields.append(cfg['validation_field'])
                
        if any(f in vals for f in trigger_fields):
            for partner in self:
                if partner.is_subcontractor:
                    # Auto-advance to compliant if ready
                    if partner.compliance_state == 'compliant' and partner.subcontractor_stage != 'compliant':
                        partner.subcontractor_stage = 'compliant'
                    # Fallback if became incomplete
                    elif partner.compliance_state != 'compliant' and partner.subcontractor_stage in ['compliant', 'bloque']:
                        partner.subcontractor_stage = 'incomplete'
                        
        return res

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
