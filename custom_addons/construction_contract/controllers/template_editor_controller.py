# -*- coding: utf-8 -*-
"""
Template Editor Controller
Handles GrapesJS visual editor interface
Provides endpoints for loading and saving templates
"""

from odoo import http, _
from odoo.http import request
from odoo.exceptions import AccessError
import json
import logging

_logger = logging.getLogger(__name__)

from ..config.template_variables import get_variable_blocks_for_grapesjs


class TemplateEditorController(http.Controller):
    """
    Template Editor Controller

    Endpoints:
    - /contract/template/editor/<int:template_id> - GrapesJS editor page
    - /contract/template/save - Save template data
    - /contract/template/load/<int:template_id> - Load template data
    """

    # ============================================================
    # EDITOR PAGE
    # ============================================================

    @http.route('/contract/template/editor/<int:template_id>',
                type='http', auth='user', website=True)
    def template_editor(self, template_id, **kwargs):
        """
        Display GrapesJS visual editor for template

        Args:
            template_id (int): Template ID to edit

        Returns:
            Rendered template editor page
        """
        # Check access rights
        template = request.env['construction.contract.template'].browse(template_id)

        if not template.exists():
            return request.not_found()

        # Check user has edit rights
        if not request.env.user.has_group('base.group_user'):
            raise AccessError(_("You don't have access to the template editor."))

        # Get variable blocks for GrapesJS
        variable_blocks = get_variable_blocks_for_grapesjs()

        # Prepare context for template
        values = {
            'template': template,
            'variable_blocks': json.dumps(variable_blocks),
            'page_name': _('Template Editor'),
        }

        return request.render('construction_contract.template_editor_page', values)

    # ============================================================
    # SAVE ENDPOINT
    # ============================================================

    @http.route('/contract/template/save', type='json', auth='user')
    def save_template(self, template_id, html, css, components, styles, **kwargs):
        """
        Save template data from GrapesJS editor

        Args:
            template_id (int): Template ID
            html (str): Generated HTML
            css (str): Generated CSS
            components (str): GrapesJS components JSON
            styles (str): GrapesJS styles JSON

        Returns:
            dict: Save result
        """
        try:
            template = request.env['construction.contract.template'].browse(template_id)

            if not template.exists():
                return {'status': 'error', 'message': _('Template not found.')}

            # Update template
            template.write({
                'grapesjs_html': html,
                'grapesjs_css': css,
                'grapesjs_components': components,
                'grapesjs_styles': styles,
            })

            _logger.info(f"Template {template.name} saved successfully by user {request.env.user.name}")

            return {
                'status': 'success',
                'message': _('Template saved successfully.'),
                'template_id': template.id,
            }

        except Exception as e:
            _logger.error(f"Error saving template: {e}")
            return {
                'status': 'error',
                'message': str(e),
            }

    # ============================================================
    # LOAD ENDPOINT
    # ============================================================

    @http.route('/contract/template/load/<int:template_id>',
                type='json', auth='user')
    def load_template(self, template_id, **kwargs):
        """
        Load template data for GrapesJS editor

        Args:
            template_id (int): Template ID

        Returns:
            dict: Template data
        """
        try:
            template = request.env['construction.contract.template'].browse(template_id)

            if not template.exists():
                return {'status': 'error', 'message': _('Template not found.')}

            # Parse JSON safely
            components = json.loads(template.grapesjs_components) if template.grapesjs_components else []
            styles = json.loads(template.grapesjs_styles) if template.grapesjs_styles else []

            return {
                'status': 'success',
                'data': {
                    'html': template.grapesjs_html or '',
                    'css': template.grapesjs_css or '',
                    'components': components,
                    'styles': styles,
                }
            }

        except Exception as e:
            _logger.error(f"Error loading template: {e}")
            return {
                'status': 'error',
                'message': str(e),
            }
