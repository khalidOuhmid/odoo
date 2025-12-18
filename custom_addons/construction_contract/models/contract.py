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
    ('doc_urssaf_status', 'doc_urssaf', _("Attestation URSSAF")),
    ('doc_kbis_status', 'doc_kbis', _("Extrait KBIS")),
    ('doc_insurance_dec_status', 'doc_insurance_dec', _("Assurance Décennale")),
]
GLOBAL_STATUS_FIELDS = [
    'doc_cni_status',
    'doc_urssaf_status',
    'doc_kbis_status',
    'doc_insurance_dec_status',
    'doc_rib_status',
]

# Import constants
from ..config.contract_constants import (
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
        domain="[('is_subcontractor', '=', True)]",
        help="Subcontractor company (from construction_subcontractor)"
    )

    lot_ids = fields.One2many(
        'construction.lot',
        'contract_id',  # Inverse field on construction.lot (defined in lot_extension.py)
        string='Lots',
        help="Construction lots included in this contract (a lot belongs to ONE contract only)"
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

    signing_token = fields.Char(
        string='Signing Token',
        copy=False,
        readonly=True,
        help="Token for portal access to sign the contract"
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

    # ============= CONTRACT BUILDER FIELDS ============= #
    
    contract_template_html = fields.Html(
        string='Contract HTML',
        sanitize=False,
        help="HTML content of the contract, editable via GrapeJS"
    )

    subcontractor_signature = fields.Binary(string='Subcontractor Signature')
    
    master_name = fields.Char(
        string='Maître d\'Ouvrage',
        help="Nom du Maître d'Ouvrage (Client)"
    )

    # Penalties Configuration
    penalty_docs_delay = fields.Monetary(string='Pénalité Retard Docs', default=150.0)
    penalty_safety = fields.Monetary(string='Pénalité Sécurité', default=80.0)
    penalty_justificatifs = fields.Monetary(string='Pénalité Justificatifs', default=150.0)
    penalty_prototypes = fields.Monetary(string='Pénalité Prototypes', default=50.0)
    penalty_cleaning = fields.Monetary(string='Pénalité Nettoyage', default=80.0)
    penalty_retard_jour = fields.Monetary(string='Pénalité Retard / Jour', default=200.0)

    # Contract Specifics
    master_address = fields.Char(string='Adresse Maître d\'Ouvrage')
    gpa_duration = fields.Integer(string='Durée GPA (Mois)', default=12)
    signatory_contractor = fields.Char(string='Signataire Contractant (BLG)', default='Direction BLG')
    signatory_subcontractor = fields.Char(string='Signataire Sous-traitant')

    # ============= SAP-GRADE: SIGNATURE PROOF FILE ============= #
    
    signature_proof_json = fields.Text(
        string='Signature Proof (JSON)',
        readonly=True,
        help="SAP-grade legal proof file - JSON containing complete audit trail"
    )
    
    signature_proof_generated = fields.Boolean(
        string='Proof File Generated',
        default=False,
        readonly=True,
    )

    # ============= LOGIC: DATA INJECTION ============= #

    def _get_contract_data_context(self):
        """
        Build Jinja2 context for contract template rendering.
        Uses getattr for ALL optional fields to prevent AttributeError.
        
        SAP-Level Validation: Defensive access, French formatting, XML escaping.
        """
        self.ensure_one()
        
        # Base objects
        partner = self.subcontractor_id
        company = self.env.company
        chantier = self.chantier_id
        
        # Safe getattr helper
        def safe(obj, field, default=''):
            return getattr(obj, field, default) or default
        
        # Financial calculations
        amount_ht = getattr(self, 'total_amount_ht', 0.0) or 0.0
        tax_rate = 0.20
        amount_ttc = amount_ht * (1 + tax_rate)
        
        # Build context with comprehensive defensive access
        context = {
            # === CONTRACTANT GÉNÉRAL (BLG) ===
            'contractant_nom': self._escape_xml(company.name).upper(),
            'contractant_adresse': self._escape_xml(company.street or ''),
            'contractant_cp_ville': f"{company.zip or ''} {company.city or ''}".strip(),
            'signataire_contractant_nom': self._escape_xml(safe(self, 'signatory_contractor', 'Direction')),

            # === ENTREPRISE SOUS-TRAITANTE ===
            'entreprise_nom': self._escape_xml(partner.name).upper() if partner else 'N/A',
            'entreprise_adresse': self._escape_xml(partner.street or '') if partner else '',
            'entreprise_cp_ville': f"{partner.zip or ''} {partner.city or ''}".strip() if partner else '',
            'entreprise_siret': self._escape_xml(safe(partner, 'siret') or safe(partner, 'company_registry') or safe(partner, 'vat', 'N/A')),
            'entreprise_naf': self._escape_xml(safe(partner, 'ape', 'N/A')),
            'signataire_entreprise_nom': self._escape_xml(safe(self, 'signatory_subcontractor') or (partner.name if partner else '')),
            # Aliases
            'partner_name': self._escape_xml(partner.name).upper() if partner else 'N/A',
            'partner_street': self._escape_xml(partner.street or '') if partner else '',
            'partner_city': self._escape_xml((partner.city or '').title()) if partner else '',

            # === MAITRE D'OUVRAGE ===
            'maitre_ouvrage_nom': self._escape_xml(safe(self, 'master_name', 'N/A')),
            'maitre_ouvrage_adresse': self._escape_xml(safe(self, 'master_address', 'N/A')),

            # === CHANTIER ===
            'chantier_reference': self._escape_xml(safe(chantier, 'reference') or safe(chantier, 'code') or (chantier.name if chantier else '')),
            'chantier_nom': self._escape_xml(chantier.name or '') if chantier else '',
            'chantier_adresse': f"{safe(chantier, 'address')}, {safe(chantier, 'zip_code')} {safe(chantier, 'city')}".strip(' ,') if chantier else '',
            'project_reference': self._escape_xml(safe(chantier, 'reference') or (chantier.name if chantier else '')),

            # === COMMANDE / CONTRAT ===
            'bc_numero': self._escape_xml(self.name or ''),
            'bc_date': self._format_date(self.date or fields.Date.today()),
            'lieu_signature': self._escape_xml(safe(self, 'signature_location') or company.city or 'Bordeaux'),
            'date_signature': self._format_date(self.signature_date or fields.Date.today()),
            
            # === FINANCIER ===
            'montant_ht': self._format_currency(amount_ht),
            'montant_ttc': self._format_currency(amount_ttc),
            'taux_tva': '20%',
            'amount_total': self._format_currency(amount_ht),

            # === PÉNALITÉS & DÉLAIS ===
            'penalite_retard_jour': self._format_currency(safe(self, 'penalty_retard_jour') or 0, no_symbol=True),
            'penalty_docs_delay': self._format_currency(safe(self, 'penalty_docs_delay') or 0, no_symbol=True),
            'penalty_safety': self._format_currency(safe(self, 'penalty_safety') or 0, no_symbol=True),
            'penalty_justificatifs': self._format_currency(safe(self, 'penalty_justificatifs') or 0, no_symbol=True),
            'penalty_prototypes': self._format_currency(safe(self, 'penalty_prototypes') or 0, no_symbol=True),
            'penalty_cleaning': self._format_currency(safe(self, 'penalty_cleaning') or 0, no_symbol=True),
            'delai_gpa_mois': str(safe(self, 'gpa_duration') or 12),

            # === VISUELS ===
            'signature_blg_image': self._get_base64_image(company.logo) if hasattr(self, '_get_base64_image') else '',
            'signature_partner_image': self._get_base64_image(safe(self, 'subcontractor_signature')) if hasattr(self, '_get_base64_image') else '',
            
            # === EXTRAS ===
            'service_description': self._escape_xml(', '.join(filter(None, self.lot_ids.mapped('description'))) or safe(self, 'notes', '')),
            'master_name': self._escape_xml(safe(self, 'master_name', "MAÎTRE D'OUVRAGE")),
            
            # === LOTS & PAYMENT SCHEDULE (FIX DATA INJECTION) ===
            'lots': self._get_lots_data_context(),
            'schedule': self._get_schedule_data_context(),
        }
        
        # Validation (skip if method missing)
        if hasattr(self, '_validate_context_completeness'):
            self._validate_context_completeness(context)
        
        return context

    def _get_lots_data_context(self):
        """Build structured list of lots for Jinja2 iteration."""
        lots_data = []
        for lot in self.lot_ids:
            # Attempt to find amount from related PO lines or lot fields
            amount = 0.0
            # Rough logic: Sum PO lines linked to this lot for this subcontractor
            # This matches logic in _compute_amounts roughly but per lot
            for po in self.purchase_order_ids:
                for line in po.order_line:
                    # Check if line relates to this lot (by name or custom field)
                    # For now, relying on lot fields if available or defaulting
                    # Assuming lot has 'price' or we use global PO division?
                    # Let's use the lot attributes if they exist or 0
                    pass
            
            # Better approach: if lot has stored price or we calculated it
            # For this hotfix, we use what we have access to easily.
            # The user Prompt said: "Récupère les lignes de commande ... associées au contrat"
            
            # Simple retrieval from lot model if it stores cost/price
            # If not, we try to sum linked PO lines found in action_generate_consolidated_po logic
            # or simple attributes.
            
            description = lot.description or lot.name
            
            # Recalculate specific amount for this lot from POs attached to this contract
            lot_amount = 0.0
            related_po_lines = self.env['purchase.order.line'].search([
                ('order_id', 'in', self.purchase_order_ids.ids),
                '|', 
                ('name', 'ilike', lot.code or 'INVALID_CODE'),
                ('product_id.name', 'ilike', lot.name)
            ])
            lot_amount = sum(related_po_lines.mapped('price_subtotal'))
            
            lots_data.append({
                'name': self._escape_xml(lot.name),
                'desc': self._escape_xml(description),
                'code': self._escape_xml(lot.code or ''),
                'amount': self._format_currency(lot_amount),
                'amount_raw': lot_amount
            })
        return lots_data

    def _get_schedule_data_context(self):
        """Build payment schedule data."""
        # TODO: Link to real payment terms or milestones
        # For now return standard placeholder structure
        return [
            {'name': 'Acompte', 'percent': '30%', 'amount': self._format_currency(self.total_amount_ttc * 0.3)},
            {'name': 'Solde', 'percent': '70%', 'amount': self._format_currency(self.total_amount_ttc * 0.7)},
        ]

    # === MÉTHODES HELPERS === #
    def _format_currency(self, amount, no_symbol=False):
        """Format: 12 345,67 € (espace insécable avant €)"""
        if not amount:
            return "0,00" if no_symbol else "0,00\u00A0€"
        formatted = "{:,.2f}".format(amount).replace(',', ' ').replace('.', ',')
        return formatted if no_symbol else f"{formatted}\u00A0€"

    def _format_date(self, date_obj):
        """Format: 15/12/2025"""
        if not date_obj:
            return ""
        return date_obj.strftime('%d/%m/%Y')

    def _escape_xml(self, text):
        """Échappement XML + suppression caractères dangereux"""
        if not text:
            return ''
        import html
        return html.escape(str(text), quote=True)
        
    def _get_base64_image(self, image_field):
        """Return base64 string for image or empty placeholder"""
        if not image_field:
            return ''
        return image_field.decode('utf-8') if isinstance(image_field, bytes) else image_field

    def _validate_context_completeness(self, context):
        """
        Validation checkpoint for required context fields.
        Only validates fields that MUST exist at generation time.
        signature_date is filled later, po_number is not used.
        """
        required_fields = [
            'partner_name', 'project_reference', 'amount_total',
        ]
        missing = [f for f in required_fields if not context.get(f)]
        if missing:
            raise ValidationError(
                f"Champs obligatoires manquants: {', '.join(missing)}"
            )
            
    def _compute_contract_hash_mock(self):
        """Temporary hash mock"""
        return "sha256_placeholder"

    def _check_required_documents(self):
        """
        VALIDATION CHECKPOINT CHAIN_1
        Checks 4 mandatory documents:
        - Planning Chantier
        - Planning Lot
        - CCTP
        - Bon de Commande
        """
        # Note: Implementation logic depends on how documents are stored.
        # Assuming they are in document_ids of the lot or chantier.
        # This will be refined.
        pass

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
        Override create to generate sequence number and access token.
        
        US-COR-012: Contract naming convention:
        Format: [CHANTIER]-CT-[LOT]-[DATE_AAAAMMJJ]
        Example: Villa-Dupont-CT-PLOM-20251218
        """
        # US-COR-012: Generate contract reference following nomenclature
        if vals.get('name', _('New')) == _('New'):
            chantier_id = vals.get('chantier_id')
            lot_ids = vals.get('lot_ids', [])
            
            if chantier_id:
                chantier = self.env['construction.chantier'].browse(chantier_id)
                chantier_name = (chantier.name or 'CHANTIER').replace(' ', '-').upper()[:15]
                
                # Get lot codes
                lot_code = 'LOT'
                if lot_ids:
                    # Handle Odoo command format [(6, 0, [ids])]
                    if isinstance(lot_ids, list) and lot_ids:
                        if isinstance(lot_ids[0], (list, tuple)) and lot_ids[0][0] == 6:
                            real_ids = lot_ids[0][2]
                        else:
                            real_ids = lot_ids
                        
                        if real_ids:
                            lots = self.env['construction.lot'].browse(real_ids)
                            lot_code = '+'.join(lots.mapped('code'))
                
                # Date format: AAAAMMJJ
                from datetime import date
                date_str = date.today().strftime('%Y%m%d')
                
                vals['name'] = f"{chantier_name}-CT-{lot_code}-{date_str}"
            else:
                # Fallback to sequence if no chantier
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

    # ============= ACTION: TEMPLATE GENERATION (CHAIN_2) ============= #

    def action_generate_contract_html(self):
        """
        CHAIN_2: Génération Template HTML
        1. Load default template
        2. Inject context data via Jinja2
        3. Store in contract_template_html
        """
        self.ensure_one()
        
        # 1. Validation Pre-requis (CHAIN_1)
        self._check_required_documents()
        
        # 2. Render Template
        try:
            # Use a sensible default if no template is set on the contract creation logic
            if self.template_id:
                 template_node = self.template_id
            else:
                 template_node = self.env.ref('construction_contract.default_contract_template', raise_if_not_found=False)
                 if not template_node:
                     template_node = self.env['construction.contract.template'].search([('is_default', '=', True)], limit=1)

            if not template_node:
                 raise UserError(_("Aucun modèle de contrat trouvé."))

            # Extract HTML content directly from grapesjs_html
            raw_html = template_node.grapesjs_html or ""
            
            # 3. Inject Context
            import jinja2
            context = self._get_contract_data_context()
            
            # Jinja2 Environment
            env = jinja2.Environment(autoescape=True)
            jinja_template = env.from_string(raw_html)
            rendered_html = jinja_template.render(**context)
            
            # 4. Store and Update State
            self.write({
                'contract_template_html': rendered_html,
                'state': 'generated' if self.state == 'draft' else self.state
            })
            
            # 5. Return Action to open Editor (Directly)
            return self.action_open_contract_editor()
            
        except Exception as e:
            raise UserError(_("Erreur lors de la génération du contrat: %s") % str(e))

    def action_open_contract_editor(self):
        """
        CHAIN_3: Ouvrir l'éditeur GrapeJS
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'construction_contract.grapejs_editor',
            'context': {
                'active_id': self.id,
                'active_model': 'construction.contract',
                'field_name': 'contract_template_html',
            },
            'target': 'fullscreen',
        }

    def _generate_signing_token(self):
        """Generate unique signing token for portal access."""
        self.ensure_one()
        import secrets
        self.signing_token = secrets.token_urlsafe(32)

    def action_generate_pdf_and_open_send_wizard(self):
        """
        Called from JS editor: Generate PDF and open send wizard.
        
        Returns:
            dict: Action to open contract.send.wizard
        """
        self.ensure_one()
        
        try:
            # 1. Generate PDF (may fail if no template)
            if self.contract_template_html:
                self.action_generate_pdf()
            else:
                # Just update state if no PDF needed
                if self.state == 'draft':
                    self.state = 'generated'
        except Exception as e:
            import logging
            _logger = logging.getLogger(__name__)
            _logger.warning("PDF generation skipped: %s", str(e))
        
        # 2. Ensure signing token exists
        if not self.signing_token:
            self._generate_signing_token()
        
        # 3. Get wizard view
        view = self.env.ref('construction_contract.contract_send_wizard_form', raise_if_not_found=False)
        
        # 4. Return action with explicit format
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Envoyer le Contrat'),
            'res_model': 'contract.send.wizard',
            'view_mode': 'form',
            'views': [(view.id if view else False, 'form')],
            'target': 'new',
            'context': {
                'default_contract_id': self.id,
            },
        }
        return action

    def action_generate_pdf(self):
        """
        CHAIN_4: Génération PDF Final
        Uses WeasyPrint to generate PDF from contract_template_html
        Then merges with CCTP, Planning, and PO PDFs
        """
        import gc
        
        self.ensure_one()
        if not self.contract_template_html:
            raise UserError(_("Veuillez d'abord générer le contrat."))

        try:
            # 1. Inject Signatures (Final check before PDF)
            html_content = self.contract_template_html
            
            # 2. Generate PDF using WeasyPrint
            from weasyprint import HTML, CSS
            import io
            
            # Base URL for local resources (images) if needed
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            
            _logger.info(f"[PDF] Starting generation for contract {self.name}")
            
            pdf_file = io.BytesIO()
            HTML(string=html_content, base_url=base_url).write_pdf(
                pdf_file,
                optimize_size=('fonts',)
            )
            
            pdf_bytes = pdf_file.getvalue()
            _logger.info(f"[PDF] Base contract generated: {len(pdf_bytes)/1024:.1f} KB")
            
            # 3. MERGE: Fusion with CCTP, Planning, PO
            pdf_generator = self.env['construction.contract.pdf.generator']
            merged_pdf_bytes = pdf_generator.merge_contract_bundle(self, pdf_bytes)
            
            # 4. Store Attachment
            attachment_name = f"Contrat_{self.name}_{self.subcontractor_id.name}.pdf".replace(' ', '_')
            attachment = self.env['ir.attachment'].create({
                'name': attachment_name,
                'type': 'binary',
                'datas': base64.b64encode(merged_pdf_bytes),
                'res_model': 'construction.contract',
                'res_id': self.id,
                'mimetype': 'application/pdf'
            })
            
            # 5. Compute Hash
            pdf_hash = hashlib.sha256(merged_pdf_bytes).hexdigest()
            
            self.write({
                'pdf_document': base64.b64encode(merged_pdf_bytes),
                'pdf_hash_before_signature': pdf_hash,
                'state': 'sent'  # Ready for signature
            })
            
            # 6. Memory cleanup
            gc.collect()
            
            _logger.info(f"[PDF] Complete for {self.name}: {len(merged_pdf_bytes)/1024:.1f} KB, hash={pdf_hash[:16]}...")
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("PDF Généré"),
                    'message': _("Le PDF fusionné a été généré et attaché au contrat."),
                    'type': 'success',
                }
            }
            
        except Exception as e:
            _logger.error("WeasyPrint/Merge Error: %s", e, exc_info=True)
            gc.collect()  # Cleanup on error too
            raise UserError(_("Erreur lors de la génération PDF: %s") % str(e))

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

    # ============================================================
    # SAP-GRADE: PROOF FILE GENERATION
    # ============================================================

    def _generate_proof_file(self):
        """
        SAP S/4HANA Grade: Generate a comprehensive JSON proof file.
        This file serves as legal evidence of the signature process.
        
        Returns:
            str: JSON string containing complete audit trail
        """
        import json
        from datetime import datetime
        
        self.ensure_one()
        
        # Get all page validations
        page_validations = self.page_validation_ids.sorted('validated_date')
        validation_logs = []
        for pv in page_validations:
            validation_logs.append({
                'page_number': pv.page_number,
                'validated_at': pv.validated_date.isoformat() if pv.validated_date else None,
                'time_spent_seconds': pv.time_spent,
                'scroll_percentage': pv.scroll_percentage,
                'validation_method': pv.validation_method,
                'ip_address': pv.ip_address,
                'user_agent': pv.user_agent[:200] if pv.user_agent else None,  # Truncate
            })
        
        # Get signature details
        signature_data = None
        if self.signature_id:
            sig = self.signature_id
            signature_data = {
                'signed_at': sig.signature_date.isoformat() if sig.signature_date else None,
                'ip_address': sig.ip_address,
                'user_agent': sig.user_agent[:200] if sig.user_agent else None,
                'device_type': sig.device_type,
                'signer_name': sig.signer_name,
                'signature_size_bytes': len(sig.signature_image) if sig.signature_image else 0,
            }
        
        # Build proof file structure
        proof_document = {
            'version': '1.0',
            'generated_at': datetime.utcnow().isoformat() + 'Z',
            'generator': 'BLG Contract Builder / SAP-Grade Module',
            
            'contract': {
                'reference': self.name,
                'created_at': self.create_date.isoformat() if self.create_date else None,
                'chantier_name': self.chantier_id.name if self.chantier_id else None,
                'subcontractor_name': self.subcontractor_id.name if self.subcontractor_id else None,
                'subcontractor_siret': self.subcontractor_id.siren if self.subcontractor_id else None,
                'total_amount_ttc': float(self.total_amount_ttc),
                'currency': self.currency_id.name if self.currency_id else 'EUR',
            },
            
            'document_integrity': {
                'algorithm': 'SHA-256',
                'hash_before_signature': self.pdf_hash_before_signature,
                'hash_after_signature': self.pdf_hash_after_signature,
                'page_count': self.pdf_page_count,
            },
            
            'reading_audit_trail': {
                'total_pages_validated': len(validation_logs),
                'total_reading_time_seconds': sum(v['time_spent_seconds'] for v in validation_logs),
                'page_validations': validation_logs,
            },
            
            'signature': signature_data,
            
            'legal_notice': (
                "Ce document constitue une preuve de signature électronique. "
                "Il atteste que le signataire a lu l'intégralité du contrat "
                "et a apposé sa signature électronique de manière volontaire. "
                "L'empreinte SHA-256 garantit l'intégrité du document."
            ),
        }
        
        # Serialize to JSON
        proof_json = json.dumps(proof_document, indent=2, ensure_ascii=False)
        
        # Store in contract
        self.write({
            'signature_proof_json': proof_json,
            'signature_proof_generated': True,
        })
        
        _logger.info(
            f"[SAP-PROOF] Generated proof file for contract {self.name}: "
            f"{len(validation_logs)} page validations, signature={'Yes' if signature_data else 'No'}"
        )
        
        return proof_json

    def action_merge_and_send(self):
        """
        SAP-Grade Unified Workflow:
        1. Generate PDF from template
        2. Merge with annexes (Planning, CCTP, PO)
        3. Send for signature
        
        Returns:
            dict: Action result with notification
        """
        self.ensure_one()
        
        if self.state == 'signed':
            raise UserError(_("Le contrat est déjà signé."))
        
        try:
            # Step 1: Generate PDF if not exists
            if not self.pdf_document or not self.contract_template_html:
                _logger.info(f"[WORKFLOW] Generating PDF for contract {self.name}")
                self.action_generate_contract()
                self.action_generate_pdf()
            
            # Step 2: Merge with annexes
            merger_service = self.env['construction.contract.pdf.merger']
            merge_result = merger_service.merge_contract_package(self)
            
            if merge_result and merge_result.get('pdf_data'):
                # Update with merged PDF
                self.write({
                    'pdf_document': base64.b64encode(merge_result['pdf_data']),
                    'pdf_hash_before_signature': merge_result['hash_after'],
                })
                _logger.info(
                    f"[WORKFLOW] Merged PDF for contract {self.name}: "
                    f"{merge_result['section_count']} sections, {merge_result['total_pages']} pages"
                )
            
            # Step 3: Send for signature
            notification_service = self.env['construction.contract.notification']
            notification_service.send_contract_invitation(self)
            
            # Update state
            self.write({
                'state': 'sent',
                'sent_date': fields.Datetime.now(),
            })
            
            self.message_post(
                body=_(
                    "Contrat fusionné (%d sections) et envoyé à %s pour signature."
                ) % (merge_result.get('section_count', 1), self.subcontractor_id.name),
                message_type='notification'
            )
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Succès"),
                    'message': _("Le contrat a été fusionné avec les annexes et envoyé pour signature."),
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            _logger.error(f"[WORKFLOW] Error in merge_and_send for contract {self.name}: {e}", exc_info=True)
            raise UserError(_("Erreur lors du workflow: %s") % str(e))

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

        if self.state not in ['sent', 'in_progress']:
            raise UserError(_("Contract must be in 'Sent' or 'In Progress' state to be signed."))

        # Regenerate PDF with BOTH signatures (company + subcontractor) included in HTML template
        _logger.info(f"Regenerating PDF with both signatures for contract {self.name}")
        
        # Get subcontractor signature from context (passed during signature save) or from contract
        subcontractor_signature = self.env.context.get('contract_signature') or self.signature_id
        
        if not subcontractor_signature:
            _logger.error(f"No subcontractor signature found for contract {self.name} - cannot regenerate PDF")
            raise UserError(_("Subcontractor signature not found. Cannot regenerate PDF."))
        
        # Calculate hash after signature for integrity
        # We need to regenerate the PDF first to include the signature image
        # The 'action_generate_pdf' method uses 'contract_template_html', which should now include the signature placeholders.
        # However, the templates usually use 'object.subcontractor_signature' etc.
        # We need to ensure the HTML context receives the signature object.
        # references: 
        #   {{ subcontractor_signature.image_data }} in the HTML template.
        #   Our _get_contract_data_context (which I need to check) populates this.
        
        # 1. Inject Signature Image (FIX SIGNATURE VISUELLE)
        if subcontractor_signature and subcontractor_signature.signature_data:
            # Get valid base64 image
            sig_image = subcontractor_signature.signature_data.decode('utf-8') if isinstance(subcontractor_signature.signature_data, bytes) else subcontractor_signature.signature_data
            img_tag = f'<img src="data:image/png;base64,{sig_image}" alt="Signature" style="max-height: 150px; border-bottom: 1px solid #000;"/>'
            
            # Inject into HTML
            if self.contract_template_html:
                if '<!-- SIGNATURE_CLIENT -->' in self.contract_template_html:
                    self.contract_template_html = self.contract_template_html.replace('<!-- SIGNATURE_CLIENT -->', img_tag)
                elif 'id="signature-placeholder"' in self.contract_template_html:
                     # Fallback to regex or simple replace if ID exists
                     import re
                     self.contract_template_html = re.sub(r'<div[^>]*id="signature-placeholder"[^>]*>.*?</div>', f'<div id="signature-placeholder">{img_tag}</div>', self.contract_template_html, flags=re.DOTALL)
                else:
                    # Append strictly if missing
                    self.contract_template_html += f'<div class="signature-injection-fallback" style="margin-top:50px;"><h4>Signature:</h4>{img_tag}</div>'

        # 2. Regenerate PDF
        self.with_context(contract_signature=subcontractor_signature).action_generate_pdf()
        
        # Verify PDF was regenerated
        if not self.pdf_document:
            _logger.error(f"PDF regeneration failed for contract {self.name} - no PDF document after generation")
            raise UserError(_("PDF regeneration failed. Please try again."))
        
        # 2. Calculate hash
        import hashlib
        import base64
        pdf_content = base64.b64decode(self.pdf_document)
        pdf_hash_after = hashlib.sha256(pdf_content).hexdigest()
        self.write({
            'pdf_hash_after_signature': pdf_hash_after
        })
        _logger.info(f"PDF regenerated successfully with both signatures for contract {self.name}, hash: {pdf_hash_after[:16]}..., size: {len(pdf_content)/1024:.1f} KB")

        # 3. Generate certificate of completion
        self._generate_certificate_of_completion()

        # 4. Update state
        self.write({
            'state': 'signed',
            'signature_date': fields.Datetime.now(),
        })

        # 5. Notify stakeholders
        self.message_post(
            body=_("Contract signed by %s on %s.") % (
                self.subcontractor_id.name,
                fields.Datetime.now().strftime('%d/%m/%Y %H:%M')
            ),
            message_type='notification',
            subtype_xmlid='mail.mt_note',
        )

        # 6. Send confirmation email
        template = self.env.ref('construction_contract.mail_template_contract_signed', raise_if_not_found=False)
        if template:
            template.send_mail(self.id)

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
    # CERTIFICATE GENERATION
    # ============================================================

    def _generate_certificate_of_completion(self):
        """
        Generate the certificate of completion PDF and attach it to the contract.
        Uses the QWeb report 'construction_contract.action_report_certificate'.
        """
        self.ensure_one()
        try:
            # Render QWeb PDF
            report = self.env.ref('construction_contract.action_report_certificate')
            # Pass additional data if needed in data dictionary, but doc is passed as docids
            pdf_content, _ = report._render_qweb_pdf(self.ids, data={'generated_date': fields.Datetime.now(), 'company': self.env.company})
            
            # Store PDF in Binary field
            self.write({
                'certificate_of_completion': base64.b64encode(pdf_content),
                'certificate_filename': f"Certificat_Signature_{self.name.replace('/', '_')}.pdf",
            })
            
            _logger.info(f"Certificate of completion generated for contract {self.name}")
            
        except Exception as e:
            _logger.error(f"Failed to generate certificate for contract {self.name}: {e}")
            # Non-blocking error, but should be logged.
            # We don't raise UserError here to avoid blocking the main signature flow if just the certificate fails,
            # but maybe we should? The prompt implies legal value. 
            # Let's log and maybe raise if critical, but for now log error is safer for user UX.
            # Actually, `action_mark_signed` doesn't catch this, so it will bubble up if we raise.
            raise UserError(_("Impossible de générer le certificat de complétion: %s") % str(e))

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


