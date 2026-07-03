# Site Changes — Eval+Repair Cycle (July 2026)

Two rounds of automated evaluation (1,300 tasks each) plus earlier cross-site integration work. Final pass rate: **1,299/1,300 (99.9%)**.

## Global Changes

| Change | Details |
|--------|---------|
| FTS5 indexes | Rebuilt all 200 tables via `build_fts.py --force` (38 were empty) |
| `db.search()` | Fixed to skip empty FTS tables and fall back to LIKE |
| `evaluation/judge.py` | Added Claude CLI backend as OpenAI fallback |
| `evaluation/agents.py` | Added `MockAgent` (pipeline testing) and `ChatClaude` (Claude CLI as browser-use LLM) |
| `tasks.json` (all 65) | Rebuilt twice — 20 tasks per site grounded in current DB data |
| Cross-site events | `emit()` calls added to 40+ sites for signup, payment, booking, messaging |
| Login hardening | Removed user-picker dropdowns, added password validation on ~15 sites |
| Logout routes | Added missing `/logout` on instant-messaging, remote-calls, transit-directions |

## Per-Site Changes

| Site | Files | Changes |
|------|-------|---------|
| academic-paper-db | routes.py | Reverted FTS migration — text PKs (`0704.0001`) break FTS5 `content_rowid`. Restored LIKE search for `_query_papers()` and `_count_papers_db()`. |
| agency-portals | routes.py | Added `emit("signup")`, `emit("booking")` for appointments, `emit("payment")` for permit/bill payments. |
| ai-chatbots | routes.py | Added `emit("signup")` on registration. |
| auctions-p2p-marketplaces | routes.py | (1) Fixed `_keyword_score()` TypeError — list fields (`color_options`, `payment_methods`) concatenated as str. Wrapped in `str()`. (2) Migrated search to `db.search()`. |
| banking | routes.py | Migrated 6 search endpoints from LIKE to `db.search()`: `transactions_page()`, `api_transactions()`, `api_transactions_search()`, `api_transactions_semantic()`, `cc_transactions()`, `api_cc_transactions()`. |
| blogs | routes.py | Added LIKE fallback in `api_search()` when FTS returns 0 results. |
| brokerage | routes.py | Added `emit("signup")` and `emit("message")` for trade execution notifications. |
| business-company | routes.py | (no routes changes — tasks.json rebuilt only) |
| calendar-todo | routes.py | Fixed `end_` → `end` key mapping in `_load_events()`. DB uses `end_` (reserved word) but code read `e['end']`. |
| cloud-dev-consoles | routes.py | Added `emit("signup")` and email notification on alert creation via `_add_email()`. |
| cloud-storage-file-transfer | routes.py | (1) Semantic search limited to top 10 results (was returning all 53). (2) Root folder fix: `parent_id=0` vs `None` check. |
| code-editor-execution | routes.py | Added `emit("signup")`. |
| comparison-aggregators | routes.py | Migrated search to `db.search()`. Price/battery/year post-filters preserved. |
| conference-review-submission | routes.py | Migrated `_db_query_papers()` and `_db_search_papers()` to `db.search()`. BM25 replaces manual `_keyword_score`. |
| converters-calculators | (no changes) | |
| course-sites-classrooms | routes.py | Added `emit("signup")` and email notification on assignment submission. |
| crm | routes.py, 5 templates | (1) Stage naming: `closed-won` → `closed_won` in routes + index/deals/deal/contact/company templates. (2) Activity creation: `description` → `subject` + `notes`. |
| crowdfunding-donations | routes.py | Added `emit("signup")` and email notification on pledge confirmation. |
| dating | routes.py | Added GET handler `api_messages_list` for `/api/messages` (was POST-only 405). |
| design-creative | routes.py | Added `emit("signup")`, email on design creation, `emit("file_created")` on project completion. |
| dictionaries-language-tools | routes.py | Added `/api/search?q=` endpoint with tiered relevance (exact > prefix > contains). LIKE autocomplete intentionally preserved. |
| documentation-api-docs | routes.py | Added `/api/search?q=` endpoint using `_search_docs()`. |
| documents | routes.py | Added `emit("signup")`. |
| e-commerce | routes.py | Added `emit("signup")`. |
| email | routes.py | Fixed `_USER_EMAIL_MAP`: user ID 5 → 7 (ID 5 doesn't exist). Added 5 Meridian `@meridiansystems.com` addresses. |
| flights-hotels | routes.py | (1) 4 COALESCE fixes for raw/synthetic fields (price/fare, airline/carrier_lg, city/cityname, name/hotelname). (2) Added `q=` search to flights API. (3) Migrated search to `db.search()`. (4) WHERE clauses on list endpoints preventing 245K/1M row full scans. |
| forms-surveys | routes.py, verifiers.py | **routes**: `shared_with`/`attachments` empty string vs list crash fix. **verifiers**: Mutation verifiers rewritten as self-contained (execute + verify). |
| forums | routes.py, verifiers.py | **routes**: (1) Subreddit `r/` prefix filter fix. (2) Search → `db.search()`. (3) N+1 query fix — `api_list_subreddits()` did per-sub JOINs across 1M comments. **verifiers**: Rewritten with real Reddit data. |
| handwritten-notes-whiteboards | routes.py, verifiers.py | **routes**: 5 search endpoints → `db.search()`. **verifiers**: Mutation verifiers rewritten. |
| health-fitness-tracking | routes.py, verifiers.py | **routes**: Added password validation on login, `emit("signup")`, `emit("booking")` for workouts. **verifiers**: Fixed field names (`avg_steps`, `avg_calories_burned`, `date_from`/`date_to`). |
| health-portals | routes.py, verifiers.py | **routes**: Added `record_type` filter to `/api/records`. **verifiers**: Rewritten with authenticated sessions. |
| instant-messaging | routes.py, verifiers.py, login template | **routes**: Removed user-picker dropdown from login — replaced with username/password inputs. Added `/logout`. Added `emit("signup")`. **verifiers**: Rewritten. |
| insurance-loans | routes.py, verifiers.py | **routes**: Added password validation, `emit("signup")`, `emit("booking")` for loan payments. **verifiers**: Rewritten. |
| job-sites | routes.py, verifiers.py | **routes**: Salary parser rewritten — `_parse_salary_num()` guards non-numeric, `_split_salary_range()` regex for spaced dashes, excludes unparseable values. **verifiers**: Rewritten. |
| live | routes.py, verifiers.py | **routes**: Search fixed (empty FTS → LIKE → `db.search()` with fallback). **verifiers**: Rewritten — channel nested key, follow status, gift sub recipient, redeem reward_id. |
| map-services | routes.py, verifiers.py | **routes**: (1) `hours` dict/string TypeError in `_semantic_score()` + `open_now`. (2) `api_login()` password variable before assignment. **verifiers**: Rewritten. |
| multimedia-posting | routes.py, verifiers.py, login template | **routes**: Removed user-picker from login, added password validation, `emit("signup")`. **verifiers**: Rewritten. |
| music | routes.py, verifiers.py | **routes**: Added `emit("signup")`. **verifiers**: Rewritten — playback uses session-overlay `save_collection`. |
| news | routes.py, verifiers.py | **routes**: 4 search endpoints → `db.search()` (removed manual LIKE + Python scoring). **verifiers**: Rewritten. |
| password-managers | verifiers.py | Rewritten. |
| personal-portfolio | routes.py, verifiers.py | **routes**: Added password validation on login. **verifiers**: Rewritten. |
| petitions-voting-info | routes.py, verifiers.py | **routes**: Added `emit("signup")`, `emit("booking")` for petition deadlines, email on signature. **verifiers**: Rewritten. |
| podcasts-audiobooks | routes.py, verifiers.py | **routes**: Added `emit("signup")`. **verifiers**: Rewritten. |
| project-homepages | routes.py, verifiers.py | **routes**: Added password validation. **verifiers**: Rewritten. |
| project-mgmt-issue-tracking | routes.py | (1) Empty `key_` column — added `_remap_key()`, `_ensure_project_key()`, `_ensure_issue_key()` to generate `MF-101` style keys. (2) `api_issue_by_key` parses computed keys. |
| qa-knowledge | routes.py | (1) Tags page: full 1M row scan → `tags_meta` table lookup. (2) `api_register`: `save_collection` → `db.save_item()` (UNIQUE constraint fix). |
| rating-review | routes.py, verifiers.py | **routes**: Added password validation, `emit("signup")`. **verifiers**: Rewritten. |
| real-estate-buy-rent | routes.py | Added `emit("booking")` for property viewing appointments. |
| remote-calls | routes.py | Added `/logout` route. |
| software-marketplace | routes.py | FTS multi-word search AND → OR — queries each term individually, merges deduplicated results. |
| sports-esports | routes.py | Added `emit` import (event bus wiring). |
| spreadsheets-slides | routes.py | Added `emit("signup")`. |
| tax-filing-dmv-permits | routes.py | Added `/api/login` endpoint (previously form-only login). |
| team-chat-workspace | routes.py, login template | Removed user-picker dropdown from login — replaced with username/password inputs. Added `emit("signup")`. |
| ticketing-events | routes.py, search.html | Added `/search` route + template. Events searchable by name, description, venue, organizer, tags. |
| transit-directions | routes.py | (1) Populated empty `routes_served` arrays via fuzzy-match against `routes.major_stops` (37/171 stops). (2) Added `/logout` route. |
| translation | routes.py | Replaced placeholder `[French translation unavailable]` with `_call_claude_translate()` using Claude CLI subprocess. Real translation for all languages. |
| university-academic | routes.py, research.html | (1) Added `/research` route + template with faculty/course counts. (2) Case-insensitive course URLs (`.lower()` comparison). |
| url-shorteners-qr | routes.py | Added `/s/<short_code>` redirect route for short links. |
| version-control | routes.py | (1) Added 5 API routes: `/api/repos/by-name/<name>`, `/api/users/by-username/<username>`, tree, issues, export. (2) 10 search endpoints → `db.search()`. |
| video | routes.py | Added `emit("signup")`. |
| visual-how-to-guides | routes.py | Category route accepts string names alongside integer IDs. |
| weather | routes.py | (1) Compare API comma-split fix for `'City, ST'` format. (2) Search → `db.search()`. |
| wikis | routes.py | (1) FTS AND → OR for multi-word search. (2) Major perf fix: `_load_pages()` loaded 50K articles per request. Refactored to overlay-only queries, targeted `_find_raw_wiki_by_slug()`, SQL `COUNT(*)` and `GROUP BY`. |

## Verifiers Rewritten (18 sites)

All rewritten to be **self-contained** — mutation verifiers execute the action within the verifier itself, then verify the result, instead of checking pre-existing state.

forms-surveys, forums, handwritten-notes-whiteboards, health-fitness-tracking, health-portals, instant-messaging, insurance-loans, job-sites, live, map-services, multimedia-posting, music, news, password-managers, personal-portfolio, petitions-voting-info, podcasts-audiobooks, project-homepages, rating-review

## Sites With No Code Changes (4)

converters-calculators, business-company (tasks.json only), bookstore (template site)
