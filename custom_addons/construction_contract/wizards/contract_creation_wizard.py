# -*- coding: utf-8 -*-
"""
Contract Creation Wizard
Guided wizard for creating contracts with validation
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

from ..config.contract_constants import DEFAULT_RETENTION_RATE


class ContractCreationWizard(models.TransientModel):
    """
    Contract Creation Wizard

    Guides users through contract creation with:
    - Chantier selection
    - Subcontractor selection with document validation
    - Lot selection with coherence checks
    - Automatic deliverable generation
    """

    _name = 'contract.creation.wizard'
    _description = 'Contract Creation Wizard'

    state = fields.Selection([
        ('step1', '1. Sous-traitant'),
        ('step2', '2. Lots'),
        ('step3', '3. Documents'),
        ('step4', '4. Récapitulatif')
    ], string='Étape', default='step1')

    chantier_id = fields.Many2one(
        'construction.chantier',
        string='Construction Site',
        required=True,
        help="Select the construction site for this contract"
    )

    subcontractor_id = fields.Many2one(
        'res.partner',
        string='Subcontractor',
        required=True,
        domain="[('is_subcontractor', '=', True)]",
        help="Select the subcontractor"
    )

    # Document validation status (computed)
    subcontractor_documents_valid = fields.Boolean(
        string='Documents Valid',
        compute='_compute_subcontractor_status',
        help="True if all required documents are valid"
    )

    subcontractor_warning = fields.Text(
        string='Validation Warning',
        compute='_compute_subcontractor_status',
        help="Warning message if documents are invalid"
    )

    # ============================================================
    # STEP 2: LOTS SELECTION (with Multi-Lot Auto-Detection)
    # ============================================================

    lot_ids = fields.Many2many(
        'construction.lot',
        'wizard_contract_lot_rel',
        'wizard_id',
        'lot_id',
        string='Lots',
        domain="[('chantier_id', '=', chantier_id)]",
        help="Select the lots for this contract"
    )

    available_lot_ids = fields.Many2many(
        'construction.lot',
        compute='_compute_available_lots',
        string='Available Lots',
        help="Lots available for this chantier (without contract)"
    )

    # Multi-lot aggregation fields
    show_aggregation_warning = fields.Boolean(
        compute='_compute_related_lots',
        string='Show Aggregation Warning'
    )
    
    related_lot_count = fields.Integer(
        compute='_compute_related_lots',
        string='Related Lots Count'
    )
    
    aggregation_message = fields.Text(
        compute='_compute_related_lots',
        string='Aggregation Message'
    )

    # ============================================================
    # STEP 3: DATES
    # ============================================================

    start_date = fields.Date(
        string='Work Start Date',
        required=True,
        default=fields.Date.context_today,
        help="Scheduled start date"
    )

    end_date = fields.Date(
        string='Work End Date',
        required=True,
        help="Scheduled completion date"
    )

    contract_date = fields.Date(
        string='Contract Date',
        required=True,
        default=fields.Date.context_today,
        help="Official contract date that will appear on the document"
    )

    # ============================================================
    # STEP 4: TEMPLATE
    # ============================================================

    template_id = fields.Many2one(
        'construction.contract.template',
        string='Contract Template',
        default=lambda self: self.env.ref(
            'construction_contract.default_contract_template',
            raise_if_not_found=False
        ),
        help="Template to use for PDF generation"
    )

    retention_rate = fields.Float(
        string='Retention Rate (%)',
        default=DEFAULT_RETENTION_RATE,
        help="Guarantee retention percentage applied to the contract total"
    )

    # ============================================================
    # OPTIONS
    # ============================================================

    generate_deliverables = fields.Boolean(
        string='Auto-Generate Deliverables',
        default=True,
        help="Automatically create deliverables from planning and documents"
    )

    send_immediately = fields.Boolean(
        string='Send Contract Immediately',
        default=False,
        help="Generate PDF and send to subcontractor immediately"
    )

    bypass_compliance_check = fields.Boolean(
        string='Ignorer la vérification de conformité',
        default=False,
        help="Forcé à True après confirmation dans le wizard d'avertissement"
    )

    # ============================================================
    # STEP 3: DOCUMENTS VALIDATION
    # ============================================================

    has_planning_general = fields.Boolean(compute='_compute_document_status')
    missing_cctp_lots = fields.Char(compute='_compute_document_status')
    missing_planning_lots = fields.Char(compute='_compute_document_status')
    missing_po_lots = fields.Char(compute='_compute_document_status')
    total_po_amount = fields.Monetary(compute='_compute_document_status', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    step3_valid = fields.Boolean(compute='_compute_document_status')

    # ============================================================
    # COMPUTED FIELDS
    # ============================================================

    @api.depends('chantier_id')
    def _compute_available_lots(self):
        """Get available lots for selected chantier (without existing contract)"""
        for wizard in self:
            if wizard.chantier_id:
                # Filter: lots on this chantier WITHOUT a contract yet
                wizard.available_lot_ids = wizard.chantier_id.lots_ids.filtered(
                    lambda l: not l.contract_id
                )
            else:
                wizard.available_lot_ids = False

    @api.depends('chantier_id', 'subcontractor_id')
    def _compute_related_lots(self):
        """
        Detect other lots on same chantier for same subcontractor.
        Used for multi-lot aggregation warning.
        """
        for wizard in self:
            if wizard.chantier_id and wizard.subcontractor_id:
                # Find ALL lots for this subcontractor on this chantier (without contract)
                related_lots = self.env['construction.lot'].search([
                    ('chantier_id', '=', wizard.chantier_id.id),
                    ('subcontractor_id', '=', wizard.subcontractor_id.id),
                    ('execution_type', '=', 'external'),
                    ('contract_id', '=', False),
                ])
                
                wizard.related_lot_count = len(related_lots)
                wizard.show_aggregation_warning = len(related_lots) > 1
                
                if wizard.show_aggregation_warning:
                    lot_names = ', '.join(related_lots.mapped('name'))
                    wizard.aggregation_message = _(
                        "⚠️ Ce sous-traitant a %d lots sans contrat sur ce chantier :\n%s\n\n"
                        "Tous ces lots seront automatiquement inclus dans le contrat."
                    ) % (len(related_lots), lot_names)
                else:
                    wizard.aggregation_message = ''
            else:
                wizard.related_lot_count = 0
                wizard.show_aggregation_warning = False
                wizard.aggregation_message = ''

    @api.onchange('chantier_id', 'subcontractor_id')
    def _onchange_auto_select_related_lots(self):
        """
        When chantier and subcontractor are selected, auto-select ALL related lots.
        This implements multi-lot aggregation.
        """
        if self.chantier_id and self.subcontractor_id:
            # Find all lots for this subcontractor on this chantier (without contract)
            related_lots = self.env['construction.lot'].search([
                ('chantier_id', '=', self.chantier_id.id),
                ('subcontractor_id', '=', self.subcontractor_id.id),
                ('execution_type', '=', 'external'),
                ('contract_id', '=', False),
            ])
            self.lot_ids = [(6, 0, related_lots.ids)]

    @api.depends('subcontractor_id')
    def _compute_subcontractor_status(self):
        """Validate subcontractor documents"""
        for wizard in self:
            if wizard.subcontractor_id:
                try:
                    validation_service = self.env['construction.contract.validation.service']
                    result = validation_service.validate_subcontractor_eligibility(
                        wizard.subcontractor_id
                    )

                    wizard.subcontractor_documents_valid = result['eligible']
                    wizard.subcontractor_warning = '\n'.join(result.get('warnings', []))

                except ValidationError as e:
                    wizard.subcontractor_documents_valid = False
                    wizard.subcontractor_warning = str(e)
            else:
                wizard.subcontractor_documents_valid = False
                wizard.subcontractor_warning = ''

    @api.depends('chantier_id', 'lot_ids', 'subcontractor_id', 'state')
    def _compute_document_status(self):
        """Check presence of required documents for Step 3."""
        for wizard in self:
            if wizard.state != 'step3':
                wizard.has_planning_general = False
                wizard.missing_cctp_lots = ''
                wizard.missing_planning_lots = ''
                wizard.missing_po_lots = ''
                wizard.total_po_amount = 0.0
                wizard.step3_valid = False
                continue

            # 1. Planning Général
            wizard.has_planning_general = bool(wizard.chantier_id and getattr(wizard.chantier_id, 'planning_general_attachment_id', False))
            
            # 2. CCTP and Planning ST per Lot
            missing_cctp = []
            missing_planning = []
            for lot in wizard.lot_ids:
                if not getattr(lot, 'document_cctp', False):
                    missing_cctp.append(lot.name)
                if not getattr(lot, 'document_planning_sous_traitant', False):
                    missing_planning.append(lot.name)
            
            wizard.missing_cctp_lots = ', '.join(missing_cctp) if missing_cctp else ''
            wizard.missing_planning_lots = ', '.join(missing_planning) if missing_planning else ''
            
            # 3. Purchase Orders integration
            missing_po = []
            total_amount = 0.0
            for lot in wizard.lot_ids:
                pos = self.env['purchase.order'].search([
                    ('lot_ids', 'in', lot.id),
                    ('partner_id', '=', wizard.subcontractor_id.id),
                    ('state', 'in', ['purchase', 'done'])
                ])
                if not pos:
                    missing_po.append(lot.name)
                else:
                    total_amount += sum(pos.mapped('amount_total'))
                    
            wizard.missing_po_lots = ', '.join(missing_po) if missing_po else ''
            wizard.total_po_amount = total_amount
            
            # Determine if Step 3 is perfectly valid
            wizard.step3_valid = wizard.has_planning_general and \
                                 not missing_cctp and \
                                 not missing_planning and \
                                 not missing_po

    # ============================================================
    # VALIDATION
    # ============================================================

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        """Validate date logic"""
        for wizard in self:
            if wizard.start_date and wizard.end_date:
                if wizard.end_date < wizard.start_date:
                    raise ValidationError(_("End date must be after start date."))

    @api.constrains('chantier_id', 'lot_ids')
    def _check_lots_coherence(self):
        """Ensure selected lots belong to chantier"""
        for wizard in self:
            if wizard.chantier_id and wizard.lot_ids:
                invalid_lots = wizard.lot_ids.filtered(
                    lambda l: l.chantier_id != wizard.chantier_id
                )
                if invalid_lots:
                    raise ValidationError(_(
                        "These lots do not belong to the selected construction site: %s"
                    ) % ', '.join(invalid_lots.mapped('name')))

    @api.constrains('retention_rate')
    def _check_retention_rate(self):
        """Ensure retention rate stays within legal bounds."""
        for wizard in self:
            if wizard.retention_rate < 0 or wizard.retention_rate > 20:
                raise ValidationError(_("Retention rate must be between 0% and 20%."))

    # ============================================================
    # ACTIONS
    # ============================================================

    def action_next(self):
        """Move to the next step in the wizard."""
        self.ensure_one()
        if self.state == 'step1':
            if not self.subcontractor_id:
                raise ValidationError(_("Veuillez sélectionner un sous-traitant."))
            self.state = 'step2'
        elif self.state == 'step2':
            if not self.lot_ids:
                raise ValidationError(_("Veuillez sélectionner au moins un lot."))
            self.state = 'step3'
        elif self.state == 'step3':
            # F-02: Bloquer l'envoi si documents manquants (CCTP, Planning, BC)
            if not self.step3_valid:
                raise ValidationError(_("Veuillez vous assurer que tous les documents requis sont présents avant de continuer."))
            self.state = 'step4'
            
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'contract.creation.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_previous(self):
        """Move to the previous step in the wizard."""
        self.ensure_one()
        if self.state == 'step2':
            self.state = 'step1'
        elif self.state == 'step3':
            self.state = 'step2'
        elif self.state == 'step4':
            self.state = 'step3'
            
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'contract.creation.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_create_contract(self):
        """
        Create contract from wizard data (called at step 4)

        Returns:
            dict: Action to open created contract
        """
        self.ensure_one()

        # Final validation — non-compliant docs open a warning wizard instead of blocking
        if not self.subcontractor_documents_valid and not self.bypass_compliance_check:
            return self._action_open_compliance_warning()

        # Check lots don't already have a contract
        lots_with_contract = self.lot_ids.filtered(lambda l: l.contract_id)
        if lots_with_contract:
            raise ValidationError(_(
                "Les lots suivants ont déjà un contrat : %s"
            ) % ', '.join(lots_with_contract.mapped('name')))

        # Validate with service
        validation_service = self.env['construction.contract.validation.service']
        validation_service.validate_contract_data({
            'chantier_id': self.chantier_id.id,
            'subcontractor_id': self.subcontractor_id.id,
            'lot_ids': self.lot_ids.ids,  # Just IDs for validation
            'start_date': self.start_date,
            'end_date': self.end_date,
            'date': self.contract_date,
            'retention_rate': self.retention_rate,
        })

        # Create contract (without lot_ids - they are One2many inverse)
        contract = self.env['construction.contract'].create({
            'bypass_compliance_check': self.bypass_compliance_check,
            'chantier_id': self.chantier_id.id,
            'subcontractor_id': self.subcontractor_id.id,
            'partner_id': self.subcontractor_id.id,  # Required by DB constraint / portal.mixin
            'date': self.contract_date,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'template_id': self.template_id.id,
            'retention_rate': self.retention_rate,
        })

        # Assign contract_id to selected lots (One2many inverse)
        self.lot_ids.write({'contract_id': contract.id})
        
        # Link Purchase Orders to the contract
        linked_pos = self.env['purchase.order'].search([
            ('lot_ids', 'in', self.lot_ids.ids),
            ('partner_id', '=', self.subcontractor_id.id),
            ('state', 'in', ['purchase', 'done'])
        ])
        if linked_pos:
            contract.write({'purchase_order_ids': [(6, 0, linked_pos.ids)]})
            
        # Trigger Document Sync (F-02)
        contract._sync_contractual_documents()

        # Generate deliverables if requested
        if self.generate_deliverables:
            self._generate_deliverables(contract)

        _logger.info(f"Contract {contract.name} created via wizard by user {self.env.user.name}")

        # Generate contract template (prefill with data) and open interactive editor
        try:
            contract.action_generate_contract()  # Prefill HTML template with contract data
            return contract.action_open_contract_editor()  # Open GrapeJS editor
        except Exception as e:
            _logger.warning(f"Could not open editor: {e}, falling back to form view")
            # Fallback to contract form view
            return {
                'type': 'ir.actions.act_window',
                'name': _('Contract Created'),
                'res_model': 'construction.contract',
                'res_id': contract.id,
                'view_mode': 'form',
                'target': 'current',
            }

    def _generate_deliverables(self, contract):
        """
        Auto-generate standard deliverables

        Args:
            contract: construction.contract record
        """
        deliverable_obj = self.env['construction.contract.deliverable']

        # Generate deliverables from subcontractor documents
        for doc_type in ['urssaf', 'kbis', 'insurance']:
            try:
                deliverable_obj.create_from_partner_document(contract, doc_type)
            except Exception as e:
                _logger.warning(f"Could not create deliverable for {doc_type}: {e}")

        _logger.info(f"Generated deliverables for contract {contract.name}")

    def _action_open_compliance_warning(self):
        """Open the compliance warning wizard to let the user proceed anyway."""
        self.ensure_one()
        warning = self.env['contract.compliance.warning.wizard'].create({
            'creation_wizard_id': self.id,
            'warning_message': self.subcontractor_warning,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Avertissement — Documents non conformes'),
            'res_model': 'contract.compliance.warning.wizard',
            'res_id': warning.id,
            'view_mode': 'form',
            'target': 'new',
        }
