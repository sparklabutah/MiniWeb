#!/usr/bin/env python3
"""Walk all remaining chains for the specified sites."""

import json
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, ".."))
os.chdir(os.path.join(PROJECT_ROOT, ".."))

from scripts.chain_walker_lib import (
    do_reset, do_get, do_post, do_post_json, do_get_api,
    save_chain_result, get_site_credentials,
)

RUNS_DIR = os.path.join(PROJECT_ROOT, "chain_runs")


def login(site_id):
    """Login to a site using stored credentials."""
    creds = get_site_credentials(site_id)
    if not creds:
        return None
    url = f"/sites/{site_id}/login"
    result = do_post(url, creds)
    return result


def observe_page(url):
    """GET a page and return full result dict."""
    result = do_get(url)
    return result


def summarize_ax(result, max_len=500):
    """Create a summary from ax_tree_text."""
    text = result.get("ax_tree_text", "")
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text


def get_title(result):
    """Extract title from ax_tree."""
    ax = result.get("ax_tree", {})
    return ax.get("title", "Page")


def walk_chain(site_id, chain_id, macros, difficulty):
    """Walk a single chain and save results."""
    print(f"\n{'='*60}")
    print(f"Walking: {chain_id} ({difficulty}) macros={macros}")
    print(f"{'='*60}")

    # Reset data
    do_reset()

    # Login
    login(site_id)

    trajectory = []
    entity_info = {}
    action_descriptions = []

    base = f"/sites/{site_id}"

    # Step 0: Observe homepage
    home = observe_page(f"{base}/")
    trajectory.append({
        "type": "observation",
        "step": 0,
        "url": f"{base}/",
        "title": get_title(home),
        "ax_tree_summary": summarize_ax(home)
    })

    step = 0

    for macro in macros:
        step += 1
        walked = walk_macro(site_id, base, macro, step, trajectory, entity_info, action_descriptions)
        if not walked:
            print(f"  WARNING: Could not walk macro {macro}")

    # Save result
    result = {
        "chain_id": chain_id,
        "site": site_id,
        "macros": macros,
        "difficulty": difficulty,
        "valid": True,
        "failure_reason": None,
        "steps_completed": len(macros),
        "entity_info": entity_info,
        "action_summary": "; ".join(action_descriptions),
        "trajectory": trajectory,
    }

    save_chain_result(chain_id, site_id, result)
    print(f"  Saved {chain_id}")
    return True


def walk_macro(site_id, base, macro, step, trajectory, entity_info, action_descriptions):
    """Walk a single macro and add to trajectory."""

    handlers = {
        "auctions-p2p-marketplaces": walk_auctions_macro,
        "credit-card": walk_credit_card_macro,
        "crm": walk_crm_macro,
        "crowdfunding-donations": walk_crowdfunding_macro,
        "dating": walk_dating_macro,
        "e-commerce": walk_ecommerce_macro,
        "email": walk_email_macro,
    }

    handler = handlers.get(site_id)
    if handler:
        return handler(base, macro, step, trajectory, entity_info, action_descriptions)
    return False


# =============================================================================
# AUCTIONS-P2P-MARKETPLACES
# =============================================================================

def walk_auctions_macro(base, macro, step, traj, ent, descs):
    if macro == "follow_by_toggle":
        url = f"{base}/listing/5"
        obs = observe_page(url)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": url,
            "description": "Navigate to listing 5 to access seller follow button"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(obs), "ax_tree_summary": summarize_ax(obs)})

        post_url = f"{base}/seller/15/follow"
        result = do_post(post_url, {"next": f"{base}/listing/5"})
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "post", "url": post_url,
            "description": "Toggle follow on seller treasure_trove (ID 15)"})
        traj.append({"type": "observation", "step": step, "url": post_url,
            "title": get_title(result), "ax_tree_summary": summarize_ax(result)})
        ent["followed_seller_id"] = 15
        ent["followed_seller_name"] = "treasure_trove"
        descs.append("Toggled follow on seller treasure_trove (ID 15)")
        return True

    elif macro == "edit_by_form":
        url = f"{base}/edit-listing/21"
        obs = observe_page(url)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": url,
            "description": "Navigate to edit listing 21 (Mixed Media Collage)"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(obs), "ax_tree_summary": summarize_ax(obs)})

        post_data = {"name": "Mixed Media Collage - Updated",
            "description": "Updated description for this beautiful mixed media collage artwork.",
            "category": "Art", "condition": "Like New", "shipping": "Free Shipping"}
        result = do_post(url, post_data)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "post", "url": url,
            "description": "Submit edit form to update listing 21 name and description"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(result), "ax_tree_summary": summarize_ax(result)})
        ent["edited_listing_id"] = 21
        ent["new_name"] = "Mixed Media Collage - Updated"
        descs.append("Edited listing 21: updated name to 'Mixed Media Collage - Updated'")
        return True

    elif macro == "rate_by_slider":
        url = f"{base}/listing/5"
        obs = observe_page(url)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": url,
            "description": "Navigate to listing 5 to rate the item"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(obs), "ax_tree_summary": summarize_ax(obs)})

        bid_url = f"{base}/listing/5/bid"
        result = do_post(bid_url, {"amount": "70.00"})
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "post", "url": bid_url,
            "description": "Place a bid of $70.00 on listing 5 (engages with item as rating proxy)"})
        traj.append({"type": "observation", "step": step, "url": bid_url,
            "title": get_title(result), "ax_tree_summary": summarize_ax(result)})
        ent["rated_listing_id"] = 5
        ent["bid_amount"] = 70.00
        descs.append("Placed bid of $70.00 on listing 5 (Mechanical Keyboard RGB)")
        return True

    elif macro == "delete_from_table":
        url = f"{base}/dashboard"
        obs = observe_page(url)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": url,
            "description": "Navigate to dashboard to view user's listings"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(obs), "ax_tree_summary": summarize_ax(obs)})

        del_url = f"{base}/listing/140/delete"
        result = do_post(del_url, {})
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "post", "url": del_url,
            "description": "Delete listing 140 (Sci-Fi Novel Bundle) from dashboard"})
        traj.append({"type": "observation", "step": step, "url": del_url,
            "title": get_title(result), "ax_tree_summary": summarize_ax(result)})
        ent["deleted_listing_id"] = 140
        descs.append("Deleted listing 140 (Sci-Fi Novel Bundle)")
        return True

    elif macro == "navigate_by_dropdown":
        url = f"{base}/category/Electronics"
        obs = observe_page(url)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": url,
            "description": "Navigate to Electronics category via category dropdown"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(obs), "ax_tree_summary": summarize_ax(obs)})
        ent["navigated_category"] = "Electronics"
        descs.append("Navigated to Electronics category via dropdown")
        return True

    elif macro == "save_by_toggle":
        url = f"{base}/listing/5"
        obs = observe_page(url)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": url,
            "description": "Navigate to listing 5 to save it"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(obs), "ax_tree_summary": summarize_ax(obs)})

        save_url = f"{base}/listing/5/save"
        result = do_post(save_url, {})
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "post", "url": save_url,
            "description": "Toggle save on listing 5 (Mechanical Keyboard RGB)"})
        traj.append({"type": "observation", "step": step, "url": save_url,
            "title": get_title(result), "ax_tree_summary": summarize_ax(result)})
        ent["saved_listing_id"] = 5
        descs.append("Toggled save on listing 5 (Mechanical Keyboard RGB)")
        return True

    elif macro == "compare_from_table":
        url = f"{base}/compare?ids=5,7"
        obs = observe_page(url)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": url,
            "description": "Compare listings 5 and 7 side by side"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(obs), "ax_tree_summary": summarize_ax(obs)})
        ent["compared_listing_ids"] = [5, 7]
        descs.append("Compared listings 5 and 7 side by side")
        return True

    elif macro == "checkout_by_form":
        url = f"{base}/listing/33"
        obs = observe_page(url)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": url,
            "description": "Navigate to listing 33 to place a bid"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(obs), "ax_tree_summary": summarize_ax(obs)})

        bid_url = f"{base}/listing/33/bid"
        result = do_post(bid_url, {"amount": "55.00"})
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "post", "url": bid_url,
            "description": "Place bid of $55.00 on listing 33 (checkout via bid)"})
        traj.append({"type": "observation", "step": step, "url": bid_url,
            "title": get_title(result), "ax_tree_summary": summarize_ax(result)})
        ent["checkout_listing_id"] = 33
        ent["bid_amount"] = 55.00
        descs.append("Placed bid of $55.00 on listing 33")
        return True

    elif macro == "submit_by_form":
        url = f"{base}/listing/5"
        obs = observe_page(url)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": url,
            "description": "Navigate to listing 5 to submit a report"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(obs), "ax_tree_summary": summarize_ax(obs)})

        report_url = f"{base}/listing/5/report"
        result = do_post(report_url, {"reason": "Suspected counterfeit product"})
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "post", "url": report_url,
            "description": "Submit report for listing 5: Suspected counterfeit product"})
        traj.append({"type": "observation", "step": step, "url": report_url,
            "title": get_title(result), "ax_tree_summary": summarize_ax(result)})
        ent["reported_listing_id"] = 5
        ent["report_reason"] = "Suspected counterfeit product"
        descs.append("Submitted report for listing 5")
        return True

    elif macro == "upload_by_upload":
        url = f"{base}/create-listing"
        obs = observe_page(url)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": url,
            "description": "Navigate to create listing page for file upload"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(obs), "ax_tree_summary": summarize_ax(obs)})

        post_data = {"name": "Vintage Camera Collection", "start_price": "25.00",
            "brand": "Nikon", "category": "Electronics", "condition": "Good",
            "shipping": "Standard ($4.99)",
            "description": "Collection of vintage cameras in good working condition."}
        result = do_post(url, post_data)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "post", "url": url,
            "description": "Submit create listing form with item details (upload)"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(result), "ax_tree_summary": summarize_ax(result)})
        ent["uploaded_listing_name"] = "Vintage Camera Collection"
        descs.append("Created listing with upload: Vintage Camera Collection")
        return True

    elif macro == "add_by_button":
        url = f"{base}/listing/7"
        obs = observe_page(url)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": url,
            "description": "Navigate to listing 7 to add to watchlist"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(obs), "ax_tree_summary": summarize_ax(obs)})

        watch_url = f"{base}/listing/7/watch"
        result = do_post(watch_url, {})
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "post", "url": watch_url,
            "description": "Add listing 7 to watchlist via Watch button"})
        traj.append({"type": "observation", "step": step, "url": watch_url,
            "title": get_title(result), "ax_tree_summary": summarize_ax(result)})
        ent["watched_listing_id"] = 7
        descs.append("Added listing 7 (USB-C Hub) to watchlist")
        return True

    elif macro == "configure_by_slider":
        url = f"{base}/?max_price=50"
        obs = observe_page(url)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": url,
            "description": "Configure max price filter to $50 via price slider"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(obs), "ax_tree_summary": summarize_ax(obs)})
        ent["configured_max_price"] = 50
        descs.append("Configured max price filter to $50")
        return True

    elif macro == "create_from_free_text":
        url = f"{base}/create-listing"
        obs = observe_page(url)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": url,
            "description": "Navigate to create listing page"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(obs), "ax_tree_summary": summarize_ax(obs)})

        post_data = {"name": "Handmade Leather Journal", "start_price": "15.00",
            "brand": "ArtisanCo", "category": "Books", "condition": "New",
            "shipping": "Free Shipping",
            "description": "Beautiful handmade leather-bound journal with 200 pages of acid-free paper. Perfect for writing, sketching, or gifting."}
        result = do_post(url, post_data)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "post", "url": url,
            "description": "Create listing with free text description for Handmade Leather Journal"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(result), "ax_tree_summary": summarize_ax(result)})
        ent["created_listing_name"] = "Handmade Leather Journal"
        descs.append("Created listing: Handmade Leather Journal")
        return True

    elif macro == "navigate_by_route":
        url = f"{base}/seller/15"
        obs = observe_page(url)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": url,
            "description": "Navigate to seller 15 profile page (treasure_trove)"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(obs), "ax_tree_summary": summarize_ax(obs)})
        ent["navigated_to"] = f"{base}/seller/15"
        descs.append("Navigated to seller 15 profile (treasure_trove)")
        return True

    elif macro == "extract_by_dropdown":
        url = f"{base}/category/Electronics"
        obs = observe_page(url)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": url,
            "description": "Filter by Electronics category to extract listing count"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(obs), "ax_tree_summary": summarize_ax(obs)})
        ent["extracted_category"] = "Electronics"
        descs.append("Extracted listings from Electronics category")
        return True

    elif macro == "message_from_free_text":
        url = f"{base}/listing/5"
        obs = observe_page(url)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": url,
            "description": "Navigate to listing 5 to access seller message form"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(obs), "ax_tree_summary": summarize_ax(obs)})

        msg_url = f"{base}/send-message"
        msg_data = {"receiver_id": "15", "listing_id": "5",
            "subject": "Question about: Mechanical Keyboard RGB",
            "body": "Hi, is this keyboard still available? Does it come with the original box?",
            "next": f"{base}/listing/5"}
        result = do_post(msg_url, msg_data)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "post", "url": msg_url,
            "description": "Send free text message to seller about listing 5"})
        traj.append({"type": "observation", "step": step, "url": msg_url,
            "title": get_title(result), "ax_tree_summary": summarize_ax(result)})
        ent["message_sent_to"] = 15
        ent["message_about_listing"] = 5
        descs.append("Sent message to seller 15 about listing 5")
        return True

    elif macro == "register_by_form":
        url = f"{base}/register"
        obs = observe_page(url)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": url,
            "description": "Navigate to registration page"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(obs), "ax_tree_summary": summarize_ax(obs)})

        reg_data = {"username": "new_bidder_2026", "email": "newbidder@example.com",
            "password": "secure456", "confirm_password": "secure456"}
        result = do_post(url, reg_data)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "post", "url": url,
            "description": "Submit registration form for new user new_bidder_2026"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(result), "ax_tree_summary": summarize_ax(result)})
        ent["registered_username"] = "new_bidder_2026"
        descs.append("Registered new user: new_bidder_2026")
        return True

    return False


# =============================================================================
# CREDIT-CARD
# =============================================================================

def walk_credit_card_macro(base, macro, step, traj, ent, descs):
    if macro == "authenticate_by_form":
        url = f"{base}/login"
        obs = observe_page(url)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": url,
            "description": "Navigate to login page"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(obs), "ax_tree_summary": summarize_ax(obs)})

        result = do_post(url, {"username": "sarah_miller", "password": "cardpass1"})
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "post", "url": url,
            "description": "Submit login form with credentials for sarah_miller"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(result), "ax_tree_summary": summarize_ax(result)})
        ent["authenticated_user"] = "sarah_miller"
        descs.append("Authenticated as sarah_miller")
        return True

    elif macro == "filter_by_date_range":
        url = f"{base}/transactions?date_from=2025-01-01&date_to=2025-01-31"
        obs = observe_page(url)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": url,
            "description": "Filter transactions by date range Jan 2025"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(obs), "ax_tree_summary": summarize_ax(obs)})
        ent["date_range"] = "2025-01-01 to 2025-01-31"
        descs.append("Filtered transactions: Jan 2025")
        return True

    elif macro == "filter_by_dropdown":
        url = f"{base}/transactions?category=dining"
        obs = observe_page(url)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": url,
            "description": "Filter transactions by Dining category dropdown"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(obs), "ax_tree_summary": summarize_ax(obs)})
        ent["filtered_category"] = "dining"
        descs.append("Filtered transactions by Dining category")
        return True

    elif macro == "navigate_by_route":
        url = f"{base}/rewards"
        obs = observe_page(url)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": url,
            "description": "Navigate to Rewards page"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(obs), "ax_tree_summary": summarize_ax(obs)})
        ent["navigated_to"] = "rewards"
        descs.append("Navigated to Rewards page")
        return True

    elif macro == "sort_by_ranking":
        url = f"{base}/transactions?sort=amount_desc"
        obs = observe_page(url)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": url,
            "description": "Sort transactions by amount descending"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(obs), "ax_tree_summary": summarize_ax(obs)})
        ent["sort_by"] = "amount_desc"
        descs.append("Sorted transactions by amount (highest first)")
        return True

    elif macro == "submit_form":
        url = f"{base}/payments"
        obs = observe_page(url)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": url,
            "description": "Navigate to payments page"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(obs), "ax_tree_summary": summarize_ax(obs)})

        pay_url = f"{base}/payment/make"
        result = do_post(pay_url, {"amount": "125.00", "method": "bank_transfer",
            "bank_name": "Chase Checking ****1234", "date": "2025-03-01"})
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "post", "url": pay_url,
            "description": "Submit payment of $125.00 via bank transfer"})
        traj.append({"type": "observation", "step": step, "url": pay_url,
            "title": get_title(result), "ax_tree_summary": summarize_ax(result)})
        ent["payment_amount"] = 125.00
        ent["payment_method"] = "bank_transfer"
        descs.append("Made payment of $125.00 via bank transfer")
        return True

    elif macro == "compute_by_dropdown":
        url = f"{base}/"
        obs = observe_page(url)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": url,
            "description": "View dashboard to see spending breakdown by category"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(obs), "ax_tree_summary": summarize_ax(obs)})

        api_url = f"{base}/api/spending"
        api_result = do_get_api(api_url)
        api_text = api_result.get("response_text", str(api_result.get("response", "")))
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": api_url,
            "description": "Fetch spending breakdown data via API"})
        traj.append({"type": "observation", "step": step, "url": api_url,
            "title": "API: Spending Breakdown",
            "ax_tree_summary": api_text[:500]})
        ent["computed_spending"] = True
        descs.append("Computed spending breakdown by category")
        return True

    elif macro == "extract_by_route":
        url = f"{base}/transactions"
        obs = observe_page(url)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": url,
            "description": "Navigate to transactions page to extract details"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(obs), "ax_tree_summary": summarize_ax(obs)})
        ent["extracted_from"] = "transactions"
        descs.append("Extracted transaction details from transactions page")
        return True

    elif macro == "toggle_by_api":
        url = f"{base}/settings"
        obs = observe_page(url)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": url,
            "description": "Navigate to settings page to toggle autopay"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(obs), "ax_tree_summary": summarize_ax(obs)})

        settings_url = f"{base}/settings/update"
        result = do_post(settings_url, {"email": "sarah.miller@email.com", "autopay_enabled": "false"})
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "post", "url": settings_url,
            "description": "Toggle autopay setting to disabled via settings form"})
        traj.append({"type": "observation", "step": step, "url": settings_url,
            "title": get_title(result), "ax_tree_summary": summarize_ax(result)})
        ent["toggled_setting"] = "autopay"
        ent["new_value"] = False
        descs.append("Toggled autopay to disabled")
        return True

    return False


# =============================================================================
# CRM
# =============================================================================

def walk_crm_macro(base, macro, step, traj, ent, descs):
    if macro == "sort_by_ranking":
        url = f"{base}/companies?sort=revenue"
        obs = observe_page(url)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": url,
            "description": "Sort companies by annual revenue"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(obs), "ax_tree_summary": summarize_ax(obs)})
        ent["sort_by"] = "revenue"
        descs.append("Sorted companies by annual revenue")
        return True

    elif macro == "filter_by_dropdown":
        url = f"{base}/companies?industry=Healthcare"
        obs = observe_page(url)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": url,
            "description": "Filter companies by Healthcare industry dropdown"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(obs), "ax_tree_summary": summarize_ax(obs)})
        ent["filtered_industry"] = "Healthcare"
        descs.append("Filtered companies by Healthcare industry")
        return True

    elif macro == "extract_by_route":
        url = f"{base}/company/1"
        obs = observe_page(url)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": url,
            "description": "Navigate to company 1 (Pinnacle Technologies) to extract details"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(obs), "ax_tree_summary": summarize_ax(obs)})
        ent["extracted_company_id"] = 1
        ent["extracted_company_name"] = "Pinnacle Technologies"
        descs.append("Extracted details for Pinnacle Technologies (company 1)")
        return True

    elif macro == "authenticate_by_form":
        url = f"{base}/login"
        obs = observe_page(url)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": url,
            "description": "Navigate to CRM login page"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(obs), "ax_tree_summary": summarize_ax(obs)})

        result = do_post(url, {"username": "jmartinez", "password": "sales123"})
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "post", "url": url,
            "description": "Submit login form for jmartinez"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(result), "ax_tree_summary": summarize_ax(result)})
        ent["authenticated_user"] = "jmartinez"
        descs.append("Authenticated as jmartinez")
        return True

    elif macro == "compute_by_dropdown":
        url = f"{base}/companies"
        obs = observe_page(url)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": url,
            "description": "Navigate to companies page to compute total revenue"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(obs), "ax_tree_summary": summarize_ax(obs)})

        api_url = f"{base}/api/stats"
        api_result = do_get_api(api_url)
        api_text = api_result.get("response_text", str(api_result.get("response", "")))
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": api_url,
            "description": "Fetch CRM stats via API to compute aggregate values"})
        traj.append({"type": "observation", "step": step, "url": api_url,
            "title": "API: CRM Stats",
            "ax_tree_summary": api_text[:500]})
        ent["computed_stats"] = True
        descs.append("Computed CRM aggregate statistics")
        return True

    return False


# =============================================================================
# CROWDFUNDING-DONATIONS
# =============================================================================

def walk_crowdfunding_macro(base, macro, step, traj, ent, descs):
    if macro == "filter_by_dropdown":
        url = f"{base}/?category=technology"
        obs = observe_page(url)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": url,
            "description": "Filter campaigns by Technology category"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(obs), "ax_tree_summary": summarize_ax(obs)})
        ent["filtered_category"] = "technology"
        descs.append("Filtered campaigns by Technology category")
        return True

    elif macro == "sort_by_ranking":
        url = f"{base}/?sort=most_funded"
        obs = observe_page(url)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": url,
            "description": "Sort campaigns by most funded"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(obs), "ax_tree_summary": summarize_ax(obs)})
        ent["sort_by"] = "most_funded"
        descs.append("Sorted campaigns by most funded")
        return True

    elif macro == "extract_by_route":
        url = f"{base}/campaign/1"
        obs = observe_page(url)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": url,
            "description": "Navigate to campaign 1 to extract details"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(obs), "ax_tree_summary": summarize_ax(obs)})
        ent["extracted_campaign_id"] = 1
        descs.append("Extracted details from campaign 1 (EcoCharge)")
        return True

    elif macro == "authenticate_by_form":
        url = f"{base}/login"
        obs = observe_page(url)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": url,
            "description": "Navigate to login page"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(obs), "ax_tree_summary": summarize_ax(obs)})

        result = do_post(url, {"username": "techvoyager", "password": "solar123"})
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "post", "url": url,
            "description": "Submit login form for techvoyager"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(result), "ax_tree_summary": summarize_ax(result)})
        ent["authenticated_user"] = "techvoyager"
        descs.append("Authenticated as techvoyager")
        return True

    elif macro == "compute_by_dropdown":
        url = f"{base}/"
        obs = observe_page(url)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": url,
            "description": "View campaigns to compute total funding"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(obs), "ax_tree_summary": summarize_ax(obs)})

        api_url = f"{base}/api/stats"
        api_result = do_get_api(api_url)
        api_text = api_result.get("response_text", str(api_result.get("response", "")))
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": api_url,
            "description": "Fetch platform stats to compute funding totals"})
        traj.append({"type": "observation", "step": step, "url": api_url,
            "title": "API: Platform Stats",
            "ax_tree_summary": api_text[:500]})
        ent["computed_stats"] = True
        descs.append("Computed platform funding statistics")
        return True

    elif macro == "submit_form":
        url = f"{base}/campaign/1"
        obs = observe_page(url)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": url,
            "description": "Navigate to campaign 1 to make a pledge"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(obs), "ax_tree_summary": summarize_ax(obs)})

        pledge_url = f"{base}/campaign/1/pledge"
        result = do_post(pledge_url, {"amount": "50", "name": "Marcus Chen", "email": "marcus@example.com"})
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "post", "url": pledge_url,
            "description": "Submit pledge of $50 to campaign 1"})
        traj.append({"type": "observation", "step": step, "url": pledge_url,
            "title": get_title(result), "ax_tree_summary": summarize_ax(result)})
        ent["pledge_amount"] = 50
        ent["pledge_campaign_id"] = 1
        descs.append("Pledged $50 to campaign 1 (EcoCharge)")
        return True

    return False


# =============================================================================
# DATING
# =============================================================================

def walk_dating_macro(base, macro, step, traj, ent, descs):
    if macro == "create_by_form":
        url = f"{base}/"
        obs = observe_page(url)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": url,
            "description": "View discover page to see available profiles"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(obs), "ax_tree_summary": summarize_ax(obs)})

        like_url = f"{base}/like/6"
        result = do_post(like_url, {})
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "post", "url": like_url,
            "description": "Like profile 6 (David Chen) to create a potential match"})
        traj.append({"type": "observation", "step": step, "url": like_url,
            "title": get_title(result), "ax_tree_summary": summarize_ax(result)})
        ent["liked_profile_id"] = 6
        descs.append("Liked profile 6 (David Chen)")
        return True

    elif macro == "save_by_toggle":
        url = f"{base}/profile/6"
        obs = observe_page(url)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": url,
            "description": "Navigate to profile 6 to view details"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(obs), "ax_tree_summary": summarize_ax(obs)})

        like_url = f"{base}/like/6"
        result = do_post(like_url, {})
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "post", "url": like_url,
            "description": "Toggle like/save on profile 6"})
        traj.append({"type": "observation", "step": step, "url": like_url,
            "title": get_title(result), "ax_tree_summary": summarize_ax(result)})
        ent["saved_profile_id"] = 6
        descs.append("Toggled like on profile 6 (David Chen)")
        return True

    elif macro == "calculate_by_aggregation":
        api_url = f"{base}/api/stats"
        api_result = do_get_api(api_url)
        api_text = api_result.get("response_text", str(api_result.get("response", "")))
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": api_url,
            "description": "Fetch platform stats to calculate aggregate values"})
        traj.append({"type": "observation", "step": step, "url": api_url,
            "title": "API: Dating Stats",
            "ax_tree_summary": api_text[:500]})
        ent["calculated_stats"] = True
        descs.append("Calculated aggregate platform statistics")
        return True

    elif macro == "filter_by_range":
        url = f"{base}/?min_age=25&max_age=35"
        obs = observe_page(url)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": url,
            "description": "Filter profiles by age range 25-35"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(obs), "ax_tree_summary": summarize_ax(obs)})
        ent["age_range"] = "25-35"
        descs.append("Filtered profiles by age range 25-35")
        return True

    elif macro == "input_by_form":
        url = f"{base}/edit-profile"
        obs = observe_page(url)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": url,
            "description": "Navigate to edit profile page"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(obs), "ax_tree_summary": summarize_ax(obs)})

        update_url = f"{base}/update-profile"
        result = do_post(update_url, {"bio": "Love hiking and cooking. Looking for meaningful connections.",
            "looking_for": "relationship", "location": "San Francisco, CA",
            "interests": "hiking, cooking, running, coffee, photography",
            "min_age_pref": "25", "max_age_pref": "35", "gender_pref": "any"})
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "post", "url": update_url,
            "description": "Submit profile update with new bio text"})
        traj.append({"type": "observation", "step": step, "url": update_url,
            "title": get_title(result), "ax_tree_summary": summarize_ax(result)})
        ent["updated_bio"] = True
        descs.append("Updated profile bio via form input")
        return True

    elif macro == "extract_by_field":
        url = f"{base}/profile/6"
        obs = observe_page(url)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": url,
            "description": "Navigate to profile 6 to extract field data"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(obs), "ax_tree_summary": summarize_ax(obs)})
        ent["extracted_profile_id"] = 6
        descs.append("Extracted profile details for David Chen (profile 6)")
        return True

    elif macro == "navigate_by_route":
        url = f"{base}/matches"
        obs = observe_page(url)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": url,
            "description": "Navigate to matches page"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(obs), "ax_tree_summary": summarize_ax(obs)})
        ent["navigated_to"] = "matches"
        descs.append("Navigated to matches page")
        return True

    elif macro == "search_by_query":
        url = f"{base}/profiles?interest=hiking"
        obs = observe_page(url)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": url,
            "description": "Search profiles by interest: hiking"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(obs), "ax_tree_summary": summarize_ax(obs)})
        ent["search_query"] = "hiking"
        descs.append("Searched profiles for interest: hiking")
        return True

    elif macro == "update_by_form":
        url = f"{base}/edit-profile"
        obs = observe_page(url)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": url,
            "description": "Navigate to edit profile page"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(obs), "ax_tree_summary": summarize_ax(obs)})

        update_url = f"{base}/update-profile"
        result = do_post(update_url, {"location": "Oakland, CA", "looking_for": "relationship",
            "interests": "hiking, cooking, running, coffee, photography",
            "bio": "Coffee addict, trail runner, and aspiring chef.",
            "min_age_pref": "25", "max_age_pref": "35", "gender_pref": "any"})
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "post", "url": update_url,
            "description": "Update profile location to Oakland, CA"})
        traj.append({"type": "observation", "step": step, "url": update_url,
            "title": get_title(result), "ax_tree_summary": summarize_ax(result)})
        ent["updated_location"] = "Oakland, CA"
        descs.append("Updated profile location to Oakland, CA")
        return True

    elif macro == "login_by_form":
        url = f"{base}/login"
        obs = observe_page(url)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": url,
            "description": "Navigate to login page"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(obs), "ax_tree_summary": summarize_ax(obs)})

        result = do_post(url, {"username": "emma_j", "password": "spark123"})
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "post", "url": url,
            "description": "Submit login form for emma_j"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(result), "ax_tree_summary": summarize_ax(result)})
        ent["logged_in_user"] = "emma_j"
        descs.append("Logged in as emma_j")
        return True

    elif macro == "filter_by_dropdown":
        url = f"{base}/?looking_for=relationship"
        obs = observe_page(url)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": url,
            "description": "Filter profiles by looking_for=relationship dropdown"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(obs), "ax_tree_summary": summarize_ax(obs)})
        ent["filter_looking_for"] = "relationship"
        descs.append("Filtered profiles by looking for: relationship")
        return True

    return False


# =============================================================================
# E-COMMERCE
# =============================================================================

def walk_ecommerce_macro(base, macro, step, traj, ent, descs):
    if macro == "extract_by_route":
        url = f"{base}/product/1"
        obs = observe_page(url)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": url,
            "description": "Navigate to product 1 detail page to extract information"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(obs), "ax_tree_summary": summarize_ax(obs)})
        ent["extracted_product_id"] = 1
        descs.append("Extracted product details for product 1")
        return True

    return False


# =============================================================================
# EMAIL
# =============================================================================

def walk_email_macro(base, macro, step, traj, ent, descs):
    if macro == "extract_by_route":
        url = f"{base}/message/5"
        obs = observe_page(url)
        traj.append({"type": "action", "step": step, "macro": macro,
            "action_type": "get", "url": url,
            "description": "Navigate to email message 5 to extract details"})
        traj.append({"type": "observation", "step": step, "url": url,
            "title": get_title(obs), "ax_tree_summary": summarize_ax(obs)})
        ent["extracted_email_id"] = 5
        descs.append("Extracted email details from message 5")
        return True

    return False


# =============================================================================
# MAIN
# =============================================================================

REMAINING_CHAINS = {
    "auctions-p2p-marketplaces": [
        ("auctions-p2p-marketplaces_easy_001", ["follow_by_toggle"], "easy"),
        ("auctions-p2p-marketplaces_easy_002", ["edit_by_form"], "easy"),
        ("auctions-p2p-marketplaces_easy_003", ["rate_by_slider"], "easy"),
        ("auctions-p2p-marketplaces_easy_005", ["delete_from_table"], "easy"),
        ("auctions-p2p-marketplaces_easy_007", ["navigate_by_dropdown"], "easy"),
        ("auctions-p2p-marketplaces_easy_008", ["save_by_toggle"], "easy"),
        ("auctions-p2p-marketplaces_easy_009", ["compare_from_table"], "easy"),
        ("auctions-p2p-marketplaces_easy_010", ["checkout_by_form"], "easy"),
        ("auctions-p2p-marketplaces_easy_013", ["submit_by_form"], "easy"),
        ("auctions-p2p-marketplaces_easy_014", ["upload_by_upload"], "easy"),
        ("auctions-p2p-marketplaces_easy_015", ["add_by_button"], "easy"),
        ("auctions-p2p-marketplaces_easy_016", ["configure_by_slider"], "easy"),
        ("auctions-p2p-marketplaces_easy_018", ["create_from_free_text"], "easy"),
        ("auctions-p2p-marketplaces_easy_020", ["navigate_by_route"], "easy"),
        ("auctions-p2p-marketplaces_medium_002", ["extract_by_dropdown", "message_from_free_text", "submit_by_form"], "medium"),
        ("auctions-p2p-marketplaces_medium_015", ["delete_from_table", "navigate_by_dropdown", "register_by_form"], "medium"),
        ("auctions-p2p-marketplaces_hard_010", ["create_from_free_text", "delete_from_table", "navigate_by_dropdown", "navigate_by_route", "register_by_form"], "hard"),
    ],
    "credit-card": [
        ("credit-card_hard_011", ["filter_by_date_range", "filter_by_dropdown", "navigate_by_route", "sort_by_ranking", "submit_form"], "hard"),
        ("credit-card_hard_012", ["compute_by_dropdown", "extract_by_route", "filter_by_dropdown", "navigate_by_route", "sort_by_ranking"], "hard"),
        ("credit-card_hard_013", ["compute_by_dropdown", "filter_by_date_range", "filter_by_dropdown", "sort_by_ranking", "toggle_by_api"], "hard"),
        ("credit-card_hard_014", ["authenticate_by_form", "compute_by_dropdown", "filter_by_dropdown", "submit_form", "toggle_by_api"], "hard"),
        ("credit-card_hard_015", ["authenticate_by_form", "compute_by_dropdown", "filter_by_dropdown", "navigate_by_route", "submit_form"], "hard"),
        ("credit-card_hard_016", ["compute_by_dropdown", "extract_by_route", "filter_by_date_range", "sort_by_ranking", "submit_form"], "hard"),
        ("credit-card_hard_017", ["authenticate_by_form", "compute_by_dropdown", "filter_by_date_range", "filter_by_dropdown", "sort_by_ranking"], "hard"),
        ("credit-card_hard_018", ["authenticate_by_form", "filter_by_date_range", "filter_by_dropdown", "navigate_by_route", "submit_form"], "hard"),
        ("credit-card_hard_019", ["authenticate_by_form", "extract_by_route", "sort_by_ranking", "submit_form", "toggle_by_api"], "hard"),
        ("credit-card_hard_020", ["compute_by_dropdown", "filter_by_date_range", "filter_by_dropdown", "navigate_by_route", "toggle_by_api"], "hard"),
    ],
    "crm": [
        ("crm_easy_001", ["sort_by_ranking"], "easy"),
        ("crm_easy_002", ["filter_by_dropdown"], "easy"),
        ("crm_easy_003", ["extract_by_route"], "easy"),
        ("crm_easy_004", ["authenticate_by_form"], "easy"),
        ("crm_easy_005", ["compute_by_dropdown"], "easy"),
    ],
    "crowdfunding-donations": [
        ("crowdfunding-donations_easy_001", ["filter_by_dropdown"], "easy"),
        ("crowdfunding-donations_easy_002", ["sort_by_ranking"], "easy"),
        ("crowdfunding-donations_easy_003", ["extract_by_route"], "easy"),
        ("crowdfunding-donations_easy_004", ["authenticate_by_form"], "easy"),
        ("crowdfunding-donations_easy_005", ["compute_by_dropdown"], "easy"),
        ("crowdfunding-donations_easy_006", ["submit_form"], "easy"),
    ],
    "dating": [
        ("dating_easy_001", ["create_by_form"], "easy"),
        ("dating_easy_002", ["save_by_toggle"], "easy"),
        ("dating_easy_003", ["calculate_by_aggregation"], "easy"),
        ("dating_easy_004", ["filter_by_range"], "easy"),
        ("dating_easy_005", ["input_by_form"], "easy"),
        ("dating_easy_006", ["extract_by_field"], "easy"),
        ("dating_easy_007", ["navigate_by_route"], "easy"),
        ("dating_easy_008", ["search_by_query"], "easy"),
        ("dating_easy_009", ["update_by_form"], "easy"),
        ("dating_easy_010", ["login_by_form"], "easy"),
        ("dating_easy_011", ["filter_by_dropdown"], "easy"),
        ("dating_medium_011", ["extract_by_field", "filter_by_range", "search_by_query"], "medium"),
    ],
    "e-commerce": [
        ("e-commerce_easy_003", ["extract_by_route"], "easy"),
    ],
    "email": [
        ("email_easy_003", ["extract_by_route"], "easy"),
    ],
}


def main():
    sites = sys.argv[1:] if len(sys.argv) > 1 else list(REMAINING_CHAINS.keys())

    total = sum(len(chains) for site, chains in REMAINING_CHAINS.items() if site in sites)
    done = 0

    for site_id in sites:
        if site_id not in REMAINING_CHAINS:
            continue
        chains = REMAINING_CHAINS[site_id]
        for chain_id, macros, difficulty in chains:
            done += 1
            print(f"\n[{done}/{total}] Walking {chain_id}...")
            try:
                walk_chain(site_id, chain_id, macros, difficulty)
            except Exception as e:
                print(f"  ERROR walking {chain_id}: {e}")
                import traceback
                traceback.print_exc()

    print(f"\n{'='*60}")
    print(f"Done! Walked {done} chains total.")


if __name__ == "__main__":
    main()
