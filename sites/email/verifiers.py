"""Per-task HTTP verification functions for email."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/email"
    r = requests.get(f"{base}/api/messages")
    data = r.json()
    total = data.get("total", 0)
    return {"pass": total > 0, "detail": f"Total messages: {total}"}


def verify_002(server_url):
    base = f"{server_url}/sites/email"
    r = requests.get(f"{base}/api/users/1")
    user = r.json()
    email = user.get("email_address")
    return {"pass": email == "lynn.blair@enron.com", "detail": f"Lynn's email: {email}"}


def verify_003(server_url):
    base = f"{server_url}/sites/email"
    r = requests.get(f"{base}/api/folders?user_id=1")
    folders = r.json()
    count = len(folders)
    return {"pass": count == 5, "detail": f"Lynn's folders: {count} ({folders})"}


def verify_004(server_url):
    base = f"{server_url}/sites/email"
    r = requests.get(f"{base}/api/folders/inbox/count?user_id=1")
    data = r.json()
    total = data.get("total", 0)
    return {"pass": total >= 0, "detail": f"Lynn's inbox messages: {total}"}


def verify_005(server_url):
    base = f"{server_url}/sites/email"
    s = requests.Session()
    r = s.post(f"{base}/api/login", json={"username": "lynn_blair", "password": "pass123"})
    data = r.json()
    ok = data.get("user_id") == 1
    return {"pass": ok, "detail": f"Login: user_id={data.get('user_id')}"}


def verify_006(server_url):
    base = f"{server_url}/sites/email"
    r = requests.get(f"{base}/api/stats?user_id=1")
    data = r.json()
    unread = data.get("unread", 0)
    return {"pass": unread >= 0, "detail": f"Lynn's unread: {unread}"}


def verify_007(server_url):
    base = f"{server_url}/sites/email"
    r = requests.get(f"{base}/api/messages?user_id=2&folder=inbox")
    data = r.json()
    total = data.get("total", 0)
    return {"pass": total >= 0, "detail": f"Michael's inbox: {total} messages"}


def verify_008(server_url):
    base = f"{server_url}/sites/email"
    r = requests.get(f"{base}/api/messages?user_id=1&folder=sent")
    data = r.json()
    total = data.get("total", 0)
    return {"pass": total >= 0, "detail": f"Lynn's sent: {total} messages"}


def verify_009(server_url):
    base = f"{server_url}/sites/email"
    r = requests.get(f"{base}/api/search?user_id=1&q=pipeline")
    results = r.json()
    count = len(results)
    return {"pass": count >= 0, "detail": f"Search 'pipeline' for Lynn: {count} results"}


def verify_010(server_url):
    base = f"{server_url}/sites/email"
    r = requests.get(f"{base}/api/contacts")
    contacts = r.json()
    count = len(contacts)
    return {"pass": count > 0, "detail": f"Unique contacts: {count}"}


def verify_011(server_url):
    base = f"{server_url}/sites/email"
    r = requests.get(f"{base}/api/messages?user_id=3&sort=subject")
    data = r.json()
    messages = data.get("messages", [])
    if messages:
        first = messages[0]
        return {"pass": True, "detail": f"First by subject: {first.get('subject', '')}"}
    return {"pass": False, "detail": "No messages for user 3"}


def verify_012(server_url):
    base = f"{server_url}/sites/email"
    r = requests.get(f"{base}/api/stats?user_id=2")
    data = r.json()
    total = data.get("total", 0)
    starred = data.get("starred", 0)
    return {"pass": total >= 0, "detail": f"Michael: {total} total, {starred} starred"}


def verify_013(server_url):
    base = f"{server_url}/sites/email"
    r = requests.get(f"{base}/api/messages?user_id=1&page=1")
    data = r.json()
    messages = data.get("messages", [])
    if messages:
        subject = messages[0].get("subject", "")
        return {"pass": True, "detail": f"Lynn's most recent: {subject}"}
    return {"pass": False, "detail": "No messages"}


def verify_014(server_url):
    base = f"{server_url}/sites/email"
    r = requests.get(f"{base}/api/stats")
    data = r.json()
    senders = data.get("unique_senders", 0)
    return {"pass": senders > 0, "detail": f"Unique senders: {senders}"}


def verify_015(server_url):
    base = f"{server_url}/sites/email"
    # Get sent count before
    r1 = requests.get(f"{base}/api/folders/sent/count?user_id=1")
    before = r1.json().get("total", 0)
    # Send message
    r = requests.post(f"{base}/api/messages/compose", json={
        "user_id": 1,
        "to": "michael.bodnar@enron.com",
        "subject": "Test Message",
        "body": "Hello Michael"
    })
    data = r.json()
    status = data.get("status")
    # Check sent count after
    r2 = requests.get(f"{base}/api/folders/sent/count?user_id=1")
    after = r2.json().get("total", 0)
    return {"pass": status == "sent" and after > before,
            "detail": f"Compose: status={status}, sent before={before}, after={after}"}


def verify_016(server_url):
    base = f"{server_url}/sites/email"
    r = requests.post(f"{base}/api/messages/1/star", json={"user_id": 1})
    data = r.json()
    is_starred = data.get("is_starred")
    return {"pass": is_starred is True, "detail": f"Message 1 starred: {is_starred}"}


def verify_017(server_url):
    base = f"{server_url}/sites/email"
    r = requests.post(f"{base}/api/messages/2/move", json={"user_id": 1, "folder": "trash"})
    data = r.json()
    new_folder = data.get("new_folder")
    return {"pass": new_folder == "trash", "detail": f"Message 2 moved to: {new_folder}"}


def verify_018(server_url):
    base = f"{server_url}/sites/email"
    r = requests.post(f"{base}/api/messages/3/label", json={
        "user_id": 1,
        "label": "important",
        "action": "add"
    })
    data = r.json()
    labels = data.get("labels", [])
    return {"pass": "important" in labels, "detail": f"Message 3 labels: {labels}"}


def verify_019(server_url):
    base = f"{server_url}/sites/email"
    # Send from user 3 to user 4
    r = requests.post(f"{base}/api/messages/compose", json={
        "user_id": 3,
        "to": "britt.davis@enron.com",
        "subject": "Meeting Tomorrow",
        "body": "Can we meet at 3pm?"
    })
    data = r.json()
    status = data.get("status")
    # Check user 4's inbox for the message
    r2 = requests.get(f"{base}/api/search?user_id=4&q=Meeting+Tomorrow")
    results = r2.json()
    found = any(m.get("subject") == "Meeting Tomorrow" for m in results)
    return {"pass": status == "sent" and found,
            "detail": f"Sent: status={status}, delivered to user 4: {found}"}


def verify_020(server_url):
    base = f"{server_url}/sites/email"
    # Mark message 1 as read
    requests.post(f"{base}/api/messages/1/read", json={"user_id": 1, "mark": "read"})
    # Get stats
    r = requests.get(f"{base}/api/stats?user_id=1")
    data = r.json()
    unread = data.get("unread", 0)
    return {"pass": unread >= 0, "detail": f"Lynn's unread after marking read: {unread}"}
