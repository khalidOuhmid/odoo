# -*- coding: utf-8 -*-
"""
Contract Validation Service
Centralizes business rules to validate subcontractor eligibility
and contract data before creation.
"""

from odoo import models, _
from odoo.exceptions import ValidationError

COMPLIANT_DOCUMENT_STATUSES = {'valid', 'expiring'}


class ContractValidationService(models.AbstractModel):
    _name = 'construction.contract.validation.service'
    _description = 'Contract Validation Service'

    # ============================================================
    # PUBLIC API
    # ============================================================

    def validate_subcontractor_eligibility(self, partner):
        """Validate subcontractor mandatory documents.

        Args:
            partner (res.partner): subcontractor record

        Returns:
            dict: {
                'eligible': bool,
                'warnings': [str...]
            }
        """
        if not partner:
            return {'eligible': False, 'warnings': [_("No subcontractor selected.")]}

        warnings = []

        # These document fields come from blg_contacts_extension
        doc_checks = [
            ('document_URSSAF_status', 'document_URSSAF', _("URSSAF certificate")),
            ('document_KBIS_status', 'document_KBIS', _("KBIS extract")),
            ('document_insurance_status', 'document_insurance', _("Insurance certificate")),
        ]

        for status_field, file_field, label in doc_checks:
            status_value = getattr(partner, status_field, False)
            has_file = bool(getattr(partner, file_field, False))
            field_def = partner._fields.get(status_field)
            selection_mapping = dict(getattr(field_def, 'selection', [])) if field_def else {}
            human_status = selection_mapping.get(status_value, status_value) if selection_mapping else status_value

            if not has_file:
                warnings.append(
                    _("%s file is missing on the subcontractor record.") % label
                )
                continue

            if status_value not in COMPLIANT_DOCUMENT_STATUSES:
                warnings.append(
                    _("%s is not compliant. Status: %s") % (label, human_status or _('Unknown'))
                )

        siret_value = getattr(partner, 'siren', False) or partner.company_registry
        if not siret_value:
            warnings.append(_("SIRET number is missing on the subcontractor record."))

        return {
            'eligible': len(warnings) == 0,
            'warnings': warnings,
        }

    def validate_contract_data(self, values):
        """Validate data before contract creation.

        Args:
            values (dict): contract values
        """
        if not values.get('chantier_id'):
            raise ValidationError(_("Construction site (chantier) is required."))

        if not values.get('subcontractor_id'):
            raise ValidationError(_("Subcontractor must be selected."))

        lot_command = values.get('lot_ids', [])
        lot_ids = set(lot_command[0][2]) if lot_command and lot_command[0][0] == 6 else set()
        if not lot_ids:
            raise ValidationError(_("Please select at least one lot for the contract."))

        start = values.get('start_date')
        end = values.get('end_date')
        if start and end and end < start:
            raise ValidationError(_("End date must be greater than start date."))

