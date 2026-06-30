"""Calendar handler — creates events for bookings."""

from datetime import datetime

from app import db
from app.events import on


@on("booking")
def handle_booking(user_id, title, start, end="", location="",
                   service_name="", confirmation_id="", **kwargs):
    max_id = db.execute(
        "SELECT MAX(id) FROM calendar_todo_events", fetch="val") or 0
    new_id = max(max_id + 1, 90001)

    event = {
        "id": new_id,
        "user_id": user_id,
        "title": title,
        "description": f"Booked via {service_name}" if service_name else "",
        "category": "personal",
        "calendar": "Personal",
        "start": start,
        "end_": end or start,
        "all_day": 0,
        "location": location,
        "recurring": "",
        "reminder_minutes": 30,
        "priority": "medium",
        "status": "confirmed",
        "attendees": [],
        "color": "#34a853",
        "created_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    }
    db.save_item("calendar-todo", "events", new_id, event)
