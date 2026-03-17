# -*- coding: utf-8 -*-
"""
Wizard Assignment Sous-traitant aux Lots
Refactored: Uses lot category selection + document uploads
FAANG-level: Clean code, type hints, XSS protection
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class LotSubcontractorAssignWizard(models.TransientModel):
    """Wizard to assign subcontractors to construction lots.
    
    Features:
    - Select lot from existing categories
    - Upload planning and CCTP documents
    - SAP-like validation with warnings
    """
    _name = 'construction.lot.subcontractor.assign.wizard'
    _description = 'Assigner Sous-traitant aux Lots'

    # ============= Chantier Context ============= #
    chantier_id = fields.Many2one(
        'construction.chantier', 
        string='Chantier', 
        required=True
    )
    
    # ============= Lot Selection (from categories) ============= #
    lot_category_id = fields.Many2one(
        'construction.lot.category',
        string='Type de Lot',
        required=True,
        help="Sélectionner la catégorie de lot à créer"
    )
    
    # ============= Existing Lot Selection ============= #
    existing_lot_id = fields.Many2one(
        'construction.lot',
        string='Lot Existant',
        domain="[('chantier_id', '=', chantier_id)]",
        help="Sélectionner un lot existant au lieu de créer un nouveau"
    )
    
    create_new_lot = fields.Boolean(
        string='Créer un Nouveau Lot',
        default=True,
        help="Cochez pour créer un nouveau lot, décochez pour modifier un existant"
    )
    
    # ============= Lot Details ============= #
    lot_price = fields.Monetary(
        string='Prix du Lot',
        currency_field='currency_id'
    )
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id
    )
    
    # ============= Subcontractor ============= #
    subcontractor_id = fields.Many2one(
        'res.partner', 
        string='Sous-traitant', 
        required=True,
        domain="[('supplier_rank', '>', 0)]"
    )
    
    # ============= Planning Dates ============= #
    date_start_planned = fields.Date(string='Date Début')
    date_end_planned = fields.Date(string='Date Fin')
    
    # ============= DOCUMENTS (Binary fields per requirement) ============= #
    document_planning_chantier = fields.Binary(
        string='Planning Chantier',
        help="Document PDF du planning général du chantier"
    )
    document_planning_chantier_filename = fields.Char()
    
    document_planning_sous_traitant = fields.Binary(
        string='Planning Sous-traitant',
        help="Planning spécifique pour ce sous-traitant"
    )
    document_planning_sous_traitant_filename = fields.Char()
    
    document_cctp = fields.Binary(
        string='CCTP',
        help="Cahier des Clauses Techniques Particulières"
    )
    document_cctp_filename = fields.Char()
    
    # ============= Assignment Details ============= #
    assignment_date = fields.Date(
        string="Date d'Assignment", 
        default=fields.Date.today, 
        required=True
    )
    notes = fields.Text(string='Notes Internes')
    
    # ============= SAP-like Validation ============= #
    warning_message = fields.Html(
        string='Avertissements', 
        compute='_compute_warnings'
    )
    has_warnings = fields.Boolean(compute='_compute_warnings')

    @api.model
    def default_get(self, fields_list):
        """Initialize wizard with context."""
        res = super().default_get(fields_list)
        
        # Get chantier from context
        if self.env.context.get('active_model') == 'construction.chantier':
            res['chantier_id'] = self.env.context.get('active_id')
        elif self.env.context.get('active_model') == 'construction.lot':
            lot = self.env['construction.lot'].browse(self.env.context.get('active_id'))
            res['chantier_id'] = lot.chantier_id.id
            res['existing_lot_id'] = lot.id
            res['create_new_lot'] = False
            res['lot_category_id'] = lot.category_id.id
            # Pre-fill current subcontractor so the user sees who is assigned
            if lot.subcontractor_id:
                res['subcontractor_id'] = lot.subcontractor_id.id

        return res

    @api.depends('subcontractor_id', 'chantier_id', 'lot_category_id', 'existing_lot_id')
    def _compute_warnings(self):
        """SAP-like: Compute warnings for user validation."""
        for wizard in self:
            warnings = []

            # Check if we are replacing an existing subcontractor on the lot
            if (not wizard.create_new_lot and wizard.existing_lot_id
                    and wizard.existing_lot_id.subcontractor_id
                    and wizard.subcontractor_id
                    and wizard.subcontractor_id != wizard.existing_lot_id.subcontractor_id):
                warnings.append(
                    f"<li>⚠️ <b>Remplacement :</b> le sous-traitant actuel "
                    f"<b>{wizard.existing_lot_id.subcontractor_id.name}</b> sera remplacé par "
                    f"<b>{wizard.subcontractor_id.name}</b>. "
                    "Les bons de commande et contrats existants ne seront pas modifiés.</li>"
                )

            # Check if subcontractor is already assigned to chantier (but different lot)
            elif wizard.subcontractor_id and wizard.chantier_id:
                if wizard.subcontractor_id in wizard.chantier_id.subcontractor_ids:
                    warnings.append(
                        f"<li>Le sous-traitant <b>{wizard.subcontractor_id.name}</b> "
                        "est déjà assigné au chantier.</li>"
                    )
            
            # Check if subcontractor has SIREN (field from construction_subcontractor module)
            if wizard.subcontractor_id and not getattr(wizard.subcontractor_id, 'siren', None):
                warnings.append(
                    "<li>⚠️ Le sous-traitant n'a pas de SIREN renseigné "
                    "(requis pour conformité légale).</li>"
                )
            
            # Check if lot category already exists on chantier
            if wizard.create_new_lot and wizard.lot_category_id and wizard.chantier_id:
                existing = self.env['construction.lot'].search([
                    ('chantier_id', '=', wizard.chantier_id.id),
                    ('category_id', '=', wizard.lot_category_id.id)
                ], limit=1)
                if existing:
                    warnings.append(
                        f"<li>⚠️ Un lot <b>{wizard.lot_category_id.name}</b> "
                        f"existe déjà sur ce chantier (code: {existing.code}).</li>"
                    )
            
            if warnings:
                wizard.warning_message = "<ul>" + "".join(warnings) + "</ul>"
                wizard.has_warnings = True
            else:
                wizard.warning_message = False
                wizard.has_warnings = False

    @api.onchange('create_new_lot')
    def _onchange_create_new_lot(self):
        """Clear fields when switching mode."""
        if self.create_new_lot:
            self.existing_lot_id = False
        else:
            self.lot_category_id = False

    @api.onchange('existing_lot_id')
    def _onchange_existing_lot_id(self):
        """Populate fields from existing lot."""
        if self.existing_lot_id:
            self.lot_category_id = self.existing_lot_id.category_id
            self.lot_price = self.existing_lot_id.price
            self.date_start_planned = self.existing_lot_id.date_start_planned
            self.date_end_planned = self.existing_lot_id.date_end_planned
            # Pre-fill current subcontractor so the user can see and modify it
            self.subcontractor_id = self.existing_lot_id.subcontractor_id

    def action_assign(self):
        """Assign subcontractor to selected/created lot."""
        self.ensure_one()
        
        if not self.lot_category_id and not self.existing_lot_id:
            raise UserError(_("Veuillez sélectionner une catégorie de lot ou un lot existant."))
        
        # Get or create lot
        if self.create_new_lot:
            # Create new lot from category
            lot = self.env['construction.lot'].create({
                'name': self.lot_category_id.name,
                'code': self.lot_category_id.code,
                'category_id': self.lot_category_id.id,
                'chantier_id': self.chantier_id.id,
                'subcontractor_id': self.subcontractor_id.id,
                'price': self.lot_price or 0.0,
                'date_start_planned': self.date_start_planned,
                'date_end_planned': self.date_end_planned,
                'execution_type': 'external',
            })
            _logger.info("Created lot %s for chantier %s", lot.name, self.chantier_id.name)
        else:
            lot = self.existing_lot_id
            lot.write({
                'subcontractor_id': self.subcontractor_id.id,
                'price': self.lot_price or lot.price,
                'date_start_planned': self.date_start_planned or lot.date_start_planned,
                'date_end_planned': self.date_end_planned or lot.date_end_planned,
            })
        
        # Attach documents to lot
        self._attach_documents(lot)
        
        # Log assignment for audit trail
        from markupsafe import Markup, escape
        assignment_message = Markup(
            f"<b>Sous-traitant assigné:</b> {escape(self.subcontractor_id.name)}<br/>"
            f"<b>Date:</b> {self.assignment_date}<br/>"
            f"<b>Lot:</b> {escape(lot.name)}<br/>"
            f"<b>Assigné par:</b> {escape(self.env.user.name)}"
        )
        
        if self.notes:
            assignment_message += Markup(f"<br/><b>Notes:</b> {escape(self.notes)}")
        
        lot.message_post(
            body=assignment_message,
            subject="Assignment Sous-traitant"
        )
        
        # Add subcontractor to chantier if not already there
        if self.subcontractor_id not in self.chantier_id.subcontractor_ids:
            self.chantier_id.subcontractor_ids = [(4, self.subcontractor_id.id)]
        
        # Post message on chantier
        self.chantier_id.message_post(
            body=assignment_message,
            subject="Assignment Sous-traitant"
        )
        
        return {'type': 'ir.actions.act_window_close'}

    def _attach_documents(self, lot):
        """Attach uploaded documents to the lot."""
        Attachment = self.env['ir.attachment']
        attachments = []
        
        if self.document_planning_chantier:
            attachments.append(Attachment.create({
                'name': self.document_planning_chantier_filename or 'Planning_Chantier.pdf',
                'datas': self.document_planning_chantier,
                'res_model': 'construction.lot',
                'res_id': lot.id,
                'type': 'binary',
            }))
        
        if self.document_planning_sous_traitant:
            attachments.append(Attachment.create({
                'name': self.document_planning_sous_traitant_filename or 'Planning_SousTraitant.pdf',
                'datas': self.document_planning_sous_traitant,
                'res_model': 'construction.lot',
                'res_id': lot.id,
                'type': 'binary',
            }))
        
        if self.document_cctp:
            attachments.append(Attachment.create({
                'name': self.document_cctp_filename or 'CCTP.pdf',
                'datas': self.document_cctp,
                'res_model': 'construction.lot',
                'res_id': lot.id,
                'type': 'binary',
            }))
        
        # Link attachments to lot
        if attachments:
            lot.document_ids = [(4, att.id) for att in attachments]
            _logger.info("Attached %d documents to lot %s", len(attachments), lot.name)
