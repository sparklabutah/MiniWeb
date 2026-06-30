#!/usr/bin/env python3
"""Walk all chains for books-comics and cloud-dev-consoles.

Uses chain_walker_lib functions directly for efficiency.
Writes status.json + trajectory.json for each chain.
"""

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
os.chdir(str(PROJECT_ROOT))

import chain_walker_lib as cw

RUNS_DIR = PROJECT_ROOT / "annotation" / "chain_runs"


def save_chain(site_id, chain_id, status_data, trajectory):
    run_dir = RUNS_DIR / site_id / chain_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "status.json").write_text(json.dumps(status_data, indent=2))
    (run_dir / "trajectory.json").write_text(json.dumps(trajectory, indent=2))


def make_obs(step, url, title, summary):
    return {"type": "observation", "step": step, "url": url, "title": title, "ax_tree_summary": summary}


def make_act(step, macro, action_type, url, description):
    return {"type": "action", "step": step, "macro": macro, "action_type": action_type, "url": url, "description": description}


def reset():
    cw.do_reset()


def get_page(url):
    return cw.do_get(url)


def post_form(url, data):
    return cw.do_post(url, data)


def post_json(url, data):
    return cw.do_post_json(url, data)


def get_api(url):
    return cw.do_get_api(url)


def obs_from_result(step, result):
    ax = result.get("ax_tree", {})
    title = ax.get("title", "")
    headings = [h["text"] for h in ax.get("headings", [])[:3]]
    forms = [f"Form: {f['action']} ({f['method']})" for f in ax.get("forms", [])[:2]]
    tables_s = [f"Table: {' | '.join(t['headers'][:5])}" for t in ax.get("tables", [])[:2]]
    links_s = [f"[{l['text'][:30]}]->{l['href']}" for l in ax.get("links", [])[:5]]
    text_s = [t[:80] for t in ax.get("text", [])[:3]]
    summary = "; ".join(filter(None, [
        f"Headings: {', '.join(headings)}" if headings else "",
        "; ".join(forms) if forms else "",
        "; ".join(tables_s) if tables_s else "",
        f"Links: {', '.join(links_s)}" if links_s else "",
        f"Text: {' | '.join(text_s)}" if text_s else "",
    ]))
    return make_obs(step, result.get("url", ""), title, summary[:500])


# =====================================================================
# BOOKS-COMICS CHAIN WALKERS
# =====================================================================

BC = "/sites/books-comics"


def bc_login():
    """Login and return user_id."""
    post_form(f"{BC}/login", {"username": "comic_fan_alice", "password": "pass123"})
    return 1


def bc_get_books_api(limit=5):
    r = get_api(f"{BC}/api/books?limit={limit}")
    return r.get("response", [])


def bc_walk_sort_by_ranking(chain_id):
    """sort_by_ranking: Sort books by rating on the homepage."""
    reset()
    traj = []
    s = 0
    r = get_page(f"{BC}/")
    traj.append(obs_from_result(s, r))
    s += 1
    traj.append(make_act(s, "sort_by_ranking", "get", f"{BC}/?sort=rating", "Sort books by rating (highest first)"))
    r = get_page(f"{BC}/?sort=rating")
    traj.append(obs_from_result(s, r))
    save_chain("books-comics", chain_id, {"chain_id": chain_id, "site": "books-comics", "valid": True, "macros_completed": ["sort_by_ranking"]}, traj)


def bc_walk_follow_by_toggle(chain_id):
    """follow_by_toggle: Follow an author on a book page."""
    reset()
    traj = []
    s = 0
    bc_login()
    r = get_page(f"{BC}/book/1")
    traj.append(obs_from_result(s, r))
    books = bc_get_books_api(3)
    author = books[0]["authors"][0] if books else "Active Learning Network"
    s += 1
    traj.append(make_act(s, "follow_by_toggle", "post", f"{BC}/book/1/follow", f"Toggle follow author '{author}'"))
    r = post_form(f"{BC}/book/1/follow", {"author": author})
    traj.append(obs_from_result(s, r))
    save_chain("books-comics", chain_id, {"chain_id": chain_id, "site": "books-comics", "valid": True, "macros_completed": ["follow_by_toggle"]}, traj)


def bc_walk_search_by_semantic(chain_id):
    """search_by_semantic: Semantic search for books."""
    reset()
    traj = []
    s = 0
    r = get_page(f"{BC}/")
    traj.append(obs_from_result(s, r))
    s += 1
    q = "biology science"
    traj.append(make_act(s, "search_by_semantic", "get", f"{BC}/api/books/semantic?q={q}", f"Semantic search for '{q}'"))
    r = get_api(f"{BC}/api/books/semantic?q={q}")
    traj.append(make_obs(s, f"{BC}/api/books/semantic?q={q}", "API: Semantic Search Results", f"Returned results for '{q}'"))
    save_chain("books-comics", chain_id, {"chain_id": chain_id, "site": "books-comics", "valid": True, "macros_completed": ["search_by_semantic"]}, traj)


def bc_walk_checkout_by_form(chain_id):
    """checkout_by_form: Add item to cart and checkout."""
    reset()
    traj = []
    s = 0
    bc_login()
    # Add book to cart
    post_form(f"{BC}/book/2/cart", {})
    r = get_page(f"{BC}/checkout")
    traj.append(obs_from_result(s, r))
    s += 1
    traj.append(make_act(s, "checkout_by_form", "post", f"{BC}/checkout", "Submit checkout form with name, email, card"))
    r = post_form(f"{BC}/checkout", {"name": "Alice Chen", "email": "alice.chen@example.com", "card": "4111111111111111"})
    traj.append(obs_from_result(s, r))
    save_chain("books-comics", chain_id, {"chain_id": chain_id, "site": "books-comics", "valid": True, "macros_completed": ["checkout_by_form"]}, traj)


def bc_walk_play_by_playback(chain_id):
    """play_by_playback: Track reading progress."""
    reset()
    traj = []
    s = 0
    bc_login()
    r = get_page(f"{BC}/book/1/read")
    traj.append(obs_from_result(s, r))
    s += 1
    traj.append(make_act(s, "play_by_playback", "post", f"{BC}/api/users/1/reading-progress", "Update reading progress for book 1, chapter 2, 50%"))
    r = post_json(f"{BC}/api/users/1/reading-progress", {"book_id": 1, "chapter": 2, "progress": 50})
    traj.append(make_obs(s, f"{BC}/api/users/1/reading-progress", "API: Reading Progress", f"Response: {json.dumps(r.get('response', {}))[:200]}"))
    save_chain("books-comics", chain_id, {"chain_id": chain_id, "site": "books-comics", "valid": True, "macros_completed": ["play_by_playback"]}, traj)


def bc_walk_select_by_dropdown(chain_id):
    """select_by_dropdown: Select a category from dropdown."""
    reset()
    traj = []
    s = 0
    r = get_page(f"{BC}/")
    traj.append(obs_from_result(s, r))
    s += 1
    traj.append(make_act(s, "select_by_dropdown", "get", f"{BC}/?category=science", "Select 'Science & Technology' from category dropdown"))
    r = get_page(f"{BC}/?category=science")
    traj.append(obs_from_result(s, r))
    save_chain("books-comics", chain_id, {"chain_id": chain_id, "site": "books-comics", "valid": True, "macros_completed": ["select_by_dropdown"]}, traj)


def bc_walk_navigate_by_route(chain_id):
    """navigate_by_route: Navigate to the dashboard."""
    reset()
    traj = []
    s = 0
    bc_login()
    r = get_page(f"{BC}/")
    traj.append(obs_from_result(s, r))
    s += 1
    traj.append(make_act(s, "navigate_by_route", "get", f"{BC}/dashboard", "Navigate to My Library dashboard"))
    r = get_page(f"{BC}/dashboard")
    traj.append(obs_from_result(s, r))
    save_chain("books-comics", chain_id, {"chain_id": chain_id, "site": "books-comics", "valid": True, "macros_completed": ["navigate_by_route"]}, traj)


def bc_walk_play_by_route(chain_id):
    """play_by_route: Navigate to the reader for a specific book."""
    reset()
    traj = []
    s = 0
    r = get_page(f"{BC}/book/1")
    traj.append(obs_from_result(s, r))
    s += 1
    traj.append(make_act(s, "play_by_route", "get", f"{BC}/book/1/read?chapter=2", "Open reader for book 1, chapter 2"))
    r = get_page(f"{BC}/book/1/read?chapter=2")
    traj.append(obs_from_result(s, r))
    save_chain("books-comics", chain_id, {"chain_id": chain_id, "site": "books-comics", "valid": True, "macros_completed": ["play_by_route"]}, traj)


def bc_walk_navigate_by_dropdown(chain_id):
    """navigate_by_dropdown: Navigate to a category page via dropdown."""
    reset()
    traj = []
    s = 0
    r = get_page(f"{BC}/")
    traj.append(obs_from_result(s, r))
    s += 1
    traj.append(make_act(s, "navigate_by_dropdown", "get", f"{BC}/category/fiction", "Select 'Fiction' from categories dropdown nav"))
    r = get_page(f"{BC}/category/fiction")
    traj.append(obs_from_result(s, r))
    save_chain("books-comics", chain_id, {"chain_id": chain_id, "site": "books-comics", "valid": True, "macros_completed": ["navigate_by_dropdown"]}, traj)


def bc_walk_subscribe_by_toggle(chain_id):
    """subscribe_by_toggle: Subscribe to a category."""
    reset()
    traj = []
    s = 0
    bc_login()
    r = get_page(f"{BC}/book/1")
    traj.append(obs_from_result(s, r))
    s += 1
    cat = "humanities"
    traj.append(make_act(s, "subscribe_by_toggle", "post", f"{BC}/book/1/subscribe", f"Subscribe to category '{cat}'"))
    r = post_form(f"{BC}/book/1/subscribe", {"category": cat})
    traj.append(obs_from_result(s, r))
    save_chain("books-comics", chain_id, {"chain_id": chain_id, "site": "books-comics", "valid": True, "macros_completed": ["subscribe_by_toggle"]}, traj)


def bc_walk_save_by_toggle(chain_id):
    """save_by_toggle: Save a book to library."""
    reset()
    traj = []
    s = 0
    bc_login()
    r = get_page(f"{BC}/book/3")
    traj.append(obs_from_result(s, r))
    s += 1
    traj.append(make_act(s, "save_by_toggle", "post", f"{BC}/book/3/save", "Toggle save book 3 to library"))
    r = post_form(f"{BC}/book/3/save", {})
    traj.append(obs_from_result(s, r))
    save_chain("books-comics", chain_id, {"chain_id": chain_id, "site": "books-comics", "valid": True, "macros_completed": ["save_by_toggle"]}, traj)


def bc_walk_post_from_free_text(chain_id):
    """post_from_free_text: Post a review with free text."""
    reset()
    traj = []
    s = 0
    bc_login()
    r = get_page(f"{BC}/book/2")
    traj.append(obs_from_result(s, r))
    s += 1
    traj.append(make_act(s, "post_from_free_text", "post", f"{BC}/book/2/review", "Submit review with text and rating"))
    r = post_form(f"{BC}/book/2/review", {"text": "An excellent introductory resource on English pronunciation. Very well organized.", "rating": "4"})
    traj.append(obs_from_result(s, r))
    save_chain("books-comics", chain_id, {"chain_id": chain_id, "site": "books-comics", "valid": True, "macros_completed": ["post_from_free_text"]}, traj)


def bc_walk_filter_by_dropdown(chain_id):
    """filter_by_dropdown: Filter books by category dropdown."""
    reset()
    traj = []
    s = 0
    r = get_page(f"{BC}/")
    traj.append(obs_from_result(s, r))
    s += 1
    traj.append(make_act(s, "filter_by_dropdown", "get", f"{BC}/?category=health", "Filter books by 'Health & Medicine' category"))
    r = get_page(f"{BC}/?category=health")
    traj.append(obs_from_result(s, r))
    save_chain("books-comics", chain_id, {"chain_id": chain_id, "site": "books-comics", "valid": True, "macros_completed": ["filter_by_dropdown"]}, traj)


def bc_walk_rate_by_slider(chain_id):
    """rate_by_slider: Rate a book."""
    reset()
    traj = []
    s = 0
    bc_login()
    r = get_page(f"{BC}/book/5")
    traj.append(obs_from_result(s, r))
    s += 1
    traj.append(make_act(s, "rate_by_slider", "post", f"{BC}/book/5/rate", "Rate book 5 with 4 stars"))
    r = post_form(f"{BC}/book/5/rate", {"rating": "4"})
    traj.append(obs_from_result(s, r))
    save_chain("books-comics", chain_id, {"chain_id": chain_id, "site": "books-comics", "valid": True, "macros_completed": ["rate_by_slider"]}, traj)


def bc_walk_add_by_button(chain_id):
    """add_by_button: Add a book to cart."""
    reset()
    traj = []
    s = 0
    bc_login()
    r = get_page(f"{BC}/book/4")
    traj.append(obs_from_result(s, r))
    s += 1
    traj.append(make_act(s, "add_by_button", "post", f"{BC}/book/4/cart", "Add book 4 to shopping cart"))
    r = post_form(f"{BC}/book/4/cart", {})
    traj.append(obs_from_result(s, r))
    save_chain("books-comics", chain_id, {"chain_id": chain_id, "site": "books-comics", "valid": True, "macros_completed": ["add_by_button"]}, traj)


def bc_walk_filter_by_slider(chain_id):
    """filter_by_slider: Filter books by minimum rating."""
    reset()
    traj = []
    s = 0
    r = get_page(f"{BC}/")
    traj.append(obs_from_result(s, r))
    s += 1
    traj.append(make_act(s, "filter_by_slider", "get", f"{BC}/?min_rating=4", "Filter books with minimum rating 4.0"))
    r = get_page(f"{BC}/?min_rating=4")
    traj.append(obs_from_result(s, r))
    save_chain("books-comics", chain_id, {"chain_id": chain_id, "site": "books-comics", "valid": True, "macros_completed": ["filter_by_slider"]}, traj)


def bc_walk_extract_by_route(chain_id):
    """extract_by_route: Extract book details from an API route."""
    reset()
    traj = []
    s = 0
    r = get_page(f"{BC}/book/1")
    traj.append(obs_from_result(s, r))
    s += 1
    traj.append(make_act(s, "extract_by_route", "get", f"{BC}/api/books/1", "Extract book 1 details via API"))
    r = get_api(f"{BC}/api/books/1")
    traj.append(make_obs(s, f"{BC}/api/books/1", "API: Book Details", f"Book 1 data retrieved: {str(r.get('response_text', ''))[:200]}"))
    save_chain("books-comics", chain_id, {"chain_id": chain_id, "site": "books-comics", "valid": True, "macros_completed": ["extract_by_route"]}, traj)


def bc_walk_react_by_toggle(chain_id):
    """react_by_toggle: React to a review."""
    reset()
    traj = []
    s = 0
    bc_login()
    # Post a review first
    post_form(f"{BC}/book/1/review", {"text": "Great book for learners.", "rating": "5"})
    r = get_page(f"{BC}/book/1")
    traj.append(obs_from_result(s, r))
    s += 1
    traj.append(make_act(s, "react_by_toggle", "post", f"{BC}/book/1/react", "React 'like' to review 1"))
    r = post_form(f"{BC}/book/1/react", {"review_id": "1", "reaction": "like"})
    traj.append(obs_from_result(s, r))
    save_chain("books-comics", chain_id, {"chain_id": chain_id, "site": "books-comics", "valid": True, "macros_completed": ["react_by_toggle"]}, traj)


def bc_walk_search_by_query(chain_id):
    """search_by_query: Search books by keyword query."""
    reset()
    traj = []
    s = 0
    r = get_page(f"{BC}/")
    traj.append(obs_from_result(s, r))
    s += 1
    q = "calculus"
    traj.append(make_act(s, "search_by_query", "get", f"{BC}/?q={q}", f"Search for '{q}' using search form"))
    r = get_page(f"{BC}/?q={q}")
    traj.append(obs_from_result(s, r))
    save_chain("books-comics", chain_id, {"chain_id": chain_id, "site": "books-comics", "valid": True, "macros_completed": ["search_by_query"]}, traj)


# =====================================================================
# BOOKS-COMICS MEDIUM CHAINS
# =====================================================================

def bc_walk_medium_001(chain_id):
    """filter_by_dropdown, navigate_by_dropdown, select_by_dropdown"""
    reset()
    traj = []
    s = 0
    r = get_page(f"{BC}/")
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "filter_by_dropdown", "get", f"{BC}/?category=science", "Filter by Science category"))
    r = get_page(f"{BC}/?category=science")
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "navigate_by_dropdown", "get", f"{BC}/category/arts", "Navigate to Arts category page"))
    r = get_page(f"{BC}/category/arts")
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "select_by_dropdown", "get", f"{BC}/?category=business&sort=rating", "Select Business category with rating sort"))
    r = get_page(f"{BC}/?category=business&sort=rating")
    traj.append(obs_from_result(s, r))

    save_chain("books-comics", chain_id, {"chain_id": chain_id, "site": "books-comics", "valid": True, "macros_completed": ["filter_by_dropdown", "navigate_by_dropdown", "select_by_dropdown"]}, traj)


def bc_walk_medium_002(chain_id):
    """add_by_button, rate_by_slider, subscribe_by_toggle"""
    reset()
    traj = []
    s = 0
    bc_login()
    r = get_page(f"{BC}/book/3")
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "add_by_button", "post", f"{BC}/book/3/cart", "Add book 3 to cart"))
    r = post_form(f"{BC}/book/3/cart", {})
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "rate_by_slider", "post", f"{BC}/book/3/rate", "Rate book 3 with 5 stars"))
    r = post_form(f"{BC}/book/3/rate", {"rating": "5"})
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "subscribe_by_toggle", "post", f"{BC}/book/3/subscribe", "Subscribe to science category"))
    r = post_form(f"{BC}/book/3/subscribe", {"category": "science"})
    traj.append(obs_from_result(s, r))

    save_chain("books-comics", chain_id, {"chain_id": chain_id, "site": "books-comics", "valid": True, "macros_completed": ["add_by_button", "rate_by_slider", "subscribe_by_toggle"]}, traj)


def bc_walk_medium_003(chain_id):
    """add_by_button, extract_by_route, select_by_dropdown"""
    reset()
    traj = []
    s = 0
    bc_login()
    r = get_page(f"{BC}/")
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "add_by_button", "post", f"{BC}/book/5/cart", "Add book 5 to cart"))
    r = post_form(f"{BC}/book/5/cart", {})
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "extract_by_route", "get", f"{BC}/api/books/5", "Extract book 5 details via API"))
    r = get_api(f"{BC}/api/books/5")
    traj.append(make_obs(s, f"{BC}/api/books/5", "API: Book 5 Details", f"Retrieved: {str(r.get('response_text',''))[:200]}"))

    s += 1
    traj.append(make_act(s, "select_by_dropdown", "get", f"{BC}/?category=education", "Select Education category"))
    r = get_page(f"{BC}/?category=education")
    traj.append(obs_from_result(s, r))

    save_chain("books-comics", chain_id, {"chain_id": chain_id, "site": "books-comics", "valid": True, "macros_completed": ["add_by_button", "extract_by_route", "select_by_dropdown"]}, traj)


def bc_walk_medium_004(chain_id):
    """post_from_free_text, react_by_toggle, search_by_query"""
    reset()
    traj = []
    s = 0
    bc_login()
    r = get_page(f"{BC}/")
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "post_from_free_text", "post", f"{BC}/book/1/review", "Post a review for book 1"))
    r = post_form(f"{BC}/book/1/review", {"text": "Very insightful work on active learning techniques.", "rating": "4"})
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "react_by_toggle", "post", f"{BC}/book/1/react", "React to review with 'like'"))
    r = post_form(f"{BC}/book/1/react", {"review_id": "1", "reaction": "like"})
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "search_by_query", "get", f"{BC}/?q=literature", "Search for 'literature'"))
    r = get_page(f"{BC}/?q=literature")
    traj.append(obs_from_result(s, r))

    save_chain("books-comics", chain_id, {"chain_id": chain_id, "site": "books-comics", "valid": True, "macros_completed": ["post_from_free_text", "react_by_toggle", "search_by_query"]}, traj)


def bc_walk_medium_005(chain_id):
    """play_by_route, search_by_query, search_by_semantic"""
    reset()
    traj = []
    s = 0
    r = get_page(f"{BC}/")
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "play_by_route", "get", f"{BC}/book/3/read?chapter=1", "Open reader for book 3 chapter 1"))
    r = get_page(f"{BC}/book/3/read?chapter=1")
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "search_by_query", "get", f"{BC}/?q=biology", "Search for 'biology'"))
    r = get_page(f"{BC}/?q=biology")
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "search_by_semantic", "get", f"{BC}/api/books/semantic?q=plant+kingdom+science", "Semantic search for plant kingdom science"))
    r = get_api(f"{BC}/api/books/semantic?q=plant+kingdom+science")
    traj.append(make_obs(s, f"{BC}/api/books/semantic?q=plant+kingdom+science", "API: Semantic Results", f"Results: {str(r.get('response_text',''))[:200]}"))

    save_chain("books-comics", chain_id, {"chain_id": chain_id, "site": "books-comics", "valid": True, "macros_completed": ["play_by_route", "search_by_query", "search_by_semantic"]}, traj)


def bc_walk_medium_006(chain_id):
    """extract_by_route, filter_by_dropdown, select_by_dropdown"""
    reset()
    traj = []
    s = 0
    r = get_page(f"{BC}/")
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "extract_by_route", "get", f"{BC}/api/categories", "Extract all categories via API"))
    r = get_api(f"{BC}/api/categories")
    traj.append(make_obs(s, f"{BC}/api/categories", "API: Categories", f"Categories: {str(r.get('response_text',''))[:200]}"))

    s += 1
    traj.append(make_act(s, "filter_by_dropdown", "get", f"{BC}/?category=reference", "Filter by Reference category"))
    r = get_page(f"{BC}/?category=reference")
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "select_by_dropdown", "get", f"{BC}/?category=fiction&sort=title", "Select Fiction with title sort"))
    r = get_page(f"{BC}/?category=fiction&sort=title")
    traj.append(obs_from_result(s, r))

    save_chain("books-comics", chain_id, {"chain_id": chain_id, "site": "books-comics", "valid": True, "macros_completed": ["extract_by_route", "filter_by_dropdown", "select_by_dropdown"]}, traj)


def bc_walk_medium_007(chain_id):
    """checkout_by_form, follow_by_toggle, subscribe_by_toggle"""
    reset()
    traj = []
    s = 0
    bc_login()
    post_form(f"{BC}/book/2/cart", {})
    r = get_page(f"{BC}/book/2")
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "checkout_by_form", "post", f"{BC}/checkout", "Checkout with payment details"))
    r = post_form(f"{BC}/checkout", {"name": "Alice Chen", "email": "alice.chen@example.com", "card": "4111111111111111"})
    traj.append(obs_from_result(s, r))

    s += 1
    books = bc_get_books_api(3)
    author = books[1]["authors"][0] if len(books) > 1 else "Allison Muir"
    traj.append(make_act(s, "follow_by_toggle", "post", f"{BC}/book/2/follow", f"Follow author '{author}'"))
    r = post_form(f"{BC}/book/2/follow", {"author": author})
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "subscribe_by_toggle", "post", f"{BC}/book/2/subscribe", "Subscribe to reference category"))
    r = post_form(f"{BC}/book/2/subscribe", {"category": "reference"})
    traj.append(obs_from_result(s, r))

    save_chain("books-comics", chain_id, {"chain_id": chain_id, "site": "books-comics", "valid": True, "macros_completed": ["checkout_by_form", "follow_by_toggle", "subscribe_by_toggle"]}, traj)


def bc_walk_medium_008(chain_id):
    """add_by_button, extract_by_route, filter_by_slider"""
    reset()
    traj = []
    s = 0
    bc_login()
    r = get_page(f"{BC}/")
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "add_by_button", "post", f"{BC}/book/7/cart", "Add book 7 to cart"))
    r = post_form(f"{BC}/book/7/cart", {})
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "extract_by_route", "get", f"{BC}/api/stats", "Extract overall stats via API"))
    r = get_api(f"{BC}/api/stats")
    traj.append(make_obs(s, f"{BC}/api/stats", "API: Stats", f"Stats: {str(r.get('response_text',''))[:200]}"))

    s += 1
    traj.append(make_act(s, "filter_by_slider", "get", f"{BC}/?min_rating=3.5", "Filter books with min rating 3.5"))
    r = get_page(f"{BC}/?min_rating=3.5")
    traj.append(obs_from_result(s, r))

    save_chain("books-comics", chain_id, {"chain_id": chain_id, "site": "books-comics", "valid": True, "macros_completed": ["add_by_button", "extract_by_route", "filter_by_slider"]}, traj)


def bc_walk_medium_009(chain_id):
    """navigate_by_dropdown, navigate_by_route, play_by_route"""
    reset()
    traj = []
    s = 0
    bc_login()
    r = get_page(f"{BC}/")
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "navigate_by_dropdown", "get", f"{BC}/category/humanities", "Navigate to Humanities category"))
    r = get_page(f"{BC}/category/humanities")
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "navigate_by_route", "get", f"{BC}/book/1", "Navigate to book 1 detail page"))
    r = get_page(f"{BC}/book/1")
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "play_by_route", "get", f"{BC}/book/1/read?chapter=1", "Open reader for book 1"))
    r = get_page(f"{BC}/book/1/read?chapter=1")
    traj.append(obs_from_result(s, r))

    save_chain("books-comics", chain_id, {"chain_id": chain_id, "site": "books-comics", "valid": True, "macros_completed": ["navigate_by_dropdown", "navigate_by_route", "play_by_route"]}, traj)


def bc_walk_medium_010(chain_id):
    """play_by_route, react_by_toggle, save_by_toggle"""
    reset()
    traj = []
    s = 0
    bc_login()
    post_form(f"{BC}/book/2/review", {"text": "Helpful pronunciation guide.", "rating": "4"})
    r = get_page(f"{BC}/book/2")
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "play_by_route", "get", f"{BC}/book/2/read", "Open reader for book 2"))
    r = get_page(f"{BC}/book/2/read")
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "react_by_toggle", "post", f"{BC}/book/2/react", "React 'like' to review"))
    r = post_form(f"{BC}/book/2/react", {"review_id": "1", "reaction": "like"})
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "save_by_toggle", "post", f"{BC}/book/2/save", "Save book 2 to library"))
    r = post_form(f"{BC}/book/2/save", {})
    traj.append(obs_from_result(s, r))

    save_chain("books-comics", chain_id, {"chain_id": chain_id, "site": "books-comics", "valid": True, "macros_completed": ["play_by_route", "react_by_toggle", "save_by_toggle"]}, traj)


def bc_walk_medium_011(chain_id):
    """extract_by_route, filter_by_slider, save_by_toggle"""
    reset()
    traj = []
    s = 0
    bc_login()
    r = get_page(f"{BC}/")
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "extract_by_route", "get", f"{BC}/api/categories/science/stats", "Extract science category stats"))
    r = get_api(f"{BC}/api/categories/science/stats")
    traj.append(make_obs(s, f"{BC}/api/categories/science/stats", "API: Science Stats", f"Stats: {str(r.get('response_text',''))[:200]}"))

    s += 1
    traj.append(make_act(s, "filter_by_slider", "get", f"{BC}/?min_rating=4.5", "Filter books with min rating 4.5"))
    r = get_page(f"{BC}/?min_rating=4.5")
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "save_by_toggle", "post", f"{BC}/book/10/save", "Save book 10"))
    r = post_form(f"{BC}/book/10/save", {})
    traj.append(obs_from_result(s, r))

    save_chain("books-comics", chain_id, {"chain_id": chain_id, "site": "books-comics", "valid": True, "macros_completed": ["extract_by_route", "filter_by_slider", "save_by_toggle"]}, traj)


def bc_walk_medium_012(chain_id):
    """extract_by_route, navigate_by_route, subscribe_by_toggle"""
    reset()
    traj = []
    s = 0
    bc_login()
    r = get_page(f"{BC}/")
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "extract_by_route", "get", f"{BC}/api/books/8", "Extract book 8 details"))
    r = get_api(f"{BC}/api/books/8")
    traj.append(make_obs(s, f"{BC}/api/books/8", "API: Book 8", f"Data: {str(r.get('response_text',''))[:200]}"))

    s += 1
    traj.append(make_act(s, "navigate_by_route", "get", f"{BC}/book/8", "Navigate to book 8 detail page"))
    r = get_page(f"{BC}/book/8")
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "subscribe_by_toggle", "post", f"{BC}/book/8/subscribe", "Subscribe to book 8's category"))
    r = post_form(f"{BC}/book/8/subscribe", {"category": "fiction"})
    traj.append(obs_from_result(s, r))

    save_chain("books-comics", chain_id, {"chain_id": chain_id, "site": "books-comics", "valid": True, "macros_completed": ["extract_by_route", "navigate_by_route", "subscribe_by_toggle"]}, traj)


def bc_walk_medium_013(chain_id):
    """filter_by_slider, post_from_free_text, react_by_toggle"""
    reset()
    traj = []
    s = 0
    bc_login()
    post_form(f"{BC}/book/4/review", {"text": "Beautiful art history content.", "rating": "5"})
    r = get_page(f"{BC}/")
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "filter_by_slider", "get", f"{BC}/?min_rating=3", "Filter with min rating 3"))
    r = get_page(f"{BC}/?min_rating=3")
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "post_from_free_text", "post", f"{BC}/book/6/review", "Post review for book 6"))
    r = post_form(f"{BC}/book/6/review", {"text": "A comprehensive anthology of American literature. Well curated.", "rating": "4"})
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "react_by_toggle", "post", f"{BC}/book/4/react", "React to review on book 4"))
    r = post_form(f"{BC}/book/4/react", {"review_id": "1", "reaction": "like"})
    traj.append(obs_from_result(s, r))

    save_chain("books-comics", chain_id, {"chain_id": chain_id, "site": "books-comics", "valid": True, "macros_completed": ["filter_by_slider", "post_from_free_text", "react_by_toggle"]}, traj)


def bc_walk_medium_014(chain_id):
    """add_by_button, checkout_by_form, rate_by_slider"""
    reset()
    traj = []
    s = 0
    bc_login()
    r = get_page(f"{BC}/book/10")
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "add_by_button", "post", f"{BC}/book/10/cart", "Add book 10 to cart"))
    r = post_form(f"{BC}/book/10/cart", {})
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "checkout_by_form", "post", f"{BC}/checkout", "Checkout with payment"))
    r = post_form(f"{BC}/checkout", {"name": "Alice Chen", "email": "alice.chen@example.com", "card": "4111111111111111"})
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "rate_by_slider", "post", f"{BC}/book/10/rate", "Rate book 10 with 3 stars"))
    r = post_form(f"{BC}/book/10/rate", {"rating": "3"})
    traj.append(obs_from_result(s, r))

    save_chain("books-comics", chain_id, {"chain_id": chain_id, "site": "books-comics", "valid": True, "macros_completed": ["add_by_button", "checkout_by_form", "rate_by_slider"]}, traj)


def bc_walk_medium_015(chain_id):
    """filter_by_slider, navigate_by_dropdown, search_by_semantic"""
    reset()
    traj = []
    s = 0
    r = get_page(f"{BC}/")
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "filter_by_slider", "get", f"{BC}/?min_rating=4", "Filter with min rating 4"))
    r = get_page(f"{BC}/?min_rating=4")
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "navigate_by_dropdown", "get", f"{BC}/category/education", "Navigate to Education category"))
    r = get_page(f"{BC}/category/education")
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "search_by_semantic", "get", f"{BC}/api/books/semantic?q=teaching+pedagogy", "Semantic search for teaching pedagogy"))
    r = get_api(f"{BC}/api/books/semantic?q=teaching+pedagogy")
    traj.append(make_obs(s, f"{BC}/api/books/semantic?q=teaching+pedagogy", "API: Semantic Results", f"Results: {str(r.get('response_text',''))[:200]}"))

    save_chain("books-comics", chain_id, {"chain_id": chain_id, "site": "books-comics", "valid": True, "macros_completed": ["filter_by_slider", "navigate_by_dropdown", "search_by_semantic"]}, traj)


def bc_walk_medium_016(chain_id):
    """checkout_by_form, rate_by_slider, search_by_semantic"""
    reset()
    traj = []
    s = 0
    bc_login()
    post_form(f"{BC}/book/5/cart", {})
    r = get_page(f"{BC}/book/5")
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "checkout_by_form", "post", f"{BC}/checkout", "Checkout"))
    r = post_form(f"{BC}/checkout", {"name": "Alice Chen", "email": "alice.chen@example.com", "card": "4111111111111111"})
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "rate_by_slider", "post", f"{BC}/book/5/rate", "Rate book 5"))
    r = post_form(f"{BC}/book/5/rate", {"rating": "5"})
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "search_by_semantic", "get", f"{BC}/api/books/semantic?q=government+politics", "Semantic search government politics"))
    r = get_api(f"{BC}/api/books/semantic?q=government+politics")
    traj.append(make_obs(s, f"{BC}/api/books/semantic?q=government+politics", "API: Semantic Results", f"Results: {str(r.get('response_text',''))[:200]}"))

    save_chain("books-comics", chain_id, {"chain_id": chain_id, "site": "books-comics", "valid": True, "macros_completed": ["checkout_by_form", "rate_by_slider", "search_by_semantic"]}, traj)


def bc_walk_medium_017(chain_id):
    """search_by_query, search_by_semantic, subscribe_by_toggle"""
    reset()
    traj = []
    s = 0
    bc_login()
    r = get_page(f"{BC}/")
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "search_by_query", "get", f"{BC}/?q=chemistry", "Search for chemistry"))
    r = get_page(f"{BC}/?q=chemistry")
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "search_by_semantic", "get", f"{BC}/api/books/semantic?q=environmental+chemistry", "Semantic search for environmental chemistry"))
    r = get_api(f"{BC}/api/books/semantic?q=environmental+chemistry")
    traj.append(make_obs(s, f"{BC}/api/books/semantic?q=environmental+chemistry", "API: Semantic Results", f"Results: {str(r.get('response_text',''))[:200]}"))

    s += 1
    traj.append(make_act(s, "subscribe_by_toggle", "post", f"{BC}/book/15/subscribe", "Subscribe to science category from book 15"))
    r = post_form(f"{BC}/book/15/subscribe", {"category": "science"})
    traj.append(obs_from_result(s, r))

    save_chain("books-comics", chain_id, {"chain_id": chain_id, "site": "books-comics", "valid": True, "macros_completed": ["search_by_query", "search_by_semantic", "subscribe_by_toggle"]}, traj)


def bc_walk_medium_018(chain_id):
    """extract_by_route, navigate_by_route, rate_by_slider"""
    reset()
    traj = []
    s = 0
    bc_login()
    r = get_page(f"{BC}/")
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "extract_by_route", "get", f"{BC}/api/books/9", "Extract book 9 details"))
    r = get_api(f"{BC}/api/books/9")
    traj.append(make_obs(s, f"{BC}/api/books/9", "API: Book 9", f"Data: {str(r.get('response_text',''))[:200]}"))

    s += 1
    traj.append(make_act(s, "navigate_by_route", "get", f"{BC}/book/9", "Navigate to book 9"))
    r = get_page(f"{BC}/book/9")
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "rate_by_slider", "post", f"{BC}/book/9/rate", "Rate book 9 with 4 stars"))
    r = post_form(f"{BC}/book/9/rate", {"rating": "4"})
    traj.append(obs_from_result(s, r))

    save_chain("books-comics", chain_id, {"chain_id": chain_id, "site": "books-comics", "valid": True, "macros_completed": ["extract_by_route", "navigate_by_route", "rate_by_slider"]}, traj)


def bc_walk_medium_019(chain_id):
    """extract_by_route, post_from_free_text, search_by_query"""
    reset()
    traj = []
    s = 0
    bc_login()
    r = get_page(f"{BC}/")
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "extract_by_route", "get", f"{BC}/api/categories/humanities/stats", "Extract humanities stats"))
    r = get_api(f"{BC}/api/categories/humanities/stats")
    traj.append(make_obs(s, f"{BC}/api/categories/humanities/stats", "API: Humanities Stats", f"Stats: {str(r.get('response_text',''))[:200]}"))

    s += 1
    traj.append(make_act(s, "post_from_free_text", "post", f"{BC}/book/3/review", "Review book 3"))
    r = post_form(f"{BC}/book/3/review", {"text": "Great biology textbook. Clear explanations with good diagrams.", "rating": "4"})
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "search_by_query", "get", f"{BC}/?q=statistics", "Search for statistics"))
    r = get_page(f"{BC}/?q=statistics")
    traj.append(obs_from_result(s, r))

    save_chain("books-comics", chain_id, {"chain_id": chain_id, "site": "books-comics", "valid": True, "macros_completed": ["extract_by_route", "post_from_free_text", "search_by_query"]}, traj)


def bc_walk_medium_020(chain_id):
    """checkout_by_form, extract_by_route, search_by_query"""
    reset()
    traj = []
    s = 0
    bc_login()
    post_form(f"{BC}/book/7/cart", {})
    r = get_page(f"{BC}/")
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "checkout_by_form", "post", f"{BC}/checkout", "Checkout"))
    r = post_form(f"{BC}/checkout", {"name": "Alice Chen", "email": "alice.chen@example.com", "card": "4111111111111111"})
    traj.append(obs_from_result(s, r))

    s += 1
    traj.append(make_act(s, "extract_by_route", "get", f"{BC}/api/books/7", "Extract book 7 details"))
    r = get_api(f"{BC}/api/books/7")
    traj.append(make_obs(s, f"{BC}/api/books/7", "API: Book 7", f"Data: {str(r.get('response_text',''))[:200]}"))

    s += 1
    traj.append(make_act(s, "search_by_query", "get", f"{BC}/?q=geoscience", "Search for geoscience"))
    r = get_page(f"{BC}/?q=geoscience")
    traj.append(obs_from_result(s, r))

    save_chain("books-comics", chain_id, {"chain_id": chain_id, "site": "books-comics", "valid": True, "macros_completed": ["checkout_by_form", "extract_by_route", "search_by_query"]}, traj)


# =====================================================================
# BOOKS-COMICS HARD CHAINS
# =====================================================================

def bc_walk_hard_001(chain_id):
    """follow_by_toggle, play_by_playback, search_by_semantic, select_by_dropdown, subscribe_by_toggle"""
    reset()
    traj = []
    s = 0
    bc_login()
    r = get_page(f"{BC}/")
    traj.append(obs_from_result(s, r))

    s += 1; traj.append(make_act(s, "follow_by_toggle", "post", f"{BC}/book/1/follow", "Follow author")); r = post_form(f"{BC}/book/1/follow", {"author": "Active Learning Network"}); traj.append(obs_from_result(s, r))
    s += 1; traj.append(make_act(s, "play_by_playback", "post", f"{BC}/api/users/1/reading-progress", "Track reading progress")); r = post_json(f"{BC}/api/users/1/reading-progress", {"book_id": 1, "chapter": 3, "progress": 75}); traj.append(make_obs(s, f"{BC}/api/users/1/reading-progress", "API: Reading Progress", f"Response: {json.dumps(r.get('response',{}))[:200]}"))
    s += 1; traj.append(make_act(s, "search_by_semantic", "get", f"{BC}/api/books/semantic?q=active+learning+education", "Semantic search")); r = get_api(f"{BC}/api/books/semantic?q=active+learning+education"); traj.append(make_obs(s, f"{BC}/api/books/semantic?q=active+learning+education", "API: Semantic Results", f"Results retrieved"))
    s += 1; traj.append(make_act(s, "select_by_dropdown", "get", f"{BC}/?category=education", "Select Education")); r = get_page(f"{BC}/?category=education"); traj.append(obs_from_result(s, r))
    s += 1; traj.append(make_act(s, "subscribe_by_toggle", "post", f"{BC}/book/1/subscribe", "Subscribe to humanities")); r = post_form(f"{BC}/book/1/subscribe", {"category": "humanities"}); traj.append(obs_from_result(s, r))

    save_chain("books-comics", chain_id, {"chain_id": chain_id, "site": "books-comics", "valid": True, "macros_completed": ["follow_by_toggle", "play_by_playback", "search_by_semantic", "select_by_dropdown", "subscribe_by_toggle"]}, traj)


def bc_walk_hard_002(chain_id):
    """filter_by_dropdown, filter_by_slider, post_from_free_text, sort_by_ranking, subscribe_by_toggle"""
    reset()
    traj = []
    s = 0
    bc_login()
    r = get_page(f"{BC}/")
    traj.append(obs_from_result(s, r))

    s += 1; traj.append(make_act(s, "filter_by_dropdown", "get", f"{BC}/?category=science", "Filter by science")); r = get_page(f"{BC}/?category=science"); traj.append(obs_from_result(s, r))
    s += 1; traj.append(make_act(s, "filter_by_slider", "get", f"{BC}/?category=science&min_rating=3.5", "Filter with min rating 3.5")); r = get_page(f"{BC}/?category=science&min_rating=3.5"); traj.append(obs_from_result(s, r))
    s += 1; traj.append(make_act(s, "post_from_free_text", "post", f"{BC}/book/3/review", "Post review")); r = post_form(f"{BC}/book/3/review", {"text": "Solid biology textbook for beginners.", "rating": "4"}); traj.append(obs_from_result(s, r))
    s += 1; traj.append(make_act(s, "sort_by_ranking", "get", f"{BC}/?sort=rating", "Sort by rating")); r = get_page(f"{BC}/?sort=rating"); traj.append(obs_from_result(s, r))
    s += 1; traj.append(make_act(s, "subscribe_by_toggle", "post", f"{BC}/book/3/subscribe", "Subscribe to science")); r = post_form(f"{BC}/book/3/subscribe", {"category": "science"}); traj.append(obs_from_result(s, r))

    save_chain("books-comics", chain_id, {"chain_id": chain_id, "site": "books-comics", "valid": True, "macros_completed": ["filter_by_dropdown", "filter_by_slider", "post_from_free_text", "sort_by_ranking", "subscribe_by_toggle"]}, traj)


def bc_walk_hard_003(chain_id):
    """navigate_by_route, play_by_route, post_from_free_text, react_by_toggle, subscribe_by_toggle"""
    reset()
    traj = []
    s = 0
    bc_login()
    post_form(f"{BC}/book/5/review", {"text": "Good government text.", "rating": "4"})
    r = get_page(f"{BC}/")
    traj.append(obs_from_result(s, r))

    s += 1; traj.append(make_act(s, "navigate_by_route", "get", f"{BC}/book/5", "Navigate to book 5")); r = get_page(f"{BC}/book/5"); traj.append(obs_from_result(s, r))
    s += 1; traj.append(make_act(s, "play_by_route", "get", f"{BC}/book/5/read?chapter=1", "Read book 5")); r = get_page(f"{BC}/book/5/read?chapter=1"); traj.append(obs_from_result(s, r))
    s += 1; traj.append(make_act(s, "post_from_free_text", "post", f"{BC}/book/5/review", "Post review")); r = post_form(f"{BC}/book/5/review", {"text": "Excellent coverage of American government.", "rating": "5"}); traj.append(obs_from_result(s, r))
    s += 1; traj.append(make_act(s, "react_by_toggle", "post", f"{BC}/book/5/react", "React to review")); r = post_form(f"{BC}/book/5/react", {"review_id": "1", "reaction": "like"}); traj.append(obs_from_result(s, r))
    s += 1; traj.append(make_act(s, "subscribe_by_toggle", "post", f"{BC}/book/5/subscribe", "Subscribe")); r = post_form(f"{BC}/book/5/subscribe", {"category": "humanities"}); traj.append(obs_from_result(s, r))

    save_chain("books-comics", chain_id, {"chain_id": chain_id, "site": "books-comics", "valid": True, "macros_completed": ["navigate_by_route", "play_by_route", "post_from_free_text", "react_by_toggle", "subscribe_by_toggle"]}, traj)


def bc_walk_hard_004(chain_id):
    """checkout_by_form, follow_by_toggle, react_by_toggle, search_by_semantic, subscribe_by_toggle"""
    reset()
    traj = []
    s = 0
    bc_login()
    post_form(f"{BC}/book/4/cart", {})
    post_form(f"{BC}/book/4/review", {"text": "Amazing art history.", "rating": "5"})
    r = get_page(f"{BC}/book/4")
    traj.append(obs_from_result(s, r))

    s += 1; traj.append(make_act(s, "checkout_by_form", "post", f"{BC}/checkout", "Checkout")); r = post_form(f"{BC}/checkout", {"name": "Alice Chen", "email": "alice.chen@example.com", "card": "4111111111111111"}); traj.append(obs_from_result(s, r))
    s += 1; traj.append(make_act(s, "follow_by_toggle", "post", f"{BC}/book/4/follow", "Follow author")); r = post_form(f"{BC}/book/4/follow", {"author": "Karen Brown"}); traj.append(obs_from_result(s, r))
    s += 1; traj.append(make_act(s, "react_by_toggle", "post", f"{BC}/book/4/react", "React to review")); r = post_form(f"{BC}/book/4/react", {"review_id": "1", "reaction": "like"}); traj.append(obs_from_result(s, r))
    s += 1; traj.append(make_act(s, "search_by_semantic", "get", f"{BC}/api/books/semantic?q=art+architecture+history", "Semantic search")); r = get_api(f"{BC}/api/books/semantic?q=art+architecture+history"); traj.append(make_obs(s, f"{BC}/api/books/semantic?q=art+architecture+history", "API: Semantic Results", "Results retrieved"))
    s += 1; traj.append(make_act(s, "subscribe_by_toggle", "post", f"{BC}/book/4/subscribe", "Subscribe")); r = post_form(f"{BC}/book/4/subscribe", {"category": "arts"}); traj.append(obs_from_result(s, r))

    save_chain("books-comics", chain_id, {"chain_id": chain_id, "site": "books-comics", "valid": True, "macros_completed": ["checkout_by_form", "follow_by_toggle", "react_by_toggle", "search_by_semantic", "subscribe_by_toggle"]}, traj)


def bc_walk_hard_generic(chain_id, macros):
    """Generic handler for hard chains - maps macros to actions."""
    reset()
    traj = []
    s = 0
    bc_login()

    # Prep: add review for react, add cart item for checkout
    if "react_by_toggle" in macros:
        post_form(f"{BC}/book/6/review", {"text": "Good anthology.", "rating": "4"})
    if "checkout_by_form" in macros:
        post_form(f"{BC}/book/8/cart", {})

    r = get_page(f"{BC}/")
    traj.append(obs_from_result(s, r))

    book_ids = iter([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    for macro in macros:
        s += 1
        bid = next(book_ids, 1)
        if macro == "sort_by_ranking":
            traj.append(make_act(s, macro, "get", f"{BC}/?sort=rating", "Sort by rating"))
            r = get_page(f"{BC}/?sort=rating"); traj.append(obs_from_result(s, r))
        elif macro == "follow_by_toggle":
            traj.append(make_act(s, macro, "post", f"{BC}/book/{bid}/follow", "Follow author"))
            r = post_form(f"{BC}/book/{bid}/follow", {"author": "Active Learning Network"}); traj.append(obs_from_result(s, r))
        elif macro == "search_by_semantic":
            traj.append(make_act(s, macro, "get", f"{BC}/api/books/semantic?q=education+learning", "Semantic search"))
            r = get_api(f"{BC}/api/books/semantic?q=education+learning"); traj.append(make_obs(s, f"{BC}/api/books/semantic?q=education+learning", "API: Semantic Results", "Results retrieved"))
        elif macro == "checkout_by_form":
            traj.append(make_act(s, macro, "post", f"{BC}/checkout", "Checkout"))
            r = post_form(f"{BC}/checkout", {"name": "Alice Chen", "email": "alice.chen@example.com", "card": "4111111111111111"}); traj.append(obs_from_result(s, r))
        elif macro == "play_by_playback":
            traj.append(make_act(s, macro, "post", f"{BC}/api/users/1/reading-progress", "Track reading"))
            r = post_json(f"{BC}/api/users/1/reading-progress", {"book_id": bid, "chapter": 2, "progress": 60}); traj.append(make_obs(s, f"{BC}/api/users/1/reading-progress", "API: Reading Progress", f"Response: {json.dumps(r.get('response',{}))[:200]}"))
        elif macro == "select_by_dropdown":
            traj.append(make_act(s, macro, "get", f"{BC}/?category=education", "Select Education"))
            r = get_page(f"{BC}/?category=education"); traj.append(obs_from_result(s, r))
        elif macro == "navigate_by_route":
            traj.append(make_act(s, macro, "get", f"{BC}/book/{bid}", "Navigate to book"))
            r = get_page(f"{BC}/book/{bid}"); traj.append(obs_from_result(s, r))
        elif macro == "play_by_route":
            traj.append(make_act(s, macro, "get", f"{BC}/book/{bid}/read", "Open reader"))
            r = get_page(f"{BC}/book/{bid}/read"); traj.append(obs_from_result(s, r))
        elif macro == "navigate_by_dropdown":
            cats = ["fiction", "science", "humanities", "education", "health", "business", "arts"]
            cat = cats[s % len(cats)]
            traj.append(make_act(s, macro, "get", f"{BC}/category/{cat}", f"Navigate to {cat}"))
            r = get_page(f"{BC}/category/{cat}"); traj.append(obs_from_result(s, r))
        elif macro == "subscribe_by_toggle":
            traj.append(make_act(s, macro, "post", f"{BC}/book/{bid}/subscribe", "Subscribe to category"))
            r = post_form(f"{BC}/book/{bid}/subscribe", {"category": "science"}); traj.append(obs_from_result(s, r))
        elif macro == "save_by_toggle":
            traj.append(make_act(s, macro, "post", f"{BC}/book/{bid}/save", "Save book"))
            r = post_form(f"{BC}/book/{bid}/save", {}); traj.append(obs_from_result(s, r))
        elif macro == "post_from_free_text":
            traj.append(make_act(s, macro, "post", f"{BC}/book/{bid}/review", "Post review"))
            r = post_form(f"{BC}/book/{bid}/review", {"text": "Informative and well-written content.", "rating": "4"}); traj.append(obs_from_result(s, r))
        elif macro == "filter_by_dropdown":
            traj.append(make_act(s, macro, "get", f"{BC}/?category=arts", "Filter by arts"))
            r = get_page(f"{BC}/?category=arts"); traj.append(obs_from_result(s, r))
        elif macro == "rate_by_slider":
            traj.append(make_act(s, macro, "post", f"{BC}/book/{bid}/rate", "Rate book"))
            r = post_form(f"{BC}/book/{bid}/rate", {"rating": "4"}); traj.append(obs_from_result(s, r))
        elif macro == "add_by_button":
            traj.append(make_act(s, macro, "post", f"{BC}/book/{bid}/cart", "Add to cart"))
            r = post_form(f"{BC}/book/{bid}/cart", {}); traj.append(obs_from_result(s, r))
        elif macro == "filter_by_slider":
            traj.append(make_act(s, macro, "get", f"{BC}/?min_rating=3.5", "Filter min rating 3.5"))
            r = get_page(f"{BC}/?min_rating=3.5"); traj.append(obs_from_result(s, r))
        elif macro == "extract_by_route":
            traj.append(make_act(s, macro, "get", f"{BC}/api/books/{bid}", "Extract book data"))
            r = get_api(f"{BC}/api/books/{bid}"); traj.append(make_obs(s, f"{BC}/api/books/{bid}", "API: Book Details", f"Data: {str(r.get('response_text',''))[:200]}"))
        elif macro == "react_by_toggle":
            traj.append(make_act(s, macro, "post", f"{BC}/book/6/react", "React to review"))
            r = post_form(f"{BC}/book/6/react", {"review_id": "1", "reaction": "like"}); traj.append(obs_from_result(s, r))
        elif macro == "search_by_query":
            traj.append(make_act(s, macro, "get", f"{BC}/?q=history", "Search for history"))
            r = get_page(f"{BC}/?q=history"); traj.append(obs_from_result(s, r))

    save_chain("books-comics", chain_id, {"chain_id": chain_id, "site": "books-comics", "valid": True, "macros_completed": macros}, traj)


# =====================================================================
# CLOUD-DEV-CONSOLES CHAIN WALKERS
# =====================================================================

CDC = "/sites/cloud-dev-consoles"


def cdc_login():
    post_form(f"{CDC}/login", {"username": "admin_sarah", "password": "cloudpass1"})
    return 1


def cdc_walk_easy_generic(chain_id, macro):
    """Generic handler for single-macro cloud-dev-consoles chains."""
    reset()
    traj = []
    s = 0

    if macro in ("configure_by_query", "authenticate_by_form"):
        cdc_login()

    if macro == "select_by_dropdown":
        r = get_page(f"{CDC}/services")
        traj.append(obs_from_result(s, r))
        s += 1; traj.append(make_act(s, macro, "get", f"{CDC}/services?category=Compute", "Select Compute from category dropdown"))
        r = get_page(f"{CDC}/services?category=Compute"); traj.append(obs_from_result(s, r))

    elif macro == "configure_by_query":
        r = get_page(f"{CDC}/dashboard")
        traj.append(obs_from_result(s, r))
        s += 1; traj.append(make_act(s, macro, "post", f"{CDC}/api/users/1/preferences", "Configure default region preference"))
        r = post_json(f"{CDC}/api/users/1/preferences", {"default_region": "us-west-2"}); traj.append(make_obs(s, f"{CDC}/api/users/1/preferences", "API: Preferences Updated", f"Response: {json.dumps(r.get('response',{}))[:200]}"))

    elif macro == "extract_by_dropdown":
        r = get_page(f"{CDC}/billing")
        traj.append(obs_from_result(s, r))
        s += 1; traj.append(make_act(s, macro, "get", f"{CDC}/billing?month=2026-06", "Select billing month 2026-06 from dropdown"))
        r = get_page(f"{CDC}/billing?month=2026-06"); traj.append(obs_from_result(s, r))

    elif macro == "search_by_semantic":
        r = get_page(f"{CDC}/services")
        traj.append(obs_from_result(s, r))
        s += 1; traj.append(make_act(s, macro, "get", f"{CDC}/api/services/semantic?q=database+storage+persistent", "Semantic search services"))
        r = get_api(f"{CDC}/api/services/semantic?q=database+storage+persistent"); traj.append(make_obs(s, f"{CDC}/api/services/semantic?q=database+storage+persistent", "API: Semantic Results", f"Results: {str(r.get('response_text',''))[:200]}"))

    elif macro == "select_from_table":
        r = get_page(f"{CDC}/instances")
        traj.append(obs_from_result(s, r))
        s += 1; traj.append(make_act(s, macro, "get", f"{CDC}/instance/i-0a1b2c3d4e5f00003", "Select instance api-server-prod-1 from table"))
        r = get_page(f"{CDC}/instance/i-0a1b2c3d4e5f00003"); traj.append(obs_from_result(s, r))

    elif macro == "navigate_by_dropdown":
        r = get_page(f"{CDC}/")
        traj.append(obs_from_result(s, r))
        s += 1; traj.append(make_act(s, macro, "get", f"{CDC}/databases", "Navigate to Databases from nav dropdown"))
        r = get_page(f"{CDC}/databases"); traj.append(obs_from_result(s, r))

    elif macro == "extract_by_query":
        r = get_page(f"{CDC}/")
        traj.append(obs_from_result(s, r))
        s += 1; traj.append(make_act(s, macro, "get", f"{CDC}/api/billing/summary?month=2026-06", "Extract billing summary for June 2026"))
        r = get_api(f"{CDC}/api/billing/summary?month=2026-06"); traj.append(make_obs(s, f"{CDC}/api/billing/summary?month=2026-06", "API: Billing Summary", f"Data: {str(r.get('response_text',''))[:200]}"))

    elif macro == "verify_by_dropdown":
        r = get_page(f"{CDC}/alerts")
        traj.append(obs_from_result(s, r))
        s += 1; traj.append(make_act(s, macro, "get", f"{CDC}/alerts?severity=critical", "Filter alerts by critical severity to verify"))
        r = get_page(f"{CDC}/alerts?severity=critical"); traj.append(obs_from_result(s, r))

    elif macro == "compute_by_slider":
        r = get_page(f"{CDC}/metrics")
        traj.append(obs_from_result(s, r))
        s += 1; traj.append(make_act(s, macro, "get", f"{CDC}/api/metrics/summary?instance_id=i-0a1b2c3d4e5f00003", "Compute metrics summary for instance"))
        r = get_api(f"{CDC}/api/metrics/summary?instance_id=i-0a1b2c3d4e5f00003"); traj.append(make_obs(s, f"{CDC}/api/metrics/summary?instance_id=i-0a1b2c3d4e5f00003", "API: Metrics Summary", f"Data: {str(r.get('response_text',''))[:200]}"))

    elif macro == "filter_by_checkbox":
        r = get_page(f"{CDC}/instances")
        traj.append(obs_from_result(s, r))
        s += 1; traj.append(make_act(s, macro, "get", f"{CDC}/instances?status=running", "Filter instances by running status"))
        r = get_page(f"{CDC}/instances?status=running"); traj.append(obs_from_result(s, r))

    elif macro == "delete_from_table":
        r = get_page(f"{CDC}/alerts")
        traj.append(obs_from_result(s, r))
        s += 1; traj.append(make_act(s, macro, "post", f"{CDC}/api/alerts/alert-001/delete", "Delete alert-001 from alerts table"))
        r = post_json(f"{CDC}/api/alerts/alert-001/delete", {}); traj.append(make_obs(s, f"{CDC}/api/alerts/alert-001/delete", "API: Alert Deleted", f"Response: {json.dumps(r.get('response',{}))[:200]}"))

    elif macro == "search_by_query":
        r = get_page(f"{CDC}/services")
        traj.append(obs_from_result(s, r))
        s += 1; traj.append(make_act(s, macro, "get", f"{CDC}/services?q=database", "Search services for 'database'"))
        r = get_page(f"{CDC}/services?q=database"); traj.append(obs_from_result(s, r))

    elif macro == "export_by_dropdown":
        r = get_page(f"{CDC}/services")
        traj.append(obs_from_result(s, r))
        s += 1; traj.append(make_act(s, macro, "get", f"{CDC}/api/export?resource=services&format=csv", "Export services as CSV"))
        r = get_api(f"{CDC}/api/export?resource=services&format=csv"); traj.append(make_obs(s, f"{CDC}/api/export?resource=services&format=csv", "Export: CSV", f"CSV data: {str(r.get('response_text',''))[:200]}"))

    elif macro == "compute_by_extremum":
        r = get_page(f"{CDC}/")
        traj.append(obs_from_result(s, r))
        s += 1; traj.append(make_act(s, macro, "get", f"{CDC}/api/stats", "Get infrastructure stats to find extremes"))
        r = get_api(f"{CDC}/api/stats"); traj.append(make_obs(s, f"{CDC}/api/stats", "API: Stats", f"Stats: {str(r.get('response_text',''))[:200]}"))

    elif macro == "filter_by_dropdown":
        r = get_page(f"{CDC}/services")
        traj.append(obs_from_result(s, r))
        s += 1; traj.append(make_act(s, macro, "get", f"{CDC}/services?category=Database", "Filter services by Database category"))
        r = get_page(f"{CDC}/services?category=Database"); traj.append(obs_from_result(s, r))

    elif macro == "extract_from_table":
        r = get_page(f"{CDC}/instances")
        traj.append(obs_from_result(s, r))
        s += 1; traj.append(make_act(s, macro, "get", f"{CDC}/api/instances/i-0a1b2c3d4e5f00005", "Extract db-primary instance details"))
        r = get_api(f"{CDC}/api/instances/i-0a1b2c3d4e5f00005"); traj.append(make_obs(s, f"{CDC}/api/instances/i-0a1b2c3d4e5f00005", "API: Instance Details", f"Data: {str(r.get('response_text',''))[:200]}"))

    elif macro == "submit_by_query":
        r = get_page(f"{CDC}/alerts")
        traj.append(obs_from_result(s, r))
        s += 1; traj.append(make_act(s, macro, "post", f"{CDC}/api/alerts/create", "Create a new custom alert"))
        r = post_json(f"{CDC}/api/alerts/create", {"name": "High Memory Usage", "severity": "warning", "resource_name": "api-server-prod-1", "condition": "Memory > 90%", "category": "Compute"}); traj.append(make_obs(s, f"{CDC}/api/alerts/create", "API: Alert Created", f"Response: {json.dumps(r.get('response',{}))[:200]}"))

    elif macro == "sort_by_ranking":
        r = get_page(f"{CDC}/services")
        traj.append(obs_from_result(s, r))
        s += 1; traj.append(make_act(s, macro, "get", f"{CDC}/services?sort=cost", "Sort services by cost (highest first)"))
        r = get_page(f"{CDC}/services?sort=cost"); traj.append(obs_from_result(s, r))

    elif macro == "authenticate_by_form":
        r = get_page(f"{CDC}/login")
        traj.append(obs_from_result(s, r))
        s += 1; traj.append(make_act(s, macro, "post", f"{CDC}/login", "Login with admin_sarah credentials"))
        r = post_form(f"{CDC}/login", {"username": "admin_sarah", "password": "cloudpass1"}); traj.append(obs_from_result(s, r))

    elif macro == "extract_by_route":
        r = get_page(f"{CDC}/")
        traj.append(obs_from_result(s, r))
        s += 1; traj.append(make_act(s, macro, "get", f"{CDC}/api/services/svc-001", "Extract Compute Engine service details"))
        r = get_api(f"{CDC}/api/services/svc-001"); traj.append(make_obs(s, f"{CDC}/api/services/svc-001", "API: Service Details", f"Data: {str(r.get('response_text',''))[:200]}"))

    save_chain("cloud-dev-consoles", chain_id, {"chain_id": chain_id, "site": "cloud-dev-consoles", "valid": True, "macros_completed": [macro]}, traj)


def cdc_walk_multi_generic(chain_id, macros):
    """Generic handler for multi-macro cloud-dev-consoles chains."""
    reset()
    traj = []
    s = 0

    # Login if needed
    needs_login = any(m in macros for m in ["authenticate_by_form", "configure_by_query", "edit_by_form", "create_from_free_text"])
    if needs_login and "authenticate_by_form" not in macros:
        cdc_login()

    r = get_page(f"{CDC}/")
    traj.append(obs_from_result(s, r))

    svc_counter = iter(["svc-001", "svc-002", "svc-003", "svc-006", "svc-009", "svc-018"])
    inst_counter = iter(["i-0a1b2c3d4e5f00003", "i-0a1b2c3d4e5f00004", "i-0a1b2c3d4e5f00005"])
    db_counter = iter(["db-001", "db-003", "db-004"])
    fn_counter = iter(["fn-004", "fn-005", "fn-006"])
    alert_counter = iter(["alert-001", "alert-002", "alert-005"])
    cat_counter = iter(["Compute", "Database", "Networking", "Storage", "Security", "Monitoring"])
    month_counter = iter(["2026-06", "2026-05", "2026-04"])

    for macro in macros:
        s += 1
        if macro == "authenticate_by_form":
            traj.append(make_act(s, macro, "post", f"{CDC}/login", "Login"))
            r = post_form(f"{CDC}/login", {"username": "admin_sarah", "password": "cloudpass1"}); traj.append(obs_from_result(s, r))

        elif macro == "select_by_dropdown":
            cat = next(cat_counter, "Compute")
            traj.append(make_act(s, macro, "get", f"{CDC}/services?category={cat}", f"Select {cat} category"))
            r = get_page(f"{CDC}/services?category={cat}"); traj.append(obs_from_result(s, r))

        elif macro == "configure_by_query":
            cdc_login()
            traj.append(make_act(s, macro, "post", f"{CDC}/api/users/1/preferences", "Configure preferences"))
            r = post_json(f"{CDC}/api/users/1/preferences", {"default_region": "eu-west-1", "notifications": False}); traj.append(make_obs(s, f"{CDC}/api/users/1/preferences", "API: Preferences", f"Response: {json.dumps(r.get('response',{}))[:200]}"))

        elif macro == "extract_by_dropdown":
            m = next(month_counter, "2026-06")
            traj.append(make_act(s, macro, "get", f"{CDC}/billing?month={m}", f"Select billing month {m}"))
            r = get_page(f"{CDC}/billing?month={m}"); traj.append(obs_from_result(s, r))

        elif macro == "search_by_semantic":
            traj.append(make_act(s, macro, "get", f"{CDC}/api/services/semantic?q=monitoring+observability+alerting", "Semantic search services"))
            r = get_api(f"{CDC}/api/services/semantic?q=monitoring+observability+alerting"); traj.append(make_obs(s, f"{CDC}/api/services/semantic?q=monitoring+observability+alerting", "API: Semantic Results", f"Results: {str(r.get('response_text',''))[:200]}"))

        elif macro == "select_from_table":
            inst = next(inst_counter, "i-0a1b2c3d4e5f00003")
            traj.append(make_act(s, macro, "get", f"{CDC}/instance/{inst}", f"Select instance {inst} from table"))
            r = get_page(f"{CDC}/instance/{inst}"); traj.append(obs_from_result(s, r))

        elif macro == "navigate_by_dropdown":
            pages = ["databases", "functions", "storage", "iam", "logs", "alerts"]
            pg = pages[s % len(pages)]
            traj.append(make_act(s, macro, "get", f"{CDC}/{pg}", f"Navigate to {pg} via dropdown"))
            r = get_page(f"{CDC}/{pg}"); traj.append(obs_from_result(s, r))

        elif macro == "navigate_by_route":
            svc = next(svc_counter, "svc-001")
            traj.append(make_act(s, macro, "get", f"{CDC}/service/{svc}", f"Navigate to service {svc}"))
            r = get_page(f"{CDC}/service/{svc}"); traj.append(obs_from_result(s, r))

        elif macro == "extract_by_query":
            traj.append(make_act(s, macro, "get", f"{CDC}/api/billing/summary?month=2026-06", "Extract billing summary"))
            r = get_api(f"{CDC}/api/billing/summary?month=2026-06"); traj.append(make_obs(s, f"{CDC}/api/billing/summary?month=2026-06", "API: Billing Summary", f"Data: {str(r.get('response_text',''))[:200]}"))

        elif macro == "verify_by_dropdown":
            traj.append(make_act(s, macro, "get", f"{CDC}/alerts?severity=critical", "Verify critical alerts"))
            r = get_page(f"{CDC}/alerts?severity=critical"); traj.append(obs_from_result(s, r))

        elif macro == "compute_by_slider":
            traj.append(make_act(s, macro, "get", f"{CDC}/api/metrics/summary?instance_id=i-0a1b2c3d4e5f00003", "Compute metrics summary"))
            r = get_api(f"{CDC}/api/metrics/summary?instance_id=i-0a1b2c3d4e5f00003"); traj.append(make_obs(s, f"{CDC}/api/metrics/summary?instance_id=i-0a1b2c3d4e5f00003", "API: Metrics Summary", f"Data: {str(r.get('response_text',''))[:200]}"))

        elif macro == "filter_by_checkbox":
            traj.append(make_act(s, macro, "get", f"{CDC}/instances?status=running", "Filter running instances"))
            r = get_page(f"{CDC}/instances?status=running"); traj.append(obs_from_result(s, r))

        elif macro == "delete_from_table":
            alert = next(alert_counter, "alert-001")
            traj.append(make_act(s, macro, "post", f"{CDC}/api/alerts/{alert}/delete", f"Delete {alert}"))
            r = post_json(f"{CDC}/api/alerts/{alert}/delete", {}); traj.append(make_obs(s, f"{CDC}/api/alerts/{alert}/delete", "API: Alert Deleted", f"Response: {json.dumps(r.get('response',{}))[:200]}"))

        elif macro == "search_by_query":
            traj.append(make_act(s, macro, "get", f"{CDC}/services?q=compute", "Search for compute"))
            r = get_page(f"{CDC}/services?q=compute"); traj.append(obs_from_result(s, r))

        elif macro == "export_by_dropdown":
            traj.append(make_act(s, macro, "get", f"{CDC}/api/export?resource=instances&format=csv", "Export instances as CSV"))
            r = get_api(f"{CDC}/api/export?resource=instances&format=csv"); traj.append(make_obs(s, f"{CDC}/api/export?resource=instances&format=csv", "Export: CSV", f"CSV: {str(r.get('response_text',''))[:200]}"))

        elif macro == "compute_by_extremum":
            traj.append(make_act(s, macro, "get", f"{CDC}/api/stats", "Get stats to find extremes"))
            r = get_api(f"{CDC}/api/stats"); traj.append(make_obs(s, f"{CDC}/api/stats", "API: Stats", f"Stats: {str(r.get('response_text',''))[:200]}"))

        elif macro == "filter_by_dropdown":
            cat = next(cat_counter, "Security")
            traj.append(make_act(s, macro, "get", f"{CDC}/services?category={cat}", f"Filter services by {cat}"))
            r = get_page(f"{CDC}/services?category={cat}"); traj.append(obs_from_result(s, r))

        elif macro == "extract_from_table":
            inst = next(inst_counter, "i-0a1b2c3d4e5f00003")
            traj.append(make_act(s, macro, "get", f"{CDC}/api/instances/{inst}", f"Extract instance {inst} details"))
            r = get_api(f"{CDC}/api/instances/{inst}"); traj.append(make_obs(s, f"{CDC}/api/instances/{inst}", "API: Instance", f"Data: {str(r.get('response_text',''))[:200]}"))

        elif macro == "submit_by_query":
            traj.append(make_act(s, macro, "post", f"{CDC}/api/alerts/create", "Submit new alert"))
            r = post_json(f"{CDC}/api/alerts/create", {"name": "Custom Alert", "severity": "warning", "resource_name": "web-server", "condition": "CPU > 85%", "category": "Compute"}); traj.append(make_obs(s, f"{CDC}/api/alerts/create", "API: Alert Created", f"Response: {json.dumps(r.get('response',{}))[:200]}"))

        elif macro == "sort_by_ranking":
            traj.append(make_act(s, macro, "get", f"{CDC}/services?sort=cost", "Sort by cost"))
            r = get_page(f"{CDC}/services?sort=cost"); traj.append(obs_from_result(s, r))

        elif macro == "extract_by_route":
            svc = next(svc_counter, "svc-006")
            traj.append(make_act(s, macro, "get", f"{CDC}/api/services/{svc}", f"Extract service {svc}"))
            r = get_api(f"{CDC}/api/services/{svc}"); traj.append(make_obs(s, f"{CDC}/api/services/{svc}", "API: Service", f"Data: {str(r.get('response_text',''))[:200]}"))

        elif macro == "filter_by_query":
            traj.append(make_act(s, macro, "get", f"{CDC}/logs?level=ERROR", "Filter logs by ERROR level"))
            r = get_page(f"{CDC}/logs?level=ERROR"); traj.append(obs_from_result(s, r))

        elif macro == "filter_by_date_range":
            traj.append(make_act(s, macro, "get", f"{CDC}/logs?date_from=2026-06-21T00:00:00Z&date_to=2026-06-21T23:59:59Z", "Filter logs by date range"))
            r = get_page(f"{CDC}/logs?date_from=2026-06-21T00:00:00Z&date_to=2026-06-21T23:59:59Z"); traj.append(obs_from_result(s, r))

        elif macro == "edit_by_form":
            cdc_login()
            traj.append(make_act(s, macro, "post", f"{CDC}/api/users/1/preferences", "Edit user preferences"))
            r = post_json(f"{CDC}/api/users/1/preferences", {"theme": "light", "notifications": True}); traj.append(make_obs(s, f"{CDC}/api/users/1/preferences", "API: Preferences Updated", f"Response: {json.dumps(r.get('response',{}))[:200]}"))

        elif macro == "create_from_free_text":
            cdc_login()
            traj.append(make_act(s, macro, "post", f"{CDC}/api/users/1/save-query", "Save a custom query"))
            r = post_json(f"{CDC}/api/users/1/save-query", {"query": "SELECT * FROM instances WHERE status='running'"}); traj.append(make_obs(s, f"{CDC}/api/users/1/save-query", "API: Query Saved", f"Response: {json.dumps(r.get('response',{}))[:200]}"))

    save_chain("cloud-dev-consoles", chain_id, {"chain_id": chain_id, "site": "cloud-dev-consoles", "valid": True, "macros_completed": macros}, traj)


# =====================================================================
# MAIN
# =====================================================================

def main():
    # Load chain definitions
    bc_chains_file = PROJECT_ROOT / "annotation" / "chains" / "books-comics.json"
    cdc_chains_file = PROJECT_ROOT / "annotation" / "chains" / "cloud-dev-consoles.json"

    bc_chains = json.loads(bc_chains_file.read_text())
    cdc_chains = json.loads(cdc_chains_file.read_text())

    # Books-comics easy chains - specific walkers
    bc_easy_map = {
        "books-comics_easy_001": bc_walk_sort_by_ranking,
        "books-comics_easy_002": bc_walk_follow_by_toggle,
        "books-comics_easy_003": bc_walk_search_by_semantic,
        "books-comics_easy_004": bc_walk_checkout_by_form,
        "books-comics_easy_005": bc_walk_play_by_playback,
        "books-comics_easy_006": bc_walk_select_by_dropdown,
        "books-comics_easy_007": bc_walk_navigate_by_route,
        "books-comics_easy_008": bc_walk_play_by_route,
        "books-comics_easy_009": bc_walk_navigate_by_dropdown,
        "books-comics_easy_010": bc_walk_subscribe_by_toggle,
        "books-comics_easy_011": bc_walk_save_by_toggle,
        "books-comics_easy_012": bc_walk_post_from_free_text,
        "books-comics_easy_013": bc_walk_filter_by_dropdown,
        "books-comics_easy_014": bc_walk_rate_by_slider,
        "books-comics_easy_015": bc_walk_add_by_button,
        "books-comics_easy_016": bc_walk_filter_by_slider,
        "books-comics_easy_017": bc_walk_extract_by_route,
        "books-comics_easy_018": bc_walk_react_by_toggle,
        "books-comics_easy_019": bc_walk_search_by_query,
    }

    bc_medium_map = {
        "books-comics_medium_001": bc_walk_medium_001,
        "books-comics_medium_002": bc_walk_medium_002,
        "books-comics_medium_003": bc_walk_medium_003,
        "books-comics_medium_004": bc_walk_medium_004,
        "books-comics_medium_005": bc_walk_medium_005,
        "books-comics_medium_006": bc_walk_medium_006,
        "books-comics_medium_007": bc_walk_medium_007,
        "books-comics_medium_008": bc_walk_medium_008,
        "books-comics_medium_009": bc_walk_medium_009,
        "books-comics_medium_010": bc_walk_medium_010,
        "books-comics_medium_011": bc_walk_medium_011,
        "books-comics_medium_012": bc_walk_medium_012,
        "books-comics_medium_013": bc_walk_medium_013,
        "books-comics_medium_014": bc_walk_medium_014,
        "books-comics_medium_015": bc_walk_medium_015,
        "books-comics_medium_016": bc_walk_medium_016,
        "books-comics_medium_017": bc_walk_medium_017,
        "books-comics_medium_018": bc_walk_medium_018,
        "books-comics_medium_019": bc_walk_medium_019,
        "books-comics_medium_020": bc_walk_medium_020,
    }

    # Walk all books-comics chains
    print("=== Walking books-comics chains ===")
    total = 0
    for chain in bc_chains:
        cid = chain["chain_id"]
        run_dir = RUNS_DIR / "books-comics" / cid
        if (run_dir / "status.json").exists():
            print(f"  SKIP {cid} (already done)")
            continue

        try:
            if cid in bc_easy_map:
                bc_easy_map[cid](cid)
            elif cid in bc_medium_map:
                bc_medium_map[cid](cid)
            elif cid.startswith("books-comics_hard_001"):
                bc_walk_hard_001(cid)
            elif cid.startswith("books-comics_hard_002"):
                bc_walk_hard_002(cid)
            elif cid.startswith("books-comics_hard_003"):
                bc_walk_hard_003(cid)
            elif cid.startswith("books-comics_hard_004"):
                bc_walk_hard_004(cid)
            else:
                # Generic hard handler
                bc_walk_hard_generic(cid, chain["macros"])
            total += 1
            print(f"  OK {cid}")
        except Exception as e:
            print(f"  FAIL {cid}: {e}")
            # Save failure
            save_chain("books-comics", cid, {"chain_id": cid, "site": "books-comics", "valid": False, "error": str(e), "macros_completed": []}, [])

    print(f"\nBooks-comics: {total} chains walked")

    # Walk all cloud-dev-consoles chains
    print("\n=== Walking cloud-dev-consoles chains ===")
    total = 0
    for chain in cdc_chains:
        cid = chain["chain_id"]
        run_dir = RUNS_DIR / "cloud-dev-consoles" / cid
        if (run_dir / "status.json").exists():
            print(f"  SKIP {cid} (already done)")
            continue

        try:
            if chain["length"] == 1:
                cdc_walk_easy_generic(cid, chain["macros"][0])
            else:
                cdc_walk_multi_generic(cid, chain["macros"])
            total += 1
            print(f"  OK {cid}")
        except Exception as e:
            print(f"  FAIL {cid}: {e}")
            save_chain("cloud-dev-consoles", cid, {"chain_id": cid, "site": "cloud-dev-consoles", "valid": False, "error": str(e), "macros_completed": []}, [])

    print(f"\nCloud-dev-consoles: {total} chains walked")


if __name__ == "__main__":
    main()
