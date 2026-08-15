"""Password manager handler — stores credentials when users register on sites."""

from datetime import datetime

from app import db
from app.events import on


@on("signup")
def add_to_vault(user_id, site_name, username, password="", email="",
                 site_url="", **kwargs):
    entries = db.query("password-managers", "entries")

    # Determine next entry ID
    max_num = 0
    for e in entries:
        eid = e.get("id", "")
        if isinstance(eid, str) and "_" in eid:
            try:
                max_num = max(max_num, int(eid.split("_")[1]))
            except (IndexError, ValueError):
                pass
        elif isinstance(eid, int):
            max_num = max(max_num, eid)
    new_id = f"entry_{max_num + 1:03d}"

    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    url = site_url or f"/sites/{site_name}/"
    display_name = site_name.replace("-", " ").title()

    entries.append({
        "id": new_id,
        "vault_id": "vault_001",
        "title": f"{display_name} Login",
        "url": url,
        "username": username,
        "password": password or "••••••••",
        "category": "login",
        "notes": f"Auto-saved from {display_name} registration",
        "created_at": now,
        "updated_at": now,
        "last_used": now,
        "strength": "strong",
        "favorite": False,
        "tags": ["auto-saved", site_name],
    })
    db.save_collection("password-managers", "entries", entries)
