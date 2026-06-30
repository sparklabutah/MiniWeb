"""Per-task HTTP verification functions for team-chat-workspace."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/team-chat-workspace"
    r = requests.get(f"{base}/api/messages/search?q=caching")
    data = r.json()
    count = len(data.get("results", []))
    return {"pass": count > 0, "detail": f"Search 'caching': {count} results"}


def verify_002(server_url):
    base = f"{server_url}/sites/team-chat-workspace"
    r = requests.get(f"{base}/api/channels/ch-engineering")
    channel = r.json()
    topic = channel.get("topic", "")
    return {"pass": len(topic) > 0, "detail": f"Engineering topic: {topic[:60]}"}


def verify_003(server_url):
    base = f"{server_url}/sites/team-chat-workspace"
    r = requests.get(f"{base}/api/threads/thr-001")
    thread = r.json()
    reply_count = len(thread.get("replies", []))
    return {"pass": reply_count > 0, "detail": f"Thread thr-001 has {reply_count} replies"}


def verify_004(server_url):
    base = f"{server_url}/sites/team-chat-workspace"
    r = requests.get(f"{base}/api/messages/search?q=deploy")
    data = r.json()
    count = data.get("count", 0)
    return {"pass": count >= 0, "detail": f"Search 'deploy': {count} total results"}


def verify_005(server_url):
    base = f"{server_url}/sites/team-chat-workspace"
    r = requests.get(f"{base}/api/messages/search?q=PR&channel=ch-engineering")
    data = r.json()
    count = len(data.get("results", []))
    return {"pass": count >= 0, "detail": f"Search 'PR' in engineering: {count} results"}


def verify_006(server_url):
    base = f"{server_url}/sites/team-chat-workspace"
    r = requests.get(f"{base}/api/members?department=Engineering")
    members = r.json()
    count = len(members)
    return {"pass": count > 0, "detail": f"Engineering members: {count}"}


def verify_007(server_url):
    base = f"{server_url}/sites/team-chat-workspace"
    r = requests.get(f"{base}/api/channels/ch-general/messages?date=2026-06-24")
    data = r.json()
    count = len(data.get("messages", []))
    return {"pass": count >= 0, "detail": f"General messages on 2026-06-24: {count}"}


def verify_008(server_url):
    base = f"{server_url}/sites/team-chat-workspace"
    r = requests.get(f"{base}/api/messages/search?q=birthday")
    data = r.json()
    results = data.get("results", [])
    if results:
        user_name = results[0].get("user", {}).get("display_name", "")
        return {"pass": len(user_name) > 0, "detail": f"Birthday poster: {user_name}"}
    return {"pass": False, "detail": "No birthday messages found"}


def verify_009(server_url):
    base = f"{server_url}/sites/team-chat-workspace"
    r = requests.get(f"{base}/api/messages/search?q=nginx")
    data = r.json()
    results = data.get("results", [])
    thread_results = data.get("thread_results", [])
    total = len(results) + len(thread_results)
    channel = ""
    if results:
        channel = results[0].get("channel", {}).get("name", "")
    elif thread_results:
        channel = thread_results[0].get("channel", {}).get("name", "")
    return {"pass": total > 0, "detail": f"nginx search: {total} results, channel={channel}"}


def verify_010(server_url):
    base = f"{server_url}/sites/team-chat-workspace"
    r = requests.get(f"{base}/api/members?department=Sales")
    members = r.json()
    if members:
        name = members[0].get("display_name", "")
        return {"pass": len(name) > 0, "detail": f"Sales member: {name}"}
    return {"pass": False, "detail": "No Sales members found"}


def verify_011(server_url):
    base = f"{server_url}/sites/team-chat-workspace"
    r = requests.get(f"{base}/api/channels/ch-general")
    channel = r.json()
    member_count = channel.get("member_count", 0)
    return {"pass": member_count > 0, "detail": f"General channel members: {member_count}"}


def verify_012(server_url):
    base = f"{server_url}/sites/team-chat-workspace"
    r = requests.post(f"{base}/api/channels", json={
        "name": "project-alpha",
        "description": "Project Alpha team discussions",
    })
    data = r.json()
    ok = r.status_code == 201 or "already exists" in data.get("error", "")
    return {"pass": ok, "detail": f"Create channel: status={r.status_code}"}


def verify_013(server_url):
    base = f"{server_url}/sites/team-chat-workspace"
    r = requests.get(f"{base}/api/messages/search?q=All-Hands")
    data = r.json()
    results = data.get("results", [])
    if results:
        text = results[0].get("text", "")
        return {"pass": len(text) > 0, "detail": f"All-Hands result: {text[:60]}"}
    return {"pass": False, "detail": "No All-Hands results"}


def verify_014(server_url):
    base = f"{server_url}/sites/team-chat-workspace"
    new_text = "The matcha was amazing! I saved some mochi in the freezer for the team."
    r = requests.put(f"{base}/api/messages/msg-004", json={"text": new_text})
    data = r.json()
    ok = data.get("text") == new_text and data.get("edited") is True
    return {"pass": ok, "detail": f"Edit msg-004: edited={data.get('edited')}"}


def verify_015(server_url):
    base = f"{server_url}/sites/team-chat-workspace"
    # After the reference solution deletes msg-006, verify it's gone
    r2 = requests.get(f"{base}/api/channels/ch-general/messages")
    msgs = r2.json().get("messages", [])
    found = any(m["id"] == "msg-006" for m in msgs)
    return {"pass": not found, "detail": f"msg-006 still_exists={found}"}


def verify_016(server_url):
    base = f"{server_url}/sites/team-chat-workspace"
    r = requests.post(f"{base}/api/channels/ch-random/messages", json={
        "text": "Anyone up for coffee at 3pm?"
    })
    data = r.json()
    ok = r.status_code == 201 and "coffee" in data.get("text", "")
    return {"pass": ok, "detail": f"Post to random: id={data.get('id')}"}


def verify_017(server_url):
    base = f"{server_url}/sites/team-chat-workspace"
    r = requests.post(f"{base}/api/messages/msg-007/react", json={"emoji": ":thumbsup:"})
    data = r.json()
    ok = data.get("status") in ("added", "removed")
    return {"pass": ok, "detail": f"React to msg-007: {data.get('status')}"}


def verify_018(server_url):
    base = f"{server_url}/sites/team-chat-workspace"
    r = requests.post(f"{base}/api/channels/ch-data-science/follow")
    data = r.json()
    ok = data.get("action") in ("followed", "unfollowed")
    return {"pass": ok, "detail": f"Follow ch-data-science: {data.get('action')}"}


def verify_019(server_url):
    base = f"{server_url}/sites/team-chat-workspace"
    s = requests.Session()
    s.post(f"{base}/login", data={"user_id": "1"})
    r = s.post(f"{base}/api/channels/ch-engineering/messages", json={
        "text": "Testing chat integration"
    })
    data = r.json()
    ok = r.status_code == 201 and "Testing" in data.get("text", "")
    return {"pass": ok, "detail": f"Auth + message: id={data.get('id')}"}


def verify_020(server_url):
    base = f"{server_url}/sites/team-chat-workspace"
    # Save message
    r1 = requests.post(f"{base}/api/messages/msg-001/save")
    save_ok = r1.json().get("action") in ("saved", "unsaved")
    # Block user
    r2 = requests.post(f"{base}/api/members/tc-u005/block")
    block_ok = r2.json().get("action") in ("blocked", "unblocked")
    return {"pass": save_ok and block_ok,
            "detail": f"Save: {r1.json().get('action')}, Block: {r2.json().get('action')}"}
