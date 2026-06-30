# Personal Portfolio -- Alex Rivera

**Category**: Static / informational
**Reviewer**: Minh
**Number of macros**: 10

## Data Source

Few-shot synthesised persona. Profile, projects, resume, and blog link data are generated to represent a realistic mid-career software engineer's personal portfolio site.

## Target Macros

1. **navigate_by_semantic** -- Use the site-wide semantic search (fuzzy word-overlap) to find content across projects, blog posts, resume, and profile. HTML page at `/search?q=...`, API at `/api/search?q=...`.
2. **navigate_by_dropdown** -- Use the project type, technology, and status dropdown filters on the `/projects` page to navigate to filtered project listings.
3. **navigate_by_route** -- Navigate directly to specific pages by URL: project detail (`/project/<id>`), resume (`/resume`), blog (`/blog`), skills table (`/skills`).
4. **extract_by_query** -- Search projects via the API (`/api/projects?q=...`) and extract information from results.
5. **extract_by_semantic** -- Use semantic search API (`/api/search?q=...`) to find and extract specific information across all content types.
6. **extract_from_table** -- Extract data from the HTML skills table on the `/skills` page, or via the `/api/skills` endpoint which returns tabular skill data with name, level, years, and category.
7. **extract_by_route** -- Access specific data by direct API route: `/api/profile`, `/api/resume`, `/api/projects/<id>`, `/api/blog-links`.
8. **submit_by_query** -- Submit a contact message via the form on the homepage or the POST API at `/api/contact`.
9. **export_by_dropdown** -- Export projects or resume skills as CSV or JSON via `/api/export?type=projects|resume&format=csv|json`. Supports optional category filtering for projects.
10. **subscribe_by_toggle** -- Toggle newsletter subscription via POST to `/api/subscribe` with `{"email": "..."}`. Repeated calls toggle between subscribed/unsubscribed states.

## Site Description

This site models **Alex Rivera's personal developer portfolio**, similar to sites built on GitHub Pages, Vercel, or personal domains. It is a single-person portfolio showcasing:

- **Profile**: Name, tagline, bio, location, skills, interests, and contact info.
- **Projects** (6): Side projects, open-source tools, and personal configs with technologies, status, collaborators, and GitHub/live links.
- **Resume**: Full structured resume with experience, education, skills by category, certifications, and selected projects.
- **Blog Links** (5): External blog post links categorised by topic (Technology, Photography, Outdoors, Gaming).
- **Contact Form**: Sends messages stored in `contact_messages.json`.
- **Newsletter Subscriptions**: Toggle-based subscription stored in `subscriptions.json`.

**Real-world model**: Personal portfolio sites like those on dev.to profiles, GitHub Pages, or custom-built developer portfolios.

**Data files** (in `data_sources/personal-portfolio/`):
- `profile.json` -- Owner profile with skills, education, work experience, contact
- `projects.json` -- Array of 6 projects with tech stacks, collaborators, status
- `resume.json` -- Structured resume with experience, education, skills, certs
- `blog_links.json` -- Array of 5 blog post links with categories and tags
- `users.json` -- Single owner user (alex_rivera)
- `contact_messages.json` -- Submitted contact messages (starts empty)
- `subscriptions.json` -- Newsletter subscriptions

**Temporal/dynamic data**: Minimal. Contact messages and subscriptions grow over time through user interaction. Project `last_updated` dates are static but represent a realistic timeline.
