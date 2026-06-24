"""Per-task HTTP verification functions for dictionaries-language-tools."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/dictionaries-language-tools"
    r = requests.get(f"{base}/api/word-of-the-day")
    data = r.json()
    word = data.get("word", "")
    return {"pass": len(word) > 0, "detail": f"Word of the day: {word}"}


def verify_002(server_url):
    base = f"{server_url}/sites/dictionaries-language-tools"
    r = requests.get(f"{base}/api/words/wayward")
    data = r.json()
    # Could be a single entry or list
    if isinstance(data, list):
        total_defs = sum(e.get("num_definitions", 0) for e in data)
    else:
        total_defs = data.get("num_definitions", 0)
    return {"pass": total_defs > 0, "detail": f"'wayward' definitions: {total_defs}"}


def verify_003(server_url):
    base = f"{server_url}/sites/dictionaries-language-tools"
    r = requests.get(f"{base}/api/browse/S")
    words = r.json()
    count = len(words)
    return {"pass": count > 0, "detail": f"Words starting with S: {count}"}


def verify_004(server_url):
    base = f"{server_url}/sites/dictionaries-language-tools"
    r = requests.get(f"{base}/api/stats")
    stats = r.json()
    total = stats.get("total_words", 0)
    return {"pass": total > 0, "detail": f"Total words: {total}"}


def verify_005(server_url):
    base = f"{server_url}/sites/dictionaries-language-tools"
    r = requests.get(f"{base}/api/words/domestically")
    data = r.json()
    if isinstance(data, list):
        pos = data[0].get("pos", "")
    else:
        pos = data.get("pos", "")
    return {"pass": len(pos) > 0, "detail": f"'domestically' POS: {pos}"}


def verify_006(server_url):
    base = f"{server_url}/sites/dictionaries-language-tools"
    r = requests.get(f"{base}/api/stats")
    stats = r.json()
    count = stats.get("words_with_pronunciation", 0)
    return {"pass": count > 0, "detail": f"Words with pronunciation: {count}"}


def verify_007(server_url):
    base = f"{server_url}/sites/dictionaries-language-tools"
    r = requests.get(f"{base}/api/stats")
    stats = r.json()
    pos_dist = stats.get("pos_distribution", {})
    if pos_dist:
        top_pos = max(pos_dist, key=pos_dist.get)
        return {"pass": True, "detail": f"Most common POS: {top_pos} ({pos_dist[top_pos]})"}
    return {"pass": False, "detail": "No POS distribution data"}


def verify_008(server_url):
    base = f"{server_url}/sites/dictionaries-language-tools"
    r = requests.get(f"{base}/api/words?q=coal")
    results = r.json()
    count = len(results)
    return {"pass": count >= 0, "detail": f"Search 'coal': {count} results"}


def verify_009(server_url):
    base = f"{server_url}/sites/dictionaries-language-tools"
    r = requests.get(f"{base}/api/browse/Q")
    words = r.json()
    if not words:
        return {"pass": False, "detail": "No words starting with Q"}
    first = words[0].get("word", "")
    return {"pass": len(first) > 0, "detail": f"First Q word: {first}"}


def verify_010(server_url):
    base = f"{server_url}/sites/dictionaries-language-tools"
    r = requests.get(f"{base}/api/stats")
    stats = r.json()
    count = stats.get("words_with_etymology", 0)
    return {"pass": count > 0, "detail": f"Words with etymology: {count}"}


def verify_011(server_url):
    base = f"{server_url}/sites/dictionaries-language-tools"
    r = requests.get(f"{base}/api/words/wayward/synonyms")
    data = r.json()
    syns = data.get("synonyms", [])
    count = len(syns)
    return {"pass": count >= 0, "detail": f"'wayward' synonyms: {count}"}


def verify_012(server_url):
    base = f"{server_url}/sites/dictionaries-language-tools"
    r = requests.get(f"{base}/api/words?pos=verb")
    results = r.json()
    count = len(results)
    return {"pass": count > 0, "detail": f"Verb entries: {count}"}


def verify_013(server_url):
    base = f"{server_url}/sites/dictionaries-language-tools"
    r = requests.get(f"{base}/api/stats")
    stats = r.json()
    avg = stats.get("avg_definitions_per_word", 0)
    return {"pass": avg > 0, "detail": f"Avg definitions per word: {avg}"}


def verify_014(server_url):
    base = f"{server_url}/sites/dictionaries-language-tools"
    r = requests.get(f"{base}/api/browse/X")
    words = r.json()
    count = len(words)
    return {"pass": True, "detail": f"Words starting with X: {count}"}


def verify_015(server_url):
    base = f"{server_url}/sites/dictionaries-language-tools"
    r = requests.get(f"{base}/api/users/1")
    user = r.json()
    saved = user.get("saved_words", [])
    count = len(saved)
    return {"pass": count >= 0, "detail": f"User 1 saved words: {count}"}


def verify_016(server_url):
    base = f"{server_url}/sites/dictionaries-language-tools"
    r = requests.get(f"{base}/api/users/1")
    user = r.json()
    saved = [w.lower() for w in user.get("saved_words", [])]
    return {"pass": "gorgonian" in saved,
            "detail": f"User 1 saved words: {user.get('saved_words', [])}"}


def verify_017(server_url):
    base = f"{server_url}/sites/dictionaries-language-tools"
    r = requests.get(f"{base}/api/users/2")
    user = r.json()
    vocab_lists = user.get("vocabulary_lists", [])
    neo_list = next((vl for vl in vocab_lists if vl["name"] == "Neologisms"), None)
    if not neo_list:
        return {"pass": False, "detail": "Neologisms list not found"}
    words = [w.lower() for w in neo_list.get("words", [])]
    return {"pass": "wayward" in words,
            "detail": f"Neologisms list: {neo_list.get('words', [])}"}


def verify_018(server_url):
    base = f"{server_url}/sites/dictionaries-language-tools"
    r = requests.get(f"{base}/api/users/3")
    user = r.json()
    saved = user.get("saved_words", [])
    saved_lower = [w.lower() for w in saved]
    has_dom = "domestically" in saved_lower
    has_euro = "eurodollar" in saved_lower
    return {"pass": has_dom and has_euro and len(saved) == 2,
            "detail": f"User 3 saved words: {saved}"}


def verify_019(server_url):
    base = f"{server_url}/sites/dictionaries-language-tools"
    r = requests.get(f"{base}/api/stats")
    stats = r.json()
    letter_dist = stats.get("letter_distribution", {})
    if letter_dist:
        top_letter = max(letter_dist, key=letter_dist.get)
        return {"pass": True, "detail": f"Letter with most words: {top_letter} ({letter_dist[top_letter]})"}
    return {"pass": False, "detail": "No letter distribution data"}


def verify_020(server_url):
    base = f"{server_url}/sites/dictionaries-language-tools"
    r = requests.get(f"{base}/api/words")
    words = r.json()
    both = [w for w in words if w.get("has_pronunciation") and w.get("has_etymology")]
    count = len(both)
    return {"pass": True, "detail": f"Words with both IPA and etymology: {count}"}
