# VaultGuard (`password-managers`)

A password manager in the style of 1Password, LastPass and Bitwarden. Users
browse vaults, search and filter entries, create, edit, delete, import and
export entries, reveal a password with a PIN, generate passwords and review a
security report and audit log.

- URL: `/sites/password-managers/` (simulated domain `vaultguard.security`)
- Data split: training site

## Pages

| Route | Page |
|---|---|
| `/` | My Vault: security score, vault cards, recently used entries, Import button |
| `/vault/<id>` | Vault entries with search, Category and Strength dropdowns, export |
| `/entry/<id>` | Entry detail: masked credentials, Reveal with PIN, tags, notes, audit history, Delete |
| `/new-entry` | New-entry form (vault, category, credentials, URL, notes, tags, icon image) |
| `/entry/<id>/edit` | Edit-entry form |
| `/generator` | Password generator with a length slider and options |
| `/security-report` | Security analysis computed from the user's entries |
| `/audit-log` | Audit trail with action and vault filters |
| `/settings` | Auto-lock, clipboard clear, password length and theme settings |
| `/login` | Email and master-password sign-in |

JSON endpoints under `/api/` cover vaults, entries (search, semantic search,
share, icon upload), audit log, security report, password generation, settings
and export.

## Interactions and macros

- Search entries in a vault: `search`
- Filter by category, strength, action or vault: `filter_by_dropdown`
- Open a vault, an entry or a nav page: `navigate_by_route`
- Create an entry: `create_by_form`; edit it: `edit_by_form`; delete it: `delete_from_table`
- Import a CSV/JSON file or attach an icon image: `upload_file`
- Set generator length or user settings: `configure_by_form`
- Export entries: `export`
- Reveal a password with the PIN, read entry metadata and the audit log: `report_information`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `password-managers`.

## Data

- Tables (`password_managers_*`): `entries`, `vaults`, `audit_log`,
  `security_report`, `users`. Passwords are synthetic plaintext values.
- Login uses `session["user_id"]`, so the global auto-login signs in user 1.
  The login form itself takes an email and master password.
- Revealing a password sends a 6-digit PIN as an instant message from
  "vaultguard-security" in the instant-messaging site; the agent reads it there
  and enters it on the entry page.
- Other sites' `signup` events add a login entry here
  (`app/handlers/password_handler.add_to_vault`).
