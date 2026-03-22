# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class BillingCycleTemplate(models.Model):
    _name = 'construction.billing.cycle.template'
    _description = 'Billing Cycle Template'
    _order = 'sequence, name'

    name = fields.Char(string="Nom du modèle", required=True)
    sequence = fields.Integer(default=10)
    step_templates = fields.One2many(
        'construction.billing.step.template',
        'template_id',
        string="Étapes",
        copy=True,
    )
    total_percent = fields.Float(
        string="Total (%)",
        compute='_compute_total_percent',
    )

    @api.depends('step_templates.percentage')
    def _compute_total_percent(self):
        for tmpl in self:
            tmpl.total_percent = sum(tmpl.step_templates.mapped('percentage'))

    @api.constrains('step_templates')
    def _check_total_percentage(self):
        for tmpl in self:
            total = sum(tmpl.step_templates.mapped('percentage'))
            if total > 100.001:
                raise UserError(
                    _("Le total des pourcentages dépasse 100%% (%.2f%%).") % total
                )


class BillingStepTemplate(models.Model):
    _name = 'construction.billing.step.template'
    _description = 'Billing Step Template'
    _order = 'sequence, id'

    template_id = fields.Many2one(
        'construction.billing.cycle.template',
        string="Modèle",
        required=True,
        ondelete='cascade',
    )
    name = fields.Char(string="Description", required=True)
    percentage = fields.Float(string="Pourcentage (%)", digits=(16, 2))
    sequence = fields.Integer(default=10)
