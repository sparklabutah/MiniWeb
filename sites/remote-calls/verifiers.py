"""Per-task HTTP verification functions for remote-calls."""
import requests


def verify_001(server_url):
    """Navigate to meeting detail for mtg-004. Host display name?"""
    base = f"{server_url}/sites/remote-calls"
    r = requests.get(f"{base}/api/meetings/mtg-004")
    data = r.json()
    host_name = data.get("host_name", "")
    return {"pass": host_name == "Priya Sharma",
            "detail": f"mtg-004 host: {host_name}"}


def verify_002(server_url):
    """Search meetings with 'standup'. How many?"""
    base = f"{server_url}/sites/remote-calls"
    r = requests.get(f"{base}/api/meetings?q=standup")
    data = r.json()
    count = data.get("count", 0)
    # Meetings with 'standup' in title: mtg-001, mtg-002, mtg-003, mtg-017 = 4
    return {"pass": count == 4, "detail": f"standup search: {count} meetings"}


def verify_003(server_url):
    """Semantic search for 'deployment infrastructure'. How many results?"""
    base = f"{server_url}/sites/remote-calls"
    r = requests.get(f"{base}/api/meetings/search?q=deployment+infrastructure")
    data = r.json()
    count = data.get("count", 0)
    return {"pass": count > 0, "detail": f"semantic search 'deployment infrastructure': {count} results"}


def verify_004(server_url):
    """Filter meetings by status 'scheduled'. How many?"""
    base = f"{server_url}/sites/remote-calls"
    r = requests.get(f"{base}/api/meetings?status=scheduled")
    data = r.json()
    count = data.get("count", 0)
    # mtg-005 and mtg-017 are scheduled = 2
    return {"pass": count == 2, "detail": f"scheduled meetings: {count}"}


def verify_005(server_url):
    """Filter call log June 20-25. How many calls?"""
    base = f"{server_url}/sites/remote-calls"
    r = requests.get(f"{base}/api/call-log?date_from=2026-06-20&date_to=2026-06-25T23:59:59")
    data = r.json()
    count = data.get("count", 0)
    return {"pass": count > 0, "detail": f"calls Jun 20-25: {count}"}


def verify_006(server_url):
    """Search recordings with 'sprint'. First result title?"""
    base = f"{server_url}/sites/remote-calls"
    r = requests.get(f"{base}/api/recordings?q=sprint")
    data = r.json()
    recs = data.get("recordings", [])
    if not recs:
        return {"pass": False, "detail": "No sprint recordings found"}
    first_title = recs[0].get("title", "")
    return {"pass": len(first_title) > 0, "detail": f"First sprint recording: {first_title}"}


def verify_007(server_url):
    """Meetings with more than 4 participants. How many?"""
    base = f"{server_url}/sites/remote-calls"
    r = requests.get(f"{base}/api/meetings")
    data = r.json()
    meetings = data.get("meetings", [])
    big_meetings = [m for m in meetings if len(m.get("participants", [])) > 4]
    count = len(big_meetings)
    # mtg-004 (5), mtg-005 (5), mtg-012 (6) = 3
    return {"pass": count == 3, "detail": f"meetings with >4 participants: {count}"}


def verify_008(server_url):
    """Recording rec-005 access level?"""
    base = f"{server_url}/sites/remote-calls"
    r = requests.get(f"{base}/api/recordings/rec-005")
    data = r.json()
    access = data.get("access", "")
    return {"pass": access == "organization",
            "detail": f"rec-005 access: {access}"}


def verify_009(server_url):
    """Schedule 'Architecture Review' meeting. New meeting ID?"""
    base = f"{server_url}/sites/remote-calls"
    r = requests.get(f"{base}/api/meetings?q=Architecture+Review")
    data = r.json()
    matches = data.get("meetings", [])
    if not matches:
        return {"pass": False, "detail": "Architecture Review meeting not found"}
    meeting = matches[0]
    return {"pass": meeting["status"] == "scheduled" and meeting["title"] == "Architecture Review",
            "detail": f"Created meeting: {meeting['id']} ({meeting['title']})"}


def verify_010(server_url):
    """Call log entry with 'API refactor' note. Caller ID?"""
    base = f"{server_url}/sites/remote-calls"
    r = requests.get(f"{base}/api/call-log?q=API+refactor")
    data = r.json()
    calls = data.get("calls", [])
    if not calls:
        return {"pass": False, "detail": "No call with 'API refactor' found"}
    caller_id = calls[0].get("caller_id", "")
    return {"pass": caller_id == "rc-u-001",
            "detail": f"API refactor caller: {caller_id}"}


def verify_011(server_url):
    """Schedule 'Budget Review' meeting. Meeting ID?"""
    base = f"{server_url}/sites/remote-calls"
    r = requests.get(f"{base}/api/meetings?q=Budget+Review")
    data = r.json()
    matches = data.get("meetings", [])
    if not matches:
        return {"pass": False, "detail": "Budget Review meeting not found"}
    meeting = matches[0]
    return {"pass": meeting["title"] == "Budget Review" and meeting["status"] == "scheduled",
            "detail": f"Created meeting: {meeting['id']} ({meeting['title']})"}


def verify_012(server_url):
    """Update settings notification_sound to 'chime'. Verify."""
    base = f"{server_url}/sites/remote-calls"
    # Login as alex.rivera first
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "alex.rivera", "password": "pass123"})
    r = s.get(f"{base}/api/settings")
    data = r.json()
    settings = data.get("settings", {})
    notification = settings.get("notification_sound", "")
    return {"pass": notification == "chime",
            "detail": f"notification_sound: {notification}"}


def verify_013(server_url):
    """Play recording rec-001. Total views?"""
    base = f"{server_url}/sites/remote-calls"
    r = requests.get(f"{base}/api/recordings/rec-001")
    data = r.json()
    views = data.get("views", 0)
    # Original views = 6, after play = 7
    return {"pass": views >= 7, "detail": f"rec-001 views: {views}"}


def verify_014(server_url):
    """Export all meetings as CSV. Data rows?"""
    base = f"{server_url}/sites/remote-calls"
    r = requests.get(f"{base}/api/export?format=csv&type=meetings")
    lines = r.text.strip().split("\n")
    data_rows = len(lines) - 1  # minus header
    return {"pass": data_rows >= 18, "detail": f"CSV export: {data_rows} data rows"}


def verify_015(server_url):
    """Toggle share link for mtg-005. Share link URL?"""
    base = f"{server_url}/sites/remote-calls"
    r = requests.get(f"{base}/api/meetings/mtg-005")
    data = r.json()
    share_link = data.get("share_link", "")
    share_active = data.get("share_link_active", False)
    return {"pass": share_active and "mtg-005" in share_link,
            "detail": f"mtg-005 share_link: {share_link}, active={share_active}"}


def verify_016(server_url):
    """Invite rc-u-006 to mtg-014. Participant count?"""
    base = f"{server_url}/sites/remote-calls"
    r = requests.get(f"{base}/api/meetings/mtg-014")
    data = r.json()
    participants = data.get("participants", [])
    has_user = "rc-u-006" in participants
    count = len(participants)
    # Original: rc-u-001, rc-u-007 (2), after invite: 3
    return {"pass": has_user and count == 3,
            "detail": f"mtg-014 participants: {count}, has rc-u-006: {has_user}"}


def verify_017(server_url):
    """Send message to mtg-005 chat. Message count?"""
    base = f"{server_url}/sites/remote-calls"
    r = requests.get(f"{base}/api/meetings/mtg-005/messages")
    data = r.json()
    count = data.get("count", 0)
    msgs = data.get("messages", [])
    has_deploy_msg = any("deployment checklist" in m.get("text", "").lower() for m in msgs)
    return {"pass": count >= 1 and has_deploy_msg,
            "detail": f"mtg-005 messages: {count}, has deploy checklist msg: {has_deploy_msg}"}


def verify_018(server_url):
    """Book 'Sprint 48 Retrospective' with participants. Meeting ID?"""
    base = f"{server_url}/sites/remote-calls"
    r = requests.get(f"{base}/api/meetings?q=Sprint+48+Retrospective")
    data = r.json()
    matches = data.get("meetings", [])
    if not matches:
        return {"pass": False, "detail": "Sprint 48 Retrospective not found"}
    meeting = matches[0]
    participants = meeting.get("participants", [])
    has_u001 = "rc-u-001" in participants
    has_u003 = "rc-u-003" in participants
    return {"pass": meeting["title"] == "Sprint 48 Retrospective" and has_u001 and has_u003,
            "detail": f"Meeting: {meeting['id']}, participants: {participants}"}


def verify_019(server_url):
    """Cancel mtg-017. New status?"""
    base = f"{server_url}/sites/remote-calls"
    r = requests.get(f"{base}/api/meetings/mtg-017")
    data = r.json()
    status = data.get("status", "")
    return {"pass": status == "cancelled",
            "detail": f"mtg-017 status: {status}"}


def verify_020(server_url):
    """Join mtg-005 using code. Meeting title?"""
    base = f"{server_url}/sites/remote-calls"
    r = requests.get(f"{base}/api/meetings/mtg-005")
    data = r.json()
    title = data.get("title", "")
    return {"pass": title == "Sprint Planning - Sprint 48",
            "detail": f"Joined meeting title: {title}"}
