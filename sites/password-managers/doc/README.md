# Password Managers

**Category**: Utilities
**Reviewer**: Kenny
**Number of macros**: 21

## Data Source

Synthetic -- all data files (entries.json, vaults.json, users.json, audit_log.json, security_report.json) are pre-generated and stored in DATA_SOURCES_DIR/password-managers/. The routes.py interpreter reads these at runtime without modification.

### Data Format

- `entries.json` -- list of password entries (logins, secure notes, credit cards). Fields: id, vault_id, title, url, username, password, category, notes, created_at, updated_at, last_used, strength, favorite, tags, card_details (optional).
- `vaults.json` -- list of vaults/collections. Fields: id, name, type, color, icon, shared, members (list of {user_id, role}).
- `users.json` -- user profiles. Fields: id, email, display_name, plan, two_factor_enabled, two_factor_codes, two_factor_backup_code, master_password, settings.
- `audit_log.json` -- access and change audit trail. Fields: timestamp, user_id, action, entry_id, entry_title, vault_id, device, ip_address, details.
- `security_report.json` -- security analysis. Fields: overall_score, overall_rating, summary, breach_alerts, password_strength, two_factor_coverage, password_age, vault_health, recommendations.

## Real-World Model

**1Password / LastPass / Bitwarden** -- dark-themed password vault management interface. Key UI elements:
- Dashboard with security score, vault cards, and recently used entries
- Vault detail pages listing entries with category/strength/search filters
- Entry detail pages showing masked credentials, tags, notes, audit history
- Password generator with configurable settings
- Security report with breach alerts, strength analysis, 2FA coverage
- Audit log with action/vault filters
- Login with master password + optional 2FA verification

## Target Macros

navigate_by_semantic, navigate_by_route, search_by_query, filter_by_dropdown, extract_by_semantic, extract_by_code, extract_by_dropdown, extract_from_table, extract_by_route, create_from_free_text, create_by_dropdown, submit_by_query, edit_by_form, delete_from_table, select_by_dropdown, configure_by_dropdown, export_by_dropdown, upload_by_image, share_by_dropdown, authenticate_by_code, verify_identity_by_code

## Temporal Dynamics

Not applicable -- password vaults are user-managed stores. Entries are created, edited, and deleted by user action. No automatic time-varying simulation needed. Audit log entries are timestamped records of past actions.

## Domain-Specific Notes

- Passwords are stored in plaintext in the data file (synthetic demo data, not real secrets)
- The "reveal password" API endpoint simulates the copy-to-clipboard action
- 2FA verification accepts codes listed in the user's two_factor_codes array or their backup code
- Semantic search uses simple keyword overlap scoring over entry titles, URLs, usernames, notes, and tags
- The security report is a pre-computed static analysis, not recalculated on the fly
- Entry sharing records are appended to the entry's "shares" array
