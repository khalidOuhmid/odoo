# Email → Chantier Automation

Emails sent to `appel-doffre@blggroupe.com` automatically create a `construction.chantier` record.

## How It Works

1. **Mail alias** — `mail.alias` record (`id=mail_alias_chantier`, `alias_name=appel-doffre`) in `construction_core/data/mail_config.xml` routes incoming emails to the `construction.chantier` model.

2. **`message_process` hook** — `mail_automation.py` extends `mail.thread.message_process` to detect construction-project emails via `_is_construction_project_email()`. Detection criteria (any match):
   - Recipient (`To`/`Cc`) contains `appel-doffre@blggroupe.com`
   - Subject contains keywords: `appel d'offre`, `appel offre`, `nouveau chantier`, `projet construction`, `projet travaux`

3. **`message_new` on `construction.chantier`** — Creates the chantier record with:
   - `name` ← email `Subject`
   - `stage_id` ← `construction_core.stage_reception` (REC stage), with fallback to first stage by sequence
   - `client` ← sender partner (found by email, or created if unknown)
   - `description` ← plain-text body (HTML stripped)
   - `address`, `phone` ← extracted from body via regex helpers in `mail_automation.py`

## Configuration

| Parameter | Key | Default |
|-----------|-----|---------|
| Construction project email | `construction_core.construction_project_email` | `appel-doffre@blggroupe.com` |
| Auto-send confirmation | `construction_core.auto_send_confirmation_email` | `True` |

Both configurable in **Settings → Technical → Parameters → System Parameters**.

## Helper Methods (on `mail.thread`)

| Method | Description |
|--------|-------------|
| `_is_construction_project_email(msg_dict)` | Returns `True` if the email matches construction criteria |
| `_extract_address_from_content(text)` | Extracts zip code, city, address line via regex |
| `_extract_phone_from_content(text)` | Extracts French phone number (0x / +33 formats) |
| `_get_or_create_client(email_from)` | Finds or creates `res.partner` from sender string |
| `_create_construction_project(data)` | Creates the `construction.chantier` record |
| `_handle_construction_project_creation(msg_dict)` | Orchestrates extraction + creation |

## Tests

Integration tests: `construction_core/tests/test_email_to_chantier.py` (6 tests, `TC-ET-01` to `TC-ET-06`)
Unit tests: `construction_core/tests/test_mail_automation.py`

Run:
```bash
./odoo-bin -c debian/odoo.conf --test-enable -d odoo --stop-after-init -i construction_core \
  --test-tags construction_core.TestEmailToChantierViaMessageProcess
```
