# -*- coding: utf-8 -*-
"""
Deliverable Selector Wizard
Allows users to choose which deliverables to generate for a contract.
"""

from odoo import models, fields, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class DeliverableSelectorWizard(models.TransientModel):
    """
    Wizard used to mass-generate deliverables (documents) for a contract.
    Users can choose which subcontractor documents and planning files to include.
    """

    _name = 'deliverable.selector.wizard'
    _description = 'Deliverable Selector Wizard'

    # ======================================================================
    # CORE FIELDS
    # ======================================================================

    contract_id = fields.Many2one(
        'construction.contract',
        string='Contract',
        required=True,
        ondelete='cascade'
    )

    # User choices
    include_urssaf = fields.Boolean(string='URSSAF Certificate', default=True)
    include_kbis = fields.Boolean(string='KBIS Extract', default=True)
    include_insurance = fields.Boolean(string='Insurance Certificate', default=True)
    include_rib = fields.Boolean(string='Bank Details (RIB)', default=False)
    include_planning = fields.Boolean(string='Planning (Tasks)', default=True)
    include_general_planning = fields.Boolean(string='General Planning Documents', default=False)

    # Availability indicators (computed)
    urssaf_available = fields.Boolean(compute='_compute_document_availability')
    kbis_available = fields.Boolean(compute='_compute_document_availability')
    insurance_available = fields.Boolean(compute='_compute_document_availability')
    rib_available = fields.Boolean(compute='_compute_document_availability')

    planning_tasks_count = fields.Integer(compute='_compute_planning_stats')

    # ======================================================================
    # COMPUTE HELPERS
    # ======================================================================

    def _compute_document_availability(self):
        """Check which subcontractor documents are available."""
        for wizard in self:
            partner = wizard.contract_id.subcontractor_id
            wizard.urssaf_available = bool(getattr(partner, 'document_URSSAF', False))
            wizard.kbis_available = bool(getattr(partner, 'document_KBIS', False))
            wizard.insurance_available = bool(getattr(partner, 'document_insurance', False))
            wizard.rib_available = bool(getattr(partner, 'document_RIB', False))

    def _compute_planning_stats(self):
        """Count relevant planning tasks for the contract."""
        for wizard in self:
            wizard.planning_tasks_count = len(wizard._get_planning_tasks())

    # ======================================================================
    # HELPERS
    # ======================================================================

    def _get_planning_tasks(self):
        """Return planning tasks relevant for this contract."""
        self.ensure_one()
        tasks = self.contract_id.chantier_id.planning_task_ids
        if self.contract_id.lot_ids:
            tasks = tasks.filtered(
                lambda t: not t.lot_id or t.lot_id in self.contract_id.lot_ids
            )
        return tasks

    def _get_general_planning_documents(self):
        """
        Gather general planning binaries from lots linked to the contract.
        Returns list of tuples (name, binary, filename).
        """
        documents = []
        for lot in self.contract_id.lot_ids:
            if lot.document_general_planning:
                documents.append((
                    _('General Planning - %s') % lot.name,
                    lot.document_general_planning,
                    'planning_general_%s.pdf' % lot.name.replace(' ', '_')
                ))

            if lot.document_subcontractor_planning:
                documents.append((
                    _('Subcontractor Planning - %s') % lot.name,
                    lot.document_subcontractor_planning,
                    'planning_subcontractor_%s.pdf' % lot.name.replace(' ', '_')
                ))
        return documents

    # ======================================================================
    # ACTION
    # ======================================================================

    def action_generate_deliverables(self):
        """Create deliverables according to the user selections."""
        self.ensure_one()

        if not self.contract_id:
            raise ValidationError(_("No contract selected."))

        deliverable_obj = self.env['construction.contract.deliverable']

        # Map selection fields to deliverable creation helper
        document_mapping = {
            'include_urssaf': ('urssaf', self.urssaf_available),
            'include_kbis': ('kbis', self.kbis_available),
            'include_insurance': ('insurance', self.insurance_available),
            'include_rib': ('rib', self.rib_available),
        }

        for include_field, (doc_type, available) in document_mapping.items():
            if getattr(self, include_field) and available:
                try:
                    deliverable_obj.create_from_partner_document(self.contract_id, doc_type)
                except ValidationError as err:
                    # Ignore if missing; user already has visual indicator
                    _logger.warning("Deliverable %s could not be created: %s", doc_type, err)

        if self.include_planning and self.planning_tasks_count:
            tasks = self._get_planning_tasks()
            if tasks:
                deliverable_obj.create_from_planning(self.contract_id, tasks)

        if self.include_general_planning:
            for name, binary_data, filename in self._get_general_planning_documents():
                deliverable_obj.create({
                    'contract_id': self.contract_id.id,
                    'name': name,
                    'deliverable_type': 'planning_general',
                    'description': _('Planning document generated from lot data.'),
                    'document': binary_data,
                    'document_name': filename,
                    'is_generated': True,
                    'generation_date': fields.Datetime.now(),
                    'included_in_contract': True,
                })

        _logger.info("Deliverables generated via wizard for contract %s", self.contract_id.name)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Deliverables'),
            'res_model': 'construction.contract.deliverable',
            'view_mode': 'tree,form',
            'domain': [('contract_id', '=', self.contract_id.id)],
            'context': {'default_contract_id': self.contract_id.id},
        }


