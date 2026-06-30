# Job Sites

**Category**: Shopping & transactional
**Reviewer**: Farhan
**Number of macros**: 22

## Data Source

Kaggle Indeed Job Posting Dataset (augmented with synthetic user activity).
Directory: `data_sources/indeed-jobs-augment/`

### Data Files

- `users.json` -- 4 user profiles with job search preferences, work history, and account info
- `saved_jobs.json` -- 8 saved job listings with full posting details (title, company, location, salary, requirements, tags)
- `applications.json` -- 2 application records with status history timelines
- `job_alerts.json` -- 2 job alert configurations with filter criteria
- `search_history.json` -- 5 past search records with query text and filters applied

### Data Format

**users.json**: Each user has `id`, `username`, `display_name`, `email`, `profile` (headline, location, experience_years, current_employer, desired_title, preferred_work_mode, resume_uploaded), `activity_status`, `last_active`.

**saved_jobs.json**: Each job has `id`, `user_id`, `job_title`, `company`, `location`, `salary_range` (string like "$155,000 - $185,000"), `job_type` (full-time/part-time/contract/internship), `posted_date`, `saved_date`, `description_snippet`, `requirements` (list), `tags` (list), `url`, `company_rating`, `notes`.

**applications.json**: Each application has `id`, `user_id`, `job_title`, `company`, `location`, `salary_range`, `applied_date`, `status`, `status_history` (list of {status, date, reason?, note?}), `cover_letter_submitted`, `resume_version`, `recruiter_name`, `recruiter_email`, `notes`.

**job_alerts.json**: Each alert has `id`, `user_id`, `alert_name`, `search_query`, `filters` (location, salary_min, job_type, work_mode, experience_level), `frequency`, `email_notifications`, `is_active`, `created_date`, `last_triggered`, `matches_last_period`.

**search_history.json**: Each entry has `id`, `user_id`, `query`, `filters_applied`, `results_count`, `results_clicked`, `searched_at`.

## Real-World Model

**Indeed.com / LinkedIn Jobs** -- job search portal with search bar, filter sidebar, job cards, saved jobs, application tracker. Key UI elements:
- Search bar with keyword + location fields
- Filter sidebar with job type radio buttons, salary slider, date range picker
- Sort dropdown (relevance, date, salary)
- Company dropdown for browsing by employer
- Job detail pages with apply button and save toggle
- Application tracker with status timeline
- Job alerts with subscribe/unsubscribe toggles
- Resume upload on application form

## Target Macros

navigate_by_dropdown, navigate_by_route, search_by_query, search_by_semantic, filter_by_query, filter_by_semantic, filter_by_dropdown, filter_by_radio, filter_by_slider, filter_by_date_range, sort_by_ranking, extract_by_query, extract_by_semantic, extract_by_dropdown, extract_by_route, create_from_free_text, submit_by_query, upload_by_upload, follow_by_toggle, subscribe_by_toggle, save_by_toggle, apply_by_form

## Temporal Dynamics

Not applicable -- job postings are a static snapshot. No temporal simulation needed.

## Domain-Specific Notes

- Salary range is stored as a formatted string ("$155,000 - $185,000"); the interpreter parses min/max integers for slider filtering
- Job type values: full-time, part-time, contract, internship
- Semantic search uses weighted keyword overlap across all job fields (title, company, description, tags, requirements)
- The site supports browse-only mode (defaults to user 1) when not logged in
- Company pages aggregate all jobs from a single employer
- Application status values: applied, phone_screen_scheduled, phone_screen_completed, onsite_scheduled, interviewing, offered, withdrawn, rejected, declined, portfolio_review, design_exercise_submitted
