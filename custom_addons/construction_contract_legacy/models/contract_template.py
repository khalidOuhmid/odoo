# -*- coding: utf-8 -*-
"""
Contract Template Model
Manages editable contract templates with GrapesJS visual editor
Stores HTML, CSS, and component structure for reusability
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import json
import logging

_logger = logging.getLogger(__name__)

# Import template variables configuration
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config.template_variables import TEMPLATE_VARIABLES, get_variable_blocks_for_grapesjs


class ConstructionContractTemplate(models.Model):
    """
    Contract Template

    Allows end users to create and customize contract templates
    using GrapesJS visual editor without coding
    """

    _name = 'construction.contract.template'
    _description = 'Construction Contract Template'
    _order = 'sequence, name'

    # ============================================================
    # BASIC FIELDS
    # ============================================================

    name = fields.Char(
        string='Template Name',
        required=True,
        translate=True,
        help="Name of the contract template"
    )

    description = fields.Text(
        string='Description',
        translate=True,
        help="Internal description of this template's purpose"
    )

    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help="Order of appearance in lists"
    )

    active = fields.Boolean(
        default=True,
        help="Uncheck to hide template from users"
    )

    is_default = fields.Boolean(
        string='Default Template',
        default=False,
        help="If checked, this template is used by default for new contracts"
    )

    # ============================================================
    # GRAPESJS STORAGE
    # ============================================================

    grapesjs_html = fields.Html(
        string='HTML Content',
        sanitize=False,
        help="Generated HTML from GrapesJS editor"
    )

    grapesjs_css = fields.Text(
        string='CSS Styles',
        help="Generated CSS from GrapesJS editor"
    )

    grapesjs_components = fields.Text(
        string='GrapesJS Components (JSON)',
        help="JSON structure of GrapesJS components for re-editing"
    )

    grapesjs_styles = fields.Text(
        string='GrapesJS Styles (JSON)',
        help="JSON structure of GrapesJS styles for re-editing"
    )

    # ============================================================
    # TEMPLATE VARIABLES
    # ============================================================

    variable_ids = fields.One2many(
        'construction.contract.template.variable',
        'template_id',
        string='Available Variables',
        help="Jinja2 variables that can be used in this template"
    )

    # ============================================================
    # URSSAF CODE INTEGRATION
    # ============================================================

    urssaf_code_helper = fields.Char(
        string='URSSAF Code Helper',
        help="Helper field for URSSAF code selector widget"
    )

    # ============================================================
    # USAGE STATISTICS
    # ============================================================

    contract_count = fields.Integer(
        string='Contracts Using This Template',
        compute='_compute_contract_count',
        store=True,
        help="Number of contracts using this template"
    )

    last_used_date = fields.Datetime(
        string='Last Used',
        help="Date when this template was last used"
    )

    # ============================================================
    # COMPUTED FIELDS
    # ============================================================

    def _compute_contract_count(self):
        """Count contracts using this template"""
        for template in self:
            template.contract_count = self.env['construction.contract'].search_count([
                ('template_id', '=', template.id)
            ])

    # ============================================================
    # CONSTRAINTS
    # ============================================================

    @api.constrains('is_default')
    def _check_single_default(self):
        """Ensure only one default template exists"""
        if self.is_default:
            other_defaults = self.search([
                ('is_default', '=', True),
                ('id', '!=', self.id)
            ])
            if other_defaults:
                raise ValidationError(_(
                    "Only one default template is allowed. "
                    "Template '%s' is already set as default."
                ) % other_defaults[0].name)

    @api.constrains('grapesjs_components')
    def _check_valid_json(self):
        """Validate JSON structure"""
        for template in self:
            if template.grapesjs_components:
                try:
                    json.loads(template.grapesjs_components)
                except json.JSONDecodeError as e:
                    raise ValidationError(_(
                        "Invalid JSON in components: %s"
                    ) % str(e))

    # ============================================================
    # CRUD METHODS
    # ============================================================

    @api.model
    def create(self, vals):
        """Override create to initialize default variables"""
        template = super(ConstructionContractTemplate, self).create(vals)

        # Create default variables if none provided
        if not template.variable_ids:
            template._create_default_variables()

        return template

    def write(self, vals):
        """Track last modification date"""
        result = super(ConstructionContractTemplate, self).write(vals)

        # Update last_used_date when template is modified
        if any(k in vals for k in ['grapesjs_html', 'grapesjs_css', 'grapesjs_components']):
            self.last_used_date = fields.Datetime.now()

        return result

    def unlink(self):
        """Prevent deletion if template is in use or is default"""
        for template in self:
            if template.is_default:
                raise ValidationError(_("Cannot delete the default template."))

            if template.contract_count > 0:
                raise ValidationError(_(
                    "Cannot delete template '%s' because it is used by %d contract(s)."
                ) % (template.name, template.contract_count))

        return super(ConstructionContractTemplate, self).unlink()

    # ============================================================
    # BUSINESS METHODS
    # ============================================================

    def _create_default_variables(self):
        """
        Create default Jinja2 variables from configuration
        Called automatically when template is created
        """
        self.ensure_one()

        variable_obj = self.env['construction.contract.template.variable']

        for category, variables in TEMPLATE_VARIABLES.items():
            if isinstance(variables, dict):
                # Handle simple variables
                if variables.get('is_table'):
                    # Table-type variable
                    variable_obj.create({
                        'template_id': self.id,
                        'name': variables['description'],
                        'code': f'{{% for item in {category} %}}...{{% endfor %}}',
                        'category': category,
                        'variable_type': 'table',
                        'description': f"Loop through {category}",
                    })
                else:
                    # Regular variables
                    for var_name, description in variables.items():
                        variable_obj.create({
                            'template_id': self.id,
                            'name': description,
                            'code': f'{{{{ {category}.{var_name} }}}}',
                            'category': category,
                            'variable_type': 'text',
                            'description': f"{category}.{var_name}",
                        })

    def action_open_editor(self):
        """
        Open GrapesJS visual editor in new window

        Returns:
            dict: Action to open editor URL
        """
        self.ensure_one()

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        editor_url = f"{base_url}/contract/template/editor/{self.id}"

        return {
            'type': 'ir.actions.act_url',
            'url': editor_url,
            'target': 'new',
        }

    def action_preview_pdf(self):
        """
        Generate preview PDF with example data

        Returns:
            dict: Action to download preview PDF
        """
        self.ensure_one()

        # Create a temporary contract with example data for preview
        from config.template_variables import get_context_example

        # Use template renderer to generate HTML
        renderer = self.env['construction.contract.template.renderer']

        # Create mock contract object with example data
        context = get_context_example()

        # Render template
        try:
            from jinja2.sandbox import SandboxedEnvironment

            env = SandboxedEnvironment(autoescape=True)
            template = env.from_string(self.grapesjs_html or '')
            rendered_html = template.render(**context)

            full_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <style>{self.grapesjs_css or ''}</style>
            </head>
            <body>
                {rendered_html}
            </body>
            </html>
            """

            # Convert to PDF
            pdf_content = self.env['ir.actions.report']._run_wkhtmltopdf(
                [full_html],
                landscape=False,
            )

            # Return as download
            import base64
            pdf_base64 = base64.b64encode(pdf_content)

            attachment = self.env['ir.attachment'].create({
                'name': f'{self.name}_preview.pdf',
                'type': 'binary',
                'datas': pdf_base64,
                'res_model': self._name,
                'res_id': self.id,
                'mimetype': 'application/pdf',
            })

            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{attachment.id}?download=true',
                'target': 'new',
            }

        except Exception as e:
            raise ValidationError(_("Error generating preview: %s") % str(e))

    def copy(self, default=None):
        """
        Override copy to ensure proper field copying
        
        Args:
            default: dict of default values to override
            
        Returns:
            New template record
        """
        self.ensure_one()
        
        if default is None:
            default = {}
        
        # Ensure is_default is False for copies
        if 'is_default' not in default:
            default['is_default'] = False
            
        # Add (Copy) suffix if name not provided
        if 'name' not in default:
            default['name'] = _("%s (Copy)") % self.name
            
        # Call parent copy - this will automatically copy One2many fields (variable_ids)
        new_template = super(ConstructionContractTemplate, self).copy(default)
        
        _logger.info(
            "Template '%s' duplicated to '%s' (ID: %d)",
            self.name, new_template.name, new_template.id
        )
        
        return new_template

    def action_duplicate(self):
        """
        Duplicate this template with proper field copying
        
        Creates a complete copy including:
        - All template content (HTML, CSS, components)
        - All variables
        - All settings except is_default
        
        Returns:
            dict: Action to open duplicated template
        """
        self.ensure_one()

        new_template = self.copy()

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': new_template.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'form_view_initial_mode': 'edit',
            }
        }

    def action_set_as_default(self):
        """Set this template as default"""
        self.ensure_one()

        # Unset other defaults
        self.search([('is_default', '=', True)]).write({'is_default': False})

        # Set this as default
        self.is_default = True

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Template "%s" set as default.') % self.name,
                'type': 'success',
            }
        }

    def action_view_contracts(self):
        """View contracts using this template"""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': _('Contracts Using This Template'),
            'res_model': 'construction.contract',
            'view_mode': 'list,form',
            'domain': [('template_id', '=', self.id)],
        }


class ConstructionContractTemplateVariable(models.Model):
    """
    Template Variables

    Defines available Jinja2 variables for each template
    Used to populate GrapesJS editor with draggable variable blocks
    """

    _name = 'construction.contract.template.variable'
    _description = 'Contract Template Variable'
    _order = 'category, sequence, name'

    template_id = fields.Many2one(
        'construction.contract.template',
        string='Template',
        required=True,
        ondelete='cascade'
    )

    name = fields.Char(
        string='Variable Name',
        required=True,
        help="Human-readable name displayed in editor"
    )

    code = fields.Char(
        string='Jinja2 Code',
        required=True,
        help="Jinja2 variable syntax (e.g., {{ contract.name }})"
    )

    category = fields.Char(
        string='Category',
        help="Category for grouping (contract, chantier, subcontractor, etc.)"
    )

    variable_type = fields.Selection([
        ('text', 'Text'),
        ('number', 'Number'),
        ('date', 'Date'),
        ('table', 'Table/Loop'),
        ('html', 'HTML Block'),
    ], string='Type', default='text', required=True)

    description = fields.Text(
        string='Description',
        help="Explanation of what this variable represents"
    )

    sequence = fields.Integer(
        string='Sequence',
        default=10
    )

    example_value = fields.Char(
        string='Example Value',
        help="Example value for documentation/preview"
    )
