# LakeReview (`rating-review`)

A Yelp-style review site for local businesses in the fictional town of
Lakeport, WA. Users browse and filter businesses, read and write star-rated
reviews, vote on reviews, follow reviewers and save businesses.

- URL: `/sites/rating-review/` (simulated domain `ratespot.com`)
- Data split: held-out (test) site

## Pages

| Route | Page |
|---|---|
| `/` | Home: search bar and featured businesses |
| `/businesses` | Business list: search, category, price and minimum-rating filters, sort links (Rating, Most Reviewed, Name), Save toggles |
| `/business/<id>` | Business detail: address, hours, photos, reviews with Useful/Funny/Cool votes, Follow buttons and owner responses |
| `/write-review/<id>` | Review form with star rating and text |
| `/my-reviews` | Your reviews with Edit and Delete |
| `/photos` | Photo gallery |
| `/login` | Sign-in form |

JSON endpoints under `/api/` cover businesses, reviews (helpful votes, owner
responses, ratings), photos, search, compare, compute, follows and saves.

## Interactions and macros

- Search businesses: `search`
- Filter by category or minimum rating: `filter_by_dropdown`
- Write a review: `create_by_form`
- Edit or delete your review: `edit_by_form`, `delete_from_table`
- Vote a review Useful, Funny or Cool: `feedback_by_react`
- Follow a reviewer or save a business: `toggle_relationship`
- Open a business from the list or the top nav: `navigate_by_route`
- Read ratings, reviews and business details: `report_information`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `rating-review`.

## Data

- Tables: `rating_review_businesses`, `rating_review_reviews`,
  `rating_review_photos`, `rating_review_users`.
- Login uses `session["user_id"]`, so the global auto-login signs in user 1
  (`alex_r`). The login form accepts a known username with an empty password.
- Logging in emits `signup` (password-vault entry and welcome email).
