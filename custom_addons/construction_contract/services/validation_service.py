# -*- coding: utf-8 -*-
"""
Contract Validation Service
Centralizes business rules to validate subcontractor eligibility
and contract data before creation.
"""

from odoo import models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

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
            _logger.warning("Subcontractor eligibility check: no partner provided")
            return {
                'eligible': False,
                'warnings': [_("❌ Aucun sous-traitant sélectionné.")]
            }

        _logger.info(f"Validating subcontractor eligibility for {partner.name} (ID: {partner.id})")
        warnings = []

        # Document checks mapping: (status_field, file_field, label)
        # Using fields from construction_subcontractor module
        doc_checks = [
            ('doc_urssaf_status', 'doc_urssaf', _("Attestation URSSAF")),
            ('doc_kbis_status', 'doc_kbis', _("Extrait KBIS")),
            ('doc_insurance_dec_status', 'doc_insurance_dec', _("Assurance Décennale")),
        ]

        for status_field, file_field, label in doc_checks:
            status_value = getattr(partner, status_field, False)
            has_file = bool(getattr(partner, file_field, False))
            field_def = partner._fields.get(status_field)
            selection_mapping = dict(getattr(field_def, 'selection', [])) if field_def else {}
            human_status = selection_mapping.get(status_value, status_value) if selection_mapping else status_value

            if not has_file:
                warnings.append(
                    _("⚠️ Document manquant : %s\n"
                      "Le fichier %s n'est pas présent dans la fiche du sous-traitant.") % (label, label)
                )
                continue

            if status_value not in COMPLIANT_DOCUMENT_STATUSES:
                warnings.append(
                    _("⚠️ Document non conforme : %s\n"
                      "Statut actuel : %s\n"
                      "Le document doit être valide ou en cours d'expiration.") % (label, human_status or _('Inconnu'))
                )

        siret_value = getattr(partner, 'siren', False) or partner.company_registry
        if not siret_value:
            warnings.append(
                _("⚠️ Numéro SIRET manquant\n"
                  "Le numéro SIRET n'est pas renseigné dans la fiche du sous-traitant.\n"
                  "Ce numéro est obligatoire pour créer un contrat.")
            )

        is_eligible = len(warnings) == 0
        
        if is_eligible:
            _logger.info(f"✓ Subcontractor {partner.name} is eligible (all documents valid)")
        else:
            _logger.warning(
                f"⚠️ Subcontractor {partner.name} has {len(warnings)} warning(s): "
                f"{'; '.join(warnings[:3])}"  # Log first 3 warnings
            )
        
        return {
            'eligible': is_eligible,
            'warnings': warnings,
        }

    def validate_contract_data(self, values):
        """Validate data before contract creation.

        Args:
            values (dict): contract values
            
        Raises:
            ValidationError: If validation fails with French error message
        """
        _logger.info("Validating contract data before creation")
        
        if not values.get('chantier_id'):
            _logger.error("✗ Contract validation failed: no chantier_id")
            raise ValidationError(_(
                "❌ Chantier manquant\n\n"
                "Un chantier doit être sélectionné pour créer un contrat.\n\n"
                "Veuillez sélectionner un chantier dans le champ 'Chantier'."
            ))

        if not values.get('subcontractor_id'):
            _logger.error("✗ Contract validation failed: no subcontractor_id")
            raise ValidationError(_(
                "❌ Sous-traitant manquant\n\n"
                "Un sous-traitant doit être sélectionné pour créer un contrat.\n\n"
                "Veuillez sélectionner un sous-traitant dans le champ 'Sous-traitant'."
            ))

        # Parse lot_ids (can be: list of ints, recordset, or Many2many command)
        lot_value = values.get('lot_ids', [])
        lot_ids = set()
        
        if hasattr(lot_value, 'ids'):
            # It's a recordset
            lot_ids = set(lot_value.ids)
        elif isinstance(lot_value, (list, tuple)):
            if lot_value and isinstance(lot_value[0], int):
                # Direct list of IDs: [1, 2, 3]
                lot_ids = set(lot_value)
            elif lot_value and isinstance(lot_value[0], (list, tuple)) and len(lot_value[0]) >= 3:
                # Many2many command: [(6, 0, [1, 2, 3])]
                if lot_value[0][0] == 6:
                    lot_ids = set(lot_value[0][2])
        
        if not lot_ids:
            _logger.error("✗ Contract validation failed: no lots selected")
            raise ValidationError(_(
                "❌ Lots manquants\n\n"
                "Au moins un lot doit être sélectionné pour créer un contrat.\n\n"
                "Veuillez sélectionner un ou plusieurs lots dans le champ 'Lots'."
            ))

        start = values.get('start_date')
        end = values.get('end_date')
        if start and end and end < start:
            _logger.error(
                f"✗ Contract validation failed: invalid dates (start={start}, end={end})"
            )
            raise ValidationError(_(
                "❌ Dates invalides\n\n"
                "La date de fin doit être postérieure à la date de début.\n\n"
                "Date de début : %s\n"
                "Date de fin : %s\n\n"
                "Veuillez corriger les dates."
            ) % (start, end))
        
        _logger.info(
            f"✓ Contract data validation passed: "
            f"chantier_id={values.get('chantier_id')}, "
            f"subcontractor_id={values.get('subcontractor_id')}, "
            f"lots={len(lot_ids)}"
        )

