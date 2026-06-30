"""Per-macro verification functions for handwritten-notes-whiteboards.

Each function tests that the corresponding macro works end-to-end.
"""
import io
import requests


def _base(server_url):
    return f"{server_url}/sites/handwritten-notes-whiteboards"


def verify_macro_navigate_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/note/1")
    return {"pass": r.status_code == 200, "detail": f"Note detail page: {r.status_code}"}


def verify_macro_navigate_by_pan_zoom(server_url):
    r = requests.get(f"{_base(server_url)}/api/whiteboards/1/view?zoom=1.5&pan_x=50&pan_y=25")
    data = r.json()
    view = data.get("view", {})
    ok = view.get("zoom") == 1.5 and view.get("pan_x") == 50 and view.get("pan_y") == 25
    return {"pass": ok, "detail": f"pan_zoom view: {view}"}


def verify_macro_search_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/notes?q=meeting")
    results = r.json()
    return {"pass": len(results) > 0, "detail": f"search_by_query 'meeting': {len(results)} results"}


def verify_macro_search_by_semantic(server_url):
    r = requests.get(f"{_base(server_url)}/api/notes/semantic?q=productivity+workflow")
    results = r.json()
    return {"pass": r.status_code == 200, "detail": f"search_by_semantic: {len(results)} results"}


def verify_macro_search_by_image(server_url):
    img_data = io.BytesIO(b'\x89PNG\r\n\x1a\n' + b'\x00' * 50)
    r = requests.post(f"{_base(server_url)}/api/notes/search_by_image",
                       files={"image": ("test.png", img_data, "image/png")})
    ok = r.status_code == 200 and "matches" in r.json()
    return {"pass": ok, "detail": f"search_by_image: status={r.status_code}"}


def verify_macro_create_from_free_text(server_url):
    r = requests.post(f"{_base(server_url)}/api/notes",
                       json={"title": "__macro_test_free_text",
                             "content": "Test content",
                             "owner_id": 1})
    data = r.json()
    ok = data.get("title") == "__macro_test_free_text"
    # Cleanup
    if ok:
        requests.delete(f"{_base(server_url)}/api/notes/{data['id']}")
    return {"pass": ok, "detail": f"create_from_free_text: title={data.get('title')}"}


def verify_macro_create_by_radio(server_url):
    r = requests.post(f"{_base(server_url)}/api/notes/create_by_radio",
                       json={"note_type": "sketch",
                             "title": "__macro_test_radio",
                             "owner_id": 1})
    data = r.json()
    ok = data.get("note_type") == "sketch"
    # Cleanup
    if ok:
        requests.delete(f"{_base(server_url)}/api/notes/{data['id']}")
    return {"pass": ok, "detail": f"create_by_radio: note_type={data.get('note_type')}"}


def verify_macro_create_by_toggle(server_url):
    r = requests.post(f"{_base(server_url)}/api/create_by_toggle",
                       json={"mode": "whiteboard",
                             "title": "__macro_test_toggle",
                             "owner_id": 1})
    data = r.json()
    ok = data.get("created") == "whiteboard"
    # Cleanup
    if ok:
        item = data.get("item", {})
        requests.delete(f"{_base(server_url)}/api/whiteboards/{item.get('id')}")
    return {"pass": ok, "detail": f"create_by_toggle: created={data.get('created')}"}


def verify_macro_create_by_drag(server_url):
    r = requests.post(f"{_base(server_url)}/api/whiteboards/1/elements",
                       json={"type": "sticky",
                             "content": "__macro_test_drag",
                             "x": 999, "y": 999})
    data = r.json()
    ok = data.get("element", {}).get("content") == "__macro_test_drag"
    return {"pass": ok, "detail": f"create_by_drag: element={data.get('element')}"}


def verify_macro_create_by_image(server_url):
    img_data = io.BytesIO(b'\xff\xd8\xff\xe0' + b'\x00' * 50)
    r = requests.post(f"{_base(server_url)}/api/notes/create_by_image",
                       files={"image": ("macro_test.jpg", img_data, "image/jpeg")},
                       data={"owner_id": "1"})
    data = r.json()
    ok = data.get("image_filename") == "macro_test.jpg"
    # Cleanup
    if ok:
        requests.delete(f"{_base(server_url)}/api/notes/{data['id']}")
    return {"pass": ok, "detail": f"create_by_image: filename={data.get('image_filename')}"}


def verify_macro_submit_by_query(server_url):
    r = requests.post(f"{_base(server_url)}/api/notes/submit_query",
                       json={"query": "checklist"})
    data = r.json()
    ok = "result_count" in data and data.get("query") == "checklist"
    return {"pass": ok, "detail": f"submit_by_query: count={data.get('result_count')}"}


def verify_macro_edit_by_form(server_url):
    # Read original title, modify, then restore
    r = requests.get(f"{_base(server_url)}/api/notes/1")
    original_title = r.json().get("title", "")
    r = requests.put(f"{_base(server_url)}/api/notes/1",
                      json={"title": "__macro_test_edit"})
    data = r.json()
    ok = data.get("title") == "__macro_test_edit"
    # Restore
    requests.put(f"{_base(server_url)}/api/notes/1",
                  json={"title": original_title})
    return {"pass": ok, "detail": f"edit_by_form: title changed to {data.get('title')}"}


def verify_macro_edit_by_ranking(server_url):
    r = requests.put(f"{_base(server_url)}/api/notes/reorder",
                      json={"note_ids": [2, 1]})
    data = r.json()
    ok = isinstance(data, list) and len(data) == 2
    if ok:
        ok = data[0].get("rank") == 0 and data[1].get("rank") == 1
    return {"pass": ok, "detail": f"edit_by_ranking: {len(data)} notes reordered"}


def verify_macro_edit_by_drag(server_url):
    # Save original position
    r = requests.get(f"{_base(server_url)}/api/whiteboards/2")
    wb = r.json()
    orig_x = wb["elements"][0].get("x")
    orig_y = wb["elements"][0].get("y")
    # Move
    r = requests.put(f"{_base(server_url)}/api/whiteboards/2/elements/0/move",
                      json={"x": 500, "y": 500})
    data = r.json()
    elem = data.get("element", {})
    ok = elem.get("x") == 500 and elem.get("y") == 500
    # Restore
    requests.put(f"{_base(server_url)}/api/whiteboards/2/elements/0/move",
                  json={"x": orig_x, "y": orig_y})
    return {"pass": ok, "detail": f"edit_by_drag: moved to ({elem.get('x')}, {elem.get('y')})"}


def verify_macro_edit_by_image(server_url):
    img_data = io.BytesIO(b'\x89PNG\r\n\x1a\n' + b'\x00' * 50)
    r = requests.put(f"{_base(server_url)}/api/notes/1/replace_image",
                      files={"image": ("macro_test_replace.png", img_data, "image/png")})
    data = r.json()
    ok = data.get("image_filename") == "macro_test_replace.png"
    return {"pass": ok, "detail": f"edit_by_image: filename={data.get('image_filename')}"}


def verify_macro_delete_from_table(server_url):
    # Create a temp note then delete it
    r = requests.post(f"{_base(server_url)}/api/notes",
                       json={"title": "__macro_test_delete",
                             "content": "temp",
                             "owner_id": 1})
    new_id = r.json().get("id")
    r = requests.delete(f"{_base(server_url)}/api/notes/{new_id}")
    data = r.json()
    ok = data.get("deleted") == new_id
    # Verify gone
    r2 = requests.get(f"{_base(server_url)}/api/notes/{new_id}")
    ok = ok and r2.status_code == 404
    return {"pass": ok, "detail": f"delete_from_table: deleted={new_id}, gone={r2.status_code == 404}"}


def verify_macro_upload_by_upload(server_url):
    file_data = io.BytesIO(b"test file content")
    r = requests.post(f"{_base(server_url)}/api/upload",
                       files={"file": ("macro_test.txt", file_data, "text/plain")})
    data = r.json()
    ok = data.get("filename") == "macro_test.txt"
    return {"pass": ok, "detail": f"upload_by_upload: filename={data.get('filename')}"}


def verify_macro_save_by_toggle(server_url):
    # Get current pin state of note 2
    r = requests.get(f"{_base(server_url)}/api/notes/2")
    was_pinned = r.json().get("is_pinned", False)
    # Toggle
    r = requests.post(f"{_base(server_url)}/api/notes/2/pin")
    data = r.json()
    expected = not was_pinned
    ok = data.get("is_pinned") == expected
    # Toggle back to restore
    requests.post(f"{_base(server_url)}/api/notes/2/pin")
    return {"pass": ok, "detail": f"save_by_toggle: is_pinned toggled to {data.get('is_pinned')}"}


def verify_macro_export_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/export?format=csv")
    lines = r.text.strip().split("\n")
    ok = len(lines) > 1
    return {"pass": ok, "detail": f"export CSV: {len(lines)} lines"}


def verify_macro_share_by_dropdown(server_url):
    # Share whiteboard 1 with user 4 (may already be shared)
    r = requests.post(f"{_base(server_url)}/api/whiteboards/1/share",
                       json={"user_id": 4})
    data = r.json()
    ok = data.get("action") in ("shared", "already_shared")
    return {"pass": ok, "detail": f"share_by_dropdown: action={data.get('action')}"}


def verify_macro_invite_by_form(server_url):
    r = requests.post(f"{_base(server_url)}/api/whiteboards/1/invite",
                       json={"email": "taylor@example.com",
                             "message": "Join the board"})
    data = r.json()
    ok = data.get("status") == "invited" and data.get("invited_email") == "taylor@example.com"
    return {"pass": ok, "detail": f"invite_by_form: status={data.get('status')}, email={data.get('invited_email')}"}


def verify_macro_translate_by_image(server_url):
    img_data = io.BytesIO(b'\x89PNG\r\n\x1a\n' + b'\x00' * 50)
    r = requests.post(f"{_base(server_url)}/api/notes/translate_by_image",
                       files={"image": ("handwriting.png", img_data, "image/png")},
                       data={"target_lang": "es"})
    data = r.json()
    ok = data.get("target_language") == "es" and data.get("status") == "placeholder"
    return {"pass": ok, "detail": f"translate_by_image: lang={data.get('target_language')}, status={data.get('status')}"}
