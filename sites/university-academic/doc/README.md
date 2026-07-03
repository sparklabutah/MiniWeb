# University Academic (Meridian State University)

**Category**: Education / university
**Reviewer**: Minh
**Number of macros**: 16

## Data Source

Fictional university CSE department website. Data files in `data_sources/university-academic/`:
- `courses.json` -- 10 CSE courses (introductory, intermediate, advanced)
- `faculty.json` -- 8 faculty members with research areas, bios, publications
- `departments.json` -- Department metadata + 5 research areas (systems, ML, HCI, security, PL)
- `events.json` -- 5 department events (career fair, hackathon, meetup, lecture, celebration)
- `alumni.json` -- 5 alumni with graduation info, current positions, achievements
- `users.json` -- 5 users (alumni, faculty affiliates) with MSU NetIDs

### Data Format

All files are JSON. Courses have id, code, title, credits, level, description, prerequisites, instructor, research_area. Faculty have id, name, title, email, office, research_areas (list), bio, publications_count. Events have id, title, type, date (YYYY-MM-DD), time, location, description. Alumni have id, name, graduation_year, degree, advisor, current_position. Users have net_id, display_name, role.

## Real-World Model

**Meridian State University CSE department website** -- academic portal with navy/gold branding. Key UI elements:
- Navigation bar with Courses, Faculty, Research, Events, Alumni links
- Hero section with department name and stats
- Course catalog with level/area filters and search
- Faculty directory with research area filter
- Research areas with associated faculty and labs
- Events calendar with date range and type filters
- Alumni network with year filter and search
- Student/alumni portal with login

## Target Macros (18)

navigate_by_semantic, navigate_by_dropdown, navigate_by_route, search_by_query, search_by_semantic, filter_by_dropdown, extract_by_query, extract_by_checkbox, extract_from_table, extract_by_route, extract_by_date_range, compare_from_table, submit_by_query, apply_by_form, export_by_dropdown, subscribe_by_toggle

## Macro-to-Route Mapping

| Macro | Route(s) |
|-------|----------|
| navigate_by_semantic | Homepage links to research areas, events |
| navigate_by_dropdown | Header nav dropdown to Courses, Faculty, Research, Events, Alumni |
| navigate_by_route | /course/<id>, /faculty/<id>, /department/<id>, /event/<id> |
| search_by_query | /courses?q=, /faculty?q=, /alumni?q= |
| search_by_semantic | /api/faculty/search?q= (keyword-overlap ranked) |
| search_by_route | /courses/search/<query> |
| filter_by_dropdown | /courses?dept=, /courses?level=, /events?type=, /alumni?year= |
| filter_by_route | /courses/level/<level>, /courses/area/<area> |
| extract_by_query | /api/courses?q=, /api/faculty?q= |
| extract_by_checkbox | /courses?levels=introductory&levels=advanced (multi-select) |
| extract_from_table | /compare?ids= (course comparison table) |
| extract_by_route | /api/courses/<id>, /api/faculty/<id>, /api/events/<id> |
| extract_by_date_range | /events?date=YYYY-MM-DD&date_to=YYYY-MM-DD |
| compare_from_table | /compare?ids=cse-446,cse-473 (side-by-side) |
| submit_by_query | /contact (POST subject + message) |
| apply_by_form | /apply (POST applicant_name, email, program, statement) |
| export_by_dropdown | /api/export?format=csv&type=courses, /api/export?format=json&type=faculty |
| subscribe_by_toggle | /subscribe/<area_slug> (POST toggle subscription) |

## Temporal Dynamics

Not applicable -- university department websites are relatively static. Course catalogs and faculty directories change quarterly/annually but not in real-time. No temporal simulation needed.

## Domain-Specific Notes

- Courses have three levels: introductory, intermediate, advanced
- Research areas serve as the department grouping mechanism
- Faculty members are linked to courses they teach and research areas
- Events have types: career_fair, hackathon, alumni_meetup, lecture, celebration
- Alumni are linked to faculty advisors and current positions
- User authentication uses MSU NetID system (simplified)
- Subscriptions and applications are persisted in users.json
