#!/usr/bin/env python3
"""Generate synthetic auction/product data for auctions-p2p-marketplaces.

Uses WebShop items_shuffle.json for product images when available. It writes:
  data/products.json   - 150 product listings with auction metadata
  data/users.json      - user accounts
  data/bids.json       - bid history
  data/messages.json   - user messages
  data/reports.json    - item reports
  data/watchlist.json  - user watchlists
  data/ratings.json    - seller ratings
  data/.pristine/      - pristine copies of all mutable files
"""
import json
import os
import pathlib
import random
import shutil
from datetime import datetime, timedelta

SITE_DIR = pathlib.Path(__file__).resolve().parent
DATA_DIR = SITE_DIR / "data"
PRISTINE_DIR = DATA_DIR / ".pristine"
CONFIG_PATH = SITE_DIR / "config" / "config.json"

SEED = 42
rng = random.Random(SEED)


def _load_webshop_images():
    """Load image URLs from WebShop items_shuffle.json.

    Returns a list of image URL strings (first image per item).
    """
    # Try config path first, then the known data_sources location
    webshop_path = None
    if CONFIG_PATH.exists():
        try:
            cfg = json.loads(CONFIG_PATH.read_text())
            webshop_path = cfg.get("webshop_data_path")
        except Exception:
            pass

    if not webshop_path:
        webshop_path = "/scratch/general/vast/u1653932/data_sources/webshop/items_shuffle.json"

    p = pathlib.Path(webshop_path)
    if not p.exists():
        print(f"WARNING: WebShop data not found at {p}, products will have no image_url")
        return []

    images = []
    try:
        # The file may be JSONL (one JSON object per line) or a large JSON array.
        # Use an incremental approach: try JSONL first, then use ijson-style manual parsing.
        with open(p, "r") as f:
            first_char = f.read(1)
            f.seek(0)

            if first_char == "[":
                # JSON array - use a streaming approach to avoid loading entire file
                # Skip the opening bracket, then parse objects one at a time
                import re
                # Read in chunks, extract image URLs via regex for efficiency
                # We need the "images" field value from each item
                buf = ""
                depth = 0
                obj_start = -1
                count = 0
                for chunk in iter(lambda: f.read(64 * 1024), ""):
                    for i, ch in enumerate(buf_offset := chunk):
                        if ch == "{":
                            if depth == 0:
                                obj_start = 0
                                obj_buf = ""
                            depth += 1
                        if depth > 0:
                            if obj_start == 0:
                                obj_buf += ch
                        if ch == "}":
                            depth -= 1
                            if depth == 0 and obj_start == 0:
                                try:
                                    item = json.loads(obj_buf)
                                    img_list = item.get("images")
                                    if img_list and isinstance(img_list, list) and len(img_list) > 0:
                                        first_img = img_list[0]
                                        if isinstance(first_img, str) and first_img.startswith("http"):
                                            images.append(first_img)
                                except (json.JSONDecodeError, TypeError):
                                    pass
                                count += 1
                                obj_start = -1
                                obj_buf = ""
                                if len(images) >= 500 or count >= 2000:
                                    break
                    if len(images) >= 500 or count >= 2000:
                        break
            else:
                # JSONL format
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        item = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    img_list = item.get("images")
                    if img_list and isinstance(img_list, list) and len(img_list) > 0:
                        first_img = img_list[0]
                        if isinstance(first_img, str) and first_img.startswith("http"):
                            images.append(first_img)
                    if len(images) >= 500:
                        break
    except Exception as e:
        print(f"WARNING: Failed to read WebShop data: {e}")
        import traceback
        traceback.print_exc()

    print(f"Loaded {len(images)} image URLs from WebShop data")
    return images

# ---------------------------------------------------------------------------
# Categories and product templates
# ---------------------------------------------------------------------------

CATEGORIES = [
    "Electronics", "Clothing", "Home & Garden", "Collectibles",
    "Sports", "Toys & Games", "Books", "Automotive",
    "Jewelry", "Art", "Music", "Health & Beauty"
]

CONDITION_OPTIONS = ["New", "Like New", "Very Good", "Good", "Acceptable"]

BRANDS = [
    "TechPro", "AuraHome", "SportMax", "ClassicVintage", "LuxeLine",
    "PrimeGear", "UrbanStyle", "NatureCraft", "EliteEdge", "RetroFind",
    "DigiWorld", "CozyNest", "FitLife", "ArtisanCo", "SmartChoice",
    "ValuePick", "GoldenAge", "TrendSet", "EcoLiving", "MasterBuild"
]

PRODUCT_TEMPLATES = {
    "Electronics": [
        ("Wireless Bluetooth Headphones", 29.99, 149.99),
        ("4K Ultra HD Smart TV 55-inch", 199.99, 799.99),
        ("Portable Bluetooth Speaker", 14.99, 89.99),
        ("Tablet 10.1 inch 128GB", 79.99, 399.99),
        ("Wireless Gaming Mouse", 9.99, 59.99),
        ("Mechanical Keyboard RGB", 24.99, 129.99),
        ("USB-C Hub Multiport Adapter", 12.99, 49.99),
        ("Noise Cancelling Earbuds", 19.99, 119.99),
        ("Portable Power Bank 20000mAh", 14.99, 54.99),
        ("Smart Watch Fitness Tracker", 24.99, 199.99),
        ("External SSD 1TB", 49.99, 159.99),
        ("Webcam 1080p HD", 19.99, 79.99),
        ("Drone with 4K Camera", 99.99, 499.99),
    ],
    "Clothing": [
        ("Vintage Denim Jacket", 19.99, 89.99),
        ("Leather Crossbody Bag", 24.99, 149.99),
        ("Cashmere Scarf", 14.99, 79.99),
        ("Running Shoes Men's Size 10", 29.99, 129.99),
        ("Wool Peacoat Women's", 39.99, 199.99),
        ("Silk Necktie Set", 9.99, 49.99),
        ("Canvas Backpack", 14.99, 69.99),
        ("Sunglasses Polarized UV400", 9.99, 59.99),
        ("Handmade Leather Belt", 12.99, 64.99),
        ("Winter Down Jacket", 49.99, 249.99),
    ],
    "Home & Garden": [
        ("Ceramic Plant Pot Set", 14.99, 59.99),
        ("Stainless Steel Cookware Set", 49.99, 249.99),
        ("LED Desk Lamp Adjustable", 12.99, 49.99),
        ("Memory Foam Pillow", 9.99, 49.99),
        ("Robot Vacuum Cleaner", 79.99, 399.99),
        ("Air Purifier HEPA Filter", 39.99, 199.99),
        ("Cordless Stick Vacuum", 49.99, 299.99),
        ("Electric Kettle 1.7L", 14.99, 59.99),
        ("Weighted Blanket 15lbs", 19.99, 79.99),
        ("Smart Thermostat", 29.99, 149.99),
    ],
    "Collectibles": [
        ("Vintage Baseball Card Collection", 49.99, 499.99),
        ("Rare Coin Set 1960s", 29.99, 299.99),
        ("First Edition Book", 19.99, 199.99),
        ("Antique Pocket Watch", 49.99, 399.99),
        ("Vinyl Record Collection", 24.99, 149.99),
        ("Vintage Movie Poster", 14.99, 99.99),
        ("Signed Sports Memorabilia", 39.99, 349.99),
        ("Vintage Action Figure Lot", 19.99, 129.99),
        ("Antique Map Print", 14.99, 89.99),
        ("Limited Edition Figurine", 24.99, 179.99),
    ],
    "Sports": [
        ("Mountain Bike 21-Speed", 99.99, 499.99),
        ("Yoga Mat Premium", 9.99, 49.99),
        ("Adjustable Dumbbell Set", 39.99, 199.99),
        ("Tennis Racket Pro", 19.99, 129.99),
        ("Golf Club Set", 79.99, 449.99),
        ("Kayak Inflatable 2-Person", 99.99, 399.99),
        ("Camping Tent 4-Person", 39.99, 199.99),
        ("Fishing Rod Combo", 19.99, 89.99),
        ("Boxing Gloves 16oz", 14.99, 69.99),
        ("Skateboard Complete", 19.99, 89.99),
    ],
    "Toys & Games": [
        ("LEGO Architecture Set", 24.99, 149.99),
        ("Board Game Collection", 14.99, 79.99),
        ("Remote Control Car", 19.99, 89.99),
        ("Puzzle 1000 Pieces", 7.99, 29.99),
        ("Building Blocks 500pc", 12.99, 59.99),
        ("Card Game Deluxe", 9.99, 39.99),
        ("Science Kit for Kids", 14.99, 59.99),
        ("Dollhouse Miniature", 29.99, 149.99),
        ("Train Set Electric", 39.99, 199.99),
        ("Drone Mini for Beginners", 19.99, 79.99),
    ],
    "Books": [
        ("Complete Works of Shakespeare", 9.99, 49.99),
        ("Cookbook Collection Set", 14.99, 69.99),
        ("Sci-Fi Novel Bundle", 7.99, 39.99),
        ("Art History Textbook", 12.99, 59.99),
        ("Programming Reference Guide", 14.99, 79.99),
        ("Children's Picture Book Set", 9.99, 44.99),
        ("Travel Guide Collection", 7.99, 34.99),
        ("Biography Hardcover", 9.99, 29.99),
        ("Mystery Novel Series", 12.99, 49.99),
        ("Self-Help Bestseller", 7.99, 24.99),
    ],
    "Automotive": [
        ("Car Dash Camera 4K", 29.99, 149.99),
        ("Tire Pressure Monitoring System", 19.99, 79.99),
        ("Car Phone Mount Magnetic", 7.99, 29.99),
        ("Jump Starter Portable", 29.99, 99.99),
        ("Car Seat Cover Set", 19.99, 89.99),
        ("LED Headlight Bulbs H11", 14.99, 59.99),
        ("OBD2 Scanner Diagnostic", 19.99, 79.99),
        ("Roof Rack Cross Bars", 39.99, 149.99),
        ("Car Vacuum Cordless", 19.99, 69.99),
        ("Steering Wheel Cover Leather", 9.99, 39.99),
    ],
    "Jewelry": [
        ("Sterling Silver Necklace", 14.99, 89.99),
        ("Gold Plated Bracelet", 9.99, 59.99),
        ("Diamond Stud Earrings", 49.99, 399.99),
        ("Vintage Brooch Pin", 9.99, 69.99),
        ("Pearl Pendant Necklace", 24.99, 149.99),
        ("Watch Automatic Mechanical", 49.99, 299.99),
        ("Gemstone Ring Set", 19.99, 129.99),
        ("Charm Bracelet Silver", 14.99, 79.99),
        ("Cufflinks Set", 9.99, 49.99),
        ("Anklet Gold Plated", 7.99, 34.99),
    ],
    "Art": [
        ("Oil Painting Canvas 24x36", 29.99, 199.99),
        ("Watercolor Art Print Set", 14.99, 69.99),
        ("Photography Print Framed", 19.99, 99.99),
        ("Sculpture Ceramic Handmade", 24.99, 149.99),
        ("Digital Art Print Limited", 9.99, 49.99),
        ("Sketch Drawing Set", 7.99, 34.99),
        ("Mixed Media Collage", 19.99, 89.99),
        ("Abstract Canvas Art", 29.99, 179.99),
        ("Portrait Commission", 49.99, 299.99),
        ("Calligraphy Art Piece", 14.99, 79.99),
    ],
    "Music": [
        ("Electric Guitar Stratocaster Style", 79.99, 399.99),
        ("Acoustic Guitar Beginner", 39.99, 199.99),
        ("MIDI Keyboard Controller 49-Key", 49.99, 199.99),
        ("Vinyl Turntable Player", 39.99, 199.99),
        ("Studio Monitor Speakers Pair", 59.99, 299.99),
        ("Microphone Condenser USB", 19.99, 99.99),
        ("Drum Practice Pad", 9.99, 49.99),
        ("Ukulele Concert Size", 14.99, 79.99),
        ("Guitar Pedal Effects", 19.99, 99.99),
        ("Harmonica Set Key of C", 7.99, 29.99),
    ],
    "Health & Beauty": [
        ("Skincare Set Korean Beauty", 14.99, 79.99),
        ("Hair Dryer Professional", 19.99, 89.99),
        ("Massage Gun Percussion", 29.99, 149.99),
        ("Essential Oil Diffuser", 12.99, 49.99),
        ("Electric Toothbrush Sonic", 14.99, 79.99),
        ("Makeup Brush Set 12pc", 9.99, 49.99),
        ("Facial Cleansing Device", 19.99, 89.99),
        ("Aromatherapy Candle Set", 9.99, 39.99),
        ("Nail Art Kit Professional", 12.99, 59.99),
        ("Body Scale Smart WiFi", 14.99, 59.99),
    ],
}

SHIPPING_OPTIONS = ["Free Shipping", "Standard ($4.99)", "Expedited ($12.99)", "Local Pickup"]

SELLER_NAMES = [
    "deal_hunter42", "vintage_vault", "tech_surplus", "bargain_barn",
    "collectible_king", "style_savvy", "home_essentials", "sports_central",
    "book_nook", "auto_parts_pro", "jewelry_box", "art_gallery99",
    "music_corner", "beauty_depot", "treasure_trove", "gadget_guru",
    "retro_finds", "luxury_resale", "eco_shop", "prime_deals"
]

SELLER_LOCATIONS = [
    "New York, NY", "Los Angeles, CA", "Chicago, IL", "Houston, TX",
    "Phoenix, AZ", "Philadelphia, PA", "San Antonio, TX", "San Diego, CA",
    "Dallas, TX", "San Jose, CA", "Austin, TX", "Jacksonville, FL",
    "Fort Worth, TX", "Columbus, OH", "Charlotte, NC", "San Francisco, CA",
    "Indianapolis, IN", "Seattle, WA", "Denver, CO", "Portland, OR"
]


def _generate_description(name, category, brand, condition):
    templates = [
        f"High-quality {name} from {brand}. Condition: {condition}. Perfect for enthusiasts and collectors alike. This item has been carefully inspected and meets our quality standards.",
        f"Authentic {brand} {name} in {condition} condition. Great value for the price. Ships in original packaging when available. Satisfaction guaranteed.",
        f"Get this amazing {name} by {brand}! Item is in {condition} condition. Ideal addition to your {category.lower()} collection. Don't miss this opportunity.",
        f"{brand} {name} - {condition} condition. Carefully stored and maintained. This {category.lower()} item is ready to ship. Buy with confidence from a trusted seller.",
        f"Rare find! {name} from {brand} in {condition} condition. This {category.lower()} gem won't last long. Includes all original accessories where applicable.",
    ]
    return rng.choice(templates)


def _generate_bid_history(listing_id, start_price, current_price, num_bids, seller_id, user_ids, base_time):
    """Generate deterministic bid history with realistic price progression."""
    bids = []
    if num_bids == 0:
        return bids

    # Price increments follow a curve: early bids are larger jumps, later bids tighter
    price_range = current_price - start_price
    bidder_pool = [uid for uid in user_ids if uid != seller_id]
    if not bidder_pool:
        return bids

    for i in range(num_bids):
        progress = (i + 1) / num_bids
        bid_price = round(start_price + price_range * progress, 2)
        bidder = bidder_pool[i % len(bidder_pool)]
        bid_time = base_time + timedelta(hours=int(i * 24 * 7 / max(num_bids, 1)))
        bids.append({
            "bid_id": len(bids) + 1,
            "listing_id": listing_id,
            "bidder_id": bidder,
            "amount": bid_price,
            "timestamp": bid_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "auto_bid": rng.random() < 0.3
        })

    return bids


def generate():
    # Load WebShop image URLs
    webshop_images = _load_webshop_images()

    # Base time: auctions start 2 weeks ago, end over next 2 weeks
    base_date = datetime(2026, 6, 7, 10, 0, 0)
    now = datetime(2026, 6, 21, 12, 0, 0)

    # Generate sellers (first 20 users are sellers)
    sellers = []
    for i, name in enumerate(SELLER_NAMES, 1):
        sellers.append({
            "id": i,
            "username": name,
            "password": f"seller{i:03d}",
            "name": name.replace("_", " ").title(),
            "email": f"{name}@auctionsite.example.com",
            "role": "seller",
            "location": SELLER_LOCATIONS[i - 1],
            "rating": round(3.5 + rng.random() * 1.5, 1),
            "total_sales": rng.randint(10, 500),
            "member_since": f"{rng.randint(2018, 2025)}-{rng.randint(1,12):02d}",
            "saved_listings": [],
            "watchlist": [],
            "followed_sellers": [],
        })

    # Generate buyers (users 21-30)
    buyer_names = [
        ("alice_bidder", "Alice Johnson", "alice_bidder"),
        ("bob_collector", "Bob Smith", "bob_collector"),
        ("carol_shopper", "Carol Williams", "carol_shopper"),
        ("dan_buyer", "Dan Brown", "dan_buyer"),
        ("eve_bargain", "Eve Davis", "eve_bargain"),
        ("frank_deals", "Frank Miller", "frank_deals"),
        ("grace_finds", "Grace Wilson", "grace_finds"),
        ("henry_hunter", "Henry Moore", "henry_hunter"),
        ("iris_treasure", "Iris Taylor", "iris_treasure"),
        ("jack_savings", "Jack Anderson", "jack_savings"),
    ]

    buyers = []
    for i, (uname, full_name, _) in enumerate(buyer_names, 21):
        buyers.append({
            "id": i,
            "username": uname,
            "password": f"buyer{i-20:03d}",
            "name": full_name,
            "email": f"{uname}@email.example.com",
            "role": "buyer",
            "location": rng.choice(SELLER_LOCATIONS),
            "rating": round(4.0 + rng.random() * 1.0, 1),
            "total_purchases": rng.randint(1, 100),
            "member_since": f"{rng.randint(2019, 2025)}-{rng.randint(1,12):02d}",
            "saved_listings": [],
            "watchlist": [],
            "followed_sellers": [],
        })

    all_users = sellers + buyers
    buyer_ids = [b["id"] for b in buyers]

    # Generate products/listings
    products = []
    all_bids = []
    bid_counter = 0

    # Flatten all product templates
    all_templates = []
    for cat, templates in PRODUCT_TEMPLATES.items():
        for t in templates:
            all_templates.append((cat, t))

    # Sample 150 products
    rng.shuffle(all_templates)
    selected = []
    while len(selected) < 150:
        selected.extend(all_templates)
    selected = selected[:150]

    for idx, (category, (name, min_price, max_price)) in enumerate(selected, 1):
        brand = rng.choice(BRANDS)
        condition = rng.choice(CONDITION_OPTIONS)
        seller = rng.choice(sellers)
        shipping = rng.choice(SHIPPING_OPTIONS)

        start_price = round(min_price + rng.random() * (max_price - min_price) * 0.3, 2)

        # Deterministic auction timing based on index
        # Some ended, some active, some starting soon
        if idx % 5 == 0:
            # Ended auctions (20%)
            auction_start = base_date + timedelta(days=rng.randint(0, 7))
            auction_end = now - timedelta(hours=rng.randint(1, 72))
            status = "ended"
        elif idx % 5 == 4:
            # Starting soon (20%)
            auction_start = now + timedelta(hours=rng.randint(1, 48))
            auction_end = auction_start + timedelta(days=rng.randint(3, 10))
            status = "scheduled"
        else:
            # Active auctions (60%)
            auction_start = base_date + timedelta(days=rng.randint(0, 10))
            auction_end = now + timedelta(hours=rng.randint(1, 168))
            status = "active"

        # Deterministic bid count: based on seed and index
        bid_seed = (SEED * 31 + idx * 17) % 100
        if status == "scheduled":
            num_bids = 0
        elif status == "ended":
            num_bids = 3 + bid_seed % 15
        else:
            num_bids = bid_seed % 12

        # Current price progression
        if num_bids > 0:
            price_multiplier = 1.0 + (num_bids * 0.08) + (bid_seed % 5) * 0.05
            current_price = round(start_price * price_multiplier, 2)
            current_price = min(current_price, max_price * 1.2)
        else:
            current_price = start_price

        # Generate bid history
        listing_bids = _generate_bid_history(
            idx, start_price, current_price, num_bids,
            seller["id"], buyer_ids, auction_start
        )
        # Re-number bids globally
        for b in listing_bids:
            bid_counter += 1
            b["bid_id"] = bid_counter
        all_bids.extend(listing_bids)

        winner_id = listing_bids[-1]["bidder_id"] if listing_bids and status == "ended" else None

        # ASIN-like identifier
        asin = f"B{idx:09d}"

        description = _generate_description(name, category, brand, condition)

        # Color/size options
        color_options = rng.sample(["Black", "White", "Red", "Blue", "Green", "Silver", "Gold"], k=rng.randint(1, 4))
        size_options = []
        if category == "Clothing":
            size_options = rng.sample(["S", "M", "L", "XL", "XXL"], k=rng.randint(2, 4))

        # Pick an image URL from WebShop data (cycling through available images)
        product_image_url = webshop_images[(idx - 1) % len(webshop_images)] if webshop_images else None

        product = {
            "id": idx,
            "asin": asin,
            "name": f"{brand} {name}" if rng.random() > 0.3 else name,
            "image_url": product_image_url,
            "category": category,
            "brand": brand,
            "condition": condition,
            "description": description,
            "start_price": start_price,
            "current_price": current_price,
            "buy_now_price": round(max_price * (0.9 + rng.random() * 0.3), 2) if rng.random() > 0.5 else None,
            "reserve_price": round(start_price * 1.5, 2) if rng.random() > 0.7 else None,
            "num_bids": num_bids,
            "seller_id": seller["id"],
            "seller_username": seller["username"],
            "seller_rating": seller["rating"],
            "auction_start": auction_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "auction_end": auction_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status": status,
            "winner_id": winner_id,
            "shipping": shipping,
            "location": seller["location"],
            "views": rng.randint(5, 500),
            "watchers": rng.randint(0, 30),
            "color_options": color_options,
            "size_options": size_options,
            "return_policy": rng.choice(["30-day returns", "14-day returns", "No returns", "60-day returns"]),
            "payment_methods": ["Credit Card", "PayPal"] + (["Bitcoin"] if rng.random() > 0.8 else []),
        }
        products.append(product)

    # Generate messages
    messages = []
    msg_templates = [
        "Hi, is this item still available?",
        "Can you provide more photos?",
        "Would you accept a lower price?",
        "What is the exact condition?",
        "Does this come with original packaging?",
        "Can you ship internationally?",
        "Is the price negotiable?",
        "How soon can you ship?",
        "Any scratches or defects?",
        "Can you combine shipping with another item?",
    ]
    for i in range(50):
        sender = rng.choice(buyers)
        listing = rng.choice(products)
        messages.append({
            "id": i + 1,
            "listing_id": listing["id"],
            "sender_id": sender["id"],
            "receiver_id": listing["seller_id"],
            "subject": f"Question about: {listing['name'][:40]}",
            "body": rng.choice(msg_templates),
            "timestamp": (base_date + timedelta(hours=rng.randint(0, 336))).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "read": rng.random() > 0.4,
        })

    # Reports
    reports = []

    # Ratings
    ratings = []
    for i in range(40):
        buyer = rng.choice(buyers)
        seller = rng.choice(sellers)
        listing = rng.choice([p for p in products if p["status"] == "ended"])
        ratings.append({
            "id": i + 1,
            "listing_id": listing["id"],
            "rater_id": buyer["id"],
            "rated_user_id": seller["id"],
            "score": rng.randint(1, 5),
            "comment": rng.choice([
                "Great seller, fast shipping!",
                "Item as described. Good transaction.",
                "Took a while to ship but item was good.",
                "Excellent condition, very happy!",
                "Average experience, nothing special.",
                "Item had minor issues not mentioned in listing.",
                "Would buy from again!",
                "Perfect transaction!",
            ]),
            "timestamp": (base_date + timedelta(hours=rng.randint(168, 336))).strftime("%Y-%m-%dT%H:%M:%SZ"),
        })

    # Watchlist data (empty, users add to it)
    watchlist = []

    # Write data files
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PRISTINE_DIR.mkdir(parents=True, exist_ok=True)

    files = {
        "products.json": products,
        "users.json": all_users,
        "bids.json": all_bids,
        "messages.json": messages,
        "reports.json": reports,
        "ratings.json": ratings,
        "watchlist.json": watchlist,
    }

    for fname, data in files.items():
        path = DATA_DIR / fname
        path.write_text(json.dumps(data, indent=2))
        # Pristine copies of mutable files
        pristine = PRISTINE_DIR / fname
        pristine.write_text(json.dumps(data, indent=2))

    print(f"Generated {len(products)} products, {len(all_users)} users, "
          f"{len(all_bids)} bids, {len(messages)} messages, {len(ratings)} ratings")
    print(f"Categories: {sorted(set(p['category'] for p in products))}")
    statuses = {}
    for p in products:
        statuses[p["status"]] = statuses.get(p["status"], 0) + 1
    print(f"Statuses: {statuses}")


if __name__ == "__main__":
    generate()
