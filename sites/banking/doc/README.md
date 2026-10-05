# SecureBank Online (`banking`)

A retail online-banking portal in the style of Chase, TD or Amex. It covers
deposit accounts, transaction history, transfers, bill pay, payees, loans and a
credit-card section with statements, payments, rewards and disputes.

- URL: `/sites/banking/` (simulated domain `securebank.com`)
- Data split: training site

## Pages

| Route | Page |
|---|---|
| `/` | Dashboard ("Welcome, Alex Rivera") with account cards |
| `/accounts`, `/account/<id>` | Accounts table; account detail with its transactions |
| `/transactions` | Transaction history: search, category/type/date filters, sort, CSV/JSON export, delete and flag per row |
| `/transfer` | Transfer form with from/to accounts, amount field and amount slider |
| `/pay-bills` | Bills table, pay form, due-date and auto-pay configuration |
| `/payees` | Payee list with add and delete |
| `/loans` | Loans with a pay-loan form |
| `/settings` | Profile and notification settings |
| `/credit-card` | Credit-card overview |
| `/credit-card/transactions`, `/credit-card/statements`, `/credit-card/payments`, `/credit-card/rewards`, `/credit-card/settings` | Card transactions (filters, disputes), statements, payments, rewards, autopay settings |
| `/verify-identity` | MFA code check |
| `/login` | Sign-in form |

JSON endpoints under `/api/` mirror these pages (accounts, transactions,
payees, bills, loans, export, credit-card data).

## Interactions and macros

- Sign in: `authenticate_by_form`
- Search transactions or card transactions: `search`
- Filter by category, type or status, or by a From/To range: `filter_by_dropdown`, `filter_by_date_range`
- Sort the transaction history: `sort_by_form`
- Add a payee, make a transfer: `create_by_form`
- Pay a bill, a loan or the card balance: `pay_by_form`
- Set a bill's due date and auto-pay, edit profile or card settings: `configure_by_form`, `edit_by_form`
- Delete transactions or payees, export transactions: `delete_from_table`, `export`
- Set an amount with the transfer slider: `compute_by_tool`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `banking`.

## Data

- Tables: `banking_users`, `banking_accounts`, `banking_transactions`,
  `banking_payees`, `banking_bills`, `banking_loans`, `banking_cc_users`,
  `banking_cc_transactions`, `banking_cc_statements`, `banking_cc_payments`.
- Login reads `session["user_id"]` (via `helpers.auth`), so the global
  auto-login signs the user in as user 1 (Alex Rivera).
- Account numbers are masked until the session reveals them through
  "Reveal account numbers" (`POST /accounts/reveal`). That goes through the
  shared 2FA flow: a code is emailed to WebMail and entered at `/verify-payment`
  (skipped when `session["_disable_2fa"]` is set).
- A successful login emits a `signup` event, which saves the credentials to the
  password manager and sends a welcome email.
- Banking is the main target of cross-site events: purchases, payments and
  trades on other sites add debit rows to `banking_transactions`
  (`app/handlers/banking_handler.py`), and card charges from other sites are
  validated against `banking_cc_users` (`app/bank_charges.py`).
