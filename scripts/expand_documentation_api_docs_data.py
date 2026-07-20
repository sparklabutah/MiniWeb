"""Expand documentation-api-docs (MeridianFlow Docs) base data.

The docs site ships with 18 docs / 18 search-index rows / 5 users. This adds a
realistic full documentation tree for the MeridianFlow workflow-automation
platform: more Getting Started / Workflows / Tasks / Webhooks / SDK guides,
per-release Changelog entries (v1.0.0 .. v2.8.0), a per-endpoint API Reference
section, plus Guides, Integrations, Security and Troubleshooting sections, a
matching 1:1 search_index row for every new doc, and additional portal users.

Scale note: routes.py renders the ENTIRE docs table in the sidebar of every
page (and again on the index "All Pages" list), unpaginated. That caps the docs
table at <~500 rows, and search_index mirrors docs 1:1, so the defensible site
ceiling is ~1000 rows total, not 5000.

Insert-only; deterministic (seeded); inserted ids recorded under
data/backups/documentation-api-docs-expansion-2026-07-20/ for rollback.
Rebuilds the external-content FTS tables after inserting.

Usage: python scripts/expand_documentation_api_docs_data.py [--dry-run]
"""
import datetime
import json
import random
import sqlite3
import string
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "trimmed_miniweb.db"
rng = random.Random(20260720)

API_BASE = "https://api.meridiansystems.com"
MAX_DOCS_TOTAL = 480  # sidebar renders every doc on every page

# ---------------------------------------------------------------------------
# Shared content helpers
# ---------------------------------------------------------------------------

BEST_PRACTICES = [
    "Use `mf_test_*` API keys while iterating in the sandbox.",
    "Prefer webhooks over polling to track state changes.",
    "Keep workflow names short and descriptive; see Naming Conventions.",
    "Restrict API key scopes to the minimum your integration needs.",
    "Retry failed requests with exponential backoff and respect `Retry-After`.",
    "Pin your integration to an explicit API version header.",
    "Log the `request_id` from every response for easier support escalation.",
    "Batch bulk operations instead of issuing one request per item.",
    "Use idempotency keys on any request you might retry.",
    "Review the audit log after making bulk changes.",
]

NOTES = [
    "This feature is available on all plans.",
    "This feature requires a Pro or Enterprise plan.",
    "Enterprise customers can request higher limits through their account manager.",
    "Changes take effect immediately for new executions; running executions are not affected.",
    "All timestamps are returned in UTC using ISO 8601 format.",
]


def kw_from(title, tags, extra=()):
    """Build a search_index keyword list from title words + tags + extras."""
    words = [w.strip(".,()&").lower() for w in title.split() if len(w) > 3]
    kws = []
    for w in words + [t.replace("-", " ") for t in tags] + list(extra):
        wl = w.lower()
        if wl and wl not in kws:
            kws.append(wl)
    return kws[:12]


def guide_content(title, intro, section, code=None, bullets=None):
    parts = [intro, "\n## Overview\n"]
    parts.append(
        f"{title} is part of the MeridianFlow {section.lower()} toolset. "
        "It is available in the dashboard and through the REST API, and behaves "
        "identically in sandbox and production environments."
    )
    if code:
        parts.append("\n## Example\n")
        parts.append(code)
    if bullets:
        parts.append("\n## Key points\n")
        parts.append("\n".join(f"- {b}" for b in bullets))
    parts.append("\n## Best practices\n")
    parts.append("\n".join(f"- {b}" for b in rng.sample(BEST_PRACTICES, 4)))
    parts.append("\n> " + rng.choice(NOTES))
    return "\n".join(parts)


def curl_block(method, path, body=None):
    lines = [f"```bash", f"curl -X {method} {API_BASE}{path} \\",
             '  -H "Authorization: Bearer YOUR_TOKEN"']
    if body is not None:
        lines[-1] += " \\"
        lines.append('  -H "Content-Type: application/json" \\')
        lines.append(f"  -d '{json.dumps(body)}'")
    lines.append("```")
    return "\n".join(lines)


def rand_date(lo="2024-06-01", hi="2026-06-24"):
    a = datetime.date.fromisoformat(lo).toordinal()
    b = datetime.date.fromisoformat(hi).toordinal()
    return datetime.date.fromordinal(rng.randint(a, b)).isoformat()


# ---------------------------------------------------------------------------
# Topic definitions per section
# ---------------------------------------------------------------------------

GETTING_STARTED = [
    ("pagination", "Pagination",
     "All MeridianFlow list endpoints are cursor-paginated. Use the `limit` and `starting_after` parameters to walk large result sets.",
     ["pagination", "cursor", "limit", "list"]),
    ("idempotency", "Idempotency Keys",
     "Pass an `Idempotency-Key` header on any POST request to safely retry without creating duplicate objects. Keys are stored for 24 hours.",
     ["idempotency", "retries", "duplicate", "safety"]),
    ("api-versioning", "API Versioning",
     "The MeridianFlow API is versioned through the URL (`/api/v2/`) and the optional `MF-Version` header for dated behavior changes.",
     ["versioning", "v2", "deprecation", "mf-version"]),
    ("environments", "Environments",
     "Every MeridianFlow account includes separate production and sandbox environments with independent data, API keys, and webhooks.",
     ["environments", "sandbox", "production", "api-keys"]),
    ("sandbox-mode", "Sandbox Mode",
     "Sandbox mode lets you build and execute workflows against test data using `mf_test_*` keys. Nothing in sandbox affects production.",
     ["sandbox", "testing", "mf_test", "getting-started"]),
    ("http-conventions", "HTTP Conventions",
     "The API follows standard REST conventions: JSON bodies, snake_case fields, standard status codes, and `request_id` on every response.",
     ["http", "rest", "conventions", "status-codes"]),
    ("glossary", "Glossary",
     "Definitions for the core MeridianFlow concepts: workflows, tasks, approval chains, routing rules, triggers, executions, and connections.",
     ["glossary", "concepts", "definitions", "terminology"]),
    ("postman-collection", "Postman Collection",
     "Download the official MeridianFlow Postman collection to explore every endpoint with pre-configured auth and example bodies.",
     ["postman", "collection", "tooling", "explore"]),
]

WORKFLOWS = [
    ("workflows-triggers", "Workflow Triggers", "Triggers determine when a workflow starts: manually, on a schedule, from an inbound event, or via the API."),
    ("workflows-scheduled-triggers", "Scheduled Triggers", "Run workflows on a fixed schedule using cron expressions evaluated in your workspace timezone."),
    ("workflows-event-triggers", "Event-Based Triggers", "Start workflows automatically when records change, forms are submitted, or webhook events arrive from connected apps."),
    ("workflows-conditions", "Conditional Logic", "Branch workflow execution with condition steps that evaluate variables, form answers, and task outcomes."),
    ("workflows-branching", "Parallel Branches", "Split a workflow into parallel branches that execute concurrently and join before downstream steps."),
    ("workflows-loops", "Loops and Iteration", "Iterate over lists — line items, approvers, attachments — with for-each steps and per-item concurrency limits."),
    ("workflows-variables", "Workflow Variables", "Variables carry data between steps. Set them at execution time, from step outputs, or from form submissions."),
    ("workflows-templates", "Workflow Templates", "Start from a template in the gallery — onboarding, procurement, incident response — and customize it for your team."),
    ("workflows-approval-chains", "Approval Chains", "Approval chains route a request through one or more approvers in sequence, with quorum and unanimous modes."),
    ("workflows-multi-step-approvals", "Multi-Step Approvals", "Combine several approval steps with conditions to build tiered sign-off, e.g. manager then finance above $10,000."),
    ("workflows-delegation", "Approval Delegation", "Approvers can delegate pending approvals to a colleague, permanently or for a date range (out-of-office)."),
    ("workflows-escalations", "Escalation Rules", "Escalate overdue approvals and tasks to a fallback assignee or manager after a configurable timeout."),
    ("workflows-sla-policies", "SLA Policies", "Attach SLA policies to workflows to track response and resolution targets, with warning and breach events."),
    ("workflows-error-handling", "Error Handling", "Configure per-step error behavior: fail the execution, continue, or route to a compensation branch."),
    ("workflows-retries", "Retry Policies", "Automatic retries for failed action steps with exponential backoff, jitter, and a configurable attempt cap."),
    ("workflows-concurrency", "Concurrency Controls", "Limit how many executions of a workflow run at once, and serialize executions that share a key."),
    ("workflows-versioning", "Workflow Versioning", "Every published change creates a new immutable version. Running executions always finish on the version they started with."),
    ("workflows-draft-publish", "Drafts and Publishing", "Edit workflows as drafts, preview changes, then publish. Only published versions can be executed."),
    ("workflows-import-export", "Import and Export", "Export workflows as JSON for backup or promotion between environments, and import them via API or dashboard."),
    ("workflows-cloning", "Cloning Workflows", "Clone an existing workflow — including steps, variables, and routing rules — as a starting point for a new process."),
    ("workflows-archiving", "Archiving Workflows", "Archive workflows you no longer run. Archived workflows keep their execution history but cannot be triggered."),
    ("workflows-permissions", "Workflow Permissions", "Control who can view, edit, execute, and manage each workflow with role- and team-based permissions."),
    ("workflows-analytics", "Workflow Analytics", "Built-in analytics for execution volume, duration percentiles, approval latency, and SLA compliance."),
    ("workflows-testing", "Testing Workflows", "Test-execute draft workflows with sample variables and inspect each step's input and output payloads."),
    ("workflows-limits", "Workflow Limits", "Platform limits per plan: steps per workflow, executions per day, payload sizes, and variable counts."),
    ("workflows-naming-conventions", "Naming Conventions", "Recommended conventions for naming workflows, steps, and variables so large workspaces stay searchable."),
]

TASKS = [
    ("tasks-routing-rules", "Task Routing Rules", "Routing rules decide which queue or assignee receives a task, based on variables, form answers, and workload."),
    ("tasks-assignment-strategies", "Assignment Strategies", "Choose how queued tasks are assigned: manual claim, round-robin, load-based, or skill-based routing."),
    ("tasks-round-robin", "Round-Robin Assignment", "Distribute tasks evenly across a team by rotating through eligible members in order."),
    ("tasks-load-based-assignment", "Load-Based Assignment", "Assign each task to the eligible member with the fewest open tasks, with configurable capacity ceilings."),
    ("tasks-skill-based-routing", "Skill-Based Routing", "Tag team members with skills and route tasks to members whose skills match the task's requirements."),
    ("tasks-due-dates", "Due Dates", "Set static or computed due dates on tasks, with business-hours calendars and holiday schedules."),
    ("tasks-reminders", "Reminders", "Automatic reminder notifications before and after a task's due date, via email, Slack, or in-app."),
    ("tasks-priorities", "Task Priorities", "Four priority levels — low, normal, high, urgent — that affect queue ordering and notification behavior."),
    ("tasks-custom-fields", "Custom Fields", "Add typed custom fields (text, number, date, select, user) to tasks and reference them in routing rules."),
    ("tasks-forms", "Task Forms", "Attach forms to tasks so assignees capture structured data; answers become workflow variables."),
    ("tasks-attachments", "Attachments", "Upload files to tasks via the dashboard or API. Attachments are virus-scanned and stored encrypted."),
    ("tasks-subtasks", "Subtasks", "Break a task into subtasks with independent assignees; the parent completes when all subtasks do."),
    ("tasks-dependencies", "Task Dependencies", "Declare that a task cannot start until other tasks complete, across branches of the same execution."),
    ("tasks-bulk-operations", "Bulk Operations", "Reassign, complete, or update up to 500 tasks in one API call with the bulk endpoints."),
    ("tasks-lifecycle", "Task Lifecycle", "Task states and transitions: pending, assigned, in_progress, blocked, completed, cancelled, expired."),
    ("tasks-reassignment", "Reassigning Tasks", "Reassign a task to another user or queue, preserving history and notifying both parties."),
    ("tasks-escalation", "Task Escalation", "Escalate overdue tasks to a fallback assignee, a manager, or an escalation queue."),
    ("tasks-watchers", "Watchers", "Add watchers to a task to receive its notifications without being the assignee."),
    ("tasks-labels", "Task Labels", "Free-form labels for filtering and reporting, applied manually or by routing rules."),
    ("tasks-saved-filters", "Saved Filters", "Save frequently used task filters — by queue, assignee, label, due date — and share them with your team."),
    ("tasks-search", "Searching Tasks", "Full-text search across task titles, descriptions, comments, and form answers."),
    ("tasks-exports", "Exporting Tasks", "Export filtered task lists to CSV or JSON, synchronously up to 10,000 rows or via async export jobs."),
    ("tasks-templates", "Task Templates", "Reusable task templates with pre-filled fields, forms, and checklists."),
    ("tasks-audit-history", "Task Audit History", "Every state change, reassignment, and field edit is recorded in the task's immutable audit history."),
]

WEBHOOK_EVENTS = [
    ("workflow.created", "Sent when a workflow is created via the dashboard or API."),
    ("workflow.published", "Sent when a draft workflow version is published."),
    ("workflow.execution.started", "Sent when a workflow execution starts."),
    ("workflow.execution.completed", "Sent when a workflow execution finishes successfully."),
    ("workflow.execution.failed", "Sent when a workflow execution fails after exhausting retries."),
    ("task.created", "Sent when a task is created by a workflow step."),
    ("task.assigned", "Sent when a task is assigned to a user or claimed from a queue."),
    ("task.completed", "Sent when a task is completed."),
    ("task.overdue", "Sent when a task passes its due date without completion."),
    ("approval.requested", "Sent when an approval step assigns an approver."),
    ("approval.decided", "Sent when an approver approves or rejects a request."),
]

WEBHOOK_GUIDES = [
    ("webhooks-verify-signatures", "Verifying Signatures", "Every webhook delivery is signed with an HMAC-SHA256 signature in the `MF-Signature` header. Always verify it before trusting the payload."),
    ("webhooks-retries-delivery", "Retries and Delivery", "Failed deliveries are retried 5 times with exponential backoff over roughly 30 minutes; after that the delivery is marked dead."),
    ("webhooks-debugging", "Debugging Deliveries", "Inspect recent deliveries, response codes, and payloads in the dashboard, and replay any delivery from the last 30 days."),
    ("webhooks-ip-allowlist", "IP Allowlist", "Webhook deliveries originate from a small set of stable egress IPs that you can allowlist in your firewall."),
    ("webhooks-payload-versioning", "Payload Versioning", "Webhook payload schemas are versioned with the API. Pin a payload version per endpoint to upgrade on your own schedule."),
    ("webhooks-testing-locally", "Testing Locally", "Use the CLI's `mflow listen` command to forward webhook events to a local port during development."),
    ("webhooks-consumer-idempotency", "Idempotent Consumers", "Deliveries can arrive more than once. Deduplicate on the `delivery_id` field to keep your consumer idempotent."),
]

SDKS = [
    ("sdk-go", "Go SDK", "go", 'go get github.com/meridianflow/meridianflow-go', 'client := meridianflow.NewClient("mf_live_...")\nwf, err := client.Workflows.Create(ctx, &meridianflow.WorkflowParams{Name: "Invoice Approval"})'),
    ("sdk-ruby", "Ruby SDK", "ruby", 'gem install meridianflow', 'client = MeridianFlow::Client.new(api_key: "mf_live_...")\nworkflow = client.workflows.create(name: "Invoice Approval")'),
    ("sdk-java", "Java SDK", "java", 'implementation "com.meridianflow:meridianflow-java:2.8.0"', 'MeridianFlowClient client = MeridianFlowClient.builder().apiKey("mf_live_...").build();\nWorkflow wf = client.workflows().create(WorkflowCreateParams.builder().name("Invoice Approval").build());'),
    ("sdk-dotnet", ".NET SDK", "csharp", 'dotnet add package MeridianFlow', 'var client = new MeridianFlowClient("mf_live_...");\nvar workflow = await client.Workflows.CreateAsync(new WorkflowCreateOptions { Name = "Invoice Approval" });'),
    ("sdk-php", "PHP SDK", "php", 'composer require meridianflow/meridianflow-php', '$client = new \\MeridianFlow\\Client("mf_live_...");\n$workflow = $client->workflows->create(["name" => "Invoice Approval"]);'),
    ("sdk-cli", "Command-Line Interface", "bash", 'brew install meridianflow/tap/mflow', 'mflow login\nmflow workflows list --limit 20\nmflow workflows execute wf_abc123 --var employee_name="Jane Doe"'),
    ("sdk-python-async", "Python SDK: Async Usage", "python", 'pip install meridianflow', 'from meridianflow import AsyncMeridianFlow\n\nclient = AsyncMeridianFlow(api_key="mf_live_...")\nworkflow = await client.workflows.create(name="Invoice Approval")'),
    ("sdk-error-handling", "SDK Error Handling", "python", 'pip install meridianflow', 'from meridianflow import MeridianFlow, RateLimitError\n\ntry:\n    client.workflows.execute("wf_abc123")\nexcept RateLimitError as e:\n    time.sleep(e.retry_after)'),
    ("sdk-pagination", "SDK Pagination Helpers", "python", 'pip install meridianflow', 'for task in client.tasks.auto_paginate(status="pending", limit=100):\n    print(task.id, task.title)'),
    ("sdk-migration-v1", "Migrating from SDK v1", "python", 'pip install --upgrade meridianflow', '# v1\nclient.create_workflow(name="X")\n# v2\nclient.workflows.create(name="X")'),
]

GUIDE_PROCESSES = [
    "Employee Onboarding", "Employee Offboarding", "Expense Approvals", "Invoice Processing",
    "Purchase Orders", "Contract Review", "Incident Response", "Change Management",
    "Content Publishing", "Customer Onboarding", "Vendor Onboarding", "Access Requests",
    "Budget Approvals", "Timesheet Approvals", "Leave Requests", "Equipment Provisioning",
    "Security Reviews", "Compliance Attestations", "Campaign Launches", "Product Launches",
    "Bug Triage", "Release Management", "Document Review", "Sales Quote Approvals",
    "Discount Approvals", "Refund Processing", "KYC Verification", "Data Access Requests",
    "Travel Requests", "Training Enrollment",
]

GUIDE_HOWTOS = [
    ("guide-migrating-from-zapier", "Migrating from Zapier", "Map Zaps to MeridianFlow workflows and move automations over incrementally."),
    ("guide-idempotent-automations", "Designing Idempotent Automations", "Build workflows that are safe to re-trigger without double side effects."),
    ("guide-monitoring-metrics", "Monitoring with Metrics", "Track execution volume, failure rates, and approval latency with the metrics API."),
    ("guide-alerting-on-failures", "Alerting on Failures", "Route workflow.execution.failed events to PagerDuty or Slack for on-call visibility."),
    ("guide-tagging-strategy", "Tagging Strategy", "A workspace-wide tagging scheme that keeps hundreds of workflows discoverable."),
    ("guide-workspace-organization", "Organizing Your Workspace", "Folders, naming, and permissions patterns for large teams."),
    ("guide-environment-promotion", "Promoting Between Environments", "Use export/import and the CLI to promote workflows from sandbox to production."),
    ("guide-bulk-data-import", "Bulk Data Import", "Seed tasks and variables from CSV using the bulk endpoints and import jobs."),
    ("guide-backfilling-executions", "Backfilling Executions", "Replay historical records through a workflow without triggering notifications."),
    ("guide-throttling-strategies", "Throttling Strategies", "Stay under rate limits with client-side queues, concurrency caps, and batching."),
    ("guide-webhook-fan-out", "Webhook Fan-Out", "Distribute one event to many consumers reliably with queues and dead-letter handling."),
    ("guide-forms-best-practices", "Forms Best Practices", "Design task forms that are fast to fill in and produce clean structured data."),
    ("guide-mobile-approvals", "Approvals on Mobile", "How approvers act on requests from the mobile app and notification actions."),
    ("guide-email-approvals", "Email-Based Approvals", "Let approvers approve or reject directly from an email without signing in."),
    ("guide-slack-approvals", "Slack-Based Approvals", "Approve requests from interactive Slack messages using the Slack integration."),
    ("guide-ooo-delegation", "Out-of-Office Delegation", "Keep approvals moving during vacations with date-ranged delegation rules."),
    ("guide-reporting-dashboards", "Building Reporting Dashboards", "Combine the analytics API with your BI tool for team-level dashboards."),
    ("guide-least-privilege-keys", "Least-Privilege API Keys", "Scope keys per integration and rotate them on a 90-day schedule."),
    ("guide-audit-readiness", "Audit Readiness", "Use audit logs, immutable execution history, and exports to prepare for audits."),
    ("guide-cost-optimization", "Execution Cost Optimization", "Reduce plan usage by consolidating triggers and pruning noisy workflows."),
    ("guide-workspace-cleanup", "Workspace Cleanup", "Find and archive stale workflows, unused connections, and orphaned queues."),
    ("guide-seasonal-scaling", "Scaling for Seasonal Peaks", "Prepare high-volume periods with concurrency tuning and burst allowances."),
    ("guide-incident-postmortems", "Automating Incident Postmortems", "Generate postmortem tasks and reviews automatically after incidents close."),
    ("guide-error-budgets", "Error Budgets for Automations", "Set failure-rate targets per workflow and alert when budgets burn down."),
    ("guide-api-pagination-patterns", "Pagination Patterns", "Cursor-walking patterns for syncing large task and execution datasets."),
]

INTEGRATIONS = [
    "Slack", "Microsoft Teams", "Jira", "Salesforce", "GitHub", "GitLab", "Bitbucket",
    "Zendesk", "HubSpot", "Workday", "NetSuite", "SAP", "Okta", "Azure AD",
    "Google Workspace", "PagerDuty", "ServiceNow", "Asana", "Trello", "Notion",
    "Airtable", "Dropbox", "Box", "Google Drive", "OneDrive", "Amazon S3",
    "Snowflake", "BigQuery", "Redshift", "Zapier", "Segment", "Datadog",
    "New Relic", "Splunk", "Twilio", "SendGrid", "Mailchimp", "Stripe",
    "QuickBooks", "Xero", "DocuSign", "Adobe Sign", "Tableau", "Power BI",
]

INTEGRATION_AUTH = ["OAuth 2.0", "OAuth 2.0", "OAuth 2.0", "API key", "personal access token"]

SECURITY = [
    ("security-overview", "Security Overview", "How MeridianFlow protects customer data across infrastructure, application, and organizational controls."),
    ("security-soc2", "SOC 2 Compliance", "MeridianFlow maintains SOC 2 Type II attestation; reports are available under NDA from the trust portal."),
    ("security-gdpr", "GDPR", "Data-processing terms, subprocessor list, and tooling for data subject access and deletion requests."),
    ("security-data-residency", "Data Residency", "Choose US or EU data residency per workspace on Enterprise plans; data never leaves the selected region."),
    ("security-encryption-at-rest", "Encryption at Rest", "All customer data is encrypted at rest with AES-256; keys are managed in a dedicated KMS with annual rotation."),
    ("security-encryption-in-transit", "Encryption in Transit", "TLS 1.2+ is required for all API and dashboard traffic; HSTS and modern cipher suites are enforced."),
    ("security-sso-saml", "Single Sign-On (SAML)", "Connect Okta, Azure AD, or any SAML 2.0 IdP for dashboard SSO, with optional enforced SSO."),
    ("security-scim", "SCIM Provisioning", "Automate user provisioning and deprovisioning from your IdP with SCIM 2.0."),
    ("security-rbac", "Role-Based Access Control", "Built-in roles — admin, developer, member, viewer — plus custom roles on Enterprise plans."),
    ("security-audit-logging", "Audit Logging", "Every administrative and data-changing action is captured in a tamper-evident audit log, exportable via API."),
    ("security-ip-allowlisting", "IP Allowlisting", "Restrict API and dashboard access to approved network ranges per workspace."),
    ("security-secrets-management", "Secrets Management", "Store connection credentials in the encrypted secrets vault; secrets are never returned by the API after creation."),
    ("security-vulnerability-disclosure", "Vulnerability Disclosure", "How to report security issues to security@meridiansystems.com and what to expect from our response process."),
    ("security-penetration-testing", "Penetration Testing", "Annual third-party penetration tests; summary letters are available on request."),
]

TROUBLESHOOTING = [
    ("ts-401-unauthorized", "401 Unauthorized Errors", "Your token is missing, malformed, or expired.", "Re-authenticate with your API key; tokens expire after 1 hour."),
    ("ts-403-scopes", "403 Missing Scope Errors", "The token lacks the scope required by the endpoint.", "Mint a token from a key that includes the required scope, e.g. `workflows:write`."),
    ("ts-429-rate-limits", "Debugging 429 Responses", "You exceeded your plan's request rate.", "Honor `Retry-After`, add backoff, and batch requests; see Rate Limits."),
    ("ts-webhook-not-received", "Webhook Not Received", "Deliveries fail TLS, time out, or your endpoint returns non-2xx.", "Check the delivery log, verify your endpoint responds 2xx within 10 seconds, and replay the delivery."),
    ("ts-stuck-workflow", "Workflow Execution Stuck", "An execution waits on an unassigned task or an unreachable connection.", "Inspect the execution timeline; reassign the blocking task or fix the connection and resume."),
    ("ts-task-not-assigned", "Task Not Being Assigned", "No routing rule matched, or every eligible assignee is at capacity.", "Add a catch-all routing rule and review capacity ceilings on load-based assignment."),
    ("ts-timeouts", "Request Timeouts", "Large payloads or synchronous exports can exceed the 30-second request limit.", "Use async export jobs and keep request bodies under 1 MB."),
    ("ts-pagination-drift", "Pagination Drift", "Offset-style paging misses or repeats rows while data changes.", "Always use cursor pagination with `starting_after`; never combine cursors with sorting changes."),
    ("ts-sdk-connection", "SDK Connection Errors", "Corporate proxies or stale CA bundles block TLS connections.", "Configure the SDK's proxy settings and update your CA certificates."),
    ("ts-payload-validation", "422 Validation Errors", "The request body fails schema validation.", "Read `error.details` for the failing fields; check types and required fields against the reference."),
    ("ts-duplicate-executions", "Duplicate Executions", "Retried POSTs without idempotency keys create duplicates.", "Send an `Idempotency-Key` header on execution requests you might retry."),
    ("ts-contact-support", "Contacting Support", "You need help beyond the docs.", "Email support@meridiansystems.com with the `request_id` from the failing response and your workspace slug."),
]

# API Reference resources: (plural, singular, id_prefix, action, fields)
RESOURCES = [
    ("approvals", "approval", "apr", "decide", ["status", "approver_id", "decided_at"]),
    ("approval-chains", "approval chain", "chn", "activate", ["name", "mode", "steps"]),
    ("forms", "form", "frm", "publish", ["name", "fields", "published"]),
    ("form-submissions", "form submission", "sub", "reopen", ["form_id", "answers", "submitted_by"]),
    ("users", "user", "usr", "deactivate", ["name", "email", "role"]),
    ("teams", "team", "team", "add-member", ["name", "member_count", "queue_id"]),
    ("roles", "role", "role", "assign", ["name", "permissions", "built_in"]),
    ("groups", "group", "grp", "sync", ["name", "source", "member_count"]),
    ("audit-logs", "audit log entry", "aud", "export", ["actor_id", "action", "target"]),
    ("reports", "report", "rpt", "run", ["name", "type", "schedule"]),
    ("schedules", "schedule", "sch", "pause", ["cron", "timezone", "workflow_id"]),
    ("connections", "connection", "con", "test", ["provider", "status", "scopes"]),
    ("variables", "variable", "var", "resolve", ["key", "value", "scope"]),
    ("templates", "template", "tpl", "instantiate", ["name", "category", "step_count"]),
    ("executions", "execution", "exe", "cancel", ["workflow_id", "status", "started_at"]),
    ("comments", "comment", "cmt", "resolve", ["task_id", "author_id", "body"]),
    ("attachments", "attachment", "att", "scan", ["task_id", "filename", "size_bytes"]),
    ("notifications", "notification", "ntf", "mark-read", ["user_id", "type", "read"]),
    ("api-keys", "API key", "key", "rotate", ["label", "prefix", "scopes"]),
    ("sla-policies", "SLA policy", "sla", "evaluate", ["name", "response_target", "resolution_target"]),
    ("labels", "label", "lbl", "merge", ["name", "color", "usage_count"]),
    ("custom-fields", "custom field", "fld", "archive", ["key", "type", "required"]),
    ("exports", "export job", "exp", "download", ["type", "status", "row_count"]),
    ("invitations", "invitation", "inv", "resend", ["email", "role", "expires_at"]),
    ("queues", "queue", "que", "drain", ["name", "strategy", "open_tasks"]),
]

OPS = [
    ("list", "GET", "List {plural}", "Returns a paginated list of {plural} in your workspace, newest first."),
    ("create", "POST", "Create {a_singular}", "Creates a new {singular}. Returns the created object."),
    ("retrieve", "GET", "Retrieve {a_singular}", "Retrieves the {singular} with the given id."),
    ("update", "PATCH", "Update {a_singular}", "Updates the provided fields on an existing {singular}; omitted fields are unchanged."),
    ("delete", "DELETE", "Delete {a_singular}", "Permanently deletes the {singular}. This cannot be undone."),
]

FIRST_NAMES = ["Sofia", "Liam", "Maya", "Ethan", "Ana", "Noah", "Ines", "Omar", "Grace",
               "Felix", "Nora", "Ivan", "Lucia", "Owen", "Amara", "Hugo", "Elena", "Jonas",
               "Tara", "Ravi", "Chloe", "Mateo", "Aisha", "Dylan", "Freya", "Kenji", "Paula",
               "Stefan", "Yara", "Colin", "Mira", "Andre", "Leila", "Tomas", "Ingrid",
               "Diego", "Hana", "Victor", "Salma", "Erik", "Bianca", "Arjun", "Wendy",
               "Pavel", "Rosa"]
LAST_NAMES = ["Alvarez", "Brandt", "Costa", "Dominguez", "Eriksen", "Fontaine", "Gallo",
              "Haddad", "Ishikawa", "Jansen", "Kovacs", "Lindqvist", "Moreau", "Novak",
              "Okafor", "Pereira", "Quinn", "Rossi", "Silva", "Tanaka", "Ueda", "Varga",
              "Weber", "Xu", "Yilmaz", "Zhang", "Ortega", "Nakamura", "Larsen", "Kaur",
              "Johansson", "Ibrahim", "Horvat", "Grant", "Fischer", "Egan", "Dubois",
              "Castillo", "Bauer", "Antonov", "Mbeki", "Sørensen", "Petit", "Romero", "Klein"]


# ---------------------------------------------------------------------------
# Doc builders
# ---------------------------------------------------------------------------

def build_docs(next_id):
    docs = []

    def add(slug, title, section, content, tags, keywords, updated_at=None):
        nonlocal next_id
        docs.append({
            "id": next_id, "slug": slug, "title": title, "section": section,
            "order_": len(docs) + 1, "content": content,
            "updated_at": updated_at or rand_date(),
            "tags": json.dumps(tags),
            "_keywords": keywords,
        })
        next_id += 1

    # Getting Started -------------------------------------------------------
    for slug, title, intro, tags in GETTING_STARTED:
        code = curl_block("GET", f"/api/v2/workflows?limit=25") if slug == "pagination" else \
            curl_block("POST", "/api/v2/workflows/wf_abc123/execute",
                       {"variables": {"amount": 4200}}) if slug == "idempotency" else None
        content = guide_content(title, intro, "Getting Started", code=code,
                                bullets=[
                                    "Works the same in sandbox and production.",
                                    "Supported by every official SDK.",
                                    "See the API Reference for exact request and response shapes.",
                                ])
        add(slug, title, "Getting Started", content, tags, kw_from(title, tags))

    # Workflows -------------------------------------------------------------
    for slug, title, intro in WORKFLOWS:
        body = {"name": "Invoice Approval", "trigger": "manual"}
        code = curl_block(rng.choice(["POST", "PATCH"]), "/api/v2/workflows/wf_abc123", body)
        tags = ["workflows"] + [w.lower().strip(",") for w in title.split()[:2]]
        content = guide_content(title, intro, "Workflows", code=code, bullets=[
            "Configured per workflow in the visual editor or via the API.",
            "Changes are tracked in workflow versions.",
            "Execution history records how each rule was evaluated.",
        ])
        add(slug, title, "Workflows", content, tags,
            kw_from(title, tags, extra=["workflow automation", "approval"]))

    # Tasks -----------------------------------------------------------------
    for slug, title, intro in TASKS:
        code = curl_block("POST", "/api/v2/tasks/tsk_9f21c/assign",
                          {"assignee": rng.choice(["it_team", "hr_team", "finance_team"])})
        tags = ["tasks"] + [w.lower().strip(",") for w in title.split()[:2]]
        content = guide_content(title, intro, "Tasks", code=code, bullets=[
            "Applies to tasks created by any workflow step.",
            "Visible in the task detail panel and the audit history.",
            "Also available through the bulk endpoints.",
        ])
        add(slug, title, "Tasks", content, tags,
            kw_from(title, tags, extra=["task routing", "assignment"]))

    # Webhooks: event pages + guides ---------------------------------------
    for event, desc in WEBHOOK_EVENTS:
        slug = "webhook-event-" + event.replace(".", "-")
        title = f"Event: {event}"
        payload = {
            "id": "evt_" + "".join(rng.choices(string.hexdigits.lower(), k=8)),
            "type": event,
            "created_at": "2026-05-14T09:32:00Z",
            "data": {"object_id": ("wf_" if event.startswith("workflow") else "tsk_")
                                  + "".join(rng.choices(string.hexdigits.lower(), k=6))},
        }
        content = (
            f"{desc}\n\n## Payload\n\n```json\n{json.dumps(payload, indent=2)}\n```\n\n"
            "## Delivery\n\nDeliveries are signed (see Verifying Signatures) and retried "
            "up to 5 times on failure. Consumers should deduplicate on `delivery_id`.\n\n"
            "## Subscribing\n\n" +
            curl_block("POST", "/api/v2/webhooks",
                       {"url": "https://example.com/hooks/mflow", "events": [event]})
        )
        tags = ["webhooks", "events", event.split(".")[0]]
        add(slug, title, "Webhooks", content, tags,
            kw_from(title, tags, extra=[event, "payload", "delivery"]))

    for slug, title, intro in WEBHOOK_GUIDES:
        content = guide_content(title, intro, "Webhooks",
                                code=curl_block("GET", "/api/v2/webhooks/whk_3a71b/deliveries?limit=20"),
                                bullets=[
                                    "Applies to every registered webhook endpoint.",
                                    "Delivery history is retained for 30 days.",
                                    "Use `mflow listen` to test locally.",
                                ])
        tags = ["webhooks"] + [w.lower() for w in title.split()[:2]]
        add(slug, title, "Webhooks", content, tags, kw_from(title, tags, extra=["delivery", "hmac"]))

    # SDKs ------------------------------------------------------------------
    for slug, title, lang, install, snippet in SDKS:
        content = (
            f"The official MeridianFlow {title.replace(' SDK', '')} tooling wraps the REST API "
            "with typed models, automatic retries, and pagination helpers.\n\n"
            f"## Installation\n\n```bash\n{install}\n```\n\n"
            f"## Quick Start\n\n```{lang}\n{snippet}\n```\n\n"
            "## Configuration\n\nThe client reads `MERIDIANFLOW_API_KEY` from the environment "
            "when no key is passed explicitly. Use `mf_test_*` keys against the sandbox.\n\n"
            "## Support\n\nSDKs follow semantic versioning and support the two most recent "
            "API versions. File issues on the public GitHub repository."
        )
        tags = ["sdk", lang, "client-library"]
        add(slug, title, "SDKs", content, tags,
            kw_from(title, tags, extra=["sdk", "install", "client"]))

    # Changelog: per-release notes -----------------------------------------
    feats = ["bulk task endpoints", "approval delegation windows", "cron trigger editor",
             "SLA breach events", "workspace audit exports", "form conditional fields",
             "execution timeline view", "connection health checks", "custom roles",
             "queue capacity ceilings", "webhook payload pinning", "CLI listen mode",
             "async export jobs", "task watchers", "label merge tooling",
             "sandbox data reset", "SCIM group sync", "per-step retry overrides"]
    fixes = ["a race condition when completing tasks in parallel branches",
             "timezone drift in scheduled triggers around DST changes",
             "duplicate webhook deliveries after a network partition",
             "incorrect pagination cursors on filtered task lists",
             "a 500 when archiving workflows with running executions",
             "missing audit entries for bulk reassignment",
             "slow queries on large execution histories",
             "an encoding issue in CSV exports with unicode labels"]
    improvements = ["faster workflow editor load times", "clearer 422 validation messages",
                    "higher default burst allowances", "reduced webhook delivery latency",
                    "better SDK error types", "expanded audit log filters",
                    "dashboard accessibility improvements", "tighter token scope checks"]

    v2_minors = {(2, 0): "2023-09-12", (2, 1): "2024-01-16", (2, 2): "2024-05-14",
                 (2, 3): "2024-09-10", (2, 4): "2025-01-21", (2, 5): "2025-05-13",
                 (2, 6): "2025-10-07", (2, 7): "2026-04-08", (2, 8): "2026-06-24"}
    releases = []
    # v1.x: minors every ~2 months 2021-01 .. 2023-07, patches between
    d = datetime.date(2021, 1, 12)
    minor = 0
    patch = 0
    while d < datetime.date(2023, 8, 20):
        releases.append(((1, minor, patch), d))
        d += datetime.timedelta(days=rng.randint(17, 27))
        if patch >= rng.choice([1, 1, 2]):
            minor += 1
            patch = 0
        else:
            patch += 1
    # v2.x: fixed minor dates (matching the summary changelog), patches between
    minor_items = sorted(v2_minors.items())
    for i, ((maj, mn), ds) in enumerate(minor_items):
        d0 = datetime.date.fromisoformat(ds)
        releases.append(((maj, mn, 0), d0))
        end = (datetime.date.fromisoformat(minor_items[i + 1][1])
               if i + 1 < len(minor_items) else None)
        if end is None:
            break
        p = 1
        d = d0 + datetime.timedelta(days=rng.randint(18, 30))
        while d < end - datetime.timedelta(days=10):
            releases.append(((maj, mn, p), d))
            p += 1
            d += datetime.timedelta(days=rng.randint(18, 30))

    for (maj, mn, pt), rdate in releases:
        ver = f"v{maj}.{mn}.{pt}"
        slug = "changelog-" + ver.replace(".", "-")
        title = f"{ver} Release Notes"
        lines = [f"Released {rdate.strftime('%B %d, %Y')}.", ""]
        if pt == 0:
            for f in rng.sample(feats, 2):
                lines.append(f"- **New**: {f.capitalize()}")
            lines.append(f"- **Improved**: {rng.choice(improvements).capitalize()}")
        lines.append(f"- **Fixed**: {rng.choice(fixes).capitalize()}")
        if rng.random() < 0.3:
            lines.append(f"- **Fixed**: {rng.choice(fixes).capitalize()}")
        lines += ["", "## Upgrade notes", "",
                  ("No breaking changes. SDKs pick this up automatically."
                   if pt else "Review the API Versioning page before pinning `MF-Version` to this release.")]
        tags = ["changelog", "release-notes", f"v{maj}-{mn}"]
        add(slug, title, "Changelog", "\n".join(lines), tags,
            kw_from(title, tags, extra=["release", ver, "upgrade"]),
            updated_at=rdate.isoformat())

    # API Reference ---------------------------------------------------------
    for plural, singular, prefix, action, fields in RESOURCES:
        a_singular = ("an " if singular[0].lower() in "aeiou" else "a ") + singular
        base = f"/api/v2/{plural}"
        oid = f"{prefix}_" + "".join(rng.choices("0123456789abcdef", k=6))
        for op, method, title_t, desc_t in OPS:
            title = title_t.format(plural=plural.replace("-", " "), a_singular=a_singular)
            desc = desc_t.format(plural=plural.replace("-", " "), singular=singular)
            path = base if op in ("list", "create") else f"{base}/{{id}}"
            example_path = base if op in ("list", "create") else f"{base}/{oid}"
            resp = {"id": oid, "object": singular.replace(" ", "_")}
            for f in fields:
                resp[f] = "..." if not f.endswith(("_at", "_id")) else (
                    "2026-03-18T10:05:00Z" if f.endswith("_at") else "usr_1a2b3c")
            if op == "list":
                resp = {"data": [resp], "has_more": True, "next_cursor": oid}
            if op == "delete":
                resp = {"id": oid, "deleted": True}
            body = ({f: "..." for f in fields[:2]} if method in ("POST", "PATCH") else None)
            content = (
                f"{desc}\n\n```http\n{method} {path}\n```\n\n"
                "## Parameters\n\n| Name | Type | Description |\n|------|------|-------------|\n"
                + "\n".join(f"| `{f}` | string | The {f.replace('_', ' ')} of the {singular}. |"
                            for f in fields)
                + ("\n| `limit` | integer | Page size, 1-100 (default 25). |"
                   "\n| `starting_after` | string | Cursor for pagination. |" if op == "list" else "")
                + "\n\n## Example Request\n\n"
                + curl_block(method, example_path, body)
                + f"\n\n## Example Response\n\n```json\n{json.dumps(resp, indent=2)}\n```\n\n"
                f"Requires the `{plural.split('-')[0]}:{'read' if method == 'GET' else 'write'}` scope."
            )
            slug = f"ref-{plural}-{op}"
            tags = ["api-reference", plural, op]
            add(slug, title, "API Reference", content, tags,
                kw_from(title, tags, extra=[method.lower(), plural.replace("-", " "), singular]))
        # action endpoint
        title = f"{action.replace('-', ' ').capitalize()} {a_singular}"
        path = f"{base}/{{id}}/{action}"
        content = (
            f"Performs the `{action}` action on {a_singular}.\n\n"
            f"```http\nPOST {path}\n```\n\n## Example Request\n\n"
            + curl_block("POST", f"{base}/{oid}/{action}")
            + "\n\n## Example Response\n\n```json\n"
            + json.dumps({"id": oid, "object": singular.replace(" ", "_"), "status": "ok"}, indent=2)
            + f"\n```\n\nRequires the `{plural.split('-')[0]}:write` scope."
        )
        add(f"ref-{plural}-{action}", title, "API Reference", content,
            ["api-reference", plural, action],
            kw_from(title, ["api-reference", plural], extra=[action, singular]))

    # Guides ----------------------------------------------------------------
    for proc in GUIDE_PROCESSES:
        slug = "guide-" + proc.lower().replace(" ", "-")
        title = f"Build an {proc} Workflow" if proc[0] in "AEIOU" else f"Build a {proc} Workflow"
        steps = rng.sample(["a form trigger", "a routing rule", "an approval chain",
                            "a webhook notification", "an SLA policy", "an escalation rule",
                            "a Slack notification", "a scheduled reminder"], 4)
        intro = (f"This guide walks through automating {proc.lower()} end to end with "
                 f"MeridianFlow, using {steps[0]}, {steps[1]}, {steps[2]}, and {steps[3]}.")
        content = guide_content(title, intro, "Guides",
                                code=curl_block("POST", "/api/v2/workflows",
                                                {"name": proc, "trigger": rng.choice(["manual", "form", "schedule"])}),
                                bullets=[
                                    f"Start from the {proc} template in the gallery.",
                                    "Test in sandbox with `mf_test_*` keys before publishing.",
                                    "Add an SLA policy so overdue steps escalate automatically.",
                                ])
        tags = ["guide", "template", proc.lower().split()[0]]
        add(slug, title, "Guides", content, tags,
            kw_from(title, tags, extra=[proc.lower(), "how to", "tutorial"]))

    for slug, title, intro in GUIDE_HOWTOS:
        content = guide_content(title, intro, "Guides",
                                code=curl_block("GET", "/api/v2/executions?limit=50"),
                                bullets=[
                                    "Applies to workspaces of any size.",
                                    "Pairs well with the analytics API for measurement.",
                                    "See related pages in Workflows and Webhooks for details.",
                                ])
        tags = ["guide", "how-to"] + [w.lower() for w in title.split()[:1]]
        add(slug, title, "Guides", content, tags, kw_from(title, tags, extra=["best practices"]))

    # Integrations ----------------------------------------------------------
    for vendor in INTEGRATIONS:
        vslug = vendor.lower().replace(" ", "-").replace(".", "")
        slug = f"integration-{vslug}"
        title = f"{vendor} Integration"
        auth = rng.choice(INTEGRATION_AUTH)
        events = rng.sample([e for e, _ in WEBHOOK_EVENTS], 3)
        content = (
            f"Connect {vendor} to MeridianFlow to trigger workflows from {vendor} events and "
            f"push workflow updates back into {vendor}.\n\n"
            "## Setup\n\n"
            f"1. In the dashboard, open **Settings > Connections** and choose **{vendor}**.\n"
            f"2. Authenticate with {auth}.\n"
            "3. Pick the environment (sandbox or production) for the connection.\n"
            "4. Test the connection from the connection detail page.\n\n"
            "## Common automations\n\n"
            f"- Create {vendor} records when a workflow completes\n"
            f"- Start a workflow when a matching {vendor} event arrives\n"
            f"- Post task and approval updates into {vendor}\n\n"
            "## Events\n\nTypical events used with this integration: "
            + ", ".join(f"`{e}`" for e in events) + ".\n\n"
            "## Troubleshooting\n\nIf the connection shows `degraded`, re-authenticate from the "
            "connection page and check the audit log for revoked credentials.\n\n> "
            + rng.choice(NOTES)
        )
        tags = ["integration", vslug, "connection"]
        add(slug, title, "Integrations", content, tags,
            kw_from(title, tags, extra=[vendor.lower(), "connect", auth.lower()]))

    # Security --------------------------------------------------------------
    for slug, title, intro in SECURITY:
        content = guide_content(title, intro, "Security", bullets=[
            "Documented in the trust portal at trust.meridiansystems.com.",
            "Enterprise plans include custom review sessions with our security team.",
            "Questions: security@meridiansystems.com.",
        ])
        tags = ["security", "compliance"] + [w.lower().strip("()") for w in title.split()[:1]]
        add(slug, title, "Security", content, tags,
            kw_from(title, tags, extra=["trust", "compliance"]))

    # Troubleshooting -------------------------------------------------------
    for slug, title, cause, fix in TROUBLESHOOTING:
        content = (
            f"## Symptom\n\n{title}.\n\n## Likely cause\n\n{cause}\n\n"
            f"## Resolution\n\n{fix}\n\n## Still stuck?\n\n"
            "Collect the `request_id` from the failing response and contact "
            "support@meridiansystems.com. Include your workspace slug and the approximate "
            "time of the failure (UTC)."
        )
        tags = ["troubleshooting", "errors"] + [w.lower() for w in title.split()[:1]]
        add(slug, title, "Troubleshooting", content, tags,
            kw_from(title, tags, extra=["debug", "fix", "support"]))

    return docs


def build_users(next_id, next_root, doc_ids):
    users = []
    pairs = list(zip(FIRST_NAMES, LAST_NAMES))
    rng.shuffle(pairs)
    for i, (fn, ln) in enumerate(pairs[:45]):
        uid = next_id + i
        role = rng.choices(["developer", "admin"], weights=[85, 15])[0]
        prefix = rng.choice(["dev", "dev", "dev", "ops", "mgr", "qa"])
        key_kind = rng.choice(["mf_live_", "mf_live_", "mf_test_"])
        api_key = key_kind + "".join(rng.choices(string.ascii_lowercase + string.digits, k=20))
        n_bm = rng.choices([0, 1, 2, 3, 4, 5], weights=[15, 20, 25, 20, 12, 8])[0]
        users.append({
            "id": uid,
            "root_user_id": next_root + i,
            "username": f"{prefix}_{fn.lower()}",
            "password": f"mflow_docs{uid}",
            "name": f"{fn} {ln}",
            "email": f"{fn.lower()}.{ln.lower().replace('ø', 'o').replace('ö', 'o')}@meridiansystems.com",
            "api_key": api_key,
            "bookmarked_pages": json.dumps(sorted(rng.sample(doc_ids, n_bm))),
            "role": role,
        })
    return users


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    dry = "--dry-run" in sys.argv
    db = sqlite3.connect(DB_PATH, timeout=60)
    db.execute("PRAGMA foreign_keys = ON")

    n_docs, max_doc = db.execute(
        "SELECT COUNT(*), MAX(id) FROM documentation_api_docs_docs").fetchone()
    max_row = db.execute(
        "SELECT MAX(row_id) FROM documentation_api_docs_search_index").fetchone()[0]
    max_user = db.execute("SELECT MAX(id) FROM documentation_api_docs_users").fetchone()[0]
    max_root = db.execute(
        "SELECT MAX(root_user_id) FROM documentation_api_docs_users").fetchone()[0]
    existing_slugs = {r[0] for r in db.execute(
        "SELECT slug FROM documentation_api_docs_docs")}
    if max_doc > 18:
        print(f"docs table already expanded (max id {max_doc}); aborting.")
        return

    docs = build_docs(max_doc + 1)

    # sanity: slug uniqueness + sidebar render ceiling
    slugs = [d["slug"] for d in docs]
    assert len(set(slugs)) == len(slugs), "duplicate new slugs"
    assert not (set(slugs) & existing_slugs), "slug collides with existing doc"
    assert n_docs + len(docs) <= MAX_DOCS_TOTAL, (
        f"{n_docs + len(docs)} docs would exceed sidebar ceiling {MAX_DOCS_TOTAL}")
    assert all(d["updated_at"] <= "2026-06-24" for d in docs), "doc newer than existing max"

    search_rows = [{"row_id": max_row + i + 1, "doc_id": d["id"],
                    "keywords": json.dumps(d["_keywords"])}
                   for i, d in enumerate(docs)]
    all_doc_ids = list(range(1, docs[-1]["id"] + 1))
    users = build_users(max_user + 1, max_root + 1, all_doc_ids)

    from collections import Counter
    sec_counts = Counter(d["section"] for d in docs)
    print(f"docs: +{len(docs)}  search_index: +{len(search_rows)}  users: +{len(users)}")
    print("new docs by section:", dict(sec_counts))
    print(f"final docs total: {n_docs + len(docs)} (ceiling {MAX_DOCS_TOTAL})")
    if dry:
        for d in docs[:3] + docs[-3:]:
            print(" ", d["id"], d["section"], "|", d["slug"], "|", d["updated_at"])
        print("  sample user:", users[0]["username"], users[0]["email"], users[0]["role"])
        return

    bdir = ROOT / "data" / "backups" / "documentation-api-docs-expansion-2026-07-20"
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "inserted_ids.json").write_text(json.dumps({
        "docs": [d["id"] for d in docs],
        "search_index": [r["row_id"] for r in search_rows],
        "users": [u["id"] for u in users],
    }, indent=1))

    doc_cols = ["id", "slug", "title", "section", "order_", "content", "updated_at", "tags"]
    db.executemany(
        f"INSERT INTO documentation_api_docs_docs ({', '.join(doc_cols)}) "
        f"VALUES ({', '.join('?' * len(doc_cols))})",
        [[d[c] for c in doc_cols] for d in docs])
    db.executemany(
        "INSERT INTO documentation_api_docs_search_index (row_id, doc_id, keywords) "
        "VALUES (?, ?, ?)",
        [[r["row_id"], r["doc_id"], r["keywords"]] for r in search_rows])
    ucols = ["id", "root_user_id", "username", "password", "name", "email",
             "api_key", "bookmarked_pages", "role"]
    db.executemany(
        f"INSERT INTO documentation_api_docs_users ({', '.join(ucols)}) "
        f"VALUES ({', '.join('?' * len(ucols))})",
        [[u[c] for c in ucols] for u in users])

    # Rebuild external-content FTS tables
    db.execute("INSERT INTO fts_documentation_api_docs_docs"
               "(fts_documentation_api_docs_docs) VALUES('rebuild')")
    db.execute("INSERT INTO fts_documentation_api_docs_search_index"
               "(fts_documentation_api_docs_search_index) VALUES('rebuild')")
    db.commit()
    print(f"inserted; rollback ids at {bdir}/inserted_ids.json")


if __name__ == "__main__":
    main()
