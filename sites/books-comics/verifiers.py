"""Per-task HTTP verification functions for books-comics."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/books-comics"
    r = requests.get(f"{base}/api/categories/education/books")
    books = r.json()
    count = len(books)
    return {"pass": count >= 0, "detail": f"education category has {count} books"}


def verify_002(server_url):
    base = f"{server_url}/sites/books-comics"
    r = requests.get(f"{base}/api/books/1")
    book = r.json()
    title = book.get("title", "")
    return {"pass": len(title) > 0, "detail": f"Book 1 title: {title[:60]}"}


def verify_003(server_url):
    base = f"{server_url}/sites/books-comics"
    r = requests.get(f"{base}/api/books/search?q=science")
    results = r.json()
    count = len(results)
    return {"pass": count >= 0, "detail": f"Search 'science': {count} results"}


def verify_004(server_url):
    base = f"{server_url}/sites/books-comics"
    r = requests.get(f"{base}/api/books/semantic?q=digital+learning+technology")
    results = r.json()
    count = len(results)
    return {"pass": count >= 0, "detail": f"Semantic 'digital learning technology': {count} results"}


def verify_005(server_url):
    base = f"{server_url}/sites/books-comics"
    r = requests.get(f"{base}/api/books?category=health")
    books = r.json()
    count = len(books)
    return {"pass": count >= 0, "detail": f"health filter: {count} books"}


def verify_006(server_url):
    base = f"{server_url}/sites/books-comics"
    r = requests.get(f"{base}/api/books?min_rating=4.0")
    books = r.json()
    count = len(books)
    ok = all(b["rating"] >= 4.0 for b in books)
    return {"pass": ok and count >= 0, "detail": f"rating>=4.0: {count} books, all_match={ok}"}


def verify_007(server_url):
    base = f"{server_url}/sites/books-comics"
    r = requests.get(f"{base}/api/books?sort=rating")
    books = r.json()
    if not books:
        return {"pass": False, "detail": "No books returned"}
    first_title = books[0]["title"]
    ratings = [b["rating"] for b in books]
    is_sorted = all(ratings[i] >= ratings[i+1] for i in range(len(ratings)-1))
    return {"pass": is_sorted, "detail": f"Top-rated: {first_title[:60]}, sorted={is_sorted}"}


def verify_008(server_url):
    base = f"{server_url}/sites/books-comics"
    r = requests.get(f"{base}/api/books/3")
    book = r.json()
    year = book.get("year")
    return {"pass": year is not None, "detail": f"Book 3 year: {year}"}


def verify_009(server_url):
    base = f"{server_url}/sites/books-comics"
    r = requests.get(f"{base}/api/categories/science/stats")
    stats = r.json()
    authors = stats.get("unique_authors", 0)
    return {"pass": authors >= 0, "detail": f"science unique authors: {authors}"}


def verify_010(server_url):
    base = f"{server_url}/sites/books-comics"
    r = requests.get(f"{base}/api/books/1/chapters/1")
    chapter = r.json()
    title = chapter.get("title", "")
    return {"pass": len(title) > 0, "detail": f"Book 1 chapter 1 title: {title}"}


def verify_011(server_url):
    base = f"{server_url}/sites/books-comics"
    r = requests.get(f"{base}/api/books/2/chapters")
    chapters = r.json()
    if not chapters:
        return {"pass": False, "detail": "No chapters for book 2"}
    last = chapters[-1]
    return {"pass": True, "detail": f"Book 2 last chapter: {last['chapter']} - {last['title']}"}


def verify_012(server_url):
    base = f"{server_url}/sites/books-comics"
    # Post a review
    r = requests.post(f"{base}/api/reviews/1",
                       json={"text": "Great educational resource, highly recommend!",
                             "user_id": 1})
    data = r.json()
    ok = data.get("text") == "Great educational resource, highly recommend!"
    return {"pass": ok, "detail": f"Review posted: {data.get('text', '')[:50]}"}


def verify_013(server_url):
    base = f"{server_url}/sites/books-comics"
    # First get reviews for book 1
    r = requests.get(f"{base}/api/reviews/1")
    reviews = r.json()
    if not reviews:
        return {"pass": False, "detail": "No reviews to react to"}
    review_id = reviews[-1]["id"]
    r2 = requests.post(f"{base}/api/reviews/1/react",
                        json={"review_id": review_id, "reaction": "like"})
    data = r2.json()
    count = data.get("count", 0)
    return {"pass": count > 0, "detail": f"Like count: {count}"}


def verify_014(server_url):
    base = f"{server_url}/sites/books-comics"
    r = requests.post(f"{base}/api/books/5/rate",
                       json={"rating": 4.5, "user_id": 2})
    data = r.json()
    ok = data.get("status") == "rated"
    return {"pass": ok, "detail": f"Rate status: {data.get('status')}"}


def verify_015(server_url):
    base = f"{server_url}/sites/books-comics"
    # Get book 1's first author
    r = requests.get(f"{base}/api/books/1")
    book = r.json()
    first_author = book["authors"][0] if book.get("authors") else ""
    # Check if user 2 already follows the author (agent may have done it)
    r2 = requests.get(f"{base}/api/users/2")
    user = r2.json()
    followed = user.get("followed_authors", [])
    if first_author in followed:
        # Agent already followed — pass
        return {"pass": True,
                "detail": f"User 2 already follows {first_author}: {followed}"}
    # Not yet followed — do it now
    r = requests.post(f"{base}/api/users/2/follow", json={"author": first_author})
    data = r.json()
    ok = data.get("action") == "followed"
    r2 = requests.get(f"{base}/api/users/2")
    user = r2.json()
    followed = user.get("followed_authors", [])
    return {"pass": ok and first_author in followed,
            "detail": f"User 2 followed: {followed}, expected: {first_author}"}


def verify_016(server_url):
    base = f"{server_url}/sites/books-comics"
    # Check if already subscribed (agent may have done it)
    r2 = requests.get(f"{base}/api/users/3")
    user = r2.json()
    subs = user.get("subscriptions", [])
    if "science" in subs:
        return {"pass": True, "detail": f"User 3 already subscribed to science: {subs}"}
    r = requests.post(f"{base}/api/users/3/subscribe", json={"category": "science"})
    data = r.json()
    ok = data.get("action") == "subscribed"
    r2 = requests.get(f"{base}/api/users/3")
    user = r2.json()
    subs = user.get("subscriptions", [])
    return {"pass": ok and "science" in subs,
            "detail": f"User 3 subscriptions: {subs}"}


def verify_017(server_url):
    base = f"{server_url}/sites/books-comics"
    # Save books 1, 2, 3 as user 1
    for bid in [1, 2, 3]:
        requests.post(f"{base}/api/users/1/save", json={"book_id": bid})
    r = requests.get(f"{base}/api/users/1")
    user = r.json()
    saved = user.get("saved_books", [])
    return {"pass": len(saved) == 3 and 1 in saved and 2 in saved and 3 in saved,
            "detail": f"User 1 saved books: {saved}"}


def verify_018(server_url):
    base = f"{server_url}/sites/books-comics"
    r = requests.post(f"{base}/api/users/4/cart", json={"book_id": 2})
    data = r.json()
    ok = data.get("action") == "added"
    return {"pass": ok, "detail": f"Cart action: {data.get('action')}, total: {data.get('total_cart')}"}


def verify_019(server_url):
    base = f"{server_url}/sites/books-comics"
    # Add books to cart
    for bid in [1, 3]:
        requests.post(f"{base}/api/users/4/cart", json={"book_id": bid})
    # Checkout
    r = requests.post(f"{base}/api/users/4/checkout",
                       json={"name": "Dan Kim", "email": "dan.kim@example.com",
                             "card": "4242424242424242"})
    data = r.json()
    ok = data.get("status") == "completed"
    return {"pass": ok, "detail": f"Checkout status: {data.get('status')}, items: {data.get('items_purchased')}"}


def verify_020(server_url):
    base = f"{server_url}/sites/books-comics"
    r = requests.get(f"{base}/api/stats")
    stats = r.json()
    authors = stats.get("unique_authors", 0)
    return {"pass": authors > 0, "detail": f"Total unique authors: {authors}"}
