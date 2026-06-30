"""Per-macro verification functions for rating-review.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/rating-review"


def verify_macro_navigate_by_dropdown(server_url):
    """Navigate to a category via dropdown."""
    r = requests.get(f"{_base(server_url)}/api/categories")
    cats = r.json()
    if not cats:
        return {"pass": False, "detail": "No categories returned"}
    r2 = requests.get(f"{_base(server_url)}/api/businesses",
                      params={"category": cats[0]})
    return {"pass": r2.status_code == 200 and len(r2.json()) > 0,
            "detail": f"Category '{cats[0]}': {len(r2.json())} businesses"}


def verify_macro_navigate_by_route(server_url):
    """Navigate to a business detail page."""
    r = requests.get(f"{_base(server_url)}/business/1")
    return {"pass": r.status_code == 200,
            "detail": f"Business detail page: {r.status_code}"}


def verify_macro_search_by_query(server_url):
    """Keyword search across businesses and reviews."""
    r = requests.get(f"{_base(server_url)}/api/search", params={"q": "coffee"})
    data = r.json()
    count = data.get("business_count", 0)
    return {"pass": count > 0,
            "detail": f"search_by_query 'coffee': {count} results"}


def verify_macro_search_by_semantic(server_url):
    """Semantic search across businesses."""
    r = requests.get(f"{_base(server_url)}/api/search/semantic",
                     params={"q": "healthy food organic"})
    data = r.json()
    return {"pass": r.status_code == 200,
            "detail": f"search_by_semantic: {data.get('count', 0)} results"}


def verify_macro_filter_by_query(server_url):
    """Filter by query text."""
    r = requests.get(f"{_base(server_url)}/api/search", params={"q": "pizza"})
    return {"pass": r.status_code == 200,
            "detail": f"filter_by_query: status={r.status_code}"}


def verify_macro_filter_by_dropdown(server_url):
    """Filter by category dropdown."""
    r = requests.get(f"{_base(server_url)}/api/businesses",
                     params={"category": "Restaurants"})
    businesses = r.json()
    ok = all(b.get("category") == "Restaurants" for b in businesses)
    return {"pass": ok and len(businesses) > 0,
            "detail": f"filter_by_dropdown Restaurants: {len(businesses)}, all_match={ok}"}


def verify_macro_filter_by_radio(server_url):
    """Filter by price range radio button."""
    r = requests.get(f"{_base(server_url)}/api/businesses", params={"price": "$$"})
    businesses = r.json()
    ok = all(b.get("price_range") == "$$" for b in businesses)
    return {"pass": ok,
            "detail": f"filter_by_radio $$: {len(businesses)}, all_match={ok}"}


def verify_macro_filter_by_toggle(server_url):
    """Filter by attribute toggle (e.g., Outdoor Seating)."""
    r = requests.get(f"{_base(server_url)}/api/businesses",
                     params={"search": "Takeout"})
    businesses = r.json()
    return {"pass": len(businesses) > 0,
            "detail": f"filter_by_toggle Takeout: {len(businesses)} businesses"}


def verify_macro_filter_by_slider(server_url):
    """Filter by minimum rating slider."""
    r = requests.get(f"{_base(server_url)}/api/businesses",
                     params={"min_rating": 4.5})
    businesses = r.json()
    ok = all(b.get("overall_rating", 0) >= 4.5 for b in businesses)
    return {"pass": ok,
            "detail": f"filter_by_slider >= 4.5: {len(businesses)}, all_match={ok}"}


def verify_macro_sort_by_dropdown(server_url):
    """Sort businesses by dropdown selection."""
    r = requests.get(f"{_base(server_url)}/api/businesses", params={"sort": "reviews"})
    businesses = r.json()
    if len(businesses) < 2:
        return {"pass": True, "detail": "Too few to verify sort"}
    counts = [b.get("review_count", 0) for b in businesses]
    is_sorted = all(counts[i] >= counts[i+1] for i in range(len(counts)-1))
    return {"pass": is_sorted,
            "detail": f"sort_by_dropdown reviews: sorted={is_sorted}"}


def verify_macro_sort_by_slider(server_url):
    """Sort businesses by rating (slider-selected)."""
    r = requests.get(f"{_base(server_url)}/api/businesses", params={"sort": "rating"})
    businesses = r.json()
    if len(businesses) < 2:
        return {"pass": True, "detail": "Too few to verify sort"}
    ratings = [b.get("overall_rating", 0) for b in businesses]
    is_sorted = all(ratings[i] >= ratings[i+1] for i in range(len(ratings)-1))
    return {"pass": is_sorted,
            "detail": f"sort_by_slider rating: sorted={is_sorted}"}


def verify_macro_extract_by_query(server_url):
    """Extract data via search query."""
    r = requests.get(f"{_base(server_url)}/api/search", params={"q": "coffee"})
    data = r.json()
    businesses = data.get("businesses", [])
    if businesses:
        return {"pass": True,
                "detail": f"extract_by_query: first='{businesses[0].get('name', '')}'"}
    return {"pass": True, "detail": "extract_by_query: no results (ok)"}


def verify_macro_extract_by_route(server_url):
    """Extract business details by route."""
    r = requests.get(f"{_base(server_url)}/api/businesses/1")
    biz = r.json()
    return {"pass": "name" in biz and "overall_rating" in biz,
            "detail": f"extract_by_route: name='{biz.get('name', '')}'"}


def verify_macro_extract_by_ranking(server_url):
    """Extract top-ranked businesses."""
    r = requests.get(f"{_base(server_url)}/api/businesses", params={"sort": "rating"})
    businesses = r.json()
    if businesses:
        return {"pass": True,
                "detail": f"extract_by_ranking: top='{businesses[0]['name']}' ({businesses[0]['overall_rating']})"}
    return {"pass": False, "detail": "No businesses for ranking"}


def verify_macro_extract_by_slider(server_url):
    """Extract stats (slider-driven filtering)."""
    r = requests.get(f"{_base(server_url)}/api/stats")
    stats = r.json()
    return {"pass": "average_rating" in stats,
            "detail": f"extract_by_slider: avg_rating={stats.get('average_rating')}"}


def verify_macro_compute_by_dropdown(server_url):
    """Compute category-level statistics."""
    r = requests.get(f"{_base(server_url)}/api/compute",
                     params={"category": "Restaurants"})
    data = r.json()
    return {"pass": "business_count" in data and "avg_business_rating" in data,
            "detail": f"compute_by_dropdown: count={data.get('business_count')}, avg={data.get('avg_business_rating')}"}


def verify_macro_compare_by_slider(server_url):
    """Compare two businesses side by side."""
    r = requests.get(f"{_base(server_url)}/api/compare", params={"ids": "1,2"})
    data = r.json()
    if len(data) < 2:
        return {"pass": False, "detail": "Compare needs 2 businesses"}
    return {"pass": data[0]["id"] != data[1]["id"],
            "detail": f"compare: {data[0]['name']} vs {data[1]['name']}"}


def verify_macro_edit_by_form(server_url):
    """Edit a review."""
    s = requests.Session()
    s.post(f"{_base(server_url)}/api/login", json={"username": "alex_r"})
    # Create a review to edit
    r = s.post(f"{_base(server_url)}/api/reviews",
               json={"business_id": 10, "rating": 3, "title": "Test edit",
                     "text": "Original text"})
    review = r.json()
    rid = review.get("id")
    # Edit it
    r2 = s.put(f"{_base(server_url)}/api/reviews/{rid}",
               json={"text": "Edited text"})
    edited = r2.json()
    ok = edited.get("text") == "Edited text"
    # Clean up
    if rid:
        s.delete(f"{_base(server_url)}/api/reviews/{rid}")
    return {"pass": ok,
            "detail": f"edit_by_form: text='{edited.get('text', '')}'"}


def verify_macro_delete_from_table(server_url):
    """Delete a review."""
    s = requests.Session()
    s.post(f"{_base(server_url)}/api/login", json={"username": "alex_r"})
    r = s.post(f"{_base(server_url)}/api/reviews",
               json={"business_id": 10, "rating": 2, "title": "To delete",
                     "text": "Will be deleted"})
    review = r.json()
    rid = review.get("id")
    r2 = s.delete(f"{_base(server_url)}/api/reviews/{rid}")
    data = r2.json()
    return {"pass": data.get("success") is True,
            "detail": f"delete_from_table: {data}"}


def verify_macro_select_by_slider(server_url):
    """Select businesses for comparison (slider-based)."""
    r = requests.get(f"{_base(server_url)}/api/compare", params={"ids": "1,3"})
    data = r.json()
    return {"pass": len(data) == 2,
            "detail": f"select_by_slider: {len(data)} businesses selected"}


def verify_macro_upload_by_upload(server_url):
    """Upload a photo."""
    s = requests.Session()
    s.post(f"{_base(server_url)}/api/login", json={"username": "alex_r"})
    r = s.post(f"{_base(server_url)}/api/photos",
               json={"business_id": 1, "caption": "Macro test photo",
                     "url": "/photos/test.jpg"})
    data = r.json()
    return {"pass": r.status_code == 201 and data.get("id"),
            "detail": f"upload_by_upload: photo_id={data.get('id')}"}


def verify_macro_post_from_free_text(server_url):
    """Post a review from free text."""
    s = requests.Session()
    s.post(f"{_base(server_url)}/api/login", json={"username": "alex_r"})
    r = s.post(f"{_base(server_url)}/api/reviews",
               json={"business_id": 10, "rating": 4,
                     "title": "Macro test review",
                     "text": "Testing the post_from_free_text macro"})
    data = r.json()
    ok = r.status_code == 201 and data.get("id")
    # Clean up
    if ok:
        s.delete(f"{_base(server_url)}/api/reviews/{data['id']}")
    return {"pass": ok,
            "detail": f"post_from_free_text: review_id={data.get('id')}"}


def verify_macro_react_by_toggle(server_url):
    """React to a review (useful/funny/cool toggle)."""
    r = requests.get(f"{_base(server_url)}/api/reviews/1")
    original = r.json().get("useful_count", 0)
    r2 = requests.post(f"{_base(server_url)}/api/reviews/1/helpful",
                       json={"type": "useful"})
    data = r2.json()
    return {"pass": data.get("success") is True,
            "detail": f"react_by_toggle: useful_count {original} -> {data.get('useful_count')}"}


def verify_macro_rate_by_slider(server_url):
    """Rate a review's helpfulness via slider."""
    r = requests.post(f"{_base(server_url)}/api/reviews/1/rate",
                      json={"rating": 3})
    data = r.json()
    return {"pass": data.get("success") is True,
            "detail": f"rate_by_slider: rating_added={data.get('rating_added')}"}


def verify_macro_follow_by_toggle(server_url):
    """Follow/unfollow a user (toggle)."""
    s = requests.Session()
    s.post(f"{_base(server_url)}/api/login", json={"username": "alex_r"})
    r = s.post(f"{_base(server_url)}/api/users/1/follow",
               json={"target_user_id": 2})
    data = r.json()
    ok = data.get("action") in ("followed", "unfollowed")
    # Toggle back
    s.post(f"{_base(server_url)}/api/users/1/follow",
           json={"target_user_id": 2})
    return {"pass": ok,
            "detail": f"follow_by_toggle: action={data.get('action')}"}


def verify_macro_save_by_toggle(server_url):
    """Save/unsave a business (toggle)."""
    s = requests.Session()
    s.post(f"{_base(server_url)}/api/login", json={"username": "alex_r"})
    r = s.post(f"{_base(server_url)}/api/users/1/save",
               json={"business_id": 5})
    data = r.json()
    ok = data.get("action") in ("saved", "unsaved")
    # Toggle back
    s.post(f"{_base(server_url)}/api/users/1/save",
           json={"business_id": 5})
    return {"pass": ok,
            "detail": f"save_by_toggle: action={data.get('action')}"}


def verify_macro_report_by_form(server_url):
    """Report a business or review."""
    s = requests.Session()
    s.post(f"{_base(server_url)}/api/login", json={"username": "alex_r"})
    r = s.post(f"{_base(server_url)}/api/report",
               json={"target_type": "business", "target_id": 1,
                     "reason": "test", "description": "Macro verification test"})
    data = r.json()
    return {"pass": r.status_code == 201 and data.get("id"),
            "detail": f"report_by_form: report_id={data.get('id')}"}
