"""Per-task reference solutions via Flask test client for remote-calls."""
import json


def solve_001(client, base="/sites/remote-calls"):
    """Navigate to meeting detail for mtg-004. Host display name?"""
    r = client.get(f"{base}/api/meetings/mtg-004")
    data = json.loads(r.data)
    return data["host_name"]


def solve_002(client, base="/sites/remote-calls"):
    """Search meetings with 'standup'. How many?"""
    r = client.get(f"{base}/api/meetings?q=standup")
    data = json.loads(r.data)
    return str(data["count"])


def solve_003(client, base="/sites/remote-calls"):
    """Semantic search for 'deployment infrastructure'. How many results?"""
    r = client.get(f"{base}/api/meetings/search?q=deployment+infrastructure")
    data = json.loads(r.data)
    return str(data["count"])


def solve_004(client, base="/sites/remote-calls"):
    """Filter meetings by status 'scheduled'. How many?"""
    r = client.get(f"{base}/api/meetings?status=scheduled")
    data = json.loads(r.data)
    return str(data["count"])


def solve_005(client, base="/sites/remote-calls"):
    """Filter call log June 20-25. How many calls?"""
    r = client.get(f"{base}/api/call-log?date_from=2026-06-20&date_to=2026-06-25T23:59:59")
    data = json.loads(r.data)
    return str(data["count"])


def solve_006(client, base="/sites/remote-calls"):
    """Search recordings with 'sprint'. First result title?"""
    r = client.get(f"{base}/api/recordings?q=sprint")
    data = json.loads(r.data)
    recs = data["recordings"]
    return recs[0]["title"] if recs else "No results"


def solve_007(client, base="/sites/remote-calls"):
    """Meetings with more than 4 participants. How many?"""
    r = client.get(f"{base}/api/meetings")
    data = json.loads(r.data)
    meetings = data["meetings"]
    big = [m for m in meetings if len(m.get("participants", [])) > 4]
    return str(len(big))


def solve_008(client, base="/sites/remote-calls"):
    """Recording rec-005 access level?"""
    r = client.get(f"{base}/api/recordings/rec-005")
    data = json.loads(r.data)
    return data["access"]


def solve_009(client, base="/sites/remote-calls"):
    """Schedule 'Architecture Review' meeting. New meeting ID?"""
    # Login as alex.rivera
    client.post(f"{base}/api/login",
                json={"username": "alex.rivera", "password": "pass123"},
                content_type="application/json")
    r = client.post(f"{base}/api/meetings",
                    json={
                        "title": "Architecture Review",
                        "date": "2026-07-01T10:00:00-07:00",
                        "duration_minutes": 60,
                        "type": "work",
                    },
                    content_type="application/json")
    data = json.loads(r.data)
    return data["id"]


def solve_010(client, base="/sites/remote-calls"):
    """Call log entry with 'API refactor' note. Caller ID?"""
    r = client.get(f"{base}/api/call-log?q=API+refactor")
    data = json.loads(r.data)
    calls = data["calls"]
    return calls[0]["caller_id"] if calls else "Not found"


def solve_011(client, base="/sites/remote-calls"):
    """Schedule 'Budget Review' meeting. Meeting ID?"""
    # Login as alex.rivera
    client.post(f"{base}/api/login",
                json={"username": "alex.rivera", "password": "pass123"},
                content_type="application/json")
    r = client.post(f"{base}/api/meetings",
                    json={
                        "title": "Budget Review",
                        "date": "2026-07-03T14:00:00-07:00",
                        "duration_minutes": 60,
                        "type": "work",
                    },
                    content_type="application/json")
    data = json.loads(r.data)
    return data["id"]


def solve_012(client, base="/sites/remote-calls"):
    """Update settings notification_sound to 'chime'. Verify."""
    client.post(f"{base}/api/login",
                json={"username": "alex.rivera", "password": "pass123"},
                content_type="application/json")
    client.put(f"{base}/api/settings",
               json={"notification_sound": "chime", "background": "blur"},
               content_type="application/json")
    r = client.get(f"{base}/api/settings")
    data = json.loads(r.data)
    return data["settings"]["notification_sound"]


def solve_013(client, base="/sites/remote-calls"):
    """Play recording rec-001. Total views?"""
    r = client.post(f"{base}/api/recordings/rec-001/play")
    data = json.loads(r.data)
    return str(data["views"])


def solve_014(client, base="/sites/remote-calls"):
    """Export all meetings as CSV. Data rows?"""
    r = client.get(f"{base}/api/export?format=csv&type=meetings")
    lines = r.data.decode().strip().split("\n")
    return str(len(lines) - 1)


def solve_015(client, base="/sites/remote-calls"):
    """Toggle share link for mtg-005. Share link URL?"""
    r = client.post(f"{base}/api/meetings/mtg-005/share")
    data = json.loads(r.data)
    return data.get("share_link", "")


def solve_016(client, base="/sites/remote-calls"):
    """Invite rc-u-006 to mtg-014. Participant count?"""
    r = client.post(f"{base}/api/meetings/mtg-014/invite",
                    json={"user_id": "rc-u-006"},
                    content_type="application/json")
    data = json.loads(r.data)
    return str(data.get("participant_count", 0))


def solve_017(client, base="/sites/remote-calls"):
    """Send message to mtg-005 chat. Message count?"""
    client.post(f"{base}/api/login",
                json={"username": "alex.rivera", "password": "pass123"},
                content_type="application/json")
    client.post(f"{base}/api/meetings/mtg-005/messages",
                json={
                    "text": "Please review the deployment checklist before our call",
                    "sender_id": "rc-u-001",
                },
                content_type="application/json")
    r = client.get(f"{base}/api/meetings/mtg-005/messages")
    data = json.loads(r.data)
    return str(data["count"])


def solve_018(client, base="/sites/remote-calls"):
    """Book 'Sprint 48 Retrospective' with participants. Meeting ID?"""
    client.post(f"{base}/api/login",
                json={"username": "priya.sharma", "password": "pass123"},
                content_type="application/json")
    r = client.post(f"{base}/api/meetings",
                    json={
                        "title": "Sprint 48 Retrospective",
                        "date": "2026-07-02T15:00:00-07:00",
                        "duration_minutes": 45,
                        "type": "work",
                        "participants": ["rc-u-002", "rc-u-001", "rc-u-003"],
                    },
                    content_type="application/json")
    data = json.loads(r.data)
    return data["id"]


def solve_019(client, base="/sites/remote-calls"):
    """Cancel mtg-017. New status?"""
    r = client.delete(f"{base}/api/meetings/mtg-017")
    data = json.loads(r.data)
    return data["meeting"]["status"]


def solve_020(client, base="/sites/remote-calls"):
    """Join mtg-005 using code. Meeting title?"""
    r = client.post(f"{base}/api/join",
                    json={"code": "mtg-005"},
                    content_type="application/json")
    data = json.loads(r.data)
    return data["meeting"]["title"]
