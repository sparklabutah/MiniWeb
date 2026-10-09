# Meridian State University (`university-academic`)

A university website and student portal: course catalog, faculty directory,
research areas, events, alumni network, admissions application and a
"My Schedule" course registration view, plus an editable course gradebook.

- URL: `/sites/university-academic/` (simulated domain `meridianstate.edu`)
- Data split: training site

## Pages

| Route | Page |
|---|---|
| `/` | Home: featured courses, upcoming events, departments |
| `/courses` | Academics: course catalog with search and department/level dropdowns (also `/courses/level/<level>`, `/courses/area/<area>`, `/courses/search/<query>`) |
| `/course/<id>` | Course detail with Register/Drop |
| `/course/<id>/gradebook` | Inline-editable score grid (student x assignment) |
| `/schedule` | My Schedule: registered and waitlisted courses |
| `/faculty`, `/faculty/<id>` | Faculty directory with search and area filter; faculty profile |
| `/departments`, `/research`, `/department/<id>` | Research areas and their faculty and courses |
| `/events`, `/event/<id>` | Events with date range and type filter; event detail |
| `/alumni` | Alumni directory with search and year filter |
| `/compare` | Two course dropdowns and a side-by-side table |
| `/apply` | Admissions application (name, email, program, statement) |
| `/subscribe` | Campus Life: subscribe/unsubscribe per research area (portal login required) |
| `/export` | Resources: download courses or faculty as CSV/JSON |
| `/contact`, `/login` | Contact form; MyMSU portal sign-in |

JSON endpoints under `/api/` mirror courses, faculty, departments, events, alumni and subscriptions.

## Interactions and macros

- Search courses, faculty or alumni: `search`
- Filter courses, faculty, events or alumni by dropdown: `filter_by_dropdown`
- Open courses, faculty profiles and events: `navigate_by_route`
- Submit an application or a contact message: `create_by_form`
- Edit gradebook cells: `edit_by_cell`
- Subscribe to a research area: `toggle_relationship`
- Export courses or faculty: `export`
- Read course, faculty and event details, compare two courses: `report_information`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `university-academic`.

## Data

- Tables: `university_academic_courses`, `_faculty`, `_departments`, `_events`,
  `_alumni`, `_users`, and `_enrollments` (created at runtime on first use).
- Course registration uses the root user id in `session["user_id"]`, so it
  works as user 1 under the global auto-login. Subscriptions and saved
  applications need a portal login, which sets the site's own `session["ua_user"]` (net id).
- An application sends a confirmation email to WebMail and emits `booking`
  (calendar entry). Portal login emits `signup`.
