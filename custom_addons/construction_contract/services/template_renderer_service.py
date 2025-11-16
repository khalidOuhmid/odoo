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
            raise UserError(_(
                "Jinja2 template engine is not installed.\n\n"
                "Please install it with: pip install jinja2"
            ))

        if not contract.template_id:
            raise UserError(_("No template selected for this contract."))

        try:
            # Step 1: Prepare context data
            context = self._prepare_context(contract)

            # Step 2: Get template HTML and CSS
            template_html = contract.template_id.grapesjs_html or ''
            template_css = contract.template_id.grapesjs_css or ''

            # Step 3 & 4: Render template and assemble HTML document
            full_html = self._render_with_context(template_html, template_css, context)

            _logger.info(f"Template rendered successfully for contract {contract.name}")

            return full_html

        except Exception as e:
            _logger.error(f"Template rendering failed for contract {contract.name}: {e}")
            raise UserError(_(
                "Failed to render template: %s\n\n"
                "Please check the template syntax and variables."
            ) % str(e))

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
            raise UserError(_(
                "Jinja2 template engine is not installed.\n\n"
                "Please install it with: pip install jinja2"
            ))

        if not wizard.template_id:
            raise UserError(_("Please select a contract template to preview."))

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
            raise
        except Exception as e:
            _logger.error("Template preview rendering failed: %s", e)
            raise UserError(_(
                "Failed to render preview: %s\n\n"
                "Please review the template and selected data."
            ) % str(e))

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
            'email': company.email or '',
            'phone': company.phone or '',
        }

        return {
            'contract': contract_data,
            'chantier': chantier_data,
            'subcontractor': subcontractor_data,
            'lots': lots_data,
            'purchase_orders': pos_data,
            'deliverables': deliverables_data,
            'company': company_data,
        }

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
            raise UserError(_("Please select a construction site to preview the contract."))
        if not wizard.subcontractor_id:
            raise UserError(_("Please select a subcontractor to preview the contract."))
        if not wizard.lot_ids:
            raise UserError(_("Please select at least one lot to preview the contract."))

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
        env = SandboxedEnvironment(autoescape=True)
        template = env.from_string(template_html)
        rendered_html = template.render(**context)
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
