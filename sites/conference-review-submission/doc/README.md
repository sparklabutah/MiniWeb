# PeerPortal (`conference-review-submission`)

An OpenReview-style venue and peer-review system. Visitors browse venues and
papers with their reviews and scores. Signed-in reviewers bid on papers, write
reviews and upload submissions, and chairs assign reviewers and post decisions.

- URL: `/sites/conference-review-submission/` (simulated domain `peerportal.org`)
- Data split: held-out (test) site
- Source data: PeerRead (https://github.com/allenai/peerread) papers and reviews,
  plus a synthetic `miniweb-workshop-2026` venue still under review

## Pages

| Route | Page |
|---|---|
| `/`, `/venues` | Venue list |
| `/venue/<venue_id>` | A venue's papers with keyword search and sidebar decision, average-score and sort controls |
| `/venue/<venue_id>/stats` | Acceptance rates and score distributions |
| `/paper/<paper_id>` | Paper detail: metadata, reviews, scores, bid, withdraw, chair actions |
| `/paper/<paper_id>/review` | Review form (recommendation, confidence, strengths, weaknesses, comments) |
| `/console` | User console: pending review tasks with review deadlines, paper upload |
| `/search` | Global navbar search over papers and venue names |
| `/login` | Sign-in form |

JSON endpoints under `/api/` cover venues, papers, reviews, scores, decisions,
stats and export.

## Interactions and macros

- Sign in: `authenticate_by_form`
- Search a venue's papers: `search`
- Open venues and papers: `navigate_by_route`
- Write a review: `create_by_form`
- Bid or unbid on a paper: `create_by_form`, `edit_by_form`
- Withdraw a submission: `delete_from_table`
- Upload a paper from the console (.pdf, .doc, .docx, .tex): `upload_file`
- Read reviews, scores and venue statistics: `report_information`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `conference-review-submission`.

## Data

- Tables: `conference_review_submission_venues`,
  `conference_review_submission_papers`, `conference_review_submission_users`.
- Login uses the site's own `session["conf_review_uid"]`, so the global
  auto-login does not sign the user in. The console, reviewing, bidding and
  uploads need an explicit login. Assigning reviewers and posting decisions
  need a user with the `chair` or `admin` role.
- The console lists a paper as a pending task only while its venue is still
  under review. `scripts/seed_peerportal_assignments.py` assigns the workshop's
  papers to the reviewer users, and `scripts/seed_peerportal_deadlines.py`
  adds each venue's `review_deadline`. Re-run both after a DB rebuild.
- Signing in emits a `signup` event (password-manager entry and welcome email).
  Submitting a review or a paper sends a WebMail notification. Assigning a reviewer emits a
  `booking` event that puts the review deadline on the reviewer's calendar.
