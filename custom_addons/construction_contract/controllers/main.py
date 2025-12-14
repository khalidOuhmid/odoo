# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.http import request
from odoo.tools.safe_eval import safe_eval
import jinja2
import base64
import logging
import json

_logger = logging.getLogger(__name__)

try:
    import weasyprint
except ImportError:
    weasyprint = None
    _logger.warning("WeasyPrint not available. PDF generation will fail.")

class ContractMainController(http.Controller):

    @http.route('/construction/contract/pdf/preview', type='json', auth='user')
    def preview_pdf(self, html_content, model, res_id):
        """
        Generate a PDF preview from HTML content using Jinja2 and WeasyPrint.
        """
        if not weasyprint:
            return {'error': "WeasyPrint is not installed on the server."}

        try:
            # 1. Fetch Record
            record = request.env[model].browse(res_id)
            if not record.exists():
                return {'error': "Record not found"}

            # 2. Jinja2 Rendering
            # Use strict/safe environment
            env = jinja2.Environment(autoescape=True)
            template = env.from_string(html_content)
            
            # Prepare signature
            company_sig = ""
            if request.env.company.external_report_layout_id: 
                 # Placeholder logic, ideally use a specific field
                 pass 
            
            # Prepare context variables
            # We pass 'o' (object), 'user', 'company'
            render_context = {
                'o': record,
                'object': record,
                'user': request.env.user,
                'company': request.env.company,
                'company_signature': "<!-- Signature Injection Here -->", # TODO link to real signature field
            }
            
            rendered_html = template.render(render_context)

            # 3. WeasyPrint Generation
            # Use base_url for assets
            base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
            
            doc = weasyprint.HTML(string=rendered_html, base_url=base_url)
            pdf_bytes = doc.write_pdf()

            return {
                'pdf_base64': base64.b64encode(pdf_bytes).decode('utf-8')
            }

        except Exception as e:
            _logger.exception("Error generating PDF preview")
            return {'error': str(e)}

    @http.route('/construction/contract/po/save', type='json', auth='user')
    def save_po_contract(self, po_id, html_content):
        """
        Save the edited contract HTML back to the Purchase Order.
        """
        try:
            po = request.env['purchase.order'].browse(po_id)
            if not po.exists():
                return {'error': "Purchase Order not found"}
            
            po.write({'contract_template_html': html_content})
            return {'success': True}
        except Exception as e:
            _logger.exception("Error saving PO contract")
            return {'error': str(e)}
