# -*- coding: utf-8 -*-
"""
PDF Generator Service - Pure Python Implementation
Uses WeasyPrint instead of wkhtmltopdf for better maintainability
"""

from odoo import models, api, _
from odoo.exceptions import UserError
import base64
import hashlib
import logging
import io

_logger = logging.getLogger(__name__)

# Try to import WeasyPrint
try:
    from weasyprint import HTML, CSS
    from weasyprint.text.fonts import FontConfiguration
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False
    _logger.warning("WeasyPrint not available. Install with: pip install WeasyPrint")

# Try to import PyPDF2 for page counting and optimization
try:
    from PyPDF2 import PdfReader, PdfWriter
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False
    _logger.warning("PyPDF2 not available. Install with: pip install PyPDF2")


class ContractPDFGenerator(models.AbstractModel):
    """
    PDF Generation Service using WeasyPrint

    Responsible for:
    - Converting HTML to PDF using WeasyPrint (pure Python)
    - Optimizing PDF file size
    - Calculating PDF hash for integrity
    - Counting pages
    """

    _name = 'construction.contract.pdf.generator'
    _description = 'Contract PDF Generator Service'

    # ============================================================
    # MAIN GENERATION METHOD
    # ============================================================

    @api.model
    def generate_pdf(self, contract):
        """
        Generate PDF for a contract using WeasyPrint

        Args:
            contract: construction.contract record

        Returns:
            bool: True if successful

        Raises:
            UserError: If generation fails
        """
        if not WEASYPRINT_AVAILABLE:
            raise UserError(_(
                "WeasyPrint is not installed.\n\n"
                "Please install it with: pip install WeasyPrint\n\n"
                "WeasyPrint is a modern, pure-Python PDF generation library "
                "that doesn't require external binaries."
            ))

        try:
            # Step 1: Get rendered HTML from template renderer
            _logger.info(f"Starting PDF generation for contract {contract.name}")
            html_content = contract._get_rendered_html_for_pdf()
            
            if not html_content or len(html_content.strip()) < 50:
                raise UserError(_(
                    "Generated HTML is empty or too short. "
                    "Please check your template configuration."
                ))

            # Step 2: Convert HTML to PDF using WeasyPrint
            pdf_content = self._convert_html_to_pdf(html_content)

            # Step 3: Optimize PDF (compress) if PyPDF2 available
            if PYPDF2_AVAILABLE:
                pdf_optimized = self._optimize_pdf(pdf_content)
            else:
                _logger.warning("PyPDF2 not available, skipping optimization")
                pdf_optimized = pdf_content

            # Step 4: Calculate hash for integrity check
            pdf_hash = self._calculate_hash(pdf_optimized)

            # Step 5: Count pages
            page_count = self._count_pages(pdf_optimized)

            # Step 6: Store PDF in contract
            contract.write({
                'pdf_document': base64.b64encode(pdf_optimized),
                'pdf_hash_before_signature': pdf_hash,
                'pdf_page_count': page_count,
            })

            _logger.info(
                f"PDF generated successfully for contract {contract.name}: "
                f"{page_count} pages, {len(pdf_optimized)/1024:.1f} KB, "
                f"hash: {pdf_hash[:16]}..."
            )

            return True

        except UserError:
            raise
        except Exception as e:
            _logger.error(
                f"PDF generation failed for contract {contract.name}: {e}",
                exc_info=True
            )
            raise UserError(_(
                "Failed to generate PDF: %s\n\n"
                "Please check the logs for more details."
            ) % str(e))

    # ============================================================
    # PRIVATE HELPER METHODS
    # ============================================================

    def _convert_html_to_pdf(self, html_content):
        """
        Convert HTML to PDF using WeasyPrint

        Args:
            html_content (str): HTML string to convert

        Returns:
            bytes: PDF content

        Raises:
            Exception: If conversion fails
        """
        try:
            # Configure fonts for better rendering
            font_config = FontConfiguration()
            
            # Create HTML object from string
            html_obj = HTML(string=html_content, base_url=None)
            
            # Optional: Add custom CSS for PDF-specific styling
            pdf_css = CSS(string='''
                @page {
                    size: A4;
                    margin: 2cm;
                }
                
                body {
                    font-family: 'DejaVu Sans', Arial, sans-serif;
                    font-size: 11pt;
                    line-height: 1.6;
                    color: #333;
                }
                
                table {
                    page-break-inside: avoid;
                }
                
                h1, h2, h3 {
                    page-break-after: avoid;
                }
                
                /* Prevent widows and orphans */
                p {
                    orphans: 3;
                    widows: 3;
                }
            ''', font_config=font_config)
            
            # Generate PDF
            pdf_bytes = html_obj.write_pdf(
                stylesheets=[pdf_css],
                font_config=font_config
            )
            
            _logger.debug(f"WeasyPrint generated PDF: {len(pdf_bytes)} bytes")
            
            return pdf_bytes

        except Exception as e:
            _logger.error(f"WeasyPrint conversion failed: {e}", exc_info=True)
            raise Exception(f"HTML to PDF conversion failed: {str(e)}")

    def _optimize_pdf(self, pdf_content):
        """
        Optimize PDF file size by compressing content streams

        Args:
            pdf_content (bytes): Original PDF content

        Returns:
            bytes: Optimized PDF content
        """
        if not PYPDF2_AVAILABLE:
            return pdf_content

        try:
            # Read PDF
            reader = PdfReader(io.BytesIO(pdf_content))
            writer = PdfWriter()

            # Compress each page
            for page in reader.pages:
                page.compress_content_streams()
                writer.add_page(page)

            # Write to bytes
            output = io.BytesIO()
            writer.write(output)
            optimized_content = output.getvalue()

            # Log compression ratio
            original_size = len(pdf_content)
            optimized_size = len(optimized_content)
            compression_ratio = (1 - optimized_size / original_size) * 100

            _logger.info(
                f"PDF optimized: {original_size / 1024:.1f} KB → "
                f"{optimized_size / 1024:.1f} KB "
                f"(saved {compression_ratio:.1f}%)"
            )

            return optimized_content

        except Exception as e:
            _logger.warning(f"PDF optimization failed: {e}, using original")
            return pdf_content

    def _calculate_hash(self, pdf_content):
        """
        Calculate SHA-256 hash of PDF for integrity verification

        Args:
            pdf_content (bytes): PDF content

        Returns:
            str: Hexadecimal hash string
        """
        return hashlib.sha256(pdf_content).hexdigest()

    def _count_pages(self, pdf_content):
        """
        Count number of pages in PDF

        Args:
            pdf_content (bytes): PDF content

        Returns:
            int: Number of pages
        """
        if not PYPDF2_AVAILABLE:
            _logger.warning("PyPDF2 not available, cannot count pages")
            return 1  # Assume 1 page

        try:
            reader = PdfReader(io.BytesIO(pdf_content))
            page_count = len(reader.pages)
            _logger.debug(f"PDF contains {page_count} pages")
            return page_count

        except Exception as e:
            _logger.error(f"Error counting PDF pages: {e}")
            return 1  # Fallback to 1 page

    # ============================================================
    # UTILITY METHODS
    # ============================================================

    @api.model
    def regenerate_pdf(self, contract):
        """
        Regenerate PDF for an existing contract
        Used when template is updated

        Args:
            contract: construction.contract record

        Returns:
            bool: True if successful
        """
        _logger.info(f"Regenerating PDF for contract {contract.name}")
        return self.generate_pdf(contract)

    @api.model
    def batch_generate_pdfs(self, contracts):
        """
        Generate PDFs for multiple contracts in batch

        Args:
            contracts: recordset of construction.contract

        Returns:
            dict: Success/failure statistics
        """
        success_count = 0
        error_count = 0
        errors = []

        for contract in contracts:
            try:
                self.generate_pdf(contract)
                success_count += 1
            except Exception as e:
                error_count += 1
                errors.append({
                    'contract_id': contract.id,
                    'contract_name': contract.name,
                    'error': str(e),
                })
                _logger.error(f"Batch PDF generation failed for {contract.name}: {e}")

        return {
            'total': len(contracts),
            'success': success_count,
            'errors': error_count,
            'error_details': errors,
        }

    @api.model
    def test_weasyprint_installation(self):
        """
        Test if WeasyPrint is properly installed and working

        Returns:
            dict: Test results
        """
        results = {
            'weasyprint_available': WEASYPRINT_AVAILABLE,
            'pypdf2_available': PYPDF2_AVAILABLE,
            'test_pdf_generation': False,
            'error': None,
        }

        if not WEASYPRINT_AVAILABLE:
            results['error'] = "WeasyPrint not installed. Run: pip install WeasyPrint"
            return results

        try:
            # Try to generate a simple test PDF
            test_html = """
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    body { font-family: sans-serif; padding: 20px; }
                    h1 { color: #2c3e50; }
                </style>
            </head>
            <body>
                <h1>Test PDF Generation</h1>
                <p>This is a test PDF generated by WeasyPrint.</p>
                <p>If you can read this, WeasyPrint is working correctly!</p>
            </body>
            </html>
            """
            
            pdf_bytes = self._convert_html_to_pdf(test_html)
            
            if pdf_bytes and len(pdf_bytes) > 100:
                results['test_pdf_generation'] = True
                results['test_pdf_size'] = len(pdf_bytes)
                _logger.info("WeasyPrint test successful")
            else:
                results['error'] = "Generated PDF is too small or empty"

        except Exception as e:
            results['error'] = str(e)
            _logger.error(f"WeasyPrint test failed: {e}")

        return results
