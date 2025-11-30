# -*- coding: utf-8 -*-
"""
PDF Merger Service
Merges contract PDF with attached documents (planning, purchase orders, etc.)
"""

from odoo import models, api, _
from odoo.exceptions import UserError, ValidationError
import base64
import logging
import io

_logger = logging.getLogger(__name__)

# Try to import PyPDF2 for PDF merging
try:
    from PyPDF2 import PdfReader, PdfWriter, PdfMerger
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False
    _logger.warning("PyPDF2 not available. Install with: pip install PyPDF2")


class ContractPDFMerger(models.AbstractModel):
    """
    PDF Merger Service

    Responsible for:
    - Merging contract PDF with deliverable attachments
    - Validating PDF format of attachments
    - Generating table of contents
    - Adding page numbers to merged document
    """

    _name = 'construction.contract.pdf.merger'
    _description = 'Contract PDF Merger Service'

    # ============================================================
    # MAIN MERGE METHOD
    # ============================================================

    @api.model
    def merge_contract_with_attachments(self, contract):
        """
        Merge contract PDF with all deliverables marked for merging

        Args:
            contract: construction.contract record

        Returns:
            bytes: Merged PDF content

        Raises:
            UserError: If merge fails or no PyPDF2 available
        """
        if not PYPDF2_AVAILABLE:
            _logger.error("✗ PyPDF2 not available - cannot merge PDFs")
            raise UserError(_(
                "❌ PyPDF2 non installé\n\n"
                "La bibliothèque PyPDF2 n'est pas installée. "
                "Elle est nécessaire pour fusionner plusieurs documents PDF.\n\n"
                "Installation :\n"
                "pip install PyPDF2\n\n"
                "PyPDF2 permet de combiner le contrat principal avec "
                "les documents annexes (planning, bons de commande, etc.).\n\n"
                "Contactez l'administrateur système pour l'installation."
            ))

        try:
            _logger.info(f"Starting PDF merge for contract {contract.name}")

            # Step 1: Get main contract PDF
            if not contract.pdf_document:
                _logger.error(
                    f"✗ Cannot merge attachments for contract {contract.name}: "
                    f"main PDF not generated"
                )
                raise UserError(_(
                    "❌ PDF du contrat manquant\n\n"
                    "Le PDF du contrat principal doit être généré avant "
                    "de fusionner les documents annexes.\n\n"
                    "Actions recommandées :\n"
                    "1. Cliquez sur 'Générer le PDF' pour créer le contrat principal\n"
                    "2. Une fois le PDF généré, vous pourrez fusionner les documents\n\n"
                    "Si le problème persiste, contactez l'administrateur."
                ))

            main_pdf_data = base64.b64decode(contract.pdf_document)
            
            # Validate main PDF
            if not self.validate_pdf_format(main_pdf_data):
                _logger.error(
                    f"✗ Main contract PDF validation failed for {contract.name}: "
                    f"size={len(main_pdf_data)} bytes"
                )
                raise UserError(_(
                    "❌ PDF du contrat invalide ou corrompu\n\n"
                    "Le PDF du contrat principal est invalide ou corrompu. "
                    "Il ne peut pas être fusionné avec les documents annexes.\n\n"
                    "Actions recommandées :\n"
                    "1. Régénérez le PDF du contrat en cliquant sur 'Générer le PDF'\n"
                    "2. Vérifiez que le modèle de contrat est valide\n"
                    "3. Contactez l'administrateur si le problème persiste\n\n"
                    "Taille du fichier : %d octets"
                ) % len(main_pdf_data))

            # Step 2: Get deliverables marked for merging, ordered by merge_order
            deliverables_to_merge = contract.deliverable_ids.filtered(
                lambda d: d.merge_in_contract and d.document
            ).sorted(key=lambda d: d.merge_order)

            if not deliverables_to_merge:
                _logger.info(f"No deliverables to merge for contract {contract.name}, returning main PDF")
                return main_pdf_data

            _logger.info(
                f"Found {len(deliverables_to_merge)} deliverables to merge: "
                f"{', '.join(deliverables_to_merge.mapped('name'))}"
            )

            # Step 3: Validate all deliverables are PDFs
            sections = [{'name': _('Main Contract'), 'data': main_pdf_data, 'page_count': 0}]
            
            for deliverable in deliverables_to_merge:
                try:
                    attachment_data = base64.b64decode(deliverable.document)
                except Exception as e:
                    _logger.error(
                        f"✗ Failed to decode document for deliverable {deliverable.name}: {e}"
                    )
                    raise UserError(_(
                        "❌ Document corrompu : '%s'\n\n"
                        "Le document ne peut pas être décodé. Il est peut-être corrompu.\n\n"
                        "Actions recommandées :\n"
                        "1. Supprimez ce document\n"
                        "2. Téléchargez à nouveau le document en format PDF\n"
                        "3. Assurez-vous que le fichier n'est pas corrompu\n\n"
                        "Détails techniques : %s"
                    ) % (deliverable.name, str(e)))
                
                if not self.validate_pdf_format(attachment_data):
                    _logger.error(
                        f"✗ Deliverable {deliverable.name} is not a valid PDF: "
                        f"size={len(attachment_data)} bytes"
                    )
                    raise UserError(_(
                        "❌ Document invalide : '%s'\n\n"
                        "Ce document n'est pas un fichier PDF valide ou est corrompu.\n\n"
                        "Actions recommandées :\n"
                        "1. Vérifiez que le fichier est bien au format PDF\n"
                        "2. Convertissez le document en PDF si nécessaire\n"
                        "3. Téléchargez à nouveau le document\n\n"
                        "Formats acceptés : PDF uniquement\n"
                        "Taille du fichier : %d octets"
                    ) % (deliverable.name, len(attachment_data)))
                
                sections.append({
                    'name': deliverable.name,
                    'data': attachment_data,
                    'page_count': 0,
                    'deliverable_type': deliverable.deliverable_type,
                })

            # Step 4: Merge PDFs
            merged_pdf = self._merge_pdfs(sections)

            # Step 5: Add table of contents
            final_pdf = self._add_table_of_contents(merged_pdf, sections)

            _logger.info(
                f"✓ PDF merge completed for contract {contract.name}: "
                f"{len(sections)} sections, {len(final_pdf)/1024:.1f} KB"
            )

            return final_pdf

        except UserError:
            # Re-raise UserError as-is (already has user-friendly message)
            raise
        except Exception as e:
            # Log detailed error for debugging
            _logger.error(
                f"✗ PDF merge failed for contract {contract.name}: {e}",
                exc_info=True
            )
            
            # Provide user-friendly error message in French
            error_type = type(e).__name__
            error_details = str(e)
            
            # Customize message based on error type
            if 'memory' in error_details.lower():
                error_msg = _(
                    "❌ Erreur de mémoire lors de la fusion\n\n"
                    "Les documents sont trop volumineux pour être fusionnés.\n\n"
                    "Actions recommandées :\n"
                    "1. Réduisez la taille des documents annexes\n"
                    "2. Fusionnez moins de documents à la fois\n"
                    "3. Contactez l'administrateur pour augmenter la mémoire disponible\n\n"
                    "Détails techniques : %s"
                ) % error_details
            elif 'pypdf' in error_details.lower() or 'pdf' in error_details.lower():
                error_msg = _(
                    "❌ Erreur de traitement PDF\n\n"
                    "Un problème est survenu lors de la fusion des PDF.\n\n"
                    "Causes possibles :\n"
                    "• Un des PDF est corrompu ou protégé par mot de passe\n"
                    "• Format PDF non standard\n"
                    "• Problème avec la bibliothèque PyPDF2\n\n"
                    "Actions recommandées :\n"
                    "1. Vérifiez que tous les PDF sont valides et non protégés\n"
                    "2. Essayez de fusionner les documents un par un\n"
                    "3. Contactez l'administrateur si le problème persiste\n\n"
                    "Détails techniques : %s"
                ) % error_details
            else:
                error_msg = _(
                    "❌ Erreur de fusion des documents\n\n"
                    "Une erreur inattendue s'est produite lors de la fusion des documents.\n\n"
                    "Type d'erreur : %s\n"
                    "Détails : %s\n\n"
                    "Veuillez contacter l'administrateur système avec ces informations."
                ) % (error_type, error_details)
            
            raise UserError(error_msg)

    # ============================================================
    # PDF VALIDATION
    # ============================================================

    @api.model
    def validate_pdf_format(self, file_data):
        """
        Validate that file is a valid PDF

        Args:
            file_data (bytes): File content to validate

        Returns:
            bool: True if valid PDF, False otherwise
        """
        if not file_data or len(file_data) < 100:
            _logger.warning("File data is empty or too small")
            return False

        try:
            # Check PDF magic number (header)
            if not file_data.startswith(b'%PDF-'):
                _logger.warning("File does not start with PDF magic number")
                return False

            # Try to read with PyPDF2
            if PYPDF2_AVAILABLE:
                reader = PdfReader(io.BytesIO(file_data))
                page_count = len(reader.pages)
                
                if page_count == 0:
                    _logger.warning("PDF has no pages")
                    return False
                
                _logger.debug(f"Valid PDF with {page_count} pages")
                return True
            else:
                # Basic validation without PyPDF2
                return True

        except Exception as e:
            _logger.warning(f"PDF validation failed: {e}")
            return False

    # ============================================================
    # PRIVATE MERGE METHODS
    # ============================================================

    def _merge_pdfs(self, sections):
        """
        Merge multiple PDF sections into one

        Args:
            sections (list): List of dicts with 'name', 'data', 'page_count'

        Returns:
            bytes: Merged PDF content
            
        Raises:
            Exception: If merge fails with detailed error message
        """
        try:
            merger = PdfMerger()
            
            # Track page numbers for each section
            current_page = 0
            
            for section in sections:
                section_name = section.get('name', 'Unknown')
                pdf_data = section['data']
                
                try:
                    reader = PdfReader(io.BytesIO(pdf_data))
                    page_count = len(reader.pages)
                    
                    if page_count == 0:
                        _logger.warning(
                            f"Section '{section_name}' has no pages, skipping"
                        )
                        continue
                    
                    # Update section page count and start page
                    section['page_count'] = page_count
                    section['start_page'] = current_page + 1
                    section['end_page'] = current_page + page_count
                    
                    # Add to merger
                    merger.append(io.BytesIO(pdf_data))
                    
                    current_page += page_count
                    
                    _logger.debug(
                        f"Added section '{section_name}': "
                        f"pages {section['start_page']}-{section['end_page']} "
                        f"({page_count} pages)"
                    )
                    
                except Exception as e:
                    _logger.error(
                        f"✗ Failed to process section '{section_name}': {e}"
                    )
                    raise Exception(_(
                        "Impossible de traiter la section '%s' : %s"
                    ) % (section_name, str(e)))
            
            # Write merged PDF
            output = io.BytesIO()
            merger.write(output)
            merger.close()
            
            merged_content = output.getvalue()
            
            _logger.info(
                f"✓ Merged {len(sections)} sections into {current_page} total pages, "
                f"{len(merged_content)/1024:.1f} KB"
            )
            
            return merged_content

        except Exception as e:
            _logger.error(f"✗ PDF merge operation failed: {e}", exc_info=True)
            raise

    def _add_table_of_contents(self, merged_pdf, sections):
        """
        Add table of contents page at beginning of merged PDF

        Args:
            merged_pdf (bytes): Merged PDF content
            sections (list): List of section dicts with page info

        Returns:
            bytes: PDF with TOC prepended
        """
        try:
            # Generate TOC HTML
            toc_html = self._generate_toc_html(sections)
            
            # Convert TOC HTML to PDF
            toc_pdf = self._convert_toc_html_to_pdf(toc_html)
            
            # Merge TOC with main PDF
            merger = PdfMerger()
            merger.append(io.BytesIO(toc_pdf))
            merger.append(io.BytesIO(merged_pdf))
            
            output = io.BytesIO()
            merger.write(output)
            merger.close()
            
            final_content = output.getvalue()
            
            _logger.info(f"Added TOC page, final PDF: {len(final_content)/1024:.1f} KB")
            
            return final_content

        except Exception as e:
            _logger.warning(f"Failed to add TOC, returning PDF without TOC: {e}")
            # Return original merged PDF if TOC generation fails
            return merged_pdf

    def _generate_toc_html(self, sections):
        """
        Generate HTML for table of contents

        Args:
            sections (list): List of section dicts

        Returns:
            str: HTML content for TOC
        """
        # Build TOC entries
        toc_entries = []
        for i, section in enumerate(sections, 1):
            # Get section type label
            section_type = section.get('deliverable_type', '')
            type_label = dict(self.env['construction.contract.deliverable']._fields['deliverable_type'].selection).get(
                section_type, ''
            ) if section_type else ''
            
            toc_entries.append({
                'number': i,
                'name': section['name'],
                'type': type_label,
                'start_page': section['start_page'],
                'end_page': section['end_page'],
                'page_count': section['page_count'],
            })
        
        # Generate HTML
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                @page {{
                    size: A4;
                    margin: 2cm;
                }}
                
                body {{
                    font-family: 'DejaVu Sans', Arial, sans-serif;
                    font-size: 11pt;
                    line-height: 1.6;
                    color: #333;
                }}
                
                h1 {{
                    color: #2c3e50;
                    font-size: 24pt;
                    margin-bottom: 30px;
                    border-bottom: 3px solid #3498db;
                    padding-bottom: 10px;
                }}
                
                .toc-entry {{
                    margin: 15px 0;
                    padding: 10px;
                    border-left: 4px solid #3498db;
                    background-color: #f8f9fa;
                }}
                
                .toc-number {{
                    font-weight: bold;
                    color: #3498db;
                    font-size: 14pt;
                }}
                
                .toc-name {{
                    font-size: 12pt;
                    font-weight: bold;
                    margin: 5px 0;
                }}
                
                .toc-type {{
                    font-size: 10pt;
                    color: #7f8c8d;
                    font-style: italic;
                }}
                
                .toc-pages {{
                    font-size: 10pt;
                    color: #7f8c8d;
                    margin-top: 5px;
                }}
                
                .footer {{
                    margin-top: 40px;
                    padding-top: 20px;
                    border-top: 1px solid #ddd;
                    font-size: 9pt;
                    color: #7f8c8d;
                    text-align: center;
                }}
            </style>
        </head>
        <body>
            <h1>{_('Table of Contents')}</h1>
            <p style="margin-bottom: 30px; color: #7f8c8d;">
                {_('This document contains %d sections with a total of %d pages.') % (
                    len(sections),
                    sum(s['page_count'] for s in sections)
                )}
            </p>
        """
        
        for entry in toc_entries:
            html += f"""
            <div class="toc-entry">
                <div class="toc-number">{entry['number']}.</div>
                <div class="toc-name">{entry['name']}</div>
                {f'<div class="toc-type">{entry["type"]}</div>' if entry['type'] else ''}
                <div class="toc-pages">
                    {_('Pages %d-%d (%d pages)') % (
                        entry['start_page'],
                        entry['end_page'],
                        entry['page_count']
                    )}
                </div>
            </div>
            """
        
        html += """
            <div class="footer">
                """ + _('Document generated automatically') + """
            </div>
        </body>
        </html>
        """
        
        return html

    def _convert_toc_html_to_pdf(self, html_content):
        """
        Convert TOC HTML to PDF using WeasyPrint

        Args:
            html_content (str): HTML string

        Returns:
            bytes: PDF content
        """
        try:
            # Try to use WeasyPrint if available
            from weasyprint import HTML, CSS
            from weasyprint.text.fonts import FontConfiguration
            
            font_config = FontConfiguration()
            html_obj = HTML(string=html_content)
            
            pdf_bytes = html_obj.write_pdf(font_config=font_config)
            
            _logger.debug(f"TOC PDF generated: {len(pdf_bytes)} bytes")
            return pdf_bytes
            
        except ImportError:
            _logger.warning("WeasyPrint not available for TOC generation")
            # Fallback: create simple text-based TOC using reportlab
            return self._create_simple_toc_pdf(html_content)

    def _create_simple_toc_pdf(self, html_content):
        """
        Create simple TOC PDF without WeasyPrint (fallback)

        Args:
            html_content (str): HTML content (will extract text)

        Returns:
            bytes: Simple PDF with TOC text
        """
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import A4
            import re
            
            # Extract text from HTML
            text = re.sub('<[^<]+?>', '', html_content)
            
            # Create PDF
            buffer = io.BytesIO()
            c = canvas.Canvas(buffer, pagesize=A4)
            
            # Add title
            c.setFont("Helvetica-Bold", 18)
            c.drawString(50, 800, _('Table of Contents'))
            
            # Add text
            c.setFont("Helvetica", 10)
            y = 750
            for line in text.split('\n'):
                line = line.strip()
                if line:
                    c.drawString(50, y, line[:80])
                    y -= 15
                    if y < 50:
                        break
            
            c.save()
            
            pdf_bytes = buffer.getvalue()
            _logger.debug(f"Simple TOC PDF generated: {len(pdf_bytes)} bytes")
            return pdf_bytes
            
        except Exception as e:
            _logger.error(f"Failed to create simple TOC PDF: {e}")
            raise

    # ============================================================
    # UTILITY METHODS
    # ============================================================

    @api.model
    def get_mergeable_deliverables(self, contract):
        """
        Get list of deliverables that can be merged

        Args:
            contract: construction.contract record

        Returns:
            recordset: Deliverables with documents that can be merged
        """
        return contract.deliverable_ids.filtered(
            lambda d: d.document and self.validate_pdf_format(base64.b64decode(d.document))
        )

    @api.model
    def preview_merge_structure(self, contract):
        """
        Preview the structure of merged PDF without actually merging

        Args:
            contract: construction.contract record

        Returns:
            dict: Preview information
        """
        deliverables_to_merge = contract.deliverable_ids.filtered(
            lambda d: d.merge_in_contract and d.document
        ).sorted(key=lambda d: d.merge_order)

        sections = []
        total_size = 0
        
        # Main contract
        if contract.pdf_document:
            main_pdf_data = base64.b64decode(contract.pdf_document)
            sections.append({
                'name': _('Main Contract'),
                'type': 'contract',
                'order': 0,
                'size_kb': len(main_pdf_data) / 1024,
                'is_valid': self.validate_pdf_format(main_pdf_data),
            })
            total_size += len(main_pdf_data)
        
        # Deliverables
        for deliverable in deliverables_to_merge:
            attachment_data = base64.b64decode(deliverable.document)
            sections.append({
                'name': deliverable.name,
                'type': deliverable.deliverable_type,
                'order': deliverable.merge_order,
                'size_kb': len(attachment_data) / 1024,
                'is_valid': self.validate_pdf_format(attachment_data),
            })
            total_size += len(attachment_data)
        
        return {
            'section_count': len(sections),
            'sections': sections,
            'total_size_kb': total_size / 1024,
            'estimated_size_kb': total_size / 1024 * 1.1,  # Add 10% overhead
        }
