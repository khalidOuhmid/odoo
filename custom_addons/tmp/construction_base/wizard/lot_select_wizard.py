# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ConstructionLotSelectWizard(models.TransientModel):
    _name = 'construction.lot.select.wizard'
    _description = 'Sélection des lots à créer pour le chantier'

    chantier_id = fields.Many2one(
        'construction.chantier',
        string='Chantier',
        required=True,
        readonly=True,
    )

    template_ids = fields.Many2many(
        'construction.lot.template',
        string='Templates de lots',
        domain=[('active', '=', True)],
        help="Sélectionnez les lots à créer pour ce chantier",
        required=True,
    )

    def action_create_selected_lots(self):
        self.ensure_one()
        if not self.template_ids:
            raise ValidationError(_('Veuillez sélectionner au moins un template de lot.'))

        created = self.env['construction.lot']
        for template in self.template_ids:
            created |= template.create_lot_for_chantier(self.chantier_id.id)

        # Notification et retour sur l'onglet lots du chantier
        self.chantier_id.message_post(
            body=_('%s lot(s) créé(s) depuis les templates.') % len(created),
            message_type='notification'
        )

        return {
            'type': 'ir.actions.act_window',
            'name': _('Lots du chantier'),
            'res_model': 'construction.chantier',
            'res_id': self.chantier_id.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'active_id': self.chantier_id.id,
            }
        }


