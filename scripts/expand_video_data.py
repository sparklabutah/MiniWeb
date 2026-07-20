"""Expand video (StreamHub) base data.

StreamHub ships with 30 videos / 50 comments / 18 watch-history rows / 10
playlists / 9 users (117 rows total), which leaves the home feed, channel
pages, comment counts, and history nearly empty. Adds deterministic (seeded)
synthetic viewer accounts, a dozen small PNW-themed creator channels, videos,
comments, watch history, and playlists, all consistent with the existing
Lakeport / Meridian / Cascadia universe.

Insert-only; inserted ids recorded under data/backups/ for rollback.

Task-constraint guardrails baked in:
  * Every new video is dated 2023-07-01 .. 2026-05-11, strictly OLDER than the
    current sitewide-latest video (id 30, Mia's Rescue Trails, 2026-05-12), so
    "find the latest video" still resolves to handle mia_rescues.
  * The date window 2020-07-01 .. 2023-06-30 stays EMPTY (currently 0 videos),
    so the "filter between July 1 2020 and June 30 2023" result is unchanged.
  * No videos are added to channel 2 (Marcus Codes & Climbs), so "My Complete
    Neovim Setup | From Zero to Productive" (134,500 views) stays its most
    popular video. New titles never reuse "Neovim".
  * No new channel is named "Mia's Rescue Trails"; no duplicate video titles.
  * New videos on existing channels get views strictly below that channel's
    current max, so every channel's "most popular video" is unchanged.
  * Thumbnails / avatars reuse the existing /static/thumbnails/vid_001..030.jpg
    and /static/avatars/user_001..009.jpg files (no invented image files).
  * Bulk rows are attached to users other than the main user (id 1); user 1
    only gets +82 watch-history rows (history page then renders 100 rows).

Usage: ~/.conda/envs/miniweb/bin/python scripts/expand_video_data.py [--dry-run]
"""
import datetime
import json
import random
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "trimmed_miniweb.db"
rng = random.Random(20260720)

TODAY = datetime.date(2026, 7, 19)
LATEST_EXISTING = datetime.date(2026, 5, 12)   # video 30, mia_rescues — must stay latest
NEW_VIDEO_MAX = LATEST_EXISTING - datetime.timedelta(days=1)   # 2026-05-11
NEW_VIDEO_MIN = datetime.date(2023, 7, 1)      # keep 2020-07-01..2023-06-30 empty

CATEGORIES = ["Education", "Entertainment", "Food & Cooking", "Gaming",
              "Pets & Animals", "Science & Technology", "Sports",
              "Travel & Outdoors"]

FIRST = ["Jordan", "Priya", "Devon", "Maya", "Caleb", "Rosa", "Trevor", "Lena",
         "Owen", "Aisha", "Felix", "Nora", "Diego", "Harper", "Ethan", "Ivy",
         "Marcus", "Tessa", "Ruben", "Chloe", "Andre", "Sadie", "Kai", "Paige",
         "Victor", "Elena", "Grant", "Bianca", "Omar", "Willow", "Silas",
         "Dana", "Colin", "Amara", "Reed", "Josie", "Hugo", "Skye", "Tobias",
         "Mara", "Wes", "Carmen", "Levi", "June", "Dmitri", "Faye", "Ellis",
         "Renee", "Zach", "Talia", "Bram", "Nina", "Cole", "Iris", "Jonas",
         "Perla", "Shane", "Vera", "Milo", "Gwen", "Arlo", "Sana", "Kurt",
         "Leah", "Basil", "Opal", "Cyrus", "Wren", "Dario", "Nell"]
LAST = ["Whitfield", "Nakamura", "Delgado", "Okafor", "Sorensen", "McAllister",
        "Vasquez", "Lindqvist", "Abara", "Thibodeaux", "Kowalski", "Reyes",
        "Fitzgerald", "Ademola", "Castellano", "Bergstrom", "Ochoa", "Hale",
        "Iverson", "Marsh", "Quintero", "Sandoval", "Pruitt", "Vang",
        "Holloway", "Barnes", "Ferreira", "Stanton", "Ng", "Calloway",
        "Duarte", "Weaver", "Osei", "Lund", "Farrow"]

VIEWER_ABOUTS = [
    "Lakeport local. Mostly here for trail videos and cooking channels.",
    "Weekend hiker, weekday desk dweller. Subscribed to way too many channels.",
    "Just here to watch and learn. Cascadia born and raised.",
    "Meridian Systems employee unwinding with gaming montages after work.",
    "Dog parent, coffee enthusiast, playlist hoarder.",
    "Learning to code one tutorial at a time.",
    "PNW transplant collecting hiking recommendations.",
    "Amateur cook working through every pasta video on this site.",
    "Fitness class regular at Brooks Fitness. The programming here got me started.",
    "Board game night organizer. Strategy guides are my weakness.",
]

# New creator channels: (username, display, channel_name, category focus,
#   joined, subs, about, links, title templates, tags)
CREATORS = [
    ("lakeport_eats", "Rosa Delgado", "Lakeport Eats", "Food & Cooking",
     "2022-08-19", 11200,
     "Eating my way through Lakeport and the greater Cascadia food scene. "
     "Honest reviews, hidden gems, and home recreations of local favorites.",
     '{"website": null, "instagram": "@lakeport_eats"}',
     ["{place} Review | Is It Worth the Hype?",
      "Recreating {dish} at Home | Lakeport Eats Kitchen",
      "Top 5 {meal} Spots in {area}",
      "First Time Trying {dish} | Honest Reaction",
      "{dish} Three Ways | Budget vs Mid vs Fancy"],
     ["food review", "Lakeport", "restaurants", "cooking", "local eats"]),
    ("cascadia_overland", "Trevor Sorensen", "Cascadia Overland", "Travel & Outdoors",
     "2022-05-30", 19800,
     "Van life and overlanding across the Pacific Northwest. Route guides, "
     "rig upgrades, and the honest parts of living on forest roads.",
     '{"website": "https://cascadiaoverland.net", "instagram": "@cascadia_overland"}',
     ["{route} Overland Route | Full Trail Report",
      "Van Camping at {area} | {season} Trip",
      "Rig Upgrade: Installing a {gear}",
      "{days} Days Off-Grid in the {area}",
      "Overlanding Mistakes I Made So You Don't Have To | Part {n}"],
     ["overlanding", "vanlife", "PNW", "camping", "off-grid"]),
    ("priya_builds", "Priya Nakamura", "Priya Builds Things", "Science & Technology",
     "2023-03-07", 8400,
     "Hardware hacking, home automation, and weekend electronics projects "
     "from my Lakeport garage workshop.",
     '{"website": null, "github": "priyabuilds"}',
     ["Building a {gadget} from Scratch",
      "{gadget} Teardown | What's Actually Inside",
      "Home Automation Ep. {n} | Wiring the {room}",
      "I Spent {days} Days Building a {gadget}",
      "Beginner Soldering Project: {gadget}"],
     ["electronics", "DIY", "home automation", "maker", "hardware"]),
    ("sound_anglers", "Ruben Ochoa", "Puget Sound Anglers", "Travel & Outdoors",
     "2022-10-11", 6700,
     "Salmon, lingcod, and everything in between. Fishing reports and boat "
     "maintenance from the Puget Sound and Cascadia rivers.",
     '{"website": null, "instagram": "@sound_anglers"}',
     ["{fish} Fishing Report | {area}, {season}",
      "How to Rig for {fish} | Tackle Walkthrough",
      "Sunrise {fish} Session at {area}",
      "Boat Maintenance Log Ep. {n} | {gear} Service",
      "Catch and Cook: {fish} Two Ways"],
     ["fishing", "Puget Sound", "salmon", "angling", "boat life"]),
    ("boardgame_nook", "Tessa McAllister", "The Board Game Nook", "Gaming",
     "2023-01-05", 13500,
     "Deep strategy breakdowns, playthroughs, and shelf tours from a cozy "
     "corner of Lakeport. Euro games are home but everything gets a seat.",
     '{"website": "https://boardgamenook.blog", "instagram": "@boardgame_nook"}',
     ["{game} Review | {plays} Plays Later",
      "{game} Strategy Deep Dive | Opening Moves That Win",
      "Top {n} Games for {group}",
      "Is {game} Worth Buying in 2026?",
      "Teaching {game} in Under 10 Minutes"],
     ["board games", "strategy", "tabletop", "review", "playthrough"]),
    ("emerald_keys", "Elena Castellano", "Emerald City Keys", "Entertainment",
     "2022-04-25", 22400,
     "Piano covers, practice-with-me sessions, and honest talk about adult "
     "music learning. Recorded in my Seattle apartment on a very patient upright.",
     '{"website": null, "instagram": "@emerald_keys"}',
     ["{piece} | Piano Cover",
      "Practice With Me | {minutes} Minute {focus} Session",
      "Learning {piece} in One Week | Day-by-Day",
      "{n} Exercises That Fixed My {focus}",
      "Apartment Piano Setup Tour | {season} Update"],
     ["piano", "music", "cover", "practice", "learning music"]),
    ("rainyday_reads", "Nora Lindqvist", "Rainy Day Reads", "Education",
     "2023-05-16", 9100,
     "Book reviews and reading vlogs for perpetually overcast weather. "
     "Literary fiction, sci-fi, and the occasional doorstopper readalong.",
     '{"website": null, "instagram": "@rainyday_reads"}',
     ["{month} Reading Wrap-Up | {n} Books",
      "Reading Vlog | A Rainy Weekend with {genre}",
      "{n} {genre} Books I Can't Stop Recommending",
      "Bookshelf Tour {season} | The {shelf} Shelf",
      "Readalong Announcement | {month} Pick"],
     ["books", "reading", "book review", "reading vlog", "bookish"]),
    ("nw_garden_lab", "Owen Whitfield", "Northwest Garden Lab", "Education",
     "2022-07-02", 15600,
     "Experiments in year-round vegetable gardening, zone 8b. Raised beds, "
     "cover crops, and data-driven composting from a Lakeport backyard.",
     '{"website": "https://nwgardenlab.com", "instagram": "@nw_garden_lab"}',
     ["Growing {crop} in the PNW | Complete Guide",
      "{month} Garden Tour | What's Thriving and What Died",
      "{crop} Experiment Results | {n} Varieties Compared",
      "Building a {structure} | Weekend Project",
      "Cool-Season {crop} | Planting to Harvest"],
     ["gardening", "PNW garden", "vegetables", "raised beds", "zone 8b"]),
    ("trailside_wrench", "Diego Quintero", "Trailside Wrench", "Sports",
     "2022-12-08", 7800,
     "Mountain bike maintenance and trail riding around Cascadia. Fix it "
     "yourself and ride more — wrenching tutorials for every skill level.",
     '{"website": null, "instagram": "@trailside_wrench"}',
     ["How to Service Your {part} at Home",
      "{trail} Trail Check | Conditions and Features",
      "Budget vs Premium {part} | Blind Test",
      "Full {task} | Step by Step, No Special Tools",
      "Ride Along: {trail} {season} Laps"],
     ["MTB", "bike maintenance", "trail riding", "wrenching", "cycling"]),
    ("cascadia_wx", "Faye Bergstrom", "Cascadia Weather Watch", "Science & Technology",
     "2023-02-27", 12900,
     "Forecast breakdowns and weather science for the Pacific Northwest. "
     "Atmospheric rivers explained by an actual meteorology nerd.",
     '{"website": "https://cascadiawx.org", "twitter": "@cascadia_wx"}',
     ["{event} Explained | Why the PNW Gets Them",
      "{month} Outlook | What the Models Are Saying",
      "How {tool} Actually Works",
      "Storm Recap: The {month} {event}",
      "Forecasting 101 Ep. {n} | Reading {tool}"],
     ["weather", "meteorology", "PNW weather", "forecast", "science"]),
    ("harbor_flow", "Amara Osei", "Harbor Yoga Flow", "Sports",
     "2023-04-20", 10400,
     "Yoga classes filmed by the Lakeport waterfront. Slow flows, mobility "
     "work for desk bodies, and breathwork you'll actually do.",
     '{"website": "https://harboryogaflow.com", "instagram": "@harbor_flow"}',
     ["{minutes} Minute {style} Flow | All Levels",
      "Morning Mobility for {audience}",
      "{style} for Beginners | No Flexibility Required",
      "Full Class: {minutes} Min {style} by the Harbor",
      "Desk Body Reset | {focus} Release Routine"],
     ["yoga", "mobility", "flow", "wellness", "stretching"]),
    ("pixel_palette", "Kai Vang", "Pixel & Palette", "Entertainment",
     "2022-09-14", 17300,
     "Digital painting process videos, brush breakdowns, and art challenges. "
     "Concept art day job, cozy illustration by night.",
     '{"website": "https://pixelandpalette.art", "instagram": "@pixel_palette"}',
     ["Painting a {subject} | Full Process",
      "{n} Brushes I Actually Use | {software} Setup",
      "Art Challenge: {subject} in {minutes} Minutes",
      "Redrawing My Art from {year} | Progress Check",
      "{software} Beginner Course Ep. {n} | {focus}"],
     ["digital art", "painting", "process", "illustration", "art tutorial"]),
]

# Fill-in vocab for the title templates above (keyed by placeholder)
VOCAB = {
    "place": ["Harborview Diner", "The Copper Kettle", "Pike & Pine Ramen",
              "Maple Lane Bakery", "Cascade Taqueria", "The Dockside Grill",
              "Juniper & Sage", "Old Mill Pizza Co", "Saltwater Oyster Bar",
              "The Night Market"],
    "dish": ["Birria Tacos", "Cedar Plank Salmon", "Hand-Pulled Noodles",
             "Marionberry Pie", "Smash Burgers", "Pho", "Sourdough Focaccia",
             "Clam Chowder", "Korean Fried Chicken", "Mushroom Risotto"],
    "meal": ["Breakfast", "Brunch", "Late-Night", "Cheap Lunch", "Dessert"],
    "area": ["Lakeport Waterfront", "North Cascades", "Olympic Peninsula",
             "Meridian District", "Gifford Pinchot", "Hood Canal",
             "Snoqualmie Valley", "the San Juans", "Capitol Forest"],
    "route": ["Naches Wagon", "Walker Valley", "Evans Creek", "Manastash Ridge",
              "Ahtanum State Forest", "Tahuya", "Elbe Hills"],
    "season": ["Spring", "Summer", "Fall", "Winter", "Shoulder-Season"],
    "gear": ["Diesel Heater", "Roof Rack", "Dual Battery System", "Awning",
             "Water Tank", "Fridge Slide", "Suspension Lift", "Trailer Hitch"],
    "days": ["3", "4", "5", "7", "10"],
    "n": ["1", "2", "3", "4", "5", "6", "7", "8"],
    "gadget": ["Weather Station", "Smart Bird Feeder", "LED Matrix Clock",
               "Garage Door Monitor", "Plant Watering Robot", "E-Ink Dashboard",
               "Retro Game Console", "Air Quality Sensor"],
    "room": ["Garage", "Kitchen", "Greenhouse", "Office", "Workshop"],
    "fish": ["Coho", "Chinook", "Lingcod", "Steelhead", "Cutthroat",
             "Halibut", "Pink Salmon"],
    "game": ["Terraforming Mars", "Brass Birmingham", "Cascadia", "Root",
             "Ark Nova", "Spirit Island", "Everdell", "Concordia",
             "The Crew", "Dune Imperium"],
    "plays": ["10", "25", "50", "100"],
    "group": ["Two Players", "Big Groups", "New Gamers", "Family Night",
              "Heavy Euro Fans"],
    "piece": ["Clair de Lune", "Gymnopedie No. 1", "River Flows in You",
              "Nuvole Bianche", "Golden Hour", "Merry-Go-Round of Life",
              "Comptine d'un autre ete", "Experience"],
    "minutes": ["10", "15", "20", "30", "45", "60"],
    "focus": ["Left Hand", "Sight Reading", "Chord Voicing", "Arpeggio",
              "Hip", "Shoulder", "Lower Back", "Hamstring", "Line Work",
              "Color Theory", "Composition"],
    "month": ["January", "February", "March", "April", "May", "June", "July",
              "August", "September", "October", "November", "December"],
    "genre": ["Sci-Fi", "Literary Fiction", "Fantasy", "Mystery", "Nonfiction"],
    "shelf": ["Unread", "Favorites", "Signed Copies", "Doorstopper"],
    "crop": ["Garlic", "Winter Squash", "Tomatoes", "Overwintering Kale",
             "Snap Peas", "Potatoes", "Brassicas", "Salad Greens"],
    "structure": ["Cold Frame", "Drip Irrigation System", "Compost Bay",
                  "Trellis Arch", "Rain Barrel Setup"],
    "part": ["Fork", "Dropper Post", "Brakes", "Drivetrain", "Wheel Bearings",
             "Tubeless Setup"],
    "trail": ["Galbraith", "Tiger Mountain", "Duthie Hill", "Raging River",
              "Olallie", "Swan Creek"],
    "task": ["Drivetrain Overhaul", "Brake Bleed", "Suspension Service",
             "Bearing Replacement"],
    "event": ["Atmospheric River", "Convergence Zone", "Heat Dome",
              "Windstorm", "Lowland Snow Event", "June Gloom"],
    "tool": ["Radar", "Ensemble Models", "Sounding Charts", "Satellite Loops"],
    "style": ["Slow Flow", "Vinyasa", "Yin", "Restorative", "Power Flow"],
    "audience": ["Desk Workers", "Runners", "Climbers", "Cyclists", "Lifters"],
    "subject": ["Rainy Street Scene", "Forest Spirit", "Lighthouse at Dusk",
                "Cozy Bookshop", "Mountain Village", "Sleeping Fox",
                "Harbor at Night", "Mossy Ruins"],
    "software": ["Procreate", "Krita", "Photoshop", "Clip Studio"],
    "year": ["2019", "2020", "2021", "2022"],
}

# Extra videos for EXISTING channels (never ch 1 = main user, never ch 2 = Marcus).
# channel_id -> (count, category pool, title templates)
EXISTING_CHANNEL_PLANS = {
    3: (10, ["Education", "Science & Technology"],
        ["MeridianVault Demo | {focus2} Walkthrough",
         "Webinar Replay: {focus2} for Growing Teams",
         "Customer Story | How {company} Uses MeridianFlow",
         "Feature Friday Ep. {n} | {focus2}",
         "B2B Content That Converts | {focus2} Edition"]),
    4: (12, ["Sports", "Education"],
        ["{minutes} Minute {bodypart} Workout | No Equipment",
         "{bodypart} Training Mistakes Ep. {n}",
         "Client Transformation | {months} Month Check-In",
         "Gym Owner Diaries Ep. {n} | Behind Brooks Fitness",
         "Mobility for Lifters | {bodypart} Routine"]),
    5: (10, ["Entertainment", "Education"],
        ["Logo Design Timelapse | {client} Brand",
         "Design Critique Ep. {n} | Viewer Submissions",
         "Freelance Diaries Ep. {n} | {biz}",
         "Rebranding a {client} | Full Process",
         "Font Talk Ep. {n} | Pairing Type for {client} Projects"]),
    6: (8, ["Sports", "Entertainment"],
        ["Basketball Drill Series | {skill} Fundamentals",
         "Pickup Runs at {court} | Game Highlights",
         "PT Corner Ep. {n} | {joint} Injury Prevention",
         "Lakeport Rec League Recap | Week {n}",
         "Training With Resistance Bands | {skill} Edition"]),
    7: (10, ["Science & Technology", "Education"],
        ["SyncWave Build Log Ep. {n} | {startup_topic}",
         "Founder Q&A | {startup_topic}",
         "Startup Finance Basics | {startup_topic}",
         "Inside Our {meeting} | Unedited",
         "What I Learned Failing at {startup_topic}"]),
    8: (10, ["Education", "Science & Technology"],
        ["LeetCode {num}: {problem} | Explained Step by Step",
         "Mock Interview Ep. {n} | {topic8} Round",
         "Study With Me | {minutes} Minutes of {topic8}",
         "How I'd Learn {topic8} Again From Scratch",
         "Junior Dev Diaries Ep. {n} | {topic8} Week"]),
    9: (10, ["Pets & Animals", "Travel & Outdoors"],
        ["Rescue Story | {dogname}'s Second Chance",
         "Foster Diaries Ep. {n} | {animal} Update",
         "Vet Tech Q&A Ep. {n} | {petcare}",
         "Trail Day with {dogname} | {area} Loop",
         "Adoption Day | {dogname} Meets the New Family"]),
}
VOCAB.update({
    "focus2": ["Document Workflows", "Access Controls", "Analytics Dashboards",
               "Onboarding Automation", "Audit Trails", "Integrations"],
    "company": ["Cedarline Logistics", "Bluepine Labs", "Harborview Clinic",
                "Northgate Manufacturing", "Summit & Co"],
    "bodypart": ["Core", "Upper Body", "Lower Body", "Back", "Shoulder",
                 "Full Body", "Glute"],
    "months": ["3", "6", "9", "12"],
    "client": ["Coffee Roaster", "Craft Brewery", "Bookstore", "Food Truck",
               "Climbing Gym", "Nonprofit"],
    "biz": ["Pricing My Work", "Finding Clients", "Handling Revisions",
            "Contracts 101", "Portfolio Cleanup"],
    "skill": ["Ball Handling", "Footwork", "Shooting Form", "Defense",
              "Conditioning"],
    "court": ["Maple Lane Park", "Lakeport Community Center", "Eastside Gym",
              "Harborview Courts"],
    "joint": ["Ankle", "Knee", "Shoulder", "Wrist", "Hip"],
    "startup_topic": ["Pricing", "Our First Enterprise Deal", "Hiring",
                      "Churn", "Fundraising", "Roadmap Planning"],
    "meeting": ["Sprint Planning", "Board Prep", "Retro", "All-Hands"],
    "num": ["23", "56", "76", "128", "155", "207", "238", "300", "394", "417"],
    "problem": ["Merge K Sorted Lists", "Sliding Window Maximum",
                "Minimum Window Substring", "Longest Consecutive Sequence",
                "Top K Frequent Elements", "Course Schedule",
                "Word Ladder", "Trapping Rain Water"],
    "topic8": ["Dynamic Programming", "Graphs", "System Design", "Binary Search",
               "Two Pointers", "Backtracking"],
    "dogname": ["Biscuit", "Juniper", "Scout", "Pepper", "Mochi", "Banjo",
                "Willa", "Tugboat", "Clementine"],
    "animal": ["Senior Beagle", "Bonded Cat Pair", "Litter of Five",
               "Three-Legged Shepherd", "Shy Husky"],
    "petcare": ["Paw Care in Winter", "Reading Dog Body Language",
                "Crate Training", "Post-Surgery Recovery", "Trail Safety"],
})

COMMENT_TEMPLATES = {
    "generic": [
        "This channel is so underrated. Instantly subscribed.",
        "Watched this twice already. The editing keeps getting better!",
        "Greetings from {area}! Love seeing local creators.",
        "The audio quality improved a lot since your early uploads. Nice work.",
        "Sent this to my roommate, we're both hooked now.",
        "This showed up in my recommendations and I have zero regrets.",
        "Can you do a follow-up on this? Would love a part two.",
        "Notification squad! Been waiting for this one all week.",
        "Honestly better than most big-channel takes on this topic.",
        "The intro made me laugh out loud. Keep these coming.",
        "Saving this to my watch later for the weekend.",
        "Quality content as always. Lakeport represent!",
        "I never comment but this one deserved it. Really well done.",
        "Timestamp 4:12 is exactly what I needed, thank you!",
        "Your pacing is perfect. No filler, all substance.",
    ],
    "Education": [
        "Took notes through the whole thing. Clearer than my actual classes.",
        "You explain this better than any textbook I've tried.",
        "Finally somebody who doesn't skip the fundamentals. Thank you!",
        "This deserves way more views. Sharing with my study group.",
        "Rewatched the middle section three times. It finally clicked.",
    ],
    "Entertainment": [
        "The vibes in this one are immaculate.",
        "Background music choice is perfect. What's the track?",
        "I came for five minutes and stayed for the whole thing.",
        "Your personality carries these videos. Never change.",
    ],
    "Food & Cooking": [
        "Made this last night. The family demolished it in minutes.",
        "My kitchen smells amazing and it's all your fault.",
        "Adding this to the weeknight rotation immediately.",
        "That sear at the end... chef's kiss.",
        "Grocery list made. Attempting this on Sunday!",
    ],
    "Gaming": [
        "That opening strategy is genius. Trying it at game night Friday.",
        "My group is completely split on this one, great breakdown.",
        "The rules explanation alone is worth the watch.",
        "GG. That comeback in the last third was unreal.",
    ],
    "Pets & Animals": [
        "I'm not crying, you're crying. What a sweet ending.",
        "Thank you for the work you do for these animals.",
        "The little tail wag at the end absolutely destroyed me.",
        "Fostering is so underrated. Videos like this help so much.",
        "Please give them an extra treat from all of us!",
    ],
    "Science & Technology": [
        "The diagrams make this so much easier to follow. Great job.",
        "Been debugging this exact thing all week. Lifesaver.",
        "Subscribed for the deep dives, stayed for the dry humor.",
        "Would love to see the benchmarks on this setup.",
    ],
    "Sports": [
        "Did this routine this morning. My legs are jelly. 10/10.",
        "Form cues at the start are so helpful, nobody else covers those.",
        "Day 14 of following along. Actually seeing progress!",
        "My physical therapist recommended your channel. Now I get why.",
    ],
    "Travel & Outdoors": [
        "Adding this to the summer list. Thanks for the honest trail notes!",
        "Was just up there in {month}. Conditions were exactly like you showed.",
        "The drone shots of the ridgeline are stunning.",
        "Appreciate the leave-no-trace reminders. More creators should do this.",
        "What's the road access like in early {season}?",
    ],
}
REPLY_TEMPLATES = [
    "Totally agree with this.",
    "Came here to say exactly this!",
    "Thanks for the extra detail, super helpful.",
    "Replying so I can find this comment later.",
    "Same experience here. Glad it's not just me.",
    "This should be pinned honestly.",
    "Good point — I hadn't considered that.",
    "+1, can confirm.",
]

PLAYLIST_TITLES = [
    ("Weekend Watchlist", "Stuff to catch up on when the week finally ends."),
    ("Workout Rotation", "Sessions I actually come back to."),
    ("Dinner Ideas", "Recipes queued for the next grocery run."),
    ("Learn Something", "Tutorials and explainers worth a second watch."),
    ("PNW Adventures", "Trails, camps, and coastline inspiration."),
    ("Cozy Background", "Low-key videos for rainy afternoons."),
    ("Game Night Prep", "Strategy refreshers before the next session."),
    ("Deep Focus", "Long-form videos for concentration sessions."),
    ("Morning Routine", "Short videos to start the day right."),
    ("Project Fuel", "Maker and DIY inspiration for the garage."),
    ("Commute Queue", "Bus-ride length videos for the daily loop."),
    ("Skill Building", "One playlist, one new hobby at a time."),
    ("Saved for Later", "The eternal to-watch pile."),
    ("Best of StreamHub", "Personal favorites from around the site."),
    ("Sunday Reset", "Cleaning, cooking, and slow living videos."),
]

TAG_EXTRAS = ["StreamHub", "Lakeport", "PNW", "2026", "tutorial", "vlog",
              "how to", "guide", "Cascadia", "local creator"]


def d2s(d):
    return d.strftime("%Y-%m-%d")


def rand_date(lo, hi):
    if hi < lo:
        hi = lo
    return lo + datetime.timedelta(days=rng.randint(0, (hi - lo).days))


def ts(d, hlo=6, hhi=23):
    return "%sT%02d:%02d:00Z" % (d2s(d), rng.randint(hlo, hhi), rng.randint(0, 59))


def fill(template):
    out = template
    for key, pool in VOCAB.items():
        token = "{%s}" % key
        while token in out:
            out = out.replace(token, rng.choice(pool), 1)
    return out


def main():
    dry = "--dry-run" in sys.argv
    db = sqlite3.connect(DB_PATH, timeout=60)
    db.row_factory = sqlite3.Row

    existing_users = [dict(r) for r in db.execute("SELECT * FROM video_users")]
    existing_videos = [dict(r) for r in db.execute("SELECT * FROM video_videos")]
    chan_max_views = dict(db.execute(
        "SELECT channel_id, MAX(views) FROM video_videos GROUP BY channel_id"))
    chan_joined = {u["id"]: u["joined_date"] for u in existing_users}
    existing_titles = {v["title"] for v in existing_videos}

    next_user = db.execute("SELECT MAX(id)+1 FROM video_users").fetchone()[0]
    next_video = db.execute("SELECT MAX(id)+1 FROM video_videos").fetchone()[0]
    next_comment = db.execute("SELECT MAX(id)+1 FROM video_comments").fetchone()[0]
    next_hist = db.execute("SELECT MAX(id)+1 FROM video_watch_history").fetchone()[0]
    next_pl = db.execute("SELECT MAX(id)+1 FROM video_playlists").fetchone()[0]

    # ---------------- users ----------------
    users_new = []
    used_usernames = {u["username"] for u in existing_users}

    creator_ids = {}
    for (uname, disp, chan, cat, joined, subs, about, links, tmpls, tags) in CREATORS:
        uid = next_user
        next_user += 1
        creator_ids[uid] = (cat, tmpls, tags, joined)
        users_new.append({
            "id": uid, "root_user_id": 0, "username": uname,
            "display_name": disp, "channel_name": chan,
            "email": "%s@gmail.com" % uname.replace("_", "."),
            "avatar_url": "/static/avatars/user_%03d.jpg" % (uid % 9 + 1),
            "subscriber_count": subs, "videos_count": 15,
            "joined_date": joined, "about": about, "links": links,
            "is_verified": 1 if subs > 18000 else 0,
        })
        used_usernames.add(uname)

    n_viewers = 128
    name_pairs = [(f, l) for f in FIRST for l in LAST]
    rng.shuffle(name_pairs)
    for f, l in name_pairs:
        if len(users_new) >= n_viewers + len(CREATORS):
            break
        uname = "%s_%s" % (f.lower(), l.lower().replace(" ", ""))
        if uname in used_usernames:
            continue
        used_usernames.add(uname)
        uid = next_user
        next_user += 1
        joined = rand_date(datetime.date(2022, 3, 1), datetime.date(2026, 4, 30))
        users_new.append({
            "id": uid, "root_user_id": 0, "username": uname,
            "display_name": "%s %s" % (f, l),
            "channel_name": "%s %s" % (f, l),
            "email": "%s.%s%s@gmail.com" % (f.lower(), l.lower(), rng.choice(["", "", str(rng.randint(1, 99))])),
            "avatar_url": "/static/avatars/user_%03d.jpg" % (uid % 9 + 1),
            "subscriber_count": rng.choice([0, 0, 1, 2, 3, 5, 8, 12, 20, 45]),
            "videos_count": 0,
            "joined_date": d2s(joined),
            "about": rng.choice(VIEWER_ABOUTS),
            "links": '{"website": null}',
            "is_verified": 0,
        })

    all_user_rows = existing_users + users_new
    user_by_id = {u["id"]: u for u in all_user_rows}
    # Bulk actors: everyone except the main user (id 1)
    actor_ids = [u["id"] for u in all_user_rows if u["id"] != 1]

    # ---------------- videos ----------------
    videos_new = []

    def add_video(chan_id, title, category, tags, joined_str, view_cap):
        nonlocal next_video
        lo = max(NEW_VIDEO_MIN,
                 datetime.datetime.strptime(joined_str, "%Y-%m-%d").date()
                 + datetime.timedelta(days=14))
        up = rand_date(lo, NEW_VIDEO_MAX)
        views = rng.randint(150, view_cap)
        likes = int(views * rng.uniform(0.02, 0.09))
        vid = {
            "id": next_video, "title": title, "channel_id": chan_id,
            "user_id": chan_id,
            "description": "",
            "duration_seconds": rng.randint(240, 2400),
            "views": views, "likes": likes,
            "dislikes": max(0, int(likes * rng.uniform(0.005, 0.04))),
            "upload_date": d2s(up),
            "category": category,
            "tags": json.dumps(rng.sample(tags, min(4, len(tags)))
                               + rng.sample(TAG_EXTRAS, 2)),
            "thumbnail_url": "/static/thumbnails/vid_%03d.jpg" % (next_video % 30 + 1),
            "video_url": "/static/videos/vid_%03d.mp4" % next_video,
            "status": "published",
        }
        next_video += 1
        videos_new.append(vid)
        return vid

    DESCS = [
        "Full breakdown in today's upload — timestamps in the pinned comment. "
        "Filmed around {area} over a couple of weekends.",
        "One of my most requested topics. Everything is linked in the "
        "description and questions are welcome in the comments.",
        "New upload! This one took longer to edit than to film. Let me know "
        "what you want to see next on the channel.",
        "Part of an ongoing series — check the channel page for the rest. "
        "Thanks for all the support from the Lakeport crew.",
        "Recorded this after a bunch of comment requests. If it helps, "
        "subscribing is the best way to support the channel.",
    ]

    # New creator channels: 15 videos each
    for uid, (cat, tmpls, tags, joined) in creator_ids.items():
        made = set()
        while len(made) < 15:
            title = fill(rng.choice(tmpls))
            if title in made or title in existing_titles:
                continue
            made.add(title)
            v = add_video(uid, title, cat, tags, joined, 92000)
            v["description"] = fill(rng.choice(DESCS))

    # Existing channels (except 1 and 2): views capped below the channel max
    for chan_id, (count, cats, tmpls) in EXISTING_CHANNEL_PLANS.items():
        base_tags = ["StreamHub"]
        cap = max(500, int(chan_max_views[chan_id] * 0.55))
        made = set()
        while len(made) < count:
            title = fill(rng.choice(tmpls))
            if title in made or title in existing_titles:
                continue
            made.add(title)
            v = add_video(chan_id, title, rng.choice(cats), base_tags,
                          chan_joined[chan_id], cap)
            v["tags"] = json.dumps(rng.sample(TAG_EXTRAS, 4))
            v["description"] = fill(rng.choice(DESCS))

    all_video_rows = existing_videos + videos_new
    video_by_id = {v["id"]: v for v in all_video_rows}

    # ---------------- comments ----------------
    comments_new = []
    # weight by views so busy videos get more chatter
    weights = [max(v["views"], 500) for v in all_video_rows]
    target_comments = 3300
    per_video = {v["id"]: 0 for v in all_video_rows}
    picks = rng.choices([v["id"] for v in all_video_rows], weights=weights,
                        k=target_comments * 2)
    top_by_video = {}
    for vid_id in picks:
        if len(comments_new) >= target_comments:
            break
        if per_video[vid_id] >= 70:
            continue
        per_video[vid_id] += 1
        v = video_by_id[vid_id]
        up = datetime.datetime.strptime(v["upload_date"], "%Y-%m-%d").date()
        cdate = rand_date(up, min(TODAY, up + datetime.timedelta(days=420)))
        author = user_by_id[rng.choice(actor_ids)]
        parents = top_by_video.get(vid_id, [])
        if parents and rng.random() < 0.15:
            parent = rng.choice(parents)
            text = rng.choice(REPLY_TEMPLATES)
            parent_id = parent
        else:
            pool = COMMENT_TEMPLATES["generic"] + COMMENT_TEMPLATES.get(
                v["category"], [])
            text = fill(rng.choice(pool))
            parent_id = 0  # existing convention: 0 = top-level
        c = {
            "id": next_comment, "video_id": vid_id, "user_id": author["id"],
            "username": author["username"],
            "display_name": author["display_name"],
            "text": text, "timestamp": ts(cdate),
            "likes": rng.choice([0, 0, 1, 1, 2, 3, 4, 6, 9, 14, 22, 35, 61]),
            "parent_comment_id": parent_id,
        }
        if parent_id == 0:
            top_by_video.setdefault(vid_id, []).append(next_comment)
        next_comment += 1
        comments_new.append(c)

    # ---------------- watch history ----------------
    history_new = []

    def add_history(uid, v):
        nonlocal next_hist
        chan = user_by_id[v["channel_id"]]
        up = datetime.datetime.strptime(v["upload_date"], "%Y-%m-%d").date()
        wdate = rand_date(up, TODAY)
        history_new.append({
            "id": next_hist, "user_id": uid, "video_id": v["id"],
            "video_title": v["title"], "channel_name": chan["channel_name"],
            "watched_at": ts(wdate, 7, 23),
            "progress_percent": rng.choice([100, 100, 100, 92, 85, 71, 64, 48, 33, 17, 8]),
            "duration_seconds": v["duration_seconds"],
        })
        next_hist += 1

    # main user: +82 (history page will render 100 rows total)
    user1_watched = set(r[0] for r in db.execute(
        "SELECT video_id FROM video_watch_history WHERE user_id=1"))
    candidates = [v for v in all_video_rows if v["id"] not in user1_watched]
    for v in rng.sample(candidates, min(82, len(candidates))):
        add_history(1, v)

    # other users: remaining 1218, ~5-15 rows each across viewers/creators
    remaining = 1300 - len(history_new)
    hist_users = rng.choices(actor_ids, k=remaining)
    seen = {}
    for uid in hist_users:
        tries = 0
        while True:
            v = rng.choices(all_video_rows, weights=weights)[0]
            key = (uid, v["id"])
            tries += 1
            if key not in seen or tries > 4:
                break
        seen[key] = True
        add_history(uid, v)

    # ---------------- playlists ----------------
    playlists_new = []
    pl_owner_pool = rng.sample(actor_ids, 70)
    for i in range(90):
        owner = user_by_id[rng.choice(pl_owner_pool)]
        title, desc = PLAYLIST_TITLES[i % len(PLAYLIST_TITLES)]
        vis = "public" if i < 22 else "private"
        vids = rng.sample(all_video_rows, rng.randint(2, 8))
        items, added_dates = [], []
        for pos, v in enumerate(vids, start=1):
            up = datetime.datetime.strptime(v["upload_date"], "%Y-%m-%d").date()
            ad = rand_date(up, TODAY)
            added_dates.append(ad)
            items.append({"video_id": v["id"], "added_date": d2s(ad),
                          "position": pos})
        joined = datetime.datetime.strptime(owner["joined_date"], "%Y-%m-%d").date()
        created = rand_date(joined, min(added_dates))
        playlists_new.append({
            "id": next_pl, "user_id": owner["id"], "username": owner["username"],
            "title": title, "description": desc, "visibility": vis,
            "created_date": d2s(created), "updated_date": d2s(max(added_dates)),
            "items": json.dumps(items),
        })
        next_pl += 1

    print("users: +%d, videos: +%d, comments: +%d, watch_history: +%d, playlists: +%d"
          % (len(users_new), len(videos_new), len(comments_new),
             len(history_new), len(playlists_new)))
    total_new = (len(users_new) + len(videos_new) + len(comments_new)
                 + len(history_new) + len(playlists_new))
    print("new rows: %d (site total will be %d)" % (total_new, total_new + 117))

    # guardrail assertions
    assert all(v["upload_date"] <= d2s(NEW_VIDEO_MAX) for v in videos_new)
    assert all(v["upload_date"] >= d2s(NEW_VIDEO_MIN) for v in videos_new)
    assert all(v["channel_id"] not in (1, 2) for v in videos_new)
    assert not any("Neovim" in v["title"] for v in videos_new)
    assert not any(u["channel_name"] == "Mia's Rescue Trails" for u in users_new)
    for v in videos_new:
        if v["channel_id"] in chan_max_views:
            assert v["views"] < chan_max_views[v["channel_id"]]

    if dry:
        print("--- sample videos ---")
        for v in videos_new[:8]:
            print("  ch%-3d %s %6dv | %s" % (v["channel_id"], v["upload_date"],
                                             v["views"], v["title"][:64]))
        print("--- sample comments ---")
        for c in comments_new[:5]:
            print("  vid %-3d %s %s | %s" % (c["video_id"], c["username"][:18],
                                             c["timestamp"], c["text"][:56]))
        print("--- sample history / playlist ---")
        print(" ", history_new[0])
        print(" ", {k: playlists_new[0][k] for k in ("id", "user_id", "title",
                                                     "visibility")})
        return

    bdir = ROOT / "data" / "backups" / "video-expansion-2026-07-20"
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "inserted_ids.json").write_text(json.dumps({
        "users": [u["id"] for u in users_new],
        "videos": [v["id"] for v in videos_new],
        "comments": [c["id"] for c in comments_new],
        "watch_history": [h["id"] for h in history_new],
        "playlists": [p["id"] for p in playlists_new]}, indent=1))

    for table, rows in (("users", users_new), ("videos", videos_new),
                        ("comments", comments_new),
                        ("watch_history", history_new),
                        ("playlists", playlists_new)):
        if not rows:
            continue
        cols = list(rows[0].keys())
        db.executemany(
            "INSERT INTO video_%s (%s) VALUES (%s)"
            % (table, ", ".join(cols), ", ".join("?" * len(cols))),
            [[r[c] for c in cols] for r in rows])
    # keep FTS mirrors in sync (users has no FTS table)
    for fts in ("fts_video_videos", "fts_video_comments",
                "fts_video_watch_history", "fts_video_playlists"):
        db.execute("INSERT INTO %s(%s) VALUES('rebuild')" % (fts, fts))
    db.commit()
    print("inserted; rollback ids at %s/inserted_ids.json" % bdir)


if __name__ == "__main__":
    main()
