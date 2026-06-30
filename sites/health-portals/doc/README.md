# Health Portals

**Category**: Health
**Reviewer**: Farhan
**Number of macros**: 26

## Data Source

Synthetic patient portal data modeled after Epic MyChart.

## Target Macros

navigate_by_dropdown, navigate_by_route, search_by_query, search_by_semantic, search_by_checkbox, filter_by_radio, filter_by_date_range, extract_by_query, extract_by_dropdown, extract_from_table, extract_by_route, compare_by_date_range, submit_by_query, submit_by_route, edit_by_form, export_by_dropdown, upload_by_upload, message_from_free_text, submit_by_form, book_by_form, book_by_date_range, pay_by_form, cancel_by_form, authenticate_by_form, register_by_form, verify_identity_by_code

## Site Description

Lakeport Medical Center Patient Portal is a MyChart-style health portal where patients can manage appointments, view medical records, send messages to providers, track prescriptions, and handle billing.

### Data files in data/
- **users.json** -- Patient and provider profiles (insurance, emergency contacts, allergies)
- **appointments.json** -- Appointment records with status, provider, location
- **medical_records.json** -- Visit records with vitals, lab results, diagnoses
- **messages.json** -- Threaded patient-provider messages
- **prescriptions.json** -- Medication prescriptions with refill tracking
- **billing.json** -- Insurance claims and patient billing

### How macros map to UI
- **navigate_by_dropdown**: Provider/department dropdown in appointment scheduling
- **navigate_by_route**: Click appointment/record/message to view detail
- **search_by_query**: Search medical records and messages
- **search_by_semantic**: Keyword-relevance search on medical records
- **search_by_checkbox**: Filter records by type checkboxes
- **filter_by_radio**: Filter appointments by status radio buttons
- **filter_by_date_range**: Filter appointments/records by date range
- **extract_by_query**: Search records and extract specific info
- **extract_by_dropdown**: Get department-specific appointment stats
- **extract_from_table**: View billing summary table
- **extract_by_route**: View specific record/appointment detail
- **compare_by_date_range**: Compare health metrics across periods
- **submit_by_query**: Search for provider and submit appointment request
- **submit_by_route**: Submit prescription refill request
- **edit_by_form**: Edit appointment details or profile info
- **export_by_dropdown**: Export records/billing as CSV or JSON
- **upload_by_upload**: Upload medical documents
- **message_from_free_text**: Compose and send message to provider
- **submit_by_form**: Submit appointment scheduling form
- **book_by_form**: Book new appointment with provider
- **book_by_date_range**: Book appointment with date range selection
- **pay_by_form**: Pay medical bill online
- **cancel_by_form**: Cancel appointment with reason
- **authenticate_by_form**: Log in with username/password
- **register_by_form**: Create new patient account
- **verify_identity_by_code**: Verify account with 6-digit code

### Temporal dynamics
Appointment dates are fixed historical/future dates. No real-time simulation required.
