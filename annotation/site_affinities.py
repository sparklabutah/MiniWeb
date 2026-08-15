"""Cross-site affinity groups and login configuration for annotation.

Sites that interact via the event bus (app/events.py) form natural groups.
When the prompt generator samples multiple sites, it should prefer sites
from the same affinity group so tasks exercise cross-site flows.

Login config: some sites should start pre-logged-in (user_id=1) to avoid
wasting annotation steps on login when it's not the task's focus.
"""

# ---------------------------------------------------------------------------
# Event flow map (source site -> event -> receiving handlers)
# ---------------------------------------------------------------------------
# purchase:  e-commerce, auctions, books-comics, ticketing -> banking (debit), email (receipt)
# payment:   crowdfunding, tax-filing, flights-hotels, insurance -> banking (debit)
# trade:     brokerage -> banking (debit)
# booking:   flights-hotels, health-portals, remote-calls, ticketing -> calendar-todo (event), email (confirmation)
# signup:    auctions, forums, health-portals, live, qa-knowledge, real-estate, ticketing -> email (welcome), password-managers (credential)
# subscribe: business-company -> email (confirmation)
# inquiry:   business-company -> email (notification)
# file_created: documents, handwritten-notes, spreadsheets, insurance -> cloud-storage (sync), email (notification)
# message:   dating -> instant-messaging

# ---------------------------------------------------------------------------
# Affinity groups — sites that work well together in multi-site tasks
# ---------------------------------------------------------------------------
SITE_AFFINITY_GROUPS = {
    "shopping": {
        "sites": ["e-commerce", "auctions-p2p-marketplaces", "books-comics", "ticketing-events"],
        "support": ["banking", "email"],
        "description": "Purchase flow: buy item -> banking debit + email receipt",
    },
    "travel": {
        "sites": ["flights-hotels", "ticketing-events"],
        "support": ["banking", "email", "calendar-todo"],
        "description": "Booking flow: book travel -> banking debit + calendar event + email confirmation",
    },
    "finance": {
        "sites": ["brokerage", "banking", "insurance-loans"],
        "support": ["email"],
        "description": "Financial flow: trade/pay -> banking debit + email notification",
    },
    "government": {
        "sites": ["agency-portals", "tax-filing-dmv-permits"],
        "support": ["banking", "email"],
        "description": "Government flow: pay taxes/fees -> banking debit + email confirmation",
    },
    "productivity": {
        "sites": ["documents", "spreadsheets-slides", "handwritten-notes-whiteboards"],
        "support": ["cloud-storage-file-transfer", "email"],
        "description": "File flow: create/edit document -> cloud storage sync + email notification",
    },
    "communication": {
        "sites": ["dating", "instant-messaging", "remote-calls", "team-chat-workspace"],
        "support": ["email", "calendar-todo"],
        "description": "Messaging flow: send message -> IM delivery; schedule call -> calendar event",
    },
    "health": {
        "sites": ["health-portals", "health-fitness-tracking"],
        "support": ["calendar-todo", "email"],
        "description": "Health flow: book appointment -> calendar event + email confirmation",
    },
    "registration": {
        "sites": ["forums", "qa-knowledge", "live", "real-estate-buy-rent", "crowdfunding-donations"],
        "support": ["email", "password-managers"],
        "description": "Signup flow: register on site -> welcome email + password manager entry",
    },
    "education": {
        "sites": ["course-sites-classrooms", "conference-review-submission"],
        "support": ["email", "calendar-todo"],
        "description": "Education flow: submit assignment/review -> email notification",
    },
    "navigation": {
        "sites": ["map-services", "transit-directions", "ticketing-events", "rating-review"],
        "support": [],
        "description": "Location flow: find place -> get directions -> check reviews -> buy tickets",
    },
    "media": {
        "sites": ["music", "video", "live", "podcasts-audiobooks"],
        "support": [],
        "description": "Media consumption: browse, play, save, share content",
    },
    "reference": {
        "sites": ["academic-paper-db", "documentation-api-docs", "dictionaries-language-tools", "wikis"],
        "support": [],
        "description": "Research flow: search, read, compare, extract information",
    },
}

# ---------------------------------------------------------------------------
# Sites that should NOT start logged out
# ---------------------------------------------------------------------------
# These sites either don't have login, or are unusable without being logged in
# (e.g., password managers show nothing without a user, IM has no conversations).
# When annotation starts, these get session["user_id"] = 1 automatically.
ALWAYS_LOGGED_IN = [
    "password-managers",       # Shows nothing without login; needed for cross-site credential lookup
    "instant-messaging",       # No conversations visible without a user
    "email",                   # Inbox is per-user; useless without login
    "calendar-todo",           # Events are per-user
    "cloud-storage-file-transfer",  # Files are per-user
    "banking",                 # Account data is per-user
    "brokerage",               # Portfolio is per-user
]

# Sites without login at all (no session["user_id"] in routes.py)
NO_LOGIN_SITES = [
    "business-company",
    "conference-review-submission",
    "university-academic",
]
