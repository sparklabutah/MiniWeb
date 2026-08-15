"""Lakeport Events -- event ticketing platform (Eventbrite / Ticketmaster style).

Reads event listings, tickets, orders, and user profiles from the shared
data-sources directory and serves them through Flask routes with filtering,
search, and purchase capabilities.

Macro coverage (27):
  navigate_by_dropdown, navigate_by_route, search_by_query,
  search_by_semantic, filter_by_query, filter_by_dropdown,
  filter_by_checkbox, filter_by_slider, filter_by_date_range,
  sort_by_ranking, extract_by_query, extract_from_table,
  compare_from_table, submit_by_query, select_by_slider,
  select_by_date_range, configure_by_dropdown, configure_by_slider,
  export_by_dropdown, save_by_toggle, add_by_button,
  checkout_by_form, book_by_form, redeem_by_code,
  cancel_by_form, authenticate_by_form, register_by_form
"""

import hashlib
import pathlib
from datetime import datetime, date

from flask import (
    Blueprint, Response, abort, jsonify, redirect, render_template, request,
    session, url_for,
)
from app import db
from app.events import emit
from helpers.auth import current_user, browsing_user

SITE = "ticketing-events"
SITE_DIR = pathlib.Path(__file__).resolve().parent
_EVENTS_TABLE = "ticketing_events_events"

# Size of one page in the scrollable events feed (search_by_scroll). The feed
# renders one page server-side and appends the rest as the user scrolls, so
# far-down events are off-screen until scrolled to.
FEED_PAGE_SIZE = 20

# Open-for-registration first (soonest date first), then past/completed events
# (most recent first). Done entirely in SQL so LIMIT/OFFSET paging is stable.
# [id] is the final tiebreaker so page boundaries never split or duplicate rows.
_LISTING_ORDER = (
    "CASE WHEN [status]='on_sale' THEN 0 ELSE 1 END, "
    "CASE WHEN [status]='on_sale' THEN [date] ELSE '' END ASC, "
    "CASE WHEN [status]='on_sale' THEN '' ELSE [date] END DESC, "
    "[id] ASC"
)

blueprint = Blueprint(
    "ticketing-events",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _load_events():
    return db.query(SITE, "events")


def _save_events(events):
    db.save_collection(SITE, "events", events)


def _events_for_listing():
    """Events ordered for the listing: open-for-registration first, past last.

    An event's state is the ``status`` field: ``on_sale`` == open for
    registration, anything else (``completed``) == past/closed. Site dates are
    intentionally static, so state comes from ``status`` -- no date anchoring or
    mutation needed. Ordering is done in SQL (open group first, then soonest
    date within the open group and most-recent date within the past group),
    matching the auctions site's "still running before ended" pattern.
    """
    order = (
        "CASE WHEN [status]='on_sale' THEN 0 ELSE 1 END, "
        "CASE WHEN [status]='on_sale' THEN [date] ELSE '' END ASC, "
        "CASE WHEN [status]='on_sale' THEN '' ELSE [date] END DESC"
    )
    rows = db.execute(f"SELECT * FROM [{_EVENTS_TABLE}] ORDER BY {order}")
    # Raw SQL reads the base table only; merge this session's overlay edits
    # (e.g. sold-count updates after a purchase) so isolation is preserved.
    events = db.merge_overlay(SITE, "events", rows)
    # Overlay merge can reorder; re-apply the open-first grouping as the
    # authoritative order over the already-materialized listing set.
    open_events = sorted(
        (e for e in events if e.get("status") == "on_sale"),
        key=lambda e: e.get("date", ""),
    )
    past_events = sorted(
        (e for e in events if e.get("status") != "on_sale"),
        key=lambda e: e.get("date", ""),
        reverse=True,
    )
    return open_events + past_events


def _events_page(limit, offset):
    """One page of the open-first listing, sliced at the SQL level.

    Powers the scrollable events feed (``search_by_scroll``): only the visible
    slice is fetched via SQL ``ORDER BY ... LIMIT ? OFFSET ?`` -- never the whole
    275-row table -- so scrolling is what reveals events further down the feed.
    """
    rows = db.execute(
        f"SELECT * FROM [{_EVENTS_TABLE}] ORDER BY {_LISTING_ORDER} LIMIT ? OFFSET ?",
        (limit, offset),
    )
    # Merge this session's overlay edits (e.g. sold-count changes) onto the page.
    # Restricting the match to this page's ids keeps overlay rows from leaking in
    # from other pages, so LIMIT/OFFSET paging stays duplicate-free.
    page_ids = {r.get("id") for r in rows}
    events = db.merge_overlay(
        SITE, "events", rows, match=lambda e: e.get("id") in page_ids
    )
    # The overlay merge can reorder the page; re-apply the open-first grouping so
    # the slice keeps the same authoritative order the SQL produced.
    open_events = sorted(
        (e for e in events if e.get("status") == "on_sale"),
        key=lambda e: (e.get("date", ""), e.get("id", 0)),
    )
    past_events = sorted(
        (e for e in events if e.get("status") != "on_sale"),
        key=lambda e: (e.get("date", ""), e.get("id", 0)),
        reverse=True,
    )
    return open_events + past_events


def _load_tickets():
    return db.query(SITE, "tickets")


def _save_tickets(tickets):
    db.save_collection(SITE, "tickets", tickets)


def _load_orders():
    return db.query(SITE, "orders")


def _save_orders(orders):
    db.save_collection(SITE, "orders", orders)


def _load_users():
    return db.query(SITE, "users")


def _get_user(user_id):
    return db.get_item(SITE, "users", user_id)


def _get_current_user():
    return current_user(_get_user)


def _get_browsing_user():
    """Return logged-in user, or fall back to user 1 for browse-only pages."""
    return browsing_user(_get_user, fallback=1)


def _min_price(event):
    """Return the minimum ticket price for an event."""
    prices = [t["price"] for t in event.get("ticket_types", []) if t["price"] > 0]
    return min(prices) if prices else 0.0


def _max_price(event):
    """Return the maximum ticket price for an event."""
    prices = [t["price"] for t in event.get("ticket_types", [])]
    return max(prices) if prices else 0.0


def _total_available(event):
    """Total remaining tickets across all types."""
    return sum(
        max(0, t["available"] - t["sold"])
        for t in event.get("ticket_types", [])
        if t["available"] > 0
    )


def _event_location(event):
    """Extract city from address for filtering."""
    addr = event.get("address", "")
    parts = [p.strip() for p in addr.split(",")]
    if len(parts) >= 2:
        return parts[-2]  # city
    return addr


# ---------------------------------------------------------------------------
# Reserved-seating support
# ---------------------------------------------------------------------------
# Indoor fixed-seat venues get an interactive seat map (section -> row -> seat).
# Everything else -- outdoor amphitheater lawn, festival grounds, marina,
# brewery, library classroom, community center, convention hall -- is general
# admission (open / standing) and stays quantity-only, no seat picker.
_RESERVED_VENUE_KEYWORDS = ("theater", "theatre", "ballroom", "playhouse",
                            "opera house", "auditorium")
# "amphitheater"/"amphitheatre" contain the substring "theater" but are open
# lawn seating, so they are explicitly general admission, never reserved.
_GA_VENUE_KEYWORDS = ("amphitheater", "amphitheatre")

# Skip I and O in row letters (they read like 1 / 0 on a seat chart).
_ROW_LETTERS = "ABCDEFGHJKLMNPQRSTUVWX"
_SEATS_PER_ROW = 16
_MAX_ROWS = 14


def _is_reserved_seating(event):
    """True when the event's venue has assigned seats (rows + seat numbers).

    Deterministic from the venue name -- no schema/date changes needed. Used to
    decide whether checkout shows a seat map (reserved) or stays quantity-only
    (general admission).
    """
    venue = (event.get("venue") or "").lower()
    if any(k in venue for k in _GA_VENUE_KEYWORDS):
        return False
    return any(k in venue for k in _RESERVED_VENUE_KEYWORDS)


def _section_layout(tt):
    """(rows, seats_per_row) for one ticket-type 'section', sized to availability."""
    available = tt.get("available") or 0
    if available <= 0:
        available = _SEATS_PER_ROW
    rows = max(1, min(_MAX_ROWS, -(-available // _SEATS_PER_ROW)))  # ceil division
    return rows, _SEATS_PER_ROW


def _seat_label(section, row_letter, num):
    return f"{section} {row_letter}{num}"


def _seat_sold_deterministic(event_id, label, sold, capacity):
    """Deterministic 'already sold' flag for a seat.

    Same result on every load (hash of event id + seat label), with the taken
    density scaled by the section's sold-through ratio so busier sections render
    fuller. This is what makes some seats blocked without touching the DB.
    """
    if capacity <= 0:
        return False
    h = int(hashlib.md5(f"{event_id}|{label}".encode()).hexdigest(), 16)
    ratio = min(0.9, sold / capacity)
    return (h % 1000) / 1000.0 < ratio


def _seat_map(event, booked=None):
    """Section/row/seat structure for a reserved-seating event's seat picker.

    ``booked`` is a set of seat labels already persisted on tickets for this
    event (base + this session's overlay); they render as taken on top of the
    deterministic sold seats.
    """
    booked = booked or set()
    sections = []
    for tt in event.get("ticket_types", []):
        rows_n, per_row = _section_layout(tt)
        capacity = rows_n * per_row
        sold = tt.get("sold") or 0
        section = tt["type"]
        rows = []
        for ri in range(rows_n):
            letter = _ROW_LETTERS[ri]
            seats = []
            for num in range(1, per_row + 1):
                label = _seat_label(section, letter, num)
                taken = (label in booked
                         or _seat_sold_deterministic(event["id"], label, sold, capacity))
                seats.append({"label": label, "num": num, "taken": taken})
            rows.append({"letter": letter, "seats": seats})
        sections.append({"type": section, "price": tt.get("price", 0.0), "rows": rows})
    return sections


def _valid_seats(event):
    """Map of valid seat label -> section (ticket_type) for the event."""
    idx = {}
    for tt in event.get("ticket_types", []):
        rows_n, per_row = _section_layout(tt)
        for ri in range(rows_n):
            letter = _ROW_LETTERS[ri]
            for num in range(1, per_row + 1):
                idx[_seat_label(tt["type"], letter, num)] = tt["type"]
    return idx


def _booked_seats(event_id):
    """Seat labels already taken by existing tickets (overlay-aware, SQL-filtered)."""
    rows = db.query(SITE, "tickets", where={"event_id": event_id})
    return {t.get("seat") for t in rows if t.get("seat")}


def _validate_seat_selection(event, ticket_type, seats, booked):
    """Return an error string if the seat selection is invalid, else None.

    Rejects unknown seats, seats outside the chosen section, duplicates, and
    seats that are already taken (already booked OR deterministically sold).
    """
    valid = _valid_seats(event)
    tt_by_type = {t["type"]: t for t in event.get("ticket_types", [])}
    seen = set()
    for label in seats:
        section = valid.get(label)
        if section is None:
            return f"Seat '{label}' does not exist for this event"
        if section != ticket_type:
            return f"Seat '{label}' is not in the '{ticket_type}' section"
        if label in seen:
            return f"Seat '{label}' was selected more than once"
        seen.add(label)
        if label in booked:
            return f"Seat '{label}' is already taken"
        tt = tt_by_type[section]
        rows_n, per_row = _section_layout(tt)
        if _seat_sold_deterministic(event["id"], label, tt.get("sold") or 0,
                                    rows_n * per_row):
            return f"Seat '{label}' is already taken"
    return None


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    # search_by_scroll: render only the first page of the feed; the rest is
    # appended as the user scrolls (see /api/events/feed). Categories and date
    # bounds are computed with SQL aggregates so we never load all 275 rows.
    events = _events_page(FEED_PAGE_SIZE, 0)
    total = db.count(SITE, "events")
    cat_rows = db.execute(
        f"SELECT DISTINCT [category] FROM [{_EVENTS_TABLE}] "
        "WHERE [category] IS NOT NULL AND [category] != '' ORDER BY [category]"
    )
    categories = [r["category"] for r in cat_rows]
    user, logged_in = _get_browsing_user()
    # Bound the date-range pickers to the actual event dates so the calendar
    # opens within the data and cannot drift to an empty month once the real
    # "today" moves past the last event in this static dataset.
    drow = db.execute(
        f"SELECT MIN([date]) AS mn, MAX([date]) AS mx FROM [{_EVENTS_TABLE}] "
        "WHERE [date] IS NOT NULL AND [date] != ''",
        fetch="one",
    )
    date_min = (drow or {}).get("mn") or ""
    date_max = (drow or {}).get("mx") or ""
    return render_template(
        "ticketing-events/index.html",
        events=events,
        total=total,
        page_size=FEED_PAGE_SIZE,
        categories=categories,
        user=user,
        logged_in=logged_in,
        date_min=date_min,
        date_max=date_max,
    )


@blueprint.route("/search")
def search_page():
    """search_by_query: search results page for events."""
    q = request.args.get("q", "").strip()
    events = _load_events()
    categories = sorted(set(e["category"] for e in events))
    user, logged_in = _get_browsing_user()

    results = []
    if q:
        ql = q.lower()
        results = [
            e for e in events
            if ql in e["name"].lower()
            or ql in e.get("description", "").lower()
            or ql in e.get("venue", "").lower()
            or ql in e.get("organizer", "").lower()
            or any(ql in t.lower() for t in e.get("tags", []))
        ]
        results.sort(key=lambda e: e["date"])

    return render_template(
        "ticketing-events/search.html",
        events=results,
        categories=categories,
        q=q,
        user=user,
        logged_in=logged_in,
    )


@blueprint.route("/event/<int:event_id>")
def event_detail(event_id):
    events = _load_events()
    event = next((e for e in events if e["id"] == event_id), None)
    if not event:
        abort(404)
    user, logged_in = _get_browsing_user()
    return render_template(
        "ticketing-events/detail.html",
        event=event,
        user=user,
        logged_in=logged_in,
        reserved=_is_reserved_seating(event),
    )


@blueprint.route("/my-tickets")
def my_tickets():
    user, logged_in = _get_browsing_user()
    orders = _load_orders()
    tickets = _load_tickets()
    events = _load_events()

    user_orders = [o for o in orders if o["user_id"] == user["id"]]
    user_tickets = [t for t in tickets if t["user_id"] == user["id"]]

    events_map = {e["id"]: e for e in events}

    return render_template(
        "ticketing-events/my_tickets.html",
        user=user,
        logged_in=logged_in,
        orders=user_orders,
        tickets=user_tickets,
        events_map=events_map,
    )


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("ticketing-events/login.html", error=None)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user:
        return render_template(
            "ticketing-events/login.html",
            error="Invalid username or password",
        )
    stored_pw = user.get("password", "password")
    if password and password != stored_pw:
        return render_template("ticketing-events/login.html", error="Invalid password")
    session["user_id"] = user["id"]
    return redirect(url_for("ticketing-events.index"))


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("ticketing-events.index"))


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@blueprint.route("/api/events")
def api_events():
    events = _load_events()

    # -- Filters --
    category = request.args.get("category", "").strip()
    if category:
        events = [e for e in events if e["category"].lower() == category.lower()]

    status = request.args.get("status", "").strip()
    if status:
        events = [e for e in events if e["status"].lower() == status.lower()]

    date_from = request.args.get("date_from", "").strip()
    if date_from:
        events = [e for e in events if e["date"] >= date_from]

    date_to = request.args.get("date_to", "").strip()
    if date_to:
        events = [e for e in events if e["date"] <= date_to]

    price_min = request.args.get("price_min", type=float)
    if price_min is not None:
        events = [e for e in events if _max_price(e) >= price_min]

    price_max = request.args.get("price_max", type=float)
    if price_max is not None:
        events = [e for e in events if _min_price(e) <= price_max]

    location = request.args.get("location", "").strip()
    if location:
        events = [
            e for e in events
            if location.lower() in e.get("address", "").lower()
            or location.lower() in e.get("venue", "").lower()
        ]

    tag = request.args.get("tag", "").strip()
    if tag:
        events = [e for e in events if tag.lower() in [t.lower() for t in e.get("tags", [])]]

    age = request.args.get("age_restriction", "").strip()
    if age:
        events = [e for e in events if e.get("age_restriction", "").lower() == age.lower()]

    q = request.args.get("q", "").strip()
    if q:
        ql = q.lower()
        events = [
            e for e in events
            if ql in e["name"].lower()
            or ql in e.get("description", "").lower()
            or ql in e.get("venue", "").lower()
            or ql in e.get("organizer", "").lower()
            or any(ql in t.lower() for t in e.get("tags", []))
        ]

    # -- Sort --
    sort_by = request.args.get("sort", "").strip()
    if sort_by == "date":
        events.sort(key=lambda e: e["date"])
    elif sort_by == "date_desc":
        events.sort(key=lambda e: e["date"], reverse=True)
    elif sort_by == "price":
        events.sort(key=lambda e: _min_price(e))
    elif sort_by == "price_desc":
        events.sort(key=lambda e: _min_price(e), reverse=True)
    elif sort_by == "name":
        events.sort(key=lambda e: e["name"].lower())
    elif sort_by == "name_desc":
        events.sort(key=lambda e: e["name"].lower(), reverse=True)
    else:
        # Default: open-for-registration events first (soonest date first),
        # then past/completed events (most recent first) at the bottom.
        open_part = sorted(
            (e for e in events if e.get("status") == "on_sale"),
            key=lambda e: e["date"],
        )
        past_part = sorted(
            (e for e in events if e.get("status") != "on_sale"),
            key=lambda e: e["date"], reverse=True,
        )
        events = open_part + past_part

    # -- Pagination --
    limit = request.args.get("limit", type=int)
    offset = request.args.get("offset", 0, type=int)
    total = len(events)
    if offset:
        events = events[offset:]
    if limit:
        events = events[:limit]

    return jsonify({"total": total, "events": events})


@blueprint.route("/api/events/feed")
def api_events_feed():
    """search_by_scroll: next page of the open-first events feed.

    The listing has 275 events (open-for-registration first, past events after).
    The frontend renders one page, then appends subsequent pages as the user
    scrolls toward the bottom -- so reaching a far-down event genuinely requires
    scrolling. Paging is done purely in SQL via ``LIMIT``/``OFFSET`` (see
    ``_events_page``); only the requested slice is ever loaded.
    """
    limit = request.args.get("limit", FEED_PAGE_SIZE, type=int)
    offset = request.args.get("offset", 0, type=int)
    limit = max(1, min(limit, 50))
    offset = max(0, offset)

    total = db.count(SITE, "events")
    events = _events_page(limit, offset)
    return jsonify({
        "total": total,
        "offset": offset,
        "limit": limit,
        "events": events,
        "has_more": offset + len(events) < total,
    })


@blueprint.route("/api/events/<int:event_id>")
def api_event(event_id):
    events = _load_events()
    event = next((e for e in events if e["id"] == event_id), None)
    if not event:
        abort(404)
    return jsonify(event)


@blueprint.route("/api/tickets")
def api_tickets():
    tickets = _load_tickets()

    user_id = request.args.get("user_id", type=int)
    if user_id is not None:
        tickets = [t for t in tickets if t["user_id"] == user_id]

    event_id = request.args.get("event_id", type=int)
    if event_id is not None:
        tickets = [t for t in tickets if t["event_id"] == event_id]

    status = request.args.get("status", "").strip()
    if status:
        tickets = [t for t in tickets if t["status"].lower() == status.lower()]

    return jsonify(tickets)


@blueprint.route("/api/orders")
def api_orders_list():
    orders = _load_orders()

    user_id = request.args.get("user_id", type=int)
    if user_id is not None:
        orders = [o for o in orders if o["user_id"] == user_id]

    event_id = request.args.get("event_id", type=int)
    if event_id is not None:
        orders = [o for o in orders if o["event_id"] == event_id]

    status = request.args.get("status", "").strip()
    if status:
        orders = [o for o in orders if o["status"].lower() == status.lower()]

    return jsonify(orders)


@blueprint.route("/api/orders", methods=["POST"])
def api_orders_create():
    """Create a new order (purchase tickets).

    Expected JSON body:
        {
            "user_id": int,
            "event_id": int,
            "ticket_type": str,
            "quantity": int,
            "payment_method": {"type": "credit_card", "last_four": "1234", "brand": "Visa"}  (optional)
        }
    """
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    event_id = data.get("event_id")
    ticket_type = data.get("ticket_type", "").strip()
    quantity = data.get("quantity", 1)

    if not user_id or not event_id or not ticket_type:
        return jsonify({"error": "user_id, event_id, and ticket_type are required"}), 400
    if quantity < 1:
        return jsonify({"error": "quantity must be at least 1"}), 400

    # Validate user
    user = _get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Validate event & ticket type
    events = _load_events()
    event = next((e for e in events if e["id"] == event_id), None)
    if not event:
        return jsonify({"error": "Event not found"}), 404

    if event["status"] not in ("on_sale",):
        return jsonify({"error": "Event is not currently on sale"}), 400

    tt = next((t for t in event["ticket_types"] if t["type"] == ticket_type), None)
    if not tt:
        return jsonify({"error": f"Ticket type '{ticket_type}' not found for this event"}), 400

    # Reserved seating: specific seats must be chosen; they define the quantity.
    reserved = _is_reserved_seating(event)
    selected_seats = []
    if reserved:
        selected_seats = [s.strip() for s in (data.get("seats") or []) if s and s.strip()]
        if not selected_seats:
            return jsonify({
                "error": "This event has reserved seating -- select seat(s) via 'seats'"
            }), 400
        err = _validate_seat_selection(event, ticket_type, selected_seats,
                                       _booked_seats(event_id))
        if err:
            return jsonify({"error": err}), 400
        quantity = len(selected_seats)

    remaining = tt["available"] - tt["sold"]
    if tt["available"] > 0 and remaining < quantity:
        return jsonify({
            "error": f"Only {remaining} tickets remaining for '{ticket_type}'"
        }), 400

    # Calculate pricing
    unit_price = tt["price"]
    subtotal = round(unit_price * quantity, 2)
    fees = round(subtotal * 0.12, 2) if subtotal > 0 else 0.0
    total = round(subtotal + fees, 2)

    # Generate IDs
    orders = _load_orders()
    tickets = _load_tickets()

    existing_order_nums = []
    for o in orders:
        try:
            existing_order_nums.append(int(o["id"].split("-")[1]))
        except (IndexError, ValueError):
            pass
    next_order_num = max(existing_order_nums, default=0) + 1
    order_id = f"ORD-{next_order_num:03d}"

    existing_ticket_nums = []
    for t in tickets:
        try:
            existing_ticket_nums.append(int(t["id"].split("-")[1]))
        except (IndexError, ValueError):
            pass
    next_ticket_num = max(existing_ticket_nums, default=0) + 1

    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    new_ticket_ids = []
    new_tickets = []
    for i in range(quantity):
        tid = f"TKT-{next_ticket_num + i:03d}"
        new_ticket_ids.append(tid)
        new_tickets.append({
            "id": tid,
            "order_id": order_id,
            "event_id": event_id,
            "user_id": user_id,
            "ticket_type": ticket_type,
            "price": unit_price,
            "status": "active",
            "barcode": f"LP{event_id:04d}{next_ticket_num + i:05d}",
            "seat": selected_seats[i] if reserved else None,
            "purchased_at": now,
            "checked_in_at": None,
        })

    # Payment method
    payment_method = data.get("payment_method")
    if not payment_method and total > 0:
        pm_list = user.get("payment_methods", [])
        default_pm = next((p for p in pm_list if p.get("is_default")), None)
        if default_pm:
            payment_method = {
                "type": default_pm["type"],
                "last_four": default_pm["last_four"],
                "brand": default_pm["brand"],
            }

    new_order = {
        "id": order_id,
        "user_id": user_id,
        "event_id": event_id,
        "event_name": event["name"],
        "tickets": new_ticket_ids,
        "quantity": quantity,
        "subtotal": subtotal,
        "fees": fees,
        "total": total,
        "payment_method": payment_method,
        "status": "confirmed",
        "ordered_at": now,
        "confirmation_email_sent": True,
        "refund_amount": 0,
    }

    # Update sold counts on event
    tt["sold"] += quantity

    # Save everything
    orders.append(new_order)
    tickets.extend(new_tickets)
    _save_orders(orders)
    _save_tickets(tickets)
    _save_events(events)

    # Bridge: notify banking/email of ticket purchase + calendar booking
    try:
        from app.bridges import on_purchase, on_booking
        on_purchase(user_id=user_id, merchant="Lakeport Events",
                    amount=total, item_description=event["name"],
                    order_id=order_id)
        on_booking(user_id=user_id, title=event["name"],
                   start=f"{event['date']}T{event.get('time', '19:00')}",
                   location=event.get("venue", ""),
                   service_name="Lakeport Events",
                   confirmation_id=order_id)
    except Exception:
        pass  # bridge failure should never block the main flow

    return jsonify(new_order), 201


@blueprint.route("/api/orders/<order_id>")
def api_order_detail(order_id):
    orders = _load_orders()
    order = next((o for o in orders if o["id"] == order_id), None)
    if not order:
        abort(404)
    return jsonify(order)


@blueprint.route("/api/orders/<order_id>/cancel", methods=["POST"])
def api_order_cancel(order_id):
    """Cancel an order and refund tickets.

    Only orders with status 'confirmed' can be cancelled.
    """
    orders = _load_orders()
    order = next((o for o in orders if o["id"] == order_id), None)
    if not order:
        return jsonify({"error": "Order not found"}), 404

    if order["status"] != "confirmed":
        return jsonify({
            "error": f"Cannot cancel order with status '{order['status']}'. Only confirmed orders can be cancelled."
        }), 400

    # Cancel the order
    order["status"] = "cancelled"
    order["refund_amount"] = order["total"]

    # Cancel associated tickets
    tickets = _load_tickets()
    for t in tickets:
        if t["order_id"] == order_id:
            t["status"] = "cancelled"

    # Restore sold counts on the event
    events = _load_events()
    event = next((e for e in events if e["id"] == order["event_id"]), None)
    if event:
        for tt in event["ticket_types"]:
            cancelled_of_type = sum(
                1 for t in tickets
                if t["order_id"] == order_id and t["ticket_type"] == tt["type"]
                and t["status"] == "cancelled"
            )
            tt["sold"] = max(0, tt["sold"] - cancelled_of_type)
        _save_events(events)

    _save_orders(orders)
    _save_tickets(tickets)

    return jsonify({
        "status": "cancelled",
        "order_id": order_id,
        "refund_amount": order["refund_amount"],
    })


@blueprint.route("/api/stats")
def api_stats():
    events = _load_events()
    orders = _load_orders()
    tickets = _load_tickets()

    user_id = request.args.get("user_id", type=int)

    if user_id is not None:
        user_orders = [o for o in orders if o["user_id"] == user_id]
        user_tickets = [t for t in tickets if t["user_id"] == user_id]
    else:
        user_orders = orders
        user_tickets = tickets

    total_spent = sum(o["total"] for o in user_orders if o["status"] != "cancelled")
    total_orders = len(user_orders)
    total_tickets = len(user_tickets)
    active_tickets = sum(1 for t in user_tickets if t["status"] == "active")
    used_tickets = sum(1 for t in user_tickets if t["status"] == "used")

    total_events = len(events)
    on_sale = sum(1 for e in events if e["status"] == "on_sale")
    completed = sum(1 for e in events if e["status"] == "completed")

    categories = {}
    for e in events:
        cat = e["category"]
        categories[cat] = categories.get(cat, 0) + 1

    return jsonify({
        "total_events": total_events,
        "events_on_sale": on_sale,
        "events_completed": completed,
        "total_orders": total_orders,
        "total_tickets": total_tickets,
        "active_tickets": active_tickets,
        "used_tickets": used_tickets,
        "total_spent": round(total_spent, 2),
        "categories": categories,
    })


@blueprint.route("/api/users")
def api_users():
    users = _load_users()
    # Strip sensitive fields
    safe = []
    for u in users:
        safe.append({k: v for k, v in u.items()})
    return jsonify(safe)


@blueprint.route("/api/users/<int:user_id>")
def api_user(user_id):
    user = _get_user(user_id)
    if not user:
        abort(404)
    return jsonify(user)


@blueprint.route("/api/login", methods=["POST"])
def api_login():
    """authenticate_by_form: log in a user."""
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user:
        return jsonify({"error": "Invalid credentials"}), 401
    session["user_id"] = user["id"]
    return jsonify({
        "user_id": user["id"],
        "username": user["username"],
        "display_name": user["display_name"],
    })


@blueprint.route("/api/register", methods=["POST"])
def api_register():
    """register_by_form: register a new user account."""
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    display_name = data.get("display_name", "").strip()
    email = data.get("email", "").strip()

    if not username or not display_name or not email:
        return jsonify({"error": "username, display_name, and email are required"}), 400

    users = _load_users()
    if any(u["username"] == username for u in users):
        return jsonify({"error": "Username already exists"}), 409

    new_id = max((u["id"] for u in users), default=0) + 1
    new_user = {
        "id": new_id,
        "root_user_id": new_id + 100,
        "username": username,
        "display_name": display_name,
        "email": email,
        "phone": data.get("phone", ""),
        "joined_date": datetime.utcnow().strftime("%Y-%m-%d"),
        "location": data.get("location", "Lakeport, WA"),
        "payment_methods": [],
        "notification_preferences": {
            "email": True,
            "sms": False,
            "push": False,
        },
    }
    users.append(new_user)
    db.save_collection(SITE, "users", users)
    emit("signup", user_id=new_id, site_name="ticketing-events",
         username=username, password="", email=email)
    session["user_id"] = new_id
    return jsonify({"user_id": new_id, "username": username, "display_name": display_name}), 201


@blueprint.route("/register", methods=["GET"])
def register_page():
    """register_by_form: registration page."""
    return render_template("ticketing-events/register.html", error=None)


@blueprint.route("/register", methods=["POST"])
def register_submit():
    """register_by_form: process registration form."""
    username = request.form.get("username", "").strip()
    display_name = request.form.get("display_name", "").strip()
    email = request.form.get("email", "").strip()

    if not username or not display_name or not email:
        return render_template("ticketing-events/register.html",
                               error="All fields are required")

    users = _load_users()
    if any(u["username"] == username for u in users):
        return render_template("ticketing-events/register.html",
                               error="Username already exists")

    new_id = max((u["id"] for u in users), default=0) + 1
    new_user = {
        "id": new_id,
        "root_user_id": new_id + 100,
        "username": username,
        "display_name": display_name,
        "email": email,
        "phone": request.form.get("phone", ""),
        "joined_date": datetime.utcnow().strftime("%Y-%m-%d"),
        "location": "Lakeport, WA",
        "payment_methods": [],
        "notification_preferences": {"email": True, "sms": False, "push": False},
    }
    users.append(new_user)
    db.save_collection(SITE, "users", users)
    emit("signup", user_id=new_id, site_name="ticketing-events",
         username=username, password="", email=email)
    session["user_id"] = new_id
    return redirect(url_for("ticketing-events.index"))


# ---------------------------------------------------------------------------
# Wishlist / save_by_toggle
# ---------------------------------------------------------------------------

def _load_wishlist():
    return db.query(SITE, "wishlist")


def _save_wishlist(data):
    db.save_collection(SITE, "wishlist", data)


@blueprint.route("/api/wishlist", methods=["GET"])
def api_wishlist():
    """save_by_toggle: get user's wishlist."""
    wishlist = _load_wishlist()
    user_id = request.args.get("user_id", type=int)
    if user_id is not None:
        wishlist = [w for w in wishlist if w["user_id"] == user_id]
    return jsonify(wishlist)


@blueprint.route("/api/wishlist", methods=["POST"])
def api_wishlist_toggle():
    """save_by_toggle: toggle an event in user's wishlist."""
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    event_id = data.get("event_id")
    if not user_id or not event_id:
        return jsonify({"error": "user_id and event_id are required"}), 400

    wishlist = _load_wishlist()
    existing = next((w for w in wishlist
                     if w["user_id"] == user_id and w["event_id"] == event_id), None)
    if existing:
        wishlist = [w for w in wishlist if w != existing]
        _save_wishlist(wishlist)
        return jsonify({"action": "removed", "event_id": event_id})

    events = _load_events()
    event = next((e for e in events if e["id"] == event_id), None)
    if not event:
        return jsonify({"error": "Event not found"}), 404

    new_entry = {
        "user_id": user_id,
        "event_id": event_id,
        "event_name": event["name"],
        "added_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    wishlist.append(new_entry)
    _save_wishlist(wishlist)
    return jsonify({"action": "saved", "event_id": event_id}), 201


# ---------------------------------------------------------------------------
# Promo codes / redeem_by_code
# ---------------------------------------------------------------------------

PROMO_CODES = {
    "SUMMER10": {"discount_pct": 10, "description": "10% off summer events"},
    "WELCOME20": {"discount_pct": 20, "description": "20% off for new users"},
    "VIP50": {"discount_pct": 50, "description": "50% off VIP tickets"},
    "PRODUCERSFRIEND": {"discount_pct": 15, "description": "15% off — producer's friends & family"},
}


@blueprint.route("/api/promo/validate", methods=["POST"])
def api_validate_promo():
    """redeem_by_code: validate and apply a promo code."""
    data = request.get_json(silent=True) or {}
    code = data.get("code", "").strip().upper()
    if not code:
        return jsonify({"error": "code is required"}), 400

    promo = PROMO_CODES.get(code)
    if not promo:
        return jsonify({"error": "Invalid promo code", "valid": False}), 404

    return jsonify({
        "valid": True,
        "code": code,
        "discount_pct": promo["discount_pct"],
        "description": promo["description"],
    })


# ---------------------------------------------------------------------------
# Checkout / book_by_form / checkout_by_form
# ---------------------------------------------------------------------------

@blueprint.route("/checkout/<int:event_id>", methods=["GET"])
def checkout_page(event_id):
    """checkout_by_form / book_by_form: checkout page for event."""
    events = _load_events()
    event = next((e for e in events if e["id"] == event_id), None)
    if not event:
        abort(404)
    user, logged_in = _get_browsing_user()
    reserved = _is_reserved_seating(event)
    seat_map = _seat_map(event, _booked_seats(event_id)) if reserved else None
    return render_template(
        "ticketing-events/checkout.html",
        event=event,
        user=user,
        logged_in=logged_in,
        reserved=reserved,
        seat_map=seat_map,
        error=None,
    )


@blueprint.route("/checkout/<int:event_id>", methods=["POST"])
def checkout_submit(event_id):
    """checkout_by_form / book_by_form: process checkout form submission."""
    user = _get_current_user()
    if not user:
        return redirect(url_for("ticketing-events.login_page"))

    ticket_type = request.form.get("ticket_type", "").strip()
    quantity = int(request.form.get("quantity", 1))
    promo_code = request.form.get("promo_code", "").strip().upper()

    # Use the API order creation logic
    events = _load_events()
    event = next((e for e in events if e["id"] == event_id), None)
    if not event or event["status"] != "on_sale":
        abort(400)

    reserved = _is_reserved_seating(event)
    selected_seats = []

    def _reshow(error):
        """Re-render the checkout form with an error (reserved-seat failures)."""
        seat_map = _seat_map(event, _booked_seats(event_id)) if reserved else None
        return render_template(
            "ticketing-events/checkout.html", event=event, user=user,
            logged_in=True, reserved=reserved, seat_map=seat_map, error=error,
        ), 400

    if reserved:
        # Reserved seating: the chosen seats define the ticket type and quantity.
        raw = request.form.get("seats", "")
        selected_seats = [s.strip() for s in raw.split(",") if s.strip()]
        if not selected_seats:
            return _reshow("Please select at least one seat.")
        booked = _booked_seats(event_id)
        err = _validate_seat_selection(event, ticket_type, selected_seats, booked)
        if err:
            return _reshow(err)
        quantity = len(selected_seats)

    tt = next((t for t in event["ticket_types"] if t["type"] == ticket_type), None)
    if not tt:
        abort(400)

    remaining = tt["available"] - tt["sold"]
    if tt["available"] > 0 and remaining < quantity:
        if reserved:
            return _reshow(f"Only {remaining} tickets remaining for '{ticket_type}'.")
        abort(400)

    unit_price = tt["price"]
    subtotal = round(unit_price * quantity, 2)

    # Apply promo
    discount_pct = 0
    if promo_code and promo_code in PROMO_CODES:
        discount_pct = PROMO_CODES[promo_code]["discount_pct"]
    discount = round(subtotal * discount_pct / 100, 2)
    subtotal_after_discount = round(subtotal - discount, 2)
    fees = round(subtotal_after_discount * 0.12, 2) if subtotal_after_discount > 0 else 0.0
    total = round(subtotal_after_discount + fees, 2)

    orders = _load_orders()
    tickets = _load_tickets()

    existing_order_nums = []
    for o in orders:
        try:
            existing_order_nums.append(int(o["id"].split("-")[1]))
        except (IndexError, ValueError):
            pass
    next_order_num = max(existing_order_nums, default=0) + 1
    order_id = f"ORD-{next_order_num:03d}"

    existing_ticket_nums = []
    for t in tickets:
        try:
            existing_ticket_nums.append(int(t["id"].split("-")[1]))
        except (IndexError, ValueError):
            pass
    next_ticket_num = max(existing_ticket_nums, default=0) + 1

    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    new_ticket_ids = []
    new_tickets = []
    for i in range(quantity):
        tid = f"TKT-{next_ticket_num + i:03d}"
        new_ticket_ids.append(tid)
        new_tickets.append({
            "id": tid, "order_id": order_id, "event_id": event_id,
            "user_id": user["id"], "ticket_type": ticket_type,
            "price": unit_price, "status": "active",
            "barcode": f"LP{event_id:04d}{next_ticket_num + i:05d}",
            "seat": selected_seats[i] if reserved else None,
            "purchased_at": now, "checked_in_at": None,
        })

    pm_list = user.get("payment_methods", [])
    default_pm = next((p for p in pm_list if p.get("is_default")), None)
    payment_method = None
    if default_pm:
        payment_method = {
            "type": default_pm["type"],
            "last_four": default_pm["last_four"],
            "brand": default_pm["brand"],
        }

    new_order = {
        "id": order_id, "user_id": user["id"], "event_id": event_id,
        "event_name": event["name"], "tickets": new_ticket_ids,
        "quantity": quantity, "subtotal": subtotal, "fees": fees,
        "total": total, "payment_method": payment_method,
        "status": "confirmed", "ordered_at": now,
        "confirmation_email_sent": True, "refund_amount": 0,
    }
    if discount > 0:
        new_order["promo_code"] = promo_code
        new_order["discount"] = discount

    tt["sold"] += quantity
    orders.append(new_order)
    tickets.extend(new_tickets)
    _save_orders(orders)
    _save_tickets(tickets)
    _save_events(events)

    # Bridge: notify banking/email of ticket purchase + calendar booking
    try:
        from app.bridges import on_purchase, on_booking
        on_purchase(user_id=user["id"], merchant="Lakeport Events",
                    amount=total, item_description=event["name"],
                    order_id=order_id)
        on_booking(user_id=user["id"], title=event["name"],
                   start=f"{event['date']}T{event.get('time', '19:00')}",
                   location=event.get("venue", ""),
                   service_name="Lakeport Events",
                   confirmation_id=order_id)
    except Exception:
        pass  # bridge failure should never block the main flow

    return redirect(url_for("ticketing-events.my_tickets"))


# ---------------------------------------------------------------------------
# Cancel / cancel_by_form
# ---------------------------------------------------------------------------

@blueprint.route("/cancel/<order_id>", methods=["GET"])
def cancel_page(order_id):
    """cancel_by_form: show cancel confirmation page."""
    orders = _load_orders()
    order = next((o for o in orders if o["id"] == order_id), None)
    if not order:
        abort(404)
    user, logged_in = _get_browsing_user()
    return render_template(
        "ticketing-events/cancel.html",
        order=order,
        user=user,
        logged_in=logged_in,
    )


@blueprint.route("/cancel/<order_id>", methods=["POST"])
def cancel_submit(order_id):
    """cancel_by_form: process cancel form submission."""
    reason = request.form.get("reason", "").strip()
    orders = _load_orders()
    order = next((o for o in orders if o["id"] == order_id), None)
    if not order:
        abort(404)
    if order["status"] != "confirmed":
        abort(400)

    order["status"] = "cancelled"
    order["refund_amount"] = order["total"]
    if reason:
        order["cancel_reason"] = reason

    tickets = _load_tickets()
    for t in tickets:
        if t["order_id"] == order_id:
            t["status"] = "cancelled"

    events = _load_events()
    event = next((e for e in events if e["id"] == order["event_id"]), None)
    if event:
        for etype in event["ticket_types"]:
            cancelled_of_type = sum(
                1 for t in tickets
                if t["order_id"] == order_id and t["ticket_type"] == etype["type"]
                and t["status"] == "cancelled"
            )
            etype["sold"] = max(0, etype["sold"] - cancelled_of_type)
        _save_events(events)

    _save_orders(orders)
    _save_tickets(tickets)
    return redirect(url_for("ticketing-events.my_tickets"))


# ---------------------------------------------------------------------------
# Compare / compare_from_table / extract_from_table
# ---------------------------------------------------------------------------

@blueprint.route("/compare")
def compare_page():
    """compare_from_table / extract_from_table: compare events side by side."""
    ids_str = request.args.get("ids", "")
    events = _load_events()
    selected = []
    if ids_str:
        ids = [int(x) for x in ids_str.split(",") if x.strip().isdigit()]
        selected = [e for e in events if e["id"] in ids]
    user, logged_in = _get_browsing_user()
    return render_template(
        "ticketing-events/compare.html",
        events=events,
        selected=selected,
        user=user,
        logged_in=logged_in,
    )


@blueprint.route("/api/compare")
def api_compare():
    """compare_from_table / extract_from_table: compare events via API."""
    ids_str = request.args.get("ids", "")
    ids = [int(x) for x in ids_str.split(",") if x.strip().isdigit()]
    events = _load_events()
    selected = [e for e in events if e["id"] in ids]
    return jsonify(selected)


# ---------------------------------------------------------------------------
# Export / export_by_dropdown
# ---------------------------------------------------------------------------

@blueprint.route("/api/export")
def api_export():
    """export_by_dropdown: export events data as JSON or CSV."""
    fmt = request.args.get("format", "json").lower()
    category = request.args.get("category", "").strip()
    events = _load_events()
    if category:
        events = [e for e in events if e["category"].lower() == category.lower()]

    if fmt == "csv":
        lines = ["id,name,category,venue,date,time,status,min_price,max_price"]
        for e in events:
            name = e["name"].replace('"', '""')
            venue = e.get("venue", "").replace('"', '""')
            lines.append(
                f'{e["id"]},"{name}","{e["category"]}","{venue}",'
                f'{e["date"]},"{e.get("time", "")}",{e["status"]},'
                f'{_min_price(e)},{_max_price(e)}'
            )
        return Response("\n".join(lines), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=events.csv"})
    return jsonify(events)


# ---------------------------------------------------------------------------
# User settings / configure_by_dropdown / configure_by_slider
# ---------------------------------------------------------------------------

@blueprint.route("/settings")
def settings_page():
    """configure_by_dropdown / configure_by_slider: user settings page."""
    user = _get_current_user()
    if not user:
        return redirect(url_for("ticketing-events.login_page"))
    return render_template("ticketing-events/settings.html", user=user)


@blueprint.route("/api/users/<int:user_id>/settings", methods=["PUT"])
def api_user_settings(user_id):
    """configure_by_dropdown / configure_by_slider: update user preferences."""
    data = request.get_json(silent=True) or {}
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)

    prefs = user.get("notification_preferences", {})
    if "email_notifications" in data:
        prefs["email"] = bool(data["email_notifications"])
    if "sms_notifications" in data:
        prefs["sms"] = bool(data["sms_notifications"])
    if "push_notifications" in data:
        prefs["push"] = bool(data["push_notifications"])
    user["notification_preferences"] = prefs

    if "location" in data:
        user["location"] = data["location"]
    if "max_price_alert" in data:
        user["max_price_alert"] = float(data["max_price_alert"])

    db.save_collection(SITE, "users", users)
    return jsonify(user)


@blueprint.route("/settings/update", methods=["POST"])
def settings_submit():
    """configure_by_dropdown: update user settings via form."""
    user = _get_current_user()
    if not user:
        return redirect(url_for("ticketing-events.login_page"))

    users = _load_users()
    u = next((u for u in users if u["id"] == user["id"]), None)
    if not u:
        return redirect(url_for("ticketing-events.login_page"))

    prefs = u.get("notification_preferences", {})
    prefs["email"] = "email_notifications" in request.form
    prefs["sms"] = "sms_notifications" in request.form
    prefs["push"] = "push_notifications" in request.form
    u["notification_preferences"] = prefs

    location = request.form.get("location", "").strip()
    if location:
        u["location"] = location

    max_price = request.form.get("max_price_alert", "").strip()
    if max_price:
        try:
            u["max_price_alert"] = float(max_price)
        except ValueError:
            pass

    db.save_collection(SITE, "users", users)
    return redirect(url_for("ticketing-events.settings_page"))


# ---------------------------------------------------------------------------
# Submit feedback / submit_by_query
# ---------------------------------------------------------------------------

@blueprint.route("/api/feedback", methods=["POST"])
def api_submit_feedback():
    """submit_by_query: submit feedback about an event."""
    data = request.get_json(silent=True) or {}
    event_id = data.get("event_id")
    message = data.get("message", "").strip()
    feedback_type = data.get("type", "general")
    if not event_id or not message:
        return jsonify({"error": "event_id and message are required"}), 400
    return jsonify({
        "status": "submitted",
        "event_id": event_id,
        "type": feedback_type,
        "message": message,
    })


# ---------------------------------------------------------------------------
# Semantic search
# ---------------------------------------------------------------------------

def _semantic_score(query, event):
    """Simple keyword-overlap relevance for semantic search."""
    terms = query.lower().split()
    text = " ".join([
        event["name"], event.get("description", ""), event.get("venue", ""),
        event.get("organizer", ""), event["category"],
        " ".join(event.get("tags", []))
    ]).lower()
    return sum(1 for t in terms if t in text)


@blueprint.route("/api/events/semantic")
def api_semantic_search():
    """search_by_semantic: ranked keyword-overlap search."""
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    events = _load_events()
    scored = [(e, _semantic_score(q, e)) for e in events]
    scored = [(e, s) for e, s in scored if s > 0]
    scored.sort(key=lambda x: -x[1])
    return jsonify([e for e, _ in scored])


# ---------------------------------------------------------------------------
# Select by slider / select by date range
# ---------------------------------------------------------------------------

@blueprint.route("/api/events/by-price-range")
def api_events_by_price_range():
    """select_by_slider: select events within a price range."""
    price_min = request.args.get("price_min", 0, type=float)
    price_max = request.args.get("price_max", 999, type=float)
    events = _load_events()
    filtered = [e for e in events if _min_price(e) >= price_min and _max_price(e) <= price_max]
    filtered.sort(key=lambda e: _min_price(e))
    return jsonify(filtered)


@blueprint.route("/api/events/by-date-range")
def api_events_by_date_range():
    """select_by_date_range: select events within a date range."""
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    events = _load_events()
    if date_from:
        events = [e for e in events if e["date"] >= date_from]
    if date_to:
        events = [e for e in events if e["date"] <= date_to]
    events.sort(key=lambda e: e["date"])
    return jsonify(events)


# ---------------------------------------------------------------------------
# Add to cart / add_by_button (add event to a cart-like queue)
# ---------------------------------------------------------------------------

def _load_cart():
    return db.query(SITE, "cart")


def _save_cart(data):
    db.save_collection(SITE, "cart", data)


@blueprint.route("/api/cart", methods=["GET"])
def api_cart():
    """add_by_button: view user's cart."""
    cart = _load_cart()
    user_id = request.args.get("user_id", type=int)
    if user_id is not None:
        cart = [c for c in cart if c["user_id"] == user_id]
    return jsonify(cart)


@blueprint.route("/api/cart", methods=["POST"])
def api_cart_add():
    """add_by_button: add an item to the cart."""
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    event_id = data.get("event_id")
    ticket_type = data.get("ticket_type", "").strip()
    quantity = data.get("quantity", 1)

    if not user_id or not event_id or not ticket_type:
        return jsonify({"error": "user_id, event_id, and ticket_type required"}), 400

    events = _load_events()
    event = next((e for e in events if e["id"] == event_id), None)
    if not event:
        return jsonify({"error": "Event not found"}), 404

    cart = _load_cart()
    cart_item = {
        "user_id": user_id,
        "event_id": event_id,
        "event_name": event["name"],
        "ticket_type": ticket_type,
        "quantity": quantity,
        "added_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    cart.append(cart_item)
    _save_cart(cart)
    return jsonify({"action": "added", "item": cart_item}), 201


@blueprint.route("/api/cart", methods=["DELETE"])
def api_cart_clear():
    """Clear cart for a user."""
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id required"}), 400
    cart = _load_cart()
    cart = [c for c in cart if c["user_id"] != user_id]
    _save_cart(cart)
    return jsonify({"action": "cleared"})
