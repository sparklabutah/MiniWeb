"""Per-task reference solutions via Flask test client for dictionaries-language-tools."""
import json


def solve_001(client, base="/sites/dictionaries-language-tools"):
    r = client.get(f"{base}/api/word-of-the-day")
    data = json.loads(r.data)
    return data["word"]


def solve_002(client, base="/sites/dictionaries-language-tools"):
    r = client.get(f"{base}/api/words/wayward")
    data = json.loads(r.data)
    if isinstance(data, list):
        total = sum(e["num_definitions"] for e in data)
    else:
        total = data["num_definitions"]
    return str(total)


def solve_003(client, base="/sites/dictionaries-language-tools"):
    r = client.get(f"{base}/api/browse/S")
    words = json.loads(r.data)
    return str(len(words))


def solve_004(client, base="/sites/dictionaries-language-tools"):
    r = client.get(f"{base}/api/stats")
    stats = json.loads(r.data)
    return str(stats["total_words"])


def solve_005(client, base="/sites/dictionaries-language-tools"):
    r = client.get(f"{base}/api/words/domestically")
    data = json.loads(r.data)
    if isinstance(data, list):
        return data[0]["pos"]
    return data["pos"]


def solve_006(client, base="/sites/dictionaries-language-tools"):
    r = client.get(f"{base}/api/stats")
    stats = json.loads(r.data)
    return str(stats["words_with_pronunciation"])


def solve_007(client, base="/sites/dictionaries-language-tools"):
    r = client.get(f"{base}/api/stats")
    stats = json.loads(r.data)
    pos_dist = stats["pos_distribution"]
    top_pos = max(pos_dist, key=pos_dist.get)
    return top_pos


def solve_008(client, base="/sites/dictionaries-language-tools"):
    r = client.get(f"{base}/api/words?q=coal")
    results = json.loads(r.data)
    return str(len(results))


def solve_009(client, base="/sites/dictionaries-language-tools"):
    r = client.get(f"{base}/api/browse/Q")
    words = json.loads(r.data)
    if words:
        return words[0]["word"]
    return ""


def solve_010(client, base="/sites/dictionaries-language-tools"):
    r = client.get(f"{base}/api/stats")
    stats = json.loads(r.data)
    return str(stats["words_with_etymology"])


def solve_011(client, base="/sites/dictionaries-language-tools"):
    r = client.get(f"{base}/api/words/wayward/synonyms")
    data = json.loads(r.data)
    return str(len(data["synonyms"]))


def solve_012(client, base="/sites/dictionaries-language-tools"):
    r = client.get(f"{base}/api/words?pos=verb")
    results = json.loads(r.data)
    return str(len(results))


def solve_013(client, base="/sites/dictionaries-language-tools"):
    r = client.get(f"{base}/api/stats")
    stats = json.loads(r.data)
    return str(stats["avg_definitions_per_word"])


def solve_014(client, base="/sites/dictionaries-language-tools"):
    r = client.get(f"{base}/api/browse/X")
    words = json.loads(r.data)
    return str(len(words))


def solve_015(client, base="/sites/dictionaries-language-tools"):
    r = client.get(f"{base}/api/users/1")
    user = json.loads(r.data)
    return str(len(user["saved_words"]))


def solve_016(client, base="/sites/dictionaries-language-tools"):
    client.post(f"{base}/api/login",
                json={"username": "wordlover_anna", "password": "pass123"})
    r = client.post(f"{base}/api/users/1/save", json={"word": "gorgonian"})
    data = json.loads(r.data)
    return data.get("action", "")


def solve_017(client, base="/sites/dictionaries-language-tools"):
    client.post(f"{base}/api/login",
                json={"username": "linguist_brian", "password": "pass456"})
    r = client.post(f"{base}/api/users/2/vocab",
                    json={"word": "wayward", "list_name": "Neologisms"})
    data = json.loads(r.data)
    return data.get("action", "")


def solve_018(client, base="/sites/dictionaries-language-tools"):
    client.post(f"{base}/api/login",
                json={"username": "student_carla", "password": "pass789"})
    client.post(f"{base}/api/users/3/save", json={"word": "domestically"})
    client.post(f"{base}/api/users/3/save", json={"word": "Eurodollar"})
    r = client.get(f"{base}/api/users/3")
    user = json.loads(r.data)
    return str(len(user["saved_words"]))


def solve_019(client, base="/sites/dictionaries-language-tools"):
    r = client.get(f"{base}/api/stats")
    stats = json.loads(r.data)
    letter_dist = stats["letter_distribution"]
    top_letter = max(letter_dist, key=letter_dist.get)
    return top_letter


def solve_020(client, base="/sites/dictionaries-language-tools"):
    r = client.get(f"{base}/api/words")
    words = json.loads(r.data)
    both = [w for w in words if w.get("has_pronunciation") and w.get("has_etymology")]
    return str(len(both))
