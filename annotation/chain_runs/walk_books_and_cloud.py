#!/usr/bin/env python3
"""Walk ALL chains for books-comics and cloud-dev-consoles sites."""
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(str(PROJECT_ROOT))

from scripts.chain_walker_lib import (
    do_get, do_post, do_post_json, do_get_api, do_reset,
    html_to_axtree, axtree_to_text, _get_client
)

RUNS_DIR = PROJECT_ROOT / "annotation" / "chain_runs"
CHAINS_DIR = PROJECT_ROOT / "annotation" / "chains"


def summarize_axtree(ax):
    """Create a concise summary of an ax_tree for trajectory."""
    parts = []
    if ax.get("title"):
        parts.append(f"title={ax['title']}")
    if ax.get("headings"):
        parts.append(f"headings=[{', '.join(h['text'][:50] for h in ax['headings'][:5])}]")
    if ax.get("forms"):
        parts.append(f"forms={len(ax['forms'])}")
    if ax.get("tables"):
        parts.append(f"tables={len(ax['tables'])}")
    if ax.get("links"):
        parts.append(f"links={len(ax['links'])}")
    return "; ".join(parts)


def save_chain(site, chain_id, trajectory, valid=True):
    """Save trajectory and status for a chain."""
    run_dir = RUNS_DIR / site / chain_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "trajectory.json").write_text(json.dumps(trajectory, indent=2))
    (run_dir / "status.json").write_text(json.dumps({
        "chain_id": chain_id,
        "site": site,
        "valid": valid,
        "num_steps": len(trajectory)
    }, indent=2))


def obs(url, step):
    """Get a page and build an observation entry."""
    result = do_get(url)
    ax = result["ax_tree"]
    return {
        "type": "observation",
        "step": step,
        "url": url,
        "title": ax.get("title", ""),
        "ax_tree_summary": summarize_axtree(ax)
    }


def obs_api(url, step):
    """Get an API endpoint and build an observation entry."""
    result = do_get_api(url)
    return {
        "type": "observation",
        "step": step,
        "url": url,
        "title": f"API Response ({result['status_code']})",
        "ax_tree_summary": result.get("response_text", "")[:300]
    }


def action(step, macro, action_type, url, description, data=None):
    """Build an action entry."""
    entry = {
        "type": "action",
        "step": step,
        "macro": macro,
        "action_type": action_type,
        "url": url,
        "description": description
    }
    if data:
        entry["data"] = data
    return entry


# ===========================================================================
# BOOKS-COMICS macro implementations
# ===========================================================================

BC = "/sites/books-comics"


def bc_sort_by_ranking():
    """Sort books by rating."""
    t = []
    t.append(obs(f"{BC}/", 0))
    t.append(action(1, "sort_by_ranking", "get", f"{BC}/?sort=rating",
                     "Sort book catalog by rating (highest first)"))
    t.append(obs(f"{BC}/?sort=rating", 1))
    return t


def bc_follow_by_toggle():
    """Follow an author."""
    t = []
    t.append(obs(f"{BC}/book/1", 0))
    t.append(action(1, "follow_by_toggle", "post", f"{BC}/book/1/follow",
                     "Toggle follow on author 'Active Learning Network'",
                     {"author": "Active Learning Network"}))
    do_post(f"{BC}/book/1/follow", {"author": "Active Learning Network"})
    t.append(obs(f"{BC}/book/1", 1))
    return t


def bc_search_by_semantic():
    """Semantic search for books."""
    t = []
    t.append(obs(f"{BC}/", 0))
    t.append(action(1, "search_by_semantic", "get",
                     f"{BC}/api/books/semantic?q=biology+science",
                     "Semantic search for books about biology and science"))
    t.append(obs_api(f"{BC}/api/books/semantic?q=biology+science", 1))
    return t


def bc_checkout_by_form():
    """Checkout items from cart."""
    t = []
    # First add an item to cart
    do_post(f"{BC}/login", {"username": "comic_fan_alice", "password": "pass123"})
    do_post(f"{BC}/book/2/cart", {})
    t.append(obs(f"{BC}/checkout", 0))
    t.append(action(1, "checkout_by_form", "post", f"{BC}/checkout",
                     "Submit checkout form with payment details",
                     {"name": "Alice Wonder", "email": "alice@example.com", "card": "4111111111111111"}))
    do_post(f"{BC}/checkout", {"name": "Alice Wonder", "email": "alice@example.com", "card": "4111111111111111"})
    t.append(obs(f"{BC}/checkout", 1))
    return t


def bc_play_by_playback():
    """Track reading progress (playback analog)."""
    t = []
    do_post(f"{BC}/login", {"username": "comic_fan_alice", "password": "pass123"})
    t.append(obs(f"{BC}/book/1/read", 0))
    t.append(action(1, "play_by_playback", "post",
                     f"{BC}/api/users/1/reading-progress",
                     "Update reading progress for book 1, chapter 2 at 50%",
                     {"book_id": 1, "chapter": 2, "progress": 50}))
    do_post_json(f"{BC}/api/users/1/reading-progress",
                 {"book_id": 1, "chapter": 2, "progress": 50})
    t.append(obs(f"{BC}/book/1/read?chapter=2", 1))
    return t


def bc_select_by_dropdown():
    """Select a category from dropdown."""
    t = []
    t.append(obs(f"{BC}/", 0))
    t.append(action(1, "select_by_dropdown", "get",
                     f"{BC}/?category=science",
                     "Select 'Science & Technology' from category dropdown"))
    t.append(obs(f"{BC}/?category=science", 1))
    return t


def bc_navigate_by_route():
    """Navigate to a specific page by route."""
    t = []
    t.append(obs(f"{BC}/", 0))
    t.append(action(1, "navigate_by_route", "get", f"{BC}/dashboard",
                     "Navigate to user dashboard"))
    do_post(f"{BC}/login", {"username": "comic_fan_alice", "password": "pass123"})
    t.append(obs(f"{BC}/dashboard", 1))
    return t


def bc_play_by_route():
    """Navigate to read a book (play = open reader)."""
    t = []
    t.append(obs(f"{BC}/book/5", 0))
    t.append(action(1, "play_by_route", "get", f"{BC}/book/5/read",
                     "Open the reader for book 5"))
    t.append(obs(f"{BC}/book/5/read", 1))
    return t


def bc_navigate_by_dropdown():
    """Navigate to a category page via sidebar dropdown."""
    t = []
    t.append(obs(f"{BC}/", 0))
    t.append(action(1, "navigate_by_dropdown", "get",
                     f"{BC}/category/fiction",
                     "Navigate to Fiction category from sidebar"))
    t.append(obs(f"{BC}/category/fiction", 1))
    return t


def bc_subscribe_by_toggle():
    """Subscribe to a category."""
    t = []
    do_post(f"{BC}/login", {"username": "comic_fan_alice", "password": "pass123"})
    t.append(obs(f"{BC}/book/3", 0))
    t.append(action(1, "subscribe_by_toggle", "post", f"{BC}/book/3/subscribe",
                     "Subscribe to the 'science' category",
                     {"category": "science"}))
    do_post(f"{BC}/book/3/subscribe", {"category": "science"})
    t.append(obs(f"{BC}/book/3", 1))
    return t


def bc_save_by_toggle():
    """Save a book to library."""
    t = []
    do_post(f"{BC}/login", {"username": "comic_fan_alice", "password": "pass123"})
    t.append(obs(f"{BC}/book/5", 0))
    t.append(action(1, "save_by_toggle", "post", f"{BC}/book/5/save",
                     "Save book 5 to personal library"))
    do_post(f"{BC}/book/5/save", {})
    t.append(obs(f"{BC}/book/5", 1))
    return t


def bc_post_from_free_text():
    """Post a review (free text)."""
    t = []
    do_post(f"{BC}/login", {"username": "comic_fan_alice", "password": "pass123"})
    t.append(obs(f"{BC}/book/2", 0))
    t.append(action(1, "post_from_free_text", "post", f"{BC}/book/2/review",
                     "Post a review for book 2",
                     {"text": "Great introduction to English pronunciation. Very helpful for ESL learners.", "rating": "4"}))
    do_post(f"{BC}/book/2/review",
            {"text": "Great introduction to English pronunciation. Very helpful for ESL learners.", "rating": "4"})
    t.append(obs(f"{BC}/book/2", 1))
    return t


def bc_filter_by_dropdown():
    """Filter books by category dropdown."""
    t = []
    t.append(obs(f"{BC}/", 0))
    t.append(action(1, "filter_by_dropdown", "get",
                     f"{BC}/?category=business",
                     "Filter books by 'Business & Economics' category"))
    t.append(obs(f"{BC}/?category=business", 1))
    return t


def bc_rate_by_slider():
    """Rate a book using the slider."""
    t = []
    do_post(f"{BC}/login", {"username": "comic_fan_alice", "password": "pass123"})
    t.append(obs(f"{BC}/book/3", 0))
    t.append(action(1, "rate_by_slider", "post", f"{BC}/book/3/rate",
                     "Rate book 3 with a rating of 4 using the slider",
                     {"rating": "4"}))
    do_post(f"{BC}/book/3/rate", {"rating": "4"})
    t.append(obs(f"{BC}/book/3", 1))
    return t


def bc_add_by_button():
    """Add a book to cart."""
    t = []
    do_post(f"{BC}/login", {"username": "comic_fan_alice", "password": "pass123"})
    t.append(obs(f"{BC}/book/1", 0))
    t.append(action(1, "add_by_button", "post", f"{BC}/book/1/cart",
                     "Add book 1 to cart"))
    do_post(f"{BC}/book/1/cart", {})
    t.append(obs(f"{BC}/book/1", 1))
    return t


def bc_filter_by_slider():
    """Filter books by minimum rating."""
    t = []
    t.append(obs(f"{BC}/", 0))
    t.append(action(1, "filter_by_slider", "get",
                     f"{BC}/?min_rating=4",
                     "Filter books with minimum rating of 4.0"))
    t.append(obs(f"{BC}/?min_rating=4", 1))
    return t


def bc_extract_by_route():
    """Extract info by navigating to a specific book page."""
    t = []
    t.append(obs(f"{BC}/", 0))
    t.append(action(1, "extract_by_route", "get", f"{BC}/book/10",
                     "Navigate to book 10 detail page to extract its information"))
    t.append(obs(f"{BC}/book/10", 1))
    return t


def bc_react_by_toggle():
    """React to a review."""
    t = []
    # First create a review so there is one to react to
    do_post(f"{BC}/login", {"username": "comic_fan_alice", "password": "pass123"})
    do_post(f"{BC}/book/1/review", {"text": "Excellent book on active learning methods.", "rating": "5"})
    reviews = do_get_api(f"{BC}/api/reviews/1")
    review_id = 1
    if reviews.get("response") and len(reviews["response"]) > 0:
        review_id = reviews["response"][0]["id"]
    t.append(obs(f"{BC}/book/1", 0))
    t.append(action(1, "react_by_toggle", "post", f"{BC}/book/1/react",
                     "Like a review on book 1",
                     {"review_id": str(review_id), "reaction": "like"}))
    do_post(f"{BC}/book/1/react", {"review_id": str(review_id), "reaction": "like"})
    t.append(obs(f"{BC}/book/1", 1))
    return t


def bc_search_by_query():
    """Search books by keyword."""
    t = []
    t.append(obs(f"{BC}/", 0))
    t.append(action(1, "search_by_query", "get",
                     f"{BC}/?q=calculus",
                     "Search for books with query 'calculus'"))
    t.append(obs(f"{BC}/?q=calculus", 1))
    return t


# ===========================================================================
# CLOUD-DEV-CONSOLES macro implementations
# ===========================================================================

CC = "/sites/cloud-dev-consoles"


def cc_select_by_dropdown():
    """Select a service category from dropdown."""
    t = []
    t.append(obs(f"{CC}/services", 0))
    t.append(action(1, "select_by_dropdown", "get",
                     f"{CC}/services?category=Compute",
                     "Select 'Compute' category from services dropdown"))
    t.append(obs(f"{CC}/services?category=Compute", 1))
    return t


def cc_configure_by_query():
    """Save a query/preference for the user."""
    t = []
    do_post(f"{CC}/login", {"username": "admin_sarah", "password": "cloudpass1"})
    t.append(obs(f"{CC}/dashboard", 0))
    t.append(action(1, "configure_by_query", "post",
                     f"{CC}/api/users/1/save-query",
                     "Save a log search query for future use",
                     {"query": "level:ERROR source:api-server-prod-1"}))
    do_post_json(f"{CC}/api/users/1/save-query",
                 {"query": "level:ERROR source:api-server-prod-1"})
    t.append(obs(f"{CC}/dashboard", 1))
    return t


def cc_extract_by_dropdown():
    """Extract information by selecting a dropdown value (billing category)."""
    t = []
    t.append(obs(f"{CC}/billing", 0))
    t.append(action(1, "extract_by_dropdown", "get",
                     f"{CC}/billing?category=Compute",
                     "Filter billing to Compute category to extract cost data"))
    t.append(obs(f"{CC}/billing?category=Compute", 1))
    return t


def cc_search_by_semantic():
    """Semantic search for services."""
    t = []
    t.append(obs(f"{CC}/services", 0))
    t.append(action(1, "search_by_semantic", "get",
                     f"{CC}/api/services/semantic?q=database+storage+backup",
                     "Semantic search for database and storage related services"))
    t.append(obs_api(f"{CC}/api/services/semantic?q=database+storage+backup", 1))
    return t


def cc_select_from_table():
    """Select a specific item from instances table."""
    t = []
    t.append(obs(f"{CC}/instances", 0))
    t.append(action(1, "select_from_table", "get",
                     f"{CC}/instance/i-0a1b2c3d4e5f00003",
                     "Select api-server-prod-1 from instances table"))
    t.append(obs(f"{CC}/instance/i-0a1b2c3d4e5f00003", 1))
    return t


def cc_navigate_by_dropdown():
    """Navigate to a section via nav dropdown."""
    t = []
    t.append(obs(f"{CC}/", 0))
    t.append(action(1, "navigate_by_dropdown", "get", f"{CC}/databases",
                     "Navigate to Databases section from nav dropdown"))
    t.append(obs(f"{CC}/databases", 1))
    return t


def cc_extract_by_query():
    """Extract info by running a search/query."""
    t = []
    t.append(obs(f"{CC}/logs", 0))
    t.append(action(1, "extract_by_query", "get",
                     f"{CC}/logs?q=timeout",
                     "Search logs for 'timeout' to extract error information"))
    t.append(obs(f"{CC}/logs?q=timeout", 1))
    return t


def cc_verify_by_dropdown():
    """Verify service status by selecting status filter."""
    t = []
    t.append(obs(f"{CC}/services", 0))
    t.append(action(1, "verify_by_dropdown", "get",
                     f"{CC}/services?status=warning",
                     "Filter services by 'warning' status to verify which have issues"))
    t.append(obs(f"{CC}/services?status=warning", 1))
    return t


def cc_compute_by_slider():
    """Use CPU threshold slider to compute/filter metrics."""
    t = []
    t.append(obs(f"{CC}/metrics", 0))
    t.append(action(1, "compute_by_slider", "get",
                     f"{CC}/metrics?cpu_threshold=70",
                     "Set CPU threshold slider to 70% to identify high-usage instances"))
    t.append(obs(f"{CC}/metrics?cpu_threshold=70", 1))
    return t


def cc_filter_by_checkbox():
    """Filter instances by environment checkbox."""
    t = []
    t.append(obs(f"{CC}/instances", 0))
    t.append(action(1, "filter_by_checkbox", "get",
                     f"{CC}/instances?env=production",
                     "Check 'production' environment checkbox to filter instances"))
    t.append(obs(f"{CC}/instances?env=production", 1))
    return t


def cc_delete_from_table():
    """Delete an alert."""
    t = []
    t.append(obs(f"{CC}/alerts", 0))
    t.append(action(1, "delete_from_table", "post",
                     f"{CC}/api/alerts/alert-004/delete",
                     "Delete resolved alert 'Lambda Error Rate Spike' (alert-004)"))
    do_post_json(f"{CC}/api/alerts/alert-004/delete", {})
    t.append(obs(f"{CC}/alerts", 1))
    return t


def cc_search_by_query():
    """Search services by keyword."""
    t = []
    t.append(obs(f"{CC}/services", 0))
    t.append(action(1, "search_by_query", "get",
                     f"{CC}/services?q=lambda",
                     "Search services for 'lambda'"))
    t.append(obs(f"{CC}/services?q=lambda", 1))
    return t


def cc_export_by_dropdown():
    """Export data in CSV format."""
    t = []
    t.append(obs(f"{CC}/services", 0))
    t.append(action(1, "export_by_dropdown", "get",
                     f"{CC}/api/export?resource=services&format=csv",
                     "Export services as CSV"))
    t.append(obs_api(f"{CC}/api/export?resource=services&format=csv", 1))
    return t


def cc_compute_by_extremum():
    """Find extremum (max/min) in metrics."""
    t = []
    t.append(obs(f"{CC}/metrics", 0))
    t.append(action(1, "compute_by_extremum", "get",
                     f"{CC}/api/metrics/summary",
                     "Get metrics summary to find CPU max/min values"))
    t.append(obs_api(f"{CC}/api/metrics/summary", 1))
    return t


def cc_filter_by_dropdown():
    """Filter services by status dropdown."""
    t = []
    t.append(obs(f"{CC}/services", 0))
    t.append(action(1, "filter_by_dropdown", "get",
                     f"{CC}/services?status=active",
                     "Filter services by 'active' status"))
    t.append(obs(f"{CC}/services?status=active", 1))
    return t


def cc_extract_from_table():
    """Extract specific data from a table view."""
    t = []
    t.append(obs(f"{CC}/billing", 0))
    t.append(action(1, "extract_from_table", "get",
                     f"{CC}/billing?month=2026-06",
                     "View billing table for June 2026 to extract cost data"))
    t.append(obs(f"{CC}/billing?month=2026-06", 1))
    return t


def cc_submit_by_query():
    """Submit a configuration or query."""
    t = []
    t.append(obs(f"{CC}/alerts", 0))
    t.append(action(1, "submit_by_query", "post",
                     f"{CC}/api/alerts/create",
                     "Create a new alert rule",
                     {"name": "High Memory Alert", "severity": "warning",
                      "resource_name": "web-server-prod-1",
                      "condition": "memory > 80%", "category": "Compute"}))
    do_post_json(f"{CC}/api/alerts/create",
                 {"name": "High Memory Alert", "severity": "warning",
                  "resource_name": "web-server-prod-1",
                  "condition": "memory > 80%", "category": "Compute"})
    t.append(obs(f"{CC}/alerts", 1))
    return t


def cc_sort_by_ranking():
    """Sort services by cost."""
    t = []
    t.append(obs(f"{CC}/services", 0))
    t.append(action(1, "sort_by_ranking", "get",
                     f"{CC}/services?sort=cost",
                     "Sort services by cost (highest first)"))
    t.append(obs(f"{CC}/services?sort=cost", 1))
    return t


def cc_authenticate_by_form():
    """Login to the console."""
    t = []
    t.append(obs(f"{CC}/login", 0))
    t.append(action(1, "authenticate_by_form", "post", f"{CC}/login",
                     "Login with admin_sarah credentials",
                     {"username": "admin_sarah", "password": "cloudpass1"}))
    do_post(f"{CC}/login", {"username": "admin_sarah", "password": "cloudpass1"})
    t.append(obs(f"{CC}/dashboard", 1))
    return t


def cc_extract_by_route():
    """Navigate to a specific service detail page."""
    t = []
    t.append(obs(f"{CC}/services", 0))
    t.append(action(1, "extract_by_route", "get",
                     f"{CC}/service/svc-001",
                     "Navigate to Compute Engine service detail"))
    t.append(obs(f"{CC}/service/svc-001", 1))
    return t


def cc_navigate_by_route():
    """Navigate to a specific page."""
    t = []
    t.append(obs(f"{CC}/", 0))
    t.append(action(1, "navigate_by_route", "get", f"{CC}/functions",
                     "Navigate to Lambda Functions page"))
    t.append(obs(f"{CC}/functions", 1))
    return t


def cc_filter_by_query():
    """Filter logs or resources by search query."""
    t = []
    t.append(obs(f"{CC}/logs", 0))
    t.append(action(1, "filter_by_query", "get",
                     f"{CC}/logs?q=connection",
                     "Filter logs by search query 'connection'"))
    t.append(obs(f"{CC}/logs?q=connection", 1))
    return t


def cc_create_from_free_text():
    """Create a new alert from free text input."""
    t = []
    t.append(obs(f"{CC}/alerts", 0))
    t.append(action(1, "create_from_free_text", "post",
                     f"{CC}/api/alerts/create",
                     "Create new alert: Disk IOPS Alert",
                     {"name": "Disk IOPS Alert", "severity": "warning",
                      "resource_name": "db-primary",
                      "condition": "Disk IOPS > 5000 for 10min", "category": "Database"}))
    do_post_json(f"{CC}/api/alerts/create",
                 {"name": "Disk IOPS Alert", "severity": "warning",
                  "resource_name": "db-primary",
                  "condition": "Disk IOPS > 5000 for 10min", "category": "Database"})
    t.append(obs(f"{CC}/alerts", 1))
    return t


def cc_filter_by_date_range():
    """Filter logs by date range."""
    t = []
    t.append(obs(f"{CC}/logs", 0))
    t.append(action(1, "filter_by_date_range", "get",
                     f"{CC}/logs?date_from=2026-06-21T09:00&date_to=2026-06-21T10:00",
                     "Filter logs between 09:00 and 10:00 on June 21"))
    t.append(obs(f"{CC}/logs?date_from=2026-06-21T09:00&date_to=2026-06-21T10:00", 1))
    return t


def cc_edit_by_form():
    """Edit user preferences."""
    t = []
    do_post(f"{CC}/login", {"username": "admin_sarah", "password": "cloudpass1"})
    t.append(obs(f"{CC}/dashboard", 0))
    t.append(action(1, "edit_by_form", "post",
                     f"{CC}/api/users/1/preferences",
                     "Update user preferences (dark mode, region)",
                     {"theme": "dark", "default_region": "us-east-1", "notifications": True}))
    do_post_json(f"{CC}/api/users/1/preferences",
                 {"theme": "dark", "default_region": "us-east-1", "notifications": True})
    t.append(obs(f"{CC}/dashboard", 1))
    return t


# ===========================================================================
# Macro dispatch tables
# ===========================================================================

BC_MACROS = {
    "sort_by_ranking": bc_sort_by_ranking,
    "follow_by_toggle": bc_follow_by_toggle,
    "search_by_semantic": bc_search_by_semantic,
    "checkout_by_form": bc_checkout_by_form,
    "play_by_playback": bc_play_by_playback,
    "select_by_dropdown": bc_select_by_dropdown,
    "navigate_by_route": bc_navigate_by_route,
    "play_by_route": bc_play_by_route,
    "navigate_by_dropdown": bc_navigate_by_dropdown,
    "subscribe_by_toggle": bc_subscribe_by_toggle,
    "save_by_toggle": bc_save_by_toggle,
    "post_from_free_text": bc_post_from_free_text,
    "filter_by_dropdown": bc_filter_by_dropdown,
    "rate_by_slider": bc_rate_by_slider,
    "add_by_button": bc_add_by_button,
    "filter_by_slider": bc_filter_by_slider,
    "extract_by_route": bc_extract_by_route,
    "react_by_toggle": bc_react_by_toggle,
    "search_by_query": bc_search_by_query,
}

CC_MACROS = {
    "select_by_dropdown": cc_select_by_dropdown,
    "configure_by_query": cc_configure_by_query,
    "extract_by_dropdown": cc_extract_by_dropdown,
    "search_by_semantic": cc_search_by_semantic,
    "select_from_table": cc_select_from_table,
    "navigate_by_dropdown": cc_navigate_by_dropdown,
    "extract_by_query": cc_extract_by_query,
    "verify_by_dropdown": cc_verify_by_dropdown,
    "compute_by_slider": cc_compute_by_slider,
    "filter_by_checkbox": cc_filter_by_checkbox,
    "delete_from_table": cc_delete_from_table,
    "search_by_query": cc_search_by_query,
    "export_by_dropdown": cc_export_by_dropdown,
    "compute_by_extremum": cc_compute_by_extremum,
    "filter_by_dropdown": cc_filter_by_dropdown,
    "extract_from_table": cc_extract_from_table,
    "submit_by_query": cc_submit_by_query,
    "sort_by_ranking": cc_sort_by_ranking,
    "authenticate_by_form": cc_authenticate_by_form,
    "extract_by_route": cc_extract_by_route,
    "navigate_by_route": cc_navigate_by_route,
    "filter_by_query": cc_filter_by_query,
    "create_from_free_text": cc_create_from_free_text,
    "filter_by_date_range": cc_filter_by_date_range,
    "edit_by_form": cc_edit_by_form,
}


# ===========================================================================
# Variant generators for multi-step chains
# These provide DIFFERENT parameters for each macro instance in a chain
# to avoid always using the same params.
# ===========================================================================

# Books-comics variants
BC_VARIANTS = {
    "sort_by_ranking": [
        ("rating", f"{BC}/?sort=rating", "Sort books by rating"),
        ("price_low", f"{BC}/?sort=price_low", "Sort books by price (low to high)"),
        ("title", f"{BC}/?sort=title", "Sort books by title"),
        ("price_high", f"{BC}/?sort=price_high", "Sort books by price (high to low)"),
    ],
    "follow_by_toggle": [
        (1, "Active Learning Network"),
        (2, "marcellinoberardo"),
        (5, "OpenStax"),
        (9, "Dale Hoffman"),
    ],
    "search_by_semantic": [
        ("biology+science", f"{BC}/api/books/semantic?q=biology+science"),
        ("art+design", f"{BC}/api/books/semantic?q=art+design"),
        ("nursing+health", f"{BC}/api/books/semantic?q=nursing+health"),
    ],
    "checkout_by_form": [
        ("Alice Wonder", "alice@example.com", "4111111111111111"),
    ],
    "play_by_playback": [
        (1, 2, 50), (3, 1, 25), (5, 3, 75),
    ],
    "select_by_dropdown": [
        ("science", "Science & Technology"),
        ("fiction", "Fiction"),
        ("health", "Health & Medicine"),
        ("business", "Business & Economics"),
    ],
    "navigate_by_route": [
        (f"{BC}/dashboard", "Navigate to user dashboard"),
        (f"{BC}/cart", "Navigate to shopping cart"),
        (f"{BC}/category/arts", "Navigate to Arts category page"),
    ],
    "play_by_route": [
        (5, 1), (10, 2), (20, 1), (1, 3),
    ],
    "navigate_by_dropdown": [
        ("fiction", "Fiction"),
        ("science", "Science & Technology"),
        ("humanities", "Humanities & Social Sciences"),
        ("education", "Education & Teaching"),
        ("arts", "Arts & Design"),
    ],
    "subscribe_by_toggle": [
        (3, "science"),
        (1, "humanities"),
        (20, "education"),
        (40, "health"),
    ],
    "save_by_toggle": [
        5, 10, 15, 20, 25,
    ],
    "post_from_free_text": [
        (2, "Great introduction to English pronunciation. Very helpful.", "4"),
        (5, "A comprehensive overview of American government.", "3"),
        (10, "Solid stats reference. Useful for students.", "4"),
    ],
    "filter_by_dropdown": [
        ("business", "Business & Economics"),
        ("health", "Health & Medicine"),
        ("arts", "Arts & Design"),
        ("education", "Education & Teaching"),
    ],
    "rate_by_slider": [
        (3, "4"), (5, "5"), (10, "3"), (20, "4"),
    ],
    "add_by_button": [
        1, 3, 5, 10, 15,
    ],
    "filter_by_slider": [
        "4", "3.5", "4.5", "3",
    ],
    "extract_by_route": [
        (10, f"{BC}/book/10"), (20, f"{BC}/book/20"),
        (50, f"{BC}/book/50"), (1, f"{BC}/book/1"),
        (30, f"{BC}/book/30"),
    ],
    "react_by_toggle": [
        "like", "helpful", "interesting",
    ],
    "search_by_query": [
        "calculus", "biology", "nursing", "economics", "shakespeare",
    ],
}

# Cloud-dev-consoles variants
CC_VARIANTS = {
    "select_by_dropdown": [
        ("Compute", f"{CC}/services?category=Compute"),
        ("Database", f"{CC}/services?category=Database"),
        ("Networking", f"{CC}/services?category=Networking"),
        ("Storage", f"{CC}/services?category=Storage"),
        ("Security", f"{CC}/services?category=Security"),
    ],
    "configure_by_query": [
        "level:ERROR source:api-server-prod-1",
        "category:Database severity:critical",
        "status:running region:us-east-1",
    ],
    "extract_by_dropdown": [
        ("Compute", f"{CC}/billing?category=Compute"),
        ("Database", f"{CC}/billing?category=Database"),
        ("Storage", f"{CC}/billing?category=Storage"),
        ("Networking", f"{CC}/billing?category=Networking"),
    ],
    "search_by_semantic": [
        ("database+storage+backup", f"{CC}/api/services/semantic?q=database+storage+backup"),
        ("compute+lambda+serverless", f"{CC}/api/services/semantic?q=compute+lambda+serverless"),
        ("security+firewall+access", f"{CC}/api/services/semantic?q=security+firewall+access"),
    ],
    "select_from_table": [
        ("i-0a1b2c3d4e5f00003", "api-server-prod-1"),
        ("i-0a1b2c3d4e5f00001", "web-server-prod-1"),
        ("i-0a1b2c3d4e5f00005", "db-primary"),
        ("i-0a1b2c3d4e5f00009", "ml-training-gpu"),
    ],
    "navigate_by_dropdown": [
        (f"{CC}/databases", "Databases"),
        (f"{CC}/functions", "Functions"),
        (f"{CC}/storage", "Storage"),
        (f"{CC}/iam", "IAM"),
        (f"{CC}/billing", "Billing"),
        (f"{CC}/logs", "Logs"),
        (f"{CC}/metrics", "Metrics"),
        (f"{CC}/alerts", "Alerts"),
    ],
    "extract_by_query": [
        ("timeout", f"{CC}/logs?q=timeout"),
        ("failed", f"{CC}/logs?q=failed"),
        ("connection", f"{CC}/logs?q=connection"),
    ],
    "verify_by_dropdown": [
        ("warning", f"{CC}/services?status=warning"),
        ("active", f"{CC}/services?status=active"),
        ("stopped", f"{CC}/services?status=stopped"),
    ],
    "compute_by_slider": [
        70, 50, 80, 90,
    ],
    "filter_by_checkbox": [
        "production", "staging", "development",
    ],
    "delete_from_table": [
        ("alert-004", "Lambda Error Rate Spike"),
        ("alert-010", "Disk Space Low"),
    ],
    "search_by_query": [
        ("lambda", f"{CC}/services?q=lambda"),
        ("cdn", f"{CC}/services?q=cdn"),
        ("api", f"{CC}/services?q=api"),
        ("cache", f"{CC}/services?q=cache"),
    ],
    "export_by_dropdown": [
        ("services", "csv"), ("instances", "csv"),
        ("databases", "json"), ("billing", "csv"),
    ],
    "compute_by_extremum": [
        ("", f"{CC}/api/metrics/summary"),
        ("i-0a1b2c3d4e5f00003", f"{CC}/api/metrics/summary?instance_id=i-0a1b2c3d4e5f00003"),
    ],
    "filter_by_dropdown": [
        ("active", f"{CC}/services?status=active"),
        ("warning", f"{CC}/services?status=warning"),
    ],
    "extract_from_table": [
        ("2026-06", f"{CC}/billing?month=2026-06"),
        ("2026-05", f"{CC}/billing?month=2026-05"),
        ("2026-04", f"{CC}/billing?month=2026-04"),
    ],
    "submit_by_query": [
        ("High Memory Alert", "warning", "web-server-prod-1", "memory > 80%", "Compute"),
        ("Network Latency Alert", "critical", "API Gateway", "latency > 500ms", "Networking"),
    ],
    "sort_by_ranking": [
        ("cost", f"{CC}/services?sort=cost"),
        ("name", f"{CC}/services?sort=name"),
        ("category", f"{CC}/services?sort=category"),
    ],
    "authenticate_by_form": [
        ("admin_sarah", "cloudpass1"),
    ],
    "extract_by_route": [
        ("svc-001", "Compute Engine"),
        ("svc-006", "Relational DB"),
        ("svc-009", "API Gateway"),
        ("svc-003", "Lambda Functions"),
        ("svc-020", "Alert Manager"),
    ],
    "navigate_by_route": [
        (f"{CC}/functions", "Lambda Functions"),
        (f"{CC}/storage", "Storage"),
        (f"{CC}/api-gateway", "API Gateway"),
        (f"{CC}/iam", "IAM"),
        (f"{CC}/billing", "Billing"),
    ],
    "filter_by_query": [
        ("connection", f"{CC}/logs?q=connection"),
        ("timeout", f"{CC}/logs?q=timeout"),
        ("failed", f"{CC}/logs?q=failed"),
        ("sql", f"{CC}/logs?q=sql"),
    ],
    "create_from_free_text": [
        ("Disk IOPS Alert", "warning", "db-primary", "Disk IOPS > 5000", "Database"),
        ("Network Spike Alert", "critical", "CDN Service", "Bandwidth > 10Gbps", "Networking"),
    ],
    "filter_by_date_range": [
        ("2026-06-21T09:00", "2026-06-21T10:00"),
        ("2026-06-21T08:00", "2026-06-21T09:00"),
    ],
    "edit_by_form": [
        ({"theme": "dark", "default_region": "us-east-1", "notifications": True},),
        ({"theme": "light", "default_region": "us-west-2", "notifications": False},),
    ],
}


def walk_multi_chain_bc(chain_id, macros):
    """Walk a multi-step chain for books-comics. Use variant data to avoid repetition."""
    # Track how many times each macro has been used in this chain
    usage_counts = {}
    trajectory = []
    step = 0

    do_reset()
    do_post(f"{BC}/login", {"username": "comic_fan_alice", "password": "pass123"})

    # Initial observation
    trajectory.append(obs(f"{BC}/", step))

    for macro_name in macros:
        idx = usage_counts.get(macro_name, 0)
        usage_counts[macro_name] = idx + 1
        step += 1

        # Execute the macro with variant data
        if macro_name == "sort_by_ranking":
            variants = BC_VARIANTS["sort_by_ranking"]
            v = variants[idx % len(variants)]
            trajectory.append(action(step, macro_name, "get", v[1], v[2]))
            trajectory.append(obs(v[1], step))

        elif macro_name == "follow_by_toggle":
            variants = BC_VARIANTS["follow_by_toggle"]
            v = variants[idx % len(variants)]
            trajectory.append(action(step, macro_name, "post", f"{BC}/book/{v[0]}/follow",
                                     f"Toggle follow on author '{v[1]}'", {"author": v[1]}))
            do_post(f"{BC}/book/{v[0]}/follow", {"author": v[1]})
            trajectory.append(obs(f"{BC}/book/{v[0]}", step))

        elif macro_name == "search_by_semantic":
            variants = BC_VARIANTS["search_by_semantic"]
            v = variants[idx % len(variants)]
            trajectory.append(action(step, macro_name, "get", v[1],
                                     f"Semantic search for '{v[0]}'"))
            trajectory.append(obs_api(v[1], step))

        elif macro_name == "checkout_by_form":
            # Ensure something in cart
            do_post(f"{BC}/book/{2+idx}/cart", {})
            trajectory.append(action(step, macro_name, "post", f"{BC}/checkout",
                                     "Submit checkout form",
                                     {"name": "Alice Wonder", "email": "alice@example.com", "card": "4111111111111111"}))
            do_post(f"{BC}/checkout", {"name": "Alice Wonder", "email": "alice@example.com", "card": "4111111111111111"})
            trajectory.append(obs(f"{BC}/checkout", step))

        elif macro_name == "play_by_playback":
            variants = BC_VARIANTS["play_by_playback"]
            v = variants[idx % len(variants)]
            trajectory.append(action(step, macro_name, "post",
                                     f"{BC}/api/users/1/reading-progress",
                                     f"Update reading progress: book {v[0]}, ch {v[1]}, {v[2]}%",
                                     {"book_id": v[0], "chapter": v[1], "progress": v[2]}))
            do_post_json(f"{BC}/api/users/1/reading-progress",
                         {"book_id": v[0], "chapter": v[1], "progress": v[2]})
            trajectory.append(obs(f"{BC}/book/{v[0]}/read?chapter={v[1]}", step))

        elif macro_name == "select_by_dropdown":
            variants = BC_VARIANTS["select_by_dropdown"]
            v = variants[idx % len(variants)]
            url = f"{BC}/?category={v[0]}"
            trajectory.append(action(step, macro_name, "get", url,
                                     f"Select '{v[1]}' from category dropdown"))
            trajectory.append(obs(url, step))

        elif macro_name == "navigate_by_route":
            variants = BC_VARIANTS["navigate_by_route"]
            v = variants[idx % len(variants)]
            trajectory.append(action(step, macro_name, "get", v[0], v[1]))
            trajectory.append(obs(v[0], step))

        elif macro_name == "play_by_route":
            variants = BC_VARIANTS["play_by_route"]
            v = variants[idx % len(variants)]
            url = f"{BC}/book/{v[0]}/read?chapter={v[1]}"
            trajectory.append(action(step, macro_name, "get", url,
                                     f"Open reader for book {v[0]} chapter {v[1]}"))
            trajectory.append(obs(url, step))

        elif macro_name == "navigate_by_dropdown":
            variants = BC_VARIANTS["navigate_by_dropdown"]
            v = variants[idx % len(variants)]
            url = f"{BC}/category/{v[0]}"
            trajectory.append(action(step, macro_name, "get", url,
                                     f"Navigate to {v[1]} category"))
            trajectory.append(obs(url, step))

        elif macro_name == "subscribe_by_toggle":
            variants = BC_VARIANTS["subscribe_by_toggle"]
            v = variants[idx % len(variants)]
            trajectory.append(action(step, macro_name, "post", f"{BC}/book/{v[0]}/subscribe",
                                     f"Subscribe to '{v[1]}' category", {"category": v[1]}))
            do_post(f"{BC}/book/{v[0]}/subscribe", {"category": v[1]})
            trajectory.append(obs(f"{BC}/book/{v[0]}", step))

        elif macro_name == "save_by_toggle":
            variants = BC_VARIANTS["save_by_toggle"]
            v = variants[idx % len(variants)]
            trajectory.append(action(step, macro_name, "post", f"{BC}/book/{v}/save",
                                     f"Save book {v} to library"))
            do_post(f"{BC}/book/{v}/save", {})
            trajectory.append(obs(f"{BC}/book/{v}", step))

        elif macro_name == "post_from_free_text":
            variants = BC_VARIANTS["post_from_free_text"]
            v = variants[idx % len(variants)]
            trajectory.append(action(step, macro_name, "post", f"{BC}/book/{v[0]}/review",
                                     f"Post review for book {v[0]}",
                                     {"text": v[1], "rating": v[2]}))
            do_post(f"{BC}/book/{v[0]}/review", {"text": v[1], "rating": v[2]})
            trajectory.append(obs(f"{BC}/book/{v[0]}", step))

        elif macro_name == "filter_by_dropdown":
            variants = BC_VARIANTS["filter_by_dropdown"]
            v = variants[idx % len(variants)]
            url = f"{BC}/?category={v[0]}"
            trajectory.append(action(step, macro_name, "get", url,
                                     f"Filter by '{v[1]}' category"))
            trajectory.append(obs(url, step))

        elif macro_name == "rate_by_slider":
            variants = BC_VARIANTS["rate_by_slider"]
            v = variants[idx % len(variants)]
            trajectory.append(action(step, macro_name, "post", f"{BC}/book/{v[0]}/rate",
                                     f"Rate book {v[0]} with {v[1]} stars",
                                     {"rating": v[1]}))
            do_post(f"{BC}/book/{v[0]}/rate", {"rating": v[1]})
            trajectory.append(obs(f"{BC}/book/{v[0]}", step))

        elif macro_name == "add_by_button":
            variants = BC_VARIANTS["add_by_button"]
            v = variants[idx % len(variants)]
            trajectory.append(action(step, macro_name, "post", f"{BC}/book/{v}/cart",
                                     f"Add book {v} to cart"))
            do_post(f"{BC}/book/{v}/cart", {})
            trajectory.append(obs(f"{BC}/book/{v}", step))

        elif macro_name == "filter_by_slider":
            variants = BC_VARIANTS["filter_by_slider"]
            v = variants[idx % len(variants)]
            url = f"{BC}/?min_rating={v}"
            trajectory.append(action(step, macro_name, "get", url,
                                     f"Filter books with min rating {v}"))
            trajectory.append(obs(url, step))

        elif macro_name == "extract_by_route":
            variants = BC_VARIANTS["extract_by_route"]
            v = variants[idx % len(variants)]
            trajectory.append(action(step, macro_name, "get", v[1],
                                     f"Navigate to book {v[0]} detail to extract info"))
            trajectory.append(obs(v[1], step))

        elif macro_name == "react_by_toggle":
            # First ensure a review exists
            book_id = 1 + idx
            do_post(f"{BC}/book/{book_id}/review",
                    {"text": f"Review for book {book_id}.", "rating": "4"})
            reviews_result = do_get_api(f"{BC}/api/reviews/{book_id}")
            review_id = 1
            if reviews_result.get("response") and len(reviews_result["response"]) > 0:
                review_id = reviews_result["response"][-1]["id"]
            reaction = BC_VARIANTS["react_by_toggle"][idx % len(BC_VARIANTS["react_by_toggle"])]
            trajectory.append(action(step, macro_name, "post", f"{BC}/book/{book_id}/react",
                                     f"React '{reaction}' to review {review_id}",
                                     {"review_id": str(review_id), "reaction": reaction}))
            do_post(f"{BC}/book/{book_id}/react", {"review_id": str(review_id), "reaction": reaction})
            trajectory.append(obs(f"{BC}/book/{book_id}", step))

        elif macro_name == "search_by_query":
            variants = BC_VARIANTS["search_by_query"]
            v = variants[idx % len(variants)]
            url = f"{BC}/?q={v}"
            trajectory.append(action(step, macro_name, "get", url,
                                     f"Search for '{v}'"))
            trajectory.append(obs(url, step))

    return trajectory


def walk_multi_chain_cc(chain_id, macros):
    """Walk a multi-step chain for cloud-dev-consoles."""
    usage_counts = {}
    trajectory = []
    step = 0

    do_reset()

    # Initial observation
    trajectory.append(obs(f"{CC}/", step))

    for macro_name in macros:
        idx = usage_counts.get(macro_name, 0)
        usage_counts[macro_name] = idx + 1
        step += 1

        if macro_name == "select_by_dropdown":
            variants = CC_VARIANTS["select_by_dropdown"]
            v = variants[idx % len(variants)]
            trajectory.append(action(step, macro_name, "get", v[1],
                                     f"Select '{v[0]}' category"))
            trajectory.append(obs(v[1], step))

        elif macro_name == "configure_by_query":
            variants = CC_VARIANTS["configure_by_query"]
            v = variants[idx % len(variants)]
            do_post(f"{CC}/login", {"username": "admin_sarah", "password": "cloudpass1"})
            trajectory.append(action(step, macro_name, "post",
                                     f"{CC}/api/users/1/save-query",
                                     f"Save query: '{v}'", {"query": v}))
            do_post_json(f"{CC}/api/users/1/save-query", {"query": v})
            trajectory.append(obs(f"{CC}/dashboard", step))

        elif macro_name == "extract_by_dropdown":
            variants = CC_VARIANTS["extract_by_dropdown"]
            v = variants[idx % len(variants)]
            trajectory.append(action(step, macro_name, "get", v[1],
                                     f"Filter billing to {v[0]} to extract cost data"))
            trajectory.append(obs(v[1], step))

        elif macro_name == "search_by_semantic":
            variants = CC_VARIANTS["search_by_semantic"]
            v = variants[idx % len(variants)]
            trajectory.append(action(step, macro_name, "get", v[1],
                                     f"Semantic search: '{v[0]}'"))
            trajectory.append(obs_api(v[1], step))

        elif macro_name == "select_from_table":
            variants = CC_VARIANTS["select_from_table"]
            v = variants[idx % len(variants)]
            url = f"{CC}/instance/{v[0]}"
            trajectory.append(action(step, macro_name, "get", url,
                                     f"Select {v[1]} from instances table"))
            trajectory.append(obs(url, step))

        elif macro_name == "navigate_by_dropdown":
            variants = CC_VARIANTS["navigate_by_dropdown"]
            v = variants[idx % len(variants)]
            trajectory.append(action(step, macro_name, "get", v[0],
                                     f"Navigate to {v[1]}"))
            trajectory.append(obs(v[0], step))

        elif macro_name == "extract_by_query":
            variants = CC_VARIANTS["extract_by_query"]
            v = variants[idx % len(variants)]
            trajectory.append(action(step, macro_name, "get", v[1],
                                     f"Search logs for '{v[0]}'"))
            trajectory.append(obs(v[1], step))

        elif macro_name == "verify_by_dropdown":
            variants = CC_VARIANTS["verify_by_dropdown"]
            v = variants[idx % len(variants)]
            trajectory.append(action(step, macro_name, "get", v[1],
                                     f"Filter services by status='{v[0]}'"))
            trajectory.append(obs(v[1], step))

        elif macro_name == "compute_by_slider":
            variants = CC_VARIANTS["compute_by_slider"]
            v = variants[idx % len(variants)]
            url = f"{CC}/metrics?cpu_threshold={v}"
            trajectory.append(action(step, macro_name, "get", url,
                                     f"Set CPU threshold to {v}%"))
            trajectory.append(obs(url, step))

        elif macro_name == "filter_by_checkbox":
            variants = CC_VARIANTS["filter_by_checkbox"]
            v = variants[idx % len(variants)]
            url = f"{CC}/instances?env={v}"
            trajectory.append(action(step, macro_name, "get", url,
                                     f"Filter instances by env={v}"))
            trajectory.append(obs(url, step))

        elif macro_name == "delete_from_table":
            variants = CC_VARIANTS["delete_from_table"]
            v = variants[idx % len(variants)]
            trajectory.append(action(step, macro_name, "post",
                                     f"{CC}/api/alerts/{v[0]}/delete",
                                     f"Delete alert '{v[1]}' ({v[0]})"))
            do_post_json(f"{CC}/api/alerts/{v[0]}/delete", {})
            trajectory.append(obs(f"{CC}/alerts", step))

        elif macro_name == "search_by_query":
            variants = CC_VARIANTS["search_by_query"]
            v = variants[idx % len(variants)]
            trajectory.append(action(step, macro_name, "get", v[1],
                                     f"Search services for '{v[0]}'"))
            trajectory.append(obs(v[1], step))

        elif macro_name == "export_by_dropdown":
            variants = CC_VARIANTS["export_by_dropdown"]
            v = variants[idx % len(variants)]
            url = f"{CC}/api/export?resource={v[0]}&format={v[1]}"
            trajectory.append(action(step, macro_name, "get", url,
                                     f"Export {v[0]} as {v[1]}"))
            trajectory.append(obs_api(url, step))

        elif macro_name == "compute_by_extremum":
            variants = CC_VARIANTS["compute_by_extremum"]
            v = variants[idx % len(variants)]
            trajectory.append(action(step, macro_name, "get", v[1],
                                     "Get metrics summary for extremum values"))
            trajectory.append(obs_api(v[1], step))

        elif macro_name == "filter_by_dropdown":
            variants = CC_VARIANTS["filter_by_dropdown"]
            v = variants[idx % len(variants)]
            trajectory.append(action(step, macro_name, "get", v[1],
                                     f"Filter services by status={v[0]}"))
            trajectory.append(obs(v[1], step))

        elif macro_name == "extract_from_table":
            variants = CC_VARIANTS["extract_from_table"]
            v = variants[idx % len(variants)]
            trajectory.append(action(step, macro_name, "get", v[1],
                                     f"View billing for {v[0]}"))
            trajectory.append(obs(v[1], step))

        elif macro_name == "submit_by_query":
            variants = CC_VARIANTS["submit_by_query"]
            v = variants[idx % len(variants)]
            data = {"name": v[0], "severity": v[1], "resource_name": v[2],
                    "condition": v[3], "category": v[4]}
            trajectory.append(action(step, macro_name, "post",
                                     f"{CC}/api/alerts/create",
                                     f"Create alert: {v[0]}", data))
            do_post_json(f"{CC}/api/alerts/create", data)
            trajectory.append(obs(f"{CC}/alerts", step))

        elif macro_name == "sort_by_ranking":
            variants = CC_VARIANTS["sort_by_ranking"]
            v = variants[idx % len(variants)]
            trajectory.append(action(step, macro_name, "get", v[1],
                                     f"Sort services by {v[0]}"))
            trajectory.append(obs(v[1], step))

        elif macro_name == "authenticate_by_form":
            trajectory.append(action(step, macro_name, "post", f"{CC}/login",
                                     "Login with admin_sarah",
                                     {"username": "admin_sarah", "password": "cloudpass1"}))
            do_post(f"{CC}/login", {"username": "admin_sarah", "password": "cloudpass1"})
            trajectory.append(obs(f"{CC}/dashboard", step))

        elif macro_name == "extract_by_route":
            variants = CC_VARIANTS["extract_by_route"]
            v = variants[idx % len(variants)]
            url = f"{CC}/service/{v[0]}"
            trajectory.append(action(step, macro_name, "get", url,
                                     f"Navigate to {v[1]} detail"))
            trajectory.append(obs(url, step))

        elif macro_name == "navigate_by_route":
            variants = CC_VARIANTS["navigate_by_route"]
            v = variants[idx % len(variants)]
            trajectory.append(action(step, macro_name, "get", v[0],
                                     f"Navigate to {v[1]}"))
            trajectory.append(obs(v[0], step))

        elif macro_name == "filter_by_query":
            variants = CC_VARIANTS["filter_by_query"]
            v = variants[idx % len(variants)]
            trajectory.append(action(step, macro_name, "get", v[1],
                                     f"Filter logs by '{v[0]}'"))
            trajectory.append(obs(v[1], step))

        elif macro_name == "create_from_free_text":
            variants = CC_VARIANTS["create_from_free_text"]
            v = variants[idx % len(variants)]
            data = {"name": v[0], "severity": v[1], "resource_name": v[2],
                    "condition": v[3], "category": v[4]}
            trajectory.append(action(step, macro_name, "post",
                                     f"{CC}/api/alerts/create",
                                     f"Create alert: {v[0]}", data))
            do_post_json(f"{CC}/api/alerts/create", data)
            trajectory.append(obs(f"{CC}/alerts", step))

        elif macro_name == "filter_by_date_range":
            variants = CC_VARIANTS["filter_by_date_range"]
            v = variants[idx % len(variants)]
            url = f"{CC}/logs?date_from={v[0]}&date_to={v[1]}"
            trajectory.append(action(step, macro_name, "get", url,
                                     f"Filter logs from {v[0]} to {v[1]}"))
            trajectory.append(obs(url, step))

        elif macro_name == "edit_by_form":
            variants = CC_VARIANTS["edit_by_form"]
            v = variants[idx % len(variants)]
            do_post(f"{CC}/login", {"username": "admin_sarah", "password": "cloudpass1"})
            trajectory.append(action(step, macro_name, "post",
                                     f"{CC}/api/users/1/preferences",
                                     "Update user preferences", v[0]))
            do_post_json(f"{CC}/api/users/1/preferences", v[0])
            trajectory.append(obs(f"{CC}/dashboard", step))

    return trajectory


def walk_all():
    """Walk all chains for both sites."""
    # Load chain definitions
    for site_id in ["books-comics", "cloud-dev-consoles"]:
        chain_file = CHAINS_DIR / f"{site_id}.json"
        chains = json.loads(chain_file.read_text())

        macro_table = BC_MACROS if site_id == "books-comics" else CC_MACROS
        multi_walker = walk_multi_chain_bc if site_id == "books-comics" else walk_multi_chain_cc

        for chain in chains:
            chain_id = chain["chain_id"]
            macros = chain["macros"]
            run_dir = RUNS_DIR / site_id / chain_id

            # Skip if already done
            if (run_dir / "status.json").exists():
                print(f"  SKIP {chain_id} (already done)")
                continue

            print(f"  Walking {chain_id} ({chain['difficulty']}, {len(macros)} macros)...")

            try:
                do_reset()

                if len(macros) == 1:
                    # Easy chain: single macro
                    macro_name = macros[0]
                    func = macro_table.get(macro_name)
                    if func:
                        trajectory = func()
                    else:
                        print(f"    WARNING: No handler for macro {macro_name}")
                        trajectory = []
                else:
                    # Medium/hard: multi-step
                    trajectory = multi_walker(chain_id, macros)

                save_chain(site_id, chain_id, trajectory, valid=True)
                print(f"    OK ({len(trajectory)} entries)")

            except Exception as e:
                print(f"    ERROR: {e}")
                import traceback
                traceback.print_exc()
                # Save with error status
                save_chain(site_id, chain_id, [], valid=False)


if __name__ == "__main__":
    walk_all()
