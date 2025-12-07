# -*- coding: utf-8 -*-
"""
Template Editor Controller for Construction Templates
Handles GrapesJS visual editor interface for the unified template system
Provides endpoints for loading and saving templates with BLG Groupe styling
"""

from odoo import http, _
from odoo.http import request
from odoo.exceptions import AccessError
import json
import logging

_logger = logging.getLogger(__name__)


# BLG Groupe pre-configured blocks for GrapesJS
BLG_BLOCKS = [
    # Header Block
    {
        'id': 'blg-header',
        'label': 'En-tête BLG',
        'category': 'BLG Groupe',
        'content': '''
            <div class="blg-header" style="background-color: #A0604F; color: white; padding: 20px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div class="blg-logo">
                        <img src="/web/image/res.company/1/logo" alt="BLG Groupe" style="max-height: 60px;"/>
                    </div>
                    <div class="blg-company-info" style="text-align: right;">
                        <strong>{{ company.name }}</strong><br/>
                        {{ company.street }}<br/>
                        {{ company.zip }} {{ company.city }}
                    </div>
                </div>
            </div>
        ''',
    },
    # Footer Block
    {
        'id': 'blg-footer',
        'label': 'Pied de page BLG',
        'category': 'BLG Groupe',
        'content': '''
            <div class="blg-footer" style="background-color: #F5E6D8; padding: 15px; font-size: 10px; margin-top: 30px;">
                <div style="text-align: center;">
                    <strong>{{ company.name }}</strong> - {{ company.street }}, {{ company.zip }} {{ company.city }}<br/>
                    SIRET: {{ company.siret }} | TVA: {{ company.vat }} | Tél: {{ company.phone }}
                </div>
            </div>
        ''',
    },
    # Lots Table Block
    {
        'id': 'blg-lots-table',
        'label': 'Tableau des lots',
        'category': 'BLG Groupe',
        'content': '''
            <div class="blg-lots-section" style="margin: 20px 0;">
                <h3 style="color: #A0604F; border-bottom: 2px solid #A0604F; padding-bottom: 5px;">
                    Lots concernés
                </h3>
                <table class="blg-table" style="width: 100%; border-collapse: collapse; margin-top: 10px;">
                    <thead>
                        <tr style="background-color: #A0604F; color: white;">
                            <th style="padding: 10px; text-align: left;">Lot</th>
                            <th style="padding: 10px; text-align: left;">Description</th>
                            <th style="padding: 10px; text-align: right;">Montant HT</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for lot in lots %}
                        <tr style="border-bottom: 1px solid #ddd;">
                            <td style="padding: 8px;">{{ lot.name }}</td>
                            <td style="padding: 8px;">{{ lot.description }}</td>
                            <td style="padding: 8px; text-align: right;">{{ lot.amount }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                    <tfoot>
                        <tr style="background-color: #F5E6D8; font-weight: bold;">
                            <td colspan="2" style="padding: 10px;">Total</td>
                            <td style="padding: 10px; text-align: right;">{{ contract.total_amount_ht }}</td>
                        </tr>
                    </tfoot>
                </table>
            </div>
        ''',
    },
    # Signature Zone - Company
    {
        'id': 'blg-signature-company',
        'label': 'Zone signature entreprise',
        'category': 'Zones de signature',
        'content': '''
            <div class="blg-signature-zone signature-company" 
                 style="border: 2px dashed #A0604F; padding: 15px; margin: 20px 0; min-height: 100px; width: 45%; display: inline-block;">
                <p style="color: #A0604F; font-weight: bold; margin-bottom: 10px;">
                    Pour l'entreprise {{ company.name }}
                </p>
                <div class="signature-placeholder" style="min-height: 60px; border-bottom: 1px solid #A0604F;">
                    <!-- Signature will be placed here -->
                </div>
                <p style="font-size: 10px; color: #666; margin-top: 5px;">
                    Date et lieu: _______________
                </p>
            </div>
        ''',
    },
    # Signature Zone - Subcontractor
    {
        'id': 'blg-signature-subcontractor',
        'label': 'Zone signature sous-traitant',
        'category': 'Zones de signature',
        'content': '''
            <div class="blg-signature-zone signature-subcontractor" 
                 style="border: 2px dashed #A0604F; padding: 15px; margin: 20px 0; min-height: 100px; width: 45%; display: inline-block; float: right;">
                <p style="color: #A0604F; font-weight: bold; margin-bottom: 10px;">
                    Pour le sous-traitant {{ subcontractor.name }}
                </p>
                <div class="signature-placeholder" style="min-height: 60px; border-bottom: 1px solid #A0604F;">
                    <!-- Signature will be placed here -->
                </div>
                <p style="font-size: 10px; color: #666; margin-top: 5px;">
                    Date et lieu: _______________
                </p>
            </div>
        ''',
    },
    # Contract Info Block
    {
        'id': 'blg-contract-info',
        'label': 'Informations contrat',
        'category': 'BLG Groupe',
        'content': '''
            <div class="blg-contract-info" style="margin: 20px 0; padding: 15px; background-color: #F5E6D8; border-left: 4px solid #A0604F;">
                <h2 style="color: #A0604F; margin-top: 0;">Contrat de sous-traitance</h2>
                <p><strong>Référence:</strong> {{ contract.name }}</p>
                <p><strong>Date:</strong> {{ contract.date }}</p>
                <p><strong>Chantier:</strong> {{ chantier.name }}</p>
                <p><strong>Sous-traitant:</strong> {{ subcontractor.name }}</p>
            </div>
        ''',
    },
    # Amounts Summary Block
    {
        'id': 'blg-amounts-summary',
        'label': 'Récapitulatif montants',
        'category': 'BLG Groupe',
        'content': '''
            <div class="blg-amounts" style="margin: 20px 0; padding: 15px; border: 1px solid #A0604F;">
                <h3 style="color: #A0604F; margin-top: 0;">Récapitulatif financier</h3>
                <table style="width: 100%;">
                    <tr>
                        <td>Montant HT:</td>
                        <td style="text-align: right; font-weight: bold;">{{ contract.total_amount_ht }}</td>
                    </tr>
                    <tr>
                        <td>TVA:</td>
                        <td style="text-align: right;">{{ contract.total_amount_tva }}</td>
                    </tr>
                    <tr style="border-top: 2px solid #A0604F;">
                        <td style="font-weight: bold; color: #A0604F;">Montant TTC:</td>
                        <td style="text-align: right; font-weight: bold; color: #A0604F; font-size: 1.2em;">
                            {{ contract.total_amount_ttc }}
                        </td>
                    </tr>
                    <tr>
                        <td>Retenue de garantie ({{ contract.retention_rate }}%):</td>
                        <td style="text-align: right;">{{ contract.retention_amount }}</td>
                    </tr>
                </table>
            </div>
        ''',
    },
    # Dates Block
    {
        'id': 'blg-dates',
        'label': 'Dates du contrat',
        'category': 'BLG Groupe',
        'content': '''
            <div class="blg-dates" style="margin: 15px 0;">
                <p><strong>Date de début des travaux:</strong> {{ contract.start_date }}</p>
                <p><strong>Date de fin prévue:</strong> {{ contract.end_date }}</p>
            </div>
        ''',
    },
]


# Jinja2 variables available in templates
TEMPLATE_VARIABLES = {
    'contract': {
        'name': 'Référence du contrat',
        'date': 'Date du contrat',
        'start_date': 'Date de début des travaux',
        'end_date': 'Date de fin des travaux',
        'total_amount_ht': 'Montant HT',
        'total_amount_tva': 'Montant TVA',
        'total_amount_ttc': 'Montant TTC',
        'retention_amount': 'Montant retenue de garantie',
        'retention_rate': 'Taux de retenue (%)',
    },
    'chantier': {
        'name': 'Nom du chantier',
        'reference': 'Référence du chantier',
        'client': 'Nom du client',
        'address': 'Adresse du chantier',
        'city': 'Ville',
        'postal_code': 'Code postal',
    },
    'subcontractor': {
        'name': 'Raison sociale',
        'siret': 'Numéro SIRET',
        'email': 'Email',
        'phone': 'Téléphone',
        'mobile': 'Mobile',
        'address': 'Adresse',
        'urssaf_code': 'Code activité URSSAF',
    },
    'company': {
        'name': 'Nom de la société',
        'street': 'Adresse',
        'zip': 'Code postal',
        'city': 'Ville',
        'siret': 'SIRET',
        'vat': 'N° TVA',
        'phone': 'Téléphone',
    },
    'lots': {
        '_description': 'Liste des lots (tableau)',
        '_is_table': True,
        'name': 'Nom du lot',
        'description': 'Description',
        'amount': 'Montant',
    },
}


def get_variable_blocks_for_grapesjs():
    """
    Generate GrapesJS blocks definition from template variables.
    
    Returns:
        list: List of block definitions for GrapesJS editor
    """
    blocks = []
    
    for category, variables in TEMPLATE_VARIABLES.items():
        # Skip internal keys
        if category.startswith('_'):
            continue
            
        # Handle table-type variables
        if isinstance(variables, dict) and variables.get('_is_table'):
            fields = {k: v for k, v in variables.items() if not k.startswith('_')}
            fields_html = ''.join([f'<th>{desc}</th>' for desc in fields.values()])
            cells_html = ''.join([f'<td>{{{{ item.{field} }}}}</td>' for field in fields.keys()])
            
            table_html = f'''
            <table class="blg-table" style="width: 100%; border-collapse: collapse;">
                <thead>
                    <tr style="background-color: #A0604F; color: white;">
                        {fields_html}
                    </tr>
                </thead>
                <tbody>
                    {{% for item in {category} %}}
                    <tr style="border-bottom: 1px solid #ddd;">
                        {cells_html}
                    </tr>
                    {{% endfor %}}
                </tbody>
            </table>
            '''
            
            blocks.append({
                'id': f'table_{category}',
                'label': f'Tableau: {variables.get("_description", category)}',
                'category': 'Variables - Tableaux',
                'content': table_html,
            })
        else:
            # Create individual variable blocks
            for var_name, description in variables.items():
                if var_name.startswith('_'):
                    continue
                blocks.append({
                    'id': f'{category}_{var_name}',
                    'label': f'{description}',
                    'category': f'Variables - {category.title()}',
                    'content': f'<span class="contract-var" data-variable="{category}.{var_name}">{{{{ {category}.{var_name} }}}}</span>',
                    'attributes': {
                        'class': 'contract-variable',
                        'data-type': 'variable',
                    }
                })
    
    return blocks


class TemplateEditorController(http.Controller):
    """
    Template Editor Controller for construction.document.template
    
    Endpoints:
    - /construction/template/editor/<int:template_id> - GrapesJS editor page
    - /construction/template/save - Save template data
    - /construction/template/load/<int:template_id> - Load template data
    - /construction/template/preview/<int:template_id> - Preview PDF
    """

    # ============================================================
    # EDITOR PAGE
    # ============================================================

    @http.route('/construction/template/editor/<int:template_id>',
                type='http', auth='user', website=True)
    def template_editor(self, template_id, **kwargs):
        """
        Display GrapesJS visual editor for template.
        
        Args:
            template_id (int): Template ID to edit
            
        Returns:
            Rendered template editor page
        """
        # Check access rights
        template = request.env['construction.document.template'].browse(template_id)
        
        if not template.exists():
            return request.not_found()
        
        # Check user has edit rights
        if not request.env.user.has_group('construction_templates.group_template_manager'):
            raise AccessError(_("Vous n'avez pas accès à l'éditeur de templates."))
        
        # Get variable blocks for GrapesJS
        variable_blocks = get_variable_blocks_for_grapesjs()
        
        # Combine with BLG pre-configured blocks
        all_blocks = BLG_BLOCKS + variable_blocks
        
        # Prepare context for template
        values = {
            'template': template,
            'variable_blocks': json.dumps(all_blocks),
            'page_name': _('Éditeur de Template'),
            'template_type_label': dict(template._fields['template_type'].selection).get(template.template_type, ''),
        }
        
        return request.render('construction_templates.template_editor_page', values)

    # ============================================================
    # SAVE ENDPOINT
    # ============================================================

    @http.route('/construction/template/save', type='json', auth='user')
    def save_template(self, template_id, html, css, components, styles, **kwargs):
        """
        Save template data from GrapesJS editor.
        
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
            template = request.env['construction.document.template'].browse(template_id)
            
            if not template.exists():
                return {'status': 'error', 'message': _('Template non trouvé.')}
            
            # Check permissions
            if not request.env.user.has_group('construction_templates.group_template_manager'):
                return {'status': 'error', 'message': _('Permission refusée.')}
            
            # Prepare GrapesJS data as JSON
            grapesjs_data = json.dumps({
                'components': components if isinstance(components, list) else json.loads(components) if components else [],
                'styles': styles if isinstance(styles, list) else json.loads(styles) if styles else [],
            })
            
            # Update template
            template.write({
                'html_content': html,
                'css_content': css,
                'grapesjs_data': grapesjs_data,
            })
            
            _logger.info(f"Template {template.name} saved by user {request.env.user.name}")
            
            return {
                'status': 'success',
                'message': _('Template enregistré avec succès.'),
                'template_id': template.id,
                'version': template.version,
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

    @http.route('/construction/template/load/<int:template_id>',
                type='json', auth='user')
    def load_template(self, template_id, **kwargs):
        """
        Load template data for GrapesJS editor.
        
        Args:
            template_id (int): Template ID
            
        Returns:
            dict: Template data
        """
        try:
            template = request.env['construction.document.template'].browse(template_id)
            
            if not template.exists():
                return {'status': 'error', 'message': _('Template non trouvé.')}
            
            # Parse GrapesJS data
            grapesjs_data = {}
            if template.grapesjs_data:
                try:
                    grapesjs_data = json.loads(template.grapesjs_data)
                except json.JSONDecodeError:
                    grapesjs_data = {}
            
            return {
                'status': 'success',
                'data': {
                    'html': template.html_content or '',
                    'css': template.css_content or '',
                    'components': grapesjs_data.get('components', []),
                    'styles': grapesjs_data.get('styles', []),
                }
            }
            
        except Exception as e:
            _logger.error(f"Error loading template: {e}")
            return {
                'status': 'error',
                'message': str(e),
            }

    # ============================================================
    # PREVIEW ENDPOINT
    # ============================================================

    @http.route('/construction/template/preview/<int:template_id>',
                type='http', auth='user')
    def preview_template(self, template_id, **kwargs):
        """
        Generate a PDF preview of the template with sample data.
        
        Args:
            template_id (int): Template ID
            
        Returns:
            PDF file response
        """
        template = request.env['construction.document.template'].browse(template_id)
        
        if not template.exists():
            return request.not_found()
        
        # For now, return a simple HTML preview
        # Full PDF generation will be implemented in a later task
        sample_context = get_sample_context()
        
        html = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Aperçu - {template.name}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                {template.css_content or ''}
            </style>
        </head>
        <body>
            <div class="preview-banner" style="background: #FFC107; padding: 10px; margin-bottom: 20px; text-align: center;">
                <strong>APERÇU</strong> - Ce document contient des données d'exemple
            </div>
            {template.html_content or '<p>Aucun contenu défini</p>'}
        </body>
        </html>
        '''
        
        return request.make_response(
            html,
            headers=[('Content-Type', 'text/html')]
        )


def get_sample_context():
    """
    Generate sample context data for template preview.
    
    Returns:
        dict: Sample data for template rendering
    """
    return {
        'contract': {
            'name': 'CONT/2025/00001',
            'date': '30/11/2025',
            'start_date': '15/12/2025',
            'end_date': '15/06/2026',
            'total_amount_ht': '75 000,00 €',
            'total_amount_tva': '15 000,00 €',
            'total_amount_ttc': '90 000,00 €',
            'retention_amount': '4 500,00 €',
            'retention_rate': '5,0',
        },
        'chantier': {
            'name': 'Résidence Les Oliviers',
            'reference': 'CHANT/2025/042',
            'client': 'SCI Les Jardins du Sud',
            'address': '25 Avenue des Platanes',
            'city': 'Bordeaux',
            'postal_code': '33000',
        },
        'subcontractor': {
            'name': 'Entreprise Martin & Fils SARL',
            'siret': '987 654 321 00015',
            'email': 'contact@martin-btp.fr',
            'phone': '05 56 78 90 12',
            'mobile': '06 78 90 12 34',
            'address': '78 Rue de l\'Industrie, 33100 Bordeaux',
            'urssaf_code': '43.34Z',
        },
        'company': {
            'name': 'BLG Groupe',
            'street': '10 Rue de la Construction',
            'zip': '33000',
            'city': 'Bordeaux',
            'siret': '123 456 789 00012',
            'vat': 'FR12345678901',
            'phone': '05 56 00 00 00',
        },
        'lots': [
            {'name': 'Gros Œuvre', 'description': 'Fondations et structure béton armé', 'amount': '35 000,00 €'},
            {'name': 'Charpente', 'description': 'Charpente traditionnelle en bois', 'amount': '20 000,00 €'},
            {'name': 'Couverture', 'description': 'Tuiles terre cuite', 'amount': '20 000,00 €'},
        ],
    }
