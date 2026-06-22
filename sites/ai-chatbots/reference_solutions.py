"""Per-task reference solutions via Flask test client for ai-chatbots."""
import json


def solve_001(client, base="/sites/ai-chatbots"):
    r = client.get(f"{base}/chat")
    # The page shows the bot name heading when no conversation is active
    return "New Chat"


def solve_002(client, base="/sites/ai-chatbots"):
    r = client.get(f"{base}/api/knowledge/search?q=python")
    return str(len(json.loads(r.data)))


def solve_003(client, base="/sites/ai-chatbots"):
    r = client.get(f"{base}/api/knowledge/semantic?q=building+web+applications")
    return str(len(json.loads(r.data)))


def solve_004(client, base="/sites/ai-chatbots"):
    r = client.get(f"{base}/api/knowledge/5")
    return json.loads(r.data)["topic"]


def solve_005(client, base="/sites/ai-chatbots"):
    r = client.get(f"{base}/api/knowledge/2")
    return json.loads(r.data)["category"]


def solve_006(client, base="/sites/ai-chatbots"):
    r = client.post(f"{base}/api/chat",
                    json={"message": "What is machine learning?", "bot": "Assistant"})
    data = json.loads(r.data)
    return data["response"][:100]


def solve_007(client, base="/sites/ai-chatbots"):
    r = client.post(f"{base}/api/login",
                    json={"username": "alice", "password": "pass123"})
    data = json.loads(r.data)
    r2 = client.get(f"{base}/api/users/{data['user_id']}")
    user = json.loads(r2.data)
    return user["display_name"]


def solve_008(client, base="/sites/ai-chatbots"):
    r = client.get(f"{base}/api/faq/search?q=token")
    return str(len(json.loads(r.data)))


def solve_009(client, base="/sites/ai-chatbots"):
    r = client.put(f"{base}/api/users/1/subscription",
                   json={"plan": "pro"},
                   content_type="application/json")
    data = json.loads(r.data)
    return data["subscription"]


def solve_010(client, base="/sites/ai-chatbots"):
    r = client.put(f"{base}/api/conversations/conv_001",
                   json={"title": "Python Programming Help"},
                   content_type="application/json")
    data = json.loads(r.data)
    return data["title"]


def solve_011(client, base="/sites/ai-chatbots"):
    r = client.put(f"{base}/api/users/2/preferences",
                   json={"default_bot": "Analyst", "theme": "light"},
                   content_type="application/json")
    data = json.loads(r.data)
    return data["preferences"]["default_bot"]


def solve_012(client, base="/sites/ai-chatbots"):
    r = client.delete(f"{base}/api/conversations/conv_005")
    data = json.loads(r.data)
    return str(data["remaining"])


def solve_013(client, base="/sites/ai-chatbots"):
    client.put(f"{base}/api/users/1/preferences",
               json={"default_bot": "Creative"},
               content_type="application/json")
    r = client.get(f"{base}/api/prompts?q=code")
    return str(len(json.loads(r.data)))


def solve_014(client, base="/sites/ai-chatbots"):
    r = client.put(f"{base}/api/users/1/preferences",
                   json={"font_size": "large"},
                   content_type="application/json")
    data = json.loads(r.data)
    return data["preferences"]["font_size"]


def solve_015(client, base="/sites/ai-chatbots"):
    r = client.post(f"{base}/api/chat",
                    json={"message": "hello", "bot": "Creative"})
    data = json.loads(r.data)
    return data["response"]


def solve_016(client, base="/sites/ai-chatbots"):
    r = client.get(f"{base}/api/export?type=knowledge&format=csv")
    lines = r.data.decode().strip().split("\n")
    return str(len(lines) - 1)


def solve_017(client, base="/sites/ai-chatbots"):
    r = client.post(f"{base}/api/upload",
                    json={
                        "topic": "Docker Containers",
                        "category": "infrastructure",
                        "content": "Docker is a platform for building and running containers.",
                        "keywords": ["docker", "container"]
                    },
                    content_type="application/json")
    data = json.loads(r.data)
    return str(data["id"])


def solve_018(client, base="/sites/ai-chatbots"):
    r = client.post(f"{base}/api/conversations/conv_003/share",
                    json={"share_with": "public"},
                    content_type="application/json")
    data = json.loads(r.data)
    return str(data["shared"]).lower()


def solve_019(client, base="/sites/ai-chatbots"):
    client.post(f"{base}/api/login",
                json={"username": "alice", "password": "pass123"},
                content_type="application/json")
    r = client.post(f"{base}/api/users/1/save-prompt",
                    json={"prompt_id": 3},
                    content_type="application/json")
    data = json.loads(r.data)
    client.put(f"{base}/api/users/1/preferences",
               json={"save_history": False},
               content_type="application/json")
    return data["action"]


def solve_020(client, base="/sites/ai-chatbots"):
    r = client.post(f"{base}/api/register",
                    json={
                        "username": "newuser",
                        "password": "newpass123",
                        "email": "new@test.com",
                        "display_name": "New User"
                    },
                    content_type="application/json")
    data = json.loads(r.data)
    return str(data["user_id"])
