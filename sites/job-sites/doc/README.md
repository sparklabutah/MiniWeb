# JobQuest (`job-sites`)

An Indeed or LinkedIn Jobs-style job board and application tracker. Users
search and filter job listings, save jobs, follow companies, apply with a
resume and cover letter, track applications and manage job alerts.

- URL: `/sites/job-sites/` (simulated domain `jobscout.careers`)
- Data split: training site
- Source data: Kaggle Indeed job postings, with synthetic user activity

## Pages

| Route | Page |
|---|---|
| `/` | Landing page with keyword and location search and a category menu |
| `/jobs` | All Jobs: search, company dropdown, job-type radios, min/max salary sliders, posted-date range, sort |
| `/job/<id>` | Job detail: description, requirements, salary, Save Job, Follow company, Apply |
| `/company/<name>` | All jobs from one company |
| `/apply/<job_id>`, `/apply/saved/<saved_id>` | Application form (name, email, resume upload, cover letter) |
| `/saved`, `/saved/<id>` | Saved jobs and saved-job snapshots |
| `/applications`, `/application/<id>` | Application tracker with status history |
| `/alerts` | Job alerts: create, subscribe and unsubscribe |
| `/profile` | Profile with followed companies, subscriptions and resume upload |
| `/login` | Sign-in form |

JSON endpoints under `/api/` cover jobs, semantic search, saves, applications,
alerts, companies, follows, resume upload and stats.

## Interactions and macros

- Search by keyword and location: `search`
- Filter by company, job type, salary range or posted date: `filter_by_dropdown`, `filter_by_options`, `filter_by_slider`, `filter_by_date_range`
- Sort by date, salary, company or title: `sort_by_form`
- Apply to a job, create a job alert: `create_by_form`
- Upload a resume: `upload_file`
- Save a job, follow a company, toggle an alert: `toggle_relationship`
- Open jobs and the Saved, Applications and Alerts pages: `navigate_by_route`
- Read job details and search results: `report_information`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `job-sites`.

## Data

- Tables: `job_sites_jobs`, `job_sites_users`, `job_sites_applications`,
  `job_sites_saved_jobs`, `job_sites_job_alerts`, `job_sites_search_history`.
- Login uses the site's own `session["job_sites_user_id"]`. Browsing pages fall
  back to user 1 in read-only mode, and actions need an explicit login.
- Uploaded resumes are written to `sites/job-sites/data/uploads/` on disk
  (gitignored).
- Applying sends a confirmation email to WebMail. Applying through the JSON API
  also emits a `booking` event that puts the application on the calendar.
  Logging in emits `signup`.
