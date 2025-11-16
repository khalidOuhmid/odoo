# -*- coding: utf-8 -*-
"""
Template Renderer Service
Handles Jinja2 template rendering with contract data
Single Responsibility: Render templates safely with data
"""

from odoo import models, api, _, fields
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

# Try to import Jinja2
try:
    from jinja2.sandbox import SandboxedEnvironment

    JINJA2_AVAILABLE = True
except ImportError:
    JINJA2_AVAILABLE = False
    _logger.warning("Jinja2 not available. Install with: pip install jinja2")


class ContractTemplateRenderer(models.AbstractModel):
    """
    Template Rendering Service

    Responsible for:
    - Preparing contract data context
    - Rendering Jinja2 templates safely
    - Handling template errors gracefully
    """

    _name = 'construction.contract.template.renderer'
    _description = 'Contract Template Renderer Service'

    # ============================================================
    # MAIN RENDERING METHOD
    # ============================================================

    @api.model
    def render_template(self, contract):
        """
        Render contract template with Jinja2

        Args:
            contract: construction.contract record

        Returns:
            str: Fully rendered HTML

        Raises:
            UserError: If Jinja2 not available or rendering fails
        """
        if not JINJA2_AVAILABLE:
            _logger.error("✗ Jinja2 not available - cannot render template")
            raise UserError(_(
                "❌ Jinja2 non installé\n\n"
                "Le moteur de templates Jinja2 n'est pas installé. "
                "Il est nécessaire pour générer les contrats.\n\n"
                "Installation :\n"
                "pip install jinja2\n\n"
                "Jinja2 permet de remplir les modèles de contrat avec "
                "les données du chantier et du sous-traitant.\n\n"
                "Contactez l'administrateur système pour l'installation."
            ))

        if not contract.template_id:
            _logger.error(
                f"✗ No template selected for contract {contract.name}"
            )
            raise UserError(_(
                "❌ Aucun modèle sélectionné\n\n"
                "Aucun modèle de contrat n'est sélectionné pour ce contrat.\n\n"
                "Actions recommandées :\n"
                "1. Sélectionnez un modèle dans le champ 'Modèle de contrat'\n"
                "2. Si aucun modèle n'existe, créez-en un dans Modèles de Contrat\n"
                "3. Assurez-vous qu'au moins un modèle est défini par défaut\n\n"
                "Contactez l'administrateur si vous ne pouvez pas sélectionner de modèle."
            ))

        try:
            # Step 1: Prepare context data
            context = self._prepare_context(contract)

            # Step 2: Get template HTML and CSS
            template_html = contract.template_id.grapesjs_html or ''
            template_css = contract.template_id.grapesjs_css or ''
            
            # DEBUG: Check if template contains signature blocks
            has_company_sig_block = 'company_signature' in template_html
            has_subcontractor_sig_block = 'subcontractor_signature' in template_html
            _logger.info(
                f"Template check for {contract.name}: "
                f"template_has_company_sig_block={has_company_sig_block}, "
                f"template_has_subcontractor_sig_block={has_subcontractor_sig_block}, "
                f"context_has_company_sig={bool(context.get('company_signature'))}, "
                f"context_has_subcontractor_sig={bool(context.get('subcontractor_signature'))}"
            )
            
            if not has_company_sig_block:
                _logger.warning(f"⚠️ Template {contract.template_id.name} does NOT contain 'company_signature' block!")
            if not has_subcontractor_sig_block:
                _logger.warning(f"⚠️ Template {contract.template_id.name} does NOT contain 'subcontractor_signature' block!")

            # Step 3 & 4: Render template and assemble HTML document
            full_html = self._render_with_context(template_html, template_css, context)
            
            # DEBUG: Check if rendered HTML contains signature images
            rendered_has_company_img = 'data:image/png;base64' in full_html and 'company_signature' in full_html.lower()
            rendered_has_subcontractor_img = 'data:image/png;base64' in full_html and 'subcontractor_signature' in full_html.lower()
            _logger.info(
                f"Rendered HTML check for {contract.name}: "
                f"has_company_img={rendered_has_company_img}, "
                f"has_subcontractor_img={rendered_has_subcontractor_img}"
            )

            _logger.info(
                f"Template rendered successfully for contract {contract.name}: "
                f"company_signature={'yes' if context.get('company_signature') else 'no'}, "
                f"subcontractor_signature={'yes' if context.get('subcontractor_signature') else 'no'}, "
                f"html_length={len(full_html)}"
            )

            return full_html

        except UserError:
            # Re-raise UserError as-is (already has user-friendly message)
            raise
        except Exception as e:
            # Log detailed error for debugging
            _logger.error(
                f"✗ Template rendering failed for contract {contract.name}: {e}",
                exc_info=True
            )
            
            # Provide user-friendly error message in French
            error_str = str(e).lower()
            
            # Customize message based on error type
            if 'undefined' in error_str or 'variable' in error_str:
                error_msg = _(
                    "❌ Erreur de variable dans le modèle\n\n"
                    "Le modèle de contrat utilise une variable qui n'existe pas "
                    "ou qui n'a pas de valeur.\n\n"
                    "Actions recommandées :\n"
                    "1. Vérifiez que toutes les variables du modèle sont correctes\n"
                    "2. Vérifiez que toutes les données du contrat sont remplies\n"
                    "3. Modifiez le modèle pour corriger les variables manquantes\n\n"
                    "Détails techniques : %s"
                ) % str(e)
            elif 'syntax' in error_str or 'template' in error_str:
                error_msg = _(
                    "❌ Erreur de syntaxe dans le modèle\n\n"
                    "Le modèle de contrat contient une erreur de syntaxe Jinja2.\n\n"
                    "Actions recommandées :\n"
                    "1. Ouvrez l'éditeur de modèle\n"
                    "2. Vérifiez la syntaxe des variables : {{ variable }}\n"
                    "3. Vérifiez la syntaxe des boucles : {% for %} ... {% endfor %}\n"
                    "4. Vérifiez la syntaxe des conditions : {% if %} ... {% endif %}\n\n"
                    "Détails techniques : %s"
                ) % str(e)
            elif 'signature' in error_str:
                error_msg = _(
                    "❌ Erreur de chargement des signatures\n\n"
                    "Un problème est survenu lors du chargement des signatures.\n\n"
                    "Actions recommandées :\n"
                    "1. Vérifiez que la signature de l'entreprise est configurée\n"
                    "2. Vérifiez que le fichier blg_signature.png existe\n"
                    "3. Si le contrat est signé, vérifiez la signature du sous-traitant\n\n"
                    "Détails techniques : %s"
                ) % str(e)
            else:
                error_msg = _(
                    "❌ Erreur de rendu du modèle\n\n"
                    "Une erreur inattendue s'est produite lors du rendu du modèle.\n\n"
                    "Type d'erreur : %s\n"
                    "Détails : %s\n\n"
                    "Actions recommandées :\n"
                    "1. Vérifiez que le modèle de contrat est valide\n"
                    "2. Vérifiez que toutes les données du contrat sont remplies\n"
                    "3. Contactez l'administrateur si le problème persiste"
                ) % (type(e).__name__, str(e))
            
            raise UserError(error_msg)

    @api.model
    def render_preview_from_wizard(self, wizard):
        """
        Render contract template preview from wizard data.

        Args:
            wizard (contract.creation.wizard): Wizard instance

        Returns:
            str: Fully rendered HTML preview
        """
        if not JINJA2_AVAILABLE:
            _logger.error("✗ Jinja2 not available - cannot render preview")
            raise UserError(_(
                "❌ Jinja2 non installé\n\n"
                "Le moteur de templates Jinja2 n'est pas installé. "
                "Il est nécessaire pour générer l'aperçu.\n\n"
                "Installation :\n"
                "pip install jinja2\n\n"
                "Contactez l'administrateur système pour l'installation."
            ))

        if not wizard.template_id:
            _logger.warning("No template selected in wizard for preview")
            raise UserError(_(
                "❌ Aucun modèle sélectionné\n\n"
                "Veuillez sélectionner un modèle de contrat pour afficher l'aperçu.\n\n"
                "Si aucun modèle n'est disponible, créez-en un dans Modèles de Contrat."
            ))

        try:
            context = self._prepare_wizard_context(wizard)
            template_html = wizard.template_id.grapesjs_html or ''
            template_css = wizard.template_id.grapesjs_css or ''
            full_html = self._render_with_context(template_html, template_css, context)

            _logger.info(
                "Preview rendered successfully for chantier %s",
                wizard.chantier_id.display_name if wizard.chantier_id else 'N/A'
            )
            return full_html

        except UserError:
            # Re-raise UserError as-is (already has user-friendly message)
            raise
        except Exception as e:
            # Log detailed error for debugging
            _logger.error(
                "✗ Template preview rendering failed: %s",
                e,
                exc_info=True
            )
            
            # Provide user-friendly error message in French
            error_str = str(e).lower()
            
            if 'undefined' in error_str or 'variable' in error_str:
                error_msg = _(
                    "❌ Erreur de variable dans l'aperçu\n\n"
                    "Le modèle utilise une variable qui n'a pas de valeur.\n\n"
                    "Actions recommandées :\n"
                    "1. Vérifiez que tous les champs requis sont remplis\n"
                    "2. Sélectionnez un chantier, un sous-traitant et des lots\n"
                    "3. Vérifiez le modèle de contrat\n\n"
                    "Détails : %s"
                ) % str(e)
            else:
                error_msg = _(
                    "❌ Erreur de génération de l'aperçu\n\n"
                    "Impossible de générer l'aperçu du contrat.\n\n"
                    "Actions recommandées :\n"
                    "1. Vérifiez que toutes les données sont remplies\n"
                    "2. Vérifiez que le modèle est valide\n"
                    "3. Contactez l'administrateur si le problème persiste\n\n"
                    "Détails : %s"
                ) % str(e)
            
            raise UserError(error_msg)

    # ============================================================
    # CONTEXT PREPARATION
    # ============================================================

    def _prepare_context(self, contract):
        """
        Prepare data context for template rendering
        Extracts all necessary data from contract and related records

        Args:
            contract: construction.contract record

        Returns:
            dict: Context dictionary with all template variables
        """
        contract.ensure_one()

        currency = contract.currency_id or self.env.company.currency_id

        contract_data = {
            'name': contract.name,
            'date': contract.date.strftime('%d/%m/%Y') if contract.date else '',
            'start_date': contract.start_date.strftime('%d/%m/%Y') if contract.start_date else '',
            'end_date': contract.end_date.strftime('%d/%m/%Y') if contract.end_date else '',
            'total_amount_ht': self._format_currency(contract.total_amount_ht, currency),
            'total_amount_tva': self._format_currency(contract.total_amount_tva, currency),
            'total_amount_ttc': self._format_currency(contract.total_amount_ttc, currency),
            'retention_amount': self._format_currency(contract.retention_amount, currency),
            'retention_rate': f"{contract.retention_rate:.1f}",
        }

        chantier = contract.chantier_id
        chantier_data = {
            'name': chantier.name or '',
            'reference': chantier.reference or '',
            'client': chantier.client.name if chantier.client else '',
            'address': chantier.address or '',
            'city': chantier.city or '',
            'postal_code': chantier.zip_code or '',
        }

        subcontractor = contract.subcontractor_id
        subcontractor_data = {
            'name': subcontractor.name or '',
            'siret': subcontractor.company_registry or '',
            'email': subcontractor.email or '',
            'phone': subcontractor.phone or '',
            'mobile': subcontractor.mobile or '',
            'address': self._format_address(subcontractor),
            'city': subcontractor.city or '',
            'urssaf_code': getattr(subcontractor, 'urssaf_code', '') or '',
        }

        lots_data = []
        for lot in contract.lot_ids:
            lot_amount = self._calculate_lot_amount(contract, lot)
            lots_data.append({
                'name': lot.name or '',
                'description': lot.description or '',
                'amount': self._format_currency(lot_amount, currency),
            })

        purchase_orders = contract.purchase_order_ids.filtered(
            lambda po: po.partner_id == contract.subcontractor_id
        )
        pos_data = []
        for po in purchase_orders:
            pos_data.append({
                'name': po.name or '',
                'date': po.date_order.strftime('%d/%m/%Y') if po.date_order else '',
                'amount': self._format_currency(po.amount_total, po.currency_id or currency),
            })

        deliverables_data = []
        for deliverable in contract.deliverable_ids:
            deliverables_data.append({
                'name': deliverable.name or '',
                'type': dict(deliverable._fields['deliverable_type'].selection).get(
                    deliverable.deliverable_type, ''
                ),
                'description': deliverable.description or '',
            })

        # Company data
        company = self.env.company
        company_data = {
            'name': company.name or '',
            'siret': company.company_registry or '',
            'address': self._format_address(company),
            'city': company.city or '',
            'email': company.email or '',
            'phone': company.phone or '',
        }

        # Company signature - use new signature loader service
        company_signature_data = None
        try:
            signature_loader = self.env['construction.contract.signature.loader']
            company_signature_data = signature_loader.load_company_signature()
            _logger.info(f"✓ Company signature loaded successfully for contract {contract.name}")
        except UserError as e:
            # User-facing error with clear instructions - log and re-raise
            _logger.error(f"✗ Failed to load company signature for contract {contract.name}: {e}")
            raise
        except Exception as e:
            # Unexpected error - log and raise with French message
            _logger.error(f"✗ Unexpected error loading company signature for contract {contract.name}: {e}", exc_info=True)
            raise UserError(_(
                "Erreur inattendue lors du chargement de la signature de l'entreprise: %s"
            ) % str(e))
        

        # Subcontractor signature (if contract is signed) - use new signature loader service
        subcontractor_signature_data = None
        # Get signature from context first (passed during PDF regeneration), then from contract
        signature = self.env.context.get('contract_signature') or contract.signature_id
        if signature:
            try:
                signature_loader = self.env['construction.contract.signature.loader']
                subcontractor_signature_data = signature_loader.load_subcontractor_signature(signature)
                _logger.info(f"✓ Subcontractor signature loaded successfully for contract {contract.name}")
            except UserError as e:
                # User-facing error - log and re-raise
                _logger.error(f"✗ Failed to load subcontractor signature for contract {contract.name}: {e}")
                raise
            except Exception as e:
                # Unexpected error - log and raise with French message
                _logger.error(f"✗ Unexpected error loading subcontractor signature for contract {contract.name}: {e}", exc_info=True)
                raise UserError(_(
                    "Erreur inattendue lors du chargement de la signature du sous-traitant: %s"
                ) % str(e))

        context = {
            'contract': contract_data,
            'chantier': chantier_data,
            'subcontractor': subcontractor_data,
            'lots': lots_data,
            'purchase_orders': pos_data,
            'deliverables': deliverables_data,
            'company': company_data,
        }
        
        # Add company signature - MUST be added if loaded
        if company_signature_data:
            context['company_signature'] = company_signature_data
            _logger.info(f"Added company signature to context for contract {contract.name}")
        else:
            _logger.warning(f"NO company signature data for contract {contract.name} - signature will not appear in PDF!")
        
        # Add subcontractor signature (only if contract is signed)
        if subcontractor_signature_data:
            context['subcontractor_signature'] = subcontractor_signature_data
            # Keep 'signature' for backward compatibility
            context['signature'] = subcontractor_signature_data
            _logger.info(f"Added subcontractor signature to context for contract {contract.name}")
        else:
            _logger.debug(f"No subcontractor signature yet for contract {contract.name} (contract not signed)")
            
        # DEBUG: Log signature data details
        if context.get('company_signature'):
            sig = context['company_signature']
            _logger.info(
                f"Company signature in context for {contract.name}: "
                f"has_image_data={bool(sig.get('image_data'))}, "
                f"image_data_length={len(sig.get('image_data', ''))}, "
                f"image_data_preview={sig.get('image_data', '')[:50]}..."
            )
        else:
            _logger.error(f"❌ NO company signature in context for {contract.name}!")
            
        if context.get('subcontractor_signature'):
            sig = context['subcontractor_signature']
            _logger.info(
                f"Subcontractor signature in context for {contract.name}: "
                f"has_image_data={bool(sig.get('image_data'))}, "
                f"image_data_length={len(sig.get('image_data', ''))}, "
                f"signature_date={sig.get('signature_date', 'N/A')}"
            )
        else:
            _logger.debug(f"No subcontractor signature in context for {contract.name} (contract not signed yet)")
            
        _logger.info(
            f"Context prepared for contract {contract.name}: "
            f"has_company_signature={bool(context.get('company_signature'))}, "
            f"has_subcontractor_signature={bool(context.get('subcontractor_signature'))}"
        )
            
        return context

    def _prepare_wizard_context(self, wizard):
        """
        Build preview context based on wizard selections without saving a contract.

        Args:
            wizard (contract.creation.wizard): Wizard record

        Returns:
            dict: Context dictionary compatible with Jinja2 template
        """
        wizard.ensure_one()

        if not wizard.chantier_id:
            _logger.warning("No chantier selected in wizard for preview")
            raise UserError(_(
                "❌ Chantier manquant\n\n"
                "Veuillez sélectionner un chantier pour afficher l'aperçu du contrat."
            ))
        if not wizard.subcontractor_id:
            _logger.warning("No subcontractor selected in wizard for preview")
            raise UserError(_(
                "❌ Sous-traitant manquant\n\n"
                "Veuillez sélectionner un sous-traitant pour afficher l'aperçu du contrat."
            ))
        if not wizard.lot_ids:
            _logger.warning("No lots selected in wizard for preview")
            raise UserError(_(
                "❌ Lots manquants\n\n"
                "Veuillez sélectionner au moins un lot pour afficher l'aperçu du contrat."
            ))

        chantier = wizard.chantier_id
        subcontractor = wizard.subcontractor_id
        currency = chantier.currency_id or wizard.env.company.currency_id

        purchase_orders = self._get_purchase_orders_for_preview(wizard)
        amount_ht = sum(purchase_orders.mapped('amount_untaxed'))
        amount_tva = sum(purchase_orders.mapped('amount_tax'))
        amount_ttc = sum(purchase_orders.mapped('amount_total'))
        retention_rate = wizard.retention_rate or 0.0
        retention_amount = amount_ttc * (retention_rate / 100.0)

        preview_reference = chantier.reference or chantier.name or _('Draft Contract')
        contract_date = wizard.contract_date or fields.Date.context_today(wizard)

        contract_data = {
            'name': _("Preview - %s") % preview_reference,
            'date': self._format_date_value(contract_date),
            'start_date': self._format_date_value(wizard.start_date),
            'end_date': self._format_date_value(wizard.end_date),
            'total_amount_ht': self._format_currency(amount_ht, currency),
            'total_amount_tva': self._format_currency(amount_tva, currency),
            'total_amount_ttc': self._format_currency(amount_ttc, currency),
            'retention_amount': self._format_currency(retention_amount, currency),
            'retention_rate': f"{retention_rate:.1f}",
        }

        chantier_data = {
            'name': chantier.name or '',
            'reference': chantier.reference or '',
            'client': chantier.client.name if chantier.client else '',
            'address': chantier.address or '',
            'city': chantier.city or '',
            'postal_code': chantier.zip_code or '',
        }

        subcontractor_data = {
            'name': subcontractor.name or '',
            'siret': subcontractor.company_registry or '',
            'email': subcontractor.email or '',
            'phone': subcontractor.phone or '',
            'mobile': subcontractor.mobile or '',
            'address': self._format_address(subcontractor),
            'urssaf_code': getattr(subcontractor, 'urssaf_code', '') or '',
        }

        lots_data = []
        for lot in wizard.lot_ids:
            lot_amount = self._calculate_lot_amount_for_partner(lot, subcontractor)
            lots_data.append({
                'name': lot.name or '',
                'description': lot.description or '',
                'amount': self._format_currency(lot_amount, currency),
            })

        pos_data = []
        for po in purchase_orders:
            po_currency = po.currency_id or currency
            pos_data.append({
                'name': po.name or '',
                'date': self._format_date_value(po.date_order),
                'amount': self._format_currency(po.amount_total, po_currency),
            })

        # Company data
        company = wizard.env.company
        company_data = {
            'name': company.name or '',
            'siret': company.company_registry or '',
            'address': self._format_address(company),
            'email': company.email or '',
            'phone': company.phone or '',
        }

        return {
            'contract': contract_data,
            'chantier': chantier_data,
            'subcontractor': subcontractor_data,
            'lots': lots_data,
            'purchase_orders': pos_data,
            'deliverables': [],
            'company': company_data,
        }

    # ============================================================
    # FORMATTING HELPERS
    # ============================================================

    def _format_currency(self, amount, currency):
        """
        Format currency amount for display

        Args:
            amount (float): Amount to format
            currency: res.currency record

        Returns:
            str: Formatted amount (e.g., "1,234.56 €")
        """
        if not amount:
            return "0.00 €"

        # Format with thousands separator
        formatted = f"{amount:,.2f}"

        # Add currency symbol
        symbol = currency.symbol if currency else '€'

        return f"{formatted} {symbol}"

    def _format_date_value(self, date_value):
        """
        Format date/datetime/str to dd/mm/YYYY.
        """
        if not date_value:
            return ''

        if hasattr(date_value, 'strftime'):
            return date_value.strftime('%d/%m/%Y')

        try:
            parsed = fields.Date.from_string(date_value)
            return parsed.strftime('%d/%m/%Y') if parsed else ''
        except Exception:
            return str(date_value)

    def _format_address(self, partner):
        """
        Format partner address as single line

        Args:
            partner: res.partner record

        Returns:
            str: Formatted address
        """
        parts = []

        if partner.street:
            parts.append(partner.street)
        if partner.street2:
            parts.append(partner.street2)
        if partner.zip:
            parts.append(partner.zip)
        if partner.city:
            parts.append(partner.city)
        if partner.country_id:
            parts.append(partner.country_id.name)

        return ', '.join(parts)

    def _calculate_lot_amount(self, contract, lot):
        """
        Calculate total amount for a lot for specific subcontractor

        Args:
            contract: construction.contract record
            lot: construction.lot record

        Returns:
            float: Total amount
        """
        return self._calculate_lot_amount_for_partner(lot, contract.subcontractor_id)

    def _calculate_lot_amount_for_partner(self, lot, partner):
        """
        Calculate lot amount for a given partner using purchase order lines.
        """
        if not lot or not partner:
            return 0.0

        lines = self.env['purchase.order.line'].search([
            ('lot_id', '=', lot.id),
            ('order_id.partner_id', '=', partner.id),
            ('order_id.state', 'in', ['purchase', 'done']),
        ])
        return sum(lines.mapped('price_total'))

    # ============================================================
    # HTML ASSEMBLY
    # ============================================================

    def _assemble_html_document(self, rendered_html, css):
        """
        Assemble complete HTML document with CSS

        Args:
            rendered_html (str): Rendered body HTML
            css (str): CSS styles

        Returns:
            str: Complete HTML document
        """
        return f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Contract Document</title>
    <style>
        /* Reset and base styles */
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Arial', 'Helvetica', sans-serif;
            font-size: 11pt;
            line-height: 1.6;
            color: #333;
        }}

        /* Table styles */
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }}

        th, td {{
            padding: 8px 12px;
            text-align: left;
            border: 1px solid #ddd;
        }}

        th {{
            background-color: #f5f5f5;
            font-weight: bold;
        }}

        /* Contract variable highlighting */
        .contract-var {{
            display: inline;
            font-weight: inherit;
        }}

        /* Page break for printing */
        @media print {{
            .page-break {{
                page-break-before: always;
            }}
        }}

        /* Custom template CSS */
        {css}
    </style>
</head>
<body>
    {rendered_html}
</body>
</html>"""

    def _render_with_context(self, template_html, template_css, context):
        """
        Render template HTML with provided context and assemble final document.
        """
        # DEBUG: Log context keys before rendering
        _logger.debug(f"Rendering template with context keys: {list(context.keys())}")
        if context.get('company_signature'):
            sig = context['company_signature']
            _logger.info(f"✓ Company signature in context: image_data_length={len(sig.get('image_data', ''))}")
        else:
            _logger.error("❌ NO company signature in context!")
        if context.get('subcontractor_signature'):
            sig = context['subcontractor_signature']
            _logger.info(f"✓ Subcontractor signature in context: image_data_length={len(sig.get('image_data', ''))}")
        else:
            _logger.debug("No subcontractor signature in context (contract may not be signed yet)")
        
        env = SandboxedEnvironment(autoescape=True)
        template = env.from_string(template_html)
        rendered_html = template.render(**context)
        
        # DEBUG: Check if rendered HTML contains signature data
        if 'company_signature' in template_html.lower():
            if 'data:image/png;base64' in rendered_html:
                _logger.info("✓ Company signature image found in rendered HTML")
            else:
                _logger.error("❌ Company signature image NOT found in rendered HTML despite being in template!")
        if 'subcontractor_signature' in template_html.lower():
            if 'data:image/png;base64' in rendered_html:
                _logger.info("✓ Subcontractor signature image found in rendered HTML")
            else:
                _logger.error("❌ Subcontractor signature image NOT found in rendered HTML despite being in template!")
        
        return self._assemble_html_document(rendered_html, template_css)

    def _get_purchase_orders_for_preview(self, wizard):
        """
        Fetch purchase orders matching wizard selections for preview totals.
        """
        domain = [
            ('partner_id', '=', wizard.subcontractor_id.id),
            ('state', 'in', ['purchase', 'done']),
        ]

        if wizard.chantier_id:
            domain.append(('chantier_id', '=', wizard.chantier_id.id))

        if wizard.lot_ids:
            domain.append(('lot_ids', 'in', wizard.lot_ids.ids))

        return self.env['purchase.order'].search(domain)
