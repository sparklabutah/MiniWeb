# KnowledgeHub (`qa-knowledge`)

A Stack Overflow-style programming Q&A site built from a Stack Exchange data
dump. Users search and browse questions by tag, read answer threads, vote,
answer, comment, accept answers, save questions, follow tags, share and
report content, and ask or edit their own questions.

- URL: `/sites/qa-knowledge/` (simulated domain `askoverflow.com`)
- Data split: training site

## Pages

| Route | Page |
|---|---|
| `/` | All Questions: search, sort tabs (Newest, Votes, Active, Unanswered), tag filters, "Follow a Tag" dropdown |
| `/question/<id>` | Question thread: votes, answers, accept, comments, save, share-platform dropdown, answer form |
| `/question/<id>/edit` | Edit question (title, body, tags) |
| `/question/<id>/report` | Report a question |
| `/ask` | Ask a question (title, body, tags) |
| `/tags`, `/tag/<tag>` | Tag directory and questions for a tag, with "Follow Tag" |
| `/users`, `/user/<id>` | User directory and profile (reputation, activity, tags) |
| `/search` | Search results |
| `/dashboard` | Saved questions and followed tags |
| `/login`, `/register` | Sign-in and registration |

JSON endpoints under `/api/` cover questions, answers, votes, tags, users, search, save, follow, share, report and stats.

## Interactions and macros

- Search questions: `search`
- Filter by tag; sort the question list: `filter_by_dropdown`, `sort_by_form`
- Open questions, tags and users: `navigate_by_route`
- Ask a question, post an answer, register: `create_by_form`
- Edit a question: `edit_by_form`
- Upvote / downvote questions and answers: `feedback_by_react`
- Save a question, follow a tag: `toggle_relationship`
- Share a question via the platform dropdown: `share_by_form`
- Read threads, scores and profiles: `report_information`
- Sign in: `authenticate_by_form`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `qa-knowledge`.

## Data

- Tables: `qa_knowledge_questions`, `qa_knowledge_answers`,
  `qa_knowledge_users`, `qa_knowledge_tags_meta`.
- Users are keyed by `root_user_id`. Login stores `session["qa_user_id"]` but
  falls back to the shared `user_id`, so the global auto-login signs in user 1.
  Logging out sets `qa_user_id` to None, which blocks that fallback until the
  next login.
- Logging in emits `signup` (password-vault entry + email).
