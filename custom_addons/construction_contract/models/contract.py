# -*- coding: utf-8 -*-
"""
Contract Model
Main model for subcontractor contracts
Handles contract lifecycle, PDF generation, and signature workflow
"""

from odoo import models, fields, api, _, http
from odoo.exceptions import ValidationError, UserError
from datetime import timedelta
import base64
import hashlib
import secrets
import logging

_logger = logging.getLogger(__name__)

COMPLIANT_DOCUMENT_STATUSES = {'valid', 'expiring'}
REQUIRED_DOCUMENTS = [
    ('document_URSSAF_status', 'document_URSSAF', _("URSSAF certificate")),
    ('document_KBIS_status', 'document_KBIS', _("KBIS extract")),
    ('document_insurance_status', 'document_insurance', _("Insurance certificate")),
]
GLOBAL_STATUS_FIELDS = [
    'document_identity_card_status',
    'document_URSSAF_status',
    'document_KBIS_status',
    'document_insurance_status',
    'document_RIB_status',
]

# Import constants
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config.contract_constants import (
    CONTRACT_STATES,
    AUTHENTICATION_METHODS,
    TOKEN_EXPIRY_DAYS,
    DEFAULT_RETENTION_RATE,
)


class ConstructionContract(models.Model):
    """
    Construction Subcontractor Contract

    Manages the complete lifecycle of a subcontractor contract:
    - Creation and validation
    - PDF generation from editable templates
    - Electronic signature workflow
    - Legal compliance and archiving
    """

    _name = 'construction.contract'
    _description = 'Construction Subcontractor Contract'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = 'date desc, id desc'
    _rec_name = 'name'

    # ============================================================
    # BASIC INFORMATION
    # ============================================================

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        help="Unique contract reference (auto-generated)"
    )

    state = fields.Selection(
        selection=CONTRACT_STATES,
        string='Status',
        default='draft',
        required=True,
        tracking=True,
        help="Contract workflow state"
    )

    active = fields.Boolean(
        default=True,
        help="Uncheck to archive the contract"
    )

    # ============================================================
    # RELATIONS TO OTHER MODULES
    # ============================================================

    chantier_id = fields.Many2one(
        'construction.chantier',
        string='Construction Site',
        required=True,
        tracking=True,
        ondelete='restrict',
        help="Related construction site (from construction_base)"
    )

    subcontractor_id = fields.Many2one(
        'res.partner',
        string='Subcontractor',
        required=True,
        tracking=True,
        domain="[('contact_type', '=', 'sous_traitant')]",
        help="Subcontractor company (from blg_contacts_extension)"
    )

    lot_ids = fields.Many2many(
        'construction.lot',
        'construction_contract_lot_rel',
        'contract_id',
        'lot_id',
        string='Lots',
        domain="[('chantier_id', '=', chantier_id)]",
        help="Construction lots included in this contract"
    )

    # ============================================================
    # DATES
    # ============================================================

    date = fields.Date(
        string='Contract Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True,
        help="Official contract signing date"
    )

    start_date = fields.Date(
        string='Work Start Date',
        required=True,
        tracking=True,
        help="Scheduled start date for work execution"
    )

    end_date = fields.Date(
        string='Work End Date',
        required=True,
        tracking=True,
        help="Scheduled completion date for work"
    )

    sent_date = fields.Datetime(
        string='Sent Date',
        readonly=True,
        help="Date when contract was sent to subcontractor"
    )

    signature_date = fields.Datetime(
        string='Signature Date',
        readonly=True,
        tracking=True,
        help="Date when contract was electronically signed"
    )

    # ============================================================
    # FINANCIAL DATA
    # ============================================================

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
        required=True
    )

    total_amount_ht = fields.Monetary(
        string='Amount Exc. VAT',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id',
        help="Total amount excluding VAT"
    )

    total_amount_tva = fields.Monetary(
        string='VAT Amount',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id',
        help="Total VAT amount"
    )

    total_amount_ttc = fields.Monetary(
        string='Amount Inc. VAT',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id',
        help="Total amount including VAT"
    )

    retention_rate = fields.Float(
        string='Retention Rate (%)',
        default=DEFAULT_RETENTION_RATE,
        help="Guarantee retention percentage (default 5% for French construction)"
    )

    retention_amount = fields.Monetary(
        string='Retention Amount',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id',
        help="Amount withheld as guarantee (retenue de garantie)"
    )

    # Related purchase orders
    purchase_order_ids = fields.Many2many(
        'purchase.order',
        compute='_compute_purchase_orders',
        store=True,
        string='Related Purchase Orders',
        help="Purchase orders linked to selected lots and subcontractor"
    )
    
    purchase_order_count = fields.Integer(
        string='Purchase Order Count',
        compute='_compute_purchase_orders',
        store=True
    )

    # ============================================================
    # TEMPLATE & PDF GENERATION
    # ============================================================

    template_id = fields.Many2one(
        'construction.contract.template',
        string='Contract Template',
        required=True,
        default=lambda self: self.env.ref(
            'construction_contract.default_contract_template',
            raise_if_not_found=False
        ),
        help="Template used to generate the contract PDF"
    )

    pdf_document = fields.Binary(
        string='PDF Document',
        attachment=True,
        help="Generated contract PDF file"
    )

    pdf_filename = fields.Char(
        string='PDF Filename',
        compute='_compute_pdf_filename',
        help="Name of the PDF file"
    )

    pdf_hash_before_signature = fields.Char(
        string='PDF Hash (Before Signature)',
        readonly=True,
        help="SHA-256 hash of PDF before signature (for integrity check)"
    )

    pdf_hash_after_signature = fields.Char(
        string='PDF Hash (After Signature)',
        readonly=True,
        help="SHA-256 hash of PDF after signature (for legal proof)"
    )

    pdf_page_count = fields.Integer(
        string='PDF Page Count',
        compute='_compute_pdf_page_count',
        store=True,
        help="Number of pages in the PDF (for validation workflow)"
    )

    custom_html_override = fields.Html(
        string='Custom HTML Override',
        sanitize=False,
        help="Manually edited HTML used instead of template rendering"
    )

    # ============================================================
    # DELIVERABLES
    # ============================================================

    deliverable_ids = fields.One2many(
        'construction.contract.deliverable',
        'contract_id',
        string='Deliverables',
        help="Documents and deliverables attached to this contract"
    )

    # ============================================================
    # SIGNATURE WORKFLOW
    # ============================================================

    signature_id = fields.Many2one(
        'construction.contract.signature',
        string='Electronic Signature',
        readonly=True,
        help="Electronic signature record"
    )

    access_token = fields.Char(
        string='Portal Access Token',
        copy=False,
        index=True,
        help="Unique token for secure portal access"
    )
    portal_url = fields.Char(
        string='Portal URL',
        compute='_compute_portal_url',
        help="Full URL for accessing the contract signature portal"
    )

    token_expiry_date = fields.Datetime(
        string='Token Expiry Date',
        compute='_compute_token_expiry',
        store=True,
        help="Date when portal access token expires"
    )

    page_validation_ids = fields.One2many(
        'construction.contract.page.validation',
        'contract_id',
        string='Page Validations',
        help="Track which pages have been validated by the signer"
    )

    certificate_of_completion = fields.Binary(
        string='Certificate of Completion',
        attachment=True,
        help="Legal proof certificate with signature details"
    )

    certificate_filename = fields.Char(
        compute='_compute_certificate_filename',
        help="Name of the certificate file"
    )

    # ============================================================
    # NOTIFICATIONS
    # ============================================================

    email_sent = fields.Boolean(
        string='Email Sent',
        default=False,
        help="True if invitation email has been sent"
    )

    sms_sent = fields.Boolean(
        string='SMS Sent',
        default=False,
        help="True if invitation SMS has been sent"
    )

    last_reminder_date = fields.Datetime(
        string='Last Reminder Date',
        help="Date of last reminder sent to subcontractor"
    )

    # ============================================================
    # COMPUTED FIELDS
    # ============================================================

    @api.depends('lot_ids', 'subcontractor_id', 'retention_rate')
    def _compute_amounts(self):
        """
        Compute all financial amounts from related purchase orders
        Filters POs by selected lots and subcontractor
        """
        for contract in self:
            # Get all purchase orders for this subcontractor in selected lots
            purchase_orders = self.env['purchase.order'].search([
                ('lot_ids', 'in', contract.lot_ids.ids),
                ('partner_id', '=', contract.subcontractor_id.id),
                ('state', 'in', ['purchase', 'done']),  # Only confirmed POs
            ])

            # Sum amounts
            amount_ht = sum(purchase_orders.mapped('amount_untaxed'))
            amount_tva = sum(purchase_orders.mapped('amount_tax'))
            amount_ttc = sum(purchase_orders.mapped('amount_total'))

            # Calculate retention
            retention = amount_ttc * (contract.retention_rate / 100.0)

            contract.write({
                'total_amount_ht': amount_ht,
                'total_amount_tva': amount_tva,
                'total_amount_ttc': amount_ttc,
                'retention_amount': retention,
            })

    @api.depends('lot_ids', 'subcontractor_id')
    def _compute_purchase_orders(self):
        """Fetch related purchase orders"""
        for contract in self:
            if contract.lot_ids and contract.subcontractor_id:
                contract.purchase_order_ids = self.env['purchase.order'].search([
                    ('lot_ids', 'in', contract.lot_ids.ids),
                    ('partner_id', '=', contract.subcontractor_id.id),
                ])
                contract.purchase_order_count = len(contract.purchase_order_ids)
            else:
                contract.purchase_order_ids = False
                contract.purchase_order_count = 0

    @api.depends('name')
    def _compute_pdf_filename(self):
        """Generate PDF filename from contract reference"""
        for contract in self:
            if contract.name and contract.name != _('New'):
                contract.pdf_filename = f"{contract.name.replace('/', '_')}_contract.pdf"
            else:
                contract.pdf_filename = 'contract.pdf'

    @api.depends('name')
    def _compute_certificate_filename(self):
        """Generate certificate filename"""
        for contract in self:
            if contract.name and contract.name != _('New'):
                contract.certificate_filename = f"{contract.name.replace('/', '_')}_certificate.pdf"
            else:
                contract.certificate_filename = 'certificate.pdf'

    @api.depends('access_token')
    def _compute_portal_url(self):
        """
        Generate the full portal URL for contract signature
        """
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for record in self:
            if record.id and record.access_token:
                record.portal_url = f"{base_url}/my/contract/{record.id}/sign?access_token={record.access_token}"
            else:
                record.portal_url = False

    @api.depends('pdf_document')
    def _compute_pdf_page_count(self):
        """Count PDF pages using PyPDF2"""
        for contract in self:
            if contract.pdf_document:
                try:
                    from PyPDF2 import PdfReader
                    import io

                    pdf_data = base64.b64decode(contract.pdf_document)
                    pdf_file = io.BytesIO(pdf_data)
                    reader = PdfReader(pdf_file)
                    contract.pdf_page_count = len(reader.pages)

                except Exception as e:
                    _logger.error(f"Error counting PDF pages for contract {contract.name}: {e}")
                    contract.pdf_page_count = 0
            else:
                contract.pdf_page_count = 0

    @api.depends('sent_date')
    def _compute_token_expiry(self):
        """Calculate token expiry date"""
        for contract in self:
            if contract.sent_date:
                contract.token_expiry_date = contract.sent_date + timedelta(days=TOKEN_EXPIRY_DAYS)
            else:
                contract.token_expiry_date = False

    # ============================================================
    # CRUD METHODS
    # ============================================================

    @api.model
    def create(self, vals):
        """
        Override create to generate sequence number and access token
        """
        # Generate contract reference from sequence
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code(
                'construction.contract'
            ) or _('New')

        # Generate secure access token for portal
        if not vals.get('access_token'):
            vals['access_token'] = self._generate_access_token()

        contract = super(ConstructionContract, self).create(vals)

        # Subscribe followers
        contract.message_subscribe(partner_ids=[contract.subcontractor_id.id])

        # Update template contract count
        if contract.template_id:
            contract.template_id._compute_contract_count()

        return contract

    def write(self, vals):
        """Override write to track important changes"""
        # Track old template_id if it's being changed
        old_templates = {}
        if 'template_id' in vals:
            for contract in self:
                old_templates[contract.id] = contract.template_id

        result = super(ConstructionContract, self).write(vals)

        # Log important state changes
        if 'state' in vals:
            for contract in self:
                contract.message_post(
                    body=_("Contract state changed to: %s") % dict(CONTRACT_STATES).get(vals['state']),
                    message_type='notification'
                )

        # Update template contract counts if template changed
        if 'template_id' in vals:
            templates_to_update = set()
            for contract in self:
                # Add old template
                if contract.id in old_templates and old_templates[contract.id]:
                    templates_to_update.add(old_templates[contract.id])
                # Add new template
                if contract.template_id:
                    templates_to_update.add(contract.template_id)
            
            # Update all affected templates
            for template in templates_to_update:
                template._compute_contract_count()

        return result

    def unlink(self):
        """Prevent deletion of signed contracts"""
        # Store templates before deletion
        templates_to_update = set()
        for contract in self:
            if contract.state == 'signed':
                raise UserError(_("Cannot delete a signed contract. Archive it instead."))
            if contract.template_id:
                templates_to_update.add(contract.template_id)
        
        result = super(ConstructionContract, self).unlink()
        
        # Update template contract counts
        for template in templates_to_update:
            template._compute_contract_count()
        
        return result

    # ============================================================
    # CONSTRAINTS & VALIDATIONS
    # ============================================================

    @api.constrains('chantier_id', 'lot_ids')
    def _check_lots_belong_to_chantier(self):
        """Ensure all selected lots belong to the selected construction site"""
        for contract in self:
            if contract.lot_ids:
                chantier_lots = contract.chantier_id.lots_ids
                invalid_lots = contract.lot_ids - chantier_lots

                if invalid_lots:
                    raise ValidationError(_(
                        "The following lots do not belong to construction site '%s':\n%s"
                    ) % (
                                              contract.chantier_id.name,
                                              ', '.join(invalid_lots.mapped('name'))
                                          ))

    @api.constrains('subcontractor_id')
    def _check_subcontractor_documents(self):
        """Validate that subcontractor has all required documents (from blg_contacts_extension)"""
        for contract in self:
            partner = contract.subcontractor_id
            self._ensure_subcontractor_documents_compliant(partner)
            if not (getattr(partner, 'siren', False) or partner.company_registry):
                raise ValidationError(_(
                    "Subcontractor '%s' must have a SIRET number before creating a contract."
                ) % partner.name)

    def _ensure_subcontractor_documents_compliant(self, partner):
        """Shared helper to validate subcontractor document statuses."""
        for status_field, content_field, label in REQUIRED_DOCUMENTS:
            status_value = getattr(partner, status_field, False)
            selection = dict(partner._fields[status_field].selection) if status_field in partner._fields else {}
            human_status = selection.get(status_value, status_value or _('Unknown'))
            if status_value not in COMPLIANT_DOCUMENT_STATUSES:
                raise ValidationError(_(
                    "Subcontractor '%(name)s' does not have a compliant %(document)s.\n"
                    "Status: %(status)s"
                ) % {
                    'name': partner.name,
                    'document': label,
                    'status': human_status,
                })
            if not getattr(partner, content_field):
                raise ValidationError(_(
                    "Subcontractor '%(name)s' is missing the %(document)s file."
                ) % {
                    'name': partner.name,
                    'document': label,
                })

    @api.constrains('start_date', 'end_date')
    def _check_dates_logic(self):
        """Ensure end date is after start date"""
        for contract in self:
            if contract.start_date and contract.end_date:
                if contract.end_date < contract.start_date:
                    raise ValidationError(_("End date must be after start date."))

    @api.constrains('retention_rate')
    def _check_retention_rate(self):
        """Validate retention rate is reasonable"""
        for contract in self:
            if contract.retention_rate < 0 or contract.retention_rate > 20:
                raise ValidationError(_("Retention rate must be between 0% and 20%."))

    # ============================================================
    # BUSINESS METHODS
    # ============================================================

    @api.model
    def _generate_access_token(self):
        """
        Generate a secure random token for portal access

        Returns:
            str: 32-character URL-safe token
        """
        return secrets.token_urlsafe(32)

    def _is_token_expired(self, token):
        """
        Check if portal access token is expired

        Args:
            token (str): Token to validate

        Returns:
            bool: True if expired or invalid
        """
        self.ensure_one()

        # Check token match
        if self.access_token != token:
            return True

        # Check expiry date
        if self.token_expiry_date and self.token_expiry_date < fields.Datetime.now():
            return True

        return False

    def _get_page_validation_status(self, token):
        """
        Get validation status for all pages

        Args:
            token (str): Access token

        Returns:
            dict: Validation status with validated pages and remaining pages
        """
        self.ensure_one()

        validations = self.page_validation_ids.filtered(
            lambda v: v.access_token == token
        )

        validated_pages = validations.mapped('page_number')

        return {
            'validated_pages': sorted(validated_pages),
            'total_pages': self.pdf_page_count,
            'remaining_pages': self.pdf_page_count - len(validated_pages),
            'can_sign': len(validated_pages) >= self.pdf_page_count,
            'completion_rate': (len(validated_pages) / self.pdf_page_count * 100) if self.pdf_page_count else 0,
        }

    def _get_subcontractor_documents_status(self):
        """
        Get subcontractor document validation status
        Uses data from blg_contacts_extension

        Returns:
            dict: Document status summary
        """
        self.ensure_one()

        partner = self.subcontractor_id

        return {
            'global_status': self._get_partner_global_status(partner),
            'siret': getattr(partner, 'siren', False) or partner.company_registry,
            'urssaf': {
                'status': partner.document_URSSAF_status,
                'expiry': partner.document_URSSAF_expiry,
                'has_file': bool(partner.document_URSSAF),
            },
            'kbis': {
                'status': partner.document_KBIS_status,
                'expiry': partner.document_KBIS_expiry,
                'has_file': bool(partner.document_KBIS),
            },
            'insurance': {
                'status': partner.document_insurance_status,
                'expiry': partner.document_insurance_expiry,
                'has_file': bool(partner.document_insurance),
            },
            'rib': {
                'status': getattr(partner, 'document_RIB_status', partner.document_RIB_manual_status),
                'has_file': bool(partner.document_RIB),
            },
        }

    def _get_partner_global_status(self, partner):
        """Compute a synthetic status based on the most critical document state."""
        severity_order = ['expired', 'rejected', 'missing', 'to_check', 'expiring', 'valid']
        statuses = []
        for field_name in GLOBAL_STATUS_FIELDS:
            if hasattr(partner, field_name):
                statuses.append(getattr(partner, field_name))
        for status in severity_order:
            if status in statuses:
                return status
        return 'missing'

    # ============================================================
    # ACTION METHODS (Buttons)
    # ============================================================

    def action_generate_pdf(self):
        """
        Generate PDF from template using Jinja2
        Delegates to PDF generation service
        Includes company signature (from Odoo or default file) in the PDF
        Merges with deliverable attachments if configured
        """
        self.ensure_one()

        if self.state not in ['draft', 'generated']:
            raise UserError(_("PDF can only be generated in Draft or Generated state."))

        # Call PDF generation service
        # Company signature will be automatically loaded by template renderer
        pdf_service = self.env['construction.contract.pdf.generator']
        pdf_service.generate_pdf(self)
        
        _logger.info(f"PDF generated for contract {self.name}, state={self.state}, has_pdf={bool(self.pdf_document)}")

        # Check if there are deliverables to merge
        deliverables_to_merge = self.deliverable_ids.filtered(
            lambda d: d.merge_in_contract and d.document
        )
        
        if deliverables_to_merge:
            _logger.info(
                f"Merging {len(deliverables_to_merge)} deliverables into contract {self.name}: "
                f"{', '.join(deliverables_to_merge.mapped('name'))}"
            )
            
            try:
                # Call PDF merger service
                merger_service = self.env['construction.contract.pdf.merger']
                merged_pdf = merger_service.merge_contract_with_attachments(self)
                
                # Update contract with merged PDF
                self.write({
                    'pdf_document': base64.b64encode(merged_pdf)
                })
                
                _logger.info(f"✓ PDF merged successfully for contract {self.name}")
                
                self.message_post(
                    body=_("Contract PDF generated and merged with %d attachments.") % len(deliverables_to_merge),
                    message_type='notification'
                )
            except Exception as e:
                _logger.error(f"PDF merge failed for contract {self.name}: {e}", exc_info=True)
                # Don't fail the whole generation, just warn
                self.message_post(
                    body=_("Contract PDF generated but merge failed: %s") % str(e),
                    message_type='notification'
                )
        else:
            self.message_post(
                body=_("Contract PDF generated successfully."),
                message_type='notification'
            )

        # Only change state if currently draft
        if self.state == 'draft':
            self.write({'state': 'generated'})

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Contract PDF generated successfully.'),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_regenerate_pdf(self):
        """Regenerate PDF (e.g., after template changes)"""
        self.ensure_one()

        # Reset state to draft temporarily
        old_state = self.state
        self.state = 'draft'

        # Regenerate
        self.action_generate_pdf()

        # Restore state if it was not draft
        if old_state != 'draft':
            self.state = old_state

        return True

    def action_send_for_signature(self):
        """
        Send contract to subcontractor for signature
        Sends email and SMS with portal link
        """
        self.ensure_one()

        if self.state != 'generated':
            raise UserError(_("Contract must be generated before sending."))

        if not self.pdf_document:
            raise UserError(_("No PDF document to send. Generate PDF first."))

        # Call notification service
        notification_service = self.env['construction.contract.notification']
        notification_service.send_contract_invitation(self)

        # Update state
        self.write({
            'state': 'sent',
            'sent_date': fields.Datetime.now(),
        })

        self.message_post(
            body=_("Contract sent to %s via email and SMS.") % self.subcontractor_id.name,
            message_type='notification'
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sent'),
                'message': _('Contract sent to subcontractor successfully.'),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_send_reminder(self):
        """Send reminder to subcontractor"""
        self.ensure_one()

        if self.state not in ['sent', 'in_progress']:
            raise UserError(_("Reminder can only be sent for contracts in 'Sent' or 'In Progress' state."))

        notification_service = self.env['construction.contract.notification']
        notification_service.send_reminder(self)

        self.last_reminder_date = fields.Datetime.now()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Reminder Sent'),
                'message': _('Reminder sent to subcontractor.'),
                'type': 'info',
            }
        }

    def action_mark_in_progress(self):
        """Mark contract as signature in progress (when subcontractor starts reading)"""
        self.ensure_one()

        if self.state == 'sent':
            self.state = 'in_progress'

            self.message_post(
                body=_("Subcontractor started reading the contract."),
                message_type='notification'
            )

    def action_mark_signed(self):
        """
        Mark contract as signed (called after successful signature)
        Generate certificate of completion and regenerate PDF with signature
        """
        self.ensure_one()

        if self.state not in ['in_progress']:
            raise UserError(_("Contract must be in 'In Progress' state to be signed."))

        # Regenerate PDF with BOTH signatures (company + subcontractor) included in HTML template
        _logger.info(f"Regenerating PDF with both signatures for contract {self.name}")
        # Get subcontractor signature from context (passed during signature save) or from contract
        subcontractor_signature = self.env.context.get('contract_signature') or self.signature_id
        
        if not subcontractor_signature:
            _logger.error(f"No subcontractor signature found for contract {self.name} - cannot regenerate PDF")
            raise UserError(_("Subcontractor signature not found. Cannot regenerate PDF."))
        
        # Generate PDF with subcontractor signature in context
        # Company signature will be automatically loaded by template renderer
        pdf_service = self.env['construction.contract.pdf.generator']
        pdf_service.with_context(contract_signature=subcontractor_signature).generate_pdf(self)
        
        # Verify PDF was regenerated
        if not self.pdf_document:
            _logger.error(f"PDF regeneration failed for contract {self.name} - no PDF document after generation")
            raise UserError(_("PDF regeneration failed. Please try again."))
        
        # Calculate hash after signature for integrity
        import hashlib
        pdf_content = base64.b64decode(self.pdf_document)
        pdf_hash_after = hashlib.sha256(pdf_content).hexdigest()
        self.write({
            'pdf_hash_after_signature': pdf_hash_after
        })
        _logger.info(f"PDF regenerated successfully with both signatures for contract {self.name}, hash: {pdf_hash_after[:16]}..., size: {len(pdf_content)/1024:.1f} KB")

        # Generate certificate of completion
        self._generate_certificate_of_completion()

        # Update state
        self.write({
            'state': 'signed',
            'signature_date': fields.Datetime.now(),
        })

        # Notify stakeholders
        self.message_post(
            body=_("Contract signed by %s on %s.") % (
                self.subcontractor_id.name,
                fields.Datetime.now().strftime('%d/%m/%Y %H:%M')
            ),
            message_type='notification',
            subtype_xmlid='mail.mt_note',
        )

        # Send confirmation email
        self.env.ref('construction_contract.mail_template_contract_signed').send_mail(self.id)

        return True

    def action_cancel(self):
        """Cancel the contract"""
        self.ensure_one()

        if self.state == 'signed':
            raise UserError(_("Cannot cancel a signed contract."))

        self.state = 'cancelled'

        self.message_post(
            body=_("Contract cancelled."),
            message_type='notification'
        )

    def action_archive(self):
        """Archive the contract"""
        self.ensure_one()

        if self.state != 'signed':
            raise UserError(_("Only signed contracts can be archived."))

        self.write({
            'state': 'archived',
            'active': False,
        })

    def action_download_pdf(self):
        """Download contract PDF"""
        self.ensure_one()

        if not self.pdf_document:
            raise UserError(_("No PDF document available."))

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/construction.contract/{self.id}/pdf_document/{self.pdf_filename}?download=true',
            'target': 'self',
        }

    def action_download_certificate(self):
        """Download certificate of completion"""
        self.ensure_one()

        if not self.certificate_of_completion:
            raise UserError(_("No certificate available."))

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/construction.contract/{self.id}/certificate_of_completion/{self.certificate_filename}?download=true',
            'target': 'self',
        }

    def action_view_portal(self):
        """Open contract in portal view (for testing)"""
        self.ensure_one()

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        portal_url = f"{base_url}/my/contract/{self.id}/sign?access_token={self.access_token}"

        return {
            'type': 'ir.actions.act_url',
            'url': portal_url,
            'target': 'new',
        }

    def action_view_deliverables(self):
        """Open deliverables view"""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': _('Contract Deliverables'),
            'res_model': 'construction.contract.deliverable',
            'view_mode': 'list,form',
            'domain': [('contract_id', '=', self.id)],
            'context': {'default_contract_id': self.id},
        }

    def action_view_purchase_orders(self):
        """Open related purchase orders"""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Orders'),
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.purchase_order_ids.ids)],
        }

    def action_view_signature_details(self):
        """View signature details"""
        self.ensure_one()

        if not self.signature_id:
            raise UserError(_("No signature record available."))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Signature Details'),
            'res_model': 'construction.contract.signature',
            'res_id': self.signature_id.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_generate_merged_pdf(self):
        """
        Generate merged PDF with all deliverables marked for merging.
        This action can be called independently to merge documents after
        the initial PDF has been generated.
        
        Returns:
            dict: Client action to display success notification with page count
        """
        self.ensure_one()

        if not self.pdf_document:
            raise UserError(_(
                "❌ PDF du contrat manquant\n\n"
                "Le PDF du contrat principal doit être généré avant "
                "de fusionner les documents annexes.\n\n"
                "Cliquez d'abord sur 'Générer le PDF' pour créer le contrat."
            ))

        # Get deliverables to merge
        deliverables_to_merge = self.deliverable_ids.filtered(
            lambda d: d.merge_in_contract and d.document
        )

        if not deliverables_to_merge:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Information'),
                    'message': _("Aucun document à fusionner. Cochez 'Fusionner dans le contrat' sur les documents à inclure."),
                    'type': 'warning',
                    'sticky': False,
                }
            }

        _logger.info(
            f"Generating merged PDF for contract {self.name} with "
            f"{len(deliverables_to_merge)} deliverables: "
            f"{', '.join(deliverables_to_merge.mapped('name'))}"
        )

        try:
            # Call PDF merger service
            merger_service = self.env['construction.contract.pdf.merger']
            merged_pdf = merger_service.merge_contract_with_attachments(self)

            # Get page count before updating
            from PyPDF2 import PdfReader
            import io
            reader = PdfReader(io.BytesIO(merged_pdf))
            page_count = len(reader.pages)

            # Update contract with merged PDF
            self.write({
                'pdf_document': base64.b64encode(merged_pdf)
            })

            _logger.info(
                f"✓ Merged PDF generated for contract {self.name}: "
                f"{page_count} pages, {len(merged_pdf)/1024:.1f} KB"
            )

            self.message_post(
                body=_("PDF fusionné généré avec %d documents annexes (%d pages au total).") % (
                    len(deliverables_to_merge),
                    page_count
                ),
                message_type='notification'
            )

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Succès'),
                    'message': _("PDF fusionné généré avec succès !\n%d documents annexes inclus.\nTotal : %d pages.") % (
                        len(deliverables_to_merge),
                        page_count
                    ),
                    'type': 'success',
                    'sticky': False,
                }
            }

        except UserError:
            # Re-raise UserError as-is (already has user-friendly message)
            raise
        except Exception as e:
            _logger.error(
                f"PDF merge failed for contract {self.name}: {e}",
                exc_info=True
            )
            raise UserError(_(
                "❌ Erreur lors de la fusion des documents\n\n"
                "Une erreur s'est produite lors de la fusion des PDF.\n\n"
                "Détails : %s\n\n"
                "Veuillez vérifier que tous les documents sont des PDF valides."
            ) % str(e))

    # ============================================================
    # SUMMARY VIEW NOTIFICATION ACTIONS
    # ============================================================

    def action_send_portal_email(self):
        """
        Send portal link via email only.
        Called from the post-creation summary view.
        """
        self.ensure_one()

        if self.state not in ['generated', 'sent', 'in_progress']:
            raise UserError(_("Le contrat doit être généré avant d'envoyer l'invitation."))

        if not self.pdf_document:
            raise UserError(_("Aucun document PDF disponible. Veuillez d'abord générer le PDF."))

        notification_service = self.env['construction.contract.notification']
        
        try:
            notification_service._send_email_invitation(self)
            self.email_sent = True
            
            # Update state to sent if still in generated state
            if self.state == 'generated':
                self.write({
                    'state': 'sent',
                    'sent_date': fields.Datetime.now(),
                })

            self.message_post(
                body=_("Invitation envoyée par e-mail à %s.") % self.subcontractor_id.name,
                message_type='notification'
            )

            return self._show_notification_success('e-mail')

        except Exception as e:
            _logger.error(f"Failed to send email for contract {self.name}: {e}", exc_info=True)
            raise UserError(_("Erreur lors de l'envoi de l'e-mail : %s") % str(e))

    def action_send_portal_sms(self):
        """
        Send portal link via SMS only.
        Called from the post-creation summary view.
        """
        self.ensure_one()

        if self.state not in ['generated', 'sent', 'in_progress']:
            raise UserError(_("Le contrat doit être généré avant d'envoyer l'invitation."))

        if not self.pdf_document:
            raise UserError(_("Aucun document PDF disponible. Veuillez d'abord générer le PDF."))

        notification_service = self.env['construction.contract.notification']
        
        try:
            notification_service._send_sms_invitation(self)
            self.sms_sent = True
            
            # Update state to sent if still in generated state
            if self.state == 'generated':
                self.write({
                    'state': 'sent',
                    'sent_date': fields.Datetime.now(),
                })

            self.message_post(
                body=_("Invitation envoyée par SMS à %s.") % self.subcontractor_id.name,
                message_type='notification'
            )

            return self._show_notification_success('SMS')

        except Exception as e:
            _logger.error(f"Failed to send SMS for contract {self.name}: {e}", exc_info=True)
            raise UserError(_("Erreur lors de l'envoi du SMS : %s") % str(e))

    def action_send_portal_email_sms(self):
        """
        Send portal link via both email and SMS.
        Called from the post-creation summary view.
        """
        self.ensure_one()

        if self.state not in ['generated', 'sent', 'in_progress']:
            raise UserError(_("Le contrat doit être généré avant d'envoyer l'invitation."))

        if not self.pdf_document:
            raise UserError(_("Aucun document PDF disponible. Veuillez d'abord générer le PDF."))

        notification_service = self.env['construction.contract.notification']
        results = {'email_sent': False, 'sms_sent': False, 'errors': []}
        
        # Send email
        try:
            notification_service._send_email_invitation(self)
            results['email_sent'] = True
            self.email_sent = True
        except Exception as e:
            _logger.warning(f"Failed to send email for contract {self.name}: {e}")
            results['errors'].append(_("E-mail : %s") % str(e))

        # Send SMS
        try:
            notification_service._send_sms_invitation(self)
            results['sms_sent'] = True
            self.sms_sent = True
        except Exception as e:
            _logger.warning(f"Failed to send SMS for contract {self.name}: {e}")
            results['errors'].append(_("SMS : %s") % str(e))

        # Update state if at least one notification was sent
        if results['email_sent'] or results['sms_sent']:
            if self.state == 'generated':
                self.write({
                    'state': 'sent',
                    'sent_date': fields.Datetime.now(),
                })

            channels = []
            if results['email_sent']:
                channels.append('e-mail')
            if results['sms_sent']:
                channels.append('SMS')

            self.message_post(
                body=_("Invitation envoyée par %s à %s.") % (
                    ' et '.join(channels),
                    self.subcontractor_id.name
                ),
                message_type='notification'
            )

            return self._show_notification_success(' et '.join(channels))
        else:
            # Both failed
            error_msg = _("Échec de l'envoi des notifications :\n%s") % '\n'.join(results['errors'])
            raise UserError(error_msg)

    def action_view_full_form(self):
        """
        Navigate to the full contract form view.
        Called from the post-creation summary view.
        """
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': _('Contrat'),
            'res_model': 'construction.contract',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('construction_contract.view_construction_contract_form').id,
            'target': 'current',
        }

    def _show_notification_success(self, channel):
        """
        Show success notification after sending invitation.
        
        Args:
            channel (str): The channel used (e-mail, SMS, or both)
            
        Returns:
            dict: Client action to display notification
        """
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Envoyé !'),
                'message': _("L'invitation a été envoyée par %s à %s.") % (
                    channel,
                    self.subcontractor_id.name
                ),
                'type': 'success',
                'sticky': False,
            }
        }

    # ============================================================
    # PRIVATE METHODS (Certificate, Signature, etc.)
    # ============================================================

    def _generate_certificate_of_completion(self):
        """
        Generate certificate of completion with all signature details
        This serves as legal proof of the signing process
        """
        self.ensure_one()

        # Prepare certificate data
        certificate_data = {
            'contract': self,
            'signature': self.signature_id,
            'page_validations': self.page_validation_ids.sorted('page_number'),
            'generated_date': fields.Datetime.now(),
            'company': self.env.company,  # Add company to context for template
        }

        # Generate PDF certificate using QWeb
        # Get the report by report_name (not XML ID) to avoid account module issues
        report = self.env['ir.actions.report'].sudo().search([
            ('report_name', '=', 'construction_contract.report_certificate_document'),
            ('model', '=', 'construction.contract')
        ], limit=1)
        
        if not report:
            _logger.error(f"Certificate report not found for contract {self.name}")
            raise UserError(_("Certificate report not found. Please contact administrator."))
        
        # Render PDF directly by bypassing account module's _pre_render_qweb_pdf
        # The issue is that account module intercepts _render_qweb_pdf and tries to use report_ref
        # which gets confused when report_ref is a list instead of a string XML ID
        try:
            # Render HTML first using QWeb template
            template = self.env.ref('construction_contract.report_certificate_document', raise_if_not_found=False)
            if not template:
                raise UserError(_("Certificate template not found."))
            
            # Prepare template context
            docs = self
            context = dict(certificate_data)
            context['docs'] = docs
            context['o'] = docs
            
            # Render HTML
            html = self.env['ir.qweb']._render(template.id, context)
            
            # Convert HTML to PDF using WeasyPrint (same as contract PDF generation)
            pdf_service = self.env['construction.contract.pdf.generator']
            pdf_content = pdf_service._convert_html_to_pdf(html)
            
            # Store certificate
            self.certificate_of_completion = base64.b64encode(pdf_content)
                
        except Exception as e:
            _logger.error(f"Error rendering certificate PDF for contract {self.name}: {e}", exc_info=True)
            raise UserError(_("Error generating certificate: %s") % str(e))

        _logger.info(f"Certificate of completion generated for contract {self.name}")

    def _get_rendered_html_for_pdf(self):
        """
        Get rendered HTML for PDF generation
        Prioritizes custom overrides before delegating to renderer

        Returns:
            str: Fully rendered HTML with data
        """
        self.ensure_one()

        if self.custom_html_override:
            _logger.info(f"Using custom HTML override for contract {self.name}")
            return self.custom_html_override

        renderer = self.env['construction.contract.template.renderer']
        return renderer.render_template(self)

    def _prepare_signature_context(self):
        """
        Prepare context data for signature portal

        Returns:
            dict: Context for portal template
        """
        self.ensure_one()

        validation_status = self._get_page_validation_status(self.access_token)

        return {
            'contract': self,
            'chantier': self.chantier_id,
            'subcontractor': self.subcontractor_id,
            'lots': self.lot_ids,
            'validation_status': validation_status,
            'pdf_url': f'/my/contract/{self.id}/pdf?access_token={self.access_token}',
            'can_sign': validation_status['can_sign'],
            'documents_status': self._get_subcontractor_documents_status(),
        }

    # ============================================================
    # PORTAL METHODS (Called from controllers)
    # ============================================================

    def portal_validate_page(self, page_number, access_token, time_spent=0):
        """
        Record that a page has been validated in the portal

        Args:
            page_number (int): Page number being validated
            access_token (str): Portal access token
            time_spent (int): Time spent reading the page (seconds)

        Returns:
            dict: Validation result
        """
        self.ensure_one()

        # Verify token
        if self._is_token_expired(access_token):
            raise ValidationError(_("Access token is invalid or expired."))

        # Check if page already validated
        existing = self.page_validation_ids.filtered(
            lambda v: v.page_number == page_number and v.access_token == access_token
        )

        if existing:
            return {'status': 'already_validated', 'page': page_number}

        # Create validation record
        self.env['construction.contract.page.validation'].create({
            'contract_id': self.id,
            'page_number': page_number,
            'access_token': access_token,
            'time_spent': time_spent,
            'validated_date': fields.Datetime.now(),
        })

        # Update contract state to in_progress
        if self.state == 'sent':
            self.action_mark_in_progress()

        return {
            'status': 'success',
            'page': page_number,
            'validation_status': self._get_page_validation_status(access_token),
        }

    def portal_save_signature(self, signature_data, access_token, ip_address=None, user_agent=None):
        """
        Save electronic signature from portal

        Args:
            signature_data (str): Base64 encoded signature image
            access_token (str): Portal access token
            ip_address (str): IP address of signer (optional, will try to get from request if not provided)
            user_agent (str): User agent string (optional, will try to get from request if not provided)

        Returns:
            dict: Signature save result
        """
        self.ensure_one()

        # Verify token
        if self._is_token_expired(access_token):
            raise ValidationError(_("Access token is invalid or expired."))

        # Verify all pages validated
        validation_status = self._get_page_validation_status(access_token)
        if not validation_status['can_sign']:
            raise ValidationError(_(
                "All pages must be validated before signing. "
                "Remaining: %d pages."
            ) % validation_status['remaining_pages'])

        # Get request information if not provided
        if not ip_address or ip_address == '0.0.0.0':
            try:
                request = http.request
                if request and hasattr(request, 'httprequest'):
                    # Get IP address from request
                    remote_addr = request.httprequest.environ.get('REMOTE_ADDR', '')
                    if remote_addr and remote_addr != '127.0.0.1':
                        ip_address = str(remote_addr)
                    else:
                        # Try proxy headers
                        forwarded_for = request.httprequest.environ.get('HTTP_X_FORWARDED_FOR', '')
                        if forwarded_for:
                            # Ensure it's a string (not a list)
                            if isinstance(forwarded_for, (list, tuple)):
                                forwarded_for = forwarded_for[0] if forwarded_for else ''
                            
                            # Convert to string if needed
                            if not isinstance(forwarded_for, str):
                                forwarded_for = str(forwarded_for) if forwarded_for else ''
                            
                            # Only split if it's a string
                            if forwarded_for and isinstance(forwarded_for, str):
                                parts = forwarded_for.split(',')
                                if parts:
                                    ip_address = parts[0].strip()
                        if not ip_address or ip_address == '127.0.0.1':
                            real_ip = request.httprequest.environ.get('HTTP_X_REAL_IP', '')
                            if real_ip:
                                ip_address = str(real_ip)
            except Exception:
                pass
        
        # Ensure we have a valid IP address
        if not ip_address or ip_address == '0.0.0.0':
            ip_address = '0.0.0.0'
        
        if not user_agent:
            try:
                request = http.request
                if request and hasattr(request, 'httprequest'):
                    user_agent = request.httprequest.environ.get('HTTP_USER_AGENT', '')
                    if user_agent and not isinstance(user_agent, str):
                        user_agent = str(user_agent)
            except Exception:
                pass
        
        if not user_agent:
            user_agent = ''
        
        # Create signature record
        signature = self.env['construction.contract.signature'].create({
            'contract_id': self.id,
            'signature_data': signature_data,
            'signature_date': fields.Datetime.now(),
            'signer_name': self.subcontractor_id.name,
            'signer_email': self.subcontractor_id.email,
            'signer_phone': self.subcontractor_id.mobile or self.subcontractor_id.phone,
            'access_token': access_token,
            'ip_address': str(ip_address),
            'user_agent': str(user_agent),
        })

        # Update contract with signature_id (use write to ensure it's saved)
        self.write({'signature_id': signature.id})
        
        # Now call action_mark_signed with signature in context for PDF regeneration
        self.with_context(contract_signature=signature).action_mark_signed()

        return {
            'status': 'success',
            'signature_id': signature.id,
            'contract_state': self.state,
        }

    # ============================================================
    # CRON METHODS
    # ============================================================

    @api.model
    def cron_check_pending_signatures(self):
        """
        Cron job to send reminders for contracts pending signature
        Runs daily to check contracts sent more than 3 days ago
        """
        three_days_ago = fields.Datetime.now() - timedelta(days=3)

        pending_contracts = self.search([
            ('state', 'in', ['sent', 'in_progress']),
            ('sent_date', '<', three_days_ago),
            '|',
            ('last_reminder_date', '=', False),
            ('last_reminder_date', '<', fields.Datetime.now() - timedelta(days=2)),
        ])

        for contract in pending_contracts:
            try:
                contract.action_send_reminder()
            except Exception as e:
                _logger.error(f"Failed to send reminder for contract {contract.name}: {e}")

        _logger.info(f"Sent reminders for {len(pending_contracts)} pending contracts")

        return True

    @api.model
    def cron_expire_tokens(self):
        """
        Cron job to clean up expired tokens
        Runs daily
        """
        expired_contracts = self.search([
            ('state', 'in', ['sent', 'in_progress']),
            ('token_expiry_date', '<', fields.Datetime.now()),
        ])

        for contract in expired_contracts:
            contract.message_post(
                body=_("Portal access token expired. Contract moved to cancelled."),
                message_type='notification'
            )
            contract.state = 'cancelled'

        _logger.info(f"Cancelled {len(expired_contracts)} contracts with expired tokens")

        return True


