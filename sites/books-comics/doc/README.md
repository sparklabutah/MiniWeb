# BookVerse (`books-comics`)

A digital bookstore and reading app in the style of Kindle / Google Play Books.
Users discover books by category, read chapters in an in-browser reader,
review and rate titles, follow authors, subscribe to categories and buy books
through a cart and checkout.

- URL: `/sites/books-comics/` (simulated domain `readshelf.com`)
- Data split: training site

## Pages

| Route | Page |
|---|---|
| `/` | Catalog: search, category / min-rating / price filters, sort |
| `/category/<slug>` | Books in one category |
| `/book/<id>` | Book detail: info, chapters, reviews, rating slider, save / follow author / subscribe / add-to-cart buttons |
| `/book/<id>/read` | Chapter reader with a reading-progress slider |
| `/cart`, `/checkout` | Cart and checkout (name, email, card, account type) |
| `/dashboard` | My Library: reading list, saved books, follows, subscriptions, "New from your subscriptions" |
| `/orders`, `/orders/<id>` | Purchase history and order receipt |
| `/login` | Sign-in form |

JSON endpoints under `/api/` serve books, chapters, categories, reviews, stats, export and per-user actions.

## Interactions and macros

- Search books by title, author or genre: `search`
- Filter by category, minimum rating or price; sort the catalog: `filter_by_dropdown`, `sort_by_form`
- Open books, categories and chapters: `navigate_by_route`
- Write a review, add a book to the cart: `create_by_form`
- Rate a book with the 1-5 slider: `feedback_by_star`
- Move the reader's progress slider: `filter_by_slider`
- Save/unsave a book, follow an author, subscribe to a category: `toggle_relationship`
- Check out the cart: `checkout_by_form`
- Read book details and reviews: `report_information`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `books-comics`.

## Data

- Tables: `books_comics_books`, `books_comics_chapters`, `books_comics_categories`,
  `books_comics_reviews`, `books_comics_users`, `books_comics_cart`,
  `books_comics_orders` (the orders table is created at runtime by `routes.py`).
- Source: open-licensed books from the Common Pile collection
  (https://huggingface.co/collections/common-pile/common-pile-v01).
- Login uses the shared `session["user_id"]`, so the global auto-login signs in user 1.
- Paid checkout charges the card through `app/bank_charges.charge_card`
  (a recognized SecureBank card needs the right CVV), records an order, then
  goes through 2FA (`request_2fa` → `/verify-payment`) before the `purchase`
  event posts a banking debit and a confirmation email. Free carts skip payment and 2FA.
