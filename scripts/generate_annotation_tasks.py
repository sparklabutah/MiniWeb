#!/usr/bin/env python3
"""Generate 60 task drafts per site using domain-aware scenario templates.

Each site type gets templates that make contextual sense — a banking user
asks about balances and transactions, not about "nicknames" or "IDs".

Usage:
    python scripts/generate_annotation_tasks.py
    python scripts/generate_annotation_tasks.py --site email
"""

import argparse
import json
import random
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SITES_DIR = PROJECT_ROOT / "sites"
OUTPUT_DIR = PROJECT_ROOT / "annotation" / "generated"


# ---------------------------------------------------------------------------
# Domain-specific scenario templates
# ---------------------------------------------------------------------------
# Each template: (instruction, difficulty, macros)
# Placeholders: {user}, {pwd}, {name}, {name2}, {cat}, {cat_val}
# Templates only use placeholders that make sense in the domain.

DOMAIN_TEMPLATES = {
    # ===== FINANCIAL =====
    "banking": {
        "easy": [
            ("Show me all my bank accounts and their balances.", ["navigate_by_route", "extract_by_route"]),
            ("How many transactions do I have this month?", ["navigate_by_route", "extract_by_route"]),
            ("What bills are due this week?", ["navigate_by_route", "extract_by_route"]),
            ("Check the status of my auto-pay settings.", ["navigate_by_route", "extract_by_route"]),
            ("What is the interest rate on my savings account?", ["navigate_by_route", "extract_by_route"]),
            ("Show me my loan details — remaining balance and monthly payment.", ["navigate_by_route", "extract_by_route"]),
            ("List all my registered payees.", ["navigate_by_route", "extract_by_route"]),
            ("What was my most recent transaction?", ["navigate_by_route", "extract_by_route"]),
        ],
        "medium": [
            ("Show me all transactions categorized as '{cat_val}' this month.", ["filter_by_dropdown", "extract_by_route"]),
            ("Find transactions over $100 and sort them by date.", ["filter_by_dropdown", "sort_by_ranking", "extract_by_route"]),
            ("Which of my bills are overdue? List the payee names and amounts.", ["filter_by_dropdown", "extract_by_route"]),
            ("Compare my checking and savings account balances — which has more?", ["navigate_by_route", "extract_by_route", "compare_from_table"]),
            ("Find the payee '{name}' and show me all payments I've made to them.", ["search_by_query", "extract_by_route"]),
            ("What is my total spending in the '{cat_val}' category?", ["filter_by_dropdown", "extract_by_route"]),
        ],
        "hard": [
            ("Log in as '{user}' (password: '{pwd}') and pay the electricity bill to '{name}'. Verify the payment appears in my transaction history.", ["authenticate_by_form", "navigate_by_route", "submit_by_form", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}') and transfer $200 from checking to savings. Confirm both balances updated.", ["authenticate_by_form", "navigate_by_route", "submit_by_form", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Add a new payee called 'Netflix' and set up auto-pay. Verify it shows in your payee list.", ["authenticate_by_form", "create_from_free_text", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Check if any bills are past due, pay them, and verify the status changed to 'paid'.", ["authenticate_by_form", "filter_by_dropdown", "submit_by_form", "extract_by_route"]),
        ],
    },

    "credit-card": {
        "easy": [
            ("What is my current credit card balance?", ["navigate_by_route", "extract_by_route"]),
            ("How many transactions have I made this billing cycle?", ["navigate_by_route", "extract_by_route"]),
            ("What is my available credit?", ["navigate_by_route", "extract_by_route"]),
            ("Show me my rewards points balance.", ["navigate_by_route", "extract_by_route"]),
            ("When is my next payment due?", ["navigate_by_route", "extract_by_route"]),
            ("What is my credit limit?", ["navigate_by_route", "extract_by_route"]),
            ("Show me the most recent statement.", ["navigate_by_route", "extract_by_route"]),
        ],
        "medium": [
            ("Show me all dining transactions and the total amount I spent on dining.", ["filter_by_dropdown", "extract_by_route"]),
            ("Find all transactions at '{name}' — how much have I spent there?", ["search_by_query", "extract_by_route"]),
            ("Which spending category has the highest total this month?", ["navigate_by_route", "extract_by_route"]),
            ("List all pending transactions sorted by amount.", ["filter_by_dropdown", "sort_by_ranking", "extract_by_route"]),
            ("Show me transactions between January 20 and January 31.", ["filter_by_dropdown", "extract_by_route"]),
            ("What is my total interest charged across all statements?", ["navigate_by_route", "extract_by_route"]),
        ],
        "hard": [
            ("Log in as '{user}' (password: '{pwd}') and make a payment of $200 via bank transfer. Verify the payment shows up in payment history.", ["authenticate_by_form", "submit_by_form", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}') and dispute the transaction at '{name}'. Confirm it's marked as disputed.", ["authenticate_by_form", "search_by_query", "submit_by_form", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}') and freeze your card. Then verify the card status shows as frozen in settings.", ["authenticate_by_form", "navigate_by_route", "submit_by_form", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}') and redeem 5000 rewards points for a statement credit. How many points remain?", ["authenticate_by_form", "navigate_by_route", "submit_by_form", "extract_by_route"]),
        ],
    },

    "brokerage": {
        "easy": [
            ("What is the current price of {name}?", ["search_by_query", "extract_by_route"]),
            ("Show me the details for ticker symbol {name}.", ["search_by_query", "extract_by_route"]),
            ("List all stocks in the {cat_val} sector.", ["filter_by_dropdown", "extract_by_route"]),
            ("How many stocks are on my watchlist?", ["navigate_by_route", "extract_by_route"]),
            ("What is the market cap of {name}?", ["search_by_query", "extract_by_route"]),
        ],
        "medium": [
            ("Show me all my buy orders and their status.", ["filter_by_dropdown", "extract_by_route"]),
            ("Find all {cat_val} sector stocks and sort them by market cap. What's the largest?", ["filter_by_dropdown", "sort_by_ranking", "extract_by_route"]),
            ("Compare {name} and {name2} — which has a higher price?", ["search_by_query", "extract_by_route", "compare_from_table"]),
            ("What is my total portfolio value across all holdings?", ["navigate_by_route", "extract_by_route"]),
            ("Show me all pending orders sorted by date.", ["filter_by_dropdown", "sort_by_ranking", "extract_by_route"]),
        ],
        "hard": [
            ("Log in as '{user}' (password: '{pwd}') and add {name} to your watchlist. Confirm it appears there.", ["authenticate_by_form", "search_by_query", "save_by_toggle", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}') and place a buy order for 10 shares of {name} at market price. Verify the order was created.", ["authenticate_by_form", "search_by_query", "submit_by_form", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Check your portfolio holdings and tell me your best-performing stock.", ["authenticate_by_form", "navigate_by_route", "extract_by_route"]),
        ],
    },

    # ===== COMMUNICATION =====
    "email": {
        "easy": [
            ("How many emails are in my inbox?", ["navigate_by_route", "extract_by_route"]),
            ("Show me the most recent email. Who sent it and what's the subject?", ["navigate_by_route", "extract_by_route"]),
            ("How many unread emails do I have?", ["navigate_by_route", "extract_by_route"]),
            ("List all my email folders and how many messages are in each.", ["navigate_by_route", "extract_by_route"]),
            ("Show me my contacts list.", ["navigate_by_route", "extract_by_route"]),
        ],
        "medium": [
            ("Search for emails about '{name}'. How many results come up?", ["search_by_query", "extract_by_route"]),
            ("Find all emails with 'meeting' in the subject line.", ["search_by_query", "extract_by_route"]),
            ("Show me emails in the sent folder sorted by newest first. What was the last email I sent?", ["navigate_by_route", "sort_by_ranking", "extract_by_route"]),
            ("Search for emails from '{name}' and tell me how many there are.", ["search_by_query", "extract_by_route"]),
            ("How many emails contain the word 'contract'?", ["search_by_query", "extract_by_route"]),
        ],
        "hard": [
            ("Log in as '{user}' (password: '{pwd}') and compose an email to test@example.com with subject 'Project Update'. Send it and confirm it appears in Sent.", ["authenticate_by_form", "create_from_free_text", "navigate_by_route", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'), open the first inbox email and star it. Then check that your starred count increased.", ["authenticate_by_form", "navigate_by_route", "save_by_toggle", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'), find the email about '{name}', and move it to the spam folder. Verify the spam folder count increased.", ["authenticate_by_form", "search_by_query", "submit_by_form", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}') and mark the first 3 inbox emails as read. How many unread emails remain?", ["authenticate_by_form", "navigate_by_route", "submit_by_form", "extract_by_route"]),
        ],
    },

    # ===== SHOPPING =====
    "e-commerce": {
        "easy": [
            ("How many products are available in the store?", ["navigate_by_route", "extract_by_route"]),
            ("Search for '{name}'. How many results come up?", ["search_by_query", "extract_by_route"]),
            ("What categories of products are available?", ["navigate_by_route", "extract_by_route"]),
            ("Show me the details for '{name}' — what is its price and rating?", ["search_by_query", "extract_by_route"]),
            ("How many brands are represented in the catalog?", ["navigate_by_route", "extract_by_route"]),
        ],
        "medium": [
            ("Find products in the '{cat_val}' category and sort by price. What's the cheapest?", ["filter_by_dropdown", "sort_by_ranking", "extract_by_route"]),
            ("Search for '{name}' and compare it with '{name2}' — which is cheaper?", ["search_by_query", "extract_by_route", "compare_from_table"]),
            ("Show me all products priced between $10 and $50.", ["filter_by_dropdown", "extract_by_route"]),
            ("What is the average rating of products in the '{cat_val}' category?", ["filter_by_dropdown", "extract_by_route"]),
            ("Find the highest-rated product in the store. What is it?", ["sort_by_ranking", "extract_by_route"]),
        ],
        "hard": [
            ("Log in as '{user}' (password: '{pwd}'), find '{name}', and add it to your cart. Then check your cart total.", ["authenticate_by_form", "search_by_query", "submit_by_form", "navigate_by_route", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'), add '{name}' to your wishlist. Verify it appears on your wishlist page.", ["authenticate_by_form", "search_by_query", "save_by_toggle", "navigate_by_route", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'), add two items to your cart, then proceed to checkout. What is the order total?", ["authenticate_by_form", "search_by_query", "submit_by_form", "navigate_by_route", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'), find '{name}' and submit a 5-star review titled 'Great product'. Verify the review appears.", ["authenticate_by_form", "search_by_query", "create_from_free_text", "extract_by_route"]),
        ],
    },

    "crowdfunding-donations": {
        "easy": [
            ("How many campaigns are currently active?", ["filter_by_dropdown", "extract_by_route"]),
            ("Show me the '{cat_val}' category campaigns.", ["navigate_by_dropdown", "extract_by_route"]),
            ("What is the funding progress of '{name}'?", ["search_by_query", "extract_by_route"]),
            ("How many total backers are there across all campaigns?", ["navigate_by_route", "extract_by_route"]),
            ("Which campaign has raised the most money?", ["sort_by_ranking", "extract_by_route"]),
        ],
        "medium": [
            ("Find all campaigns in the '{cat_val}' category that are fully funded.", ["filter_by_dropdown", "extract_by_route"]),
            ("Search for '{name}' — how much has it raised and what percentage of its goal?", ["search_by_query", "extract_by_route"]),
            ("List active campaigns sorted by backer count. Which has the most backers?", ["filter_by_dropdown", "sort_by_ranking", "extract_by_route"]),
            ("Compare '{name}' and '{name2}' — which is closer to its funding goal?", ["search_by_query", "extract_by_route", "compare_from_table"]),
            ("What reward tiers are available for '{name}'?", ["search_by_query", "extract_by_route"]),
        ],
        "hard": [
            ("Log in as '{user}' (password: '{pwd}') and pledge $50 to '{name}'. Verify the backer count increased.", ["authenticate_by_form", "search_by_query", "submit_by_form", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}') and create a new campaign titled 'Community Garden Project' in the 'community' category with a $5000 goal. Verify it appears in the listing.", ["authenticate_by_form", "create_from_free_text", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Check your dashboard — how many campaigns have you backed? Then pledge to a new campaign and confirm the count increased.", ["authenticate_by_form", "navigate_by_route", "extract_by_route", "submit_by_form"]),
        ],
    },

    # ===== PRODUCTIVITY =====
    "crm": {
        "easy": [
            ("How many deals are in the pipeline?", ["navigate_by_route", "extract_by_route"]),
            ("What is the current win rate?", ["navigate_by_route", "extract_by_route"]),
            ("List all companies in the CRM.", ["navigate_by_route", "extract_by_route"]),
            ("Show me the contact details for '{name}'.", ["search_by_query", "extract_by_route"]),
            ("How many contacts are in the system?", ["navigate_by_route", "extract_by_route"]),
        ],
        "medium": [
            ("Show me all deals in the '{cat_val}' stage. What is their total value?", ["filter_by_dropdown", "extract_by_route"]),
            ("Find all contacts at '{name}' and list their names and titles.", ["search_by_query", "extract_by_route"]),
            ("Which deal has the highest value? Show me its details.", ["sort_by_ranking", "extract_by_route"]),
            ("How many activities of type 'call' have been logged?", ["filter_by_dropdown", "extract_by_route"]),
            ("What is the total revenue from closed-won deals?", ["filter_by_dropdown", "extract_by_route"]),
        ],
        "hard": [
            ("Log in as '{user}' (password: '{pwd}') and create a new deal called 'Enterprise Upgrade' for {name} worth $75,000 in the prospecting stage. Verify it appears in the pipeline.", ["authenticate_by_form", "create_from_free_text", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}') and log a call activity for the contact at {name}. Describe it as 'Follow-up on proposal'. Verify it shows in the activity log.", ["authenticate_by_form", "create_from_free_text", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}') and move the deal '{name}' to 'closed-won' stage. What is the new win rate?", ["authenticate_by_form", "search_by_query", "edit_by_form", "extract_by_route"]),
        ],
    },

    "documents": {
        "easy": [
            ("How many documents are in the system?", ["navigate_by_route", "extract_by_route"]),
            ("Show me all starred documents.", ["navigate_by_route", "extract_by_route"]),
            ("How many documents are in the trash?", ["navigate_by_route", "extract_by_route"]),
            ("What folders exist? How many documents are in each?", ["navigate_by_route", "extract_by_route"]),
            ("Search for documents about '{name}'. How many results?", ["search_by_query", "extract_by_route"]),
        ],
        "medium": [
            ("Find '{name}' and tell me who owns it and how many collaborators it has.", ["search_by_query", "extract_by_route"]),
            ("Show me all documents sorted alphabetically. What's the first one?", ["sort_by_ranking", "extract_by_route"]),
            ("What is the total word count across all documents?", ["navigate_by_route", "extract_by_route"]),
            ("How many revisions does '{name}' have?", ["search_by_query", "extract_by_route"]),
            ("Find documents owned by user ID 1. How many are there?", ["filter_by_dropdown", "extract_by_route"]),
        ],
        "hard": [
            ("Log in as '{user}' (password: '{pwd}') and star the document '{name}'. Verify it appears in your starred list.", ["authenticate_by_form", "search_by_query", "save_by_toggle", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}') and create a new document titled 'Meeting Notes'. Verify it appears in the document list.", ["authenticate_by_form", "create_from_free_text", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'), share '{name}' with user ID 3 as an editor. Verify the collaborator was added.", ["authenticate_by_form", "search_by_query", "submit_by_form", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}') and move '{name}' to trash. Verify it no longer appears in the main list.", ["authenticate_by_form", "search_by_query", "delete_from_table", "extract_by_route"]),
        ],
    },

    # ===== EDUCATION =====
    "course-sites-classrooms": {
        "easy": [
            ("How many courses are available?", ["navigate_by_route", "extract_by_route"]),
            ("What courses does Prof. {name} teach?", ["search_by_query", "extract_by_route"]),
            ("Show me the course catalog for the CS department.", ["filter_by_dropdown", "extract_by_route"]),
            ("How many students are enrolled across all courses?", ["navigate_by_route", "extract_by_route"]),
        ],
        "medium": [
            ("What is the weighted average grade for the top student in CS201?", ["navigate_by_route", "extract_by_route"]),
            ("How many assignments are due this month in CS201?", ["navigate_by_route", "extract_by_route"]),
            ("Show me the gradebook for CS201. Who has the highest grade?", ["navigate_by_route", "sort_by_ranking", "extract_by_route"]),
            ("How many discussion posts are in CS201? What are their topics?", ["navigate_by_route", "extract_by_route"]),
        ],
        "hard": [
            ("Log in as '{user}' (password: '{pwd}') and post a new discussion titled 'Study Group for Finals' in CS201. Verify it appears.", ["authenticate_by_form", "navigate_by_route", "create_from_free_text", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}') and reply to the first discussion in CS201. Verify your reply was added.", ["authenticate_by_form", "navigate_by_route", "create_from_free_text", "extract_by_route"]),
        ],
    },

    "conference-review-submission": {
        "easy": [
            ("How many papers were submitted to ICLR 2017?", ["navigate_by_route", "extract_by_route"]),
            ("What is the acceptance rate?", ["navigate_by_route", "extract_by_route"]),
            ("How many papers were accepted?", ["filter_by_dropdown", "extract_by_route"]),
            ("Search for papers about '{name}'. How many results?", ["search_by_query", "extract_by_route"]),
        ],
        "medium": [
            ("What is the average review score for accepted papers vs rejected papers?", ["navigate_by_route", "extract_by_route"]),
            ("Find the paper with the highest review score. What is its title?", ["sort_by_ranking", "extract_by_route"]),
            ("Search for papers by '{name}'. How many did they author?", ["search_by_query", "extract_by_route"]),
            ("Show me all papers with a review score above 7. How many are there?", ["filter_by_dropdown", "extract_by_route"]),
        ],
        "hard": [
            ("Log in as '{user}' (password: '{pwd}') and submit a review for paper ID 5 with a recommendation score of 7 and comments. Verify the review was recorded.", ["authenticate_by_form", "navigate_by_route", "submit_by_form", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}') and bid on paper ID 3. Then check your assignments to confirm.", ["authenticate_by_form", "navigate_by_route", "submit_by_form", "extract_by_route"]),
        ],
    },

    # ===== SEARCH & REFERENCE =====
    "dictionaries-language-tools": {
        "easy": [
            ("What is today's word of the day?", ["navigate_by_route", "extract_by_route"]),
            ("Look up the word '{name}'. What is its definition?", ["search_by_query", "extract_by_route"]),
            ("How many words start with the letter S?", ["navigate_by_dropdown", "extract_by_route"]),
            ("What part of speech is '{name}'?", ["search_by_query", "extract_by_route"]),
        ],
        "medium": [
            ("Find all nouns in the dictionary. How many are there?", ["filter_by_dropdown", "extract_by_route"]),
            ("Look up '{name}' — does it have synonyms? List them.", ["search_by_query", "extract_by_route"]),
            ("Search for '{name}' and tell me its etymology.", ["search_by_query", "extract_by_route"]),
            ("How many words have pronunciation (IPA) data available?", ["navigate_by_route", "extract_by_route"]),
            ("Which letter of the alphabet has the most words?", ["navigate_by_route", "extract_by_route"]),
        ],
        "hard": [
            ("Log in as '{user}' (password: '{pwd}') and save the word '{name}' to your vocabulary. Verify it appears in your saved words.", ["authenticate_by_form", "search_by_query", "save_by_toggle", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'), save 3 different words, and then check your dashboard. How many saved words do you have?", ["authenticate_by_form", "search_by_query", "save_by_toggle", "navigate_by_route", "extract_by_route"]),
        ],
    },

    "documentation-api-docs": {
        "easy": [
            ("How many documentation pages are there?", ["navigate_by_route", "extract_by_route"]),
            ("What sections does the documentation have?", ["navigate_by_route", "extract_by_route"]),
            ("How many API endpoints use the GET method?", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Authentication page. What are the key concepts?", ["navigate_by_route", "extract_by_route"]),
            ("Show me the latest changelog entry. What version is it?", ["navigate_by_route", "extract_by_route"]),
        ],
        "medium": [
            ("How many API endpoints use the POST method?", ["filter_by_dropdown", "extract_by_route"]),
            ("Search for documentation about '{name}'. What pages mention it?", ["search_by_query", "extract_by_route"]),
            ("What parameters are required to create a Pod?", ["navigate_by_route", "extract_by_route"]),
            ("Find all pages tagged with '{cat_val}'. How many are there?", ["filter_by_dropdown", "extract_by_route"]),
        ],
        "hard": [
            ("Log in as '{user}' (password: '{pwd}') and bookmark the Deployments page. Verify it appears in your bookmarked pages.", ["authenticate_by_form", "navigate_by_route", "save_by_toggle", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'), bookmark 3 different documentation pages, then check your dashboard. How many bookmarks do you have?", ["authenticate_by_form", "navigate_by_route", "save_by_toggle", "extract_by_route"]),
        ],
    },

    "comparison-aggregators": {
        "easy": [
            ("How many phones are in the database?", ["navigate_by_route", "extract_by_route"]),
            ("How many brands are available?", ["navigate_by_route", "extract_by_route"]),
            ("Search for '{name}'. Show me its specs.", ["search_by_query", "extract_by_route"]),
            ("List all Samsung phones.", ["filter_by_dropdown", "extract_by_route"]),
        ],
        "medium": [
            ("Show me all Android phones sorted by battery size. Which has the biggest battery?", ["filter_by_dropdown", "sort_by_ranking", "extract_by_route"]),
            ("Compare '{name}' and '{name2}' side by side. Which has a better camera?", ["search_by_query", "compare_from_table", "extract_by_route"]),
            ("Find phones with 5000+ mAh battery. How many are there?", ["filter_by_dropdown", "extract_by_route"]),
            ("Which brand has the most phones in the database?", ["navigate_by_route", "extract_by_route"]),
        ],
        "hard": [
            ("Log in as '{user}' (password: '{pwd}') and add '{name}' to your favorites. Check your dashboard to confirm.", ["authenticate_by_form", "search_by_query", "save_by_toggle", "navigate_by_route", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'), add 3 phones to your compare list, then view the comparison. What are the key differences?", ["authenticate_by_form", "search_by_query", "save_by_toggle", "navigate_by_route", "compare_from_table"]),
        ],
    },
}

# Generic fallback for sites without specific templates
GENERIC_TEMPLATES = {
    "easy": [
        ("Show me the main page of the {site} site. What content is displayed?", ["navigate_by_route", "extract_by_route"]),
        ("How many items are listed on the {site} site?", ["navigate_by_route", "extract_by_route"]),
        ("Search for '{name}' on the {site} site.", ["search_by_query", "extract_by_route"]),
        ("Browse the '{cat_val}' section.", ["navigate_by_dropdown", "extract_by_route"]),
        ("Show me the details for '{name}'.", ["search_by_query", "extract_by_route"]),
    ],
    "medium": [
        ("Filter items by {cat_key} '{cat_val}'. How many match?", ["filter_by_dropdown", "extract_by_route"]),
        ("Search for '{name}' and tell me all its details.", ["search_by_query", "extract_by_route"]),
        ("Sort the listing by name and show me the first result.", ["sort_by_ranking", "extract_by_route"]),
        ("Compare '{name}' and '{name2}'. What are the differences?", ["search_by_query", "compare_from_table", "extract_by_route"]),
        ("Find all items in the '{cat_val}' category sorted alphabetically.", ["filter_by_dropdown", "sort_by_ranking", "extract_by_route"]),
    ],
    "hard": [
        ("Log in as '{user}' (password: '{pwd}') and save '{name}' to your favorites. Verify it's saved.", ["authenticate_by_form", "search_by_query", "save_by_toggle", "extract_by_route"]),
        ("Log in as '{user}' (password: '{pwd}') and create a new item. Verify it appears.", ["authenticate_by_form", "create_from_free_text", "extract_by_route"]),
        ("Log in as '{user}' (password: '{pwd}'), find '{name}' and update its details. Verify the change.", ["authenticate_by_form", "search_by_query", "edit_by_form", "extract_by_route"]),
        ("Log in as '{user}' (password: '{pwd}'). Check your profile/dashboard and report what's there.", ["authenticate_by_form", "navigate_by_route", "extract_by_route"]),
    ],
}


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

def load_site_context(site_id):
    site_dir = SITES_DIR / site_id
    ctx = {"site_id": site_id, "data": {}, "users": [], "entities": []}
    data_dir = site_dir / "data"
    if data_dir.exists():
        for f in list(data_dir.glob("*.json")) + list(data_dir.glob("*.jsonl")):
            if f.name.startswith("."):
                continue
            try:
                if f.suffix == ".jsonl":
                    items = []
                    with open(f) as fh:
                        for i, line in enumerate(fh):
                            if i >= 50: break
                            if line.strip(): items.append(json.loads(line))
                    ctx["data"][f.stem.replace("_sample", "")] = items
                else:
                    ctx["data"][f.stem] = json.loads(f.read_text())
            except: pass
    ctx["users"] = ctx["data"].get("users", [])

    # Extract entities
    name_keys = ["name", "title", "word", "subject", "merchant", "company", "campaign", "symbol", "headline", "topic"]
    filter_keys = ["category", "status", "type", "stage", "sector", "os", "brand", "pos", "section", "folder"]
    for source, content in ctx["data"].items():
        if source == "users" or not isinstance(content, list): continue
        for item in content:
            if not isinstance(item, dict): continue
            name = None
            for nk in name_keys:
                val = item.get(nk)
                if val and isinstance(val, str) and 2 < len(val) < 60:
                    name = val; break
            if not name: continue
            ctx["entities"].append({
                "name": name, "source": source,
                "filters": {k: v for k, v in item.items() if isinstance(v, str) and k in filter_keys},
            })
    return ctx


def generate_tasks(site_id, ctx, rng):
    templates = DOMAIN_TEMPLATES.get(site_id, GENERIC_TEMPLATES)
    site_label = site_id.replace("-", " ").replace("_", " ")
    entities = ctx["entities"]
    users = ctx["users"]
    tasks = []
    used = set()

    def fill(tmpl):
        t = tmpl
        ent = rng.choice(entities) if entities else None
        ent2 = rng.choice([e for e in entities if e != ent]) if entities and len(entities) > 1 else None
        user = rng.choice(users) if users else None
        filt = ent["filters"] if ent and ent.get("filters") else {}
        fk, fv = rng.choice(list(filt.items())) if filt else ("category", "general")

        replacements = {
            "site": site_label,
            "name": ent["name"] if ent else "example",
            "name2": ent2["name"] if ent2 else "other item",
            "cat_val": fv, "cat_key": fk.replace("_", " "),
            "user": user.get("username", "") if user else "",
            "pwd": user.get("password", "") if user else "",
        }
        try:
            return t.format(**replacements)
        except (KeyError, IndexError):
            return None

    for diff in ["easy", "medium", "hard"]:
        count = 0
        pool = list(templates.get(diff, GENERIC_TEMPLATES[diff])) * 5
        rng.shuffle(pool)
        for tmpl, macros in pool:
            if count >= 20: break
            inst = fill(tmpl)
            if not inst: continue
            key = inst.lower()[:60]
            if key in used: continue
            used.add(key)
            tasks.append({
                "task_id": f"{site_id}_draft_{len(tasks)+1:03d}",
                "site": site_id,
                "instruction": inst,
                "difficulty": diff,
                "macros": macros,
                "expected_answer": None,
                "eval": [],
                "status": "draft",
            })
            count += 1

    return tasks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--site")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)
    sites = []
    for d in sorted(SITES_DIR.iterdir()):
        if not d.is_dir() or d.name.startswith("_"): continue
        if not (d / "tasks.json").exists() or (d / "routes.py").stat().st_size < 500: continue
        if args.site and d.name != args.site: continue
        sites.append(d.name)

    print(f"Generating for {len(sites)} sites...")
    total = 0
    for site_id in sites:
        ctx = load_site_context(site_id)
        tasks = generate_tasks(site_id, ctx, rng)
        e = sum(1 for t in tasks if t["difficulty"] == "easy")
        m = sum(1 for t in tasks if t["difficulty"] == "medium")
        h = sum(1 for t in tasks if t["difficulty"] == "hard")
        print(f"  {site_id}: {len(tasks)} (E:{e} M:{m} H:{h})")
        (OUTPUT_DIR / f"{site_id}.json").write_text(json.dumps(tasks, indent=2))
        total += len(tasks)
    print(f"\nTotal: {total}")


if __name__ == "__main__":
    main()
