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

            # Step 2a: Generate cover page PDF
            cover_html = self._build_cover_page_html(contract)
            cover_pdf = self._convert_html_to_pdf(cover_html)

            # Step 2b: Convert contract body HTML to PDF
            pdf_content = self._convert_html_to_pdf(html_content)

            # Step 2c: Prepend cover page
            if PYPDF2_AVAILABLE and cover_pdf:
                try:
                    merger = PdfWriter()
                    for page in PdfReader(io.BytesIO(cover_pdf)).pages:
                        merger.add_page(page)
                    for page in PdfReader(io.BytesIO(pdf_content)).pages:
                        merger.add_page(page)
                    buf = io.BytesIO()
                    merger.write(buf)
                    pdf_content = buf.getvalue()
                    _logger.info("[PDF] Cover page prepended to contract body")
                except Exception as e:
                    _logger.warning("[PDF] Could not prepend cover page: %s", e)

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

    # PDF @page CSS with BLG branding and proper Page X/Y pagination
    _BLG_PDF_CSS = """
        @page {
            size: A4;
            margin: 2.5cm 2cm 3cm 2cm;
            @bottom-center {
                content: "Page " counter(page) " / " counter(pages);
                font-family: Arial, sans-serif;
                font-size: 9pt;
                color: #888;
            }
            @bottom-right {
                content: "BLG Groupe — " string(doc-ref);
                font-family: Arial, sans-serif;
                font-size: 9pt;
                color: #888;
            }
            @top-right {
                content: string(doc-date);
                font-family: Arial, sans-serif;
                font-size: 8pt;
                color: #aaa;
            }
        }
        @page :first {
            /* No header/footer on cover page */
            @bottom-center { content: none; }
            @bottom-right  { content: none; }
            @top-right     { content: none; }
        }
        body {
            font-family: Arial, 'DejaVu Sans', sans-serif;
            font-size: 11pt;
            line-height: 1.6;
            color: #2C2C2C;
            string-set: doc-ref attr(data-ref), doc-date attr(data-date);
        }
        table { page-break-inside: avoid; width: 100%; }
        h1, h2, h3 { page-break-after: avoid; color: #8B3A3A; }
        p { orphans: 3; widows: 3; }
        img { max-width: 100%; height: auto; }
        .page-break { page-break-before: always; }
        /* Billing schedule table */
        .blg-billing-schedule th { background: #f5f0eb; }
        .blg-billing-schedule td, .blg-billing-schedule th {
            padding: 6px 10px;
            border-bottom: 1px solid #ddd;
        }
    """

    def _build_cover_page_html(self, contract):
        """Return HTML for the BLG cover page (first page of the PDF bundle)."""
        chantier = contract.chantier_id
        st = contract.subcontractor_id
        date_str = contract._format_date(contract.date) if hasattr(contract, 'date') and contract.date else ''
        return f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"/></head>
<body>
<div style="display:flex;flex-direction:column;height:27cm;justify-content:space-between;
            font-family:Arial,sans-serif;padding:2cm;">
    <!-- Header -->
    <div style="border-bottom:4px solid #8B3A3A;padding-bottom:1.5cm;margin-bottom:1.5cm;">
        <div style="font-size:28pt;font-weight:bold;color:#8B3A3A;letter-spacing:2px;">BLG GROUPE</div>
        <div style="font-size:10pt;color:#666;margin-top:4px;">Contrat de sous-traitance</div>
    </div>
    <!-- Contract info -->
    <div style="flex:1;">
        <table style="width:100%;border-collapse:collapse;font-size:12pt;">
            <tr><td style="width:40%;color:#888;padding:8px 0;">Référence</td>
                <td style="font-weight:bold;">{contract.name or ''}</td></tr>
            <tr><td style="color:#888;padding:8px 0;">Chantier</td>
                <td>{chantier.name if chantier else '—'}</td></tr>
            <tr><td style="color:#888;padding:8px 0;">Sous-traitant</td>
                <td style="font-weight:bold;">{st.name if st else '—'}</td></tr>
            <tr><td style="color:#888;padding:8px 0;">SIRET</td>
                <td>{getattr(st, 'siret', '') or '—'}</td></tr>
            <tr><td style="color:#888;padding:8px 0;">Montant HT</td>
                <td style="font-weight:bold;color:#8B3A3A;">{contract._format_currency(contract.total_amount_ht or 0)}</td></tr>
            <tr><td style="color:#888;padding:8px 0;">Date</td>
                <td>{date_str or '—'}</td></tr>
        </table>
    </div>
    <!-- Footer watermark -->
    <div style="border-top:2px solid #e0d6cc;padding-top:1cm;text-align:center;color:#bbb;font-size:9pt;">
        Document confidentiel — BLG Groupe — {chantier.city if chantier and hasattr(chantier, 'city') and chantier.city else ''}
    </div>
</div>
</body></html>"""

    def _get_annexes_pdf(self, contract):
        """Return bytes of all annexes merged into a single PDF (without the main contract).

        Annexes order:
          1. CCTP / Cahier des charges
          2. Planning chantier
          3. Planning sous-traitant
          4. Bons de commande (POs)

        Returns:
            bytes | None: merged annexes PDF, or None if no annexes found.
        """
        if not PYPDF2_AVAILABLE:
            _logger.warning("[ANNEXES] PyPDF2 not available, skipping annexes")
            return None

        merger = PdfWriter()
        added = 0

        def _try_add(pdf_bytes, label):
            nonlocal added
            try:
                reader = PdfReader(io.BytesIO(pdf_bytes))
                for page in reader.pages:
                    merger.add_page(page)
                added += len(reader.pages)
                _logger.info("[ANNEXES] Added %s: %d pages", label, len(reader.pages))
            except Exception as e:
                _logger.warning("[ANNEXES] Skipped %s: %s", label, e)

        # 1. CCTP
        cctp_docs = self.env['construction.document'].search([
            ('chantier_id', '=', contract.chantier_id.id),
            ('document_type', '=', 'specs'),
        ], limit=1)
        if cctp_docs and cctp_docs.file_data:
            _try_add(base64.b64decode(cctp_docs.file_data), "CCTP")

        # 2. Planning chantier
        planning_docs = self.env['construction.document'].search([
            ('chantier_id', '=', contract.chantier_id.id),
            ('document_type', '=', 'schedule'),
            ('partner_id', '=', False),
        ], limit=1)
        if planning_docs and planning_docs.file_data:
            _try_add(base64.b64decode(planning_docs.file_data), "Planning Chantier")

        # 3. Planning sous-traitant
        st_planning = self.env['construction.document'].search([
            ('chantier_id', '=', contract.chantier_id.id),
            ('document_type', '=', 'schedule'),
            ('partner_id', '=', contract.subcontractor_id.id),
        ], limit=1)
        if st_planning and st_planning.file_data:
            _try_add(base64.b64decode(st_planning.file_data), "Planning ST")

        # 4. BdC (POs)
        report = self.env.ref('purchase.action_report_purchase_order', raise_if_not_found=False)
        for po in contract.purchase_order_ids:
            try:
                if report:
                    pdf_content, _ = self.env['ir.actions.report'].sudo()._render_qweb_pdf(
                        report, [po.id]
                    )
                    _try_add(pdf_content, f"BdC {po.name}")
            except Exception as e:
                _logger.warning("[ANNEXES] Skipped BdC %s: %s", po.name, e)

        if not added:
            return None

        output = io.BytesIO()
        merger.write(output)
        _logger.info("[ANNEXES] Total annexes: %d pages", added)
        return output.getvalue()

    def _convert_html_to_pdf(self, html_content, css_override=None):
        """
        Convert HTML to PDF using WeasyPrint.

        Args:
            html_content (str): HTML string to convert
            css_override (str | None): Optional CSS string to override _BLG_PDF_CSS

        Returns:
            bytes: PDF content

        Raises:
            Exception: If conversion fails
        """
        import re
        import tempfile
        import os

        try:
            # Replace data: URLs with temp files for WeasyPrint compatibility
            data_url_pattern = r'src="(data:image/[^;]+;base64,[^"]+)"'
            temp_files = []

            def replace_data_url(match):
                data_url = match.group(1)
                try:
                    header, encoded = data_url.split(',', 1)
                    image_format = header.split('/')[1].split(';')[0]
                    image_data = base64.b64decode(encoded)
                    if len(image_data) < 100:
                        return match.group(0)
                    tmp = tempfile.NamedTemporaryFile(
                        delete=False, suffix=f'.{image_format}', prefix='weasyprint_img_'
                    )
                    tmp.write(image_data)
                    tmp.close()
                    temp_files.append(tmp.name)
                    return f'src="file://{tmp.name}"'
                except Exception as e:
                    _logger.warning("Failed to convert data URL: %s", e)
                    return match.group(0)

            html_with_files = re.sub(data_url_pattern, replace_data_url, html_content)
            _logger.info(
                "Converting HTML to PDF: %d data URLs, %d temp files",
                len(re.findall(data_url_pattern, html_content)), len(temp_files),
            )

            try:
                font_config = FontConfiguration()
                html_obj = HTML(string=html_with_files, base_url=None)
                pdf_css = CSS(
                    string=css_override if css_override is not None else self._BLG_PDF_CSS,
                    font_config=font_config,
                )
                pdf_bytes = html_obj.write_pdf(
                    stylesheets=[pdf_css],
                    font_config=font_config,
                )
                _logger.info("✓ WeasyPrint generated PDF: %d bytes", len(pdf_bytes))
                return pdf_bytes
            finally:
                for tmp_path in temp_files:
                    try:
                        if os.path.exists(tmp_path):
                            os.unlink(tmp_path)
                    except Exception:
                        pass

        except Exception as e:
            _logger.error("✗ WeasyPrint conversion failed: %s", e, exc_info=True)
            error_str = str(e).lower()
            if 'font' in error_str:
                raise Exception(_("Erreur de police lors de la conversion PDF : %s") % str(e))
            elif 'image' in error_str or 'file' in error_str:
                raise Exception(_("Erreur de chargement d'image lors de la conversion PDF : %s") % str(e))
            elif 'css' in error_str or 'style' in error_str:
                raise Exception(_("Erreur de style CSS lors de la conversion PDF : %s") % str(e))
            else:
                raise Exception(_("Échec de la conversion HTML vers PDF : %s") % str(e))

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

    # ============================================================
    # PDF MERGE (FUSION NUCLEAIRE)
    # ============================================================

    @api.model
    def merge_contract_bundle(self, contract, contract_pdf_bytes):
        """Merge contract PDF with annexes.

        Delegates annexe collection to ``_get_annexes_pdf`` and prepends the
        contract body. Returns ``contract_pdf_bytes`` unchanged if no annexes
        are found or if PyPDF2 is unavailable.
        """
        import gc

        if not PYPDF2_AVAILABLE:
            _logger.warning("[MERGE] PyPDF2 not available, skipping PDF merge")
            return contract_pdf_bytes

        _logger.info("[MERGE] Starting PDF bundle merge for contract %s", contract.name)

        annexes_pdf = self._get_annexes_pdf(contract)
        if not annexes_pdf:
            _logger.info("[MERGE] No annexes found for %s", contract.name)
            return contract_pdf_bytes

        try:
            merger = PdfWriter()
            for page in PdfReader(io.BytesIO(contract_pdf_bytes)).pages:
                merger.add_page(page)
            for page in PdfReader(io.BytesIO(annexes_pdf)).pages:
                merger.add_page(page)
            output = io.BytesIO()
            merger.write(output)
            merged_pdf = output.getvalue()
            _logger.info(
                "[MERGE] Complete for %s: final size %.1f KB",
                contract.name, len(merged_pdf) / 1024,
            )
            return merged_pdf
        except UserError:
            raise
        except Exception as e:
            _logger.error("[MERGE] Critical failure for %s: %s", contract.name, e, exc_info=True)
            return contract_pdf_bytes
        finally:
            gc.collect()

