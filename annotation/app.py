"""MiniWeb Task Annotation Interface.

Two modes:
  1. Review Sites — browse each site, leave free-form feedback
  2. Annotate Tasks — system samples N sites × M macros, annotator designs task

The annotation blueprint is registered in the main MiniWeb app.
  Access at http://localhost:8080/annotate/
"""

import json
import random
import uuid
import pickle
from datetime import datetime
from pathlib import Path

from flask import Blueprint, jsonify, render_template, request, session

from annotation.macro_locations import MACRO_LOCATIONS

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SITES_DIR = PROJECT_ROOT / "sites"

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
    "navigate_by_link": {"verb": "navigate", "modality": "link", "description": "Navigate by clicking an inline hyperlink", "example": "Click the author's name link to visit their profile"},
    "navigate_by_sidebar": {"verb": "navigate", "modality": "sidebar", "description": "Navigate using a sidebar menu or tree", "example": "Click 'Getting Started' in the docs sidebar to open that section"},
    "navigate_console": {"verb": "navigate", "modality": "console", "description": "Navigate to an admin or management console", "example": "Go to the admin console to manage submissions"},
    "browse_by_letter": {"verb": "browse", "modality": "letter", "description": "Browse items alphabetically by clicking a letter", "example": "Click 'M' to browse all words starting with M"},
    "login_by_form": {"verb": "login", "modality": "form", "description": "Log in by entering credentials in a login form", "example": "Enter username and password then click Sign In"},
    # Search
    "search_by_query": {"verb": "search", "modality": "query", "description": "Search using a text query in a search box", "example": "Type 'machine learning' in the search bar and press Enter"},
    "search_by_semantic": {"verb": "search", "modality": "semantic", "description": "Search using natural language or meaning-based query", "example": "Search for 'papers about image recognition' to find relevant results"},
    "search_by_checkbox": {"verb": "search", "modality": "checkbox", "description": "Search by selecting checkboxes to define criteria", "example": "Check 'Python' and 'JavaScript' to find repos using those languages"},
    "search_by_route": {"verb": "search", "modality": "route", "description": "Search by navigating to a search-result URL pattern", "example": "Go to /search?q=einstein to see results for einstein"},
    "search_by_code": {"verb": "search", "modality": "code", "description": "Search using a code, ID, or reference number", "example": "Enter permit number 'LP-2024-001' to find the permit"},
    "search_by_dropdown": {"verb": "search", "modality": "dropdown", "description": "Search by selecting a category from a dropdown", "example": "Select 'Inbox' from the folder dropdown to search within inbox"},
    "search_by_proximity": {"verb": "search", "modality": "proximity", "description": "Search for items near a location", "example": "Search for restaurants within 5 miles of downtown"},
    "search_by_image": {"verb": "search", "modality": "image", "description": "Search using an image as input", "example": "Upload a photo to find similar items"},
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
    "filter_by_tag": {"verb": "filter", "modality": "tag", "description": "Filter by selecting tags or labels", "example": "Click the 'REST API' tag to show only REST endpoints"},
    "filter_by_starred": {"verb": "filter", "modality": "starred", "description": "Filter to show only starred or favorited items", "example": "Toggle 'Starred' to show only your starred documents"},
    "filter_by_folder": {"verb": "filter", "modality": "folder", "description": "Filter items by their folder location", "example": "Click the 'Reports' folder to show only files in that folder"},
    "filter_by_department": {"verb": "filter", "modality": "department", "description": "Filter by department or organizational unit", "example": "Select 'Computer Science' to show only CS courses"},
    "filter_by_method": {"verb": "filter", "modality": "method", "description": "Filter by HTTP method or operation type", "example": "Select 'POST' to show only POST endpoints"},
    "filter_by_owner": {"verb": "filter", "modality": "owner", "description": "Filter items by their owner or creator", "example": "Filter to show only documents you own"},
    "filter_by_pos": {"verb": "filter", "modality": "part of speech", "description": "Filter by part of speech (noun, verb, etc.)", "example": "Select 'Noun' to show only noun definitions"},
    "filter_by_range": {"verb": "filter", "modality": "range", "description": "Filter by a numeric range", "example": "Set age range to 25-35 to filter profiles"},
    "filter_by_score_range": {"verb": "filter", "modality": "score range", "description": "Filter by a score or rating range", "example": "Filter to show papers with review scores between 7 and 10"},
    "filter_by_trashed": {"verb": "filter", "modality": "trashed", "description": "Filter to show items in the trash", "example": "Open the Trash folder to see deleted files"},
    # Sort
    "sort_by_ranking": {"verb": "sort", "modality": "ranking", "description": "Sort items by a ranking criterion", "example": "Click 'Price: Low to High' to sort by ascending price"},
    "sort_by_date_range": {"verb": "sort", "modality": "date range", "description": "Sort items by date", "example": "Sort by 'Newest first' to see most recent items"},
    "sort_by_dropdown": {"verb": "sort", "modality": "dropdown", "description": "Sort by selecting an option from a dropdown", "example": "Select 'Most Popular' from the sort dropdown"},
    "sort_by_slider": {"verb": "sort", "modality": "slider", "description": "Sort by adjusting a slider value", "example": "Adjust the relevance slider to re-rank results"},
    "sort_by_toggle": {"verb": "sort", "modality": "toggle", "description": "Toggle sort direction (ascending/descending)", "example": "Click the column header to toggle ascending/descending"},
    "sort_by_extremum": {"verb": "sort", "modality": "extremum", "description": "Sort to find the min/max value", "example": "Sort by price descending to find the most expensive item"},
    "sort_by_title": {"verb": "sort", "modality": "title", "description": "Sort items alphabetically by title or name", "example": "Click 'Name' column header to sort files A-Z"},
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
    "extract_by_api": {"verb": "extract", "modality": "API", "description": "Extract data by calling an API endpoint", "example": "Call the /api/stats endpoint and report the total count"},
    "extract_by_field": {"verb": "extract", "modality": "field", "description": "Extract a specific field value from a record", "example": "What is the user's email address shown on their profile?"},
    "extract_from_changelog": {"verb": "extract", "modality": "changelog", "description": "Extract information from a changelog or version history", "example": "What was changed in version 2.3.0?"},
    "extract_from_config": {"verb": "extract", "modality": "config", "description": "Extract a value from settings or configuration", "example": "What is the current grading scale in the course settings?"},
    "extract_from_dashboard": {"verb": "extract", "modality": "dashboard", "description": "Extract a metric or value from a dashboard", "example": "What is the total number of API calls shown on the dashboard?"},
    "extract_from_list": {"verb": "extract", "modality": "list", "description": "Extract information from a list of items", "example": "How many submissions are in the pending review list?"},
    "extract_from_page": {"verb": "extract", "modality": "page", "description": "Extract information from a specific page", "example": "Go to the about page and report the company founding year"},
    "extract_from_results": {"verb": "extract", "modality": "results", "description": "Extract information from search or query results", "example": "How many results are returned for the search query?"},
    "extract_from_stats": {"verb": "extract", "modality": "stats", "description": "Extract a value from a statistics or analytics view", "example": "What is the average review score shown in the stats panel?"},
    "extract_word_of_the_day": {"verb": "extract", "modality": "featured", "description": "Extract the featured or highlighted item", "example": "What is today's Word of the Day?"},
    # Compute
    "compute_by_dropdown": {"verb": "compute", "modality": "dropdown", "description": "Compute a value after selecting options", "example": "Select 'USD to EUR' and compute the conversion of $500"},
    "compute_by_extremum": {"verb": "compute", "modality": "extremum", "description": "Compute a min/max across items", "example": "Find the highest-rated restaurant with more than 50 reviews"},
    "compute_by_slider": {"verb": "compute", "modality": "slider", "description": "Compute result by adjusting slider inputs", "example": "Set the loan calculator to $200K, 5%, 30yr and report monthly payment"},
    "compute_by_query": {"verb": "compute", "modality": "query", "description": "Compute an answer from queried data", "example": "Calculate the total cost of items in the cart"},
    "compute_by_checkbox": {"verb": "compute", "modality": "checkbox", "description": "Compute a value from checked selections", "example": "Check items to compare and compute the average price"},
    "compute_from_table": {"verb": "compute", "modality": "table", "description": "Compute from tabular data", "example": "Sum the values in the 'Amount' column"},
    "compute_by_route": {"verb": "compute", "modality": "route", "description": "Compute from data on a specific route", "example": "Go to analytics page and calculate year-over-year growth"},
    "compute_from_api": {"verb": "compute", "modality": "API", "description": "Compute a value from API response data", "example": "Call the stats endpoint and compute the acceptance rate"},
    "compute_from_list": {"verb": "compute", "modality": "list", "description": "Compute a value from a list of items", "example": "Sum the prices of all items in the shopping cart"},
    "compute_from_stats": {"verb": "compute", "modality": "stats", "description": "Compute a derived value from displayed statistics", "example": "Calculate the pass rate from the shown pass/fail counts"},
    "compute_from_submissions": {"verb": "compute", "modality": "submissions", "description": "Compute from student or user submissions", "example": "Calculate the average score across all submitted assignments"},
    "compute_stats": {"verb": "compute", "modality": "aggregate", "description": "Compute aggregate statistics from data", "example": "Calculate the total storage used across all documents"},
    "compute_grade_weighted": {"verb": "compute", "modality": "weighted", "description": "Compute a weighted grade or score", "example": "Calculate the weighted final grade (40% midterm, 60% final)"},
    "compute_grade_letter": {"verb": "compute", "modality": "letter grade", "description": "Convert a numeric score to a letter grade", "example": "What letter grade does a score of 87 correspond to?"},
    "compute_class_average": {"verb": "compute", "modality": "class average", "description": "Compute the average across a class or group", "example": "What is the class average on Assignment 3?"},
    "calculate_by_aggregation": {"verb": "calculate", "modality": "aggregation", "description": "Calculate by aggregating multiple values", "example": "Calculate the average age of all matched profiles"},
    "calculate_by_form": {"verb": "calculate", "modality": "form", "description": "Calculate a result by entering values into a form", "example": "Enter 100 USD and calculate the equivalent in EUR"},
    # Count
    "count_by_api": {"verb": "count", "modality": "API", "description": "Count items using an API endpoint", "example": "How many endpoints are documented in the API reference?"},
    "count_by_route": {"verb": "count", "modality": "route", "description": "Count items visible on a specific page", "example": "How many courses are listed on the department page?"},
    "count_by_section": {"verb": "count", "modality": "section", "description": "Count items within a specific section", "example": "How many methods are in the Authentication section?"},
    "count_by_user": {"verb": "count", "modality": "user", "description": "Count items belonging to a specific user", "example": "How many assignments has student John submitted?"},
    "count_nested_items": {"verb": "count", "modality": "nested", "description": "Count items nested inside a parent item", "example": "How many lessons are in Module 3?"},
    # Compare
    "compare_by_dropdown": {"verb": "compare", "modality": "dropdown", "description": "Compare items selected from dropdowns", "example": "Compare iPhone 15 vs Samsung S24 specs side by side"},
    "compare_from_table": {"verb": "compare", "modality": "table", "description": "Compare items listed in a table", "example": "Which of the top 3 hotels has the best price-to-rating ratio?"},
    "compare_by_slider": {"verb": "compare", "modality": "slider", "description": "Compare values at different slider positions", "example": "Compare monthly payments at 4% vs 5% interest rate"},
    "compare_by_date_range": {"verb": "compare", "modality": "date range", "description": "Compare data across different time periods", "example": "Compare Q1 vs Q2 sales figures"},
    "compare_by_route": {"verb": "compare", "modality": "route", "description": "Compare items on different pages", "example": "Compare two product detail pages"},
    "compare_by_query": {"verb": "compare", "modality": "query", "description": "Compare results for different queries", "example": "Compare the weather forecast for Monday vs Friday"},
    "compare_categories": {"verb": "compare", "modality": "categories", "description": "Compare data across different categories", "example": "Compare average grades between CS and Math departments"},
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
    "create_by_form": {"verb": "create", "modality": "form", "description": "Create new content by filling out a form", "example": "Fill in the profile form with name, bio, and interests"},
    "create_by_query": {"verb": "create", "modality": "query", "description": "Create by entering text into an input", "example": "Enter a URL to create a short link"},
    "create_by_api": {"verb": "create", "modality": "API", "description": "Create a new item via an API call", "example": "Use the API to create a new document"},
    "create_discussion": {"verb": "create", "modality": "discussion", "description": "Create a new discussion thread", "example": "Start a new discussion topic in the course forum"},
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
    "submit_form": {"verb": "submit", "modality": "form", "description": "Submit a general-purpose form", "example": "Fill in the required fields and click Submit"},
    "submit_review": {"verb": "submit", "modality": "review", "description": "Submit a peer review or evaluation", "example": "Write your review comments, assign scores, and submit"},
    "input_by_form": {"verb": "input", "modality": "form", "description": "Enter data into form fields", "example": "Type the conversion value into the input field"},
    "assign_by_form": {"verb": "assign", "modality": "form", "description": "Assign a resource or role via a form", "example": "Select a reviewer from the dropdown and assign them to the paper"},
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
    "edit_by_api": {"verb": "edit", "modality": "API", "description": "Edit data via an API call", "example": "Use the API to rename the document"},
    "update_by_form": {"verb": "update", "modality": "form", "description": "Update existing data through a form", "example": "Update your profile preferences and save changes"},
    # Delete
    "delete_from_table": {"verb": "delete", "modality": "table", "description": "Delete an item from a list or table", "example": "Click the trash icon to delete the 3rd email"},
    "delete_by_form": {"verb": "delete", "modality": "form", "description": "Delete an item via a confirmation form or button", "example": "Click Delete and confirm in the dialog"},
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
    "configure_by_route": {"verb": "configure", "modality": "route", "description": "Configure settings by navigating to a settings page", "example": "Go to Settings > Playback to configure video quality"},
    "toggle_by_api": {"verb": "toggle", "modality": "API", "description": "Toggle a boolean state via an API action", "example": "Toggle the item's active status on or off"},
    "list_by_api": {"verb": "list", "modality": "API", "description": "List items by querying an API endpoint", "example": "Retrieve the list of all API endpoints from the docs"},
    "list_by_route": {"verb": "list", "modality": "route", "description": "List items by navigating to a listing page", "example": "Go to the courses page to see all available courses"},
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
    "save_word": {"verb": "save", "modality": "word", "description": "Save a word to your personal word list", "example": "Click 'Save' to add 'ephemeral' to your vocabulary list"},
    "star_by_toggle": {"verb": "star", "modality": "toggle", "description": "Star or unstar an item", "example": "Click the star icon to mark the document as important"},
    "bookmark_by_toggle": {"verb": "bookmark", "modality": "toggle", "description": "Bookmark or unbookmark a page or item", "example": "Click the bookmark icon to save this API reference page"},
    "add_to_vocab_list": {"verb": "add", "modality": "vocabulary", "description": "Add a word to a vocabulary or study list", "example": "Add 'ubiquitous' to your custom word list"},
    "react_by_toggle": {"verb": "react", "modality": "toggle", "description": "React to content (like, upvote, etc.)", "example": "Click the heart icon to like the post"},
    "react_by_chip": {"verb": "react", "modality": "chip", "description": "React by selecting an emoji chip", "example": "Click the thumbs-up emoji reaction"},
    "react_by_gesture": {"verb": "react", "modality": "gesture", "description": "React with a gesture (swipe, double-tap)", "example": "Swipe right to like the profile"},
    "rate_by_slider": {"verb": "rate", "modality": "slider", "description": "Rate something using a star/slider rating", "example": "Set the review rating to 4 out of 5 stars"},
    "share_by_dropdown": {"verb": "share", "modality": "dropdown", "description": "Share via a method selected from dropdown", "example": "Select 'Copy link' from the share dropdown"},
    "share_by_toggle": {"verb": "share", "modality": "toggle", "description": "Toggle sharing on/off", "example": "Enable link sharing for the document"},
    "share_by_query": {"verb": "share", "modality": "query", "description": "Share by entering a recipient", "example": "Type an email address to share the file"},
    "share_by_route": {"verb": "share", "modality": "route", "description": "Share by navigating to a share page", "example": "Go to the share page and copy the public link"},
    "share_by_form": {"verb": "share", "modality": "form", "description": "Share by filling out a sharing form", "example": "Enter collaborator emails and set permissions to share the document"},
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
    "reply_to_discussion": {"verb": "reply", "modality": "discussion", "description": "Reply to an existing discussion thread", "example": "Write a reply to the student's question in the forum"},
    "rank_by_grade": {"verb": "rank", "modality": "grade", "description": "Rank items by their grade or score", "example": "Rank students by their final exam scores"},
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

def _save_task(task):
    """Save task + trajectory to the shared annotations directory."""
    from annotation.storage import save_task as fs_save, generate_task_id

    task_id = task.get("task_id") or generate_task_id()
    task["task_id"] = task_id
    annotator = task.get("annotator", "anonymous")
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
    """Load supported macros for a site from its doc/README.md Target Macros spec.

    Falls back to MACRO_LOCATIONS, then tasks.json.
    """
    import re as _re

    # Try README spec first (source of truth)
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

    # Fallback to MACRO_LOCATIONS
    if site_id in MACRO_LOCATIONS:
        macros = list(MACRO_LOCATIONS[site_id].keys())
        if macros:
            return sorted(set(macros))

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


def _get_na_macros(site_ids):
    """Get macros marked N/A for these sites (threshold: 2+ reports)."""
    return set()


def _get_macro_coverage():
    """Count how many annotated tasks cover each macro (from file storage)."""
    from annotation.storage import list_tasks
    coverage = {}
    for t in list_tasks():
        for m in t.get("macros", []):
            coverage[m] = coverage.get(m, 0) + 1
    return coverage


def _get_cell_counts():
    """Count existing tasks per (num_sites, num_macros) cell (from file storage)."""
    from annotation.storage import list_tasks
    counts = {}
    for t in list_tasks():
        n_sites = len(t.get("sites", []))
        n_macros = len(t.get("macros", []))
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
    "file_created": ["create_from_free_text", "upload_by_upload"],
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
    """Graph-aware prompt sampler.

    Strategy:
      1. Pick cell (N sites, M macros) — prefer under-filled cells
      2. For N=1: pick a single under-covered site
         For N≥2: pick a seed site, then expand along graph edges to find
                  connected sites (prefer direct edges, then hub-mediated)
      3. Pick M macros — combine site-specific macros with edge-implied macros,
         weighted toward under-covered ones
    """
    rng = random.Random()
    site_pool = list(sites)
    if not site_pool:
        return None
    site_map = {s["id"]: s for s in site_pool}

    # Load graph
    outgoing, incoming = _load_graph_edges()

    # 1. Pick cell — each chain is exactly 1 macro, 1-3 sites
    cell_counts = _get_cell_counts()
    if force_single:
        cells = [(1, 1)]
    else:
        cells = [(n, 1) for n in [1, 2, 3]]
    cell_weights = [1.0 / (cell_counts.get((n, m), 0) + 1) for n, m in cells]
    total = sum(cell_weights)
    cell_weights = [w / total for w in cell_weights]
    n_sites, n_macros = rng.choices(cells, weights=cell_weights, k=1)[0]

    # 2. Pick sites — graph-aware for multi-site tasks
    site_weights = [1.0 / (s.get("annotated_count", 0) + 1) for s in site_pool]

    # Pick seed site (weighted by under-coverage)
    total = sum(site_weights)
    norm_weights = [w / total for w in site_weights]
    seed = rng.choices(site_pool, weights=norm_weights, k=1)[0]
    sampled_sites = [seed]
    sampled_ids = {seed["id"]}
    edge_types_used = []

    if n_sites >= 2:
        # Expand along graph edges from seed
        # Priority 1: direct outgoing edges (seed does action → target receives)
        # Priority 2: direct incoming edges (source does action → seed receives)
        # Priority 3: hub-mediated (seed → hub → other site, e.g. both connect to email)
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

    # Weight: under-covered macros get higher weight; edge-implied macros get a boost
    edge_macro_set = set(edge_macros)
    macro_weights = []
    for m in macro_pool:
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
    """Single annotation interface — system samples sites × macros."""
    sites = _load_sites()
    coverage = _get_macro_coverage()
    prompt = _generate_prompt(sites, coverage)

    return render_template("annotate.html",
                           sites=sites,
                           prompt=prompt,
                           macro_descriptions=_MACRO_DESCRIPTIONS,
                           macro_locations=MACRO_LOCATIONS)


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


# --- API ---

@annotation_bp.route("/api/tasks", methods=["GET"])
def api_list_tasks():
    from annotation.storage import list_tasks
    annotator = request.args.get("annotator")
    return jsonify(list_tasks(annotator))


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

    # Record N/A macros for future sampling improvement
    na_macros = data.get("macros_not_applicable", {})
    if na_macros:
        None

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
    """Return macro-to-location map for a specific site."""
    return jsonify(MACRO_LOCATIONS.get(site_id, {}))


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
    single = request.args.get("single") == "1"
    prompt = _generate_prompt(sites, coverage, force_single=single)
    return jsonify(prompt)


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

    # Set generic user_id to 1 (Alex Rivera's ID on most sites)
    session["user_id"] = 1

    # Site-specific session keys for sites that don't use the generic "user_id"
    SITE_SESSION_KEYS = {
        "conference-review-submission": "_conf_user_id",
        "health-portals": "health_user_id",
        "insurance-loans": "il_user_id",
        "instant-messaging": "im_user_id",
        "job-sites": "job_sites_user_id",
        "qa-knowledge": "qa_user_id",
        "university-academic": "ua_user",
        "version-control": "vc_user_id",
        "team-chat-workspace": "user_id",  # uses root_user_id
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

            # Set site-specific session key
            if site_id in SITE_SESSION_KEYS:
                key = SITE_SESSION_KEYS[site_id]
                if site_id == "university-academic":
                    session[key] = user.get("net_id", user.get("username", ""))
                elif site_id == "version-control":
                    session[key] = user.get("root_user_id", uid)
                    session["vc_username"] = user.get("username", "")
                    session["vc_name"] = user.get("name", "")
                elif site_id == "team-chat-workspace":
                    session[key] = user.get("root_user_id", uid)
                else:
                    session[key] = uid

            logged_in.append(site_id)
        except Exception as exc:
            import traceback
            traceback.print_exc()

    return jsonify({"logged_in": logged_in})


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


@annotation_bp.route("/api/report", methods=["POST"])
def api_report():
    """Save a skip report."""
    data = request.get_json(silent=True) or {}
    data["timestamp"] = datetime.now().isoformat()
    report_id = 0
    return jsonify({"status": "reported", "id": report_id})


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
        "You are an expert at writing clear, precise task instructions for "
        "browser-agent benchmarks. Given a rough draft instruction, rewrite it "
        "to be:\n"
        "1. Clear and unambiguous — a person unfamiliar with the site should understand exactly what to do\n"
        "2. Specific — use concrete values, names, or identifiers when possible\n"
        "3. Natural — sound like a real user request, not a test script\n"
        "4. Concise — remove unnecessary words while keeping all required details\n"
        "5. Actionable — every step should be doable from the browser\n\n"
        "Output ONLY the refined instruction. No preamble, no explanation."
        + site_context + macro_context
    )

    refined = _call_llm(system_prompt, instruction)
    if refined:
        return jsonify({"refined": refined})
    return jsonify({"error": "LLM unavailable — check OPENAI_API_KEY in .env"}), 503


def _call_llm(system_prompt, user_prompt):
    """Call LLM via shared Groq/Claude helper."""
    from app.llm import call_llm
    return call_llm(user_prompt, system=system_prompt, max_tokens=500, temperature=0.4)


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
    """LLM call via shared Groq/Claude helper."""
    from app.llm import call_llm
    try:
        return call_llm(prompt, max_tokens=max_tokens, temperature=0.2)
    except Exception:
        import traceback
        traceback.print_exc()
        return None


_verifier_processes = {}  # job_id -> subprocess.Popen


def _spawn_claude_verifier_builder(ctx_file, result_file):
    """Spawn claude CLI as a background subprocess to build verifiers."""
    import subprocess, shutil

    claude_bin = shutil.which("claude") or "/uufs/chpc.utah.edu/sys/installdir/r8/claude/2.1.83/bin/claude"
    import os as _os
    if not _os.path.isfile(claude_bin):
        result_file.write_text(json.dumps({"error": "claude CLI not found"}))
        return

    prompt = (
        f"Read the JSON file at {ctx_file}. "
        f"It contains context for a MiniWeb annotation task with fields: "
        f"instruction, trajectory (with api_calls per action), macro_spans, "
        f"expected_answer, expected_outcome, and admin_schemas. "
        f"\n\n"
        f"Generate a JSON array of verifier configs — one per macro span. "
        f"Each config: {{\"macro\": \"name\", \"span\": [start, end], \"checks\": [...]}}. "
        f"Check types: grounding (required_urls), state_query (endpoint, params, check, expected), "
        f"answer_match (expected, match_type), record_exists/record_absent (endpoint, params), "
        f"action_performed (action, target_contains). "
        f"Always include grounding. For state-changing macros include state checks. "
        f"For extraction macros include answer_match. "
        f"Honor the expected_outcome field. "
        f"\n\n"
        f"Write ONLY the JSON array (no markdown) to {result_file}"
    )

    job_id = ctx_file.stem.replace("_context", "")

    proc = subprocess.Popen(
        [claude_bin, "-p", prompt,
         "--allowedTools", "Read", "Write",
         "--max-turns", "5"],
        cwd=str(ctx_file.parent.parent.parent),  # project root
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _verifier_processes[job_id] = proc


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
                            "error": "Claude output was not a JSON array"})
    except (json.JSONDecodeError, OSError) as e:
        return jsonify({"status": "error", "ready": False, "error": str(e)})

    return jsonify({"status": "done", "ready": True, "configs": configs})


@annotation_bp.route("/api/load_verifiers", methods=["POST"])
def api_load_verifiers():
    """Load verifier configs from file (after Claude Code writes them)."""
    from flask import current_app
    data = request.get_json(silent=True) or {}
    result_file = data.get("result_file", "")

    if not result_file:
        return jsonify({"error": "No result_file specified"}), 400

    import pathlib as _pl
    path = _pl.Path(result_file)
    if not path.exists():
        return jsonify({"error": "File not found. Run the Claude Code command first.", "ready": False})

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

    Spawns a real browser session, navigates the site, and uses ChatClaude
    (Groq/Claude) as the LLM to decide actions. After the agent finishes,
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
        from agents import ChatClaude
        from browser_use import Agent, BrowserSession

        llm = ChatClaude(model="claude-cli")
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


# --- Verifier system prompt for Claude ---
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


def _call_claude_for_verifiers(context):
    """Call Claude to generate verifier configs from task context."""
    import os

    # Try Anthropic first
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        env_path = PROJECT_ROOT / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if line.startswith("export "):
                    line = line[7:]
                if line.startswith("ANTHROPIC_API_KEY="):
                    api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break

    if api_key:
        return _call_anthropic(api_key, context)

    # Fallback to OpenAI
    return _call_openai_verifiers(context)


def _call_anthropic(api_key, context):
    """Call Anthropic Claude API to generate verifier configs."""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        # Trim trajectory to avoid token limits
        trimmed_ctx = _trim_context(context)

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            system=_VERIFIER_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": json.dumps(trimmed_ctx)}],
        )

        text = response.content[0].text.strip()
        # Extract JSON from response (handle markdown code blocks)
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()

        return json.loads(text)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return None


def _call_openai_verifiers(context):
    """Generate verifier configs via Groq/Claude."""
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

@annotation_bp.route("/api/review/<site_id>", methods=["POST"])
def api_submit_review(site_id):
    """Submit free-form feedback for a site."""
    data = request.get_json(silent=True) or {}
    # Reviews stored in file system (future: data_sources/annotations/reviews/)
    return jsonify({"status": "saved", "count": 0})


@annotation_bp.route("/api/review_status")
def api_review_status():
    """List sites with their review counts."""
    sites = _load_sites()
    review_counts = {}
    result = []
    for s in sites:
        result.append({
            "id": s["id"],
            "name": s.get("name", s["id"]),
            "review_count": review_counts.get(s["id"], 0),
        })
    return jsonify(result)


@annotation_bp.route("/api/reviews/<site_id>")
def api_get_reviews(site_id):
    """Get all reviews for a site."""
    return jsonify([])


@annotation_bp.route("/dashboard")
def dashboard():
    tasks = []
    macros = _load_macros()
    coverage = _get_macro_coverage()
    site_counts = {}
    cell_counts = _get_cell_counts()

    diff_counts = {"easy": 0, "medium": 0, "hard": 0}
    for t in tasks:
        d = t.get("difficulty", "").lower()
        if d in diff_counts:
            diff_counts[d] += 1

    return render_template("dashboard.html",
                           tasks=tasks, macros=macros, coverage=coverage,
                           site_counts=site_counts, cell_counts=cell_counts,
                           diff_counts=diff_counts)
