#!/usr/bin/env python3
"""Generate placeholder images for MiniWeb sites using OpenAI's image generation API.

Reads image_manifest.json (built by scanning data_sources/), generates images
with contextual prompts, saves to app/static/generated/, and updates the JSON
data files to point to the new local paths.

Usage:
    # Generate all images (dry run — shows prompts without calling API)
    python scripts/generate_images.py --dry-run

    # Generate all images
    python scripts/generate_images.py

    # Generate only avatars
    python scripts/generate_images.py --type avatar

    # Generate for a specific site
    python scripts/generate_images.py --site banking

    # Resume from where you left off (skips existing files)
    python scripts/generate_images.py --resume

    # Limit number of images (for testing)
    python scripts/generate_images.py --limit 5

Costs (gpt-image-1, 1024x1024):
    ~$0.04 per image
    339 images ≈ $14 total
"""

import argparse
import base64
import hashlib
import json
import os
import pathlib
import sys
import time

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent

# Load .env if it exists
_env_file = PROJECT_ROOT / ".env"
if _env_file.exists():
    with open(_env_file) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line.startswith("export "):
                _line = _line[7:]
            if "=" in _line and not _line.startswith("#"):
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

MANIFEST_PATH = PROJECT_ROOT / "scripts" / "image_manifest.json"
OUTPUT_DIR = PROJECT_ROOT / "app" / "static" / "generated"
DATA_SOURCES = pathlib.Path(
    os.environ.get("MINIWEB_DATA_SOURCES", "/scratch/general/vast/u1653932/data_sources")
)

# ---------------------------------------------------------------------------
# Prompt templates by image type
# ---------------------------------------------------------------------------

def _classify_image(entry):
    """Classify an image entry into a generation category."""
    field = entry["field"].lower()
    site = entry["site"]

    if "avatar" in field or "profile" in field:
        return "avatar"
    if "thumbnail" in field:
        if site in ("video", "live"):
            return "video_thumbnail"
        return "thumbnail"
    if "logo" in field or "icon" in field:
        return "icon"
    if "cover" in field or "banner" in field:
        return "cover"
    if "photo" in field:
        if site == "dating":
            return "dating_photo"
        if site == "rating-review":
            return "business_photo"
        return "photo"
    if site == "news":
        return "news_image"
    if site == "blogs":
        return "blog_image"
    if site in ("ticketing-events",):
        return "event_image"
    if site in ("auctions-p2p-marketplaces", "e-commerce"):
        return "product_image"
    return "generic"


def _build_prompt(entry, category):
    """Build a contextual prompt for image generation."""
    site = entry["site"]
    item_id = str(entry.get("item_id", ""))

    base_prompts = {
        "avatar": (
            "Professional headshot portrait photo of a person for a web profile. "
            "Clean background, natural lighting, friendly expression. "
            "Photorealistic, high quality. No text or watermarks."
        ),
        "video_thumbnail": (
            f"YouTube-style video thumbnail for a video. "
            "Vibrant colors, engaging composition. "
            "Clean, modern design. No text overlay."
        ),
        "thumbnail": (
            "Clean thumbnail image for web content. "
            "Modern, minimal design with soft colors. No text."
        ),
        "icon": (
            "Simple flat icon design on white background. "
            "Minimal, clean, single color accent. Vector style."
        ),
        "cover": (
            "Wide banner/cover image for a web page. "
            "Abstract gradient or landscape, modern and clean. "
            "Aspect ratio 3:1. No text."
        ),
        "dating_photo": (
            "Casual lifestyle photo of a young adult outdoors. "
            "Natural lighting, candid feel, attractive composition. "
            "Photorealistic. No text."
        ),
        "business_photo": (
            "Photo of a local business storefront or interior. "
            "Well-lit, inviting atmosphere. "
            "Photorealistic, no people as main subject. No text."
        ),
        "news_image": (
            "News article header image. Photojournalistic style, "
            "relevant to current events or local community. "
            "Clean composition. No text overlay."
        ),
        "blog_image": (
            "Blog post header image. Modern, artistic, "
            "relevant to technology or lifestyle. "
            "Clean composition. No text."
        ),
        "event_image": (
            "Event poster or venue photo for a local event. "
            "Vibrant, energetic atmosphere. "
            "Concert, festival, or community gathering feel. No text."
        ),
        "product_image": (
            "Product photo on clean white background. "
            "Well-lit, professional e-commerce style. "
            "Single product, centered. No text."
        ),
        "photo": (
            "Clean, modern photograph. "
            "Good composition, natural lighting. No text."
        ),
        "generic": (
            "Clean placeholder image for a website. "
            "Modern, minimal design. Soft colors. No text or watermarks."
        ),
    }

    prompt = base_prompts.get(category, base_prompts["generic"])

    # Add site-specific context
    site_context = {
        "banking": "Related to personal banking or finance.",
        "brokerage": "Related to stock market or investing.",
        "restaurants": "Related to a restaurant or dining.",
        "dating": "For a dating app profile.",
        "news": "For a news article.",
        "blogs": "For a blog post.",
        "ticketing-events": "For a local event in a small city.",
        "live": "For a live streaming platform.",
        "video": "For a video sharing platform.",
        "multimedia-posting": "For a social media post.",
        "sports-esports": "Related to sports or esports.",
        "music": "Related to music.",
        "health-fitness-tracking": "Related to fitness or health tracking.",
        "rating-review": "For a local business review.",
        "map-services": "For a location or map point of interest.",
    }
    if site in site_context:
        prompt += " " + site_context[site]

    return prompt


def _image_filename(entry):
    """Generate a deterministic filename from the entry."""
    key = f"{entry['site']}_{entry['file']}_{entry['field']}_{entry['item_id']}"
    h = hashlib.md5(key.encode()).hexdigest()[:12]
    return f"{entry['site']}_{h}.png"


# ---------------------------------------------------------------------------
# Image generation
# ---------------------------------------------------------------------------

def generate_image(prompt, output_path, size="1024x1024", quality="low", model="gpt-image-1"):
    """Generate an image using OpenAI's API and save to disk."""
    from openai import OpenAI
    client = OpenAI()

    response = client.images.generate(
        model=model,
        prompt=prompt,
        n=1,
        size=size,
        quality=quality,
    )

    # gpt-image-1 returns base64
    image_data = response.data[0]
    if hasattr(image_data, 'b64_json') and image_data.b64_json:
        img_bytes = base64.b64decode(image_data.b64_json)
        output_path.write_bytes(img_bytes)
    elif hasattr(image_data, 'url') and image_data.url:
        import urllib.request
        urllib.request.urlretrieve(image_data.url, str(output_path))
    else:
        raise ValueError("No image data in response")

    return output_path


def update_data_file(entry, new_url):
    """Update the source JSON data file to point to the generated image."""
    data_path = DATA_SOURCES / entry["site"] / entry["file"]
    if not data_path.exists():
        return False

    try:
        data = json.loads(data_path.read_text())
    except (json.JSONDecodeError, OSError):
        return False

    old_val = entry["current_value"]
    updated = False

    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            val = item.get(entry["field"])
            if val == old_val:
                item[entry["field"]] = new_url
                updated = True
            elif isinstance(val, list) and old_val in val:
                item[entry["field"]] = [new_url if v == old_val else v for v in val]
                updated = True
    elif isinstance(data, dict):
        if data.get(entry["field"]) == old_val:
            data[entry["field"]] = new_url
            updated = True

    if updated:
        data_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        # Also update pristine
        pristine = data_path.parent / ".pristine" / data_path.name
        if pristine.parent.exists():
            pristine.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    return updated


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true",
                        help="Show prompts without calling the API")
    parser.add_argument("--type", type=str, default="",
                        help="Only generate a specific type (avatar, thumbnail, icon, etc.)")
    parser.add_argument("--site", type=str, default="",
                        help="Only generate for a specific site")
    parser.add_argument("--resume", action="store_true",
                        help="Skip images that already exist on disk")
    parser.add_argument("--limit", type=int, default=0,
                        help="Max number of images to generate (0=all)")
    parser.add_argument("--size", type=str, default="1024x1024",
                        choices=["1024x1024", "512x512", "256x256"],
                        help="Image size (default: 1024x1024)")
    parser.add_argument("--quality", type=str, default="low",
                        choices=["low", "medium", "high"],
                        help="Image quality (default: low, cheapest)")
    parser.add_argument("--update-data", action="store_true",
                        help="Update JSON data files to point to generated images")
    args = parser.parse_args()

    if not MANIFEST_PATH.exists():
        print(f"ERROR: {MANIFEST_PATH} not found. Run the manifest builder first.")
        sys.exit(1)

    manifest = json.loads(MANIFEST_PATH.read_text())
    print(f"Loaded {len(manifest)} images from manifest")

    # Filter
    if args.type:
        manifest = [e for e in manifest if _classify_image(e) == args.type]
        print(f"Filtered to {len(manifest)} '{args.type}' images")
    if args.site:
        manifest = [e for e in manifest if e["site"] == args.site]
        print(f"Filtered to {len(manifest)} images for site '{args.site}'")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    generated = 0
    skipped = 0
    errors = 0
    cost_estimate = 0.0

    for i, entry in enumerate(manifest):
        if args.limit and generated >= args.limit:
            break

        category = _classify_image(entry)
        filename = _image_filename(entry)
        output_path = OUTPUT_DIR / filename
        url_path = f"/static/generated/{filename}"

        # Skip if already exists
        if args.resume and output_path.exists():
            skipped += 1
            continue

        prompt = _build_prompt(entry, category)

        if args.dry_run:
            print(f"[{i+1}/{len(manifest)}] {entry['site']}/{entry['field']} ({category})")
            print(f"  Prompt: {prompt[:100]}...")
            print(f"  Output: {filename}")
            cost_estimate += 0.04
            generated += 1
            continue

        # Generate
        print(f"[{i+1}/{len(manifest)}] Generating {filename} ({category})...", end=" ", flush=True)
        try:
            generate_image(prompt, output_path, size=args.size, quality=args.quality)
            generated += 1
            print("OK")

            # Update data file
            if args.update_data:
                if update_data_file(entry, url_path):
                    print(f"  Updated {entry['site']}/{entry['file']}")

            # Rate limiting (avoid hitting API limits)
            time.sleep(1)

        except Exception as e:
            errors += 1
            print(f"ERROR: {e}")
            time.sleep(2)

    print(f"\nDone: {generated} generated, {skipped} skipped, {errors} errors")
    if args.dry_run:
        print(f"Estimated cost: ${cost_estimate:.2f} ({generated} images × $0.04)")


if __name__ == "__main__":
    main()
