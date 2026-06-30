# Petitions / Voting Info -- Lakeport Civic Hub

**Category**: Government / civic
**Reviewer**: Kenny
**Number of macros**: 20

## Data Source

Generated civic data for the fictional City of Lakeport, Cascadia County, WA.
Files in `data_sources/petitions-voting/`:
- `petitions.json` -- 12 community petitions (active, won, closed) across categories: community, infrastructure, transportation, education, environment, health, arts_and_culture
- `signatures.json` -- 40 petition signatures with comments
- `elections.json` -- 3 elections (2 completed, 1 upcoming) with races, candidates, ballot measures, turnout
- `voter_info.json` -- Polling locations (4 with precincts), registration info, voting methods, deadlines, ballot measure explanations
- `users.json` -- 7 demo users with voter registration data, precincts, party affiliations

## Real-World Model

**Change.org** (petitions: create, sign, share, subscribe, progress bars) + **vote.org / county elections sites** (voter registration verification, polling locations, election results, ballot measure info).

## Target Macros (20)

| # | Macro | Implementation |
|---|-------|---------------|
| 1 | navigate_by_dropdown | Header nav links (Petitions, Elections, Voter Info) |
| 2 | navigate_by_route | Direct URL to petition or election detail page |
| 3 | search_by_query | Text search across petition titles, descriptions, tags |
| 4 | search_by_semantic | Keyword-overlap ranked search via /api/petitions/semantic |
| 5 | filter_by_query | Filter petitions by status query parameter |
| 6 | filter_by_dropdown | Filter petitions by category dropdown |
| 7 | sort_by_toggle | Sort petitions by date/signatures/title with asc/desc toggle |
| 8 | extract_by_query | Search petitions and extract first result title |
| 9 | extract_by_dropdown | View category stats (total signatures, counts) |
| 10 | extract_by_route | Get petition/election detail via direct URL |
| 11 | extract_by_date_range | Filter petitions by date_from/date_to created_at range |
| 12 | verify_by_dropdown | Check voter registration status by precinct dropdown |
| 13 | create_from_free_text | Create a new petition with title, description, category |
| 14 | submit_by_query | Submit a comment on a petition |
| 15 | sign_by_signature | Sign a petition by typing legal name in signature field |
| 16 | subscribe_by_toggle | Toggle subscription to petition updates |
| 17 | share_by_dropdown | Share petition via method dropdown (email, twitter, facebook, link) |
| 18 | save_by_toggle | Toggle save/unsave petition to user favorites |
| 19 | authenticate_by_form | Log in with username/password form |
| 20 | register_by_form | Register new voter with full registration form |

## Temporal Dynamics

Not applicable -- petitions and elections are static records with status fields. No temporal simulation needed. Mutable state: signatures, user saved/subscribed lists, new petitions.

## Domain-Specific Notes

- All 7 demo users use password "civicpass" (any non-empty password accepted in demo mode)
- Petitions have status: active, won, closed
- Elections have status: upcoming, completed
- Voter precincts: Precinct 1-4, mapped to polling locations
- Signing a petition requires a typed "signature" (legal name) field -- distinct from comments
- When a petition reaches its signature goal, status auto-changes to "won"
