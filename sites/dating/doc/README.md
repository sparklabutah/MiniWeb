# HeartLink (`dating`)

A Tinder, Bumble or Hinge-style dating app. Users swipe through discovery cards,
browse and filter the profile directory, like or pass, chat with matches and
edit their own profile and preferences.

- URL: `/sites/dating/` (simulated domain `sparkconnect.app`)
- Data split: held-out (test) site

## Pages

| Route | Page |
|---|---|
| `/` | Discover cards with like/pass, a discovery filter bar (age, looking for, interest, joined date range) and sort |
| `/profiles` | Paginated profile directory with search, gender/looking-for dropdowns, interest checkboxes and sort (Nearest needs login) |
| `/profile/<id>` | Profile detail: photo gallery, bio, interests, Like/Pass, Report, Block |
| `/likes` | "Likes You": pending likes with Like back / Pass |
| `/matches` | Match list |
| `/conversation/<match_id>` | Chat with a match, including photo attachments |
| `/edit-profile` | Edit bio, location, interests, preferences and photos |
| `/login`, `/register` | Sign-in and sign-up |

JSON endpoints under `/api/` cover profiles, discovery, likes, matches,
messages, stats and export.

## Interactions and macros

- Sign in or register: `authenticate_by_form`, `create_by_form`
- Search the directory: `search`
- Filter by dropdowns, interest checkboxes or join date: `filter_by_dropdown`, `filter_by_options`, `filter_by_date_range`
- Sort discovery cards or the directory: `sort_by_form`
- Like or pass, like back: `feedback_by_react`, `toggle_relationship`
- Block a profile: `toggle_relationship`
- Message a match, attach a photo: `message_from_free_text`, `upload_file`
- Edit the profile and set preferences: `edit_by_form`, `configure_by_form`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `dating`.

## Data

- Tables: `dating_users`, `dating_likes`, `dating_matches`, `dating_messages`.
- Login reads `session["user_id"]` (via `helpers.auth`), so the global
  auto-login signs the user in as user 1.
- Gallery photos are SVGs rendered on the fly by `sites/dating/photos.py` at
  `/photo/<user_id>/<idx>.svg`. `scripts/seed_dating_photos.py` writes the
  4-photo gallery URLs into `dating_users`. Re-run it after a DB rebuild.
- Sending a message emails the recipient a notification and mirrors the message
  into instant messaging (`on_message`). A message that mentions meeting up
  ("dinner", "coffee", "tomorrow", ...) also adds a "Date planned" calendar
  event. Login and registration emit `signup`.
