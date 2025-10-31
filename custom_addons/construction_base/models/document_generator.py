# -*- coding: utf-8 -*-
"""
Document Generator

Responsible for generating PDF and HTML documents for contracts.
Separates document generation logic from contract creation.
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging
import base64
import tempfile
import os
import subprocess
from datetime import datetime

_logger = logging.getLogger(__name__)


class DocumentGenerator(models.AbstractModel):
    """
    Generator for contract documents.
    
    This service handles:
    - PDF generation from HTML templates
    - Document consolidation
    - Template rendering
    - File management
    """
    _name = 'construction.document.generator'
    _description = 'Document Generator'

    def generate_contract_pdf(self, contract):
        """
        Generate complete PDF for contract.
        
        Args:
            contract: construction.subcontractor.contract record
            
        Returns:
            bytes: PDF content
        """
        try:
            # Generate main contract HTML
            contract_html = self._render_contract_template(contract)
            
            # Generate annexes
            annex_pdfs = self._generate_annexes(contract)
            
            # Generate signatures page
            signatures_html = self._render_signatures_template(contract)
            signatures_pdf = self._html_to_pdf(signatures_html)
            
            # Merge all PDFs
            all_pdfs = [self._html_to_pdf(contract_html)] + annex_pdfs + [signatures_pdf]
            final_pdf = self._merge_pdfs(all_pdfs)
            
            return base64.b64encode(final_pdf)
            
        except Exception as e:
            _logger.error(f"Error generating contract PDF: {e}")
            raise ValidationError(_("Error generating contract PDF: %s") % str(e))

    def generate_preview_html(self, contract_data):
        """
        Generate preview HTML for contract.
        
        Args:
            contract_data: Contract configuration data
            
        Returns:
            str: HTML content
        """
        try:
            # Create temporary contract object for preview
            temp_contract = self._create_temp_contract(contract_data)
            
            # Render template
            html_content = self._render_contract_template(temp_contract)
            
            # Wrap in complete HTML document
            return self._wrap_in_html_document(html_content)
            
        except Exception as e:
            _logger.error(f"Error generating preview HTML: {e}")
            raise ValidationError(_("Error generating preview HTML: %s") % str(e))

    def _render_contract_template(self, contract):
        """Render the main contract template."""
        blg_images = self._get_blg_images()
        
        return self.env['ir.qweb']._render('construction_base.contrat_sous_traitance_template', {
            'docs': [contract],
            'env': self.env,
            'context': self.env.context,
            'company': contract.company_id,
            'fields': self.env['ir.fields.converter'],
            'blg_logo': blg_images['logo'],
            'blg_signature': blg_images['signature'],
        })

    def _render_signatures_template(self, contract):
        """Render the signatures template."""
        blg_images = self._get_blg_images()
        
        return f"""
        <div style="page-break-before: always;">
            <h2>Contract Signatures</h2>
            <div style="display: flex; justify-content: space-around; margin: 40px 0;">
                <div style="text-align: center;">
                    <h3>General Contractor</h3>
                    <p>{contract.company_id.name or 'B.L.G GROUPE'}</p>
                    <div style="height: 120px; border: 2px solid #20B2AA; margin: 20px 0;">
                        <img src="{blg_images['signature']}" alt="BLG Signature" style="max-height: 100px;"/>
                    </div>
                </div>
                <div style="text-align: center;">
                    <h3>Subcontractor</h3>
                    <p>{contract.subcontractor_id.name}</p>
                    <div style="height: 120px; border: 2px solid #20B2AA; margin: 20px 0;">
                        {'<img src="data:image/png;base64,' + contract.signature_image.decode("utf-8") + '" alt="Subcontractor Signature" style="max-height: 100px;"/>' if contract.signature_image else '<p>Signature to be added</p>'}
                    </div>
                </div>
            </div>
        </div>
        """

    def _generate_annexes(self, contract):
        """Generate annex documents."""
        annex_pdfs = []
        
        # Generate purchase orders
        if len(contract.lot_ids) > 1:
            purchase_orders_pdf = self._generate_consolidated_purchase_orders(contract)
            if purchase_orders_pdf:
                annex_pdfs.append(purchase_orders_pdf)
        else:
            purchase_orders_pdf = self._generate_purchase_orders_for_lot(contract.lot_ids[0], contract)
            if purchase_orders_pdf:
                annex_pdfs.append(purchase_orders_pdf)
        
        # Generate planning documents
        for lot in contract.lot_ids:
            planning_pdf = self._generate_planning_document(lot, contract)
            if planning_pdf:
                annex_pdfs.append(planning_pdf)
        
        return annex_pdfs

    def _generate_consolidated_purchase_orders(self, contract):
        """Generate consolidated purchase orders for multi-lot contracts."""
        try:
            all_orders = []
            for lot in contract.lot_ids:
                lot_orders = self._get_lot_purchase_orders(lot, contract)
                all_orders.extend(lot_orders)
            
            if not all_orders:
                return None
            
            html_content = self._render_purchase_orders_template(contract, all_orders, consolidated=True)
            return self._html_to_pdf(html_content)
            
        except Exception as e:
            _logger.error(f"Error generating consolidated purchase orders: {e}")
            return None

    def _generate_purchase_orders_for_lot(self, lot, contract):
        """Generate purchase orders for a specific lot."""
        try:
            orders = self._get_lot_purchase_orders(lot, contract)
            if not orders:
                return None
            
            html_content = self._render_purchase_orders_template(contract, orders, lot=lot)
            return self._html_to_pdf(html_content)
            
        except Exception as e:
            _logger.error(f"Error generating purchase orders for lot {lot.name}: {e}")
            return None

    def _generate_planning_document(self, lot, contract):
        """Generate planning document for a lot."""
        try:
            planning_tasks = self.env['construction.planning.task'].search([
                ('lot_id', '=', lot.id),
                ('chantier_id', '=', contract.chantier_id.id)
            ], order='date_start asc')
            
            if not planning_tasks:
                return None
            
            html_content = self._render_planning_template(lot, contract, planning_tasks)
            return self._html_to_pdf(html_content)
            
        except Exception as e:
            _logger.error(f"Error generating planning document for lot {lot.name}: {e}")
            return None

    def _get_lot_purchase_orders(self, lot, contract):
        """Get purchase orders for a lot."""
        orders_via_lot_ids = self.env['purchase.order'].search([
            ('lot_ids', 'in', [lot.id]),
            ('state', 'in', ['draft', 'sent', 'to_approve', 'purchase', 'done'])
        ])
        
        order_lines_with_lot = self.env['purchase.order.line'].search([
            ('lot_id', '=', lot.id),
            ('order_id.state', 'in', ['draft', 'sent', 'to_approve', 'purchase', 'done'])
        ])
        orders_via_lines = order_lines_with_lot.mapped('order_id')
        
        all_lot_orders = orders_via_lot_ids | orders_via_lines
        
        if contract.subcontractor_id:
            return all_lot_orders.filtered(lambda po: po.partner_id == contract.subcontractor_id)
        
        return all_lot_orders

    def _render_purchase_orders_template(self, contract, orders, lot=None, consolidated=False):
        """Render purchase orders template."""
        # This would contain the HTML template for purchase orders
        # Implementation depends on the specific template requirements
        return f"<h1>Purchase Orders</h1><p>Orders for {contract.subcontractor_id.name}</p>"

    def _render_planning_template(self, lot, contract, planning_tasks):
        """Render planning template."""
        # This would contain the HTML template for planning
        # Implementation depends on the specific template requirements
        return f"<h1>Planning for {lot.name}</h1><p>Tasks: {len(planning_tasks)}</p>"

    def _create_temp_contract(self, contract_data):
        """Create temporary contract object for preview."""
        class TempContract:
            def __init__(self, env, data):
                self.env = env
                self.id = 0
                self._name = 'construction.subcontractor.contract'
                self.name = data.get('name', 'Preview Contract')
                self.chantier_id = self.env['construction.chantier'].browse(data.get('chantier_id'))
                self.subcontractor_id = self.env['res.partner'].browse(data.get('subcontractor_id'))
                self.company_id = env.company
                self.lot_ids = self.env['construction.lot'].browse(data.get('lot_ids', []))
                self.total_amount = data.get('total_amount', 0.0)
                self.currency_id = env.company.currency_id
                self.start_date = data.get('start_date')
                self.create_date = fields.Datetime.now()
                self.signature_image = None
                self.signature_hash = None
                self.signature_timestamp = None
                self.signature_ip = None
                self.user_agent = None
                self.signature_certificate = None
                self.contract_hash_before_signature = None
                self.contract_hash_after_signature = None
                self.urssaf_code = data.get('urssaf_code', '43.34Z')

            def with_context(self, *args, **kwargs):
                return self

            def __bool__(self):
                return True

        return TempContract(self.env, contract_data)

    def _wrap_in_html_document(self, html_content):
        """Wrap HTML content in complete document."""
        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Contract Preview</title>
    <style>
        body {{
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 12px;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            color: #2c3e50;
            background-color: #ffffff;
        }}
        .page {{
            min-height: 800px;
            max-width: 800px;
            margin: 0 auto;
        }}
    </style>
</head>
<body>
    <div class="page">
        {html_content}
    </div>
</body>
</html>"""

    def _get_blg_images(self):
        """Get BLG images in base64 format."""
        try:
            from odoo.tools import file_path
            import base64
            
            logo_path = file_path('construction_base/static/src/img/blg_logo.png')
            signature_path = file_path('construction_base/static/src/img/blg_signature.png')
            
            with open(logo_path, 'rb') as f:
                logo_b64 = base64.b64encode(f.read()).decode('utf-8')
            
            with open(signature_path, 'rb') as f:
                signature_b64 = base64.b64encode(f.read()).decode('utf-8')
            
            return {
                'logo': f"data:image/png;base64,{logo_b64}",
                'signature': f"data:image/png;base64,{signature_b64}"
            }
        except Exception as e:
            _logger.error(f"Error loading BLG images: {e}")
            return {'logo': '', 'signature': ''}

    def _html_to_pdf(self, html_content):
        """Convert HTML to PDF using wkhtmltopdf."""
        try:
            command = [
                'wkhtmltopdf',
                '--page-size', 'A4',
                '--orientation', 'Portrait',
                '--margin-top', '25mm',
                '--margin-right', '8mm',
                '--margin-bottom', '15mm',
                '--margin-left', '8mm',
                '--encoding', 'UTF-8',
                '--disable-external-links',
                '--disable-internal-links',
                '--disable-javascript',
                '--disable-plugins',
                '--enable-local-file-access',
                '--print-media-type',
                '--no-pdf-compression',
                '--image-quality', '100',
                '--disable-smart-shrinking',
                '--minimum-font-size', '8',
                '--zoom', '1.0',
                '--dpi', '96',
                '--viewport-size', '1024x768',
                '--quiet',
                '-', '-'
            ]
            
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            pdf_content, error = process.communicate(input=html_content.encode('utf-8'))
            
            if process.returncode == 0:
                return pdf_content
            else:
                raise Exception(f"wkhtmltopdf failed: {error.decode()}")
                
        except Exception as e:
            _logger.error(f"Error converting HTML to PDF: {e}")
            raise ValidationError(_("Error converting HTML to PDF: %s") % str(e))

    def _merge_pdfs(self, pdf_list):
        """Merge multiple PDFs into one."""
        try:
            temp_files = []
            for i, pdf_content in enumerate(pdf_list):
                with tempfile.NamedTemporaryFile(mode='w+b', suffix='.pdf', delete=False) as temp_file:
                    temp_file.write(pdf_content)
                    temp_files.append(temp_file.name)
            
            with tempfile.NamedTemporaryFile(mode='w+b', suffix='.pdf', delete=False) as final_file:
                final_path = final_file.name
            
            command = ['pdfunite'] + temp_files + [final_path]
            
            try:
                subprocess.run(command, check=True)
                
                with open(final_path, 'rb') as f:
                    final_pdf_content = f.read()
                
                return final_pdf_content
            finally:
                for temp_file in temp_files + [final_path]:
                    try:
                        os.unlink(temp_file)
                    except Exception as e:
                        _logger.warning(f"Could not clean up temporary file: {e}")
                
        except Exception as e:
            _logger.error(f"Error merging PDFs: {e}")
            raise ValidationError(_("Error merging PDFs: %s") % str(e))
