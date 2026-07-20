"""Expand ai-chatbots (AI Chat Hub) base data.

The site ships with 18 FAQ / 18 knowledge-base / 12 prompt / 10 conversation /
5 user rows. Adds deterministic (seeded) synthetic data themed to the existing
vocabulary (Meridian Systems products, Lakeport local content):

- ~120 new users (ids 6+, root_user_id 0 like other synthetic-user expansions)
- ~4000 new conversations attached ONLY to users other than id 1 (alex_rivera),
  so the main user's sidebar keeps its 5 curated chats — including the two
  task-protected titles "MeridianFlow API rate limits" and
  "Setting up webhooks in MeridianFlow" (no new title reuses those phrases).
  Messages are embedded as a JSON array in the `messages` column, matching
  the app's convention (routes.py form_chat/api_chat).
- knowledge_base / prompts_library / faq are capped well under 500 rows each
  because /knowledge, /prompts and /faq render unbounded global lists.

Insert-only; inserted ids recorded under data/backups/ for rollback.
Rebuilds the FTS5 indexes of every touched table afterwards.

Usage: ~/.conda/envs/miniweb/bin/python scripts/expand_ai_chatbots_data.py [--dry-run]
"""
import datetime
import json
import random
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "trimmed_miniweb.db"
rng = random.Random(42)

TODAY = datetime.datetime(2026, 7, 18, 12, 0, 0)
EPOCH = datetime.datetime(2025, 6, 1, 6, 0, 0)

# Titles created by annotation tasks must stay unique — never reuse these words.
FORBIDDEN_TITLE_WORDS = ("rate limit", "webhook")

TARGET_USERS = 120
TARGET_CONVS = 4000
TARGET_KB = 430
TARGET_FAQ = 130
TARGET_PROMPTS = 280


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def rand_dt():
    span = int((TODAY - EPOCH).total_seconds())
    return EPOCH + datetime.timedelta(seconds=rng.randint(0, span))


# ---------------------------------------------------------------------------
# Name / entity pools (Lakeport + Meridian vocabulary)
# ---------------------------------------------------------------------------

FIRST = ["Ava", "Ben", "Carla", "Dmitri", "Elena", "Farid", "Grace", "Hugo",
         "Imani", "Jonas", "Keiko", "Liam", "Mara", "Nico", "Olga", "Priya",
         "Quinn", "Rosa", "Sam", "Tara", "Umar", "Vera", "Wes", "Ximena",
         "Yusuf", "Zoe", "Aiden", "Bianca", "Caleb", "Delia", "Emil", "Freya",
         "Gustavo", "Hana", "Ivan", "Jade", "Kofi", "Lena", "Mateo", "Nadia"]
LAST = ["Alvarez", "Brooks", "Castillo", "Dawson", "Egan", "Fischer", "Grant",
        "Huang", "Ivanov", "Jensen", "Kaur", "Lombardi", "Mercer", "Novak",
        "Ochoa", "Petrov", "Quintana", "Reyes", "Sato", "Tran", "Ueda",
        "Vasquez", "Whitfield", "Xu", "Yamada", "Zhou", "Abbott", "Bergman",
        "Calloway", "Duval"]
MAIL = ["gmail.com", "outlook.com", "yahoo.com", "protonmail.com", "fastmail.com"]

PRODUCTS = {
    "MeridianFlow": ["approval chains", "task routing", "the workflow builder",
                     "batch task endpoints", "SLA timers", "conditional branching",
                     "the Slack integration", "workflow templates", "run history",
                     "the audit trail", "parallel execution paths", "form fields"],
    "MeridianVault": ["secret rotation", "the Kubernetes sidecar agent",
                      "the database secrets engine", "threat detection alerts",
                      "the Terraform provider", "access policies",
                      "credential grace periods", "security event streams",
                      "service account auth binding", "the audit log"],
    "MeridianLens": ["natural-language querying", "dashboard widgets",
                     "automated insights", "trend analysis", "usage-based billing",
                     "scheduled reports", "funnel charts", "data source connectors",
                     "anomaly detection", "the query history panel"],
}

LP_PLACES = ["Harborview Trail", "Cedar Ridge Loop", "Lakeport Farmers Market",
             "the Pine Street Arts District", "Driftwood Beach", "Lakeport Marina",
             "the Old Mill Museum", "Summit Overlook", "Willow Creek Park",
             "the Lakeport Botanical Garden", "Eastshore Boardwalk",
             "the Heritage Lighthouse"]
LP_SERVICES = ["parking permits", "library card renewal", "curbside recycling",
               "the LakeLink bus network", "property tax payments",
               "building permits", "pet licensing", "yard waste pickup",
               "utility billing", "voter registration", "pothole reporting",
               "street sweeping schedules"]
LP_FOOD = ["The Copper Kettle", "Lakeside Bistro", "Driftwood Diner",
           "Harbor Roast Coffee", "Pine & Vine Wine Bar", "The Salted Oar",
           "Mesa Verde Cantina", "Golden Wok Express", "Bluebird Bakery",
           "The Rusty Anchor Pub", "Saffron Table", "Milo's Pizzeria",
           "The Green Fork", "Cascadia Chowder House", "Juniper & Sage"]
LP_BIZ = ["Lakeport Cycle Works", "Cascadia Outfitters", "Page & Spine Books",
          "Northlight Yoga Studio", "The Fixit Garage", "Evergreen Pet Supply",
          "Lakeport Tech Repair", "Shoreline Fitness Club", "Bloom & Branch Florist",
          "Cedar Street Barbershop", "Bright Smiles Dental", "Lakeport Music Exchange"]

CODE_TOPICS = ["Python list comprehensions", "async/await in JavaScript",
               "SQL window functions", "Docker multi-stage builds",
               "Kubernetes liveness probes", "git rebase workflows",
               "pytest fixtures", "REST API pagination", "React state management",
               "CSS grid layouts", "TypeScript generics", "Redis caching",
               "regular expressions", "OAuth2 flows", "GraphQL schemas",
               "pandas dataframes", "unit test mocking", "database indexing",
               "message queues", "environment variables"]
LIFE_TOPICS = ["meal prep for busy weeks", "training for a 10K",
               "houseplant care basics", "budgeting with spreadsheets",
               "learning Spanish", "resume bullet points",
               "interview preparation", "a cover letter draft",
               "a birthday party plan", "a road trip itinerary",
               "sourdough starter troubleshooting", "home office ergonomics",
               "a book club reading list", "photography composition tips",
               "a garden planting schedule", "winter bike commuting"]

BOTS_W = (["Assistant"] * 7) + (["Creative"] * 2) + (["Analyst"] * 2)


# ---------------------------------------------------------------------------
# Conversation generation
# ---------------------------------------------------------------------------

def product_conv():
    prod = rng.choice(list(PRODUCTS))
    feat = rng.choice(PRODUCTS[prod])
    titles = [f"Question about {feat} in {prod}",
              f"{prod}: configuring {feat}",
              f"Help with {feat} ({prod})",
              f"Understanding {prod} {feat}",
              f"Troubleshooting {feat} in {prod}"]
    q1 = rng.choice([
        f"How do I set up {feat} in {prod}? We just upgraded our plan and I can't find the option.",
        f"Can you explain how {feat} works in {prod}? The docs are a bit sparse.",
        f"We're evaluating {prod} — is {feat} available on the Starter tier?",
        f"I'm getting inconsistent behavior with {feat} in {prod}. Where should I start debugging?"])
    a1 = rng.choice([
        f"Sure — in {prod}, {feat} is managed from the workspace settings panel. "
        f"Open Settings, pick the relevant workflow or project, and you'll see a dedicated section for it. "
        f"Changes take effect immediately, though cached clients may take a minute to pick them up.",
        f"{feat.capitalize()} in {prod} follows the tiered model Meridian Systems uses across its products: "
        f"basic functionality on Starter, advanced controls on Professional, and full customization on Enterprise. "
        f"Check your plan badge in the top-right corner of the {prod} console to see what you have.",
        f"A good starting point is the {prod} activity log — it records every event related to {feat} "
        f"with timestamps and actor IDs. Filter it to the affected resource and look for warnings first."])
    q2 = rng.choice([
        "That worked, thanks. Is there an API for this too?",
        "Got it. Any best practices I should know before rolling this out to the team?",
        "Thanks! Does this behave differently in the sandbox environment?"])
    a2 = rng.choice([
        f"Yes — the {prod} REST API v2 exposes the same controls. Authenticate with a workspace token "
        f"and check the developer reference for the exact endpoints and payload shapes.",
        "A few: start with a small pilot group, document your configuration decisions, and review the "
        "audit trail weekly for the first month so surprises surface early.",
        f"The sandbox mirrors production behavior for {feat}, but data is wiped nightly, so don't rely "
        "on it for anything long-lived."])
    return rng.choice(titles), [(q1, a1), (q2, a2)]


def code_conv():
    topic = rng.choice(CODE_TOPICS)
    titles = [f"Help with {topic}", f"Explaining {topic}", f"Quick question on {topic}",
              f"Debugging {topic}", f"{topic[0].upper() + topic[1:]} walkthrough"]
    q1 = rng.choice([
        f"Can you explain {topic} with a short example? I keep getting confused.",
        f"What's the idiomatic way to handle {topic} in a production codebase?",
        f"I'm reviewing a PR that uses {topic} heavily — what should I watch out for?"])
    a1 = rng.choice([
        f"Happy to help! The core idea behind {topic} is simpler than it looks. Start with the smallest "
        f"working example, run it, then change one thing at a time — that's the fastest way to build intuition. "
        f"The most common mistake is copying a complex snippet without understanding the moving parts.",
        f"For {topic}, the rule of thumb is: keep it readable first, optimize later. Most teams adopt a "
        f"convention and enforce it in code review rather than relying on individual style.",
        f"Watch for edge cases around error handling and empty inputs — that's where most bugs with "
        f"{topic} hide. Also check that the tests actually exercise the failure paths, not just the happy path."])
    q2 = rng.choice([
        "Makes sense. Could you show a common pitfall?",
        "Thanks — any recommended reading to go deeper?",
        "How would I test this properly?"])
    a2 = rng.choice([
        "The classic pitfall is mutating shared state where you expect a copy. Add a regression test the "
        "first time it bites you and it will never bite you twice.",
        "The official documentation is genuinely good here, and pairing it with a small throwaway project "
        "cements it much faster than reading alone.",
        "Write one test per behavior, name it after the behavior, and keep fixtures minimal. If a test "
        "needs three mocks, the code under test probably does too much."])
    return rng.choice(titles), [(q1, a1), (q2, a2)]


def local_conv():
    kind = rng.choice(["place", "service", "food", "biz"])
    if kind == "place":
        ent = rng.choice(LP_PLACES)
        titles = [f"Visiting {ent}", f"Is {ent} worth it?", f"Directions to {ent}",
                  f"Best time to visit {ent}"]
        q1 = f"I'm in Lakeport this weekend — is {ent} worth a visit, and when is it least crowded?"
        a1 = (f"{ent} is one of Lakeport's favorites. Mornings on weekdays are quietest; weekends get busy "
              f"after 11am, especially in summer. Parking nearby fills up fast, so the LakeLink bus or a "
              f"bike is often easier. Give yourself a couple of hours to enjoy it properly.")
    elif kind == "service":
        ent = rng.choice(LP_SERVICES)
        titles = [f"Lakeport {ent} question", f"How do {ent} work in Lakeport?",
                  f"Sorting out {ent}"]
        q1 = f"How do I handle {ent} in Lakeport? Is there an online option or do I need to go to City Hall?"
        a1 = (f"Lakeport moved most of {ent} online through the city portal — you'll need an account tied "
              f"to your address. In-person service is still available at City Hall on Main Street, "
              f"Monday to Friday 9am-4pm, but the online route is usually faster and confirmation "
              f"arrives by email within a couple of business days.")
    elif kind == "food":
        ent = rng.choice(LP_FOOD)
        titles = [f"Dinner at {ent}?", f"Is {ent} good for groups?",
                  f"What to order at {ent}"]
        q1 = f"Thinking of trying {ent} in Lakeport — what's it like and do I need a reservation?"
        a1 = (f"{ent} gets consistently good word of mouth in Lakeport. Weeknights you can usually walk in; "
              f"Friday and Saturday evenings a reservation is smart, especially for four or more. "
              f"Locals recommend the seasonal specials, and portions are generous.")
    else:
        ent = rng.choice(LP_BIZ)
        titles = [f"Has anyone used {ent}?", f"{ent} hours and pricing",
                  f"Recommendation: {ent}?"]
        q1 = f"Is {ent} in Lakeport reliable? I need something done this week and reviews are mixed."
        a1 = (f"{ent} has been around Lakeport for years and most feedback is positive — the mixed reviews "
              f"mostly mention busy periods when turnaround slips. Call ahead to confirm availability, "
              f"ask for a written estimate, and you should be in good shape.")
    q2 = rng.choice(["Great, thanks! Anything else nearby worth combining with the trip?",
                     "Perfect. Do they have accessible parking?",
                     "Thanks, that helps a lot."])
    a2 = rng.choice([
        "If you have spare time, the Pine Street Arts District and the Eastshore Boardwalk are both close "
        "and easy to pair with it.",
        "Yes — accessible spaces are marked near the main entrance, and the city added more last year.",
        "You're welcome! Enjoy Lakeport, and feel free to ask if you need more local tips."])
    return rng.choice(titles), [(q1, a1), (q2, a2)]


def life_conv():
    topic = rng.choice(LIFE_TOPICS)
    titles = [f"Advice on {topic}", f"Help me with {topic}", f"Ideas for {topic}",
              f"Getting started with {topic}"]
    q1 = rng.choice([
        f"I need help with {topic}. Where should I start?",
        f"Can you give me a simple plan for {topic}?",
        f"What do people usually get wrong about {topic}?"])
    a1 = rng.choice([
        f"Start small and specific. For {topic}, pick one concrete goal for the next two weeks, write it "
        f"down, and track it somewhere you'll actually look. Momentum matters more than the perfect plan.",
        f"Here's a simple approach to {topic}: block 30 minutes twice a week, prepare what you need in "
        f"advance, and review how it went each Sunday. Adjust one variable at a time.",
        f"The most common mistake with {topic} is overcommitting in week one and burning out by week three. "
        f"A sustainable routine beats an ambitious one every time."])
    q2 = rng.choice(["That's helpful — can you break it into a checklist?",
                     "What tools or apps would you recommend?",
                     "How do I stay consistent?"])
    a2 = rng.choice([
        "Checklist: 1) define the goal, 2) schedule the time, 3) prepare materials, 4) do the smallest "
        "version, 5) log it, 6) review weekly. Repeat and expand gradually.",
        "Honestly, a plain notes app and a calendar reminder cover 90% of it. Fancy tools help only after "
        "the habit exists.",
        "Tie it to an existing routine — same time, same place. Consistency comes from removing decisions, "
        "not from motivation."])
    return rng.choice(titles), [(q1, a1), (q2, a2)]


CONV_MAKERS = ([product_conv] * 3) + ([code_conv] * 3) + ([local_conv] * 2) + ([life_conv] * 2)


def make_messages(pairs, n_pairs):
    msgs = []
    for q, a in pairs[:n_pairs]:
        msgs.append({"role": "user", "content": q})
        msgs.append({"role": "assistant", "content": a})
    return msgs


# ---------------------------------------------------------------------------
# Knowledge base generation
# ---------------------------------------------------------------------------

KB_MERIDIAN_ASPECTS = ["Overview", "Setup Guide", "Permissions", "Troubleshooting",
                       "Limits and Quotas", "Best Practices", "Release Notes",
                       "Pricing Notes", "Migration Guide", "FAQ Highlights"]


def kb_meridian(eid):
    prod = rng.choice(list(PRODUCTS))
    feat = rng.choice(PRODUCTS[prod])
    aspect = rng.choice(KB_MERIDIAN_ASPECTS)
    feat_t = feat[4:] if feat.startswith("the ") else feat
    topic = f"{prod} {feat_t[0].upper() + feat_t[1:]} — {aspect}"
    content = rng.choice([
        f"{prod} supports {feat} across all subscription tiers, with advanced controls reserved for "
        f"Professional and Enterprise plans. Configuration lives in the workspace settings console and "
        f"can also be managed through the REST API v2. Changes are versioned, and administrators can "
        f"roll back to any previous configuration from the audit trail. Meridian Systems recommends "
        f"reviewing settings quarterly and after any team restructure.",
        f"To work effectively with {feat} in {prod}, start from a template rather than a blank "
        f"configuration. Templates encode Meridian Systems' recommended defaults, including sensible "
        f"retry behavior and notification settings. Test in the sandbox environment first; sandbox data "
        f"is reset nightly. Most misconfigurations surface as warnings in the activity log within minutes.",
        f"Common issues with {feat} in {prod} include stale cached settings (resolved by refreshing the "
        f"client), insufficient role permissions (requires the workspace admin to grant access), and "
        f"conflicts with legacy configurations created before the 2024 console redesign. The diagnostic "
        f"panel under Settings > Health runs automated checks and links each finding to a remediation "
        f"article."])
    kws = list({prod.lower(), aspect.split()[0].lower(),
                *[w.strip(",.").lower() for w in feat.split() if len(w) > 3][:3],
                "meridian"})
    follow = rng.choice([
        f"Would you like a step-by-step walkthrough for {feat} in {prod}?",
        f"Want to know how {feat} interacts with other {prod} features?",
        "Would you like links to the related setup guides?", ""])
    return {"id": eid, "topic": topic, "category": "meridian_products",
            "keywords": json.dumps(kws), "content": content, "follow_up": follow}


def kb_local(eid):
    cat = rng.choice(["lakeport_services", "local_attractions",
                      "local_business", "local_restaurants"])
    if cat == "lakeport_services":
        ent = rng.choice(LP_SERVICES)
        topic = f"Lakeport {ent[0].upper() + ent[1:]}"
        content = (f"The City of Lakeport administers {ent} through the municipal services portal and "
                   f"the City Hall service desk on Main Street (weekdays 9am-4pm). Online requests are "
                   f"typically processed within two business days and confirmations are sent by email. "
                   f"Fees, where applicable, can be paid by card online or in person. Seasonal schedule "
                   f"changes are announced on the city website and the LakeLink notice boards.")
        kws = ["lakeport", "city services"] + [w.lower() for w in ent.split()[:3] if len(w) > 3]
    elif cat == "local_attractions":
        ent = rng.choice(LP_PLACES)
        topic = ent[0].upper() + ent[1:]
        content = (f"{ent[0].upper() + ent[1:]} is one of Lakeport's best-known destinations. It is open "
                   f"year-round, with the busiest period from June through September. Weekday mornings are "
                   f"the quietest time to visit. The site is reachable by the LakeLink bus network, and "
                   f"bicycle racks are available at the main entrance. Nearby, the Pine Street Arts "
                   f"District and the Eastshore Boardwalk make for an easy combined outing.")
        kws = ["lakeport", "attraction", "visit"] + [w.lower().strip(",") for w in ent.split() if len(w) > 3][:3]
    elif cat == "local_business":
        ent = rng.choice(LP_BIZ)
        topic = ent
        content = (f"{ent} is a locally owned Lakeport business with a long-standing reputation for "
                   f"reliable service and fair pricing. Typical hours are Monday to Saturday, 9am to 6pm. "
                   f"Busy periods can extend turnaround times, so calling ahead is recommended. The shop "
                   f"participates in the Lakeport Local loyalty program and the annual Main Street "
                   f"summer fair.")
        kws = ["lakeport", "local business"] + [w.lower() for w in ent.replace("&", "").split() if len(w) > 3][:3]
    else:
        ent = rng.choice(LP_FOOD)
        topic = ent
        content = (f"{ent} is a popular Lakeport eatery known for generous portions and rotating seasonal "
                   f"specials. Walk-ins are fine on weeknights; reservations are recommended for Friday "
                   f"and Saturday evenings and for groups of four or more. Vegetarian options are marked "
                   f"on the menu, and takeout can be ordered by phone. The kitchen sources produce from "
                   f"the Lakeport Farmers Market in season.")
        kws = ["lakeport", "restaurant", "dining"] + [w.lower() for w in ent.replace("&", "").split() if len(w) > 3][:2]
    follow = rng.choice(["Would you like directions or opening hours?",
                         "Want suggestions for similar spots in Lakeport?",
                         "", ""])
    return {"id": eid, "topic": topic, "category": cat,
            "keywords": json.dumps(sorted(set(kws))), "content": content, "follow_up": follow}


# ---------------------------------------------------------------------------
# FAQ generation
# ---------------------------------------------------------------------------

def make_faq(eid):
    cat = rng.choice(["meridian_products"] * 4 + ["lakeport_services"] * 2 +
                     ["local_attractions"] * 2 + ["local_business"] * 2)
    if cat == "meridian_products":
        prod = rng.choice(list(PRODUCTS))
        feat = rng.choice(PRODUCTS[prod])
        q = rng.choice([f"Does {prod} support {feat}?",
                        f"How do I enable {feat} in {prod}?",
                        f"Is {feat} in {prod} available on the Starter plan?",
                        f"Where do I configure {feat} in {prod}?"])
        a = (f"Yes — {prod} includes {feat} as part of its core feature set. Basic functionality is "
             f"available on every tier, while advanced controls require a Professional or Enterprise "
             f"subscription. Configuration is done from the workspace settings console, and the same "
             f"options are exposed through the {prod} REST API v2. See the product documentation for a "
             f"step-by-step guide.")
    elif cat == "lakeport_services":
        ent = rng.choice(LP_SERVICES)
        q = rng.choice([f"How do I sign up for {ent} in Lakeport?",
                        f"Where can I manage {ent} in Lakeport?",
                        f"Is there an online option for {ent} in Lakeport?"])
        a = (f"The City of Lakeport handles {ent} through its online municipal portal, with in-person "
             f"help available at City Hall on Main Street (weekdays 9am-4pm). Online requests are "
             f"usually confirmed by email within two business days.")
    elif cat == "local_attractions":
        ent = rng.choice(LP_PLACES)
        q = rng.choice([f"When is the best time to visit {ent}?",
                        f"How do I get to {ent}?",
                        f"Is {ent} open year-round?"])
        a = (f"{ent[0].upper() + ent[1:]} is open year-round and is busiest from June through September. "
             f"Weekday mornings are quietest. The LakeLink bus network stops nearby, and bicycle racks "
             f"are available at the entrance.")
    else:
        ent = rng.choice(LP_BIZ + LP_FOOD)
        q = rng.choice([f"What are the opening hours of {ent}?",
                        f"Does {ent} take reservations or appointments?",
                        f"Is {ent} in downtown Lakeport?"])
        a = (f"{ent} is located in central Lakeport and is typically open Monday to Saturday. Busy "
             f"periods fill up quickly, so calling ahead for a reservation or appointment is "
             f"recommended, especially on weekends.")
    return {"id": eid, "question": q, "answer": a, "category": cat}


# ---------------------------------------------------------------------------
# Prompts library generation
# ---------------------------------------------------------------------------

PROMPT_RECIPES = {
    "coding": (["Refactor {x}", "Explain {x}", "Write Tests for {x}", "Debug {x}",
                "Optimize {x}", "Document {x}"],
               CODE_TOPICS,
               "You are an experienced software engineer. {verb} the following code involving {x}. "
               "Be specific: reference exact lines, explain the reasoning behind each suggestion, and "
               "show corrected code where helpful. Flag any security or performance concerns you notice.",
               ["code", "engineering", "review"]),
    "writing": (["Draft {x}", "Polish {x}", "Outline {x}", "Rewrite {x}"],
                ["a project status update", "a blog post introduction", "a product announcement",
                 "release notes", "a meeting recap", "a customer apology email",
                 "an executive summary", "a job posting", "a newsletter section",
                 "a conference talk abstract"],
                "You are a clear, concise writing assistant. {verb} {x} based on the notes I provide. "
                "Keep the tone professional but warm, lead with the key message, and keep it under "
                "300 words unless I ask for more.",
                ["writing", "communication", "editing"]),
    "analysis": (["Analyze {x}", "Summarize {x}", "Compare {x}", "Forecast {x}"],
                 ["quarterly sales figures", "survey results", "A/B test outcomes",
                  "website traffic trends", "customer churn data", "support ticket volumes",
                  "feature adoption metrics", "campaign performance"],
                 "You are a data analyst. {verb} {x} from the data I paste below. Structure your answer "
                 "as: key findings, supporting numbers, caveats, and recommended next steps. Prefer "
                 "plain language over jargon.",
                 ["analysis", "data", "insights"]),
    "productivity": (["Plan {x}", "Prioritize {x}", "Break Down {x}"],
                     ["a product launch week", "a quarterly OKR review", "a team offsite",
                      "an inbox-zero routine", "a sprint backlog", "a home move",
                      "a study schedule", "a hiring pipeline"],
                     "You are a pragmatic productivity coach. {verb} {x} into concrete, time-boxed steps. "
                     "Identify dependencies, flag the single most important task, and suggest what to "
                     "drop if time runs short.",
                     ["productivity", "planning", "organization"]),
    "creative": (["Brainstorm {x}", "Imagine {x}", "Name {x}"],
                 ["taglines for a local coffee shop", "a short story opening set in Lakeport",
                  "podcast episode ideas", "a mascot for a cycling club",
                  "themes for a summer festival", "icebreaker questions for a team",
                  "titles for a photography exhibit"],
                 "You are a creative partner with bold ideas. {verb} {x}. Offer at least eight distinct "
                 "options ranging from safe to adventurous, and note which one you would pick and why.",
                 ["creative", "ideas", "brainstorming"]),
    "education": (["Teach Me {x}", "Quiz Me on {x}", "Simplify {x}"],
                  ["the basics of personal finance", "how DNS works", "intro statistics",
                   "the water cycle", "how vaccines work", "basic music theory",
                   "the rules of chess", "photosynthesis"],
                  "You are a patient tutor. {verb} {x}. Start from first principles, use one vivid "
                  "analogy, check my understanding with two short questions, and adapt based on my "
                  "answers.",
                  ["education", "learning", "tutoring"]),
    "local": (["Plan {x}", "Recommend {x}"],
              ["a Lakeport weekend itinerary", "a dinner crawl through Lakeport",
               "a rainy-day plan in Lakeport", "a family day at the Lakeport Marina",
               "a bike route along the Eastshore Boardwalk",
               "a first-timer's tour of the Pine Street Arts District"],
              "You are a knowledgeable Lakeport local. {verb} {x}. Include timing, rough costs, "
              "transit options on the LakeLink network, and one hidden gem most visitors miss.",
              ["local", "lakeport", "recommendations"]),
}


def make_prompt(pid, used_titles):
    cat = rng.choice(list(PROMPT_RECIPES) + ["coding", "writing", "analysis"])
    verbs, xs, body, base_tags = PROMPT_RECIPES[cat]
    small = {"a", "an", "the", "for", "of", "on", "in", "with", "to", "and"}
    for _ in range(30):
        verb_t, x = rng.choice(verbs), rng.choice(xs)
        raw = verb_t.format(x=x)
        words = raw.split()
        title = " ".join(w if (0 < i and w.lower() in small) or w[0].isupper()
                         else w.capitalize() for i, w in enumerate(words))
        if title not in used_titles:
            break
    used_titles.add(title)
    verb_word = verb_t.split()[0]
    prompt_text = body.format(verb=verb_word, x=x)
    tags = sorted(set(base_tags + [w.lower().strip(",") for w in x.split() if len(w) > 4][:2]))
    return {"id": pid, "title": title, "category": cat, "prompt": prompt_text,
            "tags": json.dumps(tags), "popularity": rng.randint(5, 88)}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    dry = "--dry-run" in sys.argv
    db = sqlite3.connect(DB_PATH, timeout=60)
    db.row_factory = sqlite3.Row

    existing_users = [dict(r) for r in db.execute("SELECT id, username FROM ai_chatbots_users")]
    existing_usernames = {u["username"] for u in existing_users}
    existing_conv_ids = {r["id"] for r in db.execute("SELECT id FROM ai_chatbots_conversations")}
    next_user = db.execute("SELECT MAX(id)+1 FROM ai_chatbots_users").fetchone()[0]
    next_kb = db.execute("SELECT MAX(id)+1 FROM ai_chatbots_knowledge_base").fetchone()[0]
    next_faq = db.execute("SELECT MAX(id)+1 FROM ai_chatbots_faq").fetchone()[0]
    next_prompt = db.execute("SELECT MAX(id)+1 FROM ai_chatbots_prompts_library").fetchone()[0]
    max_prompt_existing = next_prompt - 1

    # ---- prompts ----
    prompts_new, used_titles = [], set()
    for _ in range(TARGET_PROMPTS):
        prompts_new.append(make_prompt(next_prompt, used_titles))
        next_prompt += 1
    all_prompt_ids = list(range(1, max_prompt_existing + 1)) + [p["id"] for p in prompts_new]

    # ---- knowledge base ----
    kb_new = []
    for i in range(TARGET_KB):
        maker = kb_meridian if rng.random() < 0.32 else kb_local
        kb_new.append(maker(next_kb))
        next_kb += 1

    # ---- faq ----
    faq_new = [make_faq(next_faq + i) for i in range(TARGET_FAQ)]

    # ---- users (ids 6..) — synthetic, root_user_id 0 like other expansions ----
    users_new = []
    for i in range(TARGET_USERS):
        for _ in range(50):
            fn, ln = rng.choice(FIRST), rng.choice(LAST)
            username = f"{fn.lower()}_{ln.lower()}"
            if username not in existing_usernames:
                break
            username = f"{fn.lower()}_{ln.lower()}{rng.randint(2, 99)}"
            if username not in existing_usernames:
                break
        existing_usernames.add(username)
        password = f"{fn[0].lower()}{ln[:4].capitalize()}!{rng.choice(['Chat','Hub','Ai','Bot'])}{rng.randint(10, 99)}"
        prefs = {"default_bot": rng.choice(BOTS_W), "theme": rng.choice(["dark", "dark", "light"]),
                 "font_size": rng.choice(["small", "medium", "medium", "large"]),
                 "notifications": rng.random() < 0.7, "save_history": rng.random() < 0.9}
        saved = sorted(rng.sample(all_prompt_ids, rng.choice([0, 0, 1, 1, 2, 3])))
        users_new.append({
            "id": next_user, "root_user_id": 0, "username": username,
            "password": password, "display_name": f"{fn} {ln}",
            "email": f"{fn.lower()}.{ln.lower()}@{rng.choice(MAIL)}",
            "preferences": json.dumps(prefs),
            "subscription": rng.choice(["free"] * 7 + ["pro"] * 3),
            "saved_prompts": json.dumps(saved),
            "shared_conversations": "[]",   # filled in after conversations
            "avatar": "",
        })
        next_user += 1

    # ---- conversations — only for users other than id 1 (alex_rivera) ----
    # Owners: existing users 2-5 get a light share; new users carry the bulk.
    owner_pool = [u["id"] for u in existing_users if u["id"] != 1]
    new_user_ids = [u["id"] for u in users_new]
    owner_weights = [0.3] * len(owner_pool) + [1.0] * len(new_user_ids)
    owner_pool = owner_pool + new_user_ids

    convs_new, conv_ids = [], set(existing_conv_ids)
    shared_by_user = {}
    for _ in range(TARGET_CONVS):
        title, pairs = rng.choice(CONV_MAKERS)()
        assert not any(w in title.lower() for w in FORBIDDEN_TITLE_WORDS), title
        while True:
            cid = f"conv_{rng.getrandbits(32):08x}"
            if cid not in conv_ids:
                conv_ids.add(cid)
                break
        owner = rng.choices(owner_pool, weights=owner_weights)[0]
        created = rand_dt()
        n_pairs = rng.choice([1, 1, 2, 2, 2])
        msgs = make_messages(pairs, n_pairs)
        updated = created + datetime.timedelta(minutes=rng.randint(4, 45))
        updated = min(updated, TODAY)
        # shared only for synthetic users so we never UPDATE existing user rows
        shared = 1 if (owner in new_user_ids and rng.random() < 0.05) else 0
        if shared:
            shared_by_user.setdefault(owner, []).append(cid)
        convs_new.append({
            "id": cid, "user_id": owner, "title": title,
            "bot": rng.choice(BOTS_W),
            "created_at": iso(created), "updated_at": iso(updated),
            "messages": json.dumps(msgs, ensure_ascii=False),
            "shared": shared,
            "archived": 1 if rng.random() < 0.06 else 0,
        })
    for u in users_new:
        if u["id"] in shared_by_user:
            u["shared_conversations"] = json.dumps(shared_by_user[u["id"]])

    print(f"users: +{len(users_new)}, conversations: +{len(convs_new)}, "
          f"knowledge_base: +{len(kb_new)}, faq: +{len(faq_new)}, prompts: +{len(prompts_new)}")
    if dry:
        print("\n-- sample conversations --")
        for c in convs_new[:5]:
            print(f"  u{c['user_id']:>3} {c['created_at']} | {c['title'][:60]}")
        print("-- sample kb --")
        for e in kb_new[:4]:
            print(f"  {e['id']} [{e['category']}] {e['topic'][:60]}")
        print("-- sample faq --")
        for e in faq_new[:3]:
            print(f"  {e['id']} [{e['category']}] {e['question'][:60]}")
        print("-- sample prompts --")
        for p in prompts_new[:4]:
            print(f"  {p['id']} [{p['category']}] {p['title'][:50]} pop={p['popularity']}")
        print("-- sample user --")
        print("  ", {k: users_new[0][k] for k in ("id", "username", "email", "subscription")})
        return

    bdir = ROOT / "data" / "backups" / "ai-chatbots-expansion-2026-07-20"
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "inserted_ids.json").write_text(json.dumps({
        "users": [u["id"] for u in users_new],
        "conversations": [c["id"] for c in convs_new],
        "knowledge_base": [e["id"] for e in kb_new],
        "faq": [e["id"] for e in faq_new],
        "prompts_library": [p["id"] for p in prompts_new]}, indent=1))

    for table, rows in (("users", users_new), ("prompts_library", prompts_new),
                        ("knowledge_base", kb_new), ("faq", faq_new),
                        ("conversations", convs_new)):
        cols = list(rows[0].keys())
        db.executemany(
            f"INSERT INTO ai_chatbots_{table} ({', '.join(cols)}) "
            f"VALUES ({', '.join('?' * len(cols))})",
            [[r[c] for c in cols] for r in rows])
    db.commit()

    # Rebuild FTS indexes for every touched table that has one.
    for t in ("faq", "knowledge_base", "prompts_library", "conversations"):
        fts = f"fts_ai_chatbots_{t}"
        row = db.execute("SELECT name FROM sqlite_master WHERE name = ?", (fts,)).fetchone()
        if row:
            db.execute(f"INSERT INTO {fts}({fts}) VALUES('rebuild')")
    db.commit()
    print(f"inserted; rollback ids at {bdir}/inserted_ids.json")


if __name__ == "__main__":
    main()
