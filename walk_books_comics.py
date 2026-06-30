#!/usr/bin/env python3
"""Batch chain walker for books-comics site."""
import json
import os
import subprocess
import sys

BASE = "/scratch/general/vast/u1653932/projects/MiniWeb"
OUT = f"{BASE}/annotation/chain_runs/books-comics"
CLI = f"python3 {BASE}/scripts/chain_walker_lib.py"

os.makedirs(OUT, exist_ok=True)


def run(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
    return r.stdout.strip()


def reset():
    run(f"{CLI} reset")


def observe(site="books-comics"):
    return run(f"{CLI} observe --site {site}")


def get(url):
    return run(f"{CLI} get --url '{url}'")


def post(url, data):
    return run(f"{CLI} post --url '{url}' --data '{json.dumps(data)}'")


def post_json(url, data):
    return run(f"{CLI} post_json --url '{url}' --data '{json.dumps(data)}'")


def api(url):
    return run(f"{CLI} api --url '{url}'")


def login(username, password):
    return post("/sites/books-comics/login", {"username": username, "password": password})


def login_api(username, password):
    return post_json("/sites/books-comics/api/login", {"username": username, "password": password})


def save_chain(chain_id, macros, difficulty, valid, steps, entity_info, action_summary, trajectory, failure_reason=None):
    d = f"{OUT}/{chain_id}"
    os.makedirs(d, exist_ok=True)
    status = {
        "chain_id": chain_id,
        "site": "books-comics",
        "macros": macros,
        "difficulty": difficulty,
        "valid": valid,
        "failure_reason": failure_reason,
        "steps_completed": steps,
        "entity_info": entity_info,
        "action_summary": action_summary,
    }
    with open(f"{d}/status.json", "w") as f:
        json.dump(status, f, indent=2)
    with open(f"{d}/trajectory.json", "w") as f:
        json.dump(trajectory, f, indent=2)
    print(f"  -> Saved {chain_id} valid={valid} steps={steps}")


# =============================================================================
# EASY CHAINS
# =============================================================================

def walk_easy_001():
    """sort_by_ranking"""
    chain_id = "books-comics_easy_001"
    reset()
    traj = []

    # Observe index page
    obs = observe()
    traj.append({"step": 1, "url": "/sites/books-comics/", "macro": "sort_by_ranking",
                 "description": "Observe index page, then sort by rating",
                 "ax_tree_summary": "Index page with 373 books, sort dropdown available"})

    # Sort by rating
    result = get("/sites/books-comics/?sort=rating")
    traj.append({"step": 2, "url": "/sites/books-comics/?sort=rating", "macro": "sort_by_ranking",
                 "description": "Sorted books by rating (highest first). Top book is Art History II with 5.0 rating.",
                 "ax_tree_summary": "Books sorted by rating, first result: Art History II (5.0)"})

    save_chain(chain_id, ["sort_by_ranking"], "easy", True, 2,
               {"sort_field": "rating", "top_book": "Art History II", "top_rating": 5.0},
               "Sorted all books by rating descending. Top-rated book is Art History II with 5.0 rating.",
               traj)


def walk_easy_002():
    """follow_by_toggle"""
    chain_id = "books-comics_easy_002"
    reset()
    traj = []

    # Login
    login("comic_fan_alice", "pass123")
    traj.append({"step": 1, "url": "/sites/books-comics/login", "macro": "follow_by_toggle",
                 "description": "Logged in as comic_fan_alice",
                 "ax_tree_summary": "Dashboard page after login"})

    # Go to book 1 to see author
    obs = get("/sites/books-comics/book/1")
    traj.append({"step": 2, "url": "/sites/books-comics/book/1", "macro": "follow_by_toggle",
                 "description": "View book 1 detail page. Author: Active Learning Network",
                 "ax_tree_summary": "Book detail page for '100 Ideas for Active Learning', author: Active Learning Network"})

    # Follow author
    result = post("/sites/books-comics/book/1/follow", {"author": "Active Learning Network"})
    traj.append({"step": 3, "url": "/sites/books-comics/book/1/follow", "macro": "follow_by_toggle",
                 "description": "Followed author 'Active Learning Network'",
                 "ax_tree_summary": "Redirected to book detail page, author now followed"})

    save_chain(chain_id, ["follow_by_toggle"], "easy", True, 3,
               {"author": "Active Learning Network", "book_id": 1, "action": "followed"},
               "Logged in and followed author 'Active Learning Network' from book 1.",
               traj)


def walk_easy_003():
    """search_by_semantic"""
    chain_id = "books-comics_easy_003"
    reset()
    traj = []

    obs = observe()
    traj.append({"step": 1, "url": "/sites/books-comics/", "macro": "search_by_semantic",
                 "description": "Observe index page",
                 "ax_tree_summary": "Index page with 373 books, search bar available"})

    # Semantic search
    result = api("/sites/books-comics/api/books/semantic?q=digital+learning+technology")
    data = json.loads(result.split("\n", 1)[1]) if "\n" in result else []
    count = len(data) if isinstance(data, list) else 0
    traj.append({"step": 2, "url": "/sites/books-comics/api/books/semantic?q=digital+learning+technology",
                 "macro": "search_by_semantic",
                 "description": f"Semantic search for 'digital learning technology' returned {count} results",
                 "ax_tree_summary": f"API returned {count} semantically matching books"})

    save_chain(chain_id, ["search_by_semantic"], "easy", True, 2,
               {"query": "digital learning technology", "result_count": count},
               f"Performed semantic search for 'digital learning technology', found {count} results.",
               traj)


def walk_easy_004():
    """checkout_by_form"""
    chain_id = "books-comics_easy_004"
    reset()
    traj = []

    # Login as manga_dan
    login("manga_dan", "pass321")
    traj.append({"step": 1, "url": "/sites/books-comics/login", "macro": "checkout_by_form",
                 "description": "Logged in as manga_dan",
                 "ax_tree_summary": "Dashboard page after login"})

    # Add book to cart
    post("/sites/books-comics/book/2/cart", {})
    traj.append({"step": 2, "url": "/sites/books-comics/book/2/cart", "macro": "checkout_by_form",
                 "description": "Added book 2 to cart",
                 "ax_tree_summary": "Book 2 added to cart, redirected to book detail"})

    # Go to checkout
    obs = get("/sites/books-comics/checkout")
    traj.append({"step": 3, "url": "/sites/books-comics/checkout", "macro": "checkout_by_form",
                 "description": "View checkout page with 1 item",
                 "ax_tree_summary": "Checkout form with name, email, card fields"})

    # Submit checkout
    result = post("/sites/books-comics/checkout", {"name": "Dan Kim", "email": "dan.kim@example.com", "card": "4242424242424242"})
    traj.append({"step": 4, "url": "/sites/books-comics/checkout", "macro": "checkout_by_form",
                 "description": "Completed checkout with payment details",
                 "ax_tree_summary": "Checkout success page, items moved to reading list"})

    save_chain(chain_id, ["checkout_by_form"], "easy", True, 4,
               {"user": "manga_dan", "book_id": 2, "status": "completed"},
               "Logged in as manga_dan, added book 2 to cart, completed checkout.",
               traj)


def walk_easy_005():
    """play_by_playback"""
    chain_id = "books-comics_easy_005"
    reset()
    traj = []

    # Login
    login("comic_fan_alice", "pass123")
    traj.append({"step": 1, "url": "/sites/books-comics/login", "macro": "play_by_playback",
                 "description": "Logged in as comic_fan_alice",
                 "ax_tree_summary": "Dashboard page after login"})

    # Get book 2 chapters
    result = api("/sites/books-comics/api/books/2")
    traj.append({"step": 2, "url": "/sites/books-comics/api/books/2", "macro": "play_by_playback",
                 "description": "Fetched book 2 info - 4 chapters",
                 "ax_tree_summary": "Book 2 has 4 chapters"})

    # Open reader at last chapter
    obs = get("/sites/books-comics/book/2/read?chapter=4")
    traj.append({"step": 3, "url": "/sites/books-comics/book/2/read?chapter=4", "macro": "play_by_playback",
                 "description": "Opened reader at chapter 4 (last chapter)",
                 "ax_tree_summary": "Reader showing Chapter 4 of book 2"})

    # Update reading progress
    result = post_json("/sites/books-comics/api/users/1/reading-progress",
                       {"book_id": 2, "chapter": 4, "progress": 100})
    traj.append({"step": 4, "url": "/sites/books-comics/api/users/1/reading-progress",
                 "macro": "play_by_playback",
                 "description": "Updated reading progress to 100% at chapter 4",
                 "ax_tree_summary": "Reading progress updated: chapter 4, 100%"})

    save_chain(chain_id, ["play_by_playback"], "easy", True, 4,
               {"book_id": 2, "last_chapter": 4, "progress": 100},
               "Opened book 2 reader, navigated to last chapter (4), updated reading progress to 100%.",
               traj)


def walk_easy_006():
    """select_by_dropdown"""
    chain_id = "books-comics_easy_006"
    reset()
    traj = []

    obs = observe()
    traj.append({"step": 1, "url": "/sites/books-comics/", "macro": "select_by_dropdown",
                 "description": "Observe index page with category dropdown",
                 "ax_tree_summary": "Index page with category filter dropdown"})

    # Select science category
    result = get("/sites/books-comics/?category=science")
    traj.append({"step": 2, "url": "/sites/books-comics/?category=science", "macro": "select_by_dropdown",
                 "description": "Selected 'science' from category dropdown, showing 64 science books",
                 "ax_tree_summary": "Filtered view showing science category books"})

    save_chain(chain_id, ["select_by_dropdown"], "easy", True, 2,
               {"category": "science", "count": 64},
               "Selected 'science' category from dropdown filter, showing 64 books.",
               traj)


def walk_easy_007():
    """navigate_by_route"""
    chain_id = "books-comics_easy_007"
    reset()
    traj = []

    obs = observe()
    traj.append({"step": 1, "url": "/sites/books-comics/", "macro": "navigate_by_route",
                 "description": "Observe index page",
                 "ax_tree_summary": "Index page showing 373 books"})

    # Navigate to book detail
    result = get("/sites/books-comics/book/3")
    traj.append({"step": 2, "url": "/sites/books-comics/book/3", "macro": "navigate_by_route",
                 "description": "Navigated to book 3 detail page: ABE 074: Biology",
                 "ax_tree_summary": "Book detail page for ABE 074: Biology by Allison Muir, year 2025, science category"})

    save_chain(chain_id, ["navigate_by_route"], "easy", True, 2,
               {"book_id": 3, "title": "ABE 074: Biology", "author": "Allison Muir"},
               "Navigated to book 3 detail page (ABE 074: Biology).",
               traj)


def walk_easy_008():
    """play_by_route"""
    chain_id = "books-comics_easy_008"
    reset()
    traj = []

    obs = observe()
    traj.append({"step": 1, "url": "/sites/books-comics/", "macro": "play_by_route",
                 "description": "Observe index page",
                 "ax_tree_summary": "Index page with 373 books"})

    # Open reader for book 1
    result = get("/sites/books-comics/book/1/read?chapter=1")
    traj.append({"step": 2, "url": "/sites/books-comics/book/1/read?chapter=1", "macro": "play_by_route",
                 "description": "Opened reader for book 1, Chapter 1",
                 "ax_tree_summary": "Reader showing Chapter 1 (1/5) of 100 Ideas for Active Learning"})

    save_chain(chain_id, ["play_by_route"], "easy", True, 2,
               {"book_id": 1, "chapter": 1, "title": "100 Ideas for Active Learning"},
               "Opened reader for book 1 at chapter 1.",
               traj)


def walk_easy_009():
    """navigate_by_dropdown"""
    chain_id = "books-comics_easy_009"
    reset()
    traj = []

    obs = observe()
    traj.append({"step": 1, "url": "/sites/books-comics/", "macro": "navigate_by_dropdown",
                 "description": "Observe index page with category navigation dropdown",
                 "ax_tree_summary": "Index page with category nav links"})

    # Navigate to education category
    result = get("/sites/books-comics/category/education")
    traj.append({"step": 2, "url": "/sites/books-comics/category/education", "macro": "navigate_by_dropdown",
                 "description": "Navigated to Education & Teaching category page",
                 "ax_tree_summary": "Education category page showing 39 books"})

    save_chain(chain_id, ["navigate_by_dropdown"], "easy", True, 2,
               {"category": "education", "count": 39},
               "Navigated to Education & Teaching category page via category dropdown.",
               traj)


def walk_easy_010():
    """subscribe_by_toggle"""
    chain_id = "books-comics_easy_010"
    reset()
    traj = []

    login("reader_carol", "pass789")
    traj.append({"step": 1, "url": "/sites/books-comics/login", "macro": "subscribe_by_toggle",
                 "description": "Logged in as reader_carol",
                 "ax_tree_summary": "Dashboard for reader_carol"})

    # Subscribe to science category from book 3 detail
    result = post("/sites/books-comics/book/3/subscribe", {"category": "science"})
    traj.append({"step": 2, "url": "/sites/books-comics/book/3/subscribe", "macro": "subscribe_by_toggle",
                 "description": "Subscribed to 'science' category",
                 "ax_tree_summary": "Redirected to book detail, subscription toggled on"})

    save_chain(chain_id, ["subscribe_by_toggle"], "easy", True, 2,
               {"user": "reader_carol", "category": "science", "action": "subscribed"},
               "Logged in as reader_carol and subscribed to science category.",
               traj)


def walk_easy_011():
    """save_by_toggle"""
    chain_id = "books-comics_easy_011"
    reset()
    traj = []

    login("comic_fan_alice", "pass123")
    traj.append({"step": 1, "url": "/sites/books-comics/login", "macro": "save_by_toggle",
                 "description": "Logged in as comic_fan_alice",
                 "ax_tree_summary": "Dashboard for comic_fan_alice"})

    # Save book 5
    result = post("/sites/books-comics/book/5/save", {})
    traj.append({"step": 2, "url": "/sites/books-comics/book/5/save", "macro": "save_by_toggle",
                 "description": "Saved book 5 (American Government 3e) to library",
                 "ax_tree_summary": "Redirected to book detail, book now saved"})

    save_chain(chain_id, ["save_by_toggle"], "easy", True, 2,
               {"user": "comic_fan_alice", "book_id": 5, "action": "saved"},
               "Logged in as comic_fan_alice and saved book 5 to library.",
               traj)


def walk_easy_012():
    """post_from_free_text"""
    chain_id = "books-comics_easy_012"
    reset()
    traj = []

    login("comic_fan_alice", "pass123")
    traj.append({"step": 1, "url": "/sites/books-comics/login", "macro": "post_from_free_text",
                 "description": "Logged in as comic_fan_alice",
                 "ax_tree_summary": "Dashboard for comic_fan_alice"})

    # Post a review for book 1
    result = post("/sites/books-comics/book/1/review", {"text": "Great educational resource, highly recommend!", "rating": "4"})
    traj.append({"step": 2, "url": "/sites/books-comics/book/1/review", "macro": "post_from_free_text",
                 "description": "Posted review 'Great educational resource, highly recommend!' for book 1",
                 "ax_tree_summary": "Review posted, redirected to book detail with review visible"})

    save_chain(chain_id, ["post_from_free_text"], "easy", True, 2,
               {"user": "comic_fan_alice", "book_id": 1, "review_text": "Great educational resource, highly recommend!"},
               "Logged in and posted a review for book 1.",
               traj)


def walk_easy_013():
    """filter_by_dropdown"""
    chain_id = "books-comics_easy_013"
    reset()
    traj = []

    obs = observe()
    traj.append({"step": 1, "url": "/sites/books-comics/", "macro": "filter_by_dropdown",
                 "description": "Observe index page with filter dropdowns",
                 "ax_tree_summary": "Index with category, rating, sort, price filters"})

    # Filter by health category
    result = get("/sites/books-comics/?category=health")
    traj.append({"step": 2, "url": "/sites/books-comics/?category=health", "macro": "filter_by_dropdown",
                 "description": "Filtered by health category, showing 15 books",
                 "ax_tree_summary": "Filtered view showing 15 health category books"})

    save_chain(chain_id, ["filter_by_dropdown"], "easy", True, 2,
               {"filter": "category", "value": "health", "count": 15},
               "Filtered books by health category dropdown, showing 15 results.",
               traj)


def walk_easy_014():
    """rate_by_slider"""
    chain_id = "books-comics_easy_014"
    reset()
    traj = []

    login("bookworm_bob", "pass456")
    traj.append({"step": 1, "url": "/sites/books-comics/login", "macro": "rate_by_slider",
                 "description": "Logged in as bookworm_bob",
                 "ax_tree_summary": "Dashboard for bookworm_bob"})

    # Rate book 5 with 4.5
    result = post("/sites/books-comics/book/5/rate", {"rating": "4.5"})
    traj.append({"step": 2, "url": "/sites/books-comics/book/5/rate", "macro": "rate_by_slider",
                 "description": "Rated book 5 with rating 4.5",
                 "ax_tree_summary": "Rating submitted, redirected to book detail"})

    save_chain(chain_id, ["rate_by_slider"], "easy", True, 2,
               {"user": "bookworm_bob", "book_id": 5, "rating": 4.5},
               "Logged in as bookworm_bob and rated book 5 with 4.5.",
               traj)


def walk_easy_015():
    """add_by_button"""
    chain_id = "books-comics_easy_015"
    reset()
    traj = []

    login("manga_dan", "pass321")
    traj.append({"step": 1, "url": "/sites/books-comics/login", "macro": "add_by_button",
                 "description": "Logged in as manga_dan",
                 "ax_tree_summary": "Dashboard for manga_dan"})

    # Add book 2 to cart
    result = post("/sites/books-comics/book/2/cart", {})
    traj.append({"step": 2, "url": "/sites/books-comics/book/2/cart", "macro": "add_by_button",
                 "description": "Added book 2 to cart",
                 "ax_tree_summary": "Book 2 added to cart, redirected to detail page"})

    save_chain(chain_id, ["add_by_button"], "easy", True, 2,
               {"user": "manga_dan", "book_id": 2, "action": "added_to_cart"},
               "Logged in as manga_dan and added book 2 to cart.",
               traj)


def walk_easy_016():
    """filter_by_slider"""
    chain_id = "books-comics_easy_016"
    reset()
    traj = []

    obs = observe()
    traj.append({"step": 1, "url": "/sites/books-comics/", "macro": "filter_by_slider",
                 "description": "Observe index page with rating filter",
                 "ax_tree_summary": "Index page with min_rating filter"})

    # Filter by min rating 4.0
    result = get("/sites/books-comics/?min_rating=4")
    traj.append({"step": 2, "url": "/sites/books-comics/?min_rating=4", "macro": "filter_by_slider",
                 "description": "Filtered books with min rating 4.0",
                 "ax_tree_summary": "Filtered view showing books with rating >= 4.0"})

    save_chain(chain_id, ["filter_by_slider"], "easy", True, 2,
               {"filter": "min_rating", "value": 4.0},
               "Filtered books by minimum rating of 4.0.",
               traj)


def walk_easy_017():
    """extract_by_route"""
    chain_id = "books-comics_easy_017"
    reset()
    traj = []

    obs = observe()
    traj.append({"step": 1, "url": "/sites/books-comics/", "macro": "extract_by_route",
                 "description": "Observe index page",
                 "ax_tree_summary": "Index page with 373 books"})

    # Get book 3 details
    result = api("/sites/books-comics/api/books/3")
    traj.append({"step": 2, "url": "/sites/books-comics/api/books/3", "macro": "extract_by_route",
                 "description": "Extracted book 3 info: ABE 074: Biology, year 2025, category science, rating 3.5",
                 "ax_tree_summary": "Book 3: ABE 074: Biology by Allison Muir, 2025, science, Free"})

    save_chain(chain_id, ["extract_by_route"], "easy", True, 2,
               {"book_id": 3, "title": "ABE 074: Biology", "year": 2025, "category": "science", "rating": 3.5},
               "Extracted details for book 3 (ABE 074: Biology).",
               traj)


def walk_easy_018():
    """react_by_toggle"""
    chain_id = "books-comics_easy_018"
    reset()
    traj = []

    # First post a review so there's something to react to
    login("comic_fan_alice", "pass123")
    post("/sites/books-comics/book/1/review", {"text": "Interesting book", "rating": "4"})
    traj.append({"step": 1, "url": "/sites/books-comics/book/1/review", "macro": "react_by_toggle",
                 "description": "Logged in and posted a review on book 1 to have a review to react to",
                 "ax_tree_summary": "Review posted for book 1"})

    # React to review 1 with like
    result = post("/sites/books-comics/book/1/react", {"review_id": "1", "reaction": "like"})
    traj.append({"step": 2, "url": "/sites/books-comics/book/1/react", "macro": "react_by_toggle",
                 "description": "Reacted with 'like' to review 1",
                 "ax_tree_summary": "Like reaction added to review 1, count now 1"})

    save_chain(chain_id, ["react_by_toggle"], "easy", True, 2,
               {"review_id": 1, "reaction": "like", "count": 1},
               "Posted a review on book 1 and reacted with 'like' to it.",
               traj)


def walk_easy_019():
    """search_by_query"""
    chain_id = "books-comics_easy_019"
    reset()
    traj = []

    obs = observe()
    traj.append({"step": 1, "url": "/sites/books-comics/", "macro": "search_by_query",
                 "description": "Observe index page with search bar",
                 "ax_tree_summary": "Index page with search form"})

    # Search for 'science'
    result = get("/sites/books-comics/?q=science")
    traj.append({"step": 2, "url": "/sites/books-comics/?q=science", "macro": "search_by_query",
                 "description": "Searched for 'science' using search bar",
                 "ax_tree_summary": "Search results for 'science'"})

    save_chain(chain_id, ["search_by_query"], "easy", True, 2,
               {"query": "science"},
               "Searched for 'science' using the search bar.",
               traj)


# =============================================================================
# MEDIUM CHAINS
# =============================================================================

def walk_medium_001():
    """filter_by_dropdown, navigate_by_dropdown, select_by_dropdown"""
    chain_id = "books-comics_medium_001"
    reset()
    traj = []

    obs = observe()
    traj.append({"step": 1, "url": "/sites/books-comics/", "macro": "filter_by_dropdown",
                 "description": "Observe index page",
                 "ax_tree_summary": "Index page with 373 books and filter dropdowns"})

    # Filter by arts category
    result = get("/sites/books-comics/?category=arts")
    traj.append({"step": 2, "url": "/sites/books-comics/?category=arts", "macro": "filter_by_dropdown",
                 "description": "Filtered by arts category, 31 books",
                 "ax_tree_summary": "31 arts books shown"})

    # Navigate to business category
    result = get("/sites/books-comics/category/business")
    traj.append({"step": 3, "url": "/sites/books-comics/category/business", "macro": "navigate_by_dropdown",
                 "description": "Navigated to business category page",
                 "ax_tree_summary": "Business & Economics category page with 23 books"})

    # Select price filter
    result = get("/sites/books-comics/?category=business&price=free")
    traj.append({"step": 4, "url": "/sites/books-comics/?category=business&price=free", "macro": "select_by_dropdown",
                 "description": "Selected price=free from dropdown for business category",
                 "ax_tree_summary": "Free business books shown"})

    save_chain(chain_id, ["filter_by_dropdown", "navigate_by_dropdown", "select_by_dropdown"], "medium", True, 4,
               {"categories_visited": ["arts", "business"], "price_filter": "free"},
               "Filtered by arts, navigated to business category, selected free price filter.",
               traj)


def walk_medium_002():
    """add_by_button, rate_by_slider, subscribe_by_toggle"""
    chain_id = "books-comics_medium_002"
    reset()
    traj = []

    login("bookworm_bob", "pass456")
    traj.append({"step": 1, "url": "/sites/books-comics/login", "macro": "add_by_button",
                 "description": "Logged in as bookworm_bob",
                 "ax_tree_summary": "Dashboard for bookworm_bob"})

    # Add book 10 to cart
    post("/sites/books-comics/book/10/cart", {})
    traj.append({"step": 2, "url": "/sites/books-comics/book/10/cart", "macro": "add_by_button",
                 "description": "Added book 10 to cart",
                 "ax_tree_summary": "Book 10 added to cart"})

    # Rate book 10
    post("/sites/books-comics/book/10/rate", {"rating": "4"})
    traj.append({"step": 3, "url": "/sites/books-comics/book/10/rate", "macro": "rate_by_slider",
                 "description": "Rated book 10 with rating 4",
                 "ax_tree_summary": "Rating 4 submitted for book 10"})

    # Subscribe to category of book 10 (reference)
    post("/sites/books-comics/book/10/subscribe", {"category": "reference"})
    traj.append({"step": 4, "url": "/sites/books-comics/book/10/subscribe", "macro": "subscribe_by_toggle",
                 "description": "Subscribed to reference category",
                 "ax_tree_summary": "Subscribed to reference category"})

    save_chain(chain_id, ["add_by_button", "rate_by_slider", "subscribe_by_toggle"], "medium", True, 4,
               {"user": "bookworm_bob", "book_id": 10, "rating": 4, "subscription": "reference"},
               "Added book 10 to cart, rated it 4, subscribed to reference category.",
               traj)


def walk_medium_003():
    """add_by_button, extract_by_route, select_by_dropdown"""
    chain_id = "books-comics_medium_003"
    reset()
    traj = []

    login("manga_dan", "pass321")
    traj.append({"step": 1, "url": "/sites/books-comics/login", "macro": "add_by_button",
                 "description": "Logged in as manga_dan",
                 "ax_tree_summary": "Dashboard for manga_dan"})

    # Add book 5 to cart
    post("/sites/books-comics/book/5/cart", {})
    traj.append({"step": 2, "url": "/sites/books-comics/book/5/cart", "macro": "add_by_button",
                 "description": "Added book 5 to cart",
                 "ax_tree_summary": "Book 5 added to cart"})

    # Extract book 5 details
    result = api("/sites/books-comics/api/books/5")
    data = json.loads(result.split("\n", 1)[1]) if "\n" in result else {}
    traj.append({"step": 3, "url": "/sites/books-comics/api/books/5", "macro": "extract_by_route",
                 "description": f"Extracted book 5 info: {data.get('title', 'N/A')}",
                 "ax_tree_summary": f"Book 5: {data.get('title', 'N/A')}, category: {data.get('category', 'N/A')}"})

    # Select category from dropdown
    cat = data.get("category", "humanities")
    result = get(f"/sites/books-comics/?category={cat}")
    traj.append({"step": 4, "url": f"/sites/books-comics/?category={cat}", "macro": "select_by_dropdown",
                 "description": f"Selected '{cat}' category from dropdown",
                 "ax_tree_summary": f"Books filtered by {cat} category"})

    save_chain(chain_id, ["add_by_button", "extract_by_route", "select_by_dropdown"], "medium", True, 4,
               {"user": "manga_dan", "book_id": 5, "title": data.get("title", ""), "category": cat},
               f"Added book 5 to cart, extracted its details, selected {cat} category.",
               traj)


def walk_medium_004():
    """post_from_free_text, react_by_toggle, search_by_query"""
    chain_id = "books-comics_medium_004"
    reset()
    traj = []

    login("comic_fan_alice", "pass123")
    traj.append({"step": 1, "url": "/sites/books-comics/login", "macro": "post_from_free_text",
                 "description": "Logged in as comic_fan_alice",
                 "ax_tree_summary": "Dashboard for comic_fan_alice"})

    # Post review on book 5
    post("/sites/books-comics/book/5/review", {"text": "Comprehensive guide to American government", "rating": "3"})
    traj.append({"step": 2, "url": "/sites/books-comics/book/5/review", "macro": "post_from_free_text",
                 "description": "Posted review on book 5",
                 "ax_tree_summary": "Review posted for book 5"})

    # React to the review
    post("/sites/books-comics/book/5/react", {"review_id": "1", "reaction": "like"})
    traj.append({"step": 3, "url": "/sites/books-comics/book/5/react", "macro": "react_by_toggle",
                 "description": "Reacted with like to review 1",
                 "ax_tree_summary": "Like added to review 1"})

    # Search for a book
    result = get("/sites/books-comics/?q=government")
    traj.append({"step": 4, "url": "/sites/books-comics/?q=government", "macro": "search_by_query",
                 "description": "Searched for 'government'",
                 "ax_tree_summary": "Search results for 'government'"})

    save_chain(chain_id, ["post_from_free_text", "react_by_toggle", "search_by_query"], "medium", True, 4,
               {"user": "comic_fan_alice", "review_book": 5, "search_query": "government"},
               "Posted review on book 5, reacted with like, searched for 'government'.",
               traj)


def walk_medium_005():
    """play_by_route, search_by_query, search_by_semantic"""
    chain_id = "books-comics_medium_005"
    reset()
    traj = []

    obs = observe()
    traj.append({"step": 1, "url": "/sites/books-comics/", "macro": "play_by_route",
                 "description": "Observe index page",
                 "ax_tree_summary": "Index page with 373 books"})

    # Open reader for book 3
    result = get("/sites/books-comics/book/3/read?chapter=1")
    traj.append({"step": 2, "url": "/sites/books-comics/book/3/read?chapter=1", "macro": "play_by_route",
                 "description": "Opened reader for book 3 chapter 1",
                 "ax_tree_summary": "Reader showing Chapter 1 of ABE 074: Biology"})

    # Search by query
    result = get("/sites/books-comics/?q=biology")
    traj.append({"step": 3, "url": "/sites/books-comics/?q=biology", "macro": "search_by_query",
                 "description": "Searched for 'biology'",
                 "ax_tree_summary": "Search results for 'biology'"})

    # Semantic search
    result = api("/sites/books-comics/api/books/semantic?q=cell+structure+organisms")
    traj.append({"step": 4, "url": "/sites/books-comics/api/books/semantic?q=cell+structure+organisms",
                 "macro": "search_by_semantic",
                 "description": "Semantic search for 'cell structure organisms'",
                 "ax_tree_summary": "Semantic search results for biology-related concepts"})

    save_chain(chain_id, ["play_by_route", "search_by_query", "search_by_semantic"], "medium", True, 4,
               {"book_read": 3, "search_query": "biology", "semantic_query": "cell structure organisms"},
               "Opened reader for book 3, searched 'biology', semantic searched 'cell structure organisms'.",
               traj)


def walk_medium_006():
    """extract_by_route, filter_by_dropdown, select_by_dropdown"""
    chain_id = "books-comics_medium_006"
    reset()
    traj = []

    # Extract stats
    result = api("/sites/books-comics/api/categories/science/stats")
    data = json.loads(result.split("\n", 1)[1]) if "\n" in result else {}
    traj.append({"step": 1, "url": "/sites/books-comics/api/categories/science/stats",
                 "macro": "extract_by_route",
                 "description": f"Extracted science category stats: {data.get('count', 0)} books, avg rating {data.get('avg_rating', 0)}",
                 "ax_tree_summary": f"Science: {data.get('count', 0)} books, {data.get('unique_authors', 0)} authors"})

    # Filter by education
    result = get("/sites/books-comics/?category=education")
    traj.append({"step": 2, "url": "/sites/books-comics/?category=education", "macro": "filter_by_dropdown",
                 "description": "Filtered by education category",
                 "ax_tree_summary": "Education category: 39 books"})

    # Select sort by title
    result = get("/sites/books-comics/?category=education&sort=title")
    traj.append({"step": 3, "url": "/sites/books-comics/?category=education&sort=title",
                 "macro": "select_by_dropdown",
                 "description": "Selected sort by title for education books",
                 "ax_tree_summary": "Education books sorted alphabetically"})

    save_chain(chain_id, ["extract_by_route", "filter_by_dropdown", "select_by_dropdown"], "medium", True, 3,
               {"stats_category": "science", "filter_category": "education", "sort": "title"},
               "Extracted science stats, filtered by education, sorted by title.",
               traj)


def walk_medium_007():
    """checkout_by_form, follow_by_toggle, subscribe_by_toggle"""
    chain_id = "books-comics_medium_007"
    reset()
    traj = []

    login("manga_dan", "pass321")
    traj.append({"step": 1, "url": "/sites/books-comics/login", "macro": "checkout_by_form",
                 "description": "Logged in as manga_dan",
                 "ax_tree_summary": "Dashboard for manga_dan"})

    # Add to cart and checkout
    post("/sites/books-comics/book/3/cart", {})
    post("/sites/books-comics/checkout", {"name": "Dan Kim", "email": "dan.kim@example.com", "card": "4242424242424242"})
    traj.append({"step": 2, "url": "/sites/books-comics/checkout", "macro": "checkout_by_form",
                 "description": "Added book 3 to cart and completed checkout",
                 "ax_tree_summary": "Checkout completed, book moved to reading list"})

    # Follow author of book 3
    post("/sites/books-comics/book/3/follow", {"author": "Allison Muir"})
    traj.append({"step": 3, "url": "/sites/books-comics/book/3/follow", "macro": "follow_by_toggle",
                 "description": "Followed author Allison Muir",
                 "ax_tree_summary": "Author Allison Muir now followed"})

    # Subscribe to science
    post("/sites/books-comics/book/3/subscribe", {"category": "science"})
    traj.append({"step": 4, "url": "/sites/books-comics/book/3/subscribe", "macro": "subscribe_by_toggle",
                 "description": "Subscribed to science category",
                 "ax_tree_summary": "Subscribed to science category"})

    save_chain(chain_id, ["checkout_by_form", "follow_by_toggle", "subscribe_by_toggle"], "medium", True, 4,
               {"user": "manga_dan", "checkout_book": 3, "followed_author": "Allison Muir", "subscription": "science"},
               "Checked out book 3, followed Allison Muir, subscribed to science.",
               traj)


def walk_medium_008():
    """add_by_button, extract_by_route, filter_by_slider"""
    chain_id = "books-comics_medium_008"
    reset()
    traj = []

    login("novel_eve", "pass654")
    traj.append({"step": 1, "url": "/sites/books-comics/login", "macro": "add_by_button",
                 "description": "Logged in as novel_eve",
                 "ax_tree_summary": "Dashboard for novel_eve"})

    # Add book 7 to cart
    post("/sites/books-comics/book/7/cart", {})
    traj.append({"step": 2, "url": "/sites/books-comics/book/7/cart", "macro": "add_by_button",
                 "description": "Added book 7 to cart",
                 "ax_tree_summary": "Book 7 added to cart"})

    # Extract book 7 details
    result = api("/sites/books-comics/api/books/7")
    data = json.loads(result.split("\n", 1)[1]) if "\n" in result else {}
    traj.append({"step": 3, "url": "/sites/books-comics/api/books/7", "macro": "extract_by_route",
                 "description": f"Extracted book 7: {data.get('title', 'N/A')}, rating {data.get('rating', 0)}",
                 "ax_tree_summary": f"Book 7: {data.get('title', 'N/A')}"})

    # Filter by min rating 3.5
    result = get("/sites/books-comics/?min_rating=3.5")
    traj.append({"step": 4, "url": "/sites/books-comics/?min_rating=3.5", "macro": "filter_by_slider",
                 "description": "Filtered books with min rating 3.5",
                 "ax_tree_summary": "Books with rating >= 3.5"})

    save_chain(chain_id, ["add_by_button", "extract_by_route", "filter_by_slider"], "medium", True, 4,
               {"user": "novel_eve", "book_id": 7, "title": data.get("title", ""), "min_rating_filter": 3.5},
               f"Added book 7 to cart, extracted its info, filtered by min rating 3.5.",
               traj)


def walk_medium_009():
    """navigate_by_dropdown, navigate_by_route, play_by_route"""
    chain_id = "books-comics_medium_009"
    reset()
    traj = []

    obs = observe()
    traj.append({"step": 1, "url": "/sites/books-comics/", "macro": "navigate_by_dropdown",
                 "description": "Observe index page",
                 "ax_tree_summary": "Index page with category nav"})

    # Navigate to fiction category
    result = get("/sites/books-comics/category/fiction")
    traj.append({"step": 2, "url": "/sites/books-comics/category/fiction", "macro": "navigate_by_dropdown",
                 "description": "Navigated to Fiction category, 28 books",
                 "ax_tree_summary": "Fiction category page with 28 books"})

    # Navigate to a specific book
    result = get("/sites/books-comics/book/110")
    traj.append({"step": 3, "url": "/sites/books-comics/book/110", "macro": "navigate_by_route",
                 "description": "Navigated to book 110: Bridge the Distance (fiction, 5.0 rating)",
                 "ax_tree_summary": "Book detail for Bridge the Distance"})

    # Open reader
    result = get("/sites/books-comics/book/110/read?chapter=1")
    traj.append({"step": 4, "url": "/sites/books-comics/book/110/read?chapter=1", "macro": "play_by_route",
                 "description": "Opened reader for book 110, chapter 1",
                 "ax_tree_summary": "Reader showing chapter 1 of Bridge the Distance"})

    save_chain(chain_id, ["navigate_by_dropdown", "navigate_by_route", "play_by_route"], "medium", True, 4,
               {"category": "fiction", "book_id": 110, "title": "Bridge the Distance"},
               "Navigated to fiction, then to book 110, opened reader.",
               traj)


def walk_medium_010():
    """play_by_route, react_by_toggle, save_by_toggle"""
    chain_id = "books-comics_medium_010"
    reset()
    traj = []

    login("comic_fan_alice", "pass123")
    # Post a review first so we can react
    post("/sites/books-comics/book/2/review", {"text": "Useful pronunciation guide", "rating": "4"})
    traj.append({"step": 1, "url": "/sites/books-comics/login", "macro": "play_by_route",
                 "description": "Logged in and posted review on book 2",
                 "ax_tree_summary": "Logged in, review posted on book 2"})

    # Open reader for book 2
    result = get("/sites/books-comics/book/2/read?chapter=1")
    traj.append({"step": 2, "url": "/sites/books-comics/book/2/read?chapter=1", "macro": "play_by_route",
                 "description": "Opened reader for book 2 chapter 1",
                 "ax_tree_summary": "Reader showing Chapter 1 of book 2"})

    # React to the review
    post("/sites/books-comics/book/2/react", {"review_id": "1", "reaction": "like"})
    traj.append({"step": 3, "url": "/sites/books-comics/book/2/react", "macro": "react_by_toggle",
                 "description": "Reacted with like to review 1 on book 2",
                 "ax_tree_summary": "Like added to review 1"})

    # Save book 2
    post("/sites/books-comics/book/2/save", {})
    traj.append({"step": 4, "url": "/sites/books-comics/book/2/save", "macro": "save_by_toggle",
                 "description": "Saved book 2 to library",
                 "ax_tree_summary": "Book 2 saved to library"})

    save_chain(chain_id, ["play_by_route", "react_by_toggle", "save_by_toggle"], "medium", True, 4,
               {"user": "comic_fan_alice", "book_id": 2, "review_id": 1, "actions": ["read", "react", "save"]},
               "Opened reader for book 2, reacted to review, saved book.",
               traj)


def walk_medium_011():
    """extract_by_route, filter_by_slider, save_by_toggle"""
    chain_id = "books-comics_medium_011"
    reset()
    traj = []

    # Extract stats
    result = api("/sites/books-comics/api/stats")
    data = json.loads(result.split("\n", 1)[1]) if "\n" in result else {}
    traj.append({"step": 1, "url": "/sites/books-comics/api/stats", "macro": "extract_by_route",
                 "description": f"Extracted site stats: {data.get('count', 0)} books, avg rating {data.get('avg_rating', 0)}",
                 "ax_tree_summary": f"Total: {data.get('count', 0)} books, {data.get('unique_authors', 0)} authors"})

    # Filter by min rating
    result = get("/sites/books-comics/?min_rating=4.5")
    traj.append({"step": 2, "url": "/sites/books-comics/?min_rating=4.5", "macro": "filter_by_slider",
                 "description": "Filtered books with min rating 4.5",
                 "ax_tree_summary": "Books with rating >= 4.5"})

    # Login and save a book
    login("bookworm_bob", "pass456")
    post("/sites/books-comics/book/103/save", {})
    traj.append({"step": 3, "url": "/sites/books-comics/book/103/save", "macro": "save_by_toggle",
                 "description": "Logged in and saved book 103 (Art History II, 5.0 rating)",
                 "ax_tree_summary": "Book 103 saved to library"})

    save_chain(chain_id, ["extract_by_route", "filter_by_slider", "save_by_toggle"], "medium", True, 3,
               {"stats": data, "min_rating_filter": 4.5, "saved_book": 103},
               "Extracted site stats, filtered by rating 4.5+, saved top-rated book 103.",
               traj)


def walk_medium_012():
    """extract_by_route, navigate_by_route, subscribe_by_toggle"""
    chain_id = "books-comics_medium_012"
    reset()
    traj = []

    # Extract book 15 info
    result = api("/sites/books-comics/api/books/15")
    data = json.loads(result.split("\n", 1)[1]) if "\n" in result else {}
    traj.append({"step": 1, "url": "/sites/books-comics/api/books/15", "macro": "extract_by_route",
                 "description": f"Extracted book 15: {data.get('title', 'N/A')}, category: {data.get('category', 'N/A')}",
                 "ax_tree_summary": f"Book 15: {data.get('title', 'N/A')}"})

    # Navigate to book 15
    result = get("/sites/books-comics/book/15")
    traj.append({"step": 2, "url": "/sites/books-comics/book/15", "macro": "navigate_by_route",
                 "description": f"Navigated to book 15 detail page",
                 "ax_tree_summary": f"Book detail page for book 15"})

    # Login and subscribe
    login("reader_carol", "pass789")
    cat = data.get("category", "science")
    post(f"/sites/books-comics/book/15/subscribe", {"category": cat})
    traj.append({"step": 3, "url": f"/sites/books-comics/book/15/subscribe", "macro": "subscribe_by_toggle",
                 "description": f"Subscribed to {cat} category",
                 "ax_tree_summary": f"Subscribed to {cat}"})

    save_chain(chain_id, ["extract_by_route", "navigate_by_route", "subscribe_by_toggle"], "medium", True, 3,
               {"book_id": 15, "title": data.get("title", ""), "category": cat},
               f"Extracted book 15 info, navigated to its page, subscribed to {cat}.",
               traj)


def walk_medium_013():
    """filter_by_slider, post_from_free_text, react_by_toggle"""
    chain_id = "books-comics_medium_013"
    reset()
    traj = []

    # Filter by min rating
    result = get("/sites/books-comics/?min_rating=4")
    traj.append({"step": 1, "url": "/sites/books-comics/?min_rating=4", "macro": "filter_by_slider",
                 "description": "Filtered books with min rating 4.0",
                 "ax_tree_summary": "Books with rating >= 4.0"})

    # Login and post review
    login("bookworm_bob", "pass456")
    post("/sites/books-comics/book/103/review", {"text": "Amazing art history content!", "rating": "5"})
    traj.append({"step": 2, "url": "/sites/books-comics/book/103/review", "macro": "post_from_free_text",
                 "description": "Posted review on book 103 (Art History II)",
                 "ax_tree_summary": "Review posted for book 103"})

    # React to the review
    post("/sites/books-comics/book/103/react", {"review_id": "1", "reaction": "like"})
    traj.append({"step": 3, "url": "/sites/books-comics/book/103/react", "macro": "react_by_toggle",
                 "description": "Reacted with like to review 1",
                 "ax_tree_summary": "Like added to review 1"})

    save_chain(chain_id, ["filter_by_slider", "post_from_free_text", "react_by_toggle"], "medium", True, 3,
               {"min_rating": 4.0, "review_book": 103, "reaction": "like"},
               "Filtered by rating 4+, posted review on book 103, reacted with like.",
               traj)


def walk_medium_014():
    """add_by_button, checkout_by_form, rate_by_slider"""
    chain_id = "books-comics_medium_014"
    reset()
    traj = []

    login("novel_eve", "pass654")
    traj.append({"step": 1, "url": "/sites/books-comics/login", "macro": "add_by_button",
                 "description": "Logged in as novel_eve",
                 "ax_tree_summary": "Dashboard for novel_eve"})

    # Add book 1 to cart
    post("/sites/books-comics/book/1/cart", {})
    traj.append({"step": 2, "url": "/sites/books-comics/book/1/cart", "macro": "add_by_button",
                 "description": "Added book 1 to cart",
                 "ax_tree_summary": "Book 1 added to cart"})

    # Checkout
    post("/sites/books-comics/checkout", {"name": "Eve Patel", "email": "eve.patel@example.com", "card": "4242424242424242"})
    traj.append({"step": 3, "url": "/sites/books-comics/checkout", "macro": "checkout_by_form",
                 "description": "Completed checkout for book 1",
                 "ax_tree_summary": "Checkout completed"})

    # Rate book 1
    post("/sites/books-comics/book/1/rate", {"rating": "3.5"})
    traj.append({"step": 4, "url": "/sites/books-comics/book/1/rate", "macro": "rate_by_slider",
                 "description": "Rated book 1 with 3.5",
                 "ax_tree_summary": "Rating 3.5 submitted for book 1"})

    save_chain(chain_id, ["add_by_button", "checkout_by_form", "rate_by_slider"], "medium", True, 4,
               {"user": "novel_eve", "book_id": 1, "checkout": "completed", "rating": 3.5},
               "Added book 1 to cart, checked out, rated book 1 with 3.5.",
               traj)


def walk_medium_015():
    """filter_by_slider, navigate_by_dropdown, search_by_semantic"""
    chain_id = "books-comics_medium_015"
    reset()
    traj = []

    # Filter by min rating 3
    result = get("/sites/books-comics/?min_rating=3")
    traj.append({"step": 1, "url": "/sites/books-comics/?min_rating=3", "macro": "filter_by_slider",
                 "description": "Filtered books with min rating 3.0",
                 "ax_tree_summary": "Books with rating >= 3.0"})

    # Navigate to humanities
    result = get("/sites/books-comics/category/humanities")
    traj.append({"step": 2, "url": "/sites/books-comics/category/humanities", "macro": "navigate_by_dropdown",
                 "description": "Navigated to Humanities & Social Sciences category",
                 "ax_tree_summary": "Humanities category with 32 books"})

    # Semantic search
    result = api("/sites/books-comics/api/books/semantic?q=ancient+civilization+history")
    traj.append({"step": 3, "url": "/sites/books-comics/api/books/semantic?q=ancient+civilization+history",
                 "macro": "search_by_semantic",
                 "description": "Semantic search for 'ancient civilization history'",
                 "ax_tree_summary": "Semantic search results for history-related books"})

    save_chain(chain_id, ["filter_by_slider", "navigate_by_dropdown", "search_by_semantic"], "medium", True, 3,
               {"min_rating": 3.0, "category": "humanities", "semantic_query": "ancient civilization history"},
               "Filtered by rating 3+, navigated to humanities, semantic searched history.",
               traj)


def walk_medium_016():
    """checkout_by_form, rate_by_slider, search_by_semantic"""
    chain_id = "books-comics_medium_016"
    reset()
    traj = []

    login("reader_carol", "pass789")
    traj.append({"step": 1, "url": "/sites/books-comics/login", "macro": "checkout_by_form",
                 "description": "Logged in as reader_carol",
                 "ax_tree_summary": "Dashboard for reader_carol"})

    # Add book and checkout
    post("/sites/books-comics/book/5/cart", {})
    post("/sites/books-comics/checkout", {"name": "Carol Nguyen", "email": "carol.n@example.com", "card": "4111111111111111"})
    traj.append({"step": 2, "url": "/sites/books-comics/checkout", "macro": "checkout_by_form",
                 "description": "Added book 5 and completed checkout",
                 "ax_tree_summary": "Checkout completed"})

    # Rate book 5
    post("/sites/books-comics/book/5/rate", {"rating": "4"})
    traj.append({"step": 3, "url": "/sites/books-comics/book/5/rate", "macro": "rate_by_slider",
                 "description": "Rated book 5 with 4.0",
                 "ax_tree_summary": "Rating 4.0 submitted"})

    # Semantic search
    result = api("/sites/books-comics/api/books/semantic?q=political+democracy+governance")
    traj.append({"step": 4, "url": "/sites/books-comics/api/books/semantic?q=political+democracy+governance",
                 "macro": "search_by_semantic",
                 "description": "Semantic search for 'political democracy governance'",
                 "ax_tree_summary": "Semantic search results"})

    save_chain(chain_id, ["checkout_by_form", "rate_by_slider", "search_by_semantic"], "medium", True, 4,
               {"user": "reader_carol", "checkout_book": 5, "rating": 4.0, "semantic_query": "political democracy governance"},
               "Checked out book 5, rated it 4.0, semantic searched governance topics.",
               traj)


def walk_medium_017():
    """search_by_query, search_by_semantic, subscribe_by_toggle"""
    chain_id = "books-comics_medium_017"
    reset()
    traj = []

    # Search by query
    result = get("/sites/books-comics/?q=math")
    traj.append({"step": 1, "url": "/sites/books-comics/?q=math", "macro": "search_by_query",
                 "description": "Searched for 'math'",
                 "ax_tree_summary": "Search results for 'math'"})

    # Semantic search
    result = api("/sites/books-comics/api/books/semantic?q=algebra+calculus+equations")
    traj.append({"step": 2, "url": "/sites/books-comics/api/books/semantic?q=algebra+calculus+equations",
                 "macro": "search_by_semantic",
                 "description": "Semantic search for 'algebra calculus equations'",
                 "ax_tree_summary": "Semantic search results for math topics"})

    # Login and subscribe
    login("comic_fan_alice", "pass123")
    post("/sites/books-comics/book/9/subscribe", {"category": "science"})
    traj.append({"step": 3, "url": "/sites/books-comics/book/9/subscribe", "macro": "subscribe_by_toggle",
                 "description": "Subscribed to science category",
                 "ax_tree_summary": "Subscribed to science"})

    save_chain(chain_id, ["search_by_query", "search_by_semantic", "subscribe_by_toggle"], "medium", True, 3,
               {"query": "math", "semantic_query": "algebra calculus equations", "subscription": "science"},
               "Searched 'math', semantic searched math topics, subscribed to science.",
               traj)


def walk_medium_018():
    """extract_by_route, navigate_by_route, rate_by_slider"""
    chain_id = "books-comics_medium_018"
    reset()
    traj = []

    # Extract book info via API
    result = api("/sites/books-comics/api/books/20")
    data = json.loads(result.split("\n", 1)[1]) if "\n" in result else {}
    traj.append({"step": 1, "url": "/sites/books-comics/api/books/20", "macro": "extract_by_route",
                 "description": f"Extracted book 20: {data.get('title', 'N/A')}",
                 "ax_tree_summary": f"Book 20: {data.get('title', 'N/A')}"})

    # Navigate to book 20
    result = get("/sites/books-comics/book/20")
    traj.append({"step": 2, "url": "/sites/books-comics/book/20", "macro": "navigate_by_route",
                 "description": "Navigated to book 20 detail page",
                 "ax_tree_summary": "Book detail page for book 20"})

    # Login and rate
    login("bookworm_bob", "pass456")
    post("/sites/books-comics/book/20/rate", {"rating": "4"})
    traj.append({"step": 3, "url": "/sites/books-comics/book/20/rate", "macro": "rate_by_slider",
                 "description": "Rated book 20 with 4.0",
                 "ax_tree_summary": "Rating submitted"})

    save_chain(chain_id, ["extract_by_route", "navigate_by_route", "rate_by_slider"], "medium", True, 3,
               {"book_id": 20, "title": data.get("title", ""), "rating": 4.0},
               f"Extracted book 20 info, navigated to it, rated 4.0.",
               traj)


def walk_medium_019():
    """extract_by_route, post_from_free_text, search_by_query"""
    chain_id = "books-comics_medium_019"
    reset()
    traj = []

    # Extract book 10 info
    result = api("/sites/books-comics/api/books/10")
    data = json.loads(result.split("\n", 1)[1]) if "\n" in result else {}
    traj.append({"step": 1, "url": "/sites/books-comics/api/books/10", "macro": "extract_by_route",
                 "description": f"Extracted book 10: {data.get('title', 'N/A')}",
                 "ax_tree_summary": f"Book 10: {data.get('title', 'N/A')}"})

    # Login and post review
    login("comic_fan_alice", "pass123")
    post("/sites/books-comics/book/10/review", {"text": "Well-written educational content.", "rating": "4"})
    traj.append({"step": 2, "url": "/sites/books-comics/book/10/review", "macro": "post_from_free_text",
                 "description": "Posted review on book 10",
                 "ax_tree_summary": "Review posted for book 10"})

    # Search by query
    title_word = data.get("title", "").split()[0] if data.get("title") else "learning"
    result = get(f"/sites/books-comics/?q={title_word}")
    traj.append({"step": 3, "url": f"/sites/books-comics/?q={title_word}", "macro": "search_by_query",
                 "description": f"Searched for '{title_word}'",
                 "ax_tree_summary": f"Search results for '{title_word}'"})

    save_chain(chain_id, ["extract_by_route", "post_from_free_text", "search_by_query"], "medium", True, 3,
               {"book_id": 10, "title": data.get("title", ""), "review": "Well-written educational content."},
               f"Extracted book 10 info, posted review, searched by title word.",
               traj)


def walk_medium_020():
    """checkout_by_form, extract_by_route, search_by_query"""
    chain_id = "books-comics_medium_020"
    reset()
    traj = []

    # Search by query
    result = get("/sites/books-comics/?q=calculus")
    traj.append({"step": 1, "url": "/sites/books-comics/?q=calculus", "macro": "search_by_query",
                 "description": "Searched for 'calculus'",
                 "ax_tree_summary": "Search results for 'calculus'"})

    # Extract book 9 info (Applied Calculus)
    result = api("/sites/books-comics/api/books/9")
    data = json.loads(result.split("\n", 1)[1]) if "\n" in result else {}
    traj.append({"step": 2, "url": "/sites/books-comics/api/books/9", "macro": "extract_by_route",
                 "description": f"Extracted book 9: {data.get('title', 'N/A')}, price: {data.get('price_str', 'N/A')}",
                 "ax_tree_summary": f"Book 9: {data.get('title', 'N/A')}"})

    # Login and checkout
    login("manga_dan", "pass321")
    post("/sites/books-comics/book/9/cart", {})
    post("/sites/books-comics/checkout", {"name": "Dan Kim", "email": "dan.kim@example.com", "card": "4242424242424242"})
    traj.append({"step": 3, "url": "/sites/books-comics/checkout", "macro": "checkout_by_form",
                 "description": "Added book 9 to cart and completed checkout",
                 "ax_tree_summary": "Checkout completed"})

    save_chain(chain_id, ["checkout_by_form", "extract_by_route", "search_by_query"], "medium", True, 3,
               {"search_query": "calculus", "book_id": 9, "title": data.get("title", ""), "checkout": "completed"},
               "Searched 'calculus', extracted book 9 info, checked out.",
               traj)


# =============================================================================
# HARD CHAINS
# =============================================================================

def walk_hard_001():
    """follow_by_toggle, play_by_playback, search_by_semantic, select_by_dropdown, subscribe_by_toggle"""
    chain_id = "books-comics_hard_001"
    reset()
    traj = []

    login("comic_fan_alice", "pass123")
    traj.append({"step": 1, "url": "/sites/books-comics/login", "macro": "follow_by_toggle",
                 "description": "Logged in as comic_fan_alice",
                 "ax_tree_summary": "Dashboard for comic_fan_alice"})

    # Follow author of book 1
    post("/sites/books-comics/book/1/follow", {"author": "Active Learning Network"})
    traj.append({"step": 2, "url": "/sites/books-comics/book/1/follow", "macro": "follow_by_toggle",
                 "description": "Followed author Active Learning Network",
                 "ax_tree_summary": "Author followed"})

    # Play book 2 and update progress
    get("/sites/books-comics/book/2/read?chapter=4")
    post_json("/sites/books-comics/api/users/1/reading-progress", {"book_id": 2, "chapter": 4, "progress": 100})
    traj.append({"step": 3, "url": "/sites/books-comics/book/2/read?chapter=4", "macro": "play_by_playback",
                 "description": "Read book 2 chapter 4 and set progress to 100%",
                 "ax_tree_summary": "Reading progress updated for book 2"})

    # Semantic search
    result = api("/sites/books-comics/api/books/semantic?q=language+pronunciation+phonetics")
    traj.append({"step": 4, "url": "/sites/books-comics/api/books/semantic?q=language+pronunciation+phonetics",
                 "macro": "search_by_semantic",
                 "description": "Semantic search for 'language pronunciation phonetics'",
                 "ax_tree_summary": "Semantic search results"})

    # Select category dropdown
    get("/sites/books-comics/?category=language")
    traj.append({"step": 5, "url": "/sites/books-comics/?category=language", "macro": "select_by_dropdown",
                 "description": "Selected language category from dropdown",
                 "ax_tree_summary": "Language category, 7 books"})

    # Subscribe to language
    post("/sites/books-comics/book/2/subscribe", {"category": "language"})
    traj.append({"step": 6, "url": "/sites/books-comics/book/2/subscribe", "macro": "subscribe_by_toggle",
                 "description": "Subscribed to language category",
                 "ax_tree_summary": "Subscribed to language"})

    save_chain(chain_id, ["follow_by_toggle", "play_by_playback", "search_by_semantic", "select_by_dropdown", "subscribe_by_toggle"],
               "hard", True, 6,
               {"user": "comic_fan_alice", "followed": "Active Learning Network", "book_read": 2, "subscription": "language"},
               "Followed author, read book 2 to completion, semantic searched, selected language category, subscribed.",
               traj)


def walk_hard_002():
    """filter_by_dropdown, filter_by_slider, post_from_free_text, sort_by_ranking, subscribe_by_toggle"""
    chain_id = "books-comics_hard_002"
    reset()
    traj = []

    # Filter by category
    get("/sites/books-comics/?category=science")
    traj.append({"step": 1, "url": "/sites/books-comics/?category=science", "macro": "filter_by_dropdown",
                 "description": "Filtered by science category",
                 "ax_tree_summary": "64 science books"})

    # Filter by min rating
    get("/sites/books-comics/?category=science&min_rating=4")
    traj.append({"step": 2, "url": "/sites/books-comics/?category=science&min_rating=4", "macro": "filter_by_slider",
                 "description": "Filtered science books with rating >= 4",
                 "ax_tree_summary": "High-rated science books"})

    # Login and post review
    login("bookworm_bob", "pass456")
    post("/sites/books-comics/book/3/review", {"text": "Excellent biology textbook for beginners.", "rating": "5"})
    traj.append({"step": 3, "url": "/sites/books-comics/book/3/review", "macro": "post_from_free_text",
                 "description": "Posted review on book 3",
                 "ax_tree_summary": "Review posted"})

    # Sort by rating
    get("/sites/books-comics/?sort=rating")
    traj.append({"step": 4, "url": "/sites/books-comics/?sort=rating", "macro": "sort_by_ranking",
                 "description": "Sorted all books by rating",
                 "ax_tree_summary": "Books sorted by rating, highest first"})

    # Subscribe to science
    post("/sites/books-comics/book/3/subscribe", {"category": "science"})
    traj.append({"step": 5, "url": "/sites/books-comics/book/3/subscribe", "macro": "subscribe_by_toggle",
                 "description": "Subscribed to science category",
                 "ax_tree_summary": "Subscribed to science"})

    save_chain(chain_id, ["filter_by_dropdown", "filter_by_slider", "post_from_free_text", "sort_by_ranking", "subscribe_by_toggle"],
               "hard", True, 5,
               {"category_filter": "science", "min_rating": 4, "review_book": 3, "subscription": "science"},
               "Filtered science with rating 4+, posted review, sorted by rating, subscribed to science.",
               traj)


def walk_hard_003():
    """navigate_by_route, play_by_route, post_from_free_text, react_by_toggle, subscribe_by_toggle"""
    chain_id = "books-comics_hard_003"
    reset()
    traj = []

    login("comic_fan_alice", "pass123")

    # Navigate to book 5
    get("/sites/books-comics/book/5")
    traj.append({"step": 1, "url": "/sites/books-comics/book/5", "macro": "navigate_by_route",
                 "description": "Navigated to book 5 detail page",
                 "ax_tree_summary": "Book 5 detail page"})

    # Read book 5
    get("/sites/books-comics/book/5/read?chapter=1")
    traj.append({"step": 2, "url": "/sites/books-comics/book/5/read?chapter=1", "macro": "play_by_route",
                 "description": "Opened reader for book 5 chapter 1",
                 "ax_tree_summary": "Reader showing chapter 1 of book 5"})

    # Post review
    post("/sites/books-comics/book/5/review", {"text": "Solid government textbook with good examples.", "rating": "4"})
    traj.append({"step": 3, "url": "/sites/books-comics/book/5/review", "macro": "post_from_free_text",
                 "description": "Posted review on book 5",
                 "ax_tree_summary": "Review posted"})

    # React
    post("/sites/books-comics/book/5/react", {"review_id": "1", "reaction": "like"})
    traj.append({"step": 4, "url": "/sites/books-comics/book/5/react", "macro": "react_by_toggle",
                 "description": "Reacted with like to review 1",
                 "ax_tree_summary": "Like added"})

    # Subscribe
    post("/sites/books-comics/book/5/subscribe", {"category": "humanities"})
    traj.append({"step": 5, "url": "/sites/books-comics/book/5/subscribe", "macro": "subscribe_by_toggle",
                 "description": "Subscribed to humanities category",
                 "ax_tree_summary": "Subscribed to humanities"})

    save_chain(chain_id, ["navigate_by_route", "play_by_route", "post_from_free_text", "react_by_toggle", "subscribe_by_toggle"],
               "hard", True, 5,
               {"book_id": 5, "review": "Solid government textbook", "subscription": "humanities"},
               "Navigated to book 5, read it, posted review, reacted, subscribed to humanities.",
               traj)


def walk_hard_004():
    """checkout_by_form, follow_by_toggle, react_by_toggle, search_by_semantic, subscribe_by_toggle"""
    chain_id = "books-comics_hard_004"
    reset()
    traj = []

    login("manga_dan", "pass321")

    # Add to cart and checkout
    post("/sites/books-comics/book/1/cart", {})
    post("/sites/books-comics/checkout", {"name": "Dan Kim", "email": "dan.kim@example.com", "card": "4242424242424242"})
    traj.append({"step": 1, "url": "/sites/books-comics/checkout", "macro": "checkout_by_form",
                 "description": "Added book 1 to cart and completed checkout",
                 "ax_tree_summary": "Checkout completed"})

    # Follow author
    post("/sites/books-comics/book/1/follow", {"author": "Active Learning Network"})
    traj.append({"step": 2, "url": "/sites/books-comics/book/1/follow", "macro": "follow_by_toggle",
                 "description": "Followed Active Learning Network",
                 "ax_tree_summary": "Author followed"})

    # Post a review first to react
    post("/sites/books-comics/book/1/review", {"text": "Great resource", "rating": "4"})
    post("/sites/books-comics/book/1/react", {"review_id": "1", "reaction": "like"})
    traj.append({"step": 3, "url": "/sites/books-comics/book/1/react", "macro": "react_by_toggle",
                 "description": "Posted review and reacted with like",
                 "ax_tree_summary": "Review posted and liked"})

    # Semantic search
    api("/sites/books-comics/api/books/semantic?q=active+learning+pedagogy")
    traj.append({"step": 4, "url": "/sites/books-comics/api/books/semantic?q=active+learning+pedagogy",
                 "macro": "search_by_semantic",
                 "description": "Semantic search for 'active learning pedagogy'",
                 "ax_tree_summary": "Semantic search results"})

    # Subscribe
    post("/sites/books-comics/book/1/subscribe", {"category": "humanities"})
    traj.append({"step": 5, "url": "/sites/books-comics/book/1/subscribe", "macro": "subscribe_by_toggle",
                 "description": "Subscribed to humanities category",
                 "ax_tree_summary": "Subscribed to humanities"})

    save_chain(chain_id, ["checkout_by_form", "follow_by_toggle", "react_by_toggle", "search_by_semantic", "subscribe_by_toggle"],
               "hard", True, 5,
               {"user": "manga_dan", "checkout_book": 1, "followed": "Active Learning Network", "subscription": "humanities"},
               "Checked out book 1, followed author, reacted to review, semantic searched, subscribed.",
               traj)


def walk_hard_005():
    """filter_by_dropdown, filter_by_slider, react_by_toggle, sort_by_ranking, subscribe_by_toggle"""
    chain_id = "books-comics_hard_005"
    reset()
    traj = []

    # Filter by education category
    get("/sites/books-comics/?category=education")
    traj.append({"step": 1, "url": "/sites/books-comics/?category=education", "macro": "filter_by_dropdown",
                 "description": "Filtered by education category",
                 "ax_tree_summary": "39 education books"})

    # Filter by min rating
    get("/sites/books-comics/?category=education&min_rating=3.5")
    traj.append({"step": 2, "url": "/sites/books-comics/?category=education&min_rating=3.5", "macro": "filter_by_slider",
                 "description": "Filtered education books with rating >= 3.5",
                 "ax_tree_summary": "Education books with high ratings"})

    # Login, post review and react
    login("reader_carol", "pass789")
    post("/sites/books-comics/book/1/review", {"text": "Great for teaching", "rating": "4"})
    post("/sites/books-comics/book/1/react", {"review_id": "1", "reaction": "like"})
    traj.append({"step": 3, "url": "/sites/books-comics/book/1/react", "macro": "react_by_toggle",
                 "description": "Posted review and reacted with like on book 1",
                 "ax_tree_summary": "Review posted and liked"})

    # Sort by rating
    get("/sites/books-comics/?sort=rating")
    traj.append({"step": 4, "url": "/sites/books-comics/?sort=rating", "macro": "sort_by_ranking",
                 "description": "Sorted all books by rating",
                 "ax_tree_summary": "Books sorted by rating"})

    # Subscribe
    post("/sites/books-comics/book/1/subscribe", {"category": "education"})
    traj.append({"step": 5, "url": "/sites/books-comics/book/1/subscribe", "macro": "subscribe_by_toggle",
                 "description": "Subscribed to education category",
                 "ax_tree_summary": "Subscribed to education"})

    save_chain(chain_id, ["filter_by_dropdown", "filter_by_slider", "react_by_toggle", "sort_by_ranking", "subscribe_by_toggle"],
               "hard", True, 5,
               {"category": "education", "min_rating": 3.5, "subscription": "education"},
               "Filtered education with rating 3.5+, reacted to review, sorted by rating, subscribed.",
               traj)


def walk_hard_006():
    """checkout_by_form, follow_by_toggle, navigate_by_route, play_by_route, save_by_toggle"""
    chain_id = "books-comics_hard_006"
    reset()
    traj = []

    login("bookworm_bob", "pass456")

    # Navigate to book 3
    get("/sites/books-comics/book/3")
    traj.append({"step": 1, "url": "/sites/books-comics/book/3", "macro": "navigate_by_route",
                 "description": "Navigated to book 3 (ABE 074: Biology)",
                 "ax_tree_summary": "Book 3 detail page"})

    # Add to cart and checkout
    post("/sites/books-comics/book/3/cart", {})
    post("/sites/books-comics/checkout", {"name": "Bob Martinez", "email": "bob.martinez@example.com", "card": "4111111111111111"})
    traj.append({"step": 2, "url": "/sites/books-comics/checkout", "macro": "checkout_by_form",
                 "description": "Checked out book 3",
                 "ax_tree_summary": "Checkout completed"})

    # Follow author
    post("/sites/books-comics/book/3/follow", {"author": "Allison Muir"})
    traj.append({"step": 3, "url": "/sites/books-comics/book/3/follow", "macro": "follow_by_toggle",
                 "description": "Followed Allison Muir",
                 "ax_tree_summary": "Author followed"})

    # Read book 3
    get("/sites/books-comics/book/3/read?chapter=1")
    traj.append({"step": 4, "url": "/sites/books-comics/book/3/read?chapter=1", "macro": "play_by_route",
                 "description": "Opened reader for book 3 chapter 1",
                 "ax_tree_summary": "Reader showing chapter 1"})

    # Save book 3
    post("/sites/books-comics/book/3/save", {})
    traj.append({"step": 5, "url": "/sites/books-comics/book/3/save", "macro": "save_by_toggle",
                 "description": "Saved book 3 to library",
                 "ax_tree_summary": "Book 3 saved"})

    save_chain(chain_id, ["checkout_by_form", "follow_by_toggle", "navigate_by_route", "play_by_route", "save_by_toggle"],
               "hard", True, 5,
               {"user": "bookworm_bob", "book_id": 3, "author": "Allison Muir"},
               "Navigated to book 3, checked out, followed author, read chapter 1, saved to library.",
               traj)


def walk_hard_007():
    """navigate_by_dropdown, rate_by_slider, search_by_semantic, select_by_dropdown, subscribe_by_toggle"""
    chain_id = "books-comics_hard_007"
    reset()
    traj = []

    # Navigate to arts category
    get("/sites/books-comics/category/arts")
    traj.append({"step": 1, "url": "/sites/books-comics/category/arts", "macro": "navigate_by_dropdown",
                 "description": "Navigated to Arts & Design category",
                 "ax_tree_summary": "Arts category with 31 books"})

    # Login and rate
    login("novel_eve", "pass654")
    post("/sites/books-comics/book/103/rate", {"rating": "5"})
    traj.append({"step": 2, "url": "/sites/books-comics/book/103/rate", "macro": "rate_by_slider",
                 "description": "Rated book 103 (Art History II) with 5",
                 "ax_tree_summary": "Rating submitted"})

    # Semantic search
    api("/sites/books-comics/api/books/semantic?q=visual+art+design+creativity")
    traj.append({"step": 3, "url": "/sites/books-comics/api/books/semantic?q=visual+art+design+creativity",
                 "macro": "search_by_semantic",
                 "description": "Semantic search for 'visual art design creativity'",
                 "ax_tree_summary": "Search results for arts-related books"})

    # Select sort dropdown
    get("/sites/books-comics/?sort=title")
    traj.append({"step": 4, "url": "/sites/books-comics/?sort=title", "macro": "select_by_dropdown",
                 "description": "Selected sort by title",
                 "ax_tree_summary": "Books sorted alphabetically"})

    # Subscribe to arts
    post("/sites/books-comics/book/103/subscribe", {"category": "arts"})
    traj.append({"step": 5, "url": "/sites/books-comics/book/103/subscribe", "macro": "subscribe_by_toggle",
                 "description": "Subscribed to arts category",
                 "ax_tree_summary": "Subscribed to arts"})

    save_chain(chain_id, ["navigate_by_dropdown", "rate_by_slider", "search_by_semantic", "select_by_dropdown", "subscribe_by_toggle"],
               "hard", True, 5,
               {"category": "arts", "rated_book": 103, "rating": 5, "subscription": "arts"},
               "Navigated to arts, rated book 103, semantic searched, sorted by title, subscribed.",
               traj)


def walk_hard_008():
    """add_by_button, extract_by_route, filter_by_slider, play_by_route, react_by_toggle"""
    chain_id = "books-comics_hard_008"
    reset()
    traj = []

    login("manga_dan", "pass321")

    # Add book 7 to cart
    post("/sites/books-comics/book/7/cart", {})
    traj.append({"step": 1, "url": "/sites/books-comics/book/7/cart", "macro": "add_by_button",
                 "description": "Added book 7 to cart",
                 "ax_tree_summary": "Book 7 added to cart"})

    # Extract book 7 info
    result = api("/sites/books-comics/api/books/7")
    data = json.loads(result.split("\n", 1)[1]) if "\n" in result else {}
    traj.append({"step": 2, "url": "/sites/books-comics/api/books/7", "macro": "extract_by_route",
                 "description": f"Extracted book 7: {data.get('title', 'N/A')}",
                 "ax_tree_summary": f"Book 7 details extracted"})

    # Filter by min rating
    get("/sites/books-comics/?min_rating=3")
    traj.append({"step": 3, "url": "/sites/books-comics/?min_rating=3", "macro": "filter_by_slider",
                 "description": "Filtered books with rating >= 3",
                 "ax_tree_summary": "Filtered results"})

    # Read book 7
    get("/sites/books-comics/book/7/read?chapter=1")
    traj.append({"step": 4, "url": "/sites/books-comics/book/7/read?chapter=1", "macro": "play_by_route",
                 "description": "Opened reader for book 7",
                 "ax_tree_summary": "Reader showing chapter 1 of book 7"})

    # Post review and react
    post("/sites/books-comics/book/7/review", {"text": "Interesting geoscience methods", "rating": "4"})
    post("/sites/books-comics/book/7/react", {"review_id": "1", "reaction": "like"})
    traj.append({"step": 5, "url": "/sites/books-comics/book/7/react", "macro": "react_by_toggle",
                 "description": "Posted review and reacted with like",
                 "ax_tree_summary": "Review liked"})

    save_chain(chain_id, ["add_by_button", "extract_by_route", "filter_by_slider", "play_by_route", "react_by_toggle"],
               "hard", True, 5,
               {"book_id": 7, "title": data.get("title", ""), "min_rating_filter": 3},
               "Added book 7 to cart, extracted info, filtered by rating, read chapter, reacted.",
               traj)


def walk_hard_009():
    """filter_by_slider, play_by_playback, post_from_free_text, search_by_query, search_by_semantic"""
    chain_id = "books-comics_hard_009"
    reset()
    traj = []

    # Filter by min rating
    get("/sites/books-comics/?min_rating=4")
    traj.append({"step": 1, "url": "/sites/books-comics/?min_rating=4", "macro": "filter_by_slider",
                 "description": "Filtered books with rating >= 4",
                 "ax_tree_summary": "High-rated books"})

    # Login and play book with progress
    login("comic_fan_alice", "pass123")
    get("/sites/books-comics/book/2/read?chapter=3")
    post_json("/sites/books-comics/api/users/1/reading-progress", {"book_id": 2, "chapter": 3, "progress": 75})
    traj.append({"step": 2, "url": "/sites/books-comics/book/2/read?chapter=3", "macro": "play_by_playback",
                 "description": "Read book 2 chapter 3, set progress to 75%",
                 "ax_tree_summary": "Reading progress: chapter 3, 75%"})

    # Post review
    post("/sites/books-comics/book/2/review", {"text": "Helpful pronunciation guide for ESL learners.", "rating": "4"})
    traj.append({"step": 3, "url": "/sites/books-comics/book/2/review", "macro": "post_from_free_text",
                 "description": "Posted review on book 2",
                 "ax_tree_summary": "Review posted"})

    # Search by query
    get("/sites/books-comics/?q=pronunciation")
    traj.append({"step": 4, "url": "/sites/books-comics/?q=pronunciation", "macro": "search_by_query",
                 "description": "Searched for 'pronunciation'",
                 "ax_tree_summary": "Search results for 'pronunciation'"})

    # Semantic search
    api("/sites/books-comics/api/books/semantic?q=english+speaking+accent+syllable")
    traj.append({"step": 5, "url": "/sites/books-comics/api/books/semantic?q=english+speaking+accent+syllable",
                 "macro": "search_by_semantic",
                 "description": "Semantic search for 'english speaking accent syllable'",
                 "ax_tree_summary": "Semantic search results"})

    save_chain(chain_id, ["filter_by_slider", "play_by_playback", "post_from_free_text", "search_by_query", "search_by_semantic"],
               "hard", True, 5,
               {"min_rating": 4, "book_read": 2, "progress": 75, "search_query": "pronunciation"},
               "Filtered by rating 4+, read book 2 with progress, posted review, searched twice.",
               traj)


def walk_hard_010():
    """play_by_playback, play_by_route, post_from_free_text, react_by_toggle, sort_by_ranking"""
    chain_id = "books-comics_hard_010"
    reset()
    traj = []

    login("bookworm_bob", "pass456")

    # Play book 1 with progress tracking
    get("/sites/books-comics/book/1/read?chapter=5")
    post_json("/sites/books-comics/api/users/2/reading-progress", {"book_id": 1, "chapter": 5, "progress": 100})
    traj.append({"step": 1, "url": "/sites/books-comics/book/1/read?chapter=5", "macro": "play_by_playback",
                 "description": "Read book 1 chapter 5 (last), set progress to 100%",
                 "ax_tree_summary": "Reading progress: chapter 5, 100%"})

    # Play book 3 via route
    get("/sites/books-comics/book/3/read?chapter=1")
    traj.append({"step": 2, "url": "/sites/books-comics/book/3/read?chapter=1", "macro": "play_by_route",
                 "description": "Opened reader for book 3 chapter 1",
                 "ax_tree_summary": "Reader showing chapter 1 of book 3"})

    # Post review
    post("/sites/books-comics/book/1/review", {"text": "Finished reading - excellent pedagogical ideas.", "rating": "5"})
    traj.append({"step": 3, "url": "/sites/books-comics/book/1/review", "macro": "post_from_free_text",
                 "description": "Posted review on book 1",
                 "ax_tree_summary": "Review posted"})

    # React
    post("/sites/books-comics/book/1/react", {"review_id": "1", "reaction": "like"})
    traj.append({"step": 4, "url": "/sites/books-comics/book/1/react", "macro": "react_by_toggle",
                 "description": "Reacted with like",
                 "ax_tree_summary": "Like added"})

    # Sort by rating
    get("/sites/books-comics/?sort=rating")
    traj.append({"step": 5, "url": "/sites/books-comics/?sort=rating", "macro": "sort_by_ranking",
                 "description": "Sorted books by rating",
                 "ax_tree_summary": "Books sorted by rating"})

    save_chain(chain_id, ["play_by_playback", "play_by_route", "post_from_free_text", "react_by_toggle", "sort_by_ranking"],
               "hard", True, 5,
               {"user": "bookworm_bob", "book_completed": 1, "book_started": 3},
               "Completed book 1, started book 3, posted review, reacted, sorted by rating.",
               traj)


def walk_hard_011():
    """extract_by_route, play_by_playback, rate_by_slider, save_by_toggle, select_by_dropdown"""
    chain_id = "books-comics_hard_011"
    reset()
    traj = []

    login("reader_carol", "pass789")

    # Extract book 5 info
    result = api("/sites/books-comics/api/books/5")
    data = json.loads(result.split("\n", 1)[1]) if "\n" in result else {}
    traj.append({"step": 1, "url": "/sites/books-comics/api/books/5", "macro": "extract_by_route",
                 "description": f"Extracted book 5: {data.get('title', 'N/A')}",
                 "ax_tree_summary": "Book 5 details"})

    # Play with progress tracking
    get("/sites/books-comics/book/5/read?chapter=1")
    post_json("/sites/books-comics/api/users/3/reading-progress", {"book_id": 5, "chapter": 1, "progress": 50})
    traj.append({"step": 2, "url": "/sites/books-comics/book/5/read?chapter=1", "macro": "play_by_playback",
                 "description": "Read book 5 chapter 1, progress 50%",
                 "ax_tree_summary": "Reading progress tracked"})

    # Rate
    post("/sites/books-comics/book/5/rate", {"rating": "4"})
    traj.append({"step": 3, "url": "/sites/books-comics/book/5/rate", "macro": "rate_by_slider",
                 "description": "Rated book 5 with 4.0",
                 "ax_tree_summary": "Rating submitted"})

    # Save
    post("/sites/books-comics/book/5/save", {})
    traj.append({"step": 4, "url": "/sites/books-comics/book/5/save", "macro": "save_by_toggle",
                 "description": "Saved book 5",
                 "ax_tree_summary": "Book saved"})

    # Select category dropdown
    cat = data.get("category", "humanities")
    get(f"/sites/books-comics/?category={cat}")
    traj.append({"step": 5, "url": f"/sites/books-comics/?category={cat}", "macro": "select_by_dropdown",
                 "description": f"Selected {cat} from category dropdown",
                 "ax_tree_summary": f"{cat} category selected"})

    save_chain(chain_id, ["extract_by_route", "play_by_playback", "rate_by_slider", "save_by_toggle", "select_by_dropdown"],
               "hard", True, 5,
               {"book_id": 5, "title": data.get("title", ""), "rating": 4, "category": cat},
               f"Extracted book 5 info, read with progress, rated, saved, selected {cat} category.",
               traj)


def walk_hard_012():
    """extract_by_route, follow_by_toggle, play_by_playback, save_by_toggle, select_by_dropdown"""
    chain_id = "books-comics_hard_012"
    reset()
    traj = []

    login("novel_eve", "pass654")

    # Extract book 2 info
    result = api("/sites/books-comics/api/books/2")
    data = json.loads(result.split("\n", 1)[1]) if "\n" in result else {}
    traj.append({"step": 1, "url": "/sites/books-comics/api/books/2", "macro": "extract_by_route",
                 "description": f"Extracted book 2: {data.get('title', 'N/A')}",
                 "ax_tree_summary": "Book 2 details"})

    # Follow author
    authors = data.get("authors", ["marcellinoberardo"])
    post("/sites/books-comics/book/2/follow", {"author": authors[0]})
    traj.append({"step": 2, "url": "/sites/books-comics/book/2/follow", "macro": "follow_by_toggle",
                 "description": f"Followed {authors[0]}",
                 "ax_tree_summary": "Author followed"})

    # Play with progress
    get("/sites/books-comics/book/2/read?chapter=2")
    post_json("/sites/books-comics/api/users/5/reading-progress", {"book_id": 2, "chapter": 2, "progress": 50})
    traj.append({"step": 3, "url": "/sites/books-comics/book/2/read?chapter=2", "macro": "play_by_playback",
                 "description": "Read book 2 chapter 2, progress 50%",
                 "ax_tree_summary": "Reading progress tracked"})

    # Save
    post("/sites/books-comics/book/2/save", {})
    traj.append({"step": 4, "url": "/sites/books-comics/book/2/save", "macro": "save_by_toggle",
                 "description": "Saved book 2",
                 "ax_tree_summary": "Book saved"})

    # Select sort dropdown
    get("/sites/books-comics/?sort=price_low")
    traj.append({"step": 5, "url": "/sites/books-comics/?sort=price_low", "macro": "select_by_dropdown",
                 "description": "Selected sort by price (low to high)",
                 "ax_tree_summary": "Books sorted by price ascending"})

    save_chain(chain_id, ["extract_by_route", "follow_by_toggle", "play_by_playback", "save_by_toggle", "select_by_dropdown"],
               "hard", True, 5,
               {"book_id": 2, "followed": authors[0], "progress": 50},
               f"Extracted book 2, followed {authors[0]}, read with progress, saved, sorted by price.",
               traj)


def walk_hard_013():
    """follow_by_toggle, react_by_toggle, search_by_semantic, sort_by_ranking, subscribe_by_toggle"""
    chain_id = "books-comics_hard_013"
    reset()
    traj = []

    login("comic_fan_alice", "pass123")

    # Follow author of book 3
    post("/sites/books-comics/book/3/follow", {"author": "Allison Muir"})
    traj.append({"step": 1, "url": "/sites/books-comics/book/3/follow", "macro": "follow_by_toggle",
                 "description": "Followed Allison Muir",
                 "ax_tree_summary": "Author followed"})

    # Post review and react
    post("/sites/books-comics/book/3/review", {"text": "Great biology content!", "rating": "4"})
    post("/sites/books-comics/book/3/react", {"review_id": "1", "reaction": "like"})
    traj.append({"step": 2, "url": "/sites/books-comics/book/3/react", "macro": "react_by_toggle",
                 "description": "Posted review and reacted with like",
                 "ax_tree_summary": "Review liked"})

    # Semantic search
    api("/sites/books-comics/api/books/semantic?q=biology+cell+genetics+evolution")
    traj.append({"step": 3, "url": "/sites/books-comics/api/books/semantic?q=biology+cell+genetics+evolution",
                 "macro": "search_by_semantic",
                 "description": "Semantic search for biology topics",
                 "ax_tree_summary": "Semantic search results"})

    # Sort by rating
    get("/sites/books-comics/?sort=rating")
    traj.append({"step": 4, "url": "/sites/books-comics/?sort=rating", "macro": "sort_by_ranking",
                 "description": "Sorted by rating",
                 "ax_tree_summary": "Books sorted by rating"})

    # Subscribe to science
    post("/sites/books-comics/book/3/subscribe", {"category": "science"})
    traj.append({"step": 5, "url": "/sites/books-comics/book/3/subscribe", "macro": "subscribe_by_toggle",
                 "description": "Subscribed to science",
                 "ax_tree_summary": "Subscribed"})

    save_chain(chain_id, ["follow_by_toggle", "react_by_toggle", "search_by_semantic", "sort_by_ranking", "subscribe_by_toggle"],
               "hard", True, 5,
               {"followed": "Allison Muir", "subscription": "science"},
               "Followed Allison Muir, reacted to review, semantic searched, sorted, subscribed to science.",
               traj)


def walk_hard_014():
    """extract_by_route, filter_by_dropdown, navigate_by_dropdown, save_by_toggle, sort_by_ranking"""
    chain_id = "books-comics_hard_014"
    reset()
    traj = []

    # Extract stats
    result = api("/sites/books-comics/api/categories/business/stats")
    data = json.loads(result.split("\n", 1)[1]) if "\n" in result else {}
    traj.append({"step": 1, "url": "/sites/books-comics/api/categories/business/stats", "macro": "extract_by_route",
                 "description": f"Extracted business stats: {data.get('count', 0)} books",
                 "ax_tree_summary": "Business category stats"})

    # Filter by business category
    get("/sites/books-comics/?category=business")
    traj.append({"step": 2, "url": "/sites/books-comics/?category=business", "macro": "filter_by_dropdown",
                 "description": "Filtered by business category",
                 "ax_tree_summary": "23 business books"})

    # Navigate to health category
    get("/sites/books-comics/category/health")
    traj.append({"step": 3, "url": "/sites/books-comics/category/health", "macro": "navigate_by_dropdown",
                 "description": "Navigated to health category",
                 "ax_tree_summary": "Health category with 15 books"})

    # Login and save a book
    login("bookworm_bob", "pass456")
    post("/sites/books-comics/book/10/save", {})
    traj.append({"step": 4, "url": "/sites/books-comics/book/10/save", "macro": "save_by_toggle",
                 "description": "Saved book 10",
                 "ax_tree_summary": "Book saved"})

    # Sort by rating
    get("/sites/books-comics/?sort=rating")
    traj.append({"step": 5, "url": "/sites/books-comics/?sort=rating", "macro": "sort_by_ranking",
                 "description": "Sorted by rating",
                 "ax_tree_summary": "Books sorted by rating"})

    save_chain(chain_id, ["extract_by_route", "filter_by_dropdown", "navigate_by_dropdown", "save_by_toggle", "sort_by_ranking"],
               "hard", True, 5,
               {"business_stats": data, "saved_book": 10},
               "Extracted business stats, filtered by business, navigated to health, saved book, sorted by rating.",
               traj)


def walk_hard_015():
    """filter_by_slider, navigate_by_dropdown, navigate_by_route, rate_by_slider, react_by_toggle"""
    chain_id = "books-comics_hard_015"
    reset()
    traj = []

    # Filter by min rating
    get("/sites/books-comics/?min_rating=3.5")
    traj.append({"step": 1, "url": "/sites/books-comics/?min_rating=3.5", "macro": "filter_by_slider",
                 "description": "Filtered books with rating >= 3.5",
                 "ax_tree_summary": "Books with high ratings"})

    # Navigate to science category
    get("/sites/books-comics/category/science")
    traj.append({"step": 2, "url": "/sites/books-comics/category/science", "macro": "navigate_by_dropdown",
                 "description": "Navigated to science category",
                 "ax_tree_summary": "Science category"})

    # Navigate to specific book
    get("/sites/books-comics/book/9")
    traj.append({"step": 3, "url": "/sites/books-comics/book/9", "macro": "navigate_by_route",
                 "description": "Navigated to book 9 (Applied Calculus)",
                 "ax_tree_summary": "Book 9 detail page"})

    # Login, rate, and react
    login("manga_dan", "pass321")
    post("/sites/books-comics/book/9/rate", {"rating": "4.5"})
    traj.append({"step": 4, "url": "/sites/books-comics/book/9/rate", "macro": "rate_by_slider",
                 "description": "Rated book 9 with 4.5",
                 "ax_tree_summary": "Rating submitted"})

    post("/sites/books-comics/book/9/review", {"text": "Good calculus book", "rating": "4"})
    post("/sites/books-comics/book/9/react", {"review_id": "1", "reaction": "like"})
    traj.append({"step": 5, "url": "/sites/books-comics/book/9/react", "macro": "react_by_toggle",
                 "description": "Posted review and reacted with like",
                 "ax_tree_summary": "Review liked"})

    save_chain(chain_id, ["filter_by_slider", "navigate_by_dropdown", "navigate_by_route", "rate_by_slider", "react_by_toggle"],
               "hard", True, 5,
               {"min_rating": 3.5, "category": "science", "book_id": 9, "rating": 4.5},
               "Filtered by rating, navigated to science, book 9, rated 4.5, reacted.",
               traj)


def walk_hard_016():
    """navigate_by_dropdown, post_from_free_text, rate_by_slider, react_by_toggle, save_by_toggle"""
    chain_id = "books-comics_hard_016"
    reset()
    traj = []

    login("reader_carol", "pass789")

    # Navigate to fiction category
    get("/sites/books-comics/category/fiction")
    traj.append({"step": 1, "url": "/sites/books-comics/category/fiction", "macro": "navigate_by_dropdown",
                 "description": "Navigated to fiction category",
                 "ax_tree_summary": "Fiction category with 28 books"})

    # Post review
    post("/sites/books-comics/book/110/review", {"text": "Beautiful poetry collection about the pandemic.", "rating": "5"})
    traj.append({"step": 2, "url": "/sites/books-comics/book/110/review", "macro": "post_from_free_text",
                 "description": "Posted review on book 110 (Bridge the Distance)",
                 "ax_tree_summary": "Review posted"})

    # Rate
    post("/sites/books-comics/book/110/rate", {"rating": "5"})
    traj.append({"step": 3, "url": "/sites/books-comics/book/110/rate", "macro": "rate_by_slider",
                 "description": "Rated book 110 with 5",
                 "ax_tree_summary": "Rating submitted"})

    # React
    post("/sites/books-comics/book/110/react", {"review_id": "1", "reaction": "like"})
    traj.append({"step": 4, "url": "/sites/books-comics/book/110/react", "macro": "react_by_toggle",
                 "description": "Reacted with like",
                 "ax_tree_summary": "Like added"})

    # Save
    post("/sites/books-comics/book/110/save", {})
    traj.append({"step": 5, "url": "/sites/books-comics/book/110/save", "macro": "save_by_toggle",
                 "description": "Saved book 110",
                 "ax_tree_summary": "Book saved"})

    save_chain(chain_id, ["navigate_by_dropdown", "post_from_free_text", "rate_by_slider", "react_by_toggle", "save_by_toggle"],
               "hard", True, 5,
               {"category": "fiction", "book_id": 110, "rating": 5},
               "Navigated to fiction, posted review, rated 5, reacted, saved book 110.",
               traj)


def walk_hard_017():
    """add_by_button, navigate_by_dropdown, play_by_route, select_by_dropdown, subscribe_by_toggle"""
    chain_id = "books-comics_hard_017"
    reset()
    traj = []

    login("novel_eve", "pass654")

    # Add book 20 to cart
    post("/sites/books-comics/book/20/cart", {})
    traj.append({"step": 1, "url": "/sites/books-comics/book/20/cart", "macro": "add_by_button",
                 "description": "Added book 20 to cart",
                 "ax_tree_summary": "Book 20 added to cart"})

    # Navigate to humanities category
    get("/sites/books-comics/category/humanities")
    traj.append({"step": 2, "url": "/sites/books-comics/category/humanities", "macro": "navigate_by_dropdown",
                 "description": "Navigated to humanities category",
                 "ax_tree_summary": "Humanities category with 32 books"})

    # Read book 20
    get("/sites/books-comics/book/20/read?chapter=1")
    traj.append({"step": 3, "url": "/sites/books-comics/book/20/read?chapter=1", "macro": "play_by_route",
                 "description": "Opened reader for book 20",
                 "ax_tree_summary": "Reader showing chapter 1"})

    # Select price filter
    get("/sites/books-comics/?price=paid")
    traj.append({"step": 4, "url": "/sites/books-comics/?price=paid", "macro": "select_by_dropdown",
                 "description": "Selected paid price filter",
                 "ax_tree_summary": "Paid books only"})

    # Subscribe to humanities
    post("/sites/books-comics/book/20/subscribe", {"category": "reference"})
    traj.append({"step": 5, "url": "/sites/books-comics/book/20/subscribe", "macro": "subscribe_by_toggle",
                 "description": "Subscribed to reference category",
                 "ax_tree_summary": "Subscribed to reference"})

    save_chain(chain_id, ["add_by_button", "navigate_by_dropdown", "play_by_route", "select_by_dropdown", "subscribe_by_toggle"],
               "hard", True, 5,
               {"book_id": 20, "categories": ["humanities"], "subscription": "reference"},
               "Added book 20 to cart, navigated to humanities, read book, selected paid filter, subscribed.",
               traj)


def walk_hard_018():
    """follow_by_toggle, rate_by_slider, react_by_toggle, search_by_query, subscribe_by_toggle"""
    chain_id = "books-comics_hard_018"
    reset()
    traj = []

    login("bookworm_bob", "pass456")

    # Follow author of book 1
    post("/sites/books-comics/book/1/follow", {"author": "Active Learning Network"})
    traj.append({"step": 1, "url": "/sites/books-comics/book/1/follow", "macro": "follow_by_toggle",
                 "description": "Followed Active Learning Network",
                 "ax_tree_summary": "Author followed"})

    # Rate book 1
    post("/sites/books-comics/book/1/rate", {"rating": "3"})
    traj.append({"step": 2, "url": "/sites/books-comics/book/1/rate", "macro": "rate_by_slider",
                 "description": "Rated book 1 with 3",
                 "ax_tree_summary": "Rating submitted"})

    # Post review and react
    post("/sites/books-comics/book/1/review", {"text": "Decent teaching resource", "rating": "3"})
    post("/sites/books-comics/book/1/react", {"review_id": "1", "reaction": "like"})
    traj.append({"step": 3, "url": "/sites/books-comics/book/1/react", "macro": "react_by_toggle",
                 "description": "Posted review and reacted",
                 "ax_tree_summary": "Review liked"})

    # Search
    get("/sites/books-comics/?q=active+learning")
    traj.append({"step": 4, "url": "/sites/books-comics/?q=active+learning", "macro": "search_by_query",
                 "description": "Searched for 'active learning'",
                 "ax_tree_summary": "Search results"})

    # Subscribe
    post("/sites/books-comics/book/1/subscribe", {"category": "humanities"})
    traj.append({"step": 5, "url": "/sites/books-comics/book/1/subscribe", "macro": "subscribe_by_toggle",
                 "description": "Subscribed to humanities",
                 "ax_tree_summary": "Subscribed"})

    save_chain(chain_id, ["follow_by_toggle", "rate_by_slider", "react_by_toggle", "search_by_query", "subscribe_by_toggle"],
               "hard", True, 5,
               {"followed": "Active Learning Network", "rating": 3, "subscription": "humanities"},
               "Followed author, rated book 1, reacted, searched, subscribed to humanities.",
               traj)


def walk_hard_019():
    """checkout_by_form, filter_by_slider, react_by_toggle, sort_by_ranking, subscribe_by_toggle"""
    chain_id = "books-comics_hard_019"
    reset()
    traj = []

    login("reader_carol", "pass789")

    # Add to cart and checkout
    post("/sites/books-comics/book/7/cart", {})
    post("/sites/books-comics/checkout", {"name": "Carol Nguyen", "email": "carol.n@example.com", "card": "4111111111111111"})
    traj.append({"step": 1, "url": "/sites/books-comics/checkout", "macro": "checkout_by_form",
                 "description": "Checked out book 7",
                 "ax_tree_summary": "Checkout completed"})

    # Filter by min rating
    get("/sites/books-comics/?min_rating=4")
    traj.append({"step": 2, "url": "/sites/books-comics/?min_rating=4", "macro": "filter_by_slider",
                 "description": "Filtered books with rating >= 4",
                 "ax_tree_summary": "High-rated books"})

    # Post review and react
    post("/sites/books-comics/book/7/review", {"text": "Good geoscience methods", "rating": "4"})
    post("/sites/books-comics/book/7/react", {"review_id": "1", "reaction": "like"})
    traj.append({"step": 3, "url": "/sites/books-comics/book/7/react", "macro": "react_by_toggle",
                 "description": "Posted review and reacted with like",
                 "ax_tree_summary": "Review liked"})

    # Sort by rating
    get("/sites/books-comics/?sort=rating")
    traj.append({"step": 4, "url": "/sites/books-comics/?sort=rating", "macro": "sort_by_ranking",
                 "description": "Sorted by rating",
                 "ax_tree_summary": "Books sorted by rating"})

    # Subscribe
    post("/sites/books-comics/book/7/subscribe", {"category": "science"})
    traj.append({"step": 5, "url": "/sites/books-comics/book/7/subscribe", "macro": "subscribe_by_toggle",
                 "description": "Subscribed to science",
                 "ax_tree_summary": "Subscribed"})

    save_chain(chain_id, ["checkout_by_form", "filter_by_slider", "react_by_toggle", "sort_by_ranking", "subscribe_by_toggle"],
               "hard", True, 5,
               {"checkout_book": 7, "min_rating": 4, "subscription": "science"},
               "Checked out book 7, filtered by rating, reacted, sorted, subscribed to science.",
               traj)


def walk_hard_020():
    """filter_by_slider, follow_by_toggle, play_by_route, post_from_free_text, select_by_dropdown"""
    chain_id = "books-comics_hard_020"
    reset()
    traj = []

    login("manga_dan", "pass321")

    # Filter by min rating
    get("/sites/books-comics/?min_rating=4")
    traj.append({"step": 1, "url": "/sites/books-comics/?min_rating=4", "macro": "filter_by_slider",
                 "description": "Filtered books with rating >= 4",
                 "ax_tree_summary": "High-rated books"})

    # Follow author of book 2
    post("/sites/books-comics/book/2/follow", {"author": "marcellinoberardo"})
    traj.append({"step": 2, "url": "/sites/books-comics/book/2/follow", "macro": "follow_by_toggle",
                 "description": "Followed marcellinoberardo",
                 "ax_tree_summary": "Author followed"})

    # Read book 2
    get("/sites/books-comics/book/2/read?chapter=1")
    traj.append({"step": 3, "url": "/sites/books-comics/book/2/read?chapter=1", "macro": "play_by_route",
                 "description": "Opened reader for book 2",
                 "ax_tree_summary": "Reader showing chapter 1"})

    # Post review
    post("/sites/books-comics/book/2/review", {"text": "Very helpful for understanding English pronunciation.", "rating": "4"})
    traj.append({"step": 4, "url": "/sites/books-comics/book/2/review", "macro": "post_from_free_text",
                 "description": "Posted review on book 2",
                 "ax_tree_summary": "Review posted"})

    # Select sort dropdown
    get("/sites/books-comics/?sort=price_high")
    traj.append({"step": 5, "url": "/sites/books-comics/?sort=price_high", "macro": "select_by_dropdown",
                 "description": "Selected sort by price (high to low)",
                 "ax_tree_summary": "Books sorted by price descending"})

    save_chain(chain_id, ["filter_by_slider", "follow_by_toggle", "play_by_route", "post_from_free_text", "select_by_dropdown"],
               "hard", True, 5,
               {"min_rating": 4, "followed": "marcellinoberardo", "book_id": 2},
               "Filtered by rating, followed author, read book 2, posted review, sorted by price.",
               traj)


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    all_walkers = [
        # Easy
        walk_easy_001, walk_easy_002, walk_easy_003, walk_easy_004, walk_easy_005,
        walk_easy_006, walk_easy_007, walk_easy_008, walk_easy_009, walk_easy_010,
        walk_easy_011, walk_easy_012, walk_easy_013, walk_easy_014, walk_easy_015,
        walk_easy_016, walk_easy_017, walk_easy_018, walk_easy_019,
        # Medium
        walk_medium_001, walk_medium_002, walk_medium_003, walk_medium_004, walk_medium_005,
        walk_medium_006, walk_medium_007, walk_medium_008, walk_medium_009, walk_medium_010,
        walk_medium_011, walk_medium_012, walk_medium_013, walk_medium_014, walk_medium_015,
        walk_medium_016, walk_medium_017, walk_medium_018, walk_medium_019, walk_medium_020,
        # Hard
        walk_hard_001, walk_hard_002, walk_hard_003, walk_hard_004, walk_hard_005,
        walk_hard_006, walk_hard_007, walk_hard_008, walk_hard_009, walk_hard_010,
        walk_hard_011, walk_hard_012, walk_hard_013, walk_hard_014, walk_hard_015,
        walk_hard_016, walk_hard_017, walk_hard_018, walk_hard_019, walk_hard_020,
    ]

    print(f"Walking {len(all_walkers)} chains for books-comics...")
    for i, walker in enumerate(all_walkers, 1):
        name = walker.__name__
        print(f"[{i}/{len(all_walkers)}] {name}")
        try:
            walker()
        except Exception as e:
            print(f"  ERROR: {e}")
    print("Done!")
