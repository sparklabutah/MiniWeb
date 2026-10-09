# Alex Rivera (`personal-portfolio`)

The personal developer portfolio of Alex Rivera, the shared MiniWeb persona,
in the style of a GitHub Pages / Vercel personal site. It shows a profile,
project gallery, structured resume, skills table and blog links, with a
contact form and site-wide search.

- URL: `/sites/personal-portfolio/` (simulated domain `alexrivera.dev`)
- Data split: training site

## Pages

| Route | Page |
|---|---|
| `/` | Home: profile, featured projects (sort dropdown, "Export CSV" link), contact form |
| `/contact` | Home page scrolled to the contact form |
| `/projects`, `/project/<id>` | Project gallery (search, category / tech / status filters) and project detail |
| `/resume` | Experience, education, skills, certifications |
| `/skills` | Skills table (name, level, years, category) |
| `/blog` | Links to external blog posts |
| `/search` | Search across projects, resume, blog and profile |
| `/admin` | Owner-only overview including contact messages (redirects to `/login` otherwise) |
| `/login` | Sign-in form |

JSON endpoints under `/api/` cover profile, projects, resume, blog links, skills, search, export (`?type=projects|resume&format=csv|json`), contact and newsletter subscribe.

## Interactions and macros

- Open projects, resume and blog from the nav or search results: `navigate_by_route`
- Sort the projects section: `sort_by_form`
- Send a message through the contact form: `create_by_form`
- Export the project list as CSV: `export`
- Read projects, skills, resume and search results: `report_information`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `personal-portfolio`.

## Data

- Tables: `personal_portfolio_profile`, `personal_portfolio_projects`,
  `personal_portfolio_resume`, `personal_portfolio_blog_links`,
  `personal_portfolio_subscriptions`, `personal_portfolio_users`.
- Login goes through `helpers.auth` on `session["user_id"]`, so the global
  auto-login signs in user 1. Visitors browse as user 1.
- Contact messages are saved to a `contact_messages` collection that has no base
  table, so `db.query` cannot read them back. Graders see the submission in the
  request log. Newsletter subscribe exists only as an API (`POST /api/subscribe`).
