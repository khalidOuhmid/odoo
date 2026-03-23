# -*- coding: utf-8 -*-
"""
Wizard de dérogation à la conformité documentaire des sous-traitants.
Remplace l'ancien contract.compliance.warning.wizard minimal.
Accessible aux admins et pilotes seulement (visibilité bouton contrôlée dans la vue).
"""

from datetime import datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from odoo.addons.construction_core.utils.logger import get_logger

_logger = get_logger(__name__)


class ComplianceOverrideWizard(models.TransientModel):
    """
    Wizard de dérogation conformité documentaire.

    Workflow :
    1. Pré-check détecte des documents non conformes.
    2. Ce wizard s'ouvre avec les documents concernés en lecture seule.
    3. L'utilisateur (admin ou pilote) renseigne la raison de dérogation.
    4. À la confirmation :
       - bypass_compliance_check = True sur le contrat / wizard de création
       - Log permanent créé dans construction.compliance.override.log
       - message_post sur le chantier avec traçabilité complète
    """

    _name = 'construction.compliance.override.wizard'
    _description = 'Dérogation Conformité Sous-Traitant'

    # ── Contexte de la dérogation ─────────────────────────────────────

    contract_id = fields.Many2one(
        'construction.contract',
        string='Contrat',
        ondelete='cascade',
        help="Renseigné quand la dérogation est demandée depuis un contrat existant."
    )

    creation_wizard_id = fields.Many2one(
        'contract.creation.wizard',
        string='Assistant de création',
        ondelete='cascade',
        help="Renseigné quand la dérogation est demandée depuis le wizard de création."
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Sous-traitant',
        readonly=True,
    )

    non_compliant_docs = fields.Text(
        string='Documents non conformes',
        readonly=True,
        help="Liste des documents identifiés comme non conformes."
    )

    # ── Champs de traçabilité ─────────────────────────────────────────

    override_reason = fields.Text(
        string='Raison de la dérogation',
        required=True,
        help="Justification obligatoire (minimum 20 caractères)."
    )

    override_by_id = fields.Many2one(
        'res.users',
        string='Autorisé par',
        default=lambda self: self.env.user.id,
        readonly=True,
    )

    override_date = fields.Datetime(
        string='Date de dérogation',
        default=lambda self: fields.Datetime.now(),
        readonly=True,
    )

    # ── Contrainte ────────────────────────────────────────────────────

    @api.constrains('override_reason')
    def _check_override_reason_length(self):
        for rec in self:
            if rec.override_reason and len(rec.override_reason.strip()) < 20:
                raise UserError(_(
                    "La raison de dérogation doit contenir au moins 20 caractères.\n"
                    "Actuellement : %d caractère(s)."
                ) % len(rec.override_reason.strip()))

    # ── Action de confirmation ────────────────────────────────────────

    def action_confirm_override(self):
        """Confirme la dérogation, crée le log et poursuit l'action bloquée."""
        self.ensure_one()

        # Double vérification sécurité : seuls admin et pilote peuvent confirmer
        user = self.env.user
        is_authorized = (
            user.has_group('construction_core.group_construction_admin')
            or user.has_group('construction_contract.group_construction_pilote')
        )
        if not is_authorized:
            raise UserError(_(
                "Seuls les administrateurs et pilotes peuvent accorder une dérogation."
            ))

        partner = self.partner_id
        chantier = (
            self.contract_id.chantier_id
            if self.contract_id
            else self.creation_wizard_id.chantier_id if self.creation_wizard_id
            else False
        )

        # Créer le log permanent
        try:
            self.env['construction.compliance.override.log'].create({
                'contract_id': self.contract_id.id if self.contract_id else False,
                'chantier_id': chantier.id if chantier else False,
                'partner_id': partner.id if partner else False,
                'non_compliant_docs': self.non_compliant_docs or '',
                'override_reason': self.override_reason,
                'override_by_id': self.override_by_id.id,
                'override_date': self.override_date,
            })
        except Exception as e:
            _logger.business_error(self, 'compliance_override_log_create', e)
            raise UserError(_(
                "Impossible de créer le journal de dérogation. "
                "La dérogation n'a pas été accordée. Erreur : %s"
            ) % str(e))

        _logger.compliance_check(
            partner or self,
            'compliance_override',
            passed=False,
        )

        # Message sur le chantier
        if chantier:
            chantier.message_post(
                body=_(
                    "<b>⚠ Dérogation conformité accordée</b><br/>"
                    "Sous-traitant : <b>%(partner)s</b><br/>"
                    "Documents concernés : %(docs)s<br/>"
                    "Raison : %(reason)s<br/>"
                    "Accordé par : %(user)s le %(date)s"
                ) % {
                    'partner': partner.name if partner else '—',
                    'docs': self.non_compliant_docs or '—',
                    'reason': self.override_reason,
                    'user': self.override_by_id.name,
                    'date': self.override_date.strftime('%d/%m/%Y %H:%M') if self.override_date else '—',
                },
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )

        # Continuer l'action bloquée
        if self.contract_id:
            self.contract_id.bypass_compliance_check = True
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'construction.contract',
                'res_id': self.contract_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        elif self.creation_wizard_id:
            self.creation_wizard_id.bypass_compliance_check = True
            return self.creation_wizard_id.action_create_contract()

        return {'type': 'ir.actions.act_window_close'}
