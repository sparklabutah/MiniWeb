This website simulates a job search and application tracking portal (Indeed-style). The interface emulates popular job boards where users can search for jobs, save listings, apply to positions, set up job alerts, and track application status.

Data source: data_sources/indeed-jobs-augment/ (users.json, saved_jobs.json, applications.json, job_alerts.json, search_history.json)
Searching method: keyword match + weighted keyword overlap (semantic), no external ML models
