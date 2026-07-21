"""MiniWeb Task Annotation Interface.

Two modes:
  1. Review Sites — browse each site, leave free-form feedback
  2. Annotate Tasks — system samples N sites × M macros, annotator designs task

The annotation blueprint is registered in the main MiniWeb app.
  Access at http://localhost:8080/annotate/
"""

import json
import os
import random
import uuid
import pickle
from datetime import datetime
from pathlib import Path

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from annotation.macro_locations import MACRO_LOCATIONS
from annotation.storage import ANNOTATIONS_DIR

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SITES_DIR = PROJECT_ROOT / "sites"

# Annotator credentials: override via MINIWEB_ANNOTATORS env var
# Format: "user1:pass1,user2:pass2,..."
_DEFAULT_ANNOTATORS = {"minh": "miniweb", "annotator2": "miniweb", "annotator3": "miniweb", "annotator4": "miniweb"}

def _load_annotator_credentials():
    env = os.environ.get("MINIWEB_ANNOTATORS", "")
    if env:
        creds = {}
        for pair in env.split(","):
            if ":" in pair:
                user, pw = pair.split(":", 1)
                creds[user.strip()] = pw.strip()
        return creds if creds else _DEFAULT_ANNOTATORS
    return _DEFAULT_ANNOTATORS

ANNOTATOR_CREDENTIALS = _load_annotator_credentials()

annotation_bp = Blueprint(
    "annotation",
    __name__,
    template_folder="templates",
    static_folder="static",
    url_prefix="/annotate",
)


# ---------------------------------------------------------------------------
# Macro descriptions — verb + modality + explanation + example
# ---------------------------------------------------------------------------

_MACRO_DESCRIPTIONS = {
    # Navigation
    "navigate_by_route": {"verb": "navigate", "modality": "route", "description": "Go to a specific page by clicking a link or menu item", "example": "Click 'Dashboard' in the sidebar to go to the dashboard page"},
    "navigate_by_semantic": {"verb": "navigate", "modality": "semantic", "description": "Navigate to a page described in natural language", "example": "Find and go to the page that shows your recent orders"},
    "navigate_by_date_range": {"verb": "navigate", "modality": "date range", "description": "Navigate to content within a specific date range", "example": "Go to events for next week using the calendar picker"},
    "navigate_by_pan_zoom": {"verb": "navigate", "modality": "pan/zoom", "description": "Navigate a visual interface by panning or zooming", "example": "Zoom into the downtown area on the map"},
    "navigate_by_query": {"verb": "navigate", "modality": "query", "description": "Navigate by entering a query in a search/address bar", "example": "Type a URL slug in the address bar to go to that page"},
    "navigate_from_table": {"verb": "navigate", "modality": "table", "description": "Click a row in a table to navigate to its detail page", "example": "Click a file name in the file list to open it"},
    # Search
    "search_by_query": {"verb": "search", "modality": "query", "description": "Search using a text query in a search box", "example": "Type 'machine learning' in the search bar and press Enter"},
    "search_by_semantic": {"verb": "search", "modality": "semantic", "description": "Search using natural language or meaning-based query", "example": "Search for 'papers about image recognition' to find relevant results"},
    "search_by_checkbox": {"verb": "search", "modality": "checkbox", "description": "Search by selecting checkboxes to define criteria", "example": "Check 'Python' and 'JavaScript' to find repos using those languages"},
    "search_by_route": {"verb": "search", "modality": "route", "description": "Search by navigating to a search-result URL pattern", "example": "Go to /search?q=einstein to see results for einstein"},
    "search_by_code": {"verb": "search", "modality": "code", "description": "Search using a code, ID, or reference number", "example": "Enter permit number 'LP-2024-001' to find the permit"},
    "search_by_dropdown": {"verb": "search", "modality": "dropdown", "description": "Search by selecting a category from a dropdown", "example": "Select 'Inbox' from the folder dropdown to search within inbox"},
    "search_by_proximity": {"verb": "search", "modality": "proximity", "description": "Search for items near a location", "example": "Search for restaurants within 5 miles of downtown"},
    "search_by_date_range": {"verb": "search", "modality": "date range", "description": "Search by specifying a date range", "example": "Search for flights departing between June 1 and June 15"},
    "search_by_pan_zoom": {"verb": "search", "modality": "pan/zoom", "description": "Search by panning or zooming on a map", "example": "Zoom into the downtown area to find nearby restaurants"},
    # Filter
    "filter_by_dropdown": {"verb": "filter", "modality": "dropdown", "description": "Narrow results by selecting a value from a dropdown", "example": "Select 'Electronics' from the Category dropdown"},
    "filter_by_radio": {"verb": "filter", "modality": "radio", "description": "Filter by selecting a radio button option", "example": "Select 'Credit' radio button to show only credit transactions"},
    "filter_by_checkbox": {"verb": "filter", "modality": "checkbox", "description": "Filter by checking/unchecking checkboxes", "example": "Check 'In Stock' to show only available products"},
    "filter_by_slider": {"verb": "filter", "modality": "slider", "description": "Filter by adjusting a range slider", "example": "Set the price slider from $50 to $200"},
    "filter_by_date_range": {"verb": "filter", "modality": "date range", "description": "Filter results to a specific date range", "example": "Set date range to 'Jan 1 - Mar 31' to see Q1 transactions"},
    "filter_by_query": {"verb": "filter", "modality": "query", "description": "Filter by typing text in a filter input", "example": "Type 'urgent' in the filter box to show only urgent items"},
    "filter_by_semantic": {"verb": "filter", "modality": "semantic", "description": "Filter using a natural language description", "example": "Filter for 'high priority tasks assigned to me'"},
    "filter_by_toggle": {"verb": "filter", "modality": "toggle", "description": "Filter by toggling a switch on/off", "example": "Toggle 'Show completed' to include/exclude done tasks"},
    "filter_by_chip": {"verb": "filter", "modality": "chip", "description": "Filter by clicking tag chips", "example": "Click the 'Vegan' chip to filter menu items"},
    "filter_by_route": {"verb": "filter", "modality": "route", "description": "Filter by navigating to a filtered URL", "example": "Go to /flights?class=business to see business class flights"},
    "filter_by_proximity": {"verb": "filter", "modality": "proximity", "description": "Filter by geographic proximity", "example": "Filter to show only results within 10 miles"},
    # Sort
    "sort_by_ranking": {"verb": "sort", "modality": "ranking", "description": "Sort items by a ranking criterion", "example": "Click 'Price: Low to High' to sort by ascending price"},
    "sort_by_date_range": {"verb": "sort", "modality": "date range", "description": "Sort items by date", "example": "Sort by 'Newest first' to see most recent items"},
    "sort_by_dropdown": {"verb": "sort", "modality": "dropdown", "description": "Sort by selecting an option from a dropdown", "example": "Select 'Most Popular' from the sort dropdown"},
    "sort_by_slider": {"verb": "sort", "modality": "slider", "description": "Sort by adjusting a slider value", "example": "Adjust the relevance slider to re-rank results"},
    "sort_by_toggle": {"verb": "sort", "modality": "toggle", "description": "Toggle sort direction (ascending/descending)", "example": "Click the column header to toggle ascending/descending"},
    "sort_by_extremum": {"verb": "sort", "modality": "extremum", "description": "Sort to find the min/max value", "example": "Sort by price descending to find the most expensive item"},
    "sort_by_proximity": {"verb": "sort", "modality": "proximity", "description": "Sort by geographic distance or proximity", "example": "Sort transit stops by distance from your location"},
    "sort_by_proximity": {"verb": "sort", "modality": "proximity", "description": "Sort by geographic distance or proximity", "example": "Sort transit stops by distance from your location"},
    # Extract
    "extract_by_query": {"verb": "extract", "modality": "query", "description": "Find and extract specific information from the page", "example": "What is the total balance shown on the dashboard?"},
    "extract_by_semantic": {"verb": "extract", "modality": "semantic", "description": "Extract information described in natural language", "example": "Find the author who published the most papers in 2023"},
    "extract_by_dropdown": {"verb": "extract", "modality": "dropdown", "description": "Extract info after selecting a category from dropdown", "example": "Select 'Q1 2024' and report the total revenue shown"},
    "extract_from_table": {"verb": "extract", "modality": "table", "description": "Extract data from a table on the page", "example": "What is the price in the 3rd row of the products table?"},
    "extract_by_route": {"verb": "extract", "modality": "route", "description": "Extract info from a specific page/route", "example": "Go to the user profile and report the email address"},
    "extract_by_ranking": {"verb": "extract", "modality": "ranking", "description": "Extract the item at a specific rank", "example": "What is the title of the #1 trending article?"},
    "extract_by_extremum": {"verb": "extract", "modality": "extremum", "description": "Extract the min or max value from a dataset", "example": "What is the cheapest flight to New York?"},
    "extract_by_slider": {"verb": "extract", "modality": "slider", "description": "Extract value shown at a slider position", "example": "What interest rate is shown when the term slider is at 30 years?"},
    "extract_by_date_range": {"verb": "extract", "modality": "date range", "description": "Extract info from a specific date range", "example": "How many transactions were made in March 2024?"},
    "extract_by_code": {"verb": "extract", "modality": "code", "description": "Extract data using a code or formula", "example": "What is the value of cell B5 in the spreadsheet?"},
    "extract_by_toggle": {"verb": "extract", "modality": "toggle", "description": "Extract info revealed by toggling a UI element", "example": "Expand the 'Details' section and report the serial number"},
    "extract_by_image": {"verb": "extract", "modality": "image", "description": "Extract information from an image", "example": "What text is written on the whiteboard in the image?"},
    "extract_by_checkbox": {"verb": "extract", "modality": "checkbox", "description": "Extract info after applying checkbox filters", "example": "Check 'Active' and report how many users are shown"},
    "extract_from_free_text": {"verb": "extract", "modality": "free text", "description": "Extract info from unstructured text content", "example": "Read the article and identify the main conclusion"},
    # Compute
    "compute_by_dropdown": {"verb": "compute", "modality": "dropdown", "description": "Compute a value after selecting options", "example": "Select 'USD to EUR' and compute the conversion of $500"},
    "compute_by_extremum": {"verb": "compute", "modality": "extremum", "description": "Compute a min/max across items", "example": "Find the highest-rated restaurant with more than 50 reviews"},
    "compute_by_slider": {"verb": "compute", "modality": "slider", "description": "Compute result by adjusting slider inputs", "example": "Set the loan calculator to $200K, 5%, 30yr and report monthly payment"},
    "compute_by_query": {"verb": "compute", "modality": "query", "description": "Compute an answer from queried data", "example": "Calculate the total cost of items in the cart"},
    "compute_from_table": {"verb": "compute", "modality": "table", "description": "Compute from tabular data", "example": "Sum the values in the 'Amount' column"},
    "compute_by_route": {"verb": "compute", "modality": "route", "description": "Compute from data on a specific route", "example": "Go to analytics page and calculate year-over-year growth"},    # Compare
    "compare_by_dropdown": {"verb": "compare", "modality": "dropdown", "description": "Compare items selected from dropdowns", "example": "Compare iPhone 15 vs Samsung S24 specs side by side"},
    "compare_from_table": {"verb": "compare", "modality": "table", "description": "Compare items listed in a table", "example": "Which of the top 3 hotels has the best price-to-rating ratio?"},
    "compare_by_slider": {"verb": "compare", "modality": "slider", "description": "Compare values at different slider positions", "example": "Compare monthly payments at 4% vs 5% interest rate"},
    "compare_by_date_range": {"verb": "compare", "modality": "date range", "description": "Compare data across different time periods", "example": "Compare Q1 vs Q2 sales figures"},
    "compare_by_route": {"verb": "compare", "modality": "route", "description": "Compare items on different pages", "example": "Compare two product detail pages"},
    "compare_by_query": {"verb": "compare", "modality": "query", "description": "Compare results for different queries", "example": "Compare the weather forecast for Monday vs Friday"},
    # Verify
    "verify_by_slider": {"verb": "verify", "modality": "slider", "description": "Verify a value matches expected range", "example": "Verify the portfolio return shown matches the 12-month chart"},
    "verify_by_dropdown": {"verb": "verify", "modality": "dropdown", "description": "Verify data after selecting an option", "example": "Select 'Completed' filter and verify all shown orders are completed"},
    "verify_by_toggle": {"verb": "verify", "modality": "toggle", "description": "Verify state after toggling a setting", "example": "Toggle 2FA on and verify the security status shows 'Enhanced'"},
    "verify_from_free_text": {"verb": "verify", "modality": "free text", "description": "Verify a claim by reading page content", "example": "Verify that the article mentions the source study by name"},
    "verify_identity_by_code": {"verb": "verify identity", "modality": "code", "description": "Verify identity using a code or OTP", "example": "Enter the verification code sent to your email"},
    # Create / Submit
    "create_by_form": {"verb": "create", "modality": "free text", "description": "Create new content by typing free-form text", "example": "Write a new blog post with title and body"},
    "create_by_dropdown": {"verb": "create", "modality": "dropdown", "description": "Create something by selecting from dropdowns", "example": "Create a new playlist by selecting genre and mood"},
    "create_by_toggle": {"verb": "create", "modality": "toggle", "description": "Create by toggling options", "example": "Create a new alert by toggling notification preferences"},
    "create_by_checkbox": {"verb": "create", "modality": "checkbox", "description": "Create by checking options", "example": "Create a workout plan by checking desired exercises"},
    "create_by_drag": {"verb": "create", "modality": "drag", "description": "Create by dragging elements", "example": "Drag blocks onto the canvas to build a design"},
    "create_by_radio": {"verb": "create", "modality": "radio", "description": "Create by selecting radio options", "example": "Create a new poll by selecting question type"},
    "create_by_code": {"verb": "create", "modality": "code", "description": "Create by writing code", "example": "Write a Python function in the code editor"},
    "create_from_table": {"verb": "create", "modality": "table", "description": "Create by adding a row to a table", "example": "Add a new contact by filling in the table row"},
    "create_by_timestamp": {"verb": "create", "modality": "timestamp", "description": "Create a clip or bookmark at a specific timestamp", "example": "Create a clip starting at 1:30 in the stream"},
    "create_by_query": {"verb": "create", "modality": "query", "description": "Create by entering text into an input", "example": "Enter a URL to create a short link"},
    "submit_by_form": {"verb": "submit", "modality": "form", "description": "Submit a filled-out form", "example": "Fill in the contact form and click Submit"},
    # Consolidated macros (2026-07-16 merge) — canonical targets of the aliases below.
    "submit_form": {"verb": "submit", "modality": "form", "description": "Submit form data to create or modify a record (unifies create / submit / register / apply / invite / report / post via a form)", "example": "Fill in the form fields and submit"},
    "toggle_status": {"verb": "toggle", "modality": "status", "description": "Toggle a boolean relationship on an item (unifies follow / subscribe / save / join)", "example": "Click the toggle to follow / save / subscribe an item"},
    "submit_by_route": {"verb": "submit", "modality": "route", "description": "Submit by navigating to a submission URL", "example": "Navigate to /submit to finalize your entry"},
    "submit_by_dropdown": {"verb": "submit", "modality": "dropdown", "description": "Submit by selecting and confirming from dropdown", "example": "Select the recipient and submit the transfer"},
    "submit_by_ranking": {"verb": "submit", "modality": "ranking", "description": "Submit a ranking of items", "example": "Rank the candidates and submit your vote"},
    "submit_by_slider": {"verb": "submit", "modality": "slider", "description": "Submit after setting slider values", "example": "Set the bid amount with the slider and submit"},
    "submit_by_date_range": {"verb": "submit", "modality": "date range", "description": "Submit with a date range selection", "example": "Select vacation dates and submit the request"},
    # Edit
    "edit_by_form": {"verb": "edit", "modality": "form", "description": "Edit existing data through a form", "example": "Edit your profile name and bio in the settings form"},
    "edit_by_query": {"verb": "edit", "modality": "query", "description": "Edit by entering new values", "example": "Change the document title by typing a new name"},
    "edit_by_dropdown": {"verb": "edit", "modality": "dropdown", "description": "Edit by selecting a new value from dropdown", "example": "Change the issue priority from 'Low' to 'High'"},
    "edit_by_toggle": {"verb": "edit", "modality": "toggle", "description": "Edit a setting by toggling it", "example": "Toggle 'Public' to make the repository private"},
    "edit_by_drag": {"verb": "edit", "modality": "drag", "description": "Edit by dragging elements to new positions", "example": "Drag the task card from 'To Do' to 'In Progress'"},
    "edit_by_ranking": {"verb": "edit", "modality": "ranking", "description": "Edit the order/ranking of items", "example": "Reorder the playlist by dragging songs"},
    "edit_by_date_range": {"verb": "edit", "modality": "date range", "description": "Edit by changing a date range", "example": "Change the event date to next Friday"},
    "edit_by_image": {"verb": "edit", "modality": "image", "description": "Edit an image or visual content", "example": "Crop the profile photo and save"},
    # Delete
    "delete_from_table": {"verb": "delete", "modality": "table", "description": "Delete an item from a list or table", "example": "Click the trash icon to delete the 3rd email"},
    # Select / Configure
    "select_by_dropdown": {"verb": "select", "modality": "dropdown", "description": "Select an option from a dropdown", "example": "Select 'Dark mode' from the theme dropdown"},
    "select_from_table": {"verb": "select", "modality": "table", "description": "Select items from a table", "example": "Click checkboxes to select 3 files for download"},
    "select_by_radio": {"verb": "select", "modality": "radio", "description": "Select one option from radio buttons", "example": "Select 'Priority Mail' shipping option"},
    "select_by_chip": {"verb": "select", "modality": "chip", "description": "Select by clicking tag chips", "example": "Click the 'Rock' and 'Pop' genre chips"},
    "select_by_slider": {"verb": "select", "modality": "slider", "description": "Select a value using a slider", "example": "Set the quantity slider to 5"},
    "select_by_ranking": {"verb": "select", "modality": "ranking", "description": "Select the item at a specific rank", "example": "Select the top-rated option"},
    "select_by_extremum": {"verb": "select", "modality": "extremum", "description": "Select the min or max item", "example": "Select the cheapest available flight"},
    "select_by_date_range": {"verb": "select", "modality": "date range", "description": "Select a date range", "example": "Select check-in and check-out dates"},
    "select_by_query": {"verb": "select", "modality": "query", "description": "Select by entering a search query", "example": "Type a city name to select it as destination"},
    "configure_by_dropdown": {"verb": "configure", "modality": "dropdown", "description": "Configure a setting using a dropdown", "example": "Set the language to 'Spanish' from the dropdown"},
    "configure_by_slider": {"verb": "configure", "modality": "slider", "description": "Configure a setting with a slider", "example": "Set the password length to 16 characters"},
    "configure_by_toggle": {"verb": "configure", "modality": "toggle", "description": "Configure by toggling a switch", "example": "Enable two-factor authentication"},
    "configure_by_radio": {"verb": "configure", "modality": "radio", "description": "Configure by selecting a radio option", "example": "Set notifications to 'Email only'"},
    "configure_by_query": {"verb": "configure", "modality": "query", "description": "Configure by entering a value", "example": "Set the custom domain to 'mysite.com'"},
    "configure_by_chip": {"verb": "configure", "modality": "chip", "description": "Configure by selecting chips", "example": "Select interest chips: 'Tech', 'Sports', 'Music'"},
    "configure_by_date_range": {"verb": "configure", "modality": "date range", "description": "Configure a date-based setting", "example": "Set the recurring event to every Monday"},
    "configure_by_route": {"verb": "configure", "modality": "route", "description": "Configure settings by navigating to a settings page", "example": "Go to Settings > Playback to configure video quality"},
    # Media
    "play_by_playback": {"verb": "play", "modality": "playback", "description": "Play media content using playback controls", "example": "Click the play button to start the podcast episode"},
    "play_by_dropdown": {"verb": "play", "modality": "dropdown", "description": "Play media selected from a dropdown", "example": "Select a track from the queue dropdown and play it"},
    "play_by_route": {"verb": "play", "modality": "route", "description": "Play by navigating to a media page", "example": "Click the video thumbnail to start playing"},
    "play_by_date_range": {"verb": "play", "modality": "date range", "description": "Play media from a specific time range", "example": "Jump to the 5-minute mark in the recording"},
    "play_by_slider": {"verb": "play", "modality": "slider", "description": "Control playback with a slider", "example": "Scrub the timeline slider to 50% of the video"},
    "play_by_timestamp": {"verb": "play", "modality": "timestamp", "description": "Play from a specific timestamp", "example": "Click the timestamp '2:15' to jump to that point"},
    "export_by_dropdown": {"verb": "export", "modality": "dropdown", "description": "Export data in a format selected from dropdown", "example": "Select 'CSV' and click Export to download the data"},
    "export_by_route": {"verb": "export", "modality": "route", "description": "Export by navigating to an export URL", "example": "Go to /export/pdf to download the PDF version"},
    "upload_by_upload": {"verb": "upload", "modality": "upload", "description": "Upload a file using the file picker", "example": "Click 'Choose File' and upload your resume PDF"},
    "upload_by_query": {"verb": "upload", "modality": "query", "description": "Upload by entering a URL or path", "example": "Paste the image URL to upload it"},
    "upload_by_route": {"verb": "upload", "modality": "route", "description": "Upload by navigating to upload page", "example": "Go to /upload and drag files into the drop zone"},
    "upload_by_image": {"verb": "upload", "modality": "image", "description": "Upload an image file", "example": "Upload a profile photo from your computer"},
    "copy_by_route": {"verb": "copy", "modality": "route", "description": "Copy content by clicking a copy button", "example": "Click the copy icon next to the API key"},
    # Social
    "follow_by_toggle": {"verb": "follow", "modality": "toggle", "description": "Follow/unfollow by clicking a toggle button", "example": "Click 'Follow' to start following the author"},
    "follow_by_dropdown": {"verb": "follow", "modality": "dropdown", "description": "Follow by selecting from dropdown", "example": "Select a user from the dropdown and follow them"},
    "follow_by_route": {"verb": "follow", "modality": "route", "description": "Follow by navigating to follow URL", "example": "Go to the author's page and click Follow"},
    "subscribe_by_toggle": {"verb": "subscribe", "modality": "toggle", "description": "Subscribe/unsubscribe with a toggle", "example": "Toggle the Subscribe button for the newsletter"},
    "save_by_toggle": {"verb": "save", "modality": "toggle", "description": "Save/unsave an item with a toggle", "example": "Click the bookmark icon to save the article"},
    "save_by_query": {"verb": "save", "modality": "query", "description": "Save by entering and confirming", "example": "Name your saved search and click Save"},
    "react_by_toggle": {"verb": "react", "modality": "toggle", "description": "React to content (like, upvote, etc.)", "example": "Click the heart icon to like the post"},
    "react_by_gesture": {"verb": "react", "modality": "gesture", "description": "React with a gesture (swipe, double-tap)", "example": "Swipe right to like the profile"},
    "rate_by_slider": {"verb": "rate", "modality": "slider", "description": "Rate something using a star/slider rating", "example": "Set the review rating to 4 out of 5 stars"},
    "share_by_dropdown": {"verb": "share", "modality": "dropdown", "description": "Share via a method selected from dropdown", "example": "Select 'Copy link' from the share dropdown"},
    "share_by_toggle": {"verb": "share", "modality": "toggle", "description": "Toggle sharing on/off", "example": "Enable link sharing for the document"},
    "share_by_query": {"verb": "share", "modality": "query", "description": "Share by entering a recipient", "example": "Type an email address to share the file"},
    "share_by_route": {"verb": "share", "modality": "route", "description": "Share by navigating to a share page", "example": "Go to the share page and copy the public link"},
    "report_by_form": {"verb": "report", "modality": "form", "description": "Report content by filling out a form", "example": "Select a reason and submit the report"},
    "block_by_toggle": {"verb": "block", "modality": "toggle", "description": "Block/unblock a user", "example": "Click Block to prevent the user from messaging you"},
    "block_by_dropdown": {"verb": "block", "modality": "dropdown", "description": "Block via user dropdown menu", "example": "Select 'Block user' from the three-dot menu"},
    "invite_by_form": {"verb": "invite", "modality": "form", "description": "Invite someone by filling out a form", "example": "Enter email addresses and send the meeting invite"},
    "invite_by_query": {"verb": "invite", "modality": "query", "description": "Invite by entering a name or email", "example": "Type a username to invite them to the channel"},
    "join_by_toggle": {"verb": "join", "modality": "toggle", "description": "Join/leave a group or channel", "example": "Click 'Join' to become a member of the subreddit"},
    "join_by_route": {"verb": "join", "modality": "route", "description": "Join by navigating to a join page", "example": "Go to the meeting link to join the call"},
    "join_by_code": {"verb": "join", "modality": "code", "description": "Join by entering an invite code", "example": "Enter the meeting code to join the video call"},
    "message_from_free_text": {"verb": "message", "modality": "free text", "description": "Send a message by typing text", "example": "Type a message and click Send"},
    "post_from_free_text": {"verb": "post", "modality": "free text", "description": "Create a post by writing text", "example": "Write a comment and click Post"},
    "post_by_route": {"verb": "post", "modality": "route", "description": "Post by navigating to a post page", "example": "Go to /submit to create a new post"},
    "post_by_query": {"verb": "post", "modality": "query", "description": "Post content via a query", "example": "Enter the post title and submit"},
    # Transact
    "add_by_button": {"verb": "add", "modality": "button", "description": "Add an item by clicking a button", "example": "Click 'Add to Cart' on the product page"},
    "add_by_dropdown": {"verb": "add", "modality": "dropdown", "description": "Add by selecting from a dropdown", "example": "Select a track and add it to the playlist"},
    "checkout_by_form": {"verb": "checkout", "modality": "form", "description": "Complete checkout by filling payment form", "example": "Enter card details and click 'Place Order'"},
    "pay_by_form": {"verb": "pay", "modality": "form", "description": "Make a payment via a form", "example": "Enter the amount and recipient, then click Pay"},
    "pay_by_query": {"verb": "pay", "modality": "query", "description": "Pay by entering payment details", "example": "Enter $50 and confirm the bill payment"},
    "pay_by_dropdown": {"verb": "pay", "modality": "dropdown", "description": "Pay using a method from dropdown", "example": "Select 'Credit Card' and confirm payment"},
    "book_by_form": {"verb": "book", "modality": "form", "description": "Book/reserve by filling out a form", "example": "Select date, party size, and book the restaurant"},
    "book_by_date_range": {"verb": "book", "modality": "date range", "description": "Book by selecting dates", "example": "Select check-in and check-out dates for the hotel"},
    "cancel_by_form": {"verb": "cancel", "modality": "form", "description": "Cancel a booking or order via form", "example": "Select a reason and confirm the cancellation"},
    "redeem_by_code": {"verb": "redeem", "modality": "code", "description": "Redeem a promo code or coupon", "example": "Enter code 'SAVE20' and click Apply"},
    "redeem_by_dropdown": {"verb": "redeem", "modality": "dropdown", "description": "Redeem a reward from dropdown", "example": "Select '500 points for $5 off' and redeem"},
    "apply_by_form": {"verb": "apply", "modality": "form", "description": "Apply for something by filling a form", "example": "Fill out the job application and submit"},
    "apply_by_query": {"verb": "apply", "modality": "query", "description": "Apply by entering details", "example": "Enter your qualifications and apply for the permit"},
    # Account
    "authenticate_by_form": {"verb": "authenticate", "modality": "form", "description": "Log in by entering credentials in a form", "example": "Enter username and password, then click Login"},
    "authenticate_by_code": {"verb": "authenticate", "modality": "code", "description": "Authenticate using a code", "example": "Enter the 2FA code from your authenticator app"},
    "register_by_form": {"verb": "register", "modality": "form", "description": "Create a new account via registration form", "example": "Fill in name, email, password and click Register"},
    "register_by_query": {"verb": "register", "modality": "query", "description": "Register by entering details", "example": "Enter your email to create an account"},
    # Route / Directions
    "route_by_query": {"verb": "route", "modality": "query", "description": "Get directions by entering origin and destination", "example": "Enter 'Home to Airport' to get driving directions"},
    "route_by_radio": {"verb": "route", "modality": "radio", "description": "Select route type via radio buttons", "example": "Select 'Walking' to get walking directions"},
    "route_by_route": {"verb": "route", "modality": "route", "description": "View a pre-computed route", "example": "Click on Route #3 to see its details"},
    # Translate
    "translate_by_query": {"verb": "translate", "modality": "query", "description": "Translate text by entering it", "example": "Type 'Hello, how are you?' and translate to Spanish"},
    "translate_by_dropdown": {"verb": "translate", "modality": "dropdown", "description": "Translate by selecting source/target language", "example": "Select English → French from the language dropdowns"},
    "translate_by_slider": {"verb": "translate", "modality": "slider", "description": "Adjust translation settings with slider", "example": "Set the formality slider to 'Formal'"},
    # Sign
    "sign_by_query": {"verb": "sign", "modality": "query", "description": "Sign a document by entering signature", "example": "Type your full name to e-sign the document"},
    "sign_by_signature": {"verb": "sign", "modality": "signature", "description": "Sign by drawing a signature", "example": "Draw your signature in the signature box"},
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _save_task(task):
    """Save task + trajectory to the shared annotations directory."""
    from annotation.storage import save_task as fs_save, generate_task_id

    task_id = task.get("task_id") or generate_task_id()
    task["task_id"] = task_id
    # annotator becomes a directory name and a URL path segment — strip
    # slashes/backslashes (a stray "Minh\" once forked the dataset in two)
    annotator = task.get("annotator", "anonymous").strip().strip("\\/") or "anonymous"
    task["annotator"] = annotator
    trajectory = task.pop("trajectory", [])

    # Primary storage: file system
    fs_save(annotator, task_id, task, trajectory)
    return task_id


def _load_sites():
    from annotation.storage import list_tasks
    sites = []
    # Count annotated tasks per site from file storage
    task_counts = {}
    for t in list_tasks():
        for s in t.get("sites", []):
            sid = s["id"] if isinstance(s, dict) else s
            task_counts[sid] = task_counts.get(sid, 0) + 1
    for site_json in sorted(SITES_DIR.glob("*/site.json")):
        if site_json.parent.name.startswith("_"):
            continue
        if not (site_json.parent / "tasks.json").exists():
            continue
        if (site_json.parent / "routes.py").stat().st_size < 500:
            continue
        meta = json.loads(site_json.read_text())
        meta["url"] = f"/sites/{meta['id']}/"
        meta["annotated_count"] = task_counts.get(meta["id"], 0)
        meta["review_count"] = 0
        sites.append(meta)
    return sites


def _load_macros():
    """Collect all unique (canonical) macros across all sites from MACRO_LOCATIONS."""
    macros = set()
    for site_macros in MACRO_LOCATIONS.values():
        macros.update(_canon(m) for m in site_macros.keys())
    return sorted(macros)


def _load_site_macros(site_id):
    """Load supported macros for a site.

    MACRO_LOCATIONS is the audited source of truth — it lists only macros
    whose UI elements have been verified to exist on each site.
    Falls back to README, then tasks.json for sites not yet audited.
    """
    # MACRO_LOCATIONS is the audited source of truth
    if site_id in MACRO_LOCATIONS:
        macros = [_canon(m) for m in MACRO_LOCATIONS[site_id].keys()]
        if macros:
            return sorted(set(macros))

    # Fallback to README spec for sites not yet in MACRO_LOCATIONS
    import re as _re
    readme = SITES_DIR / site_id / "doc" / "README.md"
    if readme.exists():
        try:
            text = readme.read_text()
            # Try comma-separated format
            match = _re.search(
                r"## Target Macros[^\n]*\n\s*\n?([\w_,\s]+?)(?:\n\n|\n##|\Z)",
                text, _re.DOTALL,
            )
            if match:
                macros = [m.strip() for m in match.group(1).split(",") if m.strip()]
                if macros:
                    return sorted(set(macros))
            # Try numbered list format: "1. **macro_name** -- ..."
            list_macros = _re.findall(
                r"\d+\.\s+\*\*(\w+)\*\*", text[text.find("## Target Macros"):] if "## Target Macros" in text else ""
            )
            if list_macros:
                return sorted(set(list_macros))
        except OSError:
            pass

    # Fallback to tasks.json
    tasks_file = SITES_DIR / site_id / "tasks.json"
    macros = set()
    if tasks_file.exists():
        try:
            for t in json.loads(tasks_file.read_text()):
                for m in t.get("macros", []):
                    macros.add(m)
        except (json.JSONDecodeError, OSError):
            pass
    return sorted(macros)


_NA_FILE = ANNOTATIONS_DIR / "na_reports.json"
# Skip-modal reports (reason + details) — same download-and-collect workflow
# as na_reports.json
_SKIP_REPORTS_FILE = ANNOTATIONS_DIR / "skip_reports.json"


def _load_na_reports():
    """Load NA reports from disk."""
    if _NA_FILE.exists():
        try:
            return json.loads(_NA_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return []


def _save_na_report(sites, macro, annotator):
    """Append a single NA report."""
    reports = _load_na_reports()
    reports.append({
        "sites": sites,
        "macro": macro,
        "annotator": annotator,
        "timestamp": datetime.now().isoformat(),
    })
    _NA_FILE.write_text(json.dumps(reports, indent=2))


def _get_na_macros(site_ids):
    """Get macros marked N/A for these sites (threshold: 2+ reports)."""
    from collections import Counter
    reports = _load_na_reports()
    site_set = set(site_ids)
    counts = Counter()
    for r in reports:
        if site_set & set(r.get("sites", [])):
            counts[r["macro"]] += 1
    return {m for m, c in counts.items() if c >= 2}


def _get_macro_coverage():
    """Count how many annotated tasks cover each macro (from file storage)."""
    from annotation.storage import list_tasks
    coverage = {}
    for t in list_tasks():
        for m in t.get("macros", []):
            m = _canon(m)
            coverage[m] = coverage.get(m, 0) + 1
    return coverage


def _task_site_ids(task):
    """Normalize a stored task's sites to a list of site-id strings."""
    ids = []
    for s in task.get("sites", []):
        ids.append(s.get("id") if isinstance(s, dict) else s)
    return ids


def _get_site_macro_coverage(site_id):
    """Count SINGLE-SITE tasks covering each macro for one site.

    Used for the per-site coverage floor: every site should have at least
    one single-site task per supported macro.
    """
    from annotation.storage import list_tasks
    coverage = {}
    for t in list_tasks():
        if _task_site_ids(t) != [site_id]:
            continue
        for m in t.get("macros", []):
            m = _canon(m)
            coverage[m] = coverage.get(m, 0) + 1
    return coverage


# Coverage floor: each macro should be demonstrated on K distinct sites via
# single-site tasks (or on all its sites, when fewer than K support it).
# K is adjustable from the coverage page; persisted in floor_config.json.
_FLOOR_CONFIG_FILE = Path(__file__).parent / "floor_config.json"
_DEFAULT_FLOOR_K = 3


def _get_floor_k():
    try:
        k = int(json.loads(_FLOOR_CONFIG_FILE.read_text()).get("k", _DEFAULT_FLOOR_K))
        return max(1, min(10, k))
    except (OSError, ValueError, json.JSONDecodeError):
        return _DEFAULT_FLOOR_K


# Retired macro names (merged 2026-07-08) -> canonical. Applied when READING
# task files so historical annotations keep counting; task files themselves
# are never rewritten. (filter_by_radio is site-scoped and NOT aliased —
# it remains a valid macro on other sites.)
_MACRO_ALIASES = {
    "add_by_dropdown": "select_by_dropdown",
    "apply_by_query": "create_by_query",
    "authenticate_by_code": "verify_identity_by_code",
    "configure_by_query": "edit_by_query",
    "configure_by_radio": "select_by_radio",
    "create_by_radio": "select_by_radio",
    "route_by_radio": "select_by_radio",
    "configure_by_route": "configure_by_toggle",
    "select_by_chip": "filter_by_chip",
    "filter_by_proximity": "filter_by_dropdown",
    "filter_by_route": "search_by_route",
    "follow_by_route": "follow_by_toggle",
    "invite_by_query": "invite_by_form",
    "navigate_by_date_range": "filter_by_date_range",
    "post_by_query": "post_from_free_text",
    "register_by_query": "register_by_form",
    "search_by_code": "search_by_query",
    "search_by_date_range": "filter_by_date_range",
    "select_by_query": "search_by_query",
    "select_by_slider": "filter_by_slider",
    "share_by_query": "invite_by_form",
    "sign_by_query": "sign_by_signature",
    "submit_by_dropdown": "submit_by_form",
    "translate_by_dropdown": "compute_by_dropdown",
    "upload_by_query": "upload_by_upload",
    "upload_by_image": "upload_by_upload",
    "upload_by_route": "upload_by_upload",
    # Verb-synonym clusters merged 2026-07-16 (operationally identical by the
    # swap test). Form-submit family -> submit_form; boolean status toggles ->
    # toggle_status. block/react kept separate (distinct meaning); QA/control
    # kept (distinct outcomes). Task files keep old names; aliased on read.
    "create_by_form": "submit_form",
    "create_by_query": "submit_form",
    "submit_by_form": "submit_form",
    "register_by_form": "submit_form",
    "apply_by_form": "submit_form",
    "invite_by_form": "submit_form",
    "report_by_form": "submit_form",
    "post_from_free_text": "submit_form",
    "follow_by_toggle": "toggle_status",
    "subscribe_by_toggle": "toggle_status",
    "save_by_toggle": "toggle_status",
    "join_by_toggle": "toggle_status",
    # Stray names free-typed in old tasks; never existed in MACRO_LOCATIONS
    "create_from_free_text": "submit_form",
    "navigate_by_sidebar": "navigate_by_route",
}


def _canon(macro):
    """Normalize a (possibly retired) macro name to its canonical form.
    Chains through aliases (with a cycle guard) so aliases that point at a
    since-merged macro still resolve to the final canonical name."""
    seen = set()
    while macro in _MACRO_ALIASES and macro not in seen:
        seen.add(macro)
        macro = _MACRO_ALIASES[macro]
    return macro


_CANONICAL_LOCATIONS = None

def _canonical_macro_locations():
    """MACRO_LOCATIONS re-keyed by canonical macro name, location lists
    aggregated across any alias keys that merge into the same macro. The UI
    samples canonical names, so lookups must be keyed the same way."""
    global _CANONICAL_LOCATIONS
    if _CANONICAL_LOCATIONS is None:
        out = {}
        for site, macros in MACRO_LOCATIONS.items():
            site_out = {}
            for m, locs in macros.items():
                locs = [locs] if isinstance(locs, str) else list(locs or [])
                site_out.setdefault(_canon(m), []).extend(locs)
            out[site] = site_out
        _CANONICAL_LOCATIONS = out
    return _CANONICAL_LOCATIONS


def _site_macro_pool(site_id):
    """Macros eligible for floor coverage on a site (excl. NA + navigation)."""
    pool = set(_load_site_macros(site_id)) - _get_na_macros([site_id])
    pool.discard("navigate_by_route")
    return pool


def _get_macro_site_coverage():
    """macro -> set of site ids where a SINGLE-SITE task covers it."""
    from annotation.storage import list_tasks
    cov = {}
    for t in list_tasks():
        ids = _task_site_ids(t)
        if len(ids) != 1:
            continue
        for m in t.get("macros", []):
            cov.setdefault(_canon(m), set()).add(ids[0])
    return cov


def _macro_k_targets():
    """macro -> min(configured K, number of sites supporting it)."""
    k = _get_floor_k()
    supporting = {}
    for sid in MACRO_LOCATIONS:
        for m in _site_macro_pool(sid):
            supporting[m] = supporting.get(m, 0) + 1
    return {m: min(k, n) for m, n in supporting.items()}


def _get_cell_counts():
    """Count existing tasks per (num_sites, num_macros) cell (from file storage)."""
    from annotation.storage import list_tasks
    counts = {}
    for t in list_tasks():
        n_sites = len(t.get("sites", []))
        n_macros = len({_canon(m) for m in t.get("macros", [])})
        key = (n_sites, n_macros)
        counts[key] = counts.get(key, 0) + 1
    return counts


def _load_graph_edges():
    """Load cross-site edges from proposed_edges.csv, grouped by source."""
    import csv
    from collections import defaultdict

    outgoing = defaultdict(list)
    incoming = defaultdict(list)
    edges_file = Path(__file__).parent / "proposed_edges.csv"
    if edges_file.exists():
        with open(edges_file) as f:
            for row in csv.DictReader(f):
                if row.get("status") != "approved":
                    continue
                src = row.get("source", "")
                tgt = row.get("target", "")
                evt = row.get("event_type", "")
                if src and tgt:
                    outgoing[src].append((tgt, evt))
                    incoming[tgt].append((src, evt))
    return outgoing, incoming


# Edge types that imply specific macros the task should exercise
_EDGE_MACRO_HINTS = {
    "purchase": ["checkout_by_form", "add_by_button"],
    "payment": ["pay_by_form", "pay_by_dropdown"],
    "booking": ["book_by_form", "book_by_date_range"],
    "signup": ["register_by_form", "authenticate_by_form"],
    "credential": ["authenticate_by_form"],
    "notification": ["extract_by_route"],
    "file_created": ["create_by_form", "upload_by_upload"],
    "message": ["message_from_free_text"],
    "translate": ["translate_by_query", "translate_by_dropdown"],
    "share": ["share_by_dropdown", "share_by_toggle"],
    "crosspost": ["post_from_free_text"],
    "shorten": ["create_by_query"],
    "location": ["navigate_by_route", "search_by_query"],
    "directions": ["route_by_query"],
    "deadline": ["extract_by_date_range"],
    "query": ["search_by_query"],
}


def _generate_prompt(sites, coverage, force_single=False):
    """Site-first prompt sampler.

    Strategy:
      1. Pick the site with the most uncovered macros
      2. Pick chain length using ratio 3:2:3:2 for lengths 1:2:3:4+
         (weighted toward lengths the site still needs)
      3. Pick uncovered macros for that site
      4. For cross-site: expand along graph edges
    """
    rng = random.Random()
    site_pool = list(sites)
    if not site_pool:
        return None
    site_map = {s["id"]: s for s in site_pool}

    # Load graph
    outgoing, incoming = _load_graph_edges()

    # --- Per-site coverage analysis ---
    from annotation.storage import list_tasks
    all_tasks = list_tasks()

    # Count which macros are covered per site (by any task)
    site_macro_covered = {}  # site_id -> set of covered macros
    site_chain_counts = {}   # site_id -> {chain_len: count}
    for t in all_tasks:
        t_sites = [s["id"] if isinstance(s, dict) else s for s in t.get("sites", [])]
        t_macros = t.get("macros", [])
        chain_len = len(t_macros)
        for sid in t_sites:
            site_macro_covered.setdefault(sid, set()).update(t_macros)
            site_chain_counts.setdefault(sid, {})
            site_chain_counts[sid][chain_len] = site_chain_counts[sid].get(chain_len, 0) + 1

    # For each site, find uncovered macros
    site_uncovered = {}
    for s in site_pool:
        sid = s["id"]
        all_macros = set(_load_site_macros(sid))
        covered = site_macro_covered.get(sid, set())
        uncovered = all_macros - covered
        site_uncovered[sid] = uncovered

    # --- 1. Pick site: prefer sites with most uncovered macros ---
    site_weights = []
    for s in site_pool:
        sid = s["id"]
        n_uncovered = len(site_uncovered.get(sid, set()))
        if n_uncovered > 0:
            site_weights.append(float(n_uncovered))
        else:
            site_weights.append(0.1)  # small weight for fully covered sites

    total = sum(site_weights)
    norm_weights = [w / total for w in site_weights]
    seed = rng.choices(site_pool, weights=norm_weights, k=1)[0]
    sampled_sites = [seed]
    sampled_ids = {seed["id"]}
    edge_types_used = []

    # --- 2. Pick chain length using ratio 3:2:3:2 for lengths 1:2:3:4 ---
    # Weight toward lengths the site still needs
    chain_counts = site_chain_counts.get(seed["id"], {})
    # Target ratio: 3:2:3:2 = lengths 1,2,3,4
    target_ratio = {1: 3, 2: 2, 3: 3, 4: 2}
    chain_weights = []
    chain_options = []
    for length, target_w in target_ratio.items():
        if force_single and length > 3:
            continue
        current = chain_counts.get(length, 0)
        # Weight: target ratio / (current count + 1) — under-filled lengths get priority
        w = target_w / (current + 1)
        chain_weights.append(w)
        chain_options.append(length)

    if not chain_options:
        chain_options = [1]
        chain_weights = [1.0]
    total = sum(chain_weights)
    chain_weights = [w / total for w in chain_weights]
    n_macros = rng.choices(chain_options, weights=chain_weights, k=1)[0]

    # For single-site mode, cap at 3
    if force_single:
        n_sites = 1
        n_macros = min(n_macros, 3)
    else:
        n_sites = 1  # default, may expand for cross-site below

    if not force_single and n_macros >= 2 and rng.random() < 0.2:
        # 20% chance of cross-site task when chain >= 2
        n_sites = 2
        # Expand along graph edges from seed
        candidates = []

        # Direct outgoing
        for target, etype in outgoing.get(seed["id"], []):
            if target in site_map and target not in sampled_ids:
                # Weight: prefer under-annotated targets + non-hub sites
                t = site_map[target]
                hub_penalty = 0.3 if target in ("password-managers", "email") else 1.0
                w = hub_penalty / (t.get("annotated_count", 0) + 1)
                candidates.append((t, w, etype, "outgoing"))

        # Direct incoming
        for source, etype in incoming.get(seed["id"], []):
            if source in site_map and source not in sampled_ids:
                s = site_map[source]
                hub_penalty = 0.3 if source in ("password-managers", "email") else 1.0
                w = hub_penalty / (s.get("annotated_count", 0) + 1)
                candidates.append((s, w, etype, "incoming"))

        # Hub-mediated (seed and other site share a common target/source)
        if len(candidates) < 3:
            seed_targets = {t for t, _ in outgoing.get(seed["id"], [])}
            seed_sources = {s for s, _ in incoming.get(seed["id"], [])}
            hubs = seed_targets | seed_sources
            for hub in hubs:
                # Other sites that also connect to this hub
                for other, etype in outgoing.get(hub, []):
                    if other in site_map and other not in sampled_ids and other != seed["id"]:
                        o = site_map[other]
                        w = 0.5 / (o.get("annotated_count", 0) + 1)
                        candidates.append((o, w, f"via_{hub}", "hub"))
                for other, etype in incoming.get(hub, []):
                    if other in site_map and other not in sampled_ids and other != seed["id"]:
                        o = site_map[other]
                        w = 0.5 / (o.get("annotated_count", 0) + 1)
                        candidates.append((o, w, f"via_{hub}", "hub"))

        # Deduplicate candidates (keep highest weight per site)
        best = {}
        for site_obj, w, etype, direction in candidates:
            sid = site_obj["id"]
            if sid not in best or w > best[sid][1]:
                best[sid] = (site_obj, w, etype, direction)
        candidates = list(best.values())

        # Pick additional sites from candidates
        for _ in range(n_sites - 1):
            if not candidates:
                # Fallback: random under-covered site
                remaining = [s for s in site_pool if s["id"] not in sampled_ids]
                if remaining:
                    rw = [1.0 / (s.get("annotated_count", 0) + 1) for s in remaining]
                    t = sum(rw)
                    pick = rng.choices(remaining, weights=[w/t for w in rw], k=1)[0]
                    sampled_sites.append(pick)
                    sampled_ids.add(pick["id"])
                break

            cs, ws, etypes, dirs = zip(*candidates)
            total = sum(ws)
            pick_idx = rng.choices(range(len(cs)), weights=[w/total for w in ws], k=1)[0]
            pick = cs[pick_idx]
            sampled_sites.append(pick)
            sampled_ids.add(pick["id"])
            edge_types_used.append(etypes[pick_idx])
            candidates = [(s, w, e, d) for s, w, e, d in candidates if s["id"] != pick["id"]]

    # 2b. Auto-include companion sites required for 2FA flows (skip in single-site mode):
    #   - password-managers requires instant-messaging (SMS verification codes)
    #   - any transaction site (banking edges) requires email (2FA confirmation)
    required_companions = {}
    if not force_single and "password-managers" in sampled_ids:
        required_companions["instant-messaging"] = "2fa_code"
    if not force_single:
        # Check if any sampled site sends payments/purchases to banking
        for sid in list(sampled_ids):
            for target, etype in outgoing.get(sid, []):
                if target == "banking" and etype in ("payment", "purchase", "trade"):
                    required_companions["email"] = "2fa_verification"
                    break
        # Also if banking itself is sampled (transactions need email 2FA)
        if "banking" in sampled_ids:
            required_companions["email"] = "2fa_verification"

    for companion_id, reason in required_companions.items():
        if len(sampled_sites) >= 3:
            break  # cap at 3 sites max
        if companion_id not in sampled_ids and companion_id in site_map:
            sampled_sites.append(site_map[companion_id])
            sampled_ids.add(companion_id)
            edge_types_used.append(reason)

    # Update n_sites to reflect added companions
    n_sites = len(sampled_sites)
    # Ensure n_macros >= n_sites
    if n_macros < n_sites:
        n_macros = n_sites

    # 3. Pick macros — combine site macros + edge-implied macros
    macro_pool = set()
    for s in sampled_sites:
        macro_pool.update(_load_site_macros(s["id"]))

    # Remove macros previously marked as N/A for these sites
    na_macros = _get_na_macros([s["id"] for s in sampled_sites])
    macro_pool -= na_macros

    # Add edge-implied macros — only if they exist in the sampled sites' macro pool
    edge_macros = []
    for etype in edge_types_used:
        etype_clean = etype.split("via_")[0] if etype.startswith("via_") else etype
        hints = _EDGE_MACRO_HINTS.get(etype_clean, [])
        for h in hints:
            if h in macro_pool:
                edge_macros.append(h)

    if not macro_pool:
        macro_pool = set(_load_macros())
    macro_pool = sorted(macro_pool)
    if not macro_pool:
        return None

    # Weight: strongly prefer uncovered macros for this site, all macros equal
    site_uncov = site_uncovered.get(seed["id"], set())
    edge_macro_set = set(edge_macros)
    macro_weights = []
    for m in macro_pool:
        if m in site_uncov:
            w = 10.0  # uncovered on this site — strong priority
        else:
            w = 1.0 / (coverage.get(m, 0) + 1)
        if m in edge_macro_set:
            w *= 3.0  # boost edge-implied macros
        macro_weights.append(w)
    total = sum(macro_weights)
    macro_weights = [w / total for w in macro_weights]

    _QA_VERBS = {"extract", "compute", "count", "compare", "verify", "calculate", "rank", "list"}

    sampled_macros = []
    has_qa = False
    remaining_macros = list(zip(macro_pool, macro_weights))
    for _ in range(min(n_macros, len(remaining_macros))):
        if not remaining_macros:
            break
        # If we already have a QA macro, exclude other QA macros from candidates
        if has_qa:
            remaining_macros = [(m, w) for m, w in remaining_macros
                                if m.split("_")[0] not in _QA_VERBS]
            if not remaining_macros:
                break
        ms, ws = zip(*remaining_macros)
        total = sum(ws)
        ws = [w / total for w in ws]
        pick = rng.choices(ms, weights=ws, k=1)[0]
        sampled_macros.append(pick)
        if pick.split("_")[0] in _QA_VERBS:
            has_qa = True
        remaining_macros = [(m, w) for m, w in remaining_macros if m != pick]

    # 4. Ensure every sampled site has at least 1 sampled macro it can perform
    sampled_macro_set = set(sampled_macros)
    for s in sampled_sites:
        site_macros = set(_load_site_macros(s["id"])) - na_macros
        if not (site_macros & sampled_macro_set):
            # This site has no overlap — add one of its macros
            site_only = sorted(site_macros - sampled_macro_set)
            if site_only:
                # Prefer under-covered macros from this site
                pick = min(site_only, key=lambda m: coverage.get(m, 0))
                sampled_macros.append(pick)
                sampled_macro_set.add(pick)

    return {
        "sites": [{"id": s["id"], "name": s.get("name", s["id"])} for s in sampled_sites],
        "macros": sampled_macros,
        "num_sites": len(sampled_sites),
        "num_macros": len(sampled_macros),
        "edges": edge_types_used,
    }


def _generate_site_prompt(site, rng=None):
    """Sampler for an annotator-chosen site.

    The annotator picks the site. This function picks:
      1. Chain length using ratio 3:2:3:2 for lengths 1:2:3:4
         (weighted toward lengths the site still needs)
      2. Macros — strongly prefer uncovered macros on this site,
         all macros weighted equally (no difficulty bias)
    """
    rng = rng or random.Random()
    site_id = site["id"]

    all_macros = sorted(set(_load_site_macros(site_id)))
    if not all_macros:
        return None

    # Get per-site coverage
    from annotation.storage import list_tasks
    site_tasks = [t for t in list_tasks()
                  if site_id in [s["id"] if isinstance(s, dict) else s
                                 for s in t.get("sites", [])]]

    # Which macros are already covered on this site?
    covered = set()
    chain_counts = {}  # chain_len -> count
    for t in site_tasks:
        covered.update(t.get("macros", []))
        cl = len(t.get("macros", []))
        chain_counts[cl] = chain_counts.get(cl, 0) + 1

    uncovered = [m for m in all_macros if m not in covered]

    # 1. Pick chain length: ratio 3:2:3:2 for lengths 1:2:3:4
    target_ratio = {1: 3, 2: 2, 3: 3, 4: 2}
    chain_options = []
    chain_weights = []
    for length, target_w in target_ratio.items():
        current = chain_counts.get(length, 0)
        w = target_w / (current + 1)
        chain_options.append(length)
        chain_weights.append(w)

    total = sum(chain_weights)
    chain_weights = [w / total for w in chain_weights]
    n_macros = rng.choices(chain_options, weights=chain_weights, k=1)[0]

    # 2. Pick macros — strongly prefer uncovered, equal weight otherwise
    _QA_VERBS = {"extract", "compute", "count", "compare", "verify",
                 "calculate", "rank", "list"}
    sampled = []
    remaining = list(all_macros)
    has_qa = False

    for _ in range(min(n_macros, len(remaining))):
        if has_qa:
            remaining = [m for m in remaining if m.split("_")[0] not in _QA_VERBS]
            if not remaining:
                break
        ws = []
        for m in remaining:
            if m in uncovered:
                ws.append(10.0)  # uncovered — strong priority
            else:
                site_count = sum(1 for t in site_tasks if m in t.get("macros", []))
                ws.append(1.0 / (site_count + 1))
        total = sum(ws)
        ws = [w / total for w in ws]
        pick = rng.choices(remaining, weights=ws, k=1)[0]
        sampled.append(pick)
        if pick.split("_")[0] in _QA_VERBS:
            has_qa = True
        remaining = [m for m in remaining if m != pick]

    # Compute how many tasks still needed per chain length
    # Target ratio 3:2:3:2 — scale to cover all macros
    total_macros = len(all_macros)
    # One "batch" = 3×1 + 2×2 + 3×3 + 2×4 = 24 macro slots in 10 tasks
    import math
    batches = max(1, math.ceil(total_macros / 24))
    targets = {1: 3 * batches, 2: 2 * batches, 3: 3 * batches, 4: 2 * batches}
    chain_remaining = {k: max(0, targets[k] - chain_counts.get(k, 0)) for k in targets}

    return {
        "sites": [{"id": site_id, "name": site.get("name", site_id)}],
        "macros": sampled,
        "num_sites": 1,
        "num_macros": len(sampled),
        "edges": [],
        "chosen_site": True,
        "total_macros": total_macros,
        "uncovered_macros": len(uncovered),
        "chain_counts": chain_counts,
        "chain_remaining": chain_remaining,
    }


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

_AUTH_EXEMPT = {"/annotate/login", "/annotate/api/auto_login", "/annotate/api/auto_logout"}

@annotation_bp.before_request
def _require_annotator_login():
    if request.path in _AUTH_EXEMPT:
        return None
    if session.get("annotator_authenticated"):
        return None
    # API routes get JSON 401, HTML routes get redirect
    if request.path.startswith("/annotate/api/"):
        return jsonify({"error": "Not authenticated"}), 401
    return redirect(url_for("annotation.annotator_login"))


@annotation_bp.route("/login", methods=["GET", "POST"])
def annotator_login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        if username in ANNOTATOR_CREDENTIALS and ANNOTATOR_CREDENTIALS[username] == password:
            session["annotator_authenticated"] = True
            session["annotator_name"] = username
            return redirect(url_for("annotation.index"))
        error = "Invalid credentials"
    return render_template("annotate_login.html", error=error)


@annotation_bp.route("/logout")
def annotator_logout():
    session.pop("annotator_authenticated", None)
    session.pop("annotator_name", None)
    return redirect(url_for("annotation.annotator_login"))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@annotation_bp.route("/")
def index():
    from annotation.storage import get_stats
    sites = _load_sites()
    ann_stats = get_stats()
    macros = _load_macros()
    coverage = _get_macro_coverage()
    cell_counts = _get_cell_counts()
    return render_template("index.html",
                           sites=sites, task_count=ann_stats["total_tasks"],
                           macros=macros, coverage=coverage,
                           cell_counts=cell_counts)


@annotation_bp.route("/task")
def annotate():
    """Single annotation interface — system samples sites × macros.

    With ?rerecord=<task_id>[&annotator=<name>] the prompt is built from that
    saved task instead of sampled, and the task's design data is shipped to
    the template so the editor opens prefilled; saving then replaces the
    original recording (see api_create_task's replace branch).
    """
    sites = _load_sites()
    rerecord = None
    rerecord_id = request.args.get("rerecord", "").strip()
    if rerecord_id:
        from annotation.storage import get_annotators, load_task
        annotator = request.args.get("annotator", "").strip()
        candidates = [annotator] if annotator else get_annotators()
        task = None
        for ann in candidates:
            task = load_task(ann, rerecord_id)
            if task:
                annotator = ann
                break
        if not task:
            return redirect(url_for("annotation.verify"))
        site_map = {s["id"]: s for s in sites}
        task_site_ids = [s["id"] if isinstance(s, dict) else s
                         for s in task.get("sites", [])]
        prompt = {
            "sites": [{"id": sid, "name": site_map.get(sid, {}).get("name", sid)}
                      for sid in task_site_ids],
            "macros": task.get("macros", []),
            "num_sites": len(task_site_ids),
            "num_macros": len(task.get("macros", [])),
            "edges": [],
        }
        rerecord = {
            "task_id": rerecord_id,
            "annotator": annotator,
            "instruction": task.get("instruction", ""),
            "expected_answer": task.get("expected_answer") or "",
            "answer_type": task.get("answer_type", "string"),
            "alternatives": task.get("alternatives", ""),
            "expected_outcome": task.get("expected_outcome", ""),
            "macro_edges": task.get("macro_edges", []),
            "macro_positions": task.get("macro_positions", {}),
            "macro_subtasks": task.get("macro_subtasks", {}),
            "qa_answers": task.get("qa_answers", {}),
            "starting_url": task.get("starting_url", ""),
            "requires_login": task.get("requires_login", True),
            "missing_sites": [sid for sid in task_site_ids if sid not in site_map],
        }
    else:
        coverage = _get_macro_coverage()
        prompt = _generate_prompt(sites, coverage)

    return render_template("annotate.html",
                           sites=sites,
                           prompt=prompt,
                           rerecord=rerecord,
                           macro_descriptions=_MACRO_DESCRIPTIONS,
                           macro_locations=_canonical_macro_locations())


@annotation_bp.route("/review")
def review():
    """Website review mode — browse each site, leave feedback."""
    sites = _load_sites()
    return render_template("review.html", sites=sites)


@annotation_bp.route("/verify")
def verify():
    """Verifier builder — load a saved task and build verification checks."""
    from annotation.storage import list_tasks
    task_id = request.args.get("task_id")
    annotator = request.args.get("annotator")
    tasks = list_tasks(annotator)
    task = None
    if task_id:
        from annotation.storage import load_task
        # Find the task across annotators
        if annotator:
            task = load_task(annotator, task_id)
        else:
            from annotation.storage import get_annotators
            for ann in get_annotators():
                task = load_task(ann, task_id)
                if task:
                    break
    return render_template("verify.html",
                           tasks=tasks,
                           task=task,
                           macro_descriptions=_MACRO_DESCRIPTIONS)


@annotation_bp.route("/graph")
def graph():
    """Interactive site affinity graph — visualize and edit cross-site flows."""
    from annotation.site_affinities import SITE_AFFINITY_GROUPS
    sites = _load_sites()
    return render_template("graph.html", sites=sites,
                           affinities=SITE_AFFINITY_GROUPS)


@annotation_bp.route("/accounts")
def accounts_page():
    """Credential lookup — every seeded login account across all sites."""
    from app import db
    sites = []
    for meta in _load_sites():
        users = db.query(meta["id"], "users", limit=200)
        rows = []
        for u in users or []:
            rows.append({
                "id": u.get("id"),
                "username": u.get("username") or "",
                "email": u.get("email") or "",
                "password": "" if u.get("password") in (None, "") else str(u["password"]),
                "name": u.get("name") or u.get("full_name") or u.get("display_name") or "",
                "role": u.get("role") or "",
            })
        if rows:
            rows.sort(key=lambda r: (r["id"] is None, r["id"]))
            sites.append({"id": meta["id"], "name": meta.get("name") or meta["id"],
                          "url": meta["url"], "users": rows})
    return render_template("accounts.html", sites=sites)


# --- Macro template builder ------------------------------------------------

@annotation_bp.route("/macro-templates")
def macro_templates_page():
    """Author one verifier template per macro (the reusable skeletons the
    per-task filler later fills in)."""
    from annotation import macro_templates as mt
    macros = mt.list_macros()
    selected = request.args.get("macro") or (macros[0]["macro"] if macros else "")
    return render_template("macro_templates.html",
                           macros=macros,
                           selected=selected,
                           check_schema=mt.check_schema())


@annotation_bp.route("/api/macro_templates", methods=["GET"])
def api_list_macro_templates():
    """Macros that already have a template — for the 'prefill from' dropdown."""
    from annotation import macro_templates as mt
    return jsonify({"macros": sorted(mt.load_all().keys())})


@annotation_bp.route("/api/macro_template/<macro>", methods=["GET"])
def api_get_macro_template(macro):
    from annotation import macro_templates as mt
    return jsonify({"macro": macro, "template": mt.load_template(macro)})


@annotation_bp.route("/api/macro_template/<macro>", methods=["POST"])
def api_save_macro_template(macro):
    from annotation import macro_templates as mt
    data = request.get_json(silent=True) or {}
    tree = data.get("template")  # None deletes
    try:
        mt.save_template(macro, tree)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 400
    return jsonify({"status": "ok", "macro": macro,
                    "has_template": tree is not None})


@annotation_bp.route("/api/macro_usage/<macro>", methods=["GET"])
def api_macro_usage(macro):
    from annotation import macro_templates as mt
    return jsonify(mt.macro_usage(macro))


_TEMPLATE_MODEL = "gemini-3.5-flash"


def _schema_lines(schema):
    lines = []
    for ctype, meta in schema.items():
        parts = []
        for p, ps in meta["params"].items():
            if ps["kind"] == "enum":
                parts.append(f"{p}(one of {ps['options']})")
            else:
                parts.append(f"{p}({ps['kind']})")
        lines.append(f"  {ctype}: {meta.get('help','')}  params: {', '.join(parts)}")
    return "\n".join(lines)


def _generate_macro_template(macro, meta, observed, examples_text, schema_text, actions_text):
    """Ask the LLM for a verifier template for one macro, in the style of the
    human examples. Returns a tree dict (marked _suggested) or None."""
    from app.llm import call_llm

    system_prompt = (
        "You author VERIFIER TEMPLATES for web-task macros. A template is a JSON tree:\n"
        '  group: {"op":"AND"|"OR", "label":"..."(optional), "checks":[ ... ]}\n'
        '  leaf : {"type": <check>, "label":"..."(optional), <params>}\n'
        'Each param is either a FIXED value, or {"open": true} meaning it is filled per\n'
        "task later. RULES:\n"
        "- Leave task-specific values OPEN: target, url, expected, body_fields, value.\n"
        "- FIX the invariants: the action type (for action_included) and the HTTP method\n"
        "  (for request_made) — choose them from what the macro does.\n"
        "- Prefer the highest-signal check for the macro's intent: a QA/extract/compute/\n"
        "  compare/verify macro -> qa_answer (+ answer_grounded); an interaction ->\n"
        "  action_included; a create/submit/pay/mutation -> request_made (POST) with\n"
        "  body_fields open.\n"
        "- Add a short `label` to each check and group saying what it asserts.\n"
        "- Do NOT assert scroll/navigate. Keep it minimal — one to three checks.\n\n"
        "Check types and params:\n" + schema_text + "\n\n"
        "Assertable action types (fix `action` to one of these):\n  " + actions_text + "\n\n"
        "Match the STYLE of these human-authored examples:\n" + examples_text + "\n\n"
        "Return ONLY the JSON template tree for the requested macro, nothing else."
    )
    user_prompt = json.dumps({
        "macro": macro, "verb": meta.get("verb", ""), "modality": meta.get("modality", ""),
        "description": meta.get("description", ""), "observed_actions": observed,
    }, ensure_ascii=False)

    raw = call_llm(user_prompt, system=system_prompt, max_tokens=1500,
                   temperature=0.3, json_mode=True, model=_TEMPLATE_MODEL)
    if not raw:
        return None
    try:
        tree = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(tree, dict):
        return None
    if "op" not in tree:                      # a bare leaf -> wrap in an AND group
        tree = {"op": "AND", "checks": [tree]}
    tree["_suggested"] = True
    return tree


@annotation_bp.route("/api/suggest_templates_batch", methods=["POST"])
def api_suggest_templates_batch():
    """Propose templates for macros that have none, using the confirmed
    (human-authored) templates as in-context examples. Processes up to `limit`
    per call so the caller can loop with progress. Suggestions are marked
    `_suggested` so they read as drafts until you edit + Save.
    """
    from annotation import macro_templates as mt
    data = request.get_json(silent=True) or {}
    limit = int(data.get("limit", 8))
    exclude = set(data.get("exclude") or [])   # macros already handled this run

    existing = mt.load_all()
    confirmed = {m: t for m, t in existing.items() if not mt.is_suggested(t)}
    if not confirmed:
        return jsonify({"error": "author at least one template first — it's the example"}), 400

    # targets: site-mapped macros WITHOUT a confirmed template — this regenerates
    # existing AI drafts with the latest confirmed examples, and never touches a
    # human-confirmed template. `exclude` carries the ones already done this run
    # so the batch loop terminates (regenerated drafts stay _suggested).
    mapped = mt.mapped_macros()
    targets = sorted(m for m in mapped
                     if m not in confirmed
                     and m not in exclude
                     and (_MACRO_DESCRIPTIONS.get(m) or {}).get("verb") != "navigate")
    remaining_after = max(0, len(targets) - limit)
    batch = targets[:limit]
    if not batch:
        return jsonify({"processed": 0, "remaining": 0, "results": []})

    # few-shot from confirmed templates (diverse, capped)
    ex_lines, seen_verbs = [], set()
    for m, t in confirmed.items():
        verb = (_MACRO_DESCRIPTIONS.get(m) or {}).get("verb", "")
        clean = {k: v for k, v in t.items() if k != "_suggested"}
        desc = (_MACRO_DESCRIPTIONS.get(m) or {}).get("description", "")
        ex_lines.append(f"{m} ({desc}):\n{json.dumps(clean, ensure_ascii=False)}")
        seen_verbs.add(verb)
    examples_text = "\n\n".join(ex_lines[:8])

    schema = mt.check_schema()
    schema_text = _schema_lines(schema)
    from evaluation.action_vocabulary import ASSERTABLE_ACTIONS
    actions_text = ", ".join(ASSERTABLE_ACTIONS)
    observed_map = mt.observed_actions_all()

    results = []
    for macro in batch:
        meta = _MACRO_DESCRIPTIONS.get(macro) or {}
        tree = _generate_macro_template(
            macro, meta, observed_map.get(macro, {}),
            examples_text, schema_text, actions_text)
        if tree:
            mt.save_template(macro, tree)
            results.append({"macro": macro, "ok": True})
        else:
            results.append({"macro": macro, "ok": False})

    return jsonify({
        "processed": len(batch),
        "succeeded": sum(1 for r in results if r["ok"]),
        "remaining": remaining_after,
        "results": results,
        "model": _TEMPLATE_MODEL,
    })


# task verifier — fill the macros' open template fields from the trajectory
_VERIFIER_FILL_MODEL = "gemini-3.5-flash"


def _span_actions(task, traj, macro):
    """The concrete recorded actions inside a macro's span — the strongest
    signal for what its open target/value should be."""
    from annotation import macro_templates as mt
    acts = [e for e in traj if e.get("type") == "action"]
    out = []
    # `macro` is canonical; aggregate every pre-merge span that maps to it
    for orig, span in (task.get("macro_spans") or {}).items():
        if _canon(orig) != macro:
            continue
        for idx in mt._span_indices(span, len(acts)):
            a = acts[idx]
            out.append({k: a[k] for k in
                        ("action", "target", "value", "text", "option_text", "url", "method")
                        if a.get(k) not in (None, "")})
    return out


@annotation_bp.route("/api/suggest_task_verifier", methods=["POST"])
def api_suggest_task_verifier():
    """Fill the OPEN fields of a task's macro templates from its trajectory.

    Body: {task_id, annotator?}. Returns the human templates with their open
    params filled in by the LLM (gemini-3.5-flash), grounded in the whole
    trajectory (observations reduced to axtree only).
    """
    from annotation import macro_templates as mt
    from app.llm import call_llm

    data = request.get_json(silent=True) or {}
    task_id = data.get("task_id")
    annotator = data.get("annotator")
    if not task_id:
        return jsonify({"error": "task_id required"}), 400

    _dir, task, traj = _load_saved_task(annotator, task_id)
    if not task:
        return jsonify({"error": "task not found"}), 404

    macros = task.get("macros") or []
    draft = mt.build_task_draft(macros)
    if not draft["templates"]:
        return jsonify({"error": "none of this task's macros have a template yet",
                        "missing": draft["missing"], "templates": {}}), 200
    if not draft["slots"]:
        # nothing open to fill — the templates are already concrete
        return jsonify({"templates": draft["templates"], "missing": draft["missing"],
                        "slots": [], "model": None})

    # per-macro context: description + the actions the human took in its span
    macro_ctx = []
    for macro in draft["templates"]:
        desc = (_MACRO_DESCRIPTIONS.get(macro) or {}).get("description", "")
        macro_ctx.append({"macro": macro, "description": desc,
                          "span_actions": _span_actions(task, traj, macro)})

    slots_for_llm = [{"id": s["id"], "macro": s["macro"],
                      "check": s["check_type"], "param": s["param"], "fixed": s["fixed"],
                      "label": s.get("label", ""), "context": s.get("group_labels", [])}
                     for s in draft["slots"]]

    from evaluation.trajectory import synthesize_network_events
    reduced = mt.reduce_trajectory_for_llm(synthesize_network_events(traj))

    system_prompt = (
        "You fill in the OPEN variables of pre-written verifier templates for a web task.\n"
        "A human authored one template per macro (the check structure is fixed); your ONLY job\n"
        "is to supply concrete values for the variables they left open, read off the recorded\n"
        "trajectory. Do NOT invent checks, change structure, or fill a value the trajectory does\n"
        "not support.\n\n"
        "Each slot names its macro, the check type, the param to fill, the FIXED sibling\n"
        "params, and — when the author wrote them — a `label` (what this check asserts) and\n"
        "`context` (names of the enclosing logical groups). Use those labels as the intent:\n"
        "they tell you what value the author meant this slot to capture.\n"
        "Guidance by param:\n"
        "  target  -> the human-readable component the action hit (from that macro's span action's `target`)\n"
        "  value   -> the value entered/selected (the span action's value/text/option_text)\n"
        "  url     -> the request path or page URL involved (from network events or observations)\n"
        "  method  -> the HTTP method of the mutating request\n"
        "  status  -> the response status code of that request\n"
        "  body_fields -> an object of the key payload fields that were submitted {field: value}\n"
        "  expected     -> the answer the task produces (use the task answer, or the value visible\n"
        "                  on the page the macro ends on). For qa_answer/reasoning_contains this is\n"
        "                  the value to look for; leave `mode` and `leaf` alone (leaf is auto-set).\n"
        "  alternatives -> other acceptable surface forms of the expected answer (e.g. a name and\n"
        "                  its email), as a list; [] if none\n\n"
        "Return ONLY JSON: {\"fills\": {\"<slot id>\": <value>, ...}}. Use the exact slot ids.\n"
        "A value may be a string, number, list, or object. Omit a slot only if the trajectory\n"
        "genuinely has no value for it."
    )
    user_prompt = json.dumps({
        "instruction": task.get("instruction", ""),
        "answer": task.get("answer"),
        "macros": macro_ctx,
        "slots_to_fill": slots_for_llm,
        "trajectory": reduced,
    }, ensure_ascii=False, default=str)

    raw = call_llm(user_prompt, system=system_prompt, max_tokens=4000,
                   temperature=0.2, json_mode=True, model=_VERIFIER_FILL_MODEL)
    if not raw:
        return jsonify({"error": f"LLM unavailable ({_VERIFIER_FILL_MODEL})"}), 503

    try:
        fills = (json.loads(raw) or {}).get("fills", {})
    except (json.JSONDecodeError, TypeError):
        return jsonify({"error": "LLM returned malformed JSON", "raw": raw[:2000]}), 502

    # map slot id -> (macro, path, param), then fill each macro's tree
    by_id = {s["id"]: s for s in draft["slots"]}
    per_macro_fills = {}
    for sid, value in (fills or {}).items():
        s = by_id.get(sid)
        if not s:
            continue
        per_macro_fills.setdefault(s["macro"], []).append(
            {"path": s["path"], "param": s["param"], "value": value})

    filled = {}
    for macro, tree in draft["templates"].items():
        filled[macro] = mt.fill_open(tree, per_macro_fills.get(macro, []))
    mt.inject_qa_leaf(filled, task)   # resolve qa_answer's leaf/chained per this task

    return jsonify({
        "templates": filled,
        "missing": draft["missing"],
        "slots": draft["slots"],
        "filled_count": len(fills or {}),
        "slot_count": len(draft["slots"]),
        "model": _VERIFIER_FILL_MODEL,
    })


def _load_test_trajectory(annotator, task_id, which):
    """Return (trajectory, answer, note) for the requested test source.

    Network events the recorder missed (GET navigations; POSTs dropped by the
    old walk collector) are reconstructed from the actions before verifying."""
    from annotation.storage import ANNOTATIONS_DIR
    from evaluation.trajectory import synthesize_network_events
    tdir = ANNOTATIONS_DIR / annotator / task_id

    if which == "walk":
        wf = tdir / "verification_walk.json"
        if not wf.exists():
            return None, "", "no verification walk recorded for this task"
        d = json.loads(wf.read_text())
        return synthesize_network_events(d.get("trajectory", [])), d.get("answer", ""), "verification walk"
    if which == "agent":
        from pathlib import Path
        from evaluation.trajectory import extract_final_reasoning
        rd = Path("evaluation/results") / f"recorded_{task_id}"
        ar = rd / "trajectory.json"
        if not ar.exists():
            return None, "", "no agent run recorded for this task"
        traj = synthesize_network_events(json.loads(ar.read_text()))
        reasoning = extract_final_reasoning(rd)
        if reasoning:
            traj = traj + [{"type": "reasoning", "text": reasoning}]
        # the agent's answer is its final_result (for answer_matches, if used)
        answer = ""
        rp = rd / "result.json"
        if rp.exists():
            answer = (json.loads(rp.read_text()) or {}).get("final_result", "") or ""
        return traj, answer, "agent attempt"
    # default: gold human trajectory
    tf = tdir / "trajectory.json"
    task = json.loads((tdir / "task.json").read_text()) if (tdir / "task.json").exists() else {}
    traj = json.loads(tf.read_text()) if tf.exists() else []
    return synthesize_network_events(traj), task.get("answer", ""), "gold (human)"


@annotation_bp.route("/api/run_task_verifier", methods=["POST"])
def api_run_task_verifier():
    """Sandbox: run a task verifier spec against a chosen trajectory.

    Body: {task_id, annotator, which: gold|walk|agent, macros?}. If `macros` is
    omitted the saved verifier.json is used. Returns the per-macro report.
    """
    from evaluation.verifiers import verify_task
    data = request.get_json(silent=True) or {}
    task_id = data.get("task_id")
    annotator = data.get("annotator") or "anonymous"
    which = data.get("which") or "gold"
    if not task_id:
        return jsonify({"error": "task_id required"}), 400

    macros = data.get("macros")
    if macros is None:
        from annotation.storage import ANNOTATIONS_DIR
        vf = ANNOTATIONS_DIR / annotator / task_id / "verifier.json"
        if vf.exists():
            macros = json.loads(vf.read_text()).get("macros", {})
        else:
            macros = {}
    if not macros:
        return jsonify({"error": "no verifier spec — suggest or save one first"}), 400

    traj, answer, note = _load_test_trajectory(annotator, task_id, which)
    if traj is None:
        return jsonify({"error": note, "which": which}), 404

    # resolve qa_answer leaf/chained from the task graph before running
    from annotation.storage import ANNOTATIONS_DIR
    from annotation import macro_templates as mt
    tjson = ANNOTATIONS_DIR / annotator / task_id / "task.json"
    if tjson.exists():
        mt.inject_qa_leaf(macros, json.loads(tjson.read_text()))

    report = verify_task({"task_id": task_id, "macros": macros}, traj, answer)
    report["which"] = which
    report["source"] = note
    report["action_count"] = sum(1 for e in traj if e.get("type") == "action")
    return jsonify(report)


@annotation_bp.route("/api/task_verifier/<annotator>/<task_id>", methods=["GET", "POST"])
def api_task_verifier(annotator, task_id):
    """Load/save a task's filled verifier spec (verifier.json next to the task)."""
    from annotation.storage import ANNOTATIONS_DIR
    vf = ANNOTATIONS_DIR / annotator / task_id / "verifier.json"
    if request.method == "GET":
        if vf.exists():
            return jsonify(json.loads(vf.read_text()))
        return jsonify({"task_id": task_id, "macros": {}})
    data = request.get_json(silent=True) or {}
    spec = {"task_id": task_id,
            "macros": data.get("macros", {}),
            "model": data.get("model")}
    vf.parent.mkdir(parents=True, exist_ok=True)
    vf.write_text(json.dumps(spec, indent=2, default=str))
    return jsonify({"status": "ok"})


# --- API ---

@annotation_bp.route("/api/tasks", methods=["GET"])
def api_list_tasks():
    from annotation.storage import list_tasks
    annotator = request.args.get("annotator")
    return jsonify(list_tasks(annotator))


@annotation_bp.route("/api/screenshot/<annotator>/<task_id>/<path:filename>")
def api_screenshot(annotator, task_id, filename):
    """Serve a screenshot file from the task's directory."""
    from flask import send_from_directory
    from annotation.storage import ANNOTATIONS_DIR
    task_dir = ANNOTATIONS_DIR / annotator / task_id
    return send_from_directory(str(task_dir), filename)


@annotation_bp.route("/api/update_task_field", methods=["POST"])
def api_update_task_field():
    """Update a single field on a saved task."""
    data = request.get_json(silent=True) or {}
    task_id = data.get("task_id")
    annotator = data.get("annotator", "anonymous")
    field = data.get("field")
    value = data.get("value")
    if not task_id or not field:
        return jsonify({"error": "task_id and field required"}), 400

    from annotation.storage import ANNOTATIONS_DIR
    task_file = ANNOTATIONS_DIR / annotator / task_id / "task.json"
    if not task_file.exists():
        return jsonify({"error": "Task not found"}), 404

    task_data = json.loads(task_file.read_text())
    task_data[field] = value
    task_file.write_text(json.dumps(task_data, indent=2, default=str))
    return jsonify({"status": "ok", "field": field})


@annotation_bp.route("/api/tasks", methods=["POST"])
def api_create_task():
    data = request.get_json(silent=True) or {}
    if not data.get("instruction") or not data.get("sites"):
        return jsonify({"error": "instruction and sites required"}), 400

    # Multi-macro tasks must ship a dependency graph that touches every macro
    # (mirrors the client-side check in annotate.html so the API can't bypass it)
    macros = data.get("macros") or []
    if len(macros) >= 2:
        edges = data.get("macro_edges") or []
        linked = {e.get("from") for e in edges} | {e.get("to") for e in edges}
        orphans = [m for m in macros if m not in linked]
        if orphans:
            return jsonify({"error": "macro dependencies incomplete",
                            "unconnected_macros": orphans}), 400

    sites_list = data.get("sites", [])
    task = {
        "task_id": f"{'_'.join(s['id'] if isinstance(s, dict) else s for s in sites_list[:2])}_{uuid.uuid4().hex[:6]}",
        "site": sites_list[0]["id"] if isinstance(sites_list[0], dict) else sites_list[0],
        "sites": [s["id"] if isinstance(s, dict) else s for s in sites_list],
        "instruction": data["instruction"],
        "macros": data.get("macros", []),
        "num_sites": len(sites_list),
        "num_macros": len(data.get("macros", [])),
        "expected_answer": data.get("expected_answer"),
        "answer_type": data.get("answer_type", "string"),
        "alternatives": data.get("alternatives", ""),
        "expected_outcome": data.get("expected_outcome", ""),
        "macro_edges": data.get("macro_edges", []),
        "macro_positions": data.get("macro_positions", {}),
        "macro_subtasks": data.get("macro_subtasks", {}),
        "macro_spans": data.get("macro_spans", {}),
        "qa_answers": data.get("qa_answers", {}),
        "starting_url": data.get("starting_url", ""),
        "requires_login": data.get("requires_login", True),
        "trajectory": data.get("trajectory", []),
        "server_log": data.get("server_log", []),
        "beacon_log": data.get("beacon_log", []),
        "agent_result": data.get("agent_result"),
        "annotator": data.get("annotator", "anonymous"),
    }

    # Re-record: replace an existing task in place. The new recording keeps
    # the original task_id and annotator dir (external references stay
    # stable); the previous version moves to the recoverable .trash.
    replace_id = data.get("replace_task_id")
    trashed_from = None
    if replace_id:
        from annotation.storage import ANNOTATIONS_DIR, get_annotators, trash_task
        orig_annotator = data.get("replace_annotator") or next(
            (a for a in get_annotators()
             if (ANNOTATIONS_DIR / a / replace_id).exists()), None)
        if not orig_annotator or not (ANNOTATIONS_DIR / orig_annotator / replace_id).exists():
            return jsonify({"error": "Task to replace not found"}), 404
        task["task_id"] = replace_id
        task["annotator"] = orig_annotator
        task["rerecorded_at"] = datetime.now().isoformat()
        task["rerecorded_by"] = data.get("annotator", "anonymous")
        # trash-then-save: moving the whole old dir away also removes stale
        # screenshots/ and logs that a plain overwrite would leave behind
        trashed_from = trash_task(orig_annotator, replace_id)

    try:
        task_id = _save_task(task)
    except Exception:
        if trashed_from:
            # restore the original so a failed replace never loses the task
            import shutil
            shutil.move(trashed_from, str(ANNOTATIONS_DIR / task["annotator"] / replace_id))
        raise

    # Derive axtree + screenshot from the recorded HTML snapshots so saved
    # observations match the backfilled/replayed data format (async).
    from annotation.observations import schedule_completion
    schedule_completion(task["annotator"], task_id,
                        request.host_url.rstrip("/"))

    # Record N/A macros for future sampling improvement
    na_macros = data.get("macros_not_applicable", {})
    sites_list = data.get("sites", [])
    site_ids = [s["id"] if isinstance(s, dict) else s for s in sites_list]
    annotator = data.get("annotator", "anonymous")
    for macro in na_macros:
        _save_na_report(site_ids, macro, annotator)

    return jsonify({"task_id": task_id, "status": "saved"})


@annotation_bp.route("/api/sites")
def api_sites():
    return jsonify(_load_sites())


@annotation_bp.route("/api/macros")
def api_macros():
    return jsonify(_load_macros())


@annotation_bp.route("/api/macro_descriptions")
def api_macro_descriptions():
    return jsonify(_MACRO_DESCRIPTIONS)


@annotation_bp.route("/api/schema/<site_id>")
def api_site_schema(site_id):
    """Return DB schema for a site: collections and their fields."""
    from app import db
    import sqlite3

    conn = db.get_conn()
    prefix = site_id.replace("-", "_")
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE ?",
        (f"{prefix}%",),
    ).fetchall()

    schema = {}
    for (table_name,) in tables:
        coll = table_name[len(prefix) + 1:]  # strip prefix_
        if not coll or coll.startswith("fts_"):
            continue
        cols = conn.execute(f"PRAGMA table_info([{table_name}])").fetchall()
        fields = [{"name": c[1], "type": c[2]} for c in cols]
        # Get 2 sample values per field
        try:
            sample = conn.execute(f"SELECT * FROM [{table_name}] LIMIT 2").fetchall()
            if sample:
                for f in fields:
                    vals = []
                    for row in sample:
                        v = row[next(i for i, c in enumerate(cols) if c[1] == f["name"])]
                        if v is not None:
                            vals.append(str(v)[:50])
                    f["samples"] = vals
        except Exception:
            pass
        schema[coll] = fields

    return jsonify(schema)


@annotation_bp.route("/api/macro_locations/<site_id>")
def api_macro_locations(site_id):
    """Return macro-to-location map for a specific site (canonical keys)."""
    return jsonify(_canonical_macro_locations().get(site_id, {}))


@annotation_bp.route("/api/site_macros/<site_id>")
def api_site_macros(site_id):
    return jsonify(_load_site_macros(site_id))


@annotation_bp.route("/api/coverage")
def api_coverage():
    return jsonify(_get_macro_coverage())


@annotation_bp.route("/api/cell_counts")
def api_cell_counts():
    cells = _get_cell_counts()
    return jsonify({f"{n},{m}": c for (n, m), c in cells.items()})


@annotation_bp.route("/api/prompt")
def api_prompt():
    """Get a new prompt.

    ?site=<id>  — annotator-chosen site: only macros are sampled, with the
                  per-site coverage floor prioritized (single-site task base).
    ?single=1   — random single-site prompt (legacy behavior).
    (neither)   — graph-aware multi-site sampling.
    """
    sites = _load_sites()
    site_id = (request.args.get("site") or "").strip()
    if site_id:
        site = next((s for s in sites if s["id"] == site_id), None)
        if not site:
            return jsonify({"error": f"unknown site: {site_id}"}), 404
        return jsonify(_generate_site_prompt(site))
    coverage = _get_macro_coverage()
    single = request.args.get("single") == "1"
    prompt = _generate_prompt(sites, coverage, force_single=single)
    return jsonify(prompt)


@annotation_bp.route("/coverage")
def coverage_page():
    """Per-site macro coverage matrix — which macros already have tasks."""
    return render_template("coverage.html")


@annotation_bp.route("/api/coverage_matrix")
def api_coverage_matrix():
    """Per-site coverage: macros covered, chain breakdown, tasks remaining."""
    import math
    from annotation.storage import list_tasks

    all_tasks = list_tasks()

    # Per-site analysis
    sites = {}
    for s in _load_sites():
        sid = s["id"]
        all_macros = sorted(set(_load_site_macros(sid)))
        total_macros = len(all_macros)

        # Tasks for this site
        site_tasks = [t for t in all_tasks
                      if sid in [x["id"] if isinstance(x, dict) else x
                                 for x in t.get("sites", [])]]

        # Covered macros — canonicalize task macros so retired alias names
        # (pre-consolidation) count toward the canonical macro, matching
        # _get_macro_coverage and the sampled pool
        covered = set()
        chain_counts = {}
        for t in site_tasks:
            cms = {_canon(m) for m in t.get("macros", [])}
            covered.update(cms)
            cl = len(cms)
            chain_counts[cl] = chain_counts.get(cl, 0) + 1

        uncovered = [m for m in all_macros if m not in covered]

        # Target: 3:2:3:2 ratio, scaled by batches needed
        batches = max(1, math.ceil(total_macros / 24))
        targets = {1: 3 * batches, 2: 2 * batches, 3: 3 * batches, 4: 2 * batches}
        remaining = {k: max(0, targets[k] - chain_counts.get(k, 0)) for k in targets}
        total_remaining = sum(remaining.values())
        total_target = sum(targets.values())
        total_done = sum(chain_counts.get(k, 0) for k in targets)

        # Per-macro coverage detail (canonical names on both sides)
        macro_detail = {}
        for m in all_macros:
            count = sum(1 for t in site_tasks
                        if m in {_canon(x) for x in t.get("macros", [])})
            macro_detail[m] = {"count": count, "covered": m in covered}

        sites[sid] = {
            "name": s.get("name", sid),
            "total_macros": total_macros,
            "covered_macros": total_macros - len(uncovered),
            "uncovered": uncovered,
            "chain_counts": chain_counts,
            "chain_targets": targets,
            "chain_remaining": remaining,
            "tasks_done": len(site_tasks),
            "tasks_target": total_target,
            "tasks_remaining": total_remaining,
            "macros": macro_detail,
        }

    # Global summary
    total_tasks_done = len(all_tasks)
    total_tasks_remaining = sum(s["tasks_remaining"] for s in sites.values())
    total_sites_complete = sum(1 for s in sites.values() if s["tasks_remaining"] == 0)
    all_possible_macros = set()
    for site_macros in MACRO_LOCATIONS.values():
        all_possible_macros.update(_canon(m) for m in site_macros.keys())
    # Intersect with the pool so stray macro names in old task files can't
    # push "covered" above what the denominator counts
    total_macros_covered = len({_canon(m) for t in all_tasks
                                for m in t.get("macros", [])} & all_possible_macros)
    return jsonify({
        "sites": sites,
        "total_tasks_done": total_tasks_done,
        "total_tasks_remaining": total_tasks_remaining,
        "total_sites": len(sites),
        "sites_complete": total_sites_complete,
        "macros_covered": total_macros_covered,
        "macros_total": len(all_possible_macros),
    })


@annotation_bp.route("/api/floor_k", methods=["GET", "POST"])
def api_floor_k():
    """Get or set the coverage-floor K (sites per macro)."""
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        try:
            k = max(1, min(10, int(data.get("k"))))
        except (TypeError, ValueError):
            return jsonify({"error": "k must be an integer 1-10"}), 400
        _FLOOR_CONFIG_FILE.write_text(json.dumps({"k": k}))
        return jsonify({"k": k})
    return jsonify({"k": _get_floor_k()})


@annotation_bp.route("/api/site_floors")
def api_site_floors():
    """Per-site K-floor status: how many macros still need THIS site.

    covered/total where total = site's macro pool and covered = macros that
    are either already demonstrated here or globally at their K-site target.
    """
    global_cov = _get_macro_site_coverage()
    k_targets = _macro_k_targets()
    floors = {}
    for s in _load_sites():
        sid = s["id"]
        pool = _site_macro_pool(sid)
        needy = sum(1 for m in pool
                    if sid not in global_cov.get(m, set())
                    and len(global_cov.get(m, set())) < k_targets.get(m, _get_floor_k()))
        floors[sid] = {"covered": len(pool) - needy, "total": len(pool)}
    return jsonify(floors)


@annotation_bp.route("/api/auto_login", methods=["POST"])
def api_auto_login():
    """Log into the specified sites as user 1 (Alex Rivera).

    Sets session["user_id"] and any site-specific session keys so the
    sites render as logged-in when the browser loads them.
    """
    data = request.get_json(silent=True) or {}
    site_ids = data.get("sites", [])
    if not site_ids:
        return jsonify({"error": "sites list required"}), 400

    from app import db

    # Clear the no-autologin flag so before_request auto-login works normally
    session.pop("_no_autologin", None)

    # Site-specific session keys for sites that don't use the generic "user_id"
    SITE_SESSION_KEYS = {
        "conference-review-submission": "conf_review_uid",
        "health-portals": "health_user_id",
        "insurance-loans": "il_user_id",
        "instant-messaging": "im_user_id",
        "job-sites": "job_sites_user_id",
        "live": "live_user_id",
        "qa-knowledge": "qa_user_id",
        "university-academic": "ua_user",
        "version-control": "vc_user_id",
        "video": "user_id",  # also needs username + display_name
        "weather": "weather_user_id",
        "team-chat-workspace": "user_id",  # uses root_user_id
        "remote-calls": "user_id",  # uses root_user_id, not the rc-u-XXX id
    }

    logged_in = []
    for site_id in site_ids:
        try:
            users = db.query(site_id, "users", limit=5)
            if not users:
                continue

            # Find Alex Rivera or use first user
            user = None
            for u in users:
                name = " ".join(str(v) for v in [
                    u.get("name", ""), u.get("display_name", ""), u.get("username", "")
                ]).lower()
                if "alex" in name or "rivera" in name:
                    user = u
                    break
            if not user:
                user = users[0]

            uid = user.get("id", user.get("root_user_id", 1))
            # Sites that read session["user_id"] as a root_user_id
            if site_id in ("team-chat-workspace", "remote-calls"):
                uid = user.get("root_user_id", uid)

            # Namespaced per-site key (app/__init__ swaps this into
            # session["user_id"] on requests to /sites/<site_id>/...)
            session[f"_uid_{site_id}"] = uid
            # Generic key too, for the current request cycle
            session["user_id"] = uid

            # Set site-specific session key
            if site_id in SITE_SESSION_KEYS:
                key = SITE_SESSION_KEYS[site_id]
                if site_id == "university-academic":
                    session[key] = user.get("net_id", user.get("username", ""))
                elif site_id == "version-control":
                    session[key] = user.get("root_user_id", uid)
                    session["vc_username"] = user.get("username", "")
                    session["vc_name"] = user.get("name", "")
                elif site_id in ("team-chat-workspace", "remote-calls"):
                    session[key] = user.get("root_user_id", uid)
                elif site_id == "video":
                    session[key] = uid
                    session["username"] = user.get("username", "")
                    session["display_name"] = user.get("display_name", user.get("name", ""))
                else:
                    session[key] = uid

            logged_in.append(site_id)
        except Exception as exc:
            import traceback
            traceback.print_exc()

    return jsonify({"logged_in": logged_in})


@annotation_bp.route("/api/auto_logout", methods=["POST"])
def api_auto_logout():
    """Clear all login-related session keys so sites render as logged out."""
    # All known login session keys
    login_keys = [
        "user_id", "conf_review_uid", "health_user_id", "health_pending_verify_id",
        "il_user_id", "im_user_id", "job_sites_user_id", "live_user_id",
        "qa_user_id", "ua_user", "vc_user_id", "vc_username", "vc_name",
        "weather_user_id", "username", "display_name",
    ]
    cleared = []
    for key in login_keys:
        if key in session:
            session.pop(key)
            cleared.append(key)
    # Namespaced per-site keys (app/__init__ per-site session isolation)
    for key in [k for k in session if k.startswith("_uid_")]:
        session.pop(key)
        cleared.append(key)
    # Prevent the before_request auto-login from re-setting user_id
    session["_no_autologin"] = True
    return jsonify({"cleared": cleared})


@annotation_bp.route("/api/toggle_2fa", methods=["POST"])
def api_toggle_2fa():
    """Enable or disable 2FA for the current session."""
    data = request.get_json(silent=True) or {}
    if data.get("disable"):
        session["_disable_2fa"] = True
    else:
        session.pop("_disable_2fa", None)
    return jsonify({"disabled": bool(session.get("_disable_2fa"))})


@annotation_bp.route("/api/reset_tasks", methods=["POST"])
def api_reset_tasks():
    """Delete annotation tasks from file storage. Requires annotator name."""
    from annotation.storage import list_tasks, delete_task, get_annotators
    data = request.get_json(silent=True) or {}
    annotator = data.get("annotator", "")

    if not annotator:
        return jsonify({"error": "Must specify annotator", "annotators": get_annotators()}), 400

    tasks = list_tasks(annotator)
    count = 0
    for t in tasks:
        if delete_task(annotator, t["task_id"]):
            count += 1

    return jsonify({"message": f"Deleted {count} tasks for '{annotator}'.", "deleted": count, "annotator": annotator})


@annotation_bp.route("/api/annotators")
def api_annotators():
    from annotation.storage import get_annotators, get_stats
    return jsonify({"annotators": get_annotators(), "stats": get_stats()})


@annotation_bp.route("/api/tasks/<task_id>")
def api_get_task(task_id):
    from annotation.storage import load_task
    annotator = request.args.get("annotator", "")
    if not annotator:
        # Try all annotators
        from annotation.storage import get_annotators
        for ann in get_annotators():
            task = load_task(ann, task_id)
            if task:
                return jsonify(task)
        return jsonify({"error": "Task not found"}), 404
    task = load_task(annotator, task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404
    return jsonify(task)


@annotation_bp.route("/api/tasks/<task_id>", methods=["DELETE"])
def api_delete_task(task_id):
    """Move a task to the recoverable .trash (per-task delete from review)."""
    from annotation.storage import ANNOTATIONS_DIR, get_annotators, trash_task
    annotator = request.args.get("annotator", "")
    if not annotator:
        annotator = next((a for a in get_annotators()
                          if (ANNOTATIONS_DIR / a / task_id).exists()), "")
    dest = trash_task(annotator, task_id) if annotator else None
    if not dest:
        return jsonify({"error": "Task not found"}), 404
    return jsonify({"status": "trashed", "task_id": task_id, "trash_path": dest})


@annotation_bp.route("/api/report", methods=["POST"])
def api_report():
    """Save a skip report (reason + details) and record any NA macros."""
    data = request.get_json(silent=True) or {}
    sites = data.get("sites", [])
    annotator = data.get("annotator", "anonymous")

    # Persist the full skip report — reason/details were previously discarded
    report = {
        "sites": sites,
        "macros": data.get("macros", []),
        "reason": data.get("reason", ""),
        "details": data.get("details", ""),
        "instruction": data.get("instruction", ""),
        "annotator": annotator,
        "timestamp": datetime.now().isoformat(),
    }
    reports = []
    if _SKIP_REPORTS_FILE.exists():
        try:
            reports = json.loads(_SKIP_REPORTS_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            reports = []
    reports.append(report)
    _SKIP_REPORTS_FILE.write_text(json.dumps(reports, indent=2))

    # Persist NA macro reports
    na_macros = data.get("macros_not_applicable", {})
    saved_na = 0
    for macro, _site_info in na_macros.items():
        _save_na_report(sites, macro, annotator)
        saved_na += 1

    return jsonify({"status": "reported", "na_saved": saved_na,
                    "skip_saved": True})


@annotation_bp.route("/api/routes/<site_id>")
def api_routes(site_id):
    """Extract API routes from a site's routes.py for annotator reference."""
    import re as _re
    routes_file = SITES_DIR / site_id / "routes.py"
    if not routes_file.exists():
        return jsonify([])
    try:
        content = routes_file.read_text()
    except OSError:
        return jsonify([])

    results = []
    func_pattern = _re.compile(
        r'@\w+\.route\(["\']([^"\']+)["\']\s*'
        r'(?:,\s*methods=\[([^\]]*)\])?\)'
        r'(.*?)(?=\n@\w+\.route|\nclass |\Z)',
        _re.DOTALL,
    )
    for match in func_pattern.finditer(content):
        path = match.group(1)
        methods_raw = match.group(2)
        body = match.group(3)

        if "/api/" not in path:
            continue

        if methods_raw:
            methods = [m.strip().strip("'\"") for m in methods_raw.split(",")]
        else:
            methods = ["GET"]

        func_match = _re.search(r'def\s+(\w+)\s*\(', body)
        func_name = func_match.group(1) if func_match else ""

        docstring = ""
        doc_match = _re.search(r'"""(.+?)"""', body, _re.DOTALL)
        if not doc_match:
            doc_match = _re.search(r"'''(.+?)'''", body, _re.DOTALL)
        if doc_match:
            docstring = doc_match.group(1).strip().split("\n")[0].strip()

        params = list(dict.fromkeys(
            _re.findall(r'request\.args\.get\(["\'](\w+)', body)
        ))
        body_fields = list(dict.fromkeys(
            _re.findall(r'data(?:\.get)?\(?["\'](\w+)', body)
        ))
        response_fields = list(dict.fromkeys(
            _re.findall(r'jsonify\(\{["\'](\w+)', body)
        ))[:6]

        for method in methods:
            desc = docstring or _generate_route_description(
                method, path, func_name, params, body_fields,
            )
            results.append({
                "method": method,
                "path": path,
                "description": desc,
                "params": params if method == "GET" else [],
                "body_fields": body_fields if method != "GET" else [],
                "returns": response_fields,
            })

    return jsonify(results)


def _generate_route_description(method, path, func_name, params, body_fields):
    parts = [p for p in path.replace("/api/", "").split("/")
             if p and not p.startswith("<")]
    resource = parts[0].replace("_", " ").replace("-", " ") if parts else "resource"
    action = parts[-1].replace("_", " ").replace("-", " ") if len(parts) > 1 else ""
    has_id = "<" in path
    is_sub = len(parts) > 1

    if method == "GET":
        if action == "search":
            return f"Keyword search across {resource}"
        if action == "semantic":
            return f"Semantic/natural-language search across {resource}"
        if action == "stats":
            return f"Get aggregate statistics for {resource}"
        if action == "export":
            return f"Export {resource} data"
        if action in ("count", "counts"):
            return f"Count {resource}"
        if is_sub and action:
            return f"Get {action} for {resource.rstrip('s')}"
        if has_id:
            return f"Get single {resource.rstrip('s')} by ID"
        if params:
            filterable = ", ".join(params[:5])
            return f"List {resource} (filter: {filterable})"
        return f"List all {resource}"
    elif method == "POST":
        if "login" in path or "auth" in path:
            return "Authenticate and create session"
        if "register" in path or "signup" in path:
            return "Register new user account"
        if is_sub and action:
            act = action.capitalize()
            if action in ("follow", "save", "star", "bookmark", "like",
                          "subscribe", "favorite", "flag", "report"):
                return f"Toggle {action} on {resource.rstrip('s')}"
            return f"{act} on {resource.rstrip('s')}"
        if body_fields:
            return f"Create {resource.rstrip('s')} ({', '.join(body_fields[:4])})"
        return f"Create new {resource.rstrip('s')}"
    elif method == "PUT":
        return f"Update {resource.rstrip('s')}"
    elif method == "DELETE":
        return f"Delete {resource.rstrip('s')} by ID"
    return f"{method} {resource}"


@annotation_bp.route("/api/graph/edges")
def api_graph_edges():
    """Get all graph edges from proposed_edges.csv."""
    import csv
    edges = []
    edges_file = Path(__file__).parent / "proposed_edges.csv"
    if edges_file.exists():
        with open(edges_file) as f:
            for i, row in enumerate(csv.DictReader(f)):
                if row.get("status") == "approved":
                    edges.append({
                        "id": i,
                        "source": row.get("source", ""),
                        "target": row.get("target", ""),
                        "event_type": row.get("event_type", ""),
                        "kind": row.get("kind", ""),
                    })
    return jsonify(edges)


@annotation_bp.route("/api/graph/edges", methods=["POST"])
def api_add_graph_edge():
    """Add a new edge."""
    data = request.get_json(silent=True) or {}
    source = data.get("source", "")
    target = data.get("target", "")
    event_type = data.get("event_type", "")
    if not source or not target or not event_type:
        return jsonify({"error": "source, target, and event_type required"}), 400
    edge_id = None
    return jsonify({"id": edge_id, "status": "saved"})


@annotation_bp.route("/api/graph/edges/<int:edge_id>", methods=["DELETE"])
def api_delete_graph_edge(edge_id):
    """Delete a custom edge."""
    None
    return jsonify({"status": "deleted"})


@annotation_bp.route("/api/graph/positions")
def api_graph_positions():
    """Get saved node positions."""
    return jsonify({})


@annotation_bp.route("/api/graph/positions", methods=["POST"])
def api_save_graph_positions():
    """Save node positions."""
    data = request.get_json(silent=True) or {}
    None
    return jsonify({"status": "saved"})


@annotation_bp.route("/api/graph/seed", methods=["POST"])
def api_seed_graph():
    """Seed built-in edges from site_affinities.py event flow map."""
    builtin_edges = [
        # purchase
        ("e-commerce", "banking", "purchase"), ("e-commerce", "email", "purchase"),
        ("auctions-p2p-marketplaces", "banking", "purchase"), ("auctions-p2p-marketplaces", "email", "purchase"),
        ("books-comics", "banking", "purchase"), ("books-comics", "email", "purchase"),
        ("ticketing-events", "banking", "purchase"), ("ticketing-events", "email", "purchase"),
        # payment
        ("crowdfunding-donations", "banking", "payment"),
        ("tax-filing-dmv-permits", "banking", "payment"),
        ("flights-hotels", "banking", "payment"),
        ("insurance-loans", "banking", "payment"),
        # trade
        ("brokerage", "banking", "trade"),
        # booking
        ("flights-hotels", "calendar-todo", "booking"), ("flights-hotels", "email", "booking"),
        ("health-portals", "calendar-todo", "booking"), ("health-portals", "email", "booking"),
        ("remote-calls", "calendar-todo", "booking"), ("remote-calls", "email", "booking"),
        ("ticketing-events", "calendar-todo", "booking"), ("ticketing-events", "email", "booking"),
        # signup
        ("auctions-p2p-marketplaces", "email", "signup"), ("auctions-p2p-marketplaces", "password-managers", "signup"),
        ("forums", "email", "signup"), ("forums", "password-managers", "signup"),
        ("health-portals", "email", "signup"), ("health-portals", "password-managers", "signup"),
        ("live", "email", "signup"), ("live", "password-managers", "signup"),
        ("qa-knowledge", "email", "signup"), ("qa-knowledge", "password-managers", "signup"),
        ("real-estate-buy-rent", "email", "signup"), ("real-estate-buy-rent", "password-managers", "signup"),
        ("ticketing-events", "email", "signup"),
        # subscribe / inquiry
        ("business-company", "email", "subscribe"),
        ("business-company", "email", "inquiry"),
        # file_created
        ("documents", "cloud-storage-file-transfer", "file_created"), ("documents", "email", "file_created"),
        ("handwritten-notes-whiteboards", "cloud-storage-file-transfer", "file_created"),
        ("spreadsheets-slides", "cloud-storage-file-transfer", "file_created"),
        ("insurance-loans", "cloud-storage-file-transfer", "file_created"),
        # message
        ("dating", "instant-messaging", "message"),
        # 2FA
        ("password-managers", "instant-messaging", "2fa_code"),
    ]
    count = 0
    for src, tgt, evt in builtin_edges:
        None
        count += 1
    return jsonify({"seeded": count})


@annotation_bp.route("/api/refine", methods=["POST"])
def api_refine_instruction():
    """Refine an annotator's task instruction using an LLM."""
    data = request.get_json(silent=True) or {}
    instruction = data.get("instruction", "").strip()
    if not instruction:
        return jsonify({"error": "No instruction provided"}), 400

    sites = data.get("sites", [])
    macros = data.get("macros", [])

    macro_context = ""
    if macros:
        descs = []
        for m in macros[:6]:
            d = _MACRO_DESCRIPTIONS.get(m, {})
            if d:
                descs.append(f"- {m}: {d.get('description', '')}")
        if descs:
            macro_context = "\n\nThe task should exercise these interaction patterns:\n" + "\n".join(descs)

    site_context = ""
    if sites:
        site_context = f"\n\nTarget sites: {', '.join(sites)}"

    system_prompt = (
        "Rewrite this task instruction so it sounds like a person casually asking "
        "their assistant to do something on a website. Keep it natural and conversational "
        "— like a Slack message or a quick verbal request, not a formal test case.\n\n"
        "Rules:\n"
        "- Use 'I need you to...', 'Can you...', 'Go to... and...', 'Find me...' etc.\n"
        "- Be specific about what to do but don't over-explain obvious steps\n"
        "- Include concrete values (names, numbers, categories) when the draft has them\n"
        "- One short paragraph, no bullet points or numbered steps\n"
        "- Don't mention 'the website' or 'the page' — just say what to do\n\n"
        "Output ONLY the rewritten instruction, nothing else."
        + site_context + macro_context
    )

    refined = _call_llm(system_prompt, instruction)
    if refined:
        return jsonify({"refined": refined})
    return jsonify({"error": "LLM unavailable — check OPENAI_API_KEY in .env"}), 503


def _call_llm(system_prompt, user_prompt):
    """Call LLM via the shared model-routing helper (default model)."""
    from app.llm import call_llm
    return call_llm(user_prompt, system=system_prompt, max_tokens=500, temperature=0.4)


@annotation_bp.route("/api/llm_models")
def api_llm_models():
    """Supported models per provider, with configuration status."""
    from app.llm import list_models, DEFAULT_MODEL, _get_env
    return jsonify({
        "default": _get_env("LLM_MODEL") or DEFAULT_MODEL,
        "providers": list_models(),
    })


@annotation_bp.route("/api/make_ambiguous", methods=["POST"])
def api_make_ambiguous():
    """Rewrite an instruction to be more ambiguous using LLM."""
    data = request.get_json(silent=True) or {}
    instruction = data.get("instruction", "").strip()
    if not instruction:
        return jsonify({"error": "No instruction provided"}), 400

    # Rewrite VOICE ONLY. The task already has a recorded trajectory and an
    # expected outcome, so the rewrite must not change what the agent has to do:
    # every name, id, amount and date stays. What changes is how the request
    # sounds — a colleague asking a favour (the house style, modelled on the
    # dataset's strongest instructions) instead of a spec that walks the agent
    # through the UI.
    system_prompt = (
        "You rephrase a web-task instruction so it sounds like a real person asking "
        "a colleague for a favour, instead of a spec.\n\n"

        "DIFFICULTY MUST NOT CHANGE. The task already has a recorded trajectory and "
        "a verifier — the agent must end up doing exactly the same work.\n"
        "- KEEP every specific: names, emails, IDs, amounts, dates, filenames, "
        "credentials, text to type, the sort order, the filter values.\n"
        "- Do NOT replace a name with a description ('Priya Sharma' must NOT become "
        "'the person who ran the deploy') — that adds a lookup the original task "
        "never asked for.\n"
        "- Do NOT add or remove any step.\n"
        "- If the instruction names a required mechanism ('using the slider'), keep it: "
        "the verifier checks it.\n\n"

        "WHAT YOU MAY CHANGE — only the wording:\n"
        "- Drop UI hand-holding: 'go to the History page', 'click the Filter button', "
        "'open the dropdown'. Say what is wanted, not which widget to press.\n"
        "- Make it conversational: how someone would actually ask. A short reason for "
        "the request is welcome if it does not add work.\n"
        "- 1-3 sentences.\n\n"

        "The house style (real examples):\n"
        "  'Hey, what course is Dr. Balazinska teaching? Can you give me the official "
        "course name?'\n"
        "  \"Let's start to file a new claim - can you select auto for the policy?\"\n"
        "  'I want to talk with the person running the Architecture Sync before-hand to "
        "ask them some questions. Can you make a new calendar event, then invite whoever "
        "owns that meeting for 30 minutes before that meeting starts.'\n"
        "  (note: the last one keeps its own indirection because the ORIGINAL task was "
        "written that way — do not invent indirection that was not there.)\n\n"

        "Output ONLY the rephrased instruction, nothing else."
    )

    result = _call_llm(system_prompt, instruction)
    if result:
        return jsonify({"ambiguous": result})
    return jsonify({"error": "LLM unavailable"}), 503


@annotation_bp.route("/api/suggest_tags", methods=["POST"])
def api_suggest_tags():
    """Use LLM to suggest macro span tags for a trajectory."""
    data = request.get_json(silent=True) or {}
    task_id = data.get("task_id")
    annotator = data.get("annotator", "anonymous")
    if not task_id:
        return jsonify({"error": "task_id required"}), 400

    # Support inline mode (from annotate UI) or saved task mode (from verify UI)
    if data.get("_inline"):
        macros = data.get("macros", [])
        actions = data.get("actions", [])
        instruction = data.get("instruction", "")
    else:
        from annotation.storage import load_task
        task = load_task(annotator, task_id)
        if not task:
            return jsonify({"error": "Task not found"}), 404

        macros = task.get("macros", [])
        trajectory = task.get("trajectory", [])
        instruction = task.get("instruction", "")

        # Build a compact action list for the LLM
        actions = []
        for i, e in enumerate(trajectory):
            if e.get("type") == "action":
                verb = e.get("action", "")
                target = (e.get("target", ""))[:60]
                val = e.get("text", e.get("value", ""))
                val_str = f' "{str(val)[:30]}"' if val else ""
                actions.append(f"{len(actions) + 1}. {verb} {target}{val_str}")

    if not actions or not macros:
        return jsonify({"error": "No actions or macros to tag"}), 400

    system_prompt = (
        "You are tagging a web interaction trajectory with macro labels.\n\n"
        "Each macro is a primitive skill (like filter_by_slider, create_by_form, etc.).\n"
        "A span is [start_index, end_index] (inclusive, 1-indexed) indicating which actions belong to that macro.\n"
        "Actions are numbered starting from 1.\n\n"
        "Rules:\n"
        "- Every macro must get exactly one span\n"
        "- Spans can overlap if a macro encompasses sub-macros (e.g., extract_by_extremum covers the full flow)\n"
        "- Navigation actions (clicking nav links) at the start should be untagged\n"
        "- Include the submit/confirm action at the end of form-based macros\n"
        "- For QA macros (extract/compute) with no visible actions, use the span where the answer is visible\n\n"
        "Output ONLY a JSON object mapping macro names to [start, end] spans. Example:\n"
        '{"filter_by_dropdown": [1, 5], "extract_by_route": [6, 10]}'
    )

    user_prompt = (
        f"Task instruction: {instruction}\n\n"
        f"Macros to tag: {macros}\n\n"
        f"Action trajectory:\n" + "\n".join(actions)
    )

    result = _call_llm(system_prompt, user_prompt)
    if not result:
        return jsonify({"error": "LLM unavailable"}), 503

    try:
        # Parse JSON from response
        import re
        json_match = re.search(r'\{[^}]+\}', result)
        if json_match:
            spans = json.loads(json_match.group())
            return jsonify({"suggested_spans": spans})
        return jsonify({"error": "Could not parse LLM response", "raw": result}), 500
    except Exception as e:
        return jsonify({"error": str(e), "raw": result}), 500


@annotation_bp.route("/api/build_verifiers", methods=["POST"])
def api_build_verifiers():
    """Build verifier configs: deterministic checks + LLM for expected_outcome.

    1. Auto-generate grounding, action, and state checks from the trajectory
    2. If expected_outcome is provided, call GPT-5.5 to parse it into extra checks
    3. If feedback + existing_configs, call GPT-5.5 to fix the existing configs
    4. Auto-run all checks and return results
    """
    from flask import current_app
    data = request.get_json(silent=True) or {}

    client = current_app.test_client()
    for key, val in request.cookies.items():
        client.set_cookie(key, val)

    # 1. Fetch request log and enrich trajectory
    log_resp = client.get("/_admin/log")
    log_data = log_resp.get_json() if log_resp.status_code == 200 else {}
    request_log = log_data.get("entries", []) if isinstance(log_data, dict) else log_data
    trajectory = data.get("trajectory", [])
    enriched = _enrich_trajectory(trajectory, request_log)

    macro_spans = data.get("macro_spans", {})
    expected_answer = data.get("expected_answer", "")
    expected_outcome = data.get("expected_outcome", "")
    feedback = data.get("feedback", "")
    existing_configs = data.get("existing_configs")

    # 2. Gather admin API schema per site
    schemas = {}
    sites_list = data.get("sites", [])
    for site in sites_list:
        sid = site["id"] if isinstance(site, dict) else site
        r = client.get(f"/_admin/files/{sid}")
        if r.status_code == 200:
            schemas[sid] = r.get_json()

    # 3. If feedback + existing configs → fix mode via LLM
    if feedback and existing_configs:
        configs = _llm_fix_verifiers(existing_configs, feedback, schemas)
        if not configs:
            configs = existing_configs  # fallback: keep originals
    else:
        # 4. Auto-generate deterministic checks per macro span
        configs = _auto_generate_verifiers(enriched, macro_spans, expected_answer)

        # 5. If expected_outcome provided, augment with LLM-parsed checks
        if expected_outcome:
            extra = _llm_parse_outcome(expected_outcome, macro_spans, schemas, enriched)
            if extra:
                _merge_llm_checks(configs, extra)

    # 6. Auto-run
    from annotation.evaluators import run_task_eval
    passed, results = run_task_eval(
        configs,
        server_url=request.host_url.rstrip("/"),
        flask_client=client,
        trajectory=trajectory,
        agent_answer=expected_answer,
    )

    return jsonify({"configs": configs, "results": results, "passed": passed})


def _auto_generate_verifiers(enriched_trajectory, macro_spans, expected_answer):
    """Deterministically generate verifier configs from trajectory data."""
    configs = []
    macro_names = list(macro_spans.keys())

    for macro, span in macro_spans.items():
        if not span or len(span) < 2:
            continue
        start, end = span

        checks = []

        # Extract actions and observations in this span
        action_idx = 0
        span_urls = set()
        span_actions = []
        span_api_calls = []

        for entry in enriched_trajectory:
            action_idx += 1
            if action_idx < start or action_idx > end:
                continue
            url = entry.get("url", "")
            if url and url.startswith("/sites/"):
                span_urls.add(url.split("?")[0])  # strip query params
            span_actions.append(entry)
            for call in entry.get("api_calls", []):
                span_api_calls.append(call)

        # Grounding: require visited URLs
        if span_urls:
            checks.append({
                "type": "grounding",
                "required_urls": sorted(span_urls),
                "description": f"Visited {len(span_urls)} page(s) during {macro}",
            })

        # Action checks: verify key actions occurred
        for act in span_actions:
            action_type = act.get("action", "")
            target = act.get("target", "")
            if action_type in ("click", "type", "select", "navigate", "tab_switch"):
                checks.append({
                    "type": "action_performed",
                    "action": action_type,
                    "target_contains": target[:50] if target else "",
                    "description": f"{action_type} on {target[:40]}",
                })
                break  # one key action per macro is enough

        # State checks from API calls (POST/PUT/DELETE = mutations)
        for call in span_api_calls:
            method = call.get("method", "")
            path = call.get("path", "")
            if method in ("POST", "PUT", "DELETE") and "/api/" in path:
                # Convert site API path to admin path
                # /sites/forums/api/posts -> /_admin/data/forums/posts
                parts = path.split("/api/")
                if len(parts) == 2:
                    site_part = parts[0].replace("/sites/", "")
                    collection = parts[1].split("/")[0].split("?")[0]
                    admin_endpoint = f"/_admin/data/{site_part}/{collection}"
                    if method == "POST":
                        checks.append({
                            "type": "state_query",
                            "endpoint": admin_endpoint,
                            "params": {},
                            "check": "not_empty",
                            "description": f"Records exist in {site_part}/{collection} after {method}",
                        })
                    elif method == "DELETE":
                        body = call.get("body", {})
                        item_id = body.get("id", "")
                        if item_id:
                            checks.append({
                                "type": "record_absent",
                                "endpoint": admin_endpoint,
                                "params": {"id": str(item_id)},
                                "description": f"Record {item_id} deleted from {collection}",
                            })
                break  # one state check per macro

        # Answer match: if this is the last macro and answer is provided
        if expected_answer and macro == macro_names[-1]:
            match_type = "number" if expected_answer.replace(".", "").replace("-", "").isdigit() else "string"
            checks.append({
                "type": "answer_match",
                "expected": expected_answer,
                "match_type": match_type,
                "description": f"Answer matches '{expected_answer}'",
            })

        configs.append({
            "macro": macro,
            "span": span,
            "checks": checks,
        })

    return configs


def _llm_parse_outcome(expected_outcome, macro_spans, schemas, trajectory):
    """Call LLM to parse expected_outcome text into extra check configs."""
    schema_summary = {}
    for site, colls in schemas.items():
        if isinstance(colls, list):
            schema_summary[site] = colls[:15]

    # Extract API calls from trajectory to show LLM what endpoints exist
    api_examples = []
    for entry in trajectory:
        for call in entry.get("api_calls", []):
            path = call.get("path", "")
            if "/api/" in path:
                example = {"method": call.get("method"), "path": path, "status": call.get("status")}
                if call.get("body"):
                    example["body_fields"] = list(call["body"].keys()) if isinstance(call["body"], dict) else []
                if call.get("response") and isinstance(call["response"], list) and call["response"]:
                    example["response_fields"] = list(call["response"][0].keys()) if isinstance(call["response"][0], dict) else []
                elif call.get("response") and isinstance(call["response"], dict):
                    example["response_fields"] = list(call["response"].keys())
                api_examples.append(example)
                if len(api_examples) >= 10:
                    break

    prompt = f"""Parse this expected outcome into verifier check configs for a web benchmark.

Expected outcome (written by annotator):
{expected_outcome}

Macro spans (which macro each action range belongs to): {json.dumps(macro_spans)}

Available admin API collections per site: {json.dumps(schema_summary)}
The admin API endpoint format is: /_admin/data/<site_id>/<collection_name>
It accepts query params to filter (e.g. ?user_id=1&category=Groceries) and returns a JSON array of records.

API calls observed in the trajectory:
{json.dumps(api_examples, indent=2)}

For each assertion in the expected outcome, output a JSON object with ALL required fields:
{{
  "macro": "which_macro_this_check_belongs_to (must match a key in macro_spans)",
  "check": {{
    "type": "state_query",
    "endpoint": "/_admin/data/<site>/<collection>",
    "params": {{"field": "value"}},
    "check": "contains|count_equals|count_gt|equals|not_empty",
    "expected": "the expected value",
    "description": "human-readable description"
  }}
}}

Other valid check types:
- record_exists: {{"type":"record_exists", "endpoint":"/_admin/data/...", "params":{{}}, "description":"..."}}
- record_absent: {{"type":"record_absent", "endpoint":"/_admin/data/...", "params":{{}}, "description":"..."}}
- count_equals: {{"type":"count_equals", "endpoint":"/_admin/data/...", "params":{{}}, "expected":5, "description":"..."}}

IMPORTANT RULES:
- Every check MUST have "endpoint" with a valid /_admin/data/<site>/<collection> path
- Use the admin API collections list and trajectory API calls to determine correct site and collection names
- The "macro" field MUST exactly match one of the keys in macro_spans
- Each assertion should go to the macro that is responsible for it
- Only generate checks for things the annotator explicitly mentioned — do not invent extra checks
- For "contains" checks, use {{"check": "contains", "expected": "the text to find"}}
- For record existence, use params to filter (e.g. {{"body": "15:34"}}) based on what was in the API call

Output a JSON array of these objects. If nothing to add, output [].
Output ONLY the JSON array, no explanation."""

    result = _call_openai_simple("gpt-4.1-nano", prompt, max_tokens=1500)
    if not result:
        return None
    try:
        text = result.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text.strip())
    except (json.JSONDecodeError, IndexError):
        return None


def _llm_fix_verifiers(existing_configs, feedback, schemas):
    """Call GPT-5.5 to fix existing verifier configs based on feedback."""
    schema_summary = {}
    for site, colls in schemas.items():
        if isinstance(colls, list):
            schema_summary[site] = colls[:15]

    prompt = f"""Fix these verifier configs based on the annotator's feedback.

Current configs:
{json.dumps(existing_configs, indent=2)}

Feedback:
{feedback}

Available admin API collections: {json.dumps(schema_summary)}

Apply ONLY the changes described in the feedback. Keep everything else unchanged.
Output the full corrected JSON array. Output ONLY the JSON array."""

    result = _call_openai_simple("gpt-4.1-nano", prompt, max_tokens=2000)
    if not result:
        return None
    try:
        text = result.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text.strip())
    except (json.JSONDecodeError, IndexError):
        return None


def _merge_llm_checks(configs, extra_checks):
    """Merge LLM-generated checks into existing macro configs."""
    for item in extra_checks:
        macro = item.get("macro", "")
        check = item.get("check", {})
        if not macro or not check:
            continue
        # Find the matching macro config
        target = next((c for c in configs if c["macro"] == macro), None)
        if target:
            target["checks"].append(check)
        elif configs:
            # Append to last config if macro not found
            configs[-1]["checks"].append(check)


def _call_openai_simple(model, prompt, max_tokens=1500):
    """LLM call via shared Groq/OpenAI/Gemini helper."""
    from app.llm import call_llm
    try:
        return call_llm(prompt, max_tokens=max_tokens, temperature=0.2)
    except Exception:
        import traceback
        traceback.print_exc()
        return None


_verifier_processes = {}  # job_id -> subprocess.Popen


@annotation_bp.route("/api/verifier_status/<job_id>")
def api_verifier_status(job_id):
    """Check if a verifier builder job is done."""
    import pathlib as _pl
    result_file = _pl.Path(__file__).resolve().parent / "verifier_jobs" / f"{job_id}_verifiers.json"

    # Check subprocess status
    proc = _verifier_processes.get(job_id)
    if proc and proc.poll() is None:
        return jsonify({"status": "building", "ready": False})

    if not result_file.exists():
        return jsonify({"status": "not_found", "ready": False})

    try:
        configs = json.loads(result_file.read_text())
        if not isinstance(configs, list):
            return jsonify({"status": "invalid_output", "ready": False,
                            "error": "LLM output was not a JSON array"})
    except (json.JSONDecodeError, OSError) as e:
        return jsonify({"status": "error", "ready": False, "error": str(e)})

    return jsonify({"status": "done", "ready": True, "configs": configs})


@annotation_bp.route("/api/load_verifiers", methods=["POST"])
def api_load_verifiers():
    """Load verifier configs from file (written by the verifier builder)."""
    from flask import current_app
    data = request.get_json(silent=True) or {}
    result_file = data.get("result_file", "")

    if not result_file:
        return jsonify({"error": "No result_file specified"}), 400

    import pathlib as _pl
    path = _pl.Path(result_file)
    if not path.exists():
        return jsonify({"error": "File not found. Build verifiers first.", "ready": False})

    try:
        configs = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        return jsonify({"error": f"Failed to read file: {e}", "ready": False})

    # Auto-run the loaded configs
    client = current_app.test_client()
    for key, val in request.cookies.items():
        client.set_cookie(key, val)

    from annotation.evaluators import run_task_eval
    passed, results = run_task_eval(
        configs,
        server_url=request.host_url.rstrip("/"),
        flask_client=client,
        trajectory=data.get("trajectory", []),
        agent_answer=data.get("expected_answer", ""),
    )
    return jsonify({"configs": configs, "results": results, "passed": passed, "ready": True})


# ---------------------------------------------------------------------------
# Verification walk — the annotator walks the task a SECOND time in the verify
# panel, producing an independent trajectory of the same task.
#
# Two trajectories are worth more than one: whatever appears in both is
# load-bearing (the checks a verifier should assert), whatever appears in only
# one is incidental (a stray scroll, a fumbled field, a different route to the
# same page). A second walk that cannot reproduce the outcome also means the
# task is broken against current data — which is how silent drift gets caught.
# ---------------------------------------------------------------------------

def _load_saved_task(annotator, task_id):
    """Load (dir, task.json, trajectory.json) for a task; searches all annotators."""
    from annotation.storage import ANNOTATIONS_DIR
    pattern = f"{annotator}/{task_id}" if annotator else f"*/{task_id}"
    for d in ANNOTATIONS_DIR.glob(pattern):
        task = json.loads((d / "task.json").read_text())
        tf = d / "trajectory.json"
        traj = json.loads(tf.read_text()) if tf.exists() else []
        return d, task, traj
    return None, None, []


def _action_key(a):
    """Identity of an action for cross-walk comparison.

    Uses verb + semantic target + value. Deliberately NOT the selector:
    recorded selectors are often bare tags ("a", "select") with no
    discriminating power, while `target` carries the readable description.
    """
    val = a.get("value") or a.get("text") or a.get("option_text") or ""
    target = (a.get("target") or "").strip().lower()
    return (a.get("action", ""), target, str(val).strip().lower())


@annotation_bp.route("/api/verification_walk", methods=["POST"])
def api_verification_walk():
    """Save a second walk of a task and compare it to the original.

    Body: {task_id, annotator?, trajectory: [...], answer?}
    Writes verification_walk.json next to the task and returns the comparison.
    """
    data = request.get_json(silent=True) or {}
    task_id = data.get("task_id")
    if not task_id:
        return jsonify({"error": "task_id required"}), 400

    d, task, original = _load_saved_task(data.get("annotator"), task_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404

    walk = data.get("trajectory") or []
    walk_actions = [e for e in walk if e.get("type") == "action"]
    orig_actions = [e for e in original if e.get("type") == "action"]

    orig_keys = [_action_key(a) for a in orig_actions]
    walk_keys = [_action_key(a) for a in walk_actions]
    orig_set, walk_set = set(orig_keys), set(walk_keys)

    common = [k for k in orig_keys if k in walk_set]
    seen = set()
    common = [k for k in common if not (k in seen or seen.add(k))]

    payload = {
        "task_id": task_id,
        "answer": data.get("answer", ""),
        "recorded_at": datetime.now().isoformat(),
        "trajectory": walk,
    }
    (d / "verification_walk.json").write_text(json.dumps(payload, indent=1))

    def fmt(keys):
        return [{"action": k[0], "target": k[1][:60], "value": k[2][:30]} for k in keys]

    return jsonify({
        "task_id": task_id,
        "original_actions": len(orig_actions),
        "walk_actions": len(walk_actions),
        # in BOTH walks -> essential; a verifier should assert these
        "in_both": fmt(common),
        # in one walk only -> incidental; asserting these would fail a valid path
        "original_only": fmt([k for k in dict.fromkeys(orig_keys) if k not in walk_set]),
        "walk_only": fmt([k for k in dict.fromkeys(walk_keys) if k not in orig_set]),
        "answer_original": task.get("expected_answer", ""),
        "answer_walk": data.get("answer", ""),
        "answers_agree": _norm_answer(task.get("expected_answer", "")) ==
                         _norm_answer(data.get("answer", "")) if data.get("answer") else None,
    })


def _norm_answer(s):
    import re as _re
    s = str(s or "").lower()
    return " ".join(_re.sub(r"[^a-z0-9\s.]+", " ", s).split())


@annotation_bp.route("/api/task_status", methods=["POST"])
def api_task_status():
    """Approve or reject a task after review.

    Body: {task_id, annotator?, status: "approved"|"rejected", note?}
    Records the decision on task.json — rejected tasks stay on disk (the
    recording is still evidence) but are excluded from eval task loading.
    """
    data = request.get_json(silent=True) or {}
    task_id = data.get("task_id")
    status = data.get("status")
    if status not in ("approved", "rejected", "pending"):
        return jsonify({"error": "status must be approved, rejected or pending"}), 400

    d, task, _ = _load_saved_task(data.get("annotator"), task_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404

    task["review"] = {
        "status": status,
        "note": data.get("note", ""),
        "reviewer": session.get("annotator_name", "anonymous"),
        "reviewed_at": datetime.now().isoformat(),
    }
    (d / "task.json").write_text(json.dumps(task, indent=2, default=str))
    return jsonify({"task_id": task_id, "review": task["review"]})


@annotation_bp.route("/api/run_verifiers", methods=["POST"])
def api_run_verifiers():
    """Execute verifier configs — uses server request log for agent-agnostic checks."""
    from flask import current_app
    data = request.get_json(silent=True) or {}
    configs = data.get("configs", [])

    client = current_app.test_client()
    for key, val in request.cookies.items():
        client.set_cookie(key, val)

    # Fetch both request log AND action beacon log
    request_log = []
    action_log = []
    try:
        log_resp = client.get("/_admin/log")
        if log_resp.status_code == 200:
            request_log = log_resp.get_json().get("entries", [])
        beacon_resp = client.get("/_admin/beacon")
        if beacon_resp.status_code == 200:
            action_log = beacon_resp.get_json().get("entries", [])
    except Exception:
        pass

    from annotation.evaluators import run_task_eval
    passed, results = run_task_eval(
        configs,
        server_url=request.host_url.rstrip("/"),
        flask_client=client,
        trajectory=data.get("trajectory", []),
        agent_answer=data.get("expected_answer", ""),
        request_log=request_log,
        action_log=action_log,
    )
    return jsonify({"passed": passed, "results": results})


@annotation_bp.route("/api/agent_validate", methods=["POST"])
def api_agent_validate():
    """Run a browser-use agent with headless Chrome to attempt the task.

    Spawns a real browser session, navigates the site, and uses ChatLLM
    (Groq/OpenAI/Gemini) as the LLM to decide actions. After the agent finishes,
    we check the server request log + agent's answer against the verifiers.
    """
    import asyncio
    import sys
    from flask import current_app

    data = request.get_json(silent=True) or {}
    instruction = data.get("instruction", "")
    configs = data.get("configs", [])
    sites = data.get("sites", [])

    if not instruction:
        return jsonify({"error": "Missing instruction"}), 400

    site_ids = [s["id"] if isinstance(s, dict) else s for s in sites]
    base = request.host_url.rstrip("/")
    site_url = f"{base}/sites/{site_ids[0]}" if site_ids else base

    # Clear request log before agent runs
    client = current_app.test_client()
    for key, val in request.cookies.items():
        client.set_cookie(key, val)
    client.post("/_admin/log/clear")

    # Run browser-use agent
    agent_answer = ""
    agent_steps = 0
    agent_errors = []
    agent_response = ""
    agent_cookies = {}  # capture agent's session cookies for verifier

    async def _run_agent():
        nonlocal agent_answer, agent_steps, agent_errors, agent_response, agent_cookies

        # Import browser-use components
        sys.path.insert(0, str(PROJECT_ROOT / "evaluation"))
        # Ensure browser_use is findable (installed in ~/.local)
        import site as _site
        _user_site = str(Path.home() / ".local/lib/python3.11/site-packages")
        if _user_site not in sys.path:
            sys.path.insert(0, _user_site)
        from agents import ChatLLM
        from browser_use import Agent, BrowserSession

        llm = ChatLLM()
        browser_session = BrowserSession(headless=True)

        try:
            await browser_session.start()
            page = await browser_session.get_current_page()
            await page.goto(site_url)
            await asyncio.sleep(2)

            task_prompt = (
                f"You are on a web application at {site_url}. "
                f"Your task: {instruction}"
            )

            agent = Agent(
                task=task_prompt,
                llm=llm,
                browser_session=browser_session,
                use_vision=False,
                max_steps=15,
            )

            history = await asyncio.wait_for(agent.run(), timeout=120)
            agent_steps = len(history.history)
            agent_answer = history.final_result() or ""
            agent_errors = history.errors() or []
            agent_response = f"Completed in {agent_steps} steps"

            # Capture agent's cookies so verifiers use the agent's session
            try:
                cookies = await page.context.cookies()
                for c in cookies:
                    agent_cookies[c["name"]] = c["value"]
            except Exception:
                pass

        except asyncio.TimeoutError:
            agent_errors = ["Agent timed out after 120s"]
            agent_response = "Timed out"
        except Exception as e:
            agent_errors = [str(e)]
            agent_response = f"Error: {e}"
        finally:
            try:
                await browser_session.kill()
            except Exception:
                pass

    # Run the async agent in a new event loop
    try:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(_run_agent())
        loop.close()
    except Exception as e:
        agent_errors = [str(e)]
        agent_response = f"Loop error: {e}"

    # Create a new test client with the AGENT's cookies (isolated session)
    agent_client = current_app.test_client()
    for name, value in agent_cookies.items():
        agent_client.set_cookie(name, value)

    # Fetch request log using agent's session
    request_log = []
    try:
        log_resp = agent_client.get("/_admin/log")
        if log_resp.status_code == 200:
            request_log = log_resp.get_json().get("entries", [])
    except Exception:
        pass

    # Run verifiers against agent's session state
    from annotation.evaluators import run_task_eval
    agent_passed, agent_results = run_task_eval(
        configs, flask_client=agent_client,
        trajectory=[], agent_answer=agent_answer,
        request_log=request_log,
    )

    return jsonify({
        "agent_passed": agent_passed,
        "agent_results": agent_results,
        "agent_answer": agent_answer or "(no answer)",
        "agent_response": agent_response[:500],
        "agent_steps": agent_steps,
        "agent_errors": agent_errors[:3],
        "request_count": len(request_log),
    })


@annotation_bp.route("/api/perturb_verifiers", methods=["POST"])
def api_perturb_verifiers():
    """Run verifiers against 2 perturbed versions to validate they fail correctly.

    Perturbation 1: Wrong answer — swap expected answer to something different.
    Perturbation 2: Missing actions — remove key actions from the trajectory.

    Returns the original + 2 perturbed results with diffs highlighted.
    """
    from flask import current_app
    data = request.get_json(silent=True) or {}
    configs = data.get("configs", [])
    traj = data.get("trajectory", [])
    answer = data.get("expected_answer", "")

    client = current_app.test_client()
    for key, val in request.cookies.items():
        client.set_cookie(key, val)

    from annotation.evaluators import run_task_eval

    # Original (should pass)
    orig_passed, orig_results = run_task_eval(
        configs, flask_client=client, trajectory=traj, agent_answer=answer)

    # Perturbation 1: Wrong answer
    wrong_answer = _perturb_answer(answer)
    p1_passed, p1_results = run_task_eval(
        configs, flask_client=client, trajectory=traj, agent_answer=wrong_answer)

    # Perturbation 2: Remove actions — drop half the actions from trajectory
    instruction = data.get("instruction", "")
    thin_traj = _perturb_trajectory(traj, instruction)
    p2_passed, p2_results = run_task_eval(
        configs, flask_client=client, trajectory=thin_traj, agent_answer=answer)

    # Build trajectory summaries for diff display
    def _traj_summary(t):
        out = []
        for e in t:
            if e.get("type") != "action":
                continue
            a = e.get("action", "")
            target = e.get("target", "")
            if a == "type" and e.get("text"):
                label = f'{a} "{e["text"][:25]}"'
            elif a == "select" and e.get("option_text"):
                label = f'{a} "{e["option_text"]}"'
            elif a == "tab_switch":
                label = f'switch to {e.get("to_tab", "")}'
            else:
                label = f'{a} {target[:30]}'

            entry = {"label": label, "perturbed": bool(e.get("_perturbed"))}
            if e.get("_original"):
                entry["original"] = e["_original"]
            if e.get("_changed_to"):
                entry["changed_to"] = e["_changed_to"]
            out.append(entry)
        return out

    return jsonify({
        "original": {"passed": orig_passed, "results": orig_results, "answer": answer,
                      "actions": _count_actions(traj), "trajectory": _traj_summary(traj)},
        "perturbation_1": {"passed": p1_passed, "results": p1_results, "label": "Wrong answer",
                           "answer": wrong_answer, "trajectory": _traj_summary(traj),
                           "diff": f'"{answer}" \u2192 "{wrong_answer}"'},
        "perturbation_2": {"passed": p2_passed, "results": p2_results, "label": "Missing actions",
                           "actions": _count_actions(thin_traj), "trajectory": _traj_summary(thin_traj),
                           "diff": f'{_count_actions(traj)} \u2192 {_count_actions(thin_traj)} actions'},
    })


def _perturb_answer(answer):
    """Generate a plausible but wrong answer using LLM."""
    if not answer:
        return "wrong_answer"

    prompt = f"""Given this correct answer to a web task: "{answer}"

Generate a plausible but WRONG answer that:
- Is the same type (number if number, name if name, etc.)
- Looks realistic (not obviously garbage)
- Is clearly different from the correct answer

Output ONLY the wrong answer, nothing else."""

    result = _call_openai_simple("gpt-4.1-nano", prompt, max_tokens=50)
    if result:
        return result.strip().strip('"').strip("'")

    # Fallback if no API key
    try:
        n = float(answer)
        return str(int(n + 3) if n == int(n) else round(n + 2.5, 2))
    except (ValueError, TypeError):
        pass
    return answer[::-1] if len(answer) > 1 else "X"


def _perturb_trajectory(traj, instruction=""):
    """Generate a subtly wrong trajectory using LLM — keeps structure but changes key actions."""
    # Build a summary of the trajectory for the LLM
    actions = []
    for e in traj:
        if e.get("type") != "action":
            continue
        a = e.get("action", "")
        t = e.get("target", "")
        detail = ""
        if a == "type" and e.get("text"):
            detail = f': "{e["text"][:30]}"'
        elif a == "select" and e.get("option_text"):
            detail = f': "{e["option_text"]}"'
        elif a == "tab_switch":
            detail = f': {e.get("to_tab", "")}'
        actions.append(f'{a} {t[:40]}{detail}')

    if len(actions) < 2:
        # Too short to perturb meaningfully
        return [e for e in traj if e.get("type") == "observation" or e.get("action") in ("navigate", "tab_switch")]

    actions_text = "\n".join(f"{i+1}. {a}" for i, a in enumerate(actions))

    prompt = f"""Here is a sequence of browser actions for a web task:

Task: {instruction[:200] if instruction else '(not provided)'}

Actions:
{actions_text}

Create a WRONG version of this action sequence that would fail the task. Make subtle but meaningful changes:
- Change a dropdown selection to a wrong value
- Type a different search query
- Click a different button
- Navigate to a wrong page
- Skip a critical step

Keep 60-80% of actions the same. Change 2-3 key actions.

Output the modified sequence as numbered lines in the same format. Output ONLY the list."""

    result = _call_openai_simple("gpt-4.1-nano", prompt, max_tokens=500)

    if result:
        # Parse the LLM output back into trajectory entries
        perturbed = []
        lines = [l.strip() for l in result.strip().split("\n") if l.strip()]
        orig_actions = [e for e in traj if e.get("type") == "action"]

        for i, line in enumerate(lines):
            # Remove numbering
            line = line.lstrip("0123456789. ").strip()
            if i < len(orig_actions):
                entry = dict(orig_actions[i])
                # Check if LLM changed this action
                orig_desc = actions[i] if i < len(actions) else ""
                if line.lower() != orig_desc.lower():
                    entry["_perturbed"] = True
                    entry["_original"] = orig_desc
                    entry["_changed_to"] = line
                perturbed.append(entry)
            else:
                perturbed.append({"type": "action", "action": "click", "target": line, "_perturbed": True, "_changed_to": line})

        # Add observations back
        result_traj = []
        act_idx = 0
        for e in traj:
            if e.get("type") == "observation":
                result_traj.append(e)
            elif e.get("type") == "action":
                if act_idx < len(perturbed):
                    result_traj.append(perturbed[act_idx])
                act_idx += 1
        return result_traj

    # Fallback: simple removal
    return [e for e in traj if e.get("type") == "observation" or e.get("action") in ("navigate", "tab_switch")]


def _count_actions(traj):
    return sum(1 for e in traj if e.get("type") == "action")


def _enrich_trajectory(trajectory, request_log):
    """Attach API calls from request log to each action by timestamp."""
    actions = [e for e in trajectory if e.get("type") == "action"]
    if not actions or not request_log:
        return [
            {**a, "api_calls": []}
            for a in actions
        ]

    enriched = []
    log_idx = 0
    for i, action in enumerate(actions):
        act_time = action.get("timestamp", "")
        next_time = actions[i + 1]["timestamp"] if i + 1 < len(actions) else "9999"

        api_calls = []
        while log_idx < len(request_log):
            entry = request_log[log_idx]
            entry_time = entry.get("timestamp", "")
            if entry_time < act_time:
                log_idx += 1
                continue
            if entry_time >= next_time:
                break
            api_calls.append(entry)
            log_idx += 1

        enriched.append({**action, "api_calls": api_calls})
    return enriched


# --- Verifier system prompt ---
_VERIFIER_SYSTEM_PROMPT = """You are a verifier builder for MiniWeb, a web benchmark platform.

Given a task's instruction, trajectory (with API calls), macro spans, and expected answer,
generate a JSON array of verifier configs — one per macro span.

Each verifier config has this schema:
{
  "macro": "macro_name",
  "span": [start_action_idx, end_action_idx],
  "checks": [
    {
      "type": "grounding|state_query|answer_match|record_exists|record_absent|count_equals|field_equals|action_performed",
      "description": "Human-readable description of what this checks",
      ... type-specific fields ...
    }
  ]
}

Check type schemas:

1. grounding — verify the agent visited required pages
   {"type": "grounding", "required_urls": ["/sites/banking/transactions"], "description": "..."}

2. state_query — query /_admin/data/<site>/<collection> and assert a condition
   {"type": "state_query", "endpoint": "/_admin/data/banking/transactions", "params": {"user_id": "1"}, "check": "count_gt|count_equals|count_gte|equals|contains|not_empty", "expected": ..., "field": "optional_field_name", "description": "..."}

3. answer_match — compare the agent's answer against expected
   {"type": "answer_match", "expected": "42", "match_type": "string|number|boolean|date", "alternatives": [], "description": "..."}

4. record_exists — verify a record matching params exists
   {"type": "record_exists", "endpoint": "/_admin/data/<site>/<collection>", "params": {...}, "description": "..."}

5. record_absent — verify no record matches
   {"type": "record_absent", "endpoint": "/_admin/data/<site>/<collection>", "params": {...}, "description": "..."}

6. count_equals — verify exact count
   {"type": "count_equals", "endpoint": "...", "params": {...}, "expected": 5, "description": "..."}

7. field_equals — verify a field on a record
   {"type": "field_equals", "endpoint": "...", "params": {...}, "field": "status", "expected": "completed", "description": "..."}

8. action_performed — verify the trajectory contains a specific action
   {"type": "action_performed", "action": "click|type|select|navigate|tab_switch", "target_contains": "optional text in target", "description": "..."}

Rules:
- Generate one verifier per macro span
- Always include at least one grounding check (from URLs visited in the trajectory)
- For macros that change state (create, edit, delete, pay, submit), include state_query or record_exists checks
- For macros that extract/compute information, include answer_match if this macro produces the final answer
- Use the API calls in the trajectory to understand what endpoints were hit and what data exists
- The /_admin/data/<site>/<collection> endpoint returns a JSON array of records
- Available collections per site are listed in admin_schemas
- Output ONLY the JSON array, no explanation or markdown

IMPORTANT — Fix mode:
If the input contains "mode": "fix" with "existing_configs" and "feedback", do NOT regenerate from scratch.
Instead, take the existing_configs as your starting point and apply ONLY the changes described in the feedback.
Keep everything that isn't mentioned in the feedback unchanged. Output the full corrected JSON array."""


def _call_openai_verifiers(context):
    """Generate verifier configs via the shared LLM helper."""
    from app.llm import call_llm

    trimmed_ctx = _trim_context(context)
    prompt = json.dumps(trimmed_ctx)

    text = call_llm(prompt, system=_VERIFIER_SYSTEM_PROMPT, max_tokens=4000, temperature=0.2)
    if not text:
        return None

    try:
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        if "```" in text:
            text = text.split("```")[0]
        return json.loads(text.strip())
    except Exception:
        import traceback
        traceback.print_exc()
        return None


def _trim_context(context):
    """Trim trajectory and schemas to fit within token limits."""
    trimmed = dict(context)

    # Limit trajectory to actions + their api_calls (drop observations/html)
    if "trajectory" in trimmed:
        actions = []
        for entry in trimmed["trajectory"]:
            slim = {
                "action_idx": entry.get("action_idx", 0),
                "action": entry.get("action", ""),
                "target": entry.get("target", ""),
                "url": entry.get("url", ""),
            }
            # Include key details per action type
            for key in ("text", "value", "option_text", "key", "checked",
                        "from_tab", "to_tab"):
                if key in entry and entry[key]:
                    slim[key] = entry[key]
            # Include API calls (trimmed)
            api_calls = entry.get("api_calls", [])
            slim_calls = []
            for call in api_calls[:5]:  # max 5 per action
                sc = {
                    "method": call.get("method"),
                    "path": call.get("path"),
                    "status": call.get("status"),
                }
                if "body" in call:
                    sc["body"] = call["body"]
                if "response" in call:
                    resp = call["response"]
                    # Truncate large responses
                    if isinstance(resp, list) and len(resp) > 3:
                        sc["response"] = resp[:3]
                        sc["response_truncated"] = len(resp)
                    else:
                        sc["response"] = resp
                elif "response_preview" in call:
                    sc["response_preview"] = call["response_preview"][:100]
                slim_calls.append(sc)
            slim["api_calls"] = slim_calls
            actions.append(slim)
        trimmed["trajectory"] = actions

    # Limit schema to collection names only (not full records)
    if "admin_schemas" in trimmed:
        for site in trimmed["admin_schemas"]:
            schema = trimmed["admin_schemas"][site]
            if isinstance(schema, list):
                trimmed["admin_schemas"][site] = schema[:20]

    return trimmed


# --- Website Review ---

# Override on deployments (e.g. Railway) to point at a mounted volume so
# runtime-submitted reviews survive redeploys; defaults to the repo copy.
_REVIEWS_DIR = Path(
    os.environ.get("MINIWEB_REVIEWS_DIR", str(SITES_DIR.parent / "data" / "reviews"))
).resolve()


def _review_file(site_id):
    # site_id comes from the URL — sanitize to a plain name to keep paths safe
    safe = "".join(c for c in site_id if c.isalnum() or c in "-_")
    return _REVIEWS_DIR / f"{safe}.json"


def _load_reviews(site_id):
    f = _review_file(site_id)
    if f.exists():
        try:
            return json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return []


@annotation_bp.route("/api/review/<site_id>", methods=["POST"])
def api_submit_review(site_id):
    """Submit free-form feedback for a site. Stored in data/reviews/<site>.json."""
    data = request.get_json(silent=True) or {}
    feedback = (data.get("feedback") or "").strip()
    if not feedback:
        return jsonify({"error": "feedback required"}), 400
    reviews = _load_reviews(site_id)
    reviews.append({
        "annotator": data.get("annotator", "anonymous"),
        "feedback": feedback,
        "timestamp": datetime.now().isoformat(),
    })
    _REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    _review_file(site_id).write_text(json.dumps(reviews, indent=1))
    return jsonify({"status": "saved", "count": len(reviews)})


@annotation_bp.route("/api/review_status")
def api_review_status():
    """List sites with their review counts."""
    sites = _load_sites()
    result = []
    for s in sites:
        result.append({
            "id": s["id"],
            "name": s.get("name", s["id"]),
            "review_count": len(_load_reviews(s["id"])),
        })
    return jsonify(result)


@annotation_bp.route("/api/reviews/<site_id>")
def api_get_reviews(site_id):
    """Get all reviews for a site."""
    return jsonify(_load_reviews(site_id))


    # Dashboard removed — use index page and verify page instead
