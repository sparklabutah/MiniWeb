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
from datetime import datetime
from pathlib import Path

from flask import Blueprint, jsonify, render_template, request

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SITES_DIR = PROJECT_ROOT / "sites"
TASKS_DIR = PROJECT_ROOT / "annotation" / "tasks"
REVIEWS_DIR = PROJECT_ROOT / "annotation" / "reviews"
REPORTED_DIR = PROJECT_ROOT / "annotation" / "reported"

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
    "navigate_by_dropdown": {"verb": "navigate", "modality": "dropdown", "description": "Navigate to a section by selecting from a dropdown menu", "example": "Select 'Accounts' from the navigation dropdown"},
    "navigate_by_semantic": {"verb": "navigate", "modality": "semantic", "description": "Navigate to a page described in natural language", "example": "Find and go to the page that shows your recent orders"},
    "navigate_by_ranking": {"verb": "navigate", "modality": "ranking", "description": "Navigate to an item based on its rank position", "example": "Click on the 3rd most popular article"},
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
    "search_by_image": {"verb": "search", "modality": "image", "description": "Search using an image as input", "example": "Upload a photo to find similar items"},
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
    "compute_by_checkbox": {"verb": "compute", "modality": "checkbox", "description": "Compute a value from checked selections", "example": "Check items to compare and compute the average price"},
    "compute_from_table": {"verb": "compute", "modality": "table", "description": "Compute from tabular data", "example": "Sum the values in the 'Amount' column"},
    "compute_by_route": {"verb": "compute", "modality": "route", "description": "Compute from data on a specific route", "example": "Go to analytics page and calculate year-over-year growth"},
    # Compare
    "compare_by_dropdown": {"verb": "compare", "modality": "dropdown", "description": "Compare items selected from dropdowns", "example": "Compare iPhone 15 vs Samsung S24 specs side by side"},
    "compare_from_table": {"verb": "compare", "modality": "table", "description": "Compare items listed in a table", "example": "Which of the top 3 hotels has the best price-to-rating ratio?"},
    "compare_by_slider": {"verb": "compare", "modality": "slider", "description": "Compare values at different slider positions", "example": "Compare monthly payments at 4% vs 5% interest rate"},
    "compare_by_date_range": {"verb": "compare", "modality": "date range", "description": "Compare data across different time periods", "example": "Compare Q1 vs Q2 sales figures"},
    "compare_by_route": {"verb": "compare", "modality": "route", "description": "Compare items on different pages", "example": "Compare two product detail pages"},
    # Verify
    "verify_by_slider": {"verb": "verify", "modality": "slider", "description": "Verify a value matches expected range", "example": "Verify the portfolio return shown matches the 12-month chart"},
    "verify_by_dropdown": {"verb": "verify", "modality": "dropdown", "description": "Verify data after selecting an option", "example": "Select 'Completed' filter and verify all shown orders are completed"},
    "verify_by_toggle": {"verb": "verify", "modality": "toggle", "description": "Verify state after toggling a setting", "example": "Toggle 2FA on and verify the security status shows 'Enhanced'"},
    "verify_from_free_text": {"verb": "verify", "modality": "free text", "description": "Verify a claim by reading page content", "example": "Verify that the article mentions the source study by name"},
    "verify_identity_by_code": {"verb": "verify identity", "modality": "code", "description": "Verify identity using a code or OTP", "example": "Enter the verification code sent to your email"},
    # Create / Submit
    "create_from_free_text": {"verb": "create", "modality": "free text", "description": "Create new content by typing free-form text", "example": "Write a new blog post with title and body"},
    "create_by_dropdown": {"verb": "create", "modality": "dropdown", "description": "Create something by selecting from dropdowns", "example": "Create a new playlist by selecting genre and mood"},
    "create_by_toggle": {"verb": "create", "modality": "toggle", "description": "Create by toggling options", "example": "Create a new alert by toggling notification preferences"},
    "create_by_checkbox": {"verb": "create", "modality": "checkbox", "description": "Create by checking options", "example": "Create a workout plan by checking desired exercises"},
    "create_by_drag": {"verb": "create", "modality": "drag", "description": "Create by dragging elements", "example": "Drag blocks onto the canvas to build a design"},
    "create_by_radio": {"verb": "create", "modality": "radio", "description": "Create by selecting radio options", "example": "Create a new poll by selecting question type"},
    "create_by_code": {"verb": "create", "modality": "code", "description": "Create by writing code", "example": "Write a Python function in the code editor"},
    "create_by_image": {"verb": "create", "modality": "image", "description": "Create from an uploaded image", "example": "Upload a logo to create a new brand asset"},
    "create_from_table": {"verb": "create", "modality": "table", "description": "Create by adding a row to a table", "example": "Add a new contact by filling in the table row"},
    "create_by_timestamp": {"verb": "create", "modality": "timestamp", "description": "Create a clip or bookmark at a specific timestamp", "example": "Create a clip starting at 1:30 in the stream"},
    "submit_by_query": {"verb": "submit", "modality": "query", "description": "Submit data via a search or query interface", "example": "Submit your answer in the search box"},
    "submit_by_form": {"verb": "submit", "modality": "form", "description": "Submit a filled-out form", "example": "Fill in the contact form and click Submit"},
    "submit_by_route": {"verb": "submit", "modality": "route", "description": "Submit by navigating to a submission URL", "example": "Navigate to /submit to finalize your entry"},
    "submit_by_dropdown": {"verb": "submit", "modality": "dropdown", "description": "Submit by selecting and confirming from dropdown", "example": "Select the recipient and submit the transfer"},
    "submit_by_radio": {"verb": "submit", "modality": "radio", "description": "Submit by selecting a radio option and confirming", "example": "Select the answer choice and submit the quiz"},
    "submit_by_ranking": {"verb": "submit", "modality": "ranking", "description": "Submit a ranking of items", "example": "Rank the candidates and submit your vote"},
    "submit_by_slider": {"verb": "submit", "modality": "slider", "description": "Submit after setting slider values", "example": "Set the bid amount with the slider and submit"},
    "submit_by_date_range": {"verb": "submit", "modality": "date range", "description": "Submit with a date range selection", "example": "Select vacation dates and submit the request"},
    "submit_by_image": {"verb": "submit", "modality": "image", "description": "Submit an image for processing", "example": "Upload a document photo for OCR processing"},
    "submit_from_table": {"verb": "submit", "modality": "table", "description": "Submit data entered in a table", "example": "Fill in the spreadsheet cells and submit"},
    # Edit
    "edit_by_form": {"verb": "edit", "modality": "form", "description": "Edit existing data through a form", "example": "Edit your profile name and bio in the settings form"},
    "edit_by_query": {"verb": "edit", "modality": "query", "description": "Edit by entering new values", "example": "Change the document title by typing a new name"},
    "edit_by_dropdown": {"verb": "edit", "modality": "dropdown", "description": "Edit by selecting a new value from dropdown", "example": "Change the issue priority from 'Low' to 'High'"},
    "edit_by_toggle": {"verb": "edit", "modality": "toggle", "description": "Edit a setting by toggling it", "example": "Toggle 'Public' to make the repository private"},
    "edit_by_slider": {"verb": "edit", "modality": "slider", "description": "Edit a value using a slider", "example": "Adjust the volume slider to 75%"},
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
    "select_by_route": {"verb": "select", "modality": "route", "description": "Select by navigating to a route", "example": "Click on the album cover to select it for playback"},
    "configure_by_dropdown": {"verb": "configure", "modality": "dropdown", "description": "Configure a setting using a dropdown", "example": "Set the language to 'Spanish' from the dropdown"},
    "configure_by_slider": {"verb": "configure", "modality": "slider", "description": "Configure a setting with a slider", "example": "Set the password length to 16 characters"},
    "configure_by_toggle": {"verb": "configure", "modality": "toggle", "description": "Configure by toggling a switch", "example": "Enable two-factor authentication"},
    "configure_by_radio": {"verb": "configure", "modality": "radio", "description": "Configure by selecting a radio option", "example": "Set notifications to 'Email only'"},
    "configure_by_query": {"verb": "configure", "modality": "query", "description": "Configure by entering a value", "example": "Set the custom domain to 'mysite.com'"},
    "configure_by_chip": {"verb": "configure", "modality": "chip", "description": "Configure by selecting chips", "example": "Select interest chips: 'Tech', 'Sports', 'Music'"},
    "configure_by_checkbox": {"verb": "configure", "modality": "checkbox", "description": "Configure by checking boxes", "example": "Check the notification types you want to receive"},
    "configure_by_date_range": {"verb": "configure", "modality": "date range", "description": "Configure a date-based setting", "example": "Set the recurring event to every Monday"},
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
    "upload_from_table": {"verb": "upload", "modality": "table", "description": "Upload files listed in a table", "example": "Select files from the table and click Upload"},
    "copy_by_route": {"verb": "copy", "modality": "route", "description": "Copy content by clicking a copy button", "example": "Click the copy icon next to the API key"},
    # Social
    "follow_by_toggle": {"verb": "follow", "modality": "toggle", "description": "Follow/unfollow by clicking a toggle button", "example": "Click 'Follow' to start following the author"},
    "follow_by_dropdown": {"verb": "follow", "modality": "dropdown", "description": "Follow by selecting from dropdown", "example": "Select a user from the dropdown and follow them"},
    "follow_by_route": {"verb": "follow", "modality": "route", "description": "Follow by navigating to follow URL", "example": "Go to the author's page and click Follow"},
    "subscribe_by_toggle": {"verb": "subscribe", "modality": "toggle", "description": "Subscribe/unsubscribe with a toggle", "example": "Toggle the Subscribe button for the newsletter"},
    "save_by_toggle": {"verb": "save", "modality": "toggle", "description": "Save/unsave an item with a toggle", "example": "Click the bookmark icon to save the article"},
    "save_by_query": {"verb": "save", "modality": "query", "description": "Save by entering and confirming", "example": "Name your saved search and click Save"},
    "react_by_toggle": {"verb": "react", "modality": "toggle", "description": "React to content (like, upvote, etc.)", "example": "Click the heart icon to like the post"},
    "react_by_chip": {"verb": "react", "modality": "chip", "description": "React by selecting an emoji chip", "example": "Click the thumbs-up emoji reaction"},
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
    "message_by_query": {"verb": "message", "modality": "query", "description": "Send a message by query", "example": "Search for a user and send them a direct message"},
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
    "book_by_query": {"verb": "book", "modality": "query", "description": "Book by entering details", "example": "Enter destination and dates to book the flight"},
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
    "route_by_date_range": {"verb": "route", "modality": "date range", "description": "Plan a route for a specific time", "example": "Set departure time to 8:00 AM for transit directions"},
    # Translate
    "translate_by_query": {"verb": "translate", "modality": "query", "description": "Translate text by entering it", "example": "Type 'Hello, how are you?' and translate to Spanish"},
    "translate_by_dropdown": {"verb": "translate", "modality": "dropdown", "description": "Translate by selecting source/target language", "example": "Select English → French from the language dropdowns"},
    "translate_by_slider": {"verb": "translate", "modality": "slider", "description": "Adjust translation settings with slider", "example": "Set the formality slider to 'Formal'"},
    "translate_by_image": {"verb": "translate", "modality": "image", "description": "Translate text in an image", "example": "Upload a photo of a sign to translate it"},
    # Sign
    "sign_by_query": {"verb": "sign", "modality": "query", "description": "Sign a document by entering signature", "example": "Type your full name to e-sign the document"},
    "sign_by_signature": {"verb": "sign", "modality": "signature", "description": "Sign by drawing a signature", "example": "Draw your signature in the signature box"},
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tasks_dir():
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    return TASKS_DIR


def _load_all_tasks():
    tasks = []
    for d in sorted(_tasks_dir().iterdir()):
        if d.is_dir() and (d / "task.json").exists():
            try:
                tasks.append(json.loads((d / "task.json").read_text()))
            except (json.JSONDecodeError, OSError):
                pass
        elif d.is_file() and d.suffix == ".json":
            try:
                tasks.append(json.loads(d.read_text()))
            except (json.JSONDecodeError, OSError):
                pass
    return tasks


def _save_task(task):
    """Save task with heavy data (HTML, screenshots) in a subdirectory."""
    task_id = task.get("task_id", f"task_{uuid.uuid4().hex[:8]}")
    task["task_id"] = task_id
    task["created_at"] = datetime.now().isoformat()

    task_dir = _tasks_dir() / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    html_dir = task_dir / "html"
    html_dir.mkdir(exist_ok=True)

    trajectory = task.pop("trajectory", [])
    clean_trajectory = []
    step_num = 0

    for entry in trajectory:
        if entry.get("type") == "action":
            step_num += 1
            clean_trajectory.append({
                "type": "action",
                "step": step_num,
                "url": entry.get("url", ""),
                "timestamp": entry.get("timestamp", ""),
            })
        elif entry.get("type") == "observation":
            raw_html = entry.get("raw_html", "")
            if raw_html:
                (html_dir / f"step_{step_num:03d}.html").write_text(raw_html)
            clean_trajectory.append({
                "type": "observation",
                "step": step_num,
                "title": entry.get("title", ""),
                "url": entry.get("url", ""),
                "ax_tree": entry.get("ax_tree", ""),
                "has_html": bool(raw_html),
                "has_screenshot": entry.get("screenshot", "") not in ("", "[screenshot:pending]", "[screenshot:error]"),
                "timestamp": entry.get("timestamp", ""),
            })

    (task_dir / "trajectory.json").write_text(json.dumps(clean_trajectory, indent=2))
    task["trajectory_steps"] = step_num
    (task_dir / "task.json").write_text(json.dumps(task, indent=2))
    return task_id


def _load_sites():
    sites = []
    for site_json in sorted(SITES_DIR.glob("*/site.json")):
        if site_json.parent.name.startswith("_"):
            continue
        if not (site_json.parent / "tasks.json").exists():
            continue
        if (site_json.parent / "routes.py").stat().st_size < 500:
            continue
        meta = json.loads(site_json.read_text())
        meta["url"] = f"/sites/{meta['id']}/"
        # Count human-reviewed tasks
        meta["annotated_count"] = 0
        for d in _tasks_dir().iterdir():
            if d.is_dir() and d.name.startswith(meta["id"]) and (d / "task.json").exists():
                meta["annotated_count"] += 1
        # Count reviews
        review_file = REVIEWS_DIR / f"{meta['id']}.json"
        meta["review_count"] = 0
        if review_file.exists():
            try:
                meta["review_count"] = len(json.loads(review_file.read_text()))
            except (json.JSONDecodeError, OSError):
                pass
        sites.append(meta)
    return sites


def _load_macros():
    macros = set()
    for tasks_file in SITES_DIR.glob("*/tasks.json"):
        try:
            for t in json.loads(tasks_file.read_text()):
                for m in t.get("macros", []):
                    macros.add(m)
        except (json.JSONDecodeError, OSError):
            pass
    return sorted(macros)


def _load_site_macros(site_id):
    """Load macros available for a specific site."""
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


def _get_macro_coverage():
    """Macro coverage from human-reviewed tasks only."""
    tasks = _load_all_tasks()
    coverage = {}
    for t in tasks:
        for m in t.get("macros", []):
            coverage.setdefault(m, set()).add(t.get("site", "unknown"))
    return {m: len(sites) for m, sites in coverage.items()}


def _get_cell_counts():
    """Count existing tasks per (num_sites, num_macros) cell."""
    tasks = _load_all_tasks()
    cells = {}
    for t in tasks:
        n_sites = len(t.get("sites", [t.get("site", "")]))
        n_macros = len(t.get("macros", []))
        # Clamp to grid
        n_sites = min(max(n_sites, 1), 3)
        n_macros = min(max(n_macros, 1), 4)
        key = (n_sites, n_macros)
        cells[key] = cells.get(key, 0) + 1
    return cells


def _generate_prompt(sites, coverage):
    """Sample N sites × M macros for the annotator.

    Balanced across two axes:
      - Axis 1: number of sites N ∈ {1, 2, 3}
      - Axis 2: number of macros M ∈ {1, 2, 3, 4}
    """
    rng = random.Random()
    site_pool = list(sites)
    if not site_pool:
        return None

    # 1. Pick cell (N, M) — prefer under-filled cells
    cell_counts = _get_cell_counts()
    cells = [(n, m) for n in [1, 2, 3] for m in [1, 2, 3, 4]]
    cell_weights = [1.0 / (cell_counts.get((n, m), 0) + 1) for n, m in cells]
    total = sum(cell_weights)
    cell_weights = [w / total for w in cell_weights]
    n_sites, n_macros = rng.choices(cells, weights=cell_weights, k=1)[0]

    # 2. Pick N sites — prefer sites with fewer annotated tasks
    site_weights = [1.0 / (s.get("annotated_count", 0) + 1) for s in site_pool]
    total = sum(site_weights)
    site_weights = [w / total for w in site_weights]
    sampled_sites = []
    remaining_sites = list(zip(site_pool, site_weights))
    for _ in range(min(n_sites, len(remaining_sites))):
        ss, ws = zip(*remaining_sites)
        total = sum(ws)
        ws = [w / total for w in ws]
        pick = rng.choices(ss, weights=ws, k=1)[0]
        sampled_sites.append(pick)
        remaining_sites = [(s, w) for s, w in remaining_sites if s["id"] != pick["id"]]

    # 3. Pick M macros from the union of selected sites' macro pools
    macro_pool = set()
    for s in sampled_sites:
        macro_pool.update(_load_site_macros(s["id"]))
    if not macro_pool:
        macro_pool = set(_load_macros())
    macro_pool = sorted(macro_pool)
    if not macro_pool:
        return None

    # Weight toward under-covered macros
    macro_weights = [1.0 / (coverage.get(m, 0) + 1) for m in macro_pool]
    total = sum(macro_weights)
    macro_weights = [w / total for w in macro_weights]

    sampled_macros = []
    remaining_macros = list(zip(macro_pool, macro_weights))
    for _ in range(min(n_macros, len(remaining_macros))):
        if not remaining_macros:
            break
        ms, ws = zip(*remaining_macros)
        total = sum(ws)
        ws = [w / total for w in ws]
        pick = rng.choices(ms, weights=ws, k=1)[0]
        sampled_macros.append(pick)
        remaining_macros = [(m, w) for m, w in remaining_macros if m != pick]

    return {
        "sites": [{"id": s["id"], "name": s.get("name", s["id"])} for s in sampled_sites],
        "macros": sampled_macros,
        "num_sites": len(sampled_sites),
        "num_macros": len(sampled_macros),
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@annotation_bp.route("/")
def index():
    sites = _load_sites()
    tasks = _load_all_tasks()
    macros = _load_macros()
    coverage = _get_macro_coverage()
    cell_counts = _get_cell_counts()
    return render_template("index.html",
                           sites=sites, task_count=len(tasks),
                           macros=macros, coverage=coverage,
                           cell_counts=cell_counts)


@annotation_bp.route("/task")
def annotate():
    """Single annotation interface — system samples sites × macros."""
    sites = _load_sites()
    coverage = _get_macro_coverage()
    prompt = _generate_prompt(sites, coverage)

    return render_template("annotate.html",
                           sites=sites,
                           prompt=prompt,
                           macro_descriptions=_MACRO_DESCRIPTIONS)


@annotation_bp.route("/review")
def review():
    """Website review mode — browse each site, leave feedback."""
    sites = _load_sites()
    return render_template("review.html", sites=sites)


# --- API ---

@annotation_bp.route("/api/tasks", methods=["GET"])
def api_list_tasks():
    return jsonify(_load_all_tasks())


@annotation_bp.route("/api/tasks", methods=["POST"])
def api_create_task():
    data = request.get_json(silent=True) or {}
    if not data.get("instruction") or not data.get("sites"):
        return jsonify({"error": "instruction and sites required"}), 400

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
        "eval": data.get("eval", []),
        "eval_logic": data.get("eval_logic", "all"),
        "trajectory": data.get("trajectory", []),
        "annotator": data.get("annotator", "anonymous"),
    }
    task_id = _save_task(task)
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
    """Get a new random prompt (sites + macros)."""
    sites = _load_sites()
    coverage = _get_macro_coverage()
    prompt = _generate_prompt(sites, coverage)
    return jsonify(prompt)


@annotation_bp.route("/api/reset_tasks", methods=["POST"])
def api_reset_tasks():
    """Delete all human-reviewed tasks."""
    import shutil
    count = 0
    tasks_dir = _tasks_dir()
    for entry in list(tasks_dir.iterdir()):
        if entry.is_dir():
            shutil.rmtree(entry)
            count += 1
        elif entry.is_file() and entry.suffix == ".json":
            entry.unlink()
            count += 1
    return jsonify({"message": f"Deleted {count} tasks.", "deleted": count})


@annotation_bp.route("/api/report", methods=["POST"])
def api_report():
    """Save a skip report."""
    data = request.get_json(silent=True) or {}
    sites = data.get("sites", [])
    site_key = "_".join(sites) if sites else "unknown"
    REPORTED_DIR.mkdir(parents=True, exist_ok=True)
    report_file = REPORTED_DIR / f"{site_key}.json"
    existing = []
    if report_file.exists():
        try:
            existing = json.loads(report_file.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    existing.append({
        "sites": sites,
        "macros": data.get("macros", []),
        "reason": data.get("reason"),
        "details": data.get("details"),
        "annotator": data.get("annotator", "anonymous"),
        "timestamp": datetime.now().isoformat(),
    })
    report_file.write_text(json.dumps(existing, indent=2))
    return jsonify({"status": "reported", "count": len(existing)})


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


@annotation_bp.route("/api/validate_eval", methods=["POST"])
def api_validate_eval():
    """Run eval config live."""
    from flask import current_app
    data = request.get_json(silent=True) or {}
    eval_configs = data.get("eval", [])
    agent_answer = data.get("agent_answer", "")
    server_url = request.host_url.rstrip("/")

    client = current_app.test_client()
    for key, val in request.cookies.items():
        client.set_cookie(key, val)

    from annotation.evaluators import run_task_eval
    passed, results = run_task_eval(
        eval_configs,
        eval_logic=data.get("eval_logic", "all"),
        agent_answer=agent_answer,
        server_url=server_url,
        navigation_trace=data.get("navigation_trace", []),
        flask_client=client,
    )
    return jsonify({
        "passed": passed,
        "results": [{"evaluator": r[0], "passed": r[1], "detail": r[2]} for r in results],
    })


# --- Website Review ---

@annotation_bp.route("/api/review/<site_id>", methods=["POST"])
def api_submit_review(site_id):
    """Submit free-form feedback for a site."""
    data = request.get_json(silent=True) or {}
    REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    review_file = REVIEWS_DIR / f"{site_id}.json"
    existing = []
    if review_file.exists():
        try:
            existing = json.loads(review_file.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    existing.append({
        "annotator": data.get("annotator", "anonymous"),
        "feedback": data.get("feedback", ""),
        "timestamp": datetime.now().isoformat(),
    })
    review_file.write_text(json.dumps(existing, indent=2))
    return jsonify({"status": "saved", "count": len(existing)})


@annotation_bp.route("/api/review_status")
def api_review_status():
    """List sites with their review counts."""
    sites = _load_sites()
    result = []
    for s in sites:
        review_file = REVIEWS_DIR / f"{s['id']}.json"
        count = 0
        if review_file.exists():
            try:
                count = len(json.loads(review_file.read_text()))
            except (json.JSONDecodeError, OSError):
                pass
        result.append({"id": s["id"], "name": s.get("name", s["id"]), "review_count": count})
    return jsonify(result)


@annotation_bp.route("/api/reviews/<site_id>")
def api_get_reviews(site_id):
    """Get all reviews for a site."""
    review_file = REVIEWS_DIR / f"{site_id}.json"
    if not review_file.exists():
        return jsonify([])
    try:
        return jsonify(json.loads(review_file.read_text()))
    except (json.JSONDecodeError, OSError):
        return jsonify([])


@annotation_bp.route("/dashboard")
def dashboard():
    tasks = _load_all_tasks()
    macros = _load_macros()
    coverage = _get_macro_coverage()

    site_counts = {}
    for t in tasks:
        s = t.get("site", "unknown")
        site_counts[s] = site_counts.get(s, 0) + 1

    cell_counts = _get_cell_counts()

    return render_template("dashboard.html",
                           tasks=tasks, macros=macros, coverage=coverage,
                           site_counts=site_counts, cell_counts=cell_counts)
