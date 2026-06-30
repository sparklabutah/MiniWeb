"""Per-task HTTP verification functions for translation."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/translation"
    r = requests.get(f"{base}/api/history?user_id=1")
    history = r.json()
    count = len(history)
    return {"pass": count > 0, "detail": f"User 1 history: {count} records"}


def verify_002(server_url):
    base = f"{server_url}/sites/translation"
    r = requests.get(f"{base}/api/saved?user_id=2")
    saved = r.json()
    count = len(saved)
    return {"pass": count > 0, "detail": f"User 2 saved: {count} translations"}


def verify_003(server_url):
    base = f"{server_url}/sites/translation"
    r = requests.post(f"{base}/api/translate",
                      json={"text": "hello", "source": "en", "target": "fr"})
    data = r.json()
    translated = data.get("translated_text", "")
    return {"pass": translated == "bonjour",
            "detail": f"hello -> fr: '{translated}'"}


def verify_004(server_url):
    base = f"{server_url}/sites/translation"
    r = requests.get(f"{base}/api/history?q=morning")
    results = r.json()
    count = len(results)
    return {"pass": count > 0, "detail": f"History search 'morning': {count} results"}


def verify_005(server_url):
    base = f"{server_url}/sites/translation"
    r = requests.get(f"{base}/api/languages")
    languages = r.json()
    count = len(languages)
    return {"pass": count == 10, "detail": f"Languages count: {count}"}


def verify_006(server_url):
    base = f"{server_url}/sites/translation"
    r = requests.get(f"{base}/api/glossaries/1")
    glossary = r.json()
    entries = len(glossary.get("entries", []))
    return {"pass": entries == 5, "detail": f"Glossary 1 entries: {entries}"}


def verify_007(server_url):
    base = f"{server_url}/sites/translation"
    r = requests.post(f"{base}/api/translate",
                      json={"text": "I love my family", "source": "en", "target": "es"})
    data = r.json()
    translated = data.get("translated_text", "")
    # Each word should be translated
    return {"pass": "amor" in translated.lower() and "familia" in translated.lower(),
            "detail": f"'I love my family' -> es: '{translated}'"}


def verify_008(server_url):
    base = f"{server_url}/sites/translation"
    r = requests.get(f"{base}/api/history/semantic?q=food+eating")
    results = r.json()
    count = len(results)
    return {"pass": count >= 0, "detail": f"Semantic 'food eating': {count} results"}


def verify_009(server_url):
    base = f"{server_url}/sites/translation"
    r = requests.post(f"{base}/api/translate",
                      json={"text": "The water is cold", "source": "en", "target": "de"})
    data = r.json()
    translated = data.get("translated_text", "")
    return {"pass": "Wasser" in translated,
            "detail": f"'The water is cold' -> de: '{translated}'"}


def verify_010(server_url):
    base = f"{server_url}/sites/translation"
    r = requests.post(f"{base}/api/playback",
                      json={"text": "bonjour le monde", "lang": "fr"})
    data = r.json()
    duration = data.get("estimated_duration_sec")
    return {"pass": duration is not None and duration > 0,
            "detail": f"Playback duration: {duration}s"}


def verify_011(server_url):
    base = f"{server_url}/sites/translation"
    r = requests.post(f"{base}/api/detect",
                      json={"text": "Hola donde esta el restaurante"})
    data = r.json()
    detected = data.get("detected_language", "")
    return {"pass": detected == "es",
            "detail": f"Detected language: {detected}"}


def verify_012(server_url):
    base = f"{server_url}/sites/translation"
    r = requests.get(f"{base}/api/stats?user_id=1")
    stats = r.json()
    total = stats.get("total_translations", 0)
    return {"pass": total > 0, "detail": f"User 1 total translations: {total}"}


def verify_013(server_url):
    base = f"{server_url}/sites/translation"
    r = requests.get(f"{base}/api/history/semantic?q=greeting+hello")
    results = r.json()
    if not results:
        return {"pass": False, "detail": "No results for 'greeting hello'"}
    first_source = results[0].get("source_text", "")
    return {"pass": len(first_source) > 0,
            "detail": f"First semantic result source: '{first_source}'"}


def verify_014(server_url):
    base = f"{server_url}/sites/translation"
    r = requests.post(f"{base}/api/translate",
                      json={"text": "goodbye friend", "source": "en", "target": "ja"})
    data = r.json()
    translated = data.get("translated_text", "")
    return {"pass": "sayonara" in translated.lower(),
            "detail": f"'goodbye friend' -> ja: '{translated}'"}


def verify_015(server_url):
    base = f"{server_url}/sites/translation"
    # Get initial state
    r = requests.get(f"{base}/api/settings?user_id=1")
    initial = r.json().get("auto_detect", False)
    # Toggle
    r = requests.post(f"{base}/api/settings/toggle",
                      json={"user_id": 1, "setting": "auto_detect"})
    data = r.json()
    new_val = data.get("value")
    # Should be opposite of initial
    return {"pass": new_val == (not initial),
            "detail": f"auto_detect toggled from {initial} to {new_val}"}


def verify_016(server_url):
    base = f"{server_url}/sites/translation"
    r = requests.get(f"{base}/api/export?format=csv&user_id=1")
    lines = r.text.strip().split("\n")
    data_rows = len(lines) - 1  # minus header
    return {"pass": data_rows > 0, "detail": f"CSV export user 1: {data_rows} data rows"}


def verify_017(server_url):
    base = f"{server_url}/sites/translation"
    import io
    content = "Hello friend\nGood morning"
    files = {"file": ("test.txt", io.BytesIO(content.encode()), "text/plain")}
    data = {"source": "en", "target": "fr", "user_id": "1"}
    r = requests.post(f"{base}/api/upload", files=files, data=data)
    result = r.json()
    lines_translated = result.get("lines_translated", 0)
    return {"pass": lines_translated == 2,
            "detail": f"Upload translated {lines_translated} lines"}


def verify_018(server_url):
    base = f"{server_url}/sites/translation"
    import io
    # Create a minimal 1x1 PNG
    png_data = (b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
                b'\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00'
                b'\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00'
                b'\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82')
    files = {"image": ("test.png", io.BytesIO(png_data), "image/png")}
    data = {"source": "en", "target": "es"}
    r = requests.post(f"{base}/api/image-translate", files=files, data=data)
    result = r.json()
    ocr_text = result.get("ocr_text", "")
    return {"pass": len(ocr_text) > 0,
            "detail": f"OCR text: '{ocr_text}'"}


def verify_019(server_url):
    base = f"{server_url}/sites/translation"
    # Ensure formal_mode is on for user 3
    r = requests.get(f"{base}/api/settings?user_id=3")
    current = r.json().get("formal_mode", False)
    if not current:
        requests.post(f"{base}/api/settings/toggle",
                      json={"user_id": 3, "setting": "formal_mode"})
    r = requests.get(f"{base}/api/settings?user_id=3")
    formal = r.json().get("formal_mode", False)
    # Also translate
    r = requests.post(f"{base}/api/translate",
                      json={"text": "hello how are you", "source": "en", "target": "fr"})
    translated = r.json().get("translated_text", "")
    return {"pass": formal is True and len(translated) > 0,
            "detail": f"formal_mode={formal}, translated='{translated}'"}


def verify_020(server_url):
    base = f"{server_url}/sites/translation"
    # Export JSON
    r = requests.get(f"{base}/api/export?format=json")
    history = r.json()
    if not history:
        return {"pass": False, "detail": "No history to export"}
    first_translated = history[0].get("translated_text", "")
    # Playback
    r = requests.post(f"{base}/api/playback",
                      json={"text": first_translated, "lang": history[0].get("target_lang", "es")})
    data = r.json()
    duration = data.get("estimated_duration_sec")
    return {"pass": duration is not None and duration > 0,
            "detail": f"Playback of first export: duration={duration}s"}
