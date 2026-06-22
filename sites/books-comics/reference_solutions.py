"""Per-task reference solutions via Flask test client for books-comics."""
import json


def solve_001(client, base="/sites/books-comics"):
    r = client.get(f"{base}/api/categories/education/books")
    books = json.loads(r.data)
    return str(len(books))


def solve_002(client, base="/sites/books-comics"):
    r = client.get(f"{base}/api/books/1")
    book = json.loads(r.data)
    return book["title"]


def solve_003(client, base="/sites/books-comics"):
    r = client.get(f"{base}/api/books/search?q=science")
    return str(len(json.loads(r.data)))


def solve_004(client, base="/sites/books-comics"):
    r = client.get(f"{base}/api/books/semantic?q=digital+learning+technology")
    return str(len(json.loads(r.data)))


def solve_005(client, base="/sites/books-comics"):
    r = client.get(f"{base}/api/books?category=health")
    return str(len(json.loads(r.data)))


def solve_006(client, base="/sites/books-comics"):
    r = client.get(f"{base}/api/books?min_rating=4.0")
    return str(len(json.loads(r.data)))


def solve_007(client, base="/sites/books-comics"):
    r = client.get(f"{base}/api/books?sort=rating")
    books = json.loads(r.data)
    return books[0]["title"] if books else ""


def solve_008(client, base="/sites/books-comics"):
    r = client.get(f"{base}/api/books/3")
    return str(json.loads(r.data)["year"])


def solve_009(client, base="/sites/books-comics"):
    r = client.get(f"{base}/api/categories/science/stats")
    return str(json.loads(r.data).get("unique_authors", 0))


def solve_010(client, base="/sites/books-comics"):
    r = client.get(f"{base}/api/books/1/chapters/1")
    chapter = json.loads(r.data)
    return chapter.get("title", "")


def solve_011(client, base="/sites/books-comics"):
    r = client.get(f"{base}/api/books/2/chapters")
    chapters = json.loads(r.data)
    if not chapters:
        return "0"
    last = chapters[-1]
    # Update progress
    client.post(f"{base}/api/login",
                json={"username": "comic_fan_alice", "password": "pass123"},
                content_type="application/json")
    client.post(f"{base}/api/users/1/reading-progress",
                json={"book_id": 2, "chapter": last["chapter"], "progress": 100},
                content_type="application/json")
    return str(last["chapter"])


def solve_012(client, base="/sites/books-comics"):
    client.post(f"{base}/api/login",
                json={"username": "comic_fan_alice", "password": "pass123"},
                content_type="application/json")
    r = client.post(f"{base}/api/reviews/1",
                    json={"text": "Great educational resource, highly recommend!",
                          "user_id": 1},
                    content_type="application/json")
    data = json.loads(r.data)
    return "posted" if data.get("text") else "failed"


def solve_013(client, base="/sites/books-comics"):
    # Post review first
    r = client.post(f"{base}/api/reviews/1",
                    json={"text": "Another review", "user_id": 1},
                    content_type="application/json")
    review_id = json.loads(r.data).get("id")
    # React
    r2 = client.post(f"{base}/api/reviews/1/react",
                     json={"review_id": review_id, "reaction": "like"},
                     content_type="application/json")
    data = json.loads(r2.data)
    return str(data.get("count", 0))


def solve_014(client, base="/sites/books-comics"):
    client.post(f"{base}/api/login",
                json={"username": "bookworm_bob", "password": "pass456"},
                content_type="application/json")
    r = client.post(f"{base}/api/books/5/rate",
                    json={"rating": 4.5, "user_id": 2},
                    content_type="application/json")
    data = json.loads(r.data)
    return data.get("status", "")


def solve_015(client, base="/sites/books-comics"):
    client.post(f"{base}/api/login",
                json={"username": "bookworm_bob", "password": "pass456"},
                content_type="application/json")
    r = client.get(f"{base}/api/books/1")
    book = json.loads(r.data)
    author = book["authors"][0] if book.get("authors") else ""
    r = client.post(f"{base}/api/users/2/follow",
                    json={"author": author},
                    content_type="application/json")
    return json.loads(r.data).get("action", "")


def solve_016(client, base="/sites/books-comics"):
    client.post(f"{base}/api/login",
                json={"username": "reader_carol", "password": "pass789"},
                content_type="application/json")
    r = client.post(f"{base}/api/users/3/subscribe",
                    json={"category": "science"},
                    content_type="application/json")
    return json.loads(r.data).get("action", "")


def solve_017(client, base="/sites/books-comics"):
    client.post(f"{base}/api/login",
                json={"username": "comic_fan_alice", "password": "pass123"},
                content_type="application/json")
    for bid in [1, 2, 3]:
        client.post(f"{base}/api/users/1/save",
                    json={"book_id": bid},
                    content_type="application/json")
    r = client.get(f"{base}/api/users/1")
    user = json.loads(r.data)
    return str(len(user.get("saved_books", [])))


def solve_018(client, base="/sites/books-comics"):
    client.post(f"{base}/api/login",
                json={"username": "manga_dan", "password": "pass321"},
                content_type="application/json")
    r = client.post(f"{base}/api/users/4/cart",
                    json={"book_id": 2},
                    content_type="application/json")
    data = json.loads(r.data)
    return str(data.get("total_cart", 0))


def solve_019(client, base="/sites/books-comics"):
    client.post(f"{base}/api/login",
                json={"username": "manga_dan", "password": "pass321"},
                content_type="application/json")
    for bid in [1, 3]:
        client.post(f"{base}/api/users/4/cart",
                    json={"book_id": bid},
                    content_type="application/json")
    r = client.post(f"{base}/api/users/4/checkout",
                    json={"name": "Dan Kim", "email": "dan.kim@example.com",
                          "card": "4242424242424242"},
                    content_type="application/json")
    data = json.loads(r.data)
    return data.get("status", "")


def solve_020(client, base="/sites/books-comics"):
    r = client.get(f"{base}/api/stats")
    return str(json.loads(r.data)["unique_authors"])
