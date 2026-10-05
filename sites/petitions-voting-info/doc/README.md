# Lakeport Civic Hub (`petitions-voting-info`)

A civic engagement portal for the fictional City of Lakeport, WA, combining
Change.org-style petitions (create, sign, share, subscribe) with a county
elections site (election results, voter registration, polling places).

- URL: `/sites/petitions-voting-info/` (simulated domain `civicvoice.org`)
- Data split: held-out (test) site

## Pages

| Route | Page |
|---|---|
| `/` | Active petitions and upcoming elections |
| `/petitions` | Petition list: search, category and status filters, sort with asc/desc order |
| `/petition/<id>` | Petition detail: progress bar, signatures, comments, Sign form (typed signature), Subscribe, Save, Share |
| `/create-petition` | Start a petition (title, description, goal, category, deadline) |
| `/elections`, `/election/<id>` | Elections list; races, candidates, ballot measures and results |
| `/voter-info` | Registration details, precinct check and polling locations |
| `/register-voter` | Voter registration form |
| `/dashboard` | Saved and subscribed petitions |
| `/login` | Sign-in form |

JSON endpoints under `/api/` cover petitions (search, sign, save, subscribe,
share, comments), categories, elections, voter info and registration.

## Interactions and macros

- Search petitions: `search`
- Filter petitions by category or status: `filter_by_dropdown`
- Sort petitions by date, signatures or title: `sort_by_form`
- Start a petition, sign one, register to vote: `create_by_form`
- Subscribe to or save a petition: `toggle_relationship`
- Share a petition (email, Twitter, Facebook, link): `share_by_form`
- Open petitions and elections: `navigate_by_route`
- Read petition details, election results and precinct status: `report_information`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `petitions-voting-info`.

## Data

- Tables: `petitions_voting_info_petitions`, `petitions_voting_info_signatures`,
  `petitions_voting_info_elections`, `petitions_voting_info_voter_info`,
  `petitions_voting_info_users`.
- Login reads `session["user_id"]` (via `helpers.auth`), so the global
  auto-login signs in user 1. The login form accepts any non-empty password
  for a known username.
- Signing sends a "Signature confirmed" email to WebMail. A petition flips to
  `won` once its signature count reaches its goal.
- Creating a petition with a deadline emits `booking` (calendar event and
  email). Logging in emits `signup` (password-vault entry and welcome email).
