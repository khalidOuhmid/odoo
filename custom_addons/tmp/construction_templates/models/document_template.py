# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ConstructionDocumentTemplate(models.Model):
    _name = 'construction.document.template'
    _description = 'Unified Document Template'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'template_type, name'

    # Identification
    name = fields.Char(string='Nom', required=True, tracking=True)
    code = fields.Char(string='Code', required=True, copy=False)
    template_type = fields.Selection([
        ('contract', 'Contrat de sous-traitance'),
        ('invoice', 'Facture'),
        ('quote', 'Devis'),
        ('purchase', 'Bon de commande'),
    ], string='Type', required=True, tracking=True)

    # Content (GrapesJS)
    html_content = fields.Html(string='Contenu HTML', sanitize=False)
    css_content = fields.Text(string='Styles CSS')
    grapesjs_data = fields.Text(string='Données GrapesJS')

    # Signature zones
    signature_zone_ids = fields.One2many(
        'construction.signature.zone',
        'template_id',
        string='Zones de signature'
    )

    # Status
    is_active = fields.Boolean(string='Actif', default=False, tracking=True)
    is_default = fields.Boolean(string='Par défaut', default=False, tracking=True)
    company_id = fields.Many2one(
        'res.company',
        string='Société',
        default=lambda self: self.env.company
    )

    # Versioning
    version = fields.Integer(string='Version', default=1, readonly=True)
    version_history_ids = fields.One2many(
        'construction.template.version',
        'template_id',
        string='Historique des versions'
    )

    # Statistics
    usage_count = fields.Integer(
        string='Utilisations',
        compute='_compute_usage_count',
        store=True
    )

    _sql_constraints = [
        ('code_uniq', 'unique(code, company_id)',
         'Le code du template doit être unique par société.'),
    ]

    @api.constrains('is_active', 'template_type', 'company_id')
    def _check_unique_active_template(self):
        """Ensure only one active template per type per company."""
        for record in self:
            if record.is_active:
                domain = [
                    ('id', '!=', record.id),
                    ('template_type', '=', record.template_type),
                    ('company_id', '=', record.company_id.id),
                    ('is_active', '=', True),
                ]
                if self.search_count(domain) > 0:
                    raise ValidationError(
                        f"Un template actif de type '{record.template_type}' "
                        f"existe déjà pour cette société."
                    )

    @api.depends()
    def _compute_usage_count(self):
        """Compute how many times this template has been used."""
        for record in self:
            # Will be implemented when contracts link to templates
            record.usage_count = 0

    def action_activate(self):
        """Activate this template and deactivate others of same type."""
        self.ensure_one()
        # Deactivate other templates of same type
        self.search([
            ('id', '!=', self.id),
            ('template_type', '=', self.template_type),
            ('company_id', '=', self.company_id.id),
            ('is_active', '=', True),
        ]).write({'is_active': False})
        self.is_active = True

    def action_deactivate(self):
        """Deactivate this template."""
        self.is_active = False

    def action_duplicate(self):
        """Duplicate template with new code."""
        self.ensure_one()
        return self.copy({
            'name': f"{self.name} (copie)",
            'code': f"{self.code}_copy",
            'is_active': False,
            'is_default': False,
            'version': 1,
        })

    def action_open_editor(self):
        """Open GrapesJS editor for this template."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/construction/template/editor/{self.id}',
            'target': 'new',
        }

    def action_preview_pdf(self):
        """Generate a PDF preview of the template."""
        self.ensure_one()
        # Return action to download/preview PDF
        return {
            'type': 'ir.actions.act_url',
            'url': f'/construction/template/preview/{self.id}',
            'target': 'new',
        }

    @api.model_create_multi
    def create(self, vals_list):
        """Create template and initial version snapshot."""
        records = super().create(vals_list)
        for record in records:
            record._create_version_snapshot('Création initiale')
        return records

    def write(self, vals):
        """Track content changes and create version snapshots."""
        content_fields = {'html_content', 'css_content', 'grapesjs_data'}
        if content_fields & set(vals.keys()):
            for record in self:
                record._create_version_snapshot('Modification du contenu')
                vals['version'] = record.version + 1
        return super().write(vals)

    def _create_version_snapshot(self, description=''):
        """Create a version snapshot of current template state."""
        self.ensure_one()
        self.env['construction.template.version'].create({
            'template_id': self.id,
            'version_number': self.version,
            'html_snapshot': self.html_content or '',
            'css_snapshot': self.css_content or '',
            'grapesjs_snapshot': self.grapesjs_data or '',
            'description': description,
        })
