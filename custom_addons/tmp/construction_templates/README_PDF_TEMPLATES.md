# BLG Groupe PDF Templates - Implementation Guide

## Overview

This implementation provides a complete set of PDF templates with BLG Groupe branding for all document types in the BTPVision ERP system.

## Implemented Templates

### 1. Contract Template (Contrat de Sous-Traitance)
**File:** `reports/contract_blg_template.xml`

**Features:**
- Full BLG branding with terre cuite (#A0604F) header
- Beige (#F5E6D8) content sections
- Comprehensive contract structure with:
  - Party information (Entrepreneur Principal & Sous-Traitant)
  - Contract object and site details
  - Lots table with styling
  - Financial summary with totals
  - Articles (Objet, Durée, Prix, Obligations, Assurances)
  - Dual signature zones (company & subcontractor)
- Professional footer with legal mentions

**Report Action:** `action_report_contract_blg`

### 2. Invoice Template (Facture)
**File:** `reports/invoice_blg_template.xml`

**Features:**
- Inherits from Odoo's native `account.report_invoice_document`
- BLG color scheme applied to:
  - Headers (terre cuite background)
  - Table headers (terre cuite)
  - Address blocks (beige background)
  - Total section (beige with terre cuite border)
- Alternating row colors for better readability
- Professional footer with company information

**Report Action:** `action_report_invoice_blg`

### 3. Quotation Template (Devis)
**File:** `reports/quote_blg_template.xml`

**Features:**
- Inherits from Odoo's native `sale.report_saleorder_document`
- BLG branding throughout
- Validity date info box
- Client signature zone
- Professional styling for quotes and sales orders

**Report Action:** `action_report_quote_blg`

### 4. Purchase Order Template (Bon de Commande)
**File:** `reports/purchase_order_blg_template.xml`

**Features:**
- Inherits from Odoo's native `purchase.report_purchaseorder_document`
- Status badges (Draft, Sent, Confirmed, Cancelled)
- Order information box with dates
- Delivery address section
- Contact information in footer

**Report Action:** `action_report_purchase_order_blg`

## Default Templates Configuration

**File:** `data/default_templates.xml`

Pre-configured templates for the GrapesJS editor system:

1. **Contract Template** (`BLG_CONTRACT_DEFAULT`)
   - Marked as active and default
   - Includes 2 signature zones (company & subcontractor)
   - Full HTML/CSS content for editor

2. **Invoice Template** (`BLG_INVOICE_DEFAULT`)
   - Marked as active and default
   - Professional invoice layout

3. **Quote Template** (`BLG_QUOTE_DEFAULT`)
   - Marked as active and default
   - Includes client signature zone

4. **Purchase Order Template** (`BLG_PURCHASE_DEFAULT`)
   - Marked as active and default
   - Professional purchase order layout

## BLG Groupe Color Palette

```css
Primary (Terre Cuite): #A0604F
Secondary (Beige Clair): #F5E6D8
Text: #000000
Success: #28A745
Warning: #FFC107
Danger: #DC3545
Info: #17A2B8
```

## Signature Zones

All contract and quote templates include pre-configured signature zones:

- **Position:** Percentage-based (responsive)
- **Styling:** Dashed terre cuite border with light background
- **Types:** Company, Subcontractor, Client
- **Dimensions:** Configurable width/height

## Usage

### Generating Reports

From Python code:
```python
# Contract
report = self.env.ref('construction_templates.action_report_contract_blg')
pdf_content, _ = report._render_qweb_pdf([contract.id])

# Invoice
report = self.env.ref('construction_templates.action_report_invoice_blg')
pdf_content, _ = report._render_qweb_pdf([invoice.id])

# Quote
report = self.env.ref('construction_templates.action_report_quote_blg')
pdf_content, _ = report._render_qweb_pdf([quote.id])

# Purchase Order
report = self.env.ref('construction_templates.action_report_purchase_order_blg')
pdf_content, _ = report._render_qweb_pdf([purchase.id])
```

### From UI

All reports are available in the "Print" menu of their respective models:
- Construction Contract → Print → Contrat BLG Groupe
- Account Move (Invoice) → Print → Facture BLG Groupe
- Sale Order → Print → Devis BLG Groupe
- Purchase Order → Print → Bon de Commande BLG Groupe

## Dependencies

The module requires:
- `base`
- `web`
- `mail`
- `construction_contract`
- `account` (for invoices)
- `sale` (for quotes)
- `purchase` (for purchase orders)

## File Structure

```
construction_templates/
├── reports/
│   ├── contract_blg_template.xml
│   ├── invoice_blg_template.xml
│   ├── quote_blg_template.xml
│   └── purchase_order_blg_template.xml
├── data/
│   └── default_templates.xml
└── __manifest__.py
```

## Customization

### Modifying Colors

Edit the inline styles in each template file or add custom CSS in the `<style>` sections.

### Adding New Sections

For contract templates, add new sections in the `.blg-content` div:

```xml
<div class="blg-section">
    <div class="blg-section-title">New Section Title</div>
    <p>Section content...</p>
</div>
```

### Signature Zones

Modify signature zone positions in `data/default_templates.xml`:

```xml
<record id="signature_zone_id" model="construction.signature.zone">
    <field name="position_x">10</field>  <!-- % from left -->
    <field name="position_y">75</field>  <!-- % from top -->
    <field name="width">200</field>      <!-- pixels -->
    <field name="height">100</field>     <!-- pixels -->
</record>
```

## Testing

To test the templates:

1. Install the module: `odoo-bin -u construction_templates`
2. Create a test contract/invoice/quote/purchase order
3. Click "Print" and select the BLG template
4. Verify the PDF output matches BLG branding

## Compliance

All templates follow:
- BLG Groupe visual identity guidelines
- French legal requirements for business documents
- eIDAS regulation for electronic signatures
- Odoo QWeb reporting best practices

## Support

For issues or customization requests, contact the BTPVision development team.
