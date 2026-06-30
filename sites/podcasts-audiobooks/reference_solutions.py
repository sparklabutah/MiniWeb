"""Per-task reference solutions via Flask test client for podcasts-audiobooks."""
import json


def solve_001(client, base="/sites/podcasts-audiobooks"):
    r = client.get(f"{base}/api/podcasts?category=Technology")
    return str(len(json.loads(r.data)))


def solve_002(client, base="/sites/podcasts-audiobooks"):
    r = client.get(f"{base}/api/podcasts/1")
    return json.loads(r.data)["host"]


def solve_003(client, base="/sites/podcasts-audiobooks"):
    r = client.get(f"{base}/api/search?q=crime")
    return str(len(json.loads(r.data)["podcasts"]))


def solve_004(client, base="/sites/podcasts-audiobooks"):
    r = client.get(f"{base}/api/search/semantic?q=technology+artificial+intelligence&type=podcasts")
    return str(len(json.loads(r.data)["podcasts"]))


def solve_005(client, base="/sites/podcasts-audiobooks"):
    r = client.get(f"{base}/api/audiobooks?genre=Fiction")
    return str(len(json.loads(r.data)))


def solve_006(client, base="/sites/podcasts-audiobooks"):
    r = client.get(f"{base}/api/audiobooks?min_rating=4.7")
    return str(len(json.loads(r.data)))


def solve_007(client, base="/sites/podcasts-audiobooks"):
    r = client.get(f"{base}/api/audiobooks?sort=title")
    audiobooks = json.loads(r.data)
    return audiobooks[0]["title"] if audiobooks else ""


def solve_008(client, base="/sites/podcasts-audiobooks"):
    r = client.get(f"{base}/api/search?q=history")
    results = json.loads(r.data)
    podcasts = results.get("podcasts", [])
    return podcasts[0]["title"] if podcasts else "No results"


def solve_009(client, base="/sites/podcasts-audiobooks"):
    r = client.get(f"{base}/api/podcasts?category=Science")
    podcasts = json.loads(r.data)
    return podcasts[0]["title"] if podcasts else ""


def solve_010(client, base="/sites/podcasts-audiobooks"):
    r = client.get(f"{base}/api/audiobooks?genre=Science+Fiction")
    return str(len(json.loads(r.data)))


def solve_011(client, base="/sites/podcasts-audiobooks"):
    r = client.get(f"{base}/api/episodes?podcast_id=3&sort=date&limit=1")
    episodes = json.loads(r.data)
    return episodes[0]["title"] if episodes else ""


def solve_012(client, base="/sites/podcasts-audiobooks"):
    r = client.get(f"{base}/api/episodes?date_from=2025-01-01&date_to=2025-06-30")
    return str(len(json.loads(r.data)))


def solve_013(client, base="/sites/podcasts-audiobooks"):
    client.post(f"{base}/api/login",
                json={"username": "listener_alice", "password": "pass123"})
    r = client.post(f"{base}/api/playback/speed", json={"speed": 1.5})
    return str(json.loads(r.data).get("speed", ""))


def solve_014(client, base="/sites/podcasts-audiobooks"):
    r = client.get(f"{base}/api/export?type=podcasts&format=csv")
    lines = r.data.decode().strip().split("\n")
    return str(len(lines) - 1)


def solve_015(client, base="/sites/podcasts-audiobooks"):
    client.post(f"{base}/api/login",
                json={"username": "bookworm_bob", "password": "pass456"})
    r = client.post(f"{base}/api/reviews",
                    json={"item_type": "podcast", "item_id": 1, "rating": 4,
                          "text": "Excellent daily coverage of current events."})
    data = json.loads(r.data)
    return str(data.get("id", ""))


def solve_016(client, base="/sites/podcasts-audiobooks"):
    client.post(f"{base}/api/login",
                json={"username": "podcast_carol", "password": "pass789"})
    r = client.post(f"{base}/api/episodes/1/like")
    return json.loads(r.data).get("action", "")


def solve_017(client, base="/sites/podcasts-audiobooks"):
    client.post(f"{base}/api/login",
                json={"username": "audio_dave", "password": "pass321"})
    r = client.post(f"{base}/api/reviews",
                    json={"item_type": "audiobook", "item_id": 5, "rating": 3.5,
                          "text": "Interesting but could be shorter."})
    data = json.loads(r.data)
    return str(data.get("rating", ""))


def solve_018(client, base="/sites/podcasts-audiobooks"):
    client.post(f"{base}/api/login",
                json={"username": "story_eve", "password": "pass654"})
    r = client.post(f"{base}/api/follow/host",
                    json={"host": "Sarah Mitchell"})
    return json.loads(r.data).get("action", "")


def solve_019(client, base="/sites/podcasts-audiobooks"):
    client.post(f"{base}/api/login",
                json={"username": "listener_alice", "password": "pass123"})
    r = client.post(f"{base}/api/podcasts/10/follow")
    return json.loads(r.data).get("action", "")


def solve_020(client, base="/sites/podcasts-audiobooks"):
    client.post(f"{base}/api/login",
                json={"username": "bookworm_bob", "password": "pass456"})
    client.post(f"{base}/api/podcasts/4/subscribe")
    client.post(f"{base}/api/episodes/20/save")
    r = client.get(f"{base}/api/library")
    lib = json.loads(r.data)
    subscribed = lib.get("subscribed_podcasts", [])
    saved = lib.get("saved_episodes", [])
    return f"subscribed={4 in subscribed}, saved={20 in saved}"
