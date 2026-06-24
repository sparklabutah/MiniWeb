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
            ("Navigate to the Accounts page and tell me how many accounts are listed.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Accounts page and report the checking account balance.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Transactions page and tell me the merchant name on the most recent transaction.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Pay Bills page and report how many bills are displayed.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Payees page and tell me how many registered payees there are.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Loans page and report the remaining balance on the first loan listed.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Settings page and tell me whether auto-pay is currently enabled or disabled.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Transactions page and report the dollar amount of the most recent transaction.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Pay Bills page and tell me the due date of the first bill listed.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Loans page and report the monthly payment amount for the first loan.", ["navigate_by_route", "extract_by_route"]),
        ],
        "medium": [
            ("Navigate to the Transactions page, filter by category '{cat_val}', and report how many transactions match.", ["navigate_by_route", "filter_by_dropdown", "extract_by_route"]),
            ("Navigate to the Transactions page, sort by amount descending, and tell me the merchant name on the largest transaction.", ["navigate_by_route", "sort_by_ranking", "extract_by_route"]),
            ("Navigate to the Pay Bills page, filter to show only overdue bills, and report the total dollar amount owed.", ["navigate_by_route", "filter_by_dropdown", "extract_by_route"]),
            ("Navigate to the Transactions page, search for '{name}', and report the total amount spent at that merchant.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the Accounts page, compare the checking and savings balances, and tell me which account has the higher balance.", ["navigate_by_route", "extract_by_route", "compare_from_table"]),
            ("Navigate to the Transactions page, filter by category '{cat_val}', sort by date, and tell me the date of the oldest matching transaction.", ["navigate_by_route", "filter_by_dropdown", "sort_by_ranking", "extract_by_route"]),
            ("Navigate to the Payees page, search for '{name}', and report the payee's account number.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the Transactions page, filter to show only transactions over $100, and report how many there are.", ["navigate_by_route", "filter_by_dropdown", "extract_by_route"]),
        ],
        "hard": [
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Pay Bills, click pay on the bill for '{name}', and then navigate to Transactions to verify a payment entry for '{name}' appears. Report yes or no.", ["authenticate_by_form", "navigate_by_route", "submit_by_form", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Transfers, transfer $200 from checking to savings, then navigate to Accounts and report the new savings balance.", ["authenticate_by_form", "navigate_by_route", "submit_by_form", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Payees, add a new payee named 'Netflix' with account number 99999, then navigate back to Payees and report the total number of payees now listed.", ["authenticate_by_form", "navigate_by_route", "create_from_free_text", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Pay Bills, filter for overdue bills, pay the first one, then check whether its status changed to 'paid'. Report the bill name and its new status.", ["authenticate_by_form", "navigate_by_route", "filter_by_dropdown", "submit_by_form", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Settings, enable auto-pay, then navigate back to Settings and confirm the auto-pay toggle shows 'enabled'. Report yes or no.", ["authenticate_by_form", "navigate_by_route", "submit_by_form", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Transactions, note the current transaction count, then navigate to Transfers and send $50 to payee '{name}'. Return to Transactions and report whether the count increased by one.", ["authenticate_by_form", "navigate_by_route", "extract_by_route", "submit_by_form"]),
        ],
    },

    "credit-card": {
        "easy": [
            ("Navigate to the Account Overview page and report the current credit card balance.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Account Overview page and tell me the available credit amount.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Account Overview page and report the credit limit.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Rewards page and tell me the current points balance.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Transactions page and report how many transactions are listed.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Statements page and tell me the due date shown on the most recent statement.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Transactions page and report the merchant name on the most recent transaction.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Payment page and tell me the minimum payment amount due.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Account Overview page and report the APR listed on the account.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Statements page and tell me how many statements are available.", ["navigate_by_route", "extract_by_route"]),
        ],
        "medium": [
            ("Navigate to the Transactions page, filter by category 'dining', and report the total amount spent on dining.", ["navigate_by_route", "filter_by_dropdown", "extract_by_route"]),
            ("Navigate to the Transactions page, search for '{name}', and report the total amount spent at that merchant.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the Transactions page, sort by amount descending, and tell me the merchant name and amount on the largest transaction.", ["navigate_by_route", "sort_by_ranking", "extract_by_route"]),
            ("Navigate to the Transactions page, filter to show only pending transactions, and report how many there are.", ["navigate_by_route", "filter_by_dropdown", "extract_by_route"]),
            ("Navigate to the Transactions page, filter by category '{cat_val}', sort by date, and tell me the date of the most recent matching transaction.", ["navigate_by_route", "filter_by_dropdown", "sort_by_ranking", "extract_by_route"]),
            ("Navigate to the Statements page, open the most recent statement, and report the total interest charged.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Transactions page, filter by category '{cat_val}', and report how many transactions match.", ["navigate_by_route", "filter_by_dropdown", "extract_by_route"]),
            ("Navigate to the Rewards page and tell me how many points were earned in the most recent transaction listed.", ["navigate_by_route", "extract_by_route"]),
        ],
        "hard": [
            ("Log in as '{user}' (password: '{pwd}'). Navigate to the Payment page, submit a payment of $200, then navigate to Payment History and verify the $200 payment appears. Report yes or no.", ["authenticate_by_form", "navigate_by_route", "submit_by_form", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to the Transactions page, find the transaction at '{name}', click the dispute button, then verify its status changed to 'disputed'. Report the transaction amount and new status.", ["authenticate_by_form", "navigate_by_route", "search_by_query", "submit_by_form", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Settings, click 'Freeze Card', then navigate back to Settings and confirm the card status shows 'frozen'. Report yes or no.", ["authenticate_by_form", "navigate_by_route", "submit_by_form", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to the Rewards page, redeem 5000 points for a statement credit, then check the Rewards page again and report the remaining points balance.", ["authenticate_by_form", "navigate_by_route", "submit_by_form", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Settings, update the billing address to '123 New Street', then navigate back to Settings and confirm the address shows '123 New Street'. Report yes or no.", ["authenticate_by_form", "navigate_by_route", "edit_by_form", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Account Overview, note the current balance. Then navigate to Payment, submit a $100 payment, and return to Account Overview. Report the new balance.", ["authenticate_by_form", "navigate_by_route", "extract_by_route", "submit_by_form"]),
        ],
    },

    "brokerage": {
        "easy": [
            ("Navigate to the Market page, search for '{name}', and report its current price.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the Market page, search for '{name}', and report its market cap.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the Watchlist page and tell me how many stocks are on the watchlist.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Portfolio page and report the total portfolio value.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Orders page and tell me how many orders are listed.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Market page and report the name of the first stock listed.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Portfolio page and tell me how many holdings are displayed.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Watchlist page and report the ticker symbol of the first stock on the list.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Market page, search for '{name}', and tell me its sector.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the Orders page and report the status of the most recent order.", ["navigate_by_route", "extract_by_route"]),
        ],
        "medium": [
            ("Navigate to the Orders page, filter by order type 'buy', and report how many buy orders are listed.", ["navigate_by_route", "filter_by_dropdown", "extract_by_route"]),
            ("Navigate to the Market page, filter by sector '{cat_val}', sort by market cap descending, and tell me the name of the largest company.", ["navigate_by_route", "filter_by_dropdown", "sort_by_ranking", "extract_by_route"]),
            ("Navigate to the Market page, search for '{name}', then search for '{name2}', and tell me which has the higher price.", ["navigate_by_route", "search_by_query", "extract_by_route", "compare_from_table"]),
            ("Navigate to the Orders page, filter by status 'pending', sort by date, and report the ticker symbol on the oldest pending order.", ["navigate_by_route", "filter_by_dropdown", "sort_by_ranking", "extract_by_route"]),
            ("Navigate to the Portfolio page, sort holdings by value descending, and report the ticker and value of the top holding.", ["navigate_by_route", "sort_by_ranking", "extract_by_route"]),
            ("Navigate to the Market page, filter by sector '{cat_val}', and report how many stocks are in that sector.", ["navigate_by_route", "filter_by_dropdown", "extract_by_route"]),
            ("Navigate to the Watchlist page, sort by price descending, and report the name and price of the most expensive stock.", ["navigate_by_route", "sort_by_ranking", "extract_by_route"]),
            ("Navigate to the Portfolio page and report the total gain/loss percentage across all holdings.", ["navigate_by_route", "extract_by_route"]),
        ],
        "hard": [
            ("Log in as '{user}' (password: '{pwd}'). Navigate to the Market page, search for '{name}', click 'Add to Watchlist', then navigate to the Watchlist page and confirm '{name}' appears. Report yes or no.", ["authenticate_by_form", "navigate_by_route", "search_by_query", "save_by_toggle", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to the Trade page, place a market buy order for 10 shares of '{name}', then navigate to Orders and verify the order appears. Report the order status.", ["authenticate_by_form", "navigate_by_route", "submit_by_form", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to the Portfolio page, identify the holding with the highest gain percentage, and report its ticker symbol and gain percentage.", ["authenticate_by_form", "navigate_by_route", "sort_by_ranking", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to the Watchlist page, remove '{name}' from the watchlist, then confirm the watchlist count decreased by one. Report the new count.", ["authenticate_by_form", "navigate_by_route", "delete_from_table", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to the Trade page, place a limit sell order for 5 shares of '{name}' at $150, then navigate to Orders, filter by status 'pending', and confirm the order appears. Report yes or no.", ["authenticate_by_form", "navigate_by_route", "submit_by_form", "filter_by_dropdown", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to the Portfolio page, note the total value. Then navigate to Trade, buy 10 shares of '{name}', return to Portfolio, and report the new total value.", ["authenticate_by_form", "navigate_by_route", "extract_by_route", "submit_by_form"]),
        ],
    },

    # ===== COMMUNICATION =====
    "email": {
        "easy": [
            ("Navigate to the Inbox and report how many emails are listed.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Inbox and tell me the sender and subject of the most recent email.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Inbox and report how many emails are marked as unread.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Sent folder and tell me how many sent emails are listed.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Contacts page and report how many contacts are saved.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Inbox, open the first email, and report the full sender email address.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Folders view and list all folder names displayed.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Drafts folder and report how many draft emails are saved.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Spam folder and report how many emails are in it.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Inbox and report the subject line of the oldest email on the first page.", ["navigate_by_route", "extract_by_route"]),
        ],
        "medium": [
            ("Navigate to the Inbox, search for '{name}', and report how many emails match.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the Inbox, search for emails with 'meeting' in the subject, and report the sender of the first result.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the Sent folder, sort by date descending, and report the subject of the most recently sent email.", ["navigate_by_route", "sort_by_ranking", "extract_by_route"]),
            ("Navigate to the Inbox, search for emails from '{name}', and report how many results appear.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the Inbox, search for 'contract', and tell me the subject and date of the first matching email.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the Inbox, filter by unread emails only, sort by date, and report the sender of the oldest unread email.", ["navigate_by_route", "filter_by_dropdown", "sort_by_ranking", "extract_by_route"]),
            ("Navigate to the Starred folder and report how many starred emails there are.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Inbox, search for '{name}', open the first result, and report the full body text of that email.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
        ],
        "hard": [
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Compose, write an email to test@example.com with subject 'Project Update' and body 'See attached report', click Send, then navigate to Sent and confirm an email with subject 'Project Update' appears. Report yes or no.", ["authenticate_by_form", "navigate_by_route", "create_from_free_text", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to the Inbox, open the first email, click the Star button, then navigate to the Starred folder and report how many starred emails are now listed.", ["authenticate_by_form", "navigate_by_route", "save_by_toggle", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to the Inbox, search for '{name}', open that email, click 'Move to Spam', then navigate to the Spam folder and report the new spam count.", ["authenticate_by_form", "navigate_by_route", "search_by_query", "submit_by_form", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to the Inbox, select the first three emails, click 'Mark as Read', then report how many unread emails remain in the Inbox.", ["authenticate_by_form", "navigate_by_route", "submit_by_form", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to the Inbox, open the first email, click Reply, type 'Thanks for the update', click Send, then navigate to the Sent folder and confirm the reply appears. Report yes or no.", ["authenticate_by_form", "navigate_by_route", "create_from_free_text", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to the Inbox, note the total email count. Then navigate to Compose, send a new email to test@example.com with subject 'Test', return to Sent, and report the new sent count.", ["authenticate_by_form", "navigate_by_route", "extract_by_route", "create_from_free_text"]),
        ],
    },

    # ===== SHOPPING =====
    "e-commerce": {
        "easy": [
            ("Navigate to the Products page and report how many products are listed.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Products page, search for '{name}', and report its price.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the Products page and list all available product categories shown in the filter dropdown.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Products page, click on '{name}', and report its star rating.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the Cart page and report how many items are currently in the cart.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Products page, click on '{name}', and report whether it is in stock or out of stock.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the Products page and report the name of the first product listed.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Products page, click on '{name}', and report its full description.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the Categories page and report how many categories are displayed.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Products page and report the price of the cheapest product visible on the first page.", ["navigate_by_route", "extract_by_route"]),
        ],
        "medium": [
            ("Navigate to the Products page, filter by category '{cat_val}', sort by price ascending, and report the name and price of the cheapest product.", ["navigate_by_route", "filter_by_dropdown", "sort_by_ranking", "extract_by_route"]),
            ("Navigate to the Products page, search for '{name}', then search for '{name2}', and tell me which one is cheaper and by how much.", ["navigate_by_route", "search_by_query", "extract_by_route", "compare_from_table"]),
            ("Navigate to the Products page, filter by category '{cat_val}', and report how many products are in that category.", ["navigate_by_route", "filter_by_dropdown", "extract_by_route"]),
            ("Navigate to the Products page, sort by rating descending, and report the name and rating of the top-rated product.", ["navigate_by_route", "sort_by_ranking", "extract_by_route"]),
            ("Navigate to the Products page, filter by category '{cat_val}', sort by rating descending, and report the name of the top-rated product in that category.", ["navigate_by_route", "filter_by_dropdown", "sort_by_ranking", "extract_by_route"]),
            ("Navigate to the Products page, search for '{name}', open its detail page, and report how many reviews it has.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the Products page, filter by category '{cat_val}', and report the average price of products in that category.", ["navigate_by_route", "filter_by_dropdown", "extract_by_route"]),
            ("Navigate to the Products page, search for '{name}', and report its category and stock quantity.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
        ],
        "hard": [
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Products, search for '{name}', click 'Add to Cart', then navigate to the Cart page and report the cart total.", ["authenticate_by_form", "navigate_by_route", "search_by_query", "submit_by_form", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Products, search for '{name}', click 'Add to Wishlist', then navigate to the Wishlist page and confirm '{name}' appears. Report yes or no.", ["authenticate_by_form", "navigate_by_route", "search_by_query", "save_by_toggle", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Products, add '{name}' to the cart, then add '{name2}' to the cart. Navigate to Cart and report the total number of items and the order total.", ["authenticate_by_form", "navigate_by_route", "search_by_query", "submit_by_form", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Products, search for '{name}', open its detail page, submit a 5-star review titled 'Great product' with body 'Highly recommend', then confirm the review appears on the product page. Report yes or no.", ["authenticate_by_form", "navigate_by_route", "search_by_query", "create_from_free_text", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Cart, note the current total. Then navigate to Products, add '{name}' to cart, return to Cart, and report the new total.", ["authenticate_by_form", "navigate_by_route", "extract_by_route", "search_by_query", "submit_by_form"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Products, add '{name}' to cart, navigate to Cart, proceed to Checkout, fill in shipping info, and report the final order total including shipping.", ["authenticate_by_form", "navigate_by_route", "search_by_query", "submit_by_form", "extract_by_route"]),
        ],
    },

    "crowdfunding-donations": {
        "easy": [
            ("Navigate to the Campaigns page and report how many campaigns are listed.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Campaigns page, filter by category '{cat_val}', and report how many campaigns are shown.", ["navigate_by_route", "filter_by_dropdown", "extract_by_route"]),
            ("Navigate to the Campaigns page, search for '{name}', and report its current funding amount.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the Campaigns page and report the name of the campaign with the most backers visible on the first page.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Campaigns page, click on '{name}', and report its funding goal.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the Campaigns page and report how many campaigns are marked as 'fully funded'.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Campaigns page, click on '{name}', and report how many backers it has.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the Campaigns page and report the category of the first campaign listed.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Campaigns page, click on '{name}', and report the number of days remaining.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the Campaigns page, sort by newest first, and report the name of the most recently created campaign.", ["navigate_by_route", "sort_by_ranking", "extract_by_route"]),
        ],
        "medium": [
            ("Navigate to the Campaigns page, filter by category '{cat_val}', filter by status 'active', and report how many campaigns match both filters.", ["navigate_by_route", "filter_by_dropdown", "extract_by_route"]),
            ("Navigate to the Campaigns page, search for '{name}', and report both the amount raised and the percentage of its goal reached.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the Campaigns page, filter by status 'active', sort by backer count descending, and report the name of the campaign with the most backers.", ["navigate_by_route", "filter_by_dropdown", "sort_by_ranking", "extract_by_route"]),
            ("Navigate to the Campaigns page, search for '{name}' and then '{name2}', and tell me which one is closer to its funding goal as a percentage.", ["navigate_by_route", "search_by_query", "extract_by_route", "compare_from_table"]),
            ("Navigate to the Campaigns page, click on '{name}', and list all available reward tiers with their pledge amounts.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the Campaigns page, filter by category '{cat_val}', sort by amount raised descending, and report the name and amount of the top-funded campaign.", ["navigate_by_route", "filter_by_dropdown", "sort_by_ranking", "extract_by_route"]),
            ("Navigate to the Campaigns page, filter by status 'fully funded', and report the total number of backers across all fully funded campaigns.", ["navigate_by_route", "filter_by_dropdown", "extract_by_route"]),
            ("Navigate to the Campaigns page, search for '{name}', and report its creator name and campaign end date.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
        ],
        "hard": [
            ("Log in as '{user}' (password: '{pwd}'). Navigate to the Campaigns page, click on '{name}', pledge $50, then check the campaign page again and report the new backer count.", ["authenticate_by_form", "navigate_by_route", "search_by_query", "submit_by_form", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Create Campaign, fill in title 'Community Garden Project', category 'community', goal $5000, click submit, then navigate to Campaigns and confirm 'Community Garden Project' appears. Report yes or no.", ["authenticate_by_form", "navigate_by_route", "create_from_free_text", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to your Dashboard, note how many campaigns you have backed. Then navigate to Campaigns, pledge $25 to '{name}', return to Dashboard, and report the new backed count.", ["authenticate_by_form", "navigate_by_route", "extract_by_route", "submit_by_form"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Campaigns, click on '{name}', select the second reward tier, pledge the required amount, then verify your pledge appears under 'My Pledges'. Report the reward tier name.", ["authenticate_by_form", "navigate_by_route", "search_by_query", "submit_by_form", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Create Campaign, create a campaign titled 'Tech for Good' with a $10000 goal, then navigate to Campaigns, search for 'Tech for Good', and report its current funding percentage.", ["authenticate_by_form", "navigate_by_route", "create_from_free_text", "search_by_query", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Campaigns, pledge $100 to '{name}', then navigate to your Dashboard and report the total amount you have pledged across all campaigns.", ["authenticate_by_form", "navigate_by_route", "submit_by_form", "extract_by_route"]),
        ],
    },

    # ===== PRODUCTIVITY =====
    "crm": {
        "easy": [
            ("Navigate to the Deals page and report how many deals are listed in the pipeline.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Dashboard and report the current win rate percentage.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Companies page and report how many companies are listed.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Contacts page, search for '{name}', and report their email address.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the Contacts page and report the total number of contacts.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Deals page and report the name of the deal with the highest value visible on the first page.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Activities page and report how many activities are logged.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Dashboard and report the total pipeline value.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Contacts page, search for '{name}', and report their job title.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the Companies page and report the name of the first company listed.", ["navigate_by_route", "extract_by_route"]),
        ],
        "medium": [
            ("Navigate to the Deals page, filter by stage '{cat_val}', and report the total value of all deals in that stage.", ["navigate_by_route", "filter_by_dropdown", "extract_by_route"]),
            ("Navigate to the Contacts page, search for '{name}', and list all contacts at that company with their names and titles.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the Deals page, sort by value descending, and report the name, stage, and value of the highest-value deal.", ["navigate_by_route", "sort_by_ranking", "extract_by_route"]),
            ("Navigate to the Activities page, filter by type 'call', and report how many call activities are logged.", ["navigate_by_route", "filter_by_dropdown", "extract_by_route"]),
            ("Navigate to the Deals page, filter by stage 'closed-won', and report the total revenue from closed-won deals.", ["navigate_by_route", "filter_by_dropdown", "extract_by_route"]),
            ("Navigate to the Deals page, filter by stage '{cat_val}', sort by value descending, and report the name of the top deal in that stage.", ["navigate_by_route", "filter_by_dropdown", "sort_by_ranking", "extract_by_route"]),
            ("Navigate to the Activities page, filter by type 'email', sort by date descending, and report the subject and date of the most recent email activity.", ["navigate_by_route", "filter_by_dropdown", "sort_by_ranking", "extract_by_route"]),
            ("Navigate to the Companies page, search for '{name}', and report how many contacts and deals are associated with that company.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
        ],
        "hard": [
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Deals, click 'New Deal', create a deal called 'Enterprise Upgrade' for company '{name}' worth $75,000 in stage 'prospecting', then navigate to Deals and confirm 'Enterprise Upgrade' appears. Report yes or no.", ["authenticate_by_form", "navigate_by_route", "create_from_free_text", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Activities, click 'Log Activity', create a call activity for '{name}' with notes 'Follow-up on proposal', then navigate to Activities and confirm the new call appears. Report the activity date.", ["authenticate_by_form", "navigate_by_route", "create_from_free_text", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Deals, search for '{name}', change its stage to 'closed-won', then navigate to the Dashboard and report the new win rate.", ["authenticate_by_form", "navigate_by_route", "search_by_query", "edit_by_form", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Contacts, click 'New Contact', create a contact named 'Jane Smith' at company '{name}' with title 'VP Sales', then navigate to Contacts, search for 'Jane Smith', and confirm she appears. Report yes or no.", ["authenticate_by_form", "navigate_by_route", "create_from_free_text", "search_by_query", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Deals, note the current pipeline total. Then create a new deal worth $50,000, return to Deals, and report the new pipeline total.", ["authenticate_by_form", "navigate_by_route", "extract_by_route", "create_from_free_text"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Companies, search for '{name}', click 'Add Deal', create a deal worth $30,000 in stage 'negotiation', then navigate to Deals, filter by stage 'negotiation', and confirm the new deal appears. Report the total number of deals in negotiation.", ["authenticate_by_form", "navigate_by_route", "search_by_query", "create_from_free_text", "filter_by_dropdown", "extract_by_route"]),
        ],
    },

    "documents": {
        "easy": [
            ("Navigate to the Documents page and report how many documents are listed.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Starred section and report how many starred documents there are.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Trash section and report how many documents are in the trash.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Folders view and list all folder names.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Documents page, search for '{name}', and report its title.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the Documents page and report the title of the most recently modified document.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Documents page, click on '{name}', and report its owner.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the Documents page and report how many documents are shared with you.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Documents page, click on '{name}', and report when it was last modified.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the Folders view, open the first folder, and report how many documents are inside.", ["navigate_by_route", "extract_by_route"]),
        ],
        "medium": [
            ("Navigate to the Documents page, search for '{name}', open it, and report the owner name and number of collaborators.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the Documents page, sort alphabetically by title, and report the title of the first document.", ["navigate_by_route", "sort_by_ranking", "extract_by_route"]),
            ("Navigate to the Documents page, search for '{name}', open it, and report how many revisions it has.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the Documents page, filter by owner to show only documents owned by user '{name}', and report how many there are.", ["navigate_by_route", "filter_by_dropdown", "extract_by_route"]),
            ("Navigate to the Documents page, sort by last modified date descending, and report the title and date of the most recently modified document.", ["navigate_by_route", "sort_by_ranking", "extract_by_route"]),
            ("Navigate to the Documents page, search for '{name}', open it, and list all collaborator names.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the Folders view, open each folder, and report which folder contains the most documents and how many.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Documents page, filter by type '{cat_val}', and report how many documents match.", ["navigate_by_route", "filter_by_dropdown", "extract_by_route"]),
        ],
        "hard": [
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Documents, search for '{name}', click the Star button, then navigate to the Starred section and confirm '{name}' appears. Report yes or no.", ["authenticate_by_form", "navigate_by_route", "search_by_query", "save_by_toggle", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Documents, click 'New Document', title it 'Meeting Notes', click save, then navigate to Documents and confirm 'Meeting Notes' appears in the list. Report yes or no.", ["authenticate_by_form", "navigate_by_route", "create_from_free_text", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Documents, search for '{name}', open it, click 'Share', add user ID 3 as an editor, then confirm the collaborator list includes user ID 3. Report the total number of collaborators.", ["authenticate_by_form", "navigate_by_route", "search_by_query", "submit_by_form", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Documents, search for '{name}', click 'Move to Trash', then navigate to the Documents page and confirm '{name}' no longer appears. Report the new document count.", ["authenticate_by_form", "navigate_by_route", "search_by_query", "delete_from_table", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Documents, note the total count. Then click 'New Document', title it 'Weekly Report', save it, return to Documents, and report the new total count.", ["authenticate_by_form", "navigate_by_route", "extract_by_route", "create_from_free_text"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Documents, search for '{name}', open it, click 'Rename', change the title to 'Updated Report', then search for 'Updated Report' and confirm it exists. Report yes or no.", ["authenticate_by_form", "navigate_by_route", "search_by_query", "edit_by_form", "extract_by_route"]),
        ],
    },

    # ===== EDUCATION =====
    "course-sites-classrooms": {
        "easy": [
            ("Navigate to the Course Catalog and report how many courses are listed.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Course Catalog, search for '{name}', and report the instructor name.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the Course Catalog, filter by department '{cat_val}', and report how many courses are shown.", ["navigate_by_route", "filter_by_dropdown", "extract_by_route"]),
            ("Navigate to the Course Catalog and report the total number of enrolled students shown across all courses.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Course Catalog, click on the first course listed, and report the course description.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Course Catalog, search for '{name}', and report how many students are enrolled in it.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the Course Catalog and report the name of the first course listed.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Course Catalog, click on '{name}', and report the number of assignments listed.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
        ],
        "medium": [
            ("Navigate to the Course Catalog, click on '{name}', open the Gradebook tab, and report the name of the student with the highest grade.", ["navigate_by_route", "search_by_query", "sort_by_ranking", "extract_by_route"]),
            ("Navigate to the Course Catalog, click on '{name}', open the Assignments tab, and report how many assignments have a due date this month.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the Course Catalog, click on '{name}', open the Gradebook tab, sort by grade descending, and report the top student's name and grade.", ["navigate_by_route", "search_by_query", "sort_by_ranking", "extract_by_route"]),
            ("Navigate to the Course Catalog, click on '{name}', open the Discussions tab, and report how many discussion threads exist and the title of the first one.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the Course Catalog, filter by department '{cat_val}', sort by enrollment count descending, and report the name of the most enrolled course.", ["navigate_by_route", "filter_by_dropdown", "sort_by_ranking", "extract_by_route"]),
            ("Navigate to the Course Catalog, click on '{name}', open the Assignments tab, and report the title and due date of the next upcoming assignment.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the Course Catalog, click on '{name}', open the Gradebook tab, and report the class average grade.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the Course Catalog, search for '{name}', and report the instructor, enrollment count, and department.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
        ],
        "hard": [
            ("Log in as '{user}' (password: '{pwd}'). Navigate to the Course Catalog, click on '{name}', open Discussions, click 'New Post', title it 'Study Group for Finals' with body 'Who wants to join?', submit, then confirm the post appears. Report yes or no.", ["authenticate_by_form", "navigate_by_route", "search_by_query", "create_from_free_text", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to the Course Catalog, click on '{name}', open Discussions, open the first thread, click Reply, type 'I agree with this point', submit, then confirm the reply count increased. Report the new reply count.", ["authenticate_by_form", "navigate_by_route", "search_by_query", "create_from_free_text", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to the Course Catalog, click on '{name}', open the Assignments tab, submit a file for the first assignment, then confirm the submission status changed to 'submitted'. Report yes or no.", ["authenticate_by_form", "navigate_by_route", "search_by_query", "submit_by_form", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to the Course Catalog, click on '{name}', open the Gradebook tab, note the class average, then navigate to Assignments, submit a grade of 95 for the first student on the first assignment, return to Gradebook, and report the new class average.", ["authenticate_by_form", "navigate_by_route", "search_by_query", "extract_by_route", "submit_by_form"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to the Course Catalog, click on '{name}', open Discussions, note the thread count. Then create a new post titled 'Exam Prep', return to the Discussions list, and report the new thread count.", ["authenticate_by_form", "navigate_by_route", "search_by_query", "create_from_free_text", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to the Course Catalog, click 'Enroll' on '{name}', then navigate to your Dashboard and confirm '{name}' appears under 'My Courses'. Report yes or no.", ["authenticate_by_form", "navigate_by_route", "search_by_query", "submit_by_form", "extract_by_route"]),
        ],
    },

    "conference-review-submission": {
        "easy": [
            ("Navigate to the Papers page and report how many papers are listed.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Dashboard and report the acceptance rate shown.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Papers page, filter by status 'accepted', and report how many accepted papers there are.", ["navigate_by_route", "filter_by_dropdown", "extract_by_route"]),
            ("Navigate to the Papers page, search for '{name}', and report its title.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the Papers page and report the title of the first paper listed.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Dashboard and report the total number of reviews submitted.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Papers page, search for '{name}', and report the number of authors listed.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the Papers page, filter by status 'rejected', and report how many rejected papers there are.", ["navigate_by_route", "filter_by_dropdown", "extract_by_route"]),
        ],
        "medium": [
            ("Navigate to the Papers page, filter by status 'accepted', and report the average review score of accepted papers. Then filter by 'rejected' and report their average. Which group scored higher?", ["navigate_by_route", "filter_by_dropdown", "extract_by_route"]),
            ("Navigate to the Papers page, sort by review score descending, and report the title and score of the top-ranked paper.", ["navigate_by_route", "sort_by_ranking", "extract_by_route"]),
            ("Navigate to the Papers page, search for '{name}', and report how many papers list that person as an author.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the Papers page, filter to show papers with review score above 7, and report how many there are.", ["navigate_by_route", "filter_by_dropdown", "extract_by_route"]),
            ("Navigate to the Papers page, search for '{name}', open it, and report all reviewer scores and the average score.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the Papers page, filter by status 'under review', sort by submission date, and report the title of the oldest paper still under review.", ["navigate_by_route", "filter_by_dropdown", "sort_by_ranking", "extract_by_route"]),
            ("Navigate to the Papers page, sort by review score descending, and report the titles of the top 3 papers.", ["navigate_by_route", "sort_by_ranking", "extract_by_route"]),
            ("Navigate to the Papers page, search for '{name}', and report its status, review score, and number of reviews.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
        ],
        "hard": [
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Papers, click on the first paper, click 'Submit Review', enter a score of 7 and comments 'Well-written paper with strong results', submit, then confirm the review appears on the paper page. Report the new review count.", ["authenticate_by_form", "navigate_by_route", "submit_by_form", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Papers, click on '{name}', click 'Bid', select 'willing to review', submit, then navigate to your Assignments page and confirm the bid appears. Report yes or no.", ["authenticate_by_form", "navigate_by_route", "search_by_query", "submit_by_form", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Submit Paper, fill in title 'A New Approach to Optimization', add yourself as author, upload a placeholder, submit, then navigate to Papers and confirm the new paper appears. Report its assigned paper ID.", ["authenticate_by_form", "navigate_by_route", "create_from_free_text", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Papers, search for '{name}', open it, note the current average review score. Then submit a review with score 9, and report the new average review score.", ["authenticate_by_form", "navigate_by_route", "search_by_query", "extract_by_route", "submit_by_form"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to your Assignments page, report how many papers are assigned to you. Then navigate to the first assigned paper and submit a review with score 6 and comments 'Needs revision'. Report the paper title.", ["authenticate_by_form", "navigate_by_route", "extract_by_route", "submit_by_form"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Papers, filter by status 'under review', open the first one, submit a review with score 8 and comments 'Accept with minor revisions', then confirm the review count for that paper increased. Report the new count.", ["authenticate_by_form", "navigate_by_route", "filter_by_dropdown", "submit_by_form", "extract_by_route"]),
        ],
    },

    # ===== SEARCH & REFERENCE =====
    "dictionaries-language-tools": {
        "easy": [
            ("Navigate to the Home page and report the word of the day.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Search page, look up the word '{name}', and report its definition.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the Browse page, click on the letter 'S', and report how many words are listed.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Search page, look up '{name}', and report its part of speech.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the Home page and report how many total words are in the dictionary.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Search page, look up '{name}', and report its pronunciation (IPA).", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the Browse page and report how many letters of the alphabet have words listed.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Search page, look up '{name}', and report the number of definitions shown.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
        ],
        "medium": [
            ("Navigate to the Browse page, filter by part of speech 'noun', and report how many nouns are in the dictionary.", ["navigate_by_route", "filter_by_dropdown", "extract_by_route"]),
            ("Navigate to the Search page, look up '{name}', and list all synonyms shown on the word page.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the Search page, look up '{name}', and report the etymology section text.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the Browse page, filter by part of speech 'verb', and report the first verb listed alphabetically.", ["navigate_by_route", "filter_by_dropdown", "sort_by_ranking", "extract_by_route"]),
            ("Navigate to the Browse page, click on each letter, and report which letter has the most words.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Search page, look up '{name}', and report all example sentences listed.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the Browse page, filter by part of speech '{cat_val}', sort alphabetically, and report the last word listed.", ["navigate_by_route", "filter_by_dropdown", "sort_by_ranking", "extract_by_route"]),
            ("Navigate to the Search page, look up '{name}', and tell me whether it has both synonyms and antonyms listed. Report yes or no.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
        ],
        "hard": [
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Search, look up '{name}', click 'Save to Vocabulary', then navigate to your Vocabulary page and confirm '{name}' appears. Report yes or no.", ["authenticate_by_form", "navigate_by_route", "search_by_query", "save_by_toggle", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Search, save the word '{name}' to your vocabulary, then save '{name2}', then navigate to your Vocabulary page and report how many saved words you have.", ["authenticate_by_form", "navigate_by_route", "search_by_query", "save_by_toggle", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to your Vocabulary page, note the current count. Then navigate to Search, save '{name}', return to Vocabulary, and report the new count.", ["authenticate_by_form", "navigate_by_route", "extract_by_route", "search_by_query", "save_by_toggle"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Search, look up '{name}', click 'Save to Vocabulary', then navigate to Vocabulary, remove '{name}' from the list, and confirm it no longer appears. Report the remaining count.", ["authenticate_by_form", "navigate_by_route", "search_by_query", "save_by_toggle", "delete_from_table", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Search, look up '{name}', add a custom note 'Remember for exam', then navigate back to the word page and confirm the note appears. Report yes or no.", ["authenticate_by_form", "navigate_by_route", "search_by_query", "create_from_free_text", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to your Vocabulary page, report the current word count. Then look up and save three different words, return to Vocabulary, and report the new count.", ["authenticate_by_form", "navigate_by_route", "extract_by_route", "search_by_query", "save_by_toggle"]),
        ],
    },

    "documentation-api-docs": {
        "easy": [
            ("Navigate to the Documentation index page and report how many documentation pages are listed.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Documentation index page and list all top-level section names.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the API Reference page, filter by method 'GET', and report how many GET endpoints are listed.", ["navigate_by_route", "filter_by_dropdown", "extract_by_route"]),
            ("Navigate to the Authentication page and report the first key concept mentioned.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Changelog page and report the version number of the most recent entry.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the API Reference page and report the total number of endpoints listed.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Getting Started page and report the first step described.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the API Reference page and report the name of the first endpoint listed.", ["navigate_by_route", "extract_by_route"]),
        ],
        "medium": [
            ("Navigate to the API Reference page, filter by method 'POST', and report how many POST endpoints are listed.", ["navigate_by_route", "filter_by_dropdown", "extract_by_route"]),
            ("Navigate to the Documentation index, search for '{name}', and report the titles of all pages that mention it.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the API Reference page, find the endpoint for creating a resource, and list all required parameters.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Documentation index, filter by tag '{cat_val}', and report how many pages match.", ["navigate_by_route", "filter_by_dropdown", "extract_by_route"]),
            ("Navigate to the Changelog page, sort by date descending, and report the version and description of the two most recent entries.", ["navigate_by_route", "sort_by_ranking", "extract_by_route"]),
            ("Navigate to the API Reference page, search for '{name}', and report the HTTP method, path, and description of the matching endpoint.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the API Reference page, filter by method 'DELETE', and report the names of all DELETE endpoints.", ["navigate_by_route", "filter_by_dropdown", "extract_by_route"]),
            ("Navigate to the Documentation index, search for '{name}', open the first result, and report the full page content summary.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
        ],
        "hard": [
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Documentation, open the Deployments page, click 'Bookmark', then navigate to your Bookmarks page and confirm 'Deployments' appears. Report yes or no.", ["authenticate_by_form", "navigate_by_route", "save_by_toggle", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Documentation, bookmark three different pages, then navigate to your Bookmarks page and report the total number of bookmarks.", ["authenticate_by_form", "navigate_by_route", "save_by_toggle", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Documentation, open '{name}', click 'Bookmark', then navigate to Bookmarks, remove it, and confirm it no longer appears. Report the remaining bookmark count.", ["authenticate_by_form", "navigate_by_route", "save_by_toggle", "delete_from_table", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to your Bookmarks page, note the current count. Then navigate to Documentation, bookmark a new page, return to Bookmarks, and report the new count.", ["authenticate_by_form", "navigate_by_route", "extract_by_route", "save_by_toggle"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to the API Reference page, open the first endpoint, click 'Try It', fill in the required parameters with test values, submit, and report the response status code.", ["authenticate_by_form", "navigate_by_route", "submit_by_form", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Documentation, search for '{name}', open the page, add a comment 'Needs clarification on parameters', then confirm the comment appears. Report yes or no.", ["authenticate_by_form", "navigate_by_route", "search_by_query", "create_from_free_text", "extract_by_route"]),
        ],
    },

    "comparison-aggregators": {
        "easy": [
            ("Navigate to the Phones page and report how many phones are in the database.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Phones page and report how many distinct brands are shown in the brand filter.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Phones page, search for '{name}', and report its screen size.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the Phones page, filter by brand 'Samsung', and report how many Samsung phones are listed.", ["navigate_by_route", "filter_by_dropdown", "extract_by_route"]),
            ("Navigate to the Phones page, search for '{name}', and report its battery capacity in mAh.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the Phones page, search for '{name}', and report its operating system.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
            ("Navigate to the Phones page and report the name of the first phone listed.", ["navigate_by_route", "extract_by_route"]),
            ("Navigate to the Phones page, search for '{name}', and report its price.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
        ],
        "medium": [
            ("Navigate to the Phones page, filter by OS 'Android', sort by battery capacity descending, and report the name and battery size of the phone with the biggest battery.", ["navigate_by_route", "filter_by_dropdown", "sort_by_ranking", "extract_by_route"]),
            ("Navigate to the Phones page, search for '{name}' and '{name2}', and report which one has a higher camera megapixel count.", ["navigate_by_route", "search_by_query", "compare_from_table", "extract_by_route"]),
            ("Navigate to the Phones page, filter to show phones with battery 5000 mAh or more, and report how many match.", ["navigate_by_route", "filter_by_dropdown", "extract_by_route"]),
            ("Navigate to the Phones page, filter by brand '{cat_val}', and report how many phones that brand has.", ["navigate_by_route", "filter_by_dropdown", "extract_by_route"]),
            ("Navigate to the Phones page, sort by price ascending, and report the name and price of the cheapest phone.", ["navigate_by_route", "sort_by_ranking", "extract_by_route"]),
            ("Navigate to the Phones page, filter by OS '{cat_val}', sort by price descending, and report the name of the most expensive phone with that OS.", ["navigate_by_route", "filter_by_dropdown", "sort_by_ranking", "extract_by_route"]),
            ("Navigate to the Phones page, search for '{name}' and '{name2}', compare their specs side by side, and report which has more RAM.", ["navigate_by_route", "search_by_query", "compare_from_table", "extract_by_route"]),
            ("Navigate to the Phones page, filter by brand '{cat_val}', sort by screen size descending, and report the name of the phone with the largest screen.", ["navigate_by_route", "filter_by_dropdown", "sort_by_ranking", "extract_by_route"]),
        ],
        "hard": [
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Phones, search for '{name}', click 'Add to Favorites', then navigate to your Favorites page and confirm '{name}' appears. Report yes or no.", ["authenticate_by_form", "navigate_by_route", "search_by_query", "save_by_toggle", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Phones, add '{name}' and '{name2}' to your Compare list, then navigate to the Compare page and report which phone has the better camera resolution.", ["authenticate_by_form", "navigate_by_route", "search_by_query", "save_by_toggle", "compare_from_table", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to your Favorites page, note the current count. Then navigate to Phones, add '{name}' to Favorites, return to Favorites, and report the new count.", ["authenticate_by_form", "navigate_by_route", "extract_by_route", "search_by_query", "save_by_toggle"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Phones, add '{name}' to Favorites, then navigate to Favorites, remove it, and confirm the Favorites list is empty. Report yes or no.", ["authenticate_by_form", "navigate_by_route", "search_by_query", "save_by_toggle", "delete_from_table", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Phones, search for '{name}', click 'Write Review', submit a review with rating 4 and text 'Great value for money', then confirm the review appears on the phone page. Report the new review count.", ["authenticate_by_form", "navigate_by_route", "search_by_query", "create_from_free_text", "extract_by_route"]),
            ("Log in as '{user}' (password: '{pwd}'). Navigate to Phones, add '{name}', '{name2}', and a third phone to Compare, then navigate to Compare and report which of the three has the largest battery.", ["authenticate_by_form", "navigate_by_route", "search_by_query", "save_by_toggle", "compare_from_table", "extract_by_route"]),
        ],
    },
}

# Generic fallback for sites without specific templates
GENERIC_TEMPLATES = {
    "easy": [
        ("Navigate to the main listing page of the {site} site and report how many items are displayed.", ["navigate_by_route", "extract_by_route"]),
        ("Navigate to the main listing page of the {site} site and report the name of the first item listed.", ["navigate_by_route", "extract_by_route"]),
        ("Navigate to the {site} site, search for '{name}', and report whether it exists. Answer yes or no.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
        ("Navigate to the {site} site, click on the '{cat_val}' category, and report how many items are shown.", ["navigate_by_route", "filter_by_dropdown", "extract_by_route"]),
        ("Navigate to the {site} site, search for '{name}', and report its title or name as displayed.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
        ("Navigate to the {site} site and list all categories or sections available in the navigation.", ["navigate_by_route", "extract_by_route"]),
        ("Navigate to the {site} site, click on '{name}', and report the first detail field shown on its page.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
        ("Navigate to the {site} site and report the title of the most recently updated item on the main page.", ["navigate_by_route", "extract_by_route"]),
    ],
    "medium": [
        ("Navigate to the {site} site, filter by {cat_key} '{cat_val}', and report how many items match.", ["navigate_by_route", "filter_by_dropdown", "extract_by_route"]),
        ("Navigate to the {site} site, search for '{name}', open its detail page, and list all fields displayed.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
        ("Navigate to the {site} site, sort the listing alphabetically by name, and report the name of the first item.", ["navigate_by_route", "sort_by_ranking", "extract_by_route"]),
        ("Navigate to the {site} site, search for '{name}' and then '{name2}', and report which one appears first in the default listing.", ["navigate_by_route", "search_by_query", "compare_from_table", "extract_by_route"]),
        ("Navigate to the {site} site, filter by {cat_key} '{cat_val}', sort alphabetically, and report the last item listed.", ["navigate_by_route", "filter_by_dropdown", "sort_by_ranking", "extract_by_route"]),
        ("Navigate to the {site} site, search for '{name}', and report all {cat_key} values associated with it.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
        ("Navigate to the {site} site, filter by {cat_key} '{cat_val}', and report the total count and the name of the first matching item.", ["navigate_by_route", "filter_by_dropdown", "extract_by_route"]),
        ("Navigate to the {site} site, search for '{name}', open its page, and report when it was last updated.", ["navigate_by_route", "search_by_query", "extract_by_route"]),
    ],
    "hard": [
        ("Log in as '{user}' (password: '{pwd}') on the {site} site. Navigate to '{name}', click the save/favorite button, then navigate to your saved items page and confirm '{name}' appears. Report yes or no.", ["authenticate_by_form", "navigate_by_route", "search_by_query", "save_by_toggle", "extract_by_route"]),
        ("Log in as '{user}' (password: '{pwd}') on the {site} site. Navigate to the create/new page, fill in a title of 'Test Entry' and submit, then navigate to the main listing and confirm 'Test Entry' appears. Report yes or no.", ["authenticate_by_form", "navigate_by_route", "create_from_free_text", "extract_by_route"]),
        ("Log in as '{user}' (password: '{pwd}') on the {site} site. Navigate to '{name}', click edit, change the {cat_key} to '{cat_val}', save, then reopen '{name}' and confirm the {cat_key} shows '{cat_val}'. Report yes or no.", ["authenticate_by_form", "navigate_by_route", "search_by_query", "edit_by_form", "extract_by_route"]),
        ("Log in as '{user}' (password: '{pwd}') on the {site} site. Navigate to your profile or dashboard and report the number of items associated with your account.", ["authenticate_by_form", "navigate_by_route", "extract_by_route"]),
        ("Log in as '{user}' (password: '{pwd}') on the {site} site. Navigate to the main listing, note the total count. Then create a new item, return to the listing, and report the new total count.", ["authenticate_by_form", "navigate_by_route", "extract_by_route", "create_from_free_text"]),
        ("Log in as '{user}' (password: '{pwd}') on the {site} site. Navigate to '{name}', click delete, confirm the deletion, then navigate to the main listing and confirm '{name}' no longer appears. Report the new total count.", ["authenticate_by_form", "navigate_by_route", "search_by_query", "delete_from_table", "extract_by_route"]),
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
