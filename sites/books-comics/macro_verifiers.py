"""Per-macro verification functions for books-comics.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/books-comics"


def verify_macro_navigate_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/categories")
    cats = r.json()
    if not cats:
        return {"pass": False, "detail": "No categories returned"}
    slug = cats[0]["slug"]
    r2 = requests.get(f"{_base(server_url)}/category/{slug}")
    return {"pass": r2.status_code == 200, "detail": f"Category page '{slug}': {r2.status_code}"}


def verify_macro_navigate_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/book/1")
    return {"pass": r.status_code == 200, "detail": f"Book detail page: {r.status_code}"}


def verify_macro_search_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/books/search?q=the")
    results = r.json()
    return {"pass": len(results) > 0, "detail": f"search_by_query 'the': {len(results)} results"}


def verify_macro_search_by_semantic(server_url):
    r = requests.get(f"{_base(server_url)}/api/books/semantic?q=learning+education")
    results = r.json()
    return {"pass": r.status_code == 200, "detail": f"search_by_semantic: {len(results)} results"}


def verify_macro_filter_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/books?category=science")
    books = r.json()
    ok = all(b["category"] == "science" for b in books)
    return {"pass": ok, "detail": f"filter_by_dropdown science: {len(books)} books, all_science={ok}"}


def verify_macro_filter_by_slider(server_url):
    r = requests.get(f"{_base(server_url)}/api/books?min_rating=4.0")
    books = r.json()
    ok = all(b["rating"] >= 4.0 for b in books)
    return {"pass": ok, "detail": f"filter_by_slider rating>=4.0: {len(books)} books, all_match={ok}"}


def verify_macro_sort_by_ranking(server_url):
    r = requests.get(f"{_base(server_url)}/api/books?sort=rating")
    books = r.json()
    if len(books) < 2:
        return {"pass": True, "detail": "Too few books to verify sort"}
    ratings = [b["rating"] for b in books]
    is_sorted = all(ratings[i] >= ratings[i+1] for i in range(len(ratings)-1))
    return {"pass": is_sorted, "detail": f"sort_by_ranking: sorted={is_sorted}"}


def verify_macro_extract_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/books/1")
    book = r.json()
    return {"pass": "description" in book and "year" in book,
            "detail": f"extract_by_route: book has description={len(book.get('description',''))} chars"}


def verify_macro_select_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/categories/science/stats")
    stats = r.json()
    return {"pass": "unique_authors" in stats,
            "detail": f"select_by_dropdown: science stats={stats}"}


def verify_macro_play_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/book/1/read?chapter=1")
    return {"pass": r.status_code == 200, "detail": f"play_by_route (reader): {r.status_code}"}


def verify_macro_play_by_playback(server_url):
    base = _base(server_url)
    # Login first
    requests.post(f"{base}/api/login",
                  json={"username": "novel_eve", "password": "pass654"})
    # Update reading progress
    r = requests.post(f"{base}/api/users/5/reading-progress",
                      json={"book_id": 1, "chapter": 2, "progress": 50})
    data = r.json()
    ok = data.get("status") == "updated"
    # Verify
    r2 = requests.get(f"{base}/api/users/5/reading-progress")
    progress = r2.json()
    return {"pass": ok and "1" in progress,
            "detail": f"play_by_playback: progress={progress}"}


def verify_macro_post_from_free_text(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/reviews/2",
                      json={"text": "Test review for macro verification", "user_id": 5})
    data = r.json()
    ok = data.get("text") == "Test review for macro verification"
    return {"pass": ok, "detail": f"post_from_free_text: review posted={ok}"}


def verify_macro_react_by_toggle(server_url):
    base = _base(server_url)
    # Post a review first
    r = requests.post(f"{base}/api/reviews/3",
                      json={"text": "Macro test review", "user_id": 5})
    review_id = r.json().get("id")
    # React to it
    r2 = requests.post(f"{base}/api/reviews/3/react",
                       json={"review_id": review_id, "reaction": "like"})
    data = r2.json()
    ok = data.get("count", 0) > 0
    return {"pass": ok, "detail": f"react_by_toggle: like count={data.get('count')}"}


def verify_macro_rate_by_slider(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/books/3/rate",
                      json={"rating": 4.0, "user_id": 5})
    data = r.json()
    ok = data.get("status") == "rated"
    return {"pass": ok, "detail": f"rate_by_slider: status={data.get('status')}"}


def verify_macro_follow_by_toggle(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/users/4/follow", json={"author": "TestAuthor"})
    data = r.json()
    ok = data.get("action") == "followed"
    # Toggle back
    requests.post(f"{base}/api/users/4/follow", json={"author": "TestAuthor"})
    return {"pass": ok, "detail": f"follow_by_toggle: action={data.get('action')}"}


def verify_macro_subscribe_by_toggle(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/users/4/subscribe", json={"category": "test_cat"})
    data = r.json()
    ok = data.get("action") == "subscribed"
    # Toggle back
    requests.post(f"{base}/api/users/4/subscribe", json={"category": "test_cat"})
    return {"pass": ok, "detail": f"subscribe_by_toggle: action={data.get('action')}"}


def verify_macro_save_by_toggle(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/users/4/save", json={"book_id": 99})
    data = r.json()
    ok = data.get("action") == "saved"
    # Toggle back
    requests.post(f"{base}/api/users/4/save", json={"book_id": 99})
    return {"pass": ok, "detail": f"save_by_toggle: action={data.get('action')}"}


def verify_macro_add_by_button(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/users/4/cart", json={"book_id": 99})
    data = r.json()
    ok = data.get("action") == "added"
    # Toggle back
    requests.post(f"{base}/api/users/4/cart", json={"book_id": 99})
    return {"pass": ok, "detail": f"add_by_button: action={data.get('action')}"}


def verify_macro_checkout_by_form(server_url):
    base = _base(server_url)
    # Add item to cart first
    requests.post(f"{base}/api/users/5/cart", json={"book_id": 1})
    # Checkout
    r = requests.post(f"{base}/api/users/5/checkout",
                      json={"name": "Eve Patel", "email": "eve@example.com",
                            "card": "4242424242424242"})
    data = r.json()
    ok = data.get("status") == "completed"
    return {"pass": ok, "detail": f"checkout_by_form: status={data.get('status')}"}
