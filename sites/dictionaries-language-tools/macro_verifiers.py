"""Per-macro verification functions for dictionaries-language-tools.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/dictionaries-language-tools"


def verify_macro_extract_word_of_the_day(server_url):
    r = requests.get(f"{_base(server_url)}/api/word-of-the-day")
    data = r.json()
    ok = "word" in data and len(data["word"]) > 0
    return {"pass": ok, "detail": f"word_of_the_day: {data.get('word', '')}"}


def verify_macro_search_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/words?q=coal")
    results = r.json()
    return {"pass": len(results) > 0,
            "detail": f"search_by_query 'coal': {len(results)} results"}


def verify_macro_browse_by_letter(server_url):
    r = requests.get(f"{_base(server_url)}/api/browse/A")
    words = r.json()
    ok = len(words) > 0
    return {"pass": ok, "detail": f"browse_by_letter A: {len(words)} words"}


def verify_macro_extract_from_stats(server_url):
    r = requests.get(f"{_base(server_url)}/api/stats")
    stats = r.json()
    ok = "total_words" in stats and "words_with_pronunciation" in stats
    return {"pass": ok,
            "detail": f"extract_from_stats: total={stats.get('total_words')}, pron={stats.get('words_with_pronunciation')}"}


def verify_macro_extract_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/words/domestically")
    data = r.json()
    if isinstance(data, list):
        data = data[0]
    ok = "word" in data and "pos" in data and "definitions" in data
    return {"pass": ok,
            "detail": f"extract_by_route: word={data.get('word')}, pos={data.get('pos')}"}


def verify_macro_compute_from_stats(server_url):
    r = requests.get(f"{_base(server_url)}/api/stats")
    stats = r.json()
    ok = "pos_distribution" in stats and "letter_distribution" in stats
    return {"pass": ok,
            "detail": f"compute_from_stats: {len(stats.get('pos_distribution', {}))} POS types, {len(stats.get('letter_distribution', {}))} letters"}


def verify_macro_filter_by_pos(server_url):
    r = requests.get(f"{_base(server_url)}/api/words?pos=noun")
    results = r.json()
    return {"pass": len(results) > 0,
            "detail": f"filter_by_pos noun: {len(results)} results"}


def verify_macro_compute_from_api(server_url):
    r = requests.get(f"{_base(server_url)}/api/words")
    words = r.json()
    both = [w for w in words if w.get("has_pronunciation") and w.get("has_etymology")]
    return {"pass": len(words) > 0,
            "detail": f"compute_from_api: {len(both)} words with both pron+etym out of {len(words)} total"}


def verify_macro_authenticate_by_form(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/login",
                      json={"username": "wordlover_anna", "password": "pass123"})
    data = r.json()
    ok = data.get("user_id") == 1
    return {"pass": ok, "detail": f"authenticate: user_id={data.get('user_id')}"}


def verify_macro_save_word(server_url):
    base = _base(server_url)
    # Use a test word save on a test user
    r = requests.post(f"{base}/api/users/5/save", json={"word": "__test_macro_word__"})
    data = r.json()
    ok = data.get("action") == "saved"
    # Clean up: toggle back
    requests.post(f"{base}/api/users/5/save", json={"word": "__test_macro_word__"})
    return {"pass": ok, "detail": f"save_word: action={data.get('action')}"}


def verify_macro_add_to_vocab_list(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/users/5/vocab",
                      json={"word": "__test_macro_word__", "list_name": "Test List"})
    data = r.json()
    ok = data.get("action") == "added"
    # Clean up: toggle back
    requests.post(f"{base}/api/users/5/vocab",
                  json={"word": "__test_macro_word__", "list_name": "Test List"})
    return {"pass": ok, "detail": f"add_to_vocab_list: action={data.get('action')}"}
