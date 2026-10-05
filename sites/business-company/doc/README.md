# Apex Dynamics Corp (`business-company`)

A corporate marketing website for a fictional software company: products,
services, team, blog, careers, contact form and newsletter. Its product line
is the "Meridian" suite (MeridianFlow, MeridianVault and others).

- URL: `/sites/business-company/` (simulated domain `apexdynamics.com`)
- Data split: training site

## Pages

| Route | Page |
|---|---|
| `/` | Home: featured products, latest blog posts, team grid, newsletter signup |
| `/search?q=` | Site-wide search over products, blog posts and team members |
| `/products`, `/product/<id>` | Product catalog with category filter; product detail |
| `/services` | Services overview |
| `/about`, `/team/<id>` | Company and team page; team member bio |
| `/blog`, `/blog/<id>` | Blog index and post |
| `/careers`, `/careers/<id>` | Job openings with department/location dropdowns; job detail with an application form |
| `/applications` | The current user's submitted applications |
| `/contact` | Contact form (subject dropdown, name, email, message) |
| `/newsletter` | Newsletter subscription and topic preferences |

JSON endpoints under `/api/` expose team, products, services, posts, jobs, stats, compare and export.

## Interactions and macros

- Search from the header or the search page: `search`
- Open products, posts, team members and jobs: `navigate_by_route`
- Send the contact form or apply to a job: `create_by_form`
- Subscribe to the newsletter: `toggle_relationship`
- Read product, job and team details, or filtered product/job lists: `report_information`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `business-company`.

## Data

- Tables: `business_company_products`, `_services`, `_team`, `_posts`,
  `_testimonials`, `_jobs`, `_contacts`, `_subscribers`, `_applications`
  (created at runtime on first use). Content is synthetic.
- No login. Form handlers attribute actions to `session["user_id"]`, which the
  global auto-login sets to user 1.
- Contact messages and job applications send a confirmation email to WebMail
  (`on_inquiry`); a newsletter signup sends a welcome email (`on_subscribe`).
