# CalendarTodo (`calendar-todo`)

A Google Calendar-style calendar and to-do app. Users browse events by week or
day, filter them by category, priority, calendar owner or date range, and
create, edit, share, invite to and RSVP to events.

- URL: `/sites/calendar-todo/` (simulated domain `calflow.app`)
- Data split: training site

## Pages

| Route | Page |
|---|---|
| `/` | Week view (`?view=`, `?week_offset=`) with search, sidebar filters, sort and CSV/ICS/JSON export links |
| `/week/<date>`, `/day/<date>` | Week and day views for a given date |
| `/event/<id>` | Event detail: attendees and RSVPs, invite form, share link, delete |
| `/event/<id>/edit` | Edit form (title, description, date/time, category, priority, status) |
| `/dashboard` | The user's overview |
| `/login`, `/register` | Sign-in and registration |

New events are created through the "New Event" form, which posts to `/create`.
JSON endpoints under `/api/` cover events, search, ranges, categories, stats,
sharing, invites, RSVPs and export.

## Interactions and macros

- Search events: `search`
- Filter by category, priority or user, or by a From/To range: `filter_by_dropdown`, `filter_by_date_range`
- Sort events by date, title or priority: `sort_by_form`
- Create an event or invite someone to it: `create_by_form`
- Edit or reschedule an event: `edit_by_form`
- Delete an event: `delete_from_table`
- Copy an event's share link: `share_by_form`
- Export the calendar: `export`
- Open events and switch Day/Week views: `navigate_by_route`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `calendar-todo`.

## Data

- Tables: `calendar_todo_events`, `calendar_todo_users`.
- "Today" is fixed by `sites/calendar-todo/config/config.json`
  (`simulated_today`, currently 2026-06-21). The default week view is built
  around that date.
- Pages require `session["user_id"]`, so the global auto-login signs the user
  in as user 1 (Alex Rivera).
- Creating an event sends a confirmation email to WebMail. Registering emits a
  `signup` event (password-manager entry and welcome email).
- Bookings on other sites (the `booking` event) add events here via
  `app/handlers/calendar_handler.py`.
