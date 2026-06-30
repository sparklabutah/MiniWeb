"""Per-task HTTP verification functions for handwritten-notes-whiteboards."""
import io
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/handwritten-notes-whiteboards"
    r = requests.get(f"{base}/api/notes/1")
    note = r.json()
    title = note.get("title", "")
    return {"pass": title == "Q3 Product Roadmap", "detail": f"Note 1 title: {title}"}


def verify_002(server_url):
    base = f"{server_url}/sites/handwritten-notes-whiteboards"
    r = requests.get(f"{base}/api/whiteboards/1/view?zoom=2.0&pan_x=100&pan_y=50")
    data = r.json()
    wb = data.get("whiteboard", {})
    view = data.get("view", {})
    title = wb.get("title", "")
    ok = (title == "Product Architecture Overview" and
          view.get("zoom") == 2.0 and
          view.get("pan_x") == 100 and
          view.get("pan_y") == 50)
    return {"pass": ok, "detail": f"Whiteboard 1 title: {title}, view: {view}"}


def verify_003(server_url):
    base = f"{server_url}/sites/handwritten-notes-whiteboards"
    r = requests.get(f"{base}/api/notes?q=sprint")
    results = r.json()
    count = len(results)
    return {"pass": count > 0, "detail": f"Search 'sprint': {count} notes"}


def verify_004(server_url):
    base = f"{server_url}/sites/handwritten-notes-whiteboards"
    r = requests.get(f"{base}/api/notes/semantic?q=software+deployment")
    results = r.json()
    count = len(results)
    return {"pass": count >= 0, "detail": f"Semantic 'software deployment': {count} results"}


def verify_005(server_url):
    base = f"{server_url}/sites/handwritten-notes-whiteboards"
    # Test search_by_image
    img_data = io.BytesIO(b'\x89PNG\r\n\x1a\n' + b'\x00' * 50)
    r1 = requests.post(f"{base}/api/notes/search_by_image",
                        files={"image": ("test.png", img_data, "image/png")})
    search_ok = r1.status_code == 200 and "matches" in r1.json()
    # Test translate_by_image
    img_data2 = io.BytesIO(b'\x89PNG\r\n\x1a\n' + b'\x00' * 50)
    r2 = requests.post(f"{base}/api/notes/translate_by_image",
                        files={"image": ("test.png", img_data2, "image/png")},
                        data={"target_lang": "es"})
    translate_ok = r2.status_code == 200 and r2.json().get("target_language") == "es"
    ok = search_ok and translate_ok
    return {"pass": ok, "detail": f"search_by_image: {search_ok}, translate_by_image(es): {translate_ok}"}


def verify_006(server_url):
    base = f"{server_url}/sites/handwritten-notes-whiteboards"
    # Check that a note titled 'Team Goals 2026' exists
    r = requests.get(f"{base}/api/notes?q=Team+Goals+2026")
    notes = r.json()
    found = any(n["title"] == "Team Goals 2026" for n in notes)
    return {"pass": found, "detail": f"Note 'Team Goals 2026' found: {found}"}


def verify_007(server_url):
    base = f"{server_url}/sites/handwritten-notes-whiteboards"
    r = requests.get(f"{base}/api/notes?q=Daily+Tasks")
    notes = r.json()
    match = [n for n in notes if n.get("title") == "Daily Tasks"]
    if match:
        note_type = match[0].get("note_type", "")
        return {"pass": note_type == "checklist", "detail": f"note_type: {note_type}"}
    return {"pass": False, "detail": "Note 'Daily Tasks' not found"}


def verify_008(server_url):
    base = f"{server_url}/sites/handwritten-notes-whiteboards"
    r = requests.get(f"{base}/api/whiteboards")
    wbs = r.json()
    found = any(w["title"] == "Design Sprint Board" for w in wbs)
    return {"pass": found, "detail": f"Whiteboard 'Design Sprint Board' found: {found}"}


def verify_009(server_url):
    base = f"{server_url}/sites/handwritten-notes-whiteboards"
    r = requests.get(f"{base}/api/whiteboards/3")
    wb = r.json()
    elements = wb.get("elements", [])
    # Check that an element with 'New feature request' exists at x=30, y=300
    found = any(e.get("content") == "New feature request" and
                e.get("x") == 30 and e.get("y") == 300
                for e in elements)
    return {"pass": found, "detail": f"Element 'New feature request' at (30,300): {found}, total elements: {len(elements)}"}


def verify_010(server_url):
    base = f"{server_url}/sites/handwritten-notes-whiteboards"
    r = requests.get(f"{base}/api/notes")
    notes = r.json()
    match = [n for n in notes if n.get("image_filename") == "whiteboard_photo.jpg"]
    ok = len(match) > 0
    detail = match[0].get("content", "") if match else "not found"
    return {"pass": ok, "detail": f"Image note content: {detail}"}


def verify_011(server_url):
    base = f"{server_url}/sites/handwritten-notes-whiteboards"
    r = requests.post(f"{base}/api/notes/submit_query",
                       json={"query": "recipe"})
    data = r.json()
    count = data.get("result_count", 0)
    return {"pass": count >= 0, "detail": f"submit_by_query 'recipe': {count} results"}


def verify_012(server_url):
    base = f"{server_url}/sites/handwritten-notes-whiteboards"
    r = requests.get(f"{base}/api/notes/5")
    note = r.json()
    title = note.get("title", "")
    return {"pass": title == "Transformer Architecture Notes",
            "detail": f"Note 5 title: {title}"}


def verify_013(server_url):
    base = f"{server_url}/sites/handwritten-notes-whiteboards"
    r = requests.get(f"{base}/api/notes/3")
    note = r.json()
    rank = note.get("rank")
    return {"pass": rank == 0, "detail": f"Note 3 rank: {rank}"}


def verify_014(server_url):
    base = f"{server_url}/sites/handwritten-notes-whiteboards"
    r = requests.get(f"{base}/api/whiteboards/1")
    wb = r.json()
    elements = wb.get("elements", [])
    if not elements:
        return {"pass": False, "detail": "No elements on whiteboard 1"}
    elem = elements[0]
    ok = elem.get("x") == 200 and elem.get("y") == 300
    return {"pass": ok, "detail": f"Element 0 position: ({elem.get('x')}, {elem.get('y')})"}


def verify_015(server_url):
    base = f"{server_url}/sites/handwritten-notes-whiteboards"
    r = requests.get(f"{base}/api/notes/10")
    note = r.json()
    filename = note.get("image_filename", "")
    return {"pass": filename == "updated_feedback.png",
            "detail": f"Note 10 image_filename: {filename}"}


def verify_016(server_url):
    base = f"{server_url}/sites/handwritten-notes-whiteboards"
    r = requests.get(f"{base}/api/notes/12")
    gone = r.status_code == 404
    return {"pass": gone, "detail": f"Note 12 status: {r.status_code} (expected 404)"}


def verify_017(server_url):
    base = f"{server_url}/sites/handwritten-notes-whiteboards"
    r = requests.get(f"{base}/api/notes/4")
    note = r.json()
    attachments = note.get("attachments", [])
    ok = "meeting_recording.mp3" in attachments
    return {"pass": ok, "detail": f"Note 4 attachments: {attachments}"}


def verify_018(server_url):
    base = f"{server_url}/sites/handwritten-notes-whiteboards"
    r = requests.get(f"{base}/api/notes/2")
    note = r.json()
    pinned = note.get("is_pinned", False)
    return {"pass": pinned is True, "detail": f"Note 2 is_pinned: {pinned}"}


def verify_019(server_url):
    base = f"{server_url}/sites/handwritten-notes-whiteboards"
    r = requests.get(f"{base}/api/export?format=csv&notebook_id=1")
    lines = r.text.strip().split("\n")
    data_rows = len(lines) - 1  # minus header
    return {"pass": data_rows > 0, "detail": f"CSV export notebook 1: {data_rows} data rows"}


def verify_020(server_url):
    base = f"{server_url}/sites/handwritten-notes-whiteboards"
    # Check whiteboard 4 shared_with list
    # Started with [1], shared with user 2, invited morgan (user 3) => [1, 2, 3]
    r = requests.get(f"{base}/api/whiteboards/4")
    wb = r.json()
    shared = wb.get("shared_with", [])
    count = len(shared)
    ok = 1 in shared and 2 in shared and 3 in shared and count == 3
    return {"pass": ok, "detail": f"Whiteboard 4 shared_with ({count} users): {shared}"}
