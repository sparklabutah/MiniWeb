import yaml, collections

banking = collections.OrderedDict()

banking["authenticate_by_form"] = [
    "Login page (/login) -> username + password fields with a 'Sign In' button; authenticates the customer and opens the SecureBank dashboard. A separate step-up 2FA gate (/verify-identity) then takes a 6-digit MFA code before sensitive actions. Real credentials for Alex Rivera (primary demo customer): username 'alex_rivera' / password 'secure111', MFA code 482917. Example: Log in as alex_rivera with password secure111, then enter MFA code 482917 on the Verify Identity page.",
]

banking["compute_by_tool"] = [
    "'Transfer Funds' page (/transfer) -> 'Or use slider' amount range input (min $1, max $10,000, step $1) that two-way syncs with the numeric Amount box and a live '$X.XX' display; use it to dial in a transfer amount that satisfies a computed target. Accounts available for Alex Rivera: Checking CHK-847291 ($4,237.82) and Savings SAV-310456 ($18,942.15). Example: Use the slider to move exactly half of the Checking balance ($2,118.91) from CHK-847291 to Savings SAV-310456.",
]

banking["configure_by_form"] = [
    "'Pay Bills' page (/pay-bills), 'Configure a bill' form -> Bill ID (number), Due Date (date picker) and Auto-Pay dropdown (options: 'No change', 'Enable', 'Disable'); reschedules a bill or toggles autopay. Alex Rivera's bills include Mendez Properties rent ($1,650, due 2026-07-01, autopay on) and Puget Sound Energy ($112.47, due 2026-07-08, autopay off). Example: Configure bill #7 (Puget Sound Energy) to change its due date to 2026-07-20 and Enable auto-pay.",
]

banking["create_by_form"] = [
    "'Payees' page (/payees), 'Add Payee' form -> Payee name (required), Account number, and Category text fields; adds a new bill-pay recipient to the customer's payee list. Alex Rivera already has payees like Mendez Properties (Rent), Xfinity Internet (Utility) and Elena Vasquez (Transfer). Example: Add a new payee named 'Seattle City Light' with account number PAY-55012 and category 'Utility'.",
    "'Transfer Funds' page (/transfer) -> transfer form with 'From account' and 'To account' dropdowns (Alex Rivera's options: Checking CHK-847291 $4,237.82, Savings SAV-310456 $18,942.15), an Amount box, optional Memo, and 'Transfer' submit; moves money between the customer's own accounts and writes a debit + credit transaction pair. Example: Transfer $500.00 from Checking CHK-847291 to Savings SAV-310456 with memo 'Rent payment'.",
]

banking["delete_from_table"] = [
    "'Transaction History' page (/transactions) -> 'Delete' button on each transaction row; permanently removes that transaction from the ledger. Rows show date, description, category, amount, type and reference (e.g. 'Amazon.com', $34.97, Shopping, ref TXN000008). Example: On the Transactions page, delete the 'Cascadia Coffee Roasters' $6.75 Dining charge from 2026-06-25.",
    "'Payees' page (/payees) -> 'Delete' button on each payee card/row; removes that saved payee. Alex Rivera's payees include Mendez Properties, Xfinity Internet, Puget Sound Energy, T-Mobile Wireless, Elena Vasquez and James Rivera ('Dad'). Example: Delete the 'James Rivera' payee (nickname 'Dad') from the payee list.",
]

banking["edit_by_form"] = [
    "'Settings' page (/settings) -> profile form with Name, Email, Phone and Address text inputs and 'Save Changes'; updates the customer's contact details. Alex Rivera's current values: email alex.rivera@gmail.com, phone (555) 201-3344, address 1247 Maple Ln, Lakeport, WA 98401. Example: On Settings, change Alex Rivera's phone number to (555) 999-0000 and save.",
    "Credit Card Settings page (/credit-card/settings) -> update form with Email field plus Auto-pay toggle (autopay_enabled true/false) and Freeze-card toggle (card_frozen true/false); manages the credit-card account (Alex Rivera's gold card ending 4821, $12,000 limit, autopay currently on, not frozen). Example: On Credit Card Settings, freeze the card ending 4821 and turn auto-pay off.",
]

banking["export"] = [
    "'Transactions' page (/transactions) -> export controls: a format dropdown ('CSV' or 'JSON') plus an 'Export' button (backed by /api/export, type=transactions or accounts); downloads the customer's transaction ledger. Alex Rivera has 4,220 transactions across categories like Dining, Groceries, Gas and Shopping. Example: Export Alex Rivera's transaction history as a CSV file.",
]

banking["filter_by_date_range"] = [
    "'Transaction History' page (/transactions) -> 'From' and 'To' date fields above the table (inclusive date_from/date_to filters, YYYY-MM-DD); narrows the ledger to a period. Alex Rivera's transactions run through 2026-06-25 (latest month June 2026). Example: Filter transactions to the range 2026-06-01 through 2026-06-30 to see June activity.",
    "Credit Card Transactions page (/credit-card/transactions) -> 'From' and 'To' date filters over the card's purchase history (Alex Rivera's card charges span Jan-Mar 2026). Example: On Credit Card Transactions, filter to 2026-02-01 through 2026-02-28 to review February charges.",
]

banking["filter_by_dropdown"] = [
    "'Transaction History' page (/transactions) -> 'Category' dropdown ('All' plus the customer's real categories: Deposit, Dining, Donations, Entertainment, Gas, Groceries, Health, Insurance, Rent, Shopping, Subscriptions, Transfer, Transport, Travel, Utilities); filters the ledger to one spending category. Example: Filter Alex Rivera's transactions to the 'Groceries' category (e.g. the $87.43 Safeway - Lakeport charge).",
    "'Transaction History' page (/transactions) -> 'Type' dropdown (options 'All', 'Debit', 'Credit'); shows only money out (debit) or money in (credit). Example: Filter to 'Credit' to see deposits like the $4,285.00 'Meridian Systems - Direct Deposit'.",
    "'Transaction History' page (/transactions) -> 'Sort' dropdown (options 'Date (newest)', 'Amount (high to low)', 'Amount (low to high)', 'Description (A-Z)'); reorders the visible rows. Example: Sort transactions by 'Amount (high to low)' to find the largest charge.",
    "Credit Card Transactions page (/credit-card/transactions) -> 'Category' dropdown (dining, groceries, gas, subscriptions, shopping, travel, entertainment, health, insurance, transport, utilities) and a 'Status' dropdown ('All', 'Posted', 'Pending'); filters the card's purchase list. Example: On Credit Card Transactions, filter to category 'subscriptions' to see recurring charges like Netflix ($15.99) and Spotify ($10.99).",
]

banking["navigate_by_route"] = [
    "'Welcome, Alex Rivera' dashboard (/) -> click an account summary card to open its detail page (/account/<id>) showing that account's info and recent transactions. Cards shown: Checking CHK-847291 ($4,237.82) and Savings SAV-310456 ($18,942.15, 4.2% APY). Example: From the dashboard, click the Savings SAV-310456 card to view its account detail.",
    "'Transactions' page (/transactions) -> click a transaction row to drill into its detail; the row lists date, description, category, amount and reference. Example: Open the detail for the 'Shell Gas - Cedar Blvd' $52.18 Gas transaction (ref TXN000005).",
]

banking["pay_by_form"] = [
    "'Pay Bills' page (/pay-bills) -> per-bill 'Pay' form with a source-account dropdown (Alex Rivera's checking/savings, e.g. CHK-847291 $4,237.82) and submit; debits the account, marks the bill paid and posts a 'Bill payment' transaction. Due bills include Xfinity Internet ($79.99, due 2026-07-05). Example: Pay the Xfinity Internet bill of $79.99 from Checking CHK-847291.",
    "'Pay Bills' page (/pay-bills) -> pay form (account dropdown + amount) for a selected bill; use for the largest outstanding bill. Alex Rivera's biggest due bill is Mendez Properties rent at $1,650.00 (due 2026-07-01). Example: Pay the Mendez Properties rent bill ($1,650.00) from Checking.",
    "'Loans' page (/loans) -> 'Make a payment' form with a loan selector, Amount input (defaults to the monthly payment if left blank) and source account; debits the account and reduces the loan balance. Alex Rivera's loans: student loan (balance $12,840.55, monthly $308.72) and auto loan (balance $8,475.33, monthly $413.86). Example: Make the $308.72 monthly payment on the student loan from Checking CHK-847291.",
    "Credit Card Payments page (/credit-card/payments) -> 'Make a payment' form with Amount, payment Method (bank_transfer) and bank name; reduces the card's current balance and logs a confirmation (PMT-YYYYMMDD-###). Alex Rivera's card ending 4821 carries a $2,874.33 balance (minimum $110.00). Example: Make a $500.00 credit-card payment via bank transfer to pay down the card ending 4821.",
]

banking["report_information"] = [
    "'Transaction History' page (/transactions) -> after searching/filtering, the results table reports matching transactions (date, description, category, amount, type, reference) plus the total match count; read values off it. Example: Report how many 'Dining' transactions Alex Rivera has and the amount of the most recent one (Cascadia Coffee Roasters, $6.75).",
    "'Accounts' page (/accounts) -> accounts table with columns account number, type, balance and status (optionally filtered by type checking/savings/credit/loan). Alex Rivera: CHK-847291 checking $4,237.82 (active), SAV-310456 savings $18,942.15 (active). Example: Report the total balance across Alex Rivera's checking and savings accounts.",
    "Account detail page (/account/<id>) -> the account's recent transactions table (up to 30 rows); read individual charges/deposits for that one account. Example: On the CHK-847291 detail page, report the amount of the most recent direct deposit ($4,285.00 from Meridian Systems).",
    "'Transaction History' page (/transactions) -> the main transactions table (30 per page) with a total count of matching rows; read/scan ledger entries. Example: Report the description and amount of Alex Rivera's single largest debit transaction.",
    "'Pay Bills' page (/pay-bills) -> bills table with payee name, amount, due date, status (due/paid), category and auto-pay flag; read upcoming or paid bills. Alex Rivera's due bills: Mendez Properties $1,650, Xfinity Internet $79.99, Puget Sound Energy $112.47, T-Mobile Wireless $85. Example: Report the total dollar amount of Alex Rivera's bills currently marked 'due'.",
    "'Payees' page (/payees) -> payees table/cards with name, nickname, account number and category. Alex Rivera's payees: Mendez Properties ('Rent - Carlos'), Xfinity Internet, Puget Sound Energy, T-Mobile Wireless, Elena Vasquez, James Rivera ('Dad'). Example: Report how many of Alex Rivera's payees are in the 'Utility' category.",
    "Credit Card pages (/credit-card, /credit-card/transactions, /credit-card/payments, /credit-card/rewards, /credit-card/statements) -> tables of card transactions (merchant, amount, category, status), payments (date, amount, confirmation), rewards points by category, and monthly statements (period, charges, closing balance, minimum due). Alex Rivera: gold tier, APR 18.99%, 34,250 rewards points; 2026-03 statement closing balance $2,239.33 (minimum due $90.00). Example: Report Alex Rivera's current credit-card rewards points balance (34,250) and the closing balance on the March 2026 statement.",
    "Account detail page (/account/<id>) -> account info header (number, type, balance, opened date, interest rate) plus transactions; read account-level facts. Example: Report the interest rate on Alex Rivera's savings account SAV-310456 (4.2% / 0.042).",
    "'Transaction History' page (/transactions) -> 'Sort' dropdown ('Amount high to low') combined with the amount column to surface the maximum charge; read the top row after sorting. Example: Sort by amount descending and report Alex Rivera's largest single transaction.",
    "'Transaction History' page (/transactions) -> 'From'/'To' date fields plus the results table let you total activity over a window; read/aggregate the filtered rows. Example: Filter to June 2026 (2026-06-01 to 2026-06-30) and report the number of transactions shown.",
    "'Transfer Funds' page (/transfer) -> the Amount box synced to the range slider (with live $ display) and the source-account balances lets you verify a transfer amount before submitting. Alex Rivera's Checking holds $4,237.82. Example: Set the slider so the transfer amount equals $1,000.00 and report the remaining Checking balance after transferring it.",
    "'Transaction History' page (/transactions) -> each row has a flag/select control marking a transaction for review; after flagging, report which transactions are flagged. Example: Flag the 'Amazon.com' $34.97 charge for review and report its reference number (TXN000008).",
]

banking["search"] = [
    "'Transaction History' page (/transactions) -> 'Search transactions by description, category, or reference...' box (FTS full-text, all keywords must match); returns matching ledger rows. Example: Search Alex Rivera's transactions for 'Safeway' to find the $87.43 grocery charge.",
    "Credit Card Transactions page (/credit-card/transactions) -> search box matching merchant/description on the card's purchases. Example: Search the credit-card transactions for 'Netflix' to find the $15.99 subscription charge.",
    "'Transaction History' page (/transactions) -> keyword search that can be combined with the Category/Type/date/amount filters to pinpoint a transaction. Example: Search 'transfer' and filter Type='Debit' to list outgoing transfers like the $200.00 'Transfer to Elena Vasquez'.",
]

banking["sort_by_form"] = [
    "'Transaction History' page (/transactions) -> 'Sort' dropdown with options 'Date (newest)', 'Amount (high to low)', 'Amount (low to high)' and 'Description (A-Z)'; reorders the ledger. Example: Sort Alex Rivera's transactions by 'Amount (low to high)' to find the smallest charge.",
]

out = {"banking": {k: v for k, v in banking.items()}}
with open("scratchpad/enriched_banking.yaml", "w") as f:
    yaml.safe_dump(out, f, sort_keys=False, allow_unicode=True, width=1000, default_flow_style=False)
print("written")
