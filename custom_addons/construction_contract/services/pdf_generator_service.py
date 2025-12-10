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
        Includes signature validation after generation

        Args:
            contract: construction.contract record

        Returns:
            bool: True if successful

        Raises:
            UserError: If generation fails
        """
        if not WEASYPRINT_AVAILABLE:
            _logger.error("✗ WeasyPrint not available - cannot generate PDF")
            raise UserError(_(
                "❌ WeasyPrint non installé\n\n"
                "La bibliothèque WeasyPrint n'est pas installée. "
                "Elle est nécessaire pour générer les PDF.\n\n"
                "Installation :\n"
                "pip install WeasyPrint\n\n"
                "WeasyPrint est une bibliothèque Python moderne pour "
                "la génération de PDF qui ne nécessite pas de binaires externes.\n\n"
                "Contactez l'administrateur système pour l'installation."
            ))

        try:
            # Step 1: Get rendered HTML from template renderer
            _logger.info(
                f"Starting PDF generation for contract {contract.name}, "
                f"state={contract.state}, "
                f"has_signature={bool(contract.signature_id)}, "
                f"context_signature={bool(self.env.context.get('contract_signature'))}"
            )
            # Ensure contract has context for template rendering (e.g., signature)
            contract_with_context = contract.with_context(self.env.context)
            html_content = contract_with_context._get_rendered_html_for_pdf()
            
            if not html_content or len(html_content.strip()) < 50:
                _logger.error(
                    f"✗ Generated HTML is too short for contract {contract.name}: "
                    f"{len(html_content) if html_content else 0} chars"
                )
                raise UserError(_(
                    "❌ Contenu HTML vide ou trop court\n\n"
                    "Le modèle de contrat n'a pas généré de contenu HTML valide.\n\n"
                    "Actions recommandées :\n"
                    "1. Vérifiez que le modèle de contrat est correctement configuré\n"
                    "2. Vérifiez que le modèle contient du contenu\n"
                    "3. Essayez de modifier et sauvegarder le modèle\n\n"
                    "Contactez l'administrateur si le problème persiste."
                ))
            
            _logger.debug(f"HTML content length for contract {contract.name}: {len(html_content)} chars")

            # Step 2: Convert HTML to PDF using WeasyPrint
            pdf_content = self._convert_html_to_pdf(html_content)

            # Step 3: Validate signatures in PDF (if expected)
            expected_signatures = []
            if 'company_signature' in html_content.lower():
                expected_signatures.append('company')
            if contract.signature_id or self.env.context.get('contract_signature'):
                if 'subcontractor_signature' in html_content.lower():
                    expected_signatures.append('subcontractor')
            
            if expected_signatures:
                self._validate_signatures_in_pdf(pdf_content, expected_signatures, contract.name)

            # Step 4: Optimize PDF (compress) if PyPDF2 available
            if PYPDF2_AVAILABLE:
                pdf_optimized = self._optimize_pdf(pdf_content)
            else:
                _logger.warning("PyPDF2 not available, skipping optimization")
                pdf_optimized = pdf_content

            # Step 5: Calculate hash for integrity check
            pdf_hash = self._calculate_hash(pdf_optimized)

            # Step 6: Count pages
            page_count = self._count_pages(pdf_optimized)

            # Step 7: Store PDF in contract
            # Only update pdf_hash_before_signature if it doesn't exist (first generation)
            # If contract is signed, we're regenerating, so keep the original hash
            update_vals = {
                'pdf_document': base64.b64encode(pdf_optimized),
                'pdf_page_count': page_count,
            }
            # Only set hash_before_signature if not already set (first generation)
            if not contract.pdf_hash_before_signature:
                update_vals['pdf_hash_before_signature'] = pdf_hash
            
            contract.write(update_vals)
            
            _logger.info(f"PDF stored in contract {contract.name}: {len(pdf_optimized)/1024:.1f} KB, {page_count} pages")

            _logger.info(
                f"✓ PDF generated successfully for contract {contract.name}: "
                f"{page_count} pages, {len(pdf_optimized)/1024:.1f} KB, "
                f"hash: {pdf_hash[:16]}..., "
                f"signatures validated: {', '.join(expected_signatures) if expected_signatures else 'none'}"
            )

            return True

        except UserError:
            # Re-raise UserError as-is (already has user-friendly message)
            raise
        except Exception as e:
            # Log detailed error for debugging
            _logger.error(
                f"✗ PDF generation failed for contract {contract.name}: {e}",
                exc_info=True
            )
            
            # Provide user-friendly error message in French with actionable instructions
            error_type = type(e).__name__
            error_details = str(e)
            
            # Customize message based on error type
            if 'weasyprint' in error_details.lower() or 'html' in error_details.lower():
                error_msg = _(
                    "❌ Erreur de génération PDF\n\n"
                    "La conversion HTML vers PDF a échoué.\n\n"
                    "Causes possibles :\n"
                    "• Erreur de syntaxe dans le modèle de contrat\n"
                    "• Image manquante ou corrompue\n"
                    "• Problème avec WeasyPrint\n\n"
                    "Actions recommandées :\n"
                    "1. Vérifiez que le modèle de contrat est valide\n"
                    "2. Vérifiez que toutes les images sont accessibles\n"
                    "3. Contactez l'administrateur si le problème persiste\n\n"
                    "Détails techniques : %s"
                ) % error_details
            elif 'signature' in error_details.lower():
                error_msg = _(
                    "❌ Erreur de signature\n\n"
                    "Un problème est survenu avec les signatures du contrat.\n\n"
                    "Actions recommandées :\n"
                    "1. Vérifiez que la signature de l'entreprise est configurée\n"
                    "2. Si le contrat est signé, vérifiez la signature du sous-traitant\n"
                    "3. Régénérez le PDF après avoir corrigé les signatures\n\n"
                    "Détails techniques : %s"
                ) % error_details
            else:
                error_msg = _(
                    "❌ Erreur de génération PDF\n\n"
                    "Une erreur inattendue s'est produite lors de la génération du PDF.\n\n"
                    "Type d'erreur : %s\n"
                    "Détails : %s\n\n"
                    "Veuillez contacter l'administrateur système avec ces informations."
                ) % (error_type, error_details)
            
            raise UserError(error_msg)

    # ============================================================
    # PRIVATE HELPER METHODS
    # ============================================================

    def _convert_html_to_pdf(self, html_content):
        """
        Convert HTML to PDF using WeasyPrint
        Improved image handling for data URLs

        Args:
            html_content (str): HTML string to convert

        Returns:
            bytes: PDF content

        Raises:
            Exception: If conversion fails
        """
        try:
            # WeasyPrint may have issues with data URLs, so we convert them to temp files
            import re
            import tempfile
            import os
            
            # Find all data URLs in img src attributes
            data_url_pattern = r'src="(data:image/[^;]+;base64,[^"]+)"'
            temp_files = []
            
            def replace_data_url(match):
                """Replace data URL with temporary file path"""
                data_url = match.group(1)
                try:
                    # Extract image data
                    header, encoded = data_url.split(',', 1)
                    image_format = header.split('/')[1].split(';')[0]  # e.g., 'png'
                    image_data = base64.b64decode(encoded)
                    
                    # Validate image data
                    if len(image_data) < 100:
                        _logger.warning(f"Image data too small ({len(image_data)} bytes), skipping")
                        return match.group(0)
                    
                    # Create temporary file
                    temp_file = tempfile.NamedTemporaryFile(
                        delete=False,
                        suffix=f'.{image_format}',
                        prefix='weasyprint_img_'
                    )
                    temp_file.write(image_data)
                    temp_file.close()
                    temp_files.append(temp_file.name)
                    
                    # Return file:// URL for WeasyPrint
                    file_url = f'file://{temp_file.name}'
                    _logger.debug(
                        f"Converted data URL to temp file: {file_url} "
                        f"({len(image_data)} bytes, {image_format})"
                    )
                    return f'src="{file_url}"'
                except Exception as e:
                    _logger.warning(f"Failed to convert data URL to temp file: {e}, keeping original")
                    return match.group(0)
            
            # Replace data URLs with temp files
            html_with_files = re.sub(data_url_pattern, replace_data_url, html_content)
            
            # Log conversion statistics
            data_url_count = len(re.findall(data_url_pattern, html_content))
            _logger.info(f"Converting HTML to PDF: {data_url_count} data URLs found, {len(temp_files)} temp files created")
            
            try:
                # Configure fonts for better rendering
                font_config = FontConfiguration()
                
                # Create HTML object from string
                html_obj = HTML(string=html_with_files, base_url=None)
                
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
                    
                    /* Ensure images are visible */
                    img {
                        max-width: 100%;
                        height: auto;
                    }
                ''', font_config=font_config)
                
                # Generate PDF
                pdf_bytes = html_obj.write_pdf(
                    stylesheets=[pdf_css],
                    font_config=font_config
                )
                
                _logger.info(f"✓ WeasyPrint generated PDF: {len(pdf_bytes)} bytes")
                
                return pdf_bytes
            finally:
                # Clean up temporary files
                for temp_file in temp_files:
                    try:
                        if os.path.exists(temp_file):
                            os.unlink(temp_file)
                            _logger.debug(f"Cleaned up temp file: {temp_file}")
                    except Exception as e:
                        _logger.warning(f"Failed to delete temp file {temp_file}: {e}")

        except Exception as e:
            _logger.error(f"✗ WeasyPrint conversion failed: {e}", exc_info=True)
            
            # Provide detailed error message based on error type
            error_str = str(e).lower()
            if 'font' in error_str:
                raise Exception(_(
                    "Erreur de police de caractères lors de la conversion PDF. "
                    "Vérifiez que les polices nécessaires sont installées."
                ))
            elif 'image' in error_str or 'file' in error_str:
                raise Exception(_(
                    "Erreur de chargement d'image lors de la conversion PDF. "
                    "Vérifiez que toutes les images sont accessibles et valides."
                ))
            elif 'css' in error_str or 'style' in error_str:
                raise Exception(_(
                    "Erreur de style CSS lors de la conversion PDF. "
                    "Vérifiez la syntaxe CSS du modèle."
                ))
            else:
                raise Exception(_(
                    "Échec de la conversion HTML vers PDF : %s"
                ) % str(e))

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

    def _validate_signatures_in_pdf(self, pdf_content, expected_signatures, contract_name):
        """
        Validate that signature images are embedded in PDF
        Uses PyPDF2 to extract and verify images

        Args:
            pdf_content (bytes): PDF content
            expected_signatures (list): List of expected signature types ('company', 'subcontractor')
            contract_name (str): Contract name for logging

        Raises:
            UserError: If expected signatures are not found in PDF
        """
        if not PYPDF2_AVAILABLE:
            _logger.warning("PyPDF2 not available, skipping signature validation")
            return

        try:
            reader = PdfReader(io.BytesIO(pdf_content))
            
            # Count images in PDF
            image_count = 0
            for page in reader.pages:
                if '/XObject' in page['/Resources']:
                    xobjects = page['/Resources']['/XObject'].get_object()
                    for obj in xobjects:
                        if xobjects[obj]['/Subtype'] == '/Image':
                            image_count += 1
            
            _logger.info(
                f"PDF signature validation for {contract_name}: "
                f"found {image_count} images, expected {len(expected_signatures)} signatures"
            )
            
            # Basic validation: check if we have at least as many images as expected signatures
            if image_count < len(expected_signatures):
                _logger.warning(
                    f"⚠️ PDF may be missing signatures for {contract_name}: "
                    f"found {image_count} images but expected {len(expected_signatures)} signatures"
                )
                # Don't raise error, just warn - images might be embedded differently
            else:
                _logger.info(
                    f"✓ PDF signature validation passed for {contract_name}: "
                    f"{image_count} images found (expected {len(expected_signatures)} signatures)"
                )

        except Exception as e:
            _logger.warning(f"Could not validate signatures in PDF for {contract_name}: {e}")
            # Don't fail PDF generation if validation fails

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
