# EduPortal LMS (`course-sites-classrooms`)

A Canvas / Moodle-style learning management system. Students browse and enroll
in courses, play lectures, submit assignments (text plus an optional file) and
post in discussion boards. Instructors and admins also grade submissions and
edit the gradebook. Access is role-based (admin / instructor / student).

- URL: `/sites/course-sites-classrooms/` (simulated domain `learnhub.edu`)
- Data split: training site

## Pages

| Route | Page |
|---|---|
| `/` | Dashboard and course catalog with search |
| `/course/<id>` | Course page: modules, lecture player, assignments, enroll / leave toggle |
| `/course/<id>/assignment/<aid>` | Assignment instructions, submit form with file upload, submissions table with date filter, grading |
| `/course/<id>/gradebook` | Inline-editable gradebook grid with "+ Add row", save and CSV export |
| `/course/<id>/discussions` | Discussion threads, new-thread and reply forms |
| `/login` | Sign-in form |

JSON endpoints under `/api/` expose courses, assignments, submissions, gradebooks, discussions, users and stats; `/api/export/gradebook/<course_id>` returns CSV.

## Interactions and macros

- Search the course catalog: `search`
- Open courses and assignments: `navigate_by_route`
- Enroll in or leave a course: `toggle_relationship`
- Play a lecture in the lecture player: `play_by_playback`
- Submit an assignment, grade a submission, start or reply to a discussion: `create_by_form`
- Attach a file to a submission: `upload_file`
- Edit gradebook cells: `edit_by_cell`
- Read course content, assignment details and filtered submissions: `report_information`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `course-sites-classrooms`.

## Data

- Tables: `course_sites_classrooms_courses`, `_assignments`, `_submissions`,
  `_discussions`, `_users` (all prefixed `course_sites_classrooms_`).
- Login uses the shared `session["user_id"]`, so the global auto-login signs in
  user 1 (Alex Rivera, a student). Grading and gradebook edits need an
  instructor or admin account.
- Logging in emits `signup` (password-vault entry + email). Submitting an
  assignment sends a confirmation email and emits `booking`, which adds the
  assignment's due date to the calendar.
