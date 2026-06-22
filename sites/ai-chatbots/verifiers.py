"""Per-task HTTP verification functions for ai-chatbots."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/ai-chatbots"
    r = requests.get(f"{base}/chat")
    ok = r.status_code == 200 and "How can I help you today" in r.text
    return {"pass": ok, "detail": f"Chat page loads: {r.status_code}"}


def verify_002(server_url):
    base = f"{server_url}/sites/ai-chatbots"
    r = requests.get(f"{base}/api/knowledge/search?q=python")
    results = r.json()
    count = len(results)
    return {"pass": count > 0, "detail": f"Knowledge search 'python': {count} results"}


def verify_003(server_url):
    base = f"{server_url}/sites/ai-chatbots"
    r = requests.get(f"{base}/api/knowledge/semantic?q=building+web+applications")
    results = r.json()
    count = len(results)
    return {"pass": count > 0, "detail": f"Semantic search 'web applications': {count} results"}


def verify_004(server_url):
    base = f"{server_url}/sites/ai-chatbots"
    r = requests.get(f"{base}/api/knowledge/5")
    entry = r.json()
    topic = entry.get("topic", "")
    return {"pass": topic == "Natural Language Processing",
            "detail": f"KB entry 5 topic: {topic}"}


def verify_005(server_url):
    base = f"{server_url}/sites/ai-chatbots"
    r = requests.get(f"{base}/api/knowledge/2")
    entry = r.json()
    cat = entry.get("category", "")
    return {"pass": cat == "ai", "detail": f"KB entry 2 category: {cat}"}


def verify_006(server_url):
    base = f"{server_url}/sites/ai-chatbots"
    r = requests.post(f"{base}/api/chat", json={
        "message": "What is machine learning?",
        "bot": "Assistant"
    })
    data = r.json()
    response = data.get("response", "")
    has_ml = "machine learning" in response.lower() or "learning" in response.lower()
    return {"pass": has_ml and len(response) > 20,
            "detail": f"Chat response length: {len(response)}, mentions ML: {has_ml}"}


def verify_007(server_url):
    base = f"{server_url}/sites/ai-chatbots"
    r = requests.get(f"{base}/api/users/1")
    user = r.json()
    name = user.get("display_name", "")
    return {"pass": name == "Alice Johnson", "detail": f"User 1 display_name: {name}"}


def verify_008(server_url):
    base = f"{server_url}/sites/ai-chatbots"
    r = requests.get(f"{base}/api/faq/search?q=token")
    results = r.json()
    count = len(results)
    return {"pass": count > 0, "detail": f"FAQ search 'token': {count} results"}


def verify_009(server_url):
    base = f"{server_url}/sites/ai-chatbots"
    r = requests.put(f"{base}/api/users/1/subscription",
                     json={"plan": "pro"})
    data = r.json()
    sub = data.get("subscription", "")
    return {"pass": sub == "pro", "detail": f"User 1 subscription: {sub}"}


def verify_010(server_url):
    base = f"{server_url}/sites/ai-chatbots"
    r = requests.put(f"{base}/api/conversations/conv_001",
                     json={"title": "Python Programming Help"})
    data = r.json()
    title = data.get("title", "")
    return {"pass": title == "Python Programming Help",
            "detail": f"Conv title updated: {title}"}


def verify_011(server_url):
    base = f"{server_url}/sites/ai-chatbots"
    r = requests.put(f"{base}/api/users/2/preferences",
                     json={"default_bot": "Analyst", "theme": "light"})
    data = r.json()
    prefs = data.get("preferences", {})
    bot = prefs.get("default_bot", "")
    return {"pass": bot == "Analyst", "detail": f"User 2 default_bot: {bot}"}


def verify_012(server_url):
    base = f"{server_url}/sites/ai-chatbots"
    r = requests.delete(f"{base}/api/conversations/conv_005")
    data = r.json()
    remaining = data.get("remaining", -1)
    return {"pass": remaining >= 0 and data.get("deleted") == "conv_005",
            "detail": f"Deleted conv_005, remaining: {remaining}"}


def verify_013(server_url):
    base = f"{server_url}/sites/ai-chatbots"
    # Configure
    requests.put(f"{base}/api/users/1/preferences",
                 json={"default_bot": "Creative"})
    # Search prompts
    r = requests.get(f"{base}/api/prompts?q=code")
    results = r.json()
    count = len(results)
    return {"pass": count > 0, "detail": f"Prompts search 'code': {count} results"}


def verify_014(server_url):
    base = f"{server_url}/sites/ai-chatbots"
    r = requests.put(f"{base}/api/users/1/preferences",
                     json={"font_size": "large"})
    data = r.json()
    fs = data.get("preferences", {}).get("font_size", "")
    return {"pass": fs == "large", "detail": f"User 1 font_size: {fs}"}


def verify_015(server_url):
    base = f"{server_url}/sites/ai-chatbots"
    r = requests.post(f"{base}/api/chat", json={
        "message": "hello",
        "bot": "Creative"
    })
    data = r.json()
    response = data.get("response", "")
    has_greeting = "hello" in response.lower() or "hi" in response.lower()
    return {"pass": has_greeting, "detail": f"Greeting response: {response[:80]}"}


def verify_016(server_url):
    base = f"{server_url}/sites/ai-chatbots"
    r = requests.get(f"{base}/api/export?type=knowledge&format=csv")
    lines = r.text.strip().split("\n")
    data_rows = len(lines) - 1
    return {"pass": data_rows > 0, "detail": f"KB CSV export: {data_rows} data rows"}


def verify_017(server_url):
    base = f"{server_url}/sites/ai-chatbots"
    r = requests.post(f"{base}/api/upload", json={
        "topic": "Docker Containers",
        "category": "infrastructure",
        "content": "Docker is a platform for building, shipping, and running applications in containers. Containers package an application with all its dependencies into a standardized unit.",
        "keywords": ["docker", "container", "devops"]
    })
    data = r.json()
    new_id = data.get("id")
    return {"pass": new_id is not None and new_id > 0,
            "detail": f"Upload new KB entry, id: {new_id}"}


def verify_018(server_url):
    base = f"{server_url}/sites/ai-chatbots"
    r = requests.post(f"{base}/api/conversations/conv_003/share",
                      json={"share_with": "public"})
    data = r.json()
    shared = data.get("shared", False)
    return {"pass": shared is True, "detail": f"Conv shared: {shared}"}


def verify_019(server_url):
    base = f"{server_url}/sites/ai-chatbots"
    # Login
    requests.post(f"{base}/api/login",
                  json={"username": "alice", "password": "pass123"})
    # Save prompt
    r = requests.post(f"{base}/api/users/1/save-prompt",
                      json={"prompt_id": 3})
    data = r.json()
    action = data.get("action", "")
    # Toggle save_history
    requests.put(f"{base}/api/users/1/preferences",
                 json={"save_history": False})
    return {"pass": action == "saved", "detail": f"Save prompt action: {action}"}


def verify_020(server_url):
    base = f"{server_url}/sites/ai-chatbots"
    r = requests.post(f"{base}/api/register", json={
        "username": "newuser",
        "password": "newpass123",
        "email": "new@test.com",
        "display_name": "New User"
    })
    data = r.json()
    user_id = data.get("user_id")
    return {"pass": user_id is not None and user_id > 0,
            "detail": f"Registered user_id: {user_id}"}
