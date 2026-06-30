"""Per-macro verification functions for translation.

Each function tests that the corresponding macro works end-to-end.
"""
import io
import requests


def _base(server_url):
    return f"{server_url}/sites/translation"


def verify_macro_navigate_by_route(server_url):
    """Verify route-based navigation to key pages."""
    pages = ["/history", "/saved", "/glossaries", "/settings"]
    results = []
    for page in pages:
        r = requests.get(f"{_base(server_url)}{page}")
        results.append(r.status_code)
    all_ok = all(c == 200 for c in results)
    return {"pass": all_ok,
            "detail": f"Page status codes: {dict(zip(pages, results))}"}


def verify_macro_extract_by_query(server_url):
    """Verify text-query search across translation history."""
    r = requests.get(f"{_base(server_url)}/api/history?q=hello")
    results = r.json()
    return {"pass": len(results) > 0,
            "detail": f"extract_by_query 'hello': {len(results)} results"}


def verify_macro_extract_by_semantic(server_url):
    """Verify semantic/fuzzy search across translation history."""
    r = requests.get(f"{_base(server_url)}/api/history/semantic?q=greeting+morning")
    results = r.json()
    return {"pass": r.status_code == 200,
            "detail": f"extract_by_semantic 'greeting morning': {len(results)} results"}


def verify_macro_select_by_dropdown(server_url):
    """Verify language dropdown selection works for translation."""
    # Translate with specific source/target language selections
    r = requests.post(f"{_base(server_url)}/api/translate",
                      json={"text": "hello", "source": "en", "target": "de"})
    data = r.json()
    ok = data.get("target_lang") == "de" and "hallo" in data.get("translated_text", "").lower()
    return {"pass": ok,
            "detail": f"select_by_dropdown en->de: '{data.get('translated_text')}'"}


def verify_macro_configure_by_toggle(server_url):
    """Verify toggle settings work (auto_detect, formal_mode, auto_pronounce)."""
    # Get initial value
    r = requests.get(f"{_base(server_url)}/api/settings?user_id=4")
    initial = r.json().get("auto_detect", False)
    # Toggle
    r = requests.post(f"{_base(server_url)}/api/settings/toggle",
                      json={"user_id": 4, "setting": "auto_detect"})
    data = r.json()
    toggled = data.get("value")
    ok = toggled == (not initial)
    # Toggle back to restore state
    requests.post(f"{_base(server_url)}/api/settings/toggle",
                  json={"user_id": 4, "setting": "auto_detect"})
    return {"pass": ok,
            "detail": f"configure_by_toggle: auto_detect {initial} -> {toggled}"}


def verify_macro_play_by_playback(server_url):
    """Verify audio playback endpoint returns valid metadata."""
    r = requests.post(f"{_base(server_url)}/api/playback",
                      json={"text": "hello world", "lang": "en", "speed": 1.0})
    data = r.json()
    ok = (data.get("status") == "ready" and
          data.get("word_count") == 2 and
          data.get("estimated_duration_sec", 0) > 0)
    return {"pass": ok,
            "detail": f"play_by_playback: status={data.get('status')}, "
                      f"duration={data.get('estimated_duration_sec')}s"}


def verify_macro_export_by_dropdown(server_url):
    """Verify export in multiple formats (JSON, CSV, TXT)."""
    # CSV
    r_csv = requests.get(f"{_base(server_url)}/api/export?format=csv")
    csv_lines = r_csv.text.strip().split("\n")
    csv_ok = len(csv_lines) > 1

    # JSON
    r_json = requests.get(f"{_base(server_url)}/api/export?format=json")
    json_data = r_json.json()
    json_ok = len(json_data) > 0

    # TXT
    r_txt = requests.get(f"{_base(server_url)}/api/export?format=txt")
    txt_ok = len(r_txt.text.strip()) > 0

    all_ok = csv_ok and json_ok and txt_ok
    return {"pass": all_ok,
            "detail": f"export_by_dropdown: csv={len(csv_lines)-1} rows, "
                      f"json={len(json_data)} items, txt={'ok' if txt_ok else 'empty'}"}


def verify_macro_upload_by_upload(server_url):
    """Verify file upload for batch translation."""
    content = "Hello\nGoodbye"
    files = {"file": ("test.txt", io.BytesIO(content.encode()), "text/plain")}
    data = {"source": "en", "target": "es", "user_id": "4"}
    r = requests.post(f"{_base(server_url)}/api/upload", files=files, data=data)
    result = r.json()
    ok = result.get("lines_translated") == 2
    translations = result.get("translations", [])
    return {"pass": ok,
            "detail": f"upload_by_upload: {result.get('lines_translated')} lines, "
                      f"first='{translations[0]['translated'] if translations else 'N/A'}'"}


def verify_macro_submit_by_image(server_url):
    """Verify image submission for OCR translation (placeholder)."""
    # Create a minimal 1x1 PNG
    png_data = (b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
                b'\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00'
                b'\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00'
                b'\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82')
    files = {"image": ("test.png", io.BytesIO(png_data), "image/png")}
    data = {"source": "en", "target": "es"}
    r = requests.post(f"{_base(server_url)}/api/image-translate", files=files, data=data)
    result = r.json()
    ok = (r.status_code == 200 and
          len(result.get("ocr_text", "")) > 0 and
          len(result.get("translated_text", "")) > 0)
    return {"pass": ok,
            "detail": f"submit_by_image: ocr='{result.get('ocr_text')}', "
                      f"translated='{result.get('translated_text')}'"}


def verify_macro_translate_by_query(server_url):
    """Verify core translation functionality."""
    r = requests.post(f"{_base(server_url)}/api/translate",
                      json={"text": "good morning", "source": "en", "target": "es"})
    data = r.json()
    translated = data.get("translated_text", "")
    ok = r.status_code == 200 and len(translated) > 0
    return {"pass": ok,
            "detail": f"translate_by_query: 'good morning' -> es: '{translated}'"}
