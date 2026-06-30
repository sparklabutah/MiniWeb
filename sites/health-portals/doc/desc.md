# Lakeport Medical Center Patient Portal

## Domain
A patient health portal modeled after MyChart (Epic Systems). Patients can view and manage appointments, medical records, prescriptions, messages with providers, and billing. Providers can receive messages and manage patient care.

## Data Sources
- **users.json** - Patient and provider profiles with insurance, emergency contacts, allergies, blood type (4 users: 2 patients, 2 providers)
- **appointments.json** - Appointment records with status, provider, location, check-in/out times (12 entries)
- **medical_records.json** - Visit records with vitals, lab results, diagnoses, prescriptions, follow-up notes (10 entries)
- **messages.json** - Threaded patient-provider messages with categories and read status (15 entries)
- **prescriptions.json** - Medication prescriptions with refill tracking (5 entries)
- **billing.json** - Insurance claims and patient billing with payment status (10 entries)

## Real-World Model
Modeled after **MyChart by Epic Systems** -- the most widely used patient portal in the US. Features appointment scheduling, medical records access, secure messaging, prescription management, and online bill pay.

## Key Features
- Dashboard with upcoming appointments, unread messages, active prescriptions, pending bills
- Appointment management: list, filter, book, reschedule, cancel
- Medical records browser with vitals and lab results
- Secure messaging with threaded conversations and reply
- Prescription list with refill requests
- Billing summary with online payment
- Patient registration with identity verification (6-digit code)
- Document upload capability
- Data export (CSV/JSON)
- Provider directory with department filtering

## Temporal Dynamics
Appointment dates are fixed historical/future dates. No real-time simulation needed -- the portal represents a snapshot of patient data.
