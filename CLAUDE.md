# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A **construction site management ERP** built on Odoo 18.0, consisting of 12 custom modules under `custom_addons/`. The system covers the full lifecycle of construction projects: site creation, subcontractor compliance, contract e-signing, procurement, invoicing, and financial forecasting.

## Commands

### Running Odoo (Docker)

```bash
cd docker/
docker-compose up -d              # Start PostgreSQL + Odoo (port 8069)
docker-compose down               # Stop
docker-compose logs -f odoo_web   # Tail Odoo logs
docker-compose restart odoo_web   # Restart Odoo after code changes
```

### Running Odoo (local)

```bash
./odoo-bin -c debian/odoo.conf --dev=all
```

### Running Tests

```bash
# Run all tests for a specific module
./odoo-bin -c debian/odoo.conf --test-enable -d odoo --stop-after-init -i construction_contract

# Run a single test class
./odoo-bin -c debian/odoo.conf --test-enable -d odoo --stop-after-init -i construction_core --test-tags construction_core.TestConstructionChantier

# Run a single test method
./odoo-bin -c debian/odoo.conf --test-enable -d odoo --stop-after-init -i construction_core --test-tags construction_core.TestConstructionChantier.test_stage_transition

# In Docker
docker-compose exec odoo_web odoo --test-enable -d odoo --stop-after-init -i construction_contract
```

### Linting

```bash
flake8 custom_addons/          # Uses setup.cfg config (RST rules enabled)
```

### Installing / Updating a Module

```bash
./odoo-bin -c debian/odoo.conf -d odoo -i construction_core     # Install
./odoo-bin -c debian/odoo.conf -d odoo -u construction_contract  # Update (after model changes)
```

## Module Architecture

`construction_core` is the central module. All functional modules depend on it and extend it via `_inherit`.

```
                        construction_core
                     (Chantier, Lot, Stage, Chapter)
                              │
          ┌───────────────────┼──────────────────────┐
          │                   │                      │
   construction_visit  construction_subcontractor  construction_invoice
   (site visits, ICS,  (compliance docs: KBIS/     (progressive billing
    Waze deep links)    URSSAF/insurance, portal)   30/30/40, stage-triggered)
                               │                      │
                    construction_contract         construction_purchase
                    (GrapesJS editor,             (lot-based PO wizard,
                     WeasyPrint PDFs,              subcontractor grouping)
                     eIDAS e-signature)                 │
                                                   construction_sale
                                                   (Owl SPA quote builder,
                                                    drag-drop, undo/redo)
                                                        │
                                                  construction_finance
                                                  (dashboard 100 sites,
                                                   margin alerts,
                                                   M+1/M+2/M+3 forecasts)
```

Inter-module dependencies (beyond `construction_core`):
- `construction_contract` → `construction_subcontractor`, `construction_purchase`
- `construction_finance` → `construction_sale`, `construction_invoice`, `construction_purchase`

Other modules:
- `construction_all` — meta-installer (installs everything in dependency order)
- `construction_base` — legacy module (pre-consolidation; avoid extending it for new features)
- `web_gantt` — Gantt view widget (third-party, vendored)
- `mail_quoted_reply` — Quoted-reply threading for chatter

### Key Concepts

- **Chantier**: A construction site (`construction.chantier`). Central record that most modules extend via `_inherit`.
- **Lot**: A work package (`construction.lot`) within a Chantier. Drives procurement and invoicing.
- **Chapter** (`construction.chapter`): A major project phase grouping stages (e.g., Avant-Vente, Travaux, Clôture).
- **Stage** (`construction.stage`): Ordered steps within a chapter. Each Chantier has a `stage_id`.
- **Stage machine** (in `chantier.py`): Strict ordered transitions with per-stage validators:
  `REC → VT → DE → DA → FD → T25 → T50 → T75 → T100 → LR → AP → RET → DC` (+ `SS` as terminal/cancelled)
  T25/T50/T75/T100 are progress milestones (25%/50%/75%/100% completion). FD requires signed contract; ARCH/RET chapters block backward transitions.
- **Situation / BillingCycle**: The progressive invoicing concept. `construction.billing.cycle` is the parent record (one per chantier), containing `construction.billing.step` children (each with a `percentage` and a generated `account.move`). Total steps must sum ≤ 100%. Default split: 30/30/40. Each step transitions `draft → invoiced → paid`.
- **Contract lifecycle** (`construction.contract`): `draft → generated → sent → in_progress → signed → archived` (or `cancelled`). Authentication levels: email-only / email+SMS / email+SMS+ID.
- **Compliance docs** on `res.partner`: KBIS (2-month validity), URSSAF, insurance décennale, RIB, CNI. Status per doc: `missing / uploaded / expiring / valid / expired`. Contract creation blocks if required docs are not `valid` or `expiring`.

### Stage Machine — Dev/Test Notes

The `force_stage_wizard` (`construction_core/wizard/force_stage_wizard.py`) allows bypassing stage validators (useful in tests and dev to jump directly to a target stage). The `sans_suite_wizard` moves a chantier to the terminal `SS` state. Both are accessible from the Chantier form.

### How Modules Extend Core

Modules extend `construction.chantier` and `construction.lot` via `_inherit`, adding computed fields and buttons to the core views. For example, `construction_invoice` adds billing steps to chantier, and `construction_contract` adds signature tracking.

### Frontend

- **Owl.js** for reactive components (sale quote builder, contract editor)
- **GrapesJS** embedded in `construction_contract` for visual contract template editing
- Assets declared in `__manifest__.py` under `assets.web.assets_backend`

### PDF Generation

`construction_contract` uses **WeasyPrint** + **Jinja2** for contract PDFs. The Dockerfile installs `libpango`, `libcairo` system deps required by WeasyPrint.

### Portal / Controllers

`construction_contract` and `construction_subcontractor` have HTTP controllers under `controllers/` serving portal pages for external signatories and subcontractors.

### Contract Constants

Module-level enumerations and config live in `construction_contract/config/contract_constants.py` (states, auth methods, token expiry, retention rate defaults) and `config/template_variables.py` (Jinja2 variable registry for contract templates).

## Standard Module Layout

```
module_name/
├── __manifest__.py
├── models/           # ORM models
├── views/            # XML (forms, lists, menus)
├── data/             # Seed data, email templates, cron jobs
├── security/         # ir.model.access.csv + record rules
├── reports/          # QWeb report templates
├── wizards/          # TransientModel + wizard views
├── tests/            # TransactionCase tests (tagged post_install)
├── controllers/      # HTTP routes (portal, JSON-RPC)
├── static/src/       # JS components (Owl), SCSS
└── config/           # Python constants (e.g. contract_constants.py)
```

Note: the folder is named `wizard/` (not `wizards/`) in `construction_core`.

```
```

## Testing Conventions

Tests use `odoo.tests.common.TransactionCase` and are tagged `@tagged('post_install', '-at_install')`. Test files live in `module/tests/test_*.py`; some modules also have `tests/unit/` and `tests/integration/` subdirectories.

All `construction_core` tests inherit from `ConstructionCoreTestBase` (in `tests/common.py`) instead of `TransactionCase` directly to reuse pre-built fixtures: `self.chapter`, `self.stage`, `self.stage2`, `self.client`, `self.subcontractor`, `self.chantier`, `self.category`, `self.lot`. Use `tracking_disable=True` context to silence mail/activity logs in tests.

## Structured Logging

All modules must use the custom logger from `construction_core.utils.logger` instead of `logging.getLogger()`:

```python
from odoo.addons.construction_core.utils.logger import get_logger
_logger = get_logger(__name__)
```

This enforces `%s` lazy formatting (no f-strings in log calls) and emits `[BLG][CATEGORY][EVENT]` prefixes for grep-ability in Odoo.sh logs. Use semantic methods for business events:

| Method | Level | Use case |
|--------|-------|----------|
| `_logger.stage_transition(chantier, from_code, to_code, forced=False)` | INFO/WARNING | Stage transitions |
| `_logger.financial_alert(record, label, amount, percent=None)` | CRITICAL | Negative margins, overbilling |
| `_logger.overbilling(lot, completion_pct)` | CRITICAL | Billing > completion |
| `_logger.compliance_check(record, check_name, passed)` | INFO/WARNING | Document compliance |
| `_logger.business_error(record_or_name, action, exc)` | ERROR | Caught exceptions |
| `_logger.email_event(event, details="")` | INFO | Mail automation events |
| `_logger.wizard_action(wizard_name, action, record=None)` | INFO | Wizard operations |

## Mail Automation

`mail_automation.py` hooks into `MailThread.message_process()` to auto-create chantiers from inbound emails. Triggered when recipient is `appel-doffre@blggroupe.com` OR subject contains keywords like `"appel d'offre"`, `"nouveau chantier"`. The email address is configurable via `ir.config_parameter` key `construction_core.construction_project_email`.

Mail alias: `alias_name=appel-doffre` in `construction_core/data/mail_config.xml`. `message_new` places new chantiers at `stage_reception` (XML ID `construction_core.stage_reception`). See `docs/email_to_chantier.md` for full spec.

## Thread Messages Unification (message_post)

4 models override `message_post` to duplicate messages into the parent chantier thread:
- `purchase.order` (construction_purchase) — prefix `[BdC — {name}]`
- `construction.contract` (construction_contract) — prefix `[Contrat — {name}]`
- `construction.visit` (construction_visit) — prefix `[Visite — {name}]`
- `construction.billing.cycle` (construction_invoice) — prefix `[Facturation — {name}]`

Anti-recursion: guard via `context.get('_posting_to_chantier')`. Chantier messages use `subtype_xmlid='mail.mt_note'` and `mail_notify_author=False`.

## Contract Injectable Variables

`construction_contract/config/contract_constants.py` exports `INJECTABLE_VARIABLES` — a dict mapping Jinja2 template paths (e.g. `"contract.total_amount_ht"`) to French labels. The Owl ContractEditor calls `get_rendered_variables(contract_id)` and `get_injectable_variables_meta()` on `construction.contract` via RPC after sidebar saves to refresh live preview values.

`_get_billing_schedule_html()` on `construction.contract` reads `chantier_id.billing_cycle_id.step_ids` (from `construction_invoice` if installed) and renders an HTML `<table>` for injection; falls back to 30/30/40 split.

## PDF Generation (WeasyPrint)

`construction_contract/services/pdf_generator_service.py` provides:
- `_BLG_PDF_CSS`: class constant with `@page` rules — Page X/Y footer via `counter(page)/counter(pages)`, suppressed cover page footer via `@page :first`
- `_build_cover_page_html(contract)`: BLG-branded cover page (separate HTML → PDF, prepended)
- `_get_annexes_pdf(contract)`: collects annexes (CCTP, planning, POs) into a single PDF
- `merge_contract_bundle(contract, pdf_bytes)`: delegates to `_get_annexes_pdf`, appends to contract PDF

Portal layouts (`signature_portal_templates.xml`, `contract_viewer_templates.xml`) use `portal.frontend_layout` with `no_header`/`no_footer` and an explicit CSS block to suppress any injected Odoo navbar.

## Migrations

When removing Many2many tabs that have data, create a migration script under `module/migrations/VERSION/post-migrate.py`. Use `ON CONFLICT DO NOTHING` for idempotency. See `construction_visit/migrations/18.0.2.2.0/post-migrate.py` for the pattern (migrates `attachment_ids` → typed photo/video/doc fields by MIME type).

## Python Dependencies

Non-standard dependencies required: `weasyprint`, `PyPDF2`, `pandas`, `openpyxl`, `Pillow`, `Jinja2`. These are installed in the Docker image. For local dev, install via `pip install -r requirements.txt` (file is in `custom_addons/`).

## Branches

- `18.0` — main/production branch
- `new` — active development branch
- Feature branches: `livraison`, `refactoring`, `travaux`
