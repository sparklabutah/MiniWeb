#!/usr/bin/env python3
"""
Data preparation script for the MiniWeb stock-crypto site.

Fetches real market data:
- Crypto: CoinGecko free API (top 50 coins by market cap)
- Stocks: Hardcoded realistic data for ~150 major US-listed companies
  (mirrors real-world tickers, sectors, exchanges, and approximate price ranges)

Outputs: assets.json, price_history.json, sectors.json, users.json, watchlists.json
"""

import json
import math
import pathlib
import random
import time
from datetime import datetime, timedelta

import requests

DATA_DIR = pathlib.Path("/scratch/general/vast/u1653932/data_sources/stock-crypto-prices")

# ---------------------------------------------------------------------------
# 1. STOCK DEFINITIONS  (150 major US stocks with realistic data)
# ---------------------------------------------------------------------------

STOCK_DEFS = [
    # Technology
    {"symbol": "AAPL", "name": "Apple Inc.", "sector": "Technology", "exchange": "NASDAQ", "price": 195.0, "mcap": 3010e9, "pe": 30.5, "div": 0.52, "desc": "Consumer electronics and software giant known for iPhone, Mac, and services ecosystem"},
    {"symbol": "MSFT", "name": "Microsoft Corp.", "sector": "Technology", "exchange": "NASDAQ", "price": 420.0, "mcap": 3120e9, "pe": 36.8, "div": 0.72, "desc": "Enterprise software leader in cloud computing, AI, and productivity tools"},
    {"symbol": "GOOGL", "name": "Alphabet Inc.", "sector": "Technology", "exchange": "NASDAQ", "price": 175.0, "mcap": 2180e9, "pe": 26.4, "div": 0.0, "desc": "Internet search and advertising giant leading in cloud and AI research"},
    {"symbol": "AMZN", "name": "Amazon.com Inc.", "sector": "Technology", "exchange": "NASDAQ", "price": 185.0, "mcap": 1930e9, "pe": 60.2, "div": 0.0, "desc": "E-commerce and cloud computing powerhouse with AWS leading cloud infrastructure"},
    {"symbol": "NVDA", "name": "NVIDIA Corp.", "sector": "Technology", "exchange": "NASDAQ", "price": 130.0, "mcap": 3200e9, "pe": 68.5, "div": 0.03, "desc": "Leading GPU manufacturer powering AI training and data center acceleration"},
    {"symbol": "META", "name": "Meta Platforms Inc.", "sector": "Technology", "exchange": "NASDAQ", "price": 510.0, "mcap": 1310e9, "pe": 27.9, "div": 0.38, "desc": "Social media conglomerate with Facebook, Instagram, WhatsApp, and AI platforms"},
    {"symbol": "TSM", "name": "Taiwan Semiconductor", "sector": "Technology", "exchange": "NYSE", "price": 165.0, "mcap": 850e9, "pe": 28.3, "div": 1.25, "desc": "World's largest semiconductor foundry manufacturing chips for global tech companies"},
    {"symbol": "AVGO", "name": "Broadcom Inc.", "sector": "Technology", "exchange": "NASDAQ", "price": 175.0, "mcap": 810e9, "pe": 35.2, "div": 1.40, "desc": "Semiconductor and infrastructure software company serving enterprise and cloud markets"},
    {"symbol": "ORCL", "name": "Oracle Corp.", "sector": "Technology", "exchange": "NYSE", "price": 175.0, "mcap": 480e9, "pe": 38.5, "div": 1.10, "desc": "Enterprise database and cloud infrastructure provider for business applications"},
    {"symbol": "CRM", "name": "Salesforce Inc.", "sector": "Technology", "exchange": "NYSE", "price": 265.0, "mcap": 257e9, "pe": 42.1, "div": 0.56, "desc": "Cloud-based CRM platform leader for sales, service, and marketing automation"},
    {"symbol": "AMD", "name": "Advanced Micro Devices", "sector": "Technology", "exchange": "NASDAQ", "price": 158.0, "mcap": 255e9, "pe": 44.8, "div": 0.0, "desc": "Semiconductor company competing in CPUs, GPUs, and data center chips"},
    {"symbol": "ADBE", "name": "Adobe Inc.", "sector": "Technology", "exchange": "NASDAQ", "price": 485.0, "mcap": 216e9, "pe": 38.2, "div": 0.0, "desc": "Creative and digital experience software maker with Photoshop and Creative Cloud"},
    {"symbol": "INTC", "name": "Intel Corp.", "sector": "Technology", "exchange": "NASDAQ", "price": 31.0, "mcap": 132e9, "pe": 15.2, "div": 0.50, "desc": "Semiconductor manufacturer rebuilding its foundry business and CPU leadership"},
    {"symbol": "CSCO", "name": "Cisco Systems Inc.", "sector": "Technology", "exchange": "NASDAQ", "price": 52.0, "mcap": 213e9, "pe": 15.8, "div": 3.02, "desc": "Networking equipment and software provider for enterprise and service provider markets"},
    {"symbol": "IBM", "name": "International Business Machines", "sector": "Technology", "exchange": "NYSE", "price": 190.0, "mcap": 174e9, "pe": 21.5, "div": 3.50, "desc": "Enterprise IT services and hybrid cloud solutions with Red Hat integration"},
    {"symbol": "NOW", "name": "ServiceNow Inc.", "sector": "Technology", "exchange": "NYSE", "price": 790.0, "mcap": 161e9, "pe": 62.3, "div": 0.0, "desc": "Cloud-based digital workflow platform for IT service management and automation"},
    {"symbol": "QCOM", "name": "Qualcomm Inc.", "sector": "Technology", "exchange": "NASDAQ", "price": 170.0, "mcap": 190e9, "pe": 20.8, "div": 1.90, "desc": "Leading mobile chipmaker and wireless technology licensor for smartphones and IoT"},
    {"symbol": "TXN", "name": "Texas Instruments", "sector": "Technology", "exchange": "NASDAQ", "price": 175.0, "mcap": 159e9, "pe": 30.5, "div": 2.80, "desc": "Analog and embedded semiconductor manufacturer for industrial and automotive markets"},
    {"symbol": "INTU", "name": "Intuit Inc.", "sector": "Technology", "exchange": "NASDAQ", "price": 625.0, "mcap": 176e9, "pe": 52.4, "div": 0.56, "desc": "Financial software maker of TurboTax, QuickBooks, and Credit Karma platforms"},
    {"symbol": "AMAT", "name": "Applied Materials", "sector": "Technology", "exchange": "NASDAQ", "price": 195.0, "mcap": 160e9, "pe": 22.5, "div": 0.82, "desc": "Semiconductor equipment manufacturer providing chip fabrication systems"},
    {"symbol": "PANW", "name": "Palo Alto Networks", "sector": "Technology", "exchange": "NASDAQ", "price": 310.0, "mcap": 102e9, "pe": 48.7, "div": 0.0, "desc": "Cybersecurity platform company providing network security and cloud protection"},
    {"symbol": "SNPS", "name": "Synopsys Inc.", "sector": "Technology", "exchange": "NASDAQ", "price": 510.0, "mcap": 78e9, "pe": 52.1, "div": 0.0, "desc": "Electronic design automation software for semiconductor chip design"},
    {"symbol": "MU", "name": "Micron Technology", "sector": "Technology", "exchange": "NASDAQ", "price": 105.0, "mcap": 116e9, "pe": 18.5, "div": 0.46, "desc": "Memory and storage chip manufacturer producing DRAM and NAND flash"},
    {"symbol": "PLTR", "name": "Palantir Technologies", "sector": "Technology", "exchange": "NYSE", "price": 24.0, "mcap": 52e9, "pe": 72.3, "div": 0.0, "desc": "Data analytics platform for government intelligence and enterprise decision-making"},
    {"symbol": "SHOP", "name": "Shopify Inc.", "sector": "Technology", "exchange": "NYSE", "price": 78.0, "mcap": 100e9, "pe": 65.4, "div": 0.0, "desc": "E-commerce platform enabling merchants to build online stores and process payments"},

    # Healthcare
    {"symbol": "UNH", "name": "UnitedHealth Group", "sector": "Healthcare", "exchange": "NYSE", "price": 525.0, "mcap": 485e9, "pe": 20.8, "div": 1.35, "desc": "Largest US health insurer also providing pharmacy benefits and care delivery"},
    {"symbol": "JNJ", "name": "Johnson & Johnson", "sector": "Healthcare", "exchange": "NYSE", "price": 158.0, "mcap": 382e9, "pe": 18.5, "div": 2.95, "desc": "Diversified healthcare conglomerate with pharmaceuticals and medical devices"},
    {"symbol": "LLY", "name": "Eli Lilly & Co.", "sector": "Healthcare", "exchange": "NYSE", "price": 780.0, "mcap": 740e9, "pe": 82.3, "div": 0.68, "desc": "Pharmaceutical giant leading in diabetes, obesity, and Alzheimer's treatments"},
    {"symbol": "ABBV", "name": "AbbVie Inc.", "sector": "Healthcare", "exchange": "NYSE", "price": 180.0, "mcap": 318e9, "pe": 14.2, "div": 3.40, "desc": "Biopharmaceutical company with immunology and oncology drug portfolio"},
    {"symbol": "MRK", "name": "Merck & Co.", "sector": "Healthcare", "exchange": "NYSE", "price": 125.0, "mcap": 317e9, "pe": 16.8, "div": 2.35, "desc": "Global pharmaceutical company known for Keytruda cancer immunotherapy"},
    {"symbol": "PFE", "name": "Pfizer Inc.", "sector": "Healthcare", "exchange": "NYSE", "price": 28.0, "mcap": 158e9, "pe": 11.5, "div": 5.80, "desc": "Major pharmaceutical company with vaccines, oncology, and specialty care drugs"},
    {"symbol": "TMO", "name": "Thermo Fisher Scientific", "sector": "Healthcare", "exchange": "NYSE", "price": 580.0, "mcap": 224e9, "pe": 30.2, "div": 0.22, "desc": "Life sciences instruments and reagents provider serving research and diagnostics"},
    {"symbol": "ABT", "name": "Abbott Laboratories", "sector": "Healthcare", "exchange": "NYSE", "price": 112.0, "mcap": 194e9, "pe": 24.5, "div": 1.85, "desc": "Healthcare company making diagnostics, medical devices, and nutritional products"},
    {"symbol": "AMGN", "name": "Amgen Inc.", "sector": "Healthcare", "exchange": "NASDAQ", "price": 280.0, "mcap": 150e9, "pe": 18.9, "div": 3.15, "desc": "Biotechnology company developing therapies for cardiovascular and bone health"},
    {"symbol": "GILD", "name": "Gilead Sciences", "sector": "Healthcare", "exchange": "NASDAQ", "price": 82.0, "mcap": 102e9, "pe": 12.4, "div": 3.65, "desc": "Biopharmaceutical company specializing in antiviral therapies and oncology"},
    {"symbol": "ISRG", "name": "Intuitive Surgical", "sector": "Healthcare", "exchange": "NASDAQ", "price": 395.0, "mcap": 140e9, "pe": 58.7, "div": 0.0, "desc": "Robotic surgical systems maker with the da Vinci platform for minimally invasive surgery"},
    {"symbol": "BMY", "name": "Bristol-Myers Squibb", "sector": "Healthcare", "exchange": "NYSE", "price": 52.0, "mcap": 105e9, "pe": 8.5, "div": 4.30, "desc": "Biopharmaceutical company with cardiovascular, oncology, and immunology drugs"},
    {"symbol": "MDT", "name": "Medtronic PLC", "sector": "Healthcare", "exchange": "NYSE", "price": 84.0, "mcap": 112e9, "pe": 16.2, "div": 3.25, "desc": "Medical device company making cardiac, spinal, and diabetes management products"},
    {"symbol": "ZTS", "name": "Zoetis Inc.", "sector": "Healthcare", "exchange": "NYSE", "price": 180.0, "mcap": 82e9, "pe": 32.5, "div": 0.78, "desc": "Animal health pharmaceutical company with vaccines and diagnostics for livestock and pets"},
    {"symbol": "VRTX", "name": "Vertex Pharmaceuticals", "sector": "Healthcare", "exchange": "NASDAQ", "price": 420.0, "mcap": 108e9, "pe": 25.8, "div": 0.0, "desc": "Biotechnology company leading in cystic fibrosis and gene-editing therapies"},

    # Finance
    {"symbol": "JPM", "name": "JPMorgan Chase & Co.", "sector": "Finance", "exchange": "NYSE", "price": 200.0, "mcap": 580e9, "pe": 11.8, "div": 2.30, "desc": "Largest US bank by assets offering investment banking and financial services"},
    {"symbol": "V", "name": "Visa Inc.", "sector": "Finance", "exchange": "NYSE", "price": 282.0, "mcap": 555e9, "pe": 30.5, "div": 0.76, "desc": "Global payments technology company processing billions of transactions annually"},
    {"symbol": "MA", "name": "Mastercard Inc.", "sector": "Finance", "exchange": "NYSE", "price": 460.0, "mcap": 430e9, "pe": 34.2, "div": 0.56, "desc": "International payment processing network connecting consumers and financial institutions"},
    {"symbol": "BAC", "name": "Bank of America Corp.", "sector": "Finance", "exchange": "NYSE", "price": 35.0, "mcap": 280e9, "pe": 10.5, "div": 2.65, "desc": "Major US bank providing consumer banking, wealth management, and global markets"},
    {"symbol": "GS", "name": "Goldman Sachs Group", "sector": "Finance", "exchange": "NYSE", "price": 470.0, "mcap": 160e9, "pe": 14.6, "div": 2.15, "desc": "Leading global investment bank and financial services institution"},
    {"symbol": "MS", "name": "Morgan Stanley", "sector": "Finance", "exchange": "NYSE", "price": 95.0, "mcap": 155e9, "pe": 13.8, "div": 3.20, "desc": "Investment bank and wealth management firm serving institutional and retail clients"},
    {"symbol": "AXP", "name": "American Express Co.", "sector": "Finance", "exchange": "NYSE", "price": 230.0, "mcap": 168e9, "pe": 19.5, "div": 1.05, "desc": "Premium charge and credit card issuer with global merchant network and travel services"},
    {"symbol": "BLK", "name": "BlackRock Inc.", "sector": "Finance", "exchange": "NYSE", "price": 810.0, "mcap": 122e9, "pe": 22.1, "div": 2.30, "desc": "World's largest asset manager with ETFs and risk management technology"},
    {"symbol": "SPGI", "name": "S&P Global Inc.", "sector": "Finance", "exchange": "NYSE", "price": 450.0, "mcap": 140e9, "pe": 35.8, "div": 0.78, "desc": "Financial data analytics and credit ratings provider powering global capital markets"},
    {"symbol": "C", "name": "Citigroup Inc.", "sector": "Finance", "exchange": "NYSE", "price": 55.0, "mcap": 105e9, "pe": 8.2, "div": 3.80, "desc": "Diversified financial services company with global institutional and consumer banking"},
    {"symbol": "SCHW", "name": "Charles Schwab Corp.", "sector": "Finance", "exchange": "NYSE", "price": 72.0, "mcap": 132e9, "pe": 18.4, "div": 1.40, "desc": "Discount brokerage and financial services firm serving individual investors"},
    {"symbol": "CB", "name": "Chubb Ltd.", "sector": "Finance", "exchange": "NYSE", "price": 255.0, "mcap": 105e9, "pe": 11.5, "div": 1.35, "desc": "Global property and casualty insurance company with specialty commercial lines"},
    {"symbol": "ICE", "name": "Intercontinental Exchange", "sector": "Finance", "exchange": "NYSE", "price": 140.0, "mcap": 80e9, "pe": 28.2, "div": 1.15, "desc": "Operator of commodity and financial exchanges including the NYSE"},
    {"symbol": "CME", "name": "CME Group Inc.", "sector": "Finance", "exchange": "NASDAQ", "price": 210.0, "mcap": 75e9, "pe": 24.5, "div": 2.10, "desc": "Largest financial derivatives exchange trading futures, options, and swaps"},
    {"symbol": "PGR", "name": "Progressive Corp.", "sector": "Finance", "exchange": "NYSE", "price": 195.0, "mcap": 114e9, "pe": 18.2, "div": 0.30, "desc": "Auto and property insurer using data analytics for competitive pricing models"},

    # Energy
    {"symbol": "XOM", "name": "Exxon Mobil Corp.", "sector": "Energy", "exchange": "NYSE", "price": 108.0, "mcap": 440e9, "pe": 12.5, "div": 3.25, "desc": "Largest US integrated oil and gas company with global exploration and refining"},
    {"symbol": "CVX", "name": "Chevron Corp.", "sector": "Energy", "exchange": "NYSE", "price": 155.0, "mcap": 295e9, "pe": 11.8, "div": 3.80, "desc": "Major integrated energy company with upstream and downstream operations globally"},
    {"symbol": "COP", "name": "ConocoPhillips", "sector": "Energy", "exchange": "NYSE", "price": 118.0, "mcap": 145e9, "pe": 10.2, "div": 1.85, "desc": "Independent exploration and production company with global shale and conventional assets"},
    {"symbol": "SLB", "name": "Schlumberger NV", "sector": "Energy", "exchange": "NYSE", "price": 48.0, "mcap": 68e9, "pe": 15.4, "div": 1.90, "desc": "Oilfield services company providing drilling, completions, and production technology"},
    {"symbol": "EOG", "name": "EOG Resources Inc.", "sector": "Energy", "exchange": "NYSE", "price": 125.0, "mcap": 72e9, "pe": 9.8, "div": 2.50, "desc": "Shale oil producer focused on low-cost operations in the Permian and Eagle Ford basins"},
    {"symbol": "PXD", "name": "Pioneer Natural Resources", "sector": "Energy", "exchange": "NYSE", "price": 245.0, "mcap": 57e9, "pe": 10.5, "div": 5.20, "desc": "Permian Basin oil and gas exploration company with large-scale horizontal drilling"},
    {"symbol": "OXY", "name": "Occidental Petroleum", "sector": "Energy", "exchange": "NYSE", "price": 62.0, "mcap": 55e9, "pe": 8.5, "div": 1.30, "desc": "Oil and gas exploration company with carbon capture technology investments"},
    {"symbol": "ENPH", "name": "Enphase Energy", "sector": "Energy", "exchange": "NASDAQ", "price": 120.0, "mcap": 16e9, "pe": 32.5, "div": 0.0, "desc": "Solar microinverter manufacturer enabling residential and commercial clean energy"},
    {"symbol": "NEE", "name": "NextEra Energy", "sector": "Energy", "exchange": "NYSE", "price": 75.0, "mcap": 153e9, "pe": 22.8, "div": 2.50, "desc": "Largest US utility company and world's largest generator of wind and solar energy"},
    {"symbol": "LNG", "name": "Cheniere Energy", "sector": "Energy", "exchange": "NYSE", "price": 175.0, "mcap": 41e9, "pe": 7.8, "div": 1.25, "desc": "Leading liquefied natural gas producer and exporter in the United States"},

    # Consumer
    {"symbol": "WMT", "name": "Walmart Inc.", "sector": "Consumer", "exchange": "NYSE", "price": 165.0, "mcap": 445e9, "pe": 28.5, "div": 1.35, "desc": "World's largest retailer with supercenters, Sam's Club, and growing e-commerce"},
    {"symbol": "PG", "name": "Procter & Gamble Co.", "sector": "Consumer", "exchange": "NYSE", "price": 158.0, "mcap": 372e9, "pe": 24.8, "div": 2.45, "desc": "Consumer goods giant with brands like Tide, Pampers, and Gillette"},
    {"symbol": "KO", "name": "Coca-Cola Co.", "sector": "Consumer", "exchange": "NYSE", "price": 62.0, "mcap": 268e9, "pe": 23.5, "div": 2.95, "desc": "Global beverage company with Coca-Cola, Sprite, Fanta, and Dasani brands"},
    {"symbol": "PEP", "name": "PepsiCo Inc.", "sector": "Consumer", "exchange": "NASDAQ", "price": 175.0, "mcap": 240e9, "pe": 22.1, "div": 2.70, "desc": "Beverage and snack company with Pepsi, Lay's, Gatorade, and Quaker brands"},
    {"symbol": "COST", "name": "Costco Wholesale", "sector": "Consumer", "exchange": "NASDAQ", "price": 720.0, "mcap": 320e9, "pe": 45.2, "div": 0.58, "desc": "Membership warehouse retailer offering bulk goods at low prices with high customer loyalty"},
    {"symbol": "MCD", "name": "McDonald's Corp.", "sector": "Consumer", "exchange": "NYSE", "price": 295.0, "mcap": 213e9, "pe": 24.8, "div": 2.15, "desc": "Global fast-food chain with franchise operations in over 100 countries"},
    {"symbol": "NKE", "name": "Nike Inc.", "sector": "Consumer", "exchange": "NYSE", "price": 105.0, "mcap": 162e9, "pe": 28.5, "div": 1.22, "desc": "World's largest athletic footwear and apparel company with global brand reach"},
    {"symbol": "SBUX", "name": "Starbucks Corp.", "sector": "Consumer", "exchange": "NASDAQ", "price": 98.0, "mcap": 112e9, "pe": 25.2, "div": 2.10, "desc": "Global coffeehouse chain with premium drinks, food, and loyalty rewards program"},
    {"symbol": "TGT", "name": "Target Corp.", "sector": "Consumer", "exchange": "NYSE", "price": 140.0, "mcap": 65e9, "pe": 16.5, "div": 2.85, "desc": "Discount department store chain with curated private label brands and e-commerce"},
    {"symbol": "HD", "name": "The Home Depot", "sector": "Consumer", "exchange": "NYSE", "price": 345.0, "mcap": 343e9, "pe": 22.8, "div": 2.45, "desc": "Largest US home improvement retailer serving contractors and DIY consumers"},
    {"symbol": "LOW", "name": "Lowe's Companies", "sector": "Consumer", "exchange": "NYSE", "price": 225.0, "mcap": 132e9, "pe": 18.2, "div": 1.85, "desc": "Home improvement retailer competing with Home Depot in DIY and pro markets"},
    {"symbol": "EL", "name": "Estee Lauder Cos.", "sector": "Consumer", "exchange": "NYSE", "price": 145.0, "mcap": 52e9, "pe": 35.8, "div": 1.52, "desc": "Prestige beauty company with skincare, makeup, and fragrance brands globally"},
    {"symbol": "TSLA", "name": "Tesla Inc.", "sector": "Consumer", "exchange": "NASDAQ", "price": 245.0, "mcap": 780e9, "pe": 58.2, "div": 0.0, "desc": "Electric vehicle manufacturer and clean energy company with autonomous driving technology"},

    # Communication
    {"symbol": "DIS", "name": "Walt Disney Co.", "sector": "Communication", "exchange": "NYSE", "price": 105.0, "mcap": 192e9, "pe": 22.5, "div": 0.0, "desc": "Entertainment conglomerate with theme parks, streaming, film studios, and sports networks"},
    {"symbol": "NFLX", "name": "Netflix Inc.", "sector": "Communication", "exchange": "NASDAQ", "price": 600.0, "mcap": 262e9, "pe": 42.8, "div": 0.0, "desc": "Global streaming entertainment service with original content and advertising tier"},
    {"symbol": "CMCSA", "name": "Comcast Corp.", "sector": "Communication", "exchange": "NASDAQ", "price": 42.0, "mcap": 170e9, "pe": 10.5, "div": 2.80, "desc": "Media and telecom conglomerate with cable, NBCUniversal, and Peacock streaming"},
    {"symbol": "TMUS", "name": "T-Mobile US Inc.", "sector": "Communication", "exchange": "NASDAQ", "price": 162.0, "mcap": 192e9, "pe": 22.8, "div": 1.40, "desc": "Major US wireless carrier with nationwide 5G network and postpaid growth"},
    {"symbol": "VZ", "name": "Verizon Communications", "sector": "Communication", "exchange": "NYSE", "price": 38.0, "mcap": 160e9, "pe": 8.5, "div": 6.85, "desc": "Largest US wireless carrier with broadband and enterprise communication services"},
    {"symbol": "ATVI", "name": "Activision Blizzard", "sector": "Communication", "exchange": "NASDAQ", "price": 94.0, "mcap": 74e9, "pe": 28.5, "div": 0.50, "desc": "Video game publisher with Call of Duty, World of Warcraft, and mobile gaming titles"},
    {"symbol": "SPOT", "name": "Spotify Technology", "sector": "Communication", "exchange": "NYSE", "price": 240.0, "mcap": 47e9, "pe": 85.2, "div": 0.0, "desc": "Audio streaming platform with music, podcasts, and personalized recommendations"},
    {"symbol": "WBD", "name": "Warner Bros. Discovery", "sector": "Communication", "exchange": "NASDAQ", "price": 10.5, "mcap": 25e9, "pe": 15.2, "div": 0.0, "desc": "Media company with HBO, Warner Bros. studios, CNN, and discovery channels"},
    {"symbol": "RBLX", "name": "Roblox Corp.", "sector": "Communication", "exchange": "NYSE", "price": 42.0, "mcap": 26e9, "pe": 0.0, "div": 0.0, "desc": "Online gaming platform with user-generated experiences popular among young audiences"},

    # Industrial
    {"symbol": "HON", "name": "Honeywell International", "sector": "Industrial", "exchange": "NASDAQ", "price": 200.0, "mcap": 132e9, "pe": 24.5, "div": 2.05, "desc": "Diversified industrial conglomerate in aerospace, building tech, and specialty chemicals"},
    {"symbol": "UPS", "name": "United Parcel Service", "sector": "Industrial", "exchange": "NYSE", "price": 155.0, "mcap": 133e9, "pe": 16.8, "div": 4.15, "desc": "Global package delivery and supply chain management company"},
    {"symbol": "CAT", "name": "Caterpillar Inc.", "sector": "Industrial", "exchange": "NYSE", "price": 290.0, "mcap": 148e9, "pe": 14.5, "div": 1.72, "desc": "Construction and mining equipment manufacturer with global dealer network"},
    {"symbol": "BA", "name": "Boeing Co.", "sector": "Industrial", "exchange": "NYSE", "price": 215.0, "mcap": 130e9, "pe": 0.0, "div": 0.0, "desc": "Aerospace manufacturer building commercial airplanes and defense systems"},
    {"symbol": "GE", "name": "GE Aerospace", "sector": "Industrial", "exchange": "NYSE", "price": 158.0, "mcap": 172e9, "pe": 32.5, "div": 0.25, "desc": "Aerospace company making jet engines and aviation services spun off from General Electric"},
    {"symbol": "RTX", "name": "RTX Corp.", "sector": "Industrial", "exchange": "NYSE", "price": 95.0, "mcap": 132e9, "pe": 18.2, "div": 2.25, "desc": "Aerospace and defense company with Pratt & Whitney engines and Raytheon missiles"},
    {"symbol": "LMT", "name": "Lockheed Martin", "sector": "Industrial", "exchange": "NYSE", "price": 470.0, "mcap": 113e9, "pe": 16.8, "div": 2.55, "desc": "Defense contractor building F-35 fighters, missile systems, and space technology"},
    {"symbol": "DE", "name": "Deere & Co.", "sector": "Industrial", "exchange": "NYSE", "price": 395.0, "mcap": 115e9, "pe": 12.5, "div": 1.32, "desc": "Agricultural and construction equipment maker with precision technology solutions"},
    {"symbol": "MMM", "name": "3M Company", "sector": "Industrial", "exchange": "NYSE", "price": 105.0, "mcap": 58e9, "pe": 12.8, "div": 5.60, "desc": "Diversified manufacturer of adhesives, abrasives, and consumer products"},
    {"symbol": "FDX", "name": "FedEx Corp.", "sector": "Industrial", "exchange": "NYSE", "price": 265.0, "mcap": 66e9, "pe": 14.5, "div": 1.90, "desc": "Express shipping and logistics company with global air and ground delivery networks"},

    # Real Estate
    {"symbol": "AMT", "name": "American Tower Corp.", "sector": "Real Estate", "exchange": "NYSE", "price": 210.0, "mcap": 98e9, "pe": 42.5, "div": 3.05, "desc": "Cell tower REIT owning and leasing wireless communications infrastructure globally"},
    {"symbol": "PLD", "name": "Prologis Inc.", "sector": "Real Estate", "exchange": "NYSE", "price": 125.0, "mcap": 116e9, "pe": 38.2, "div": 2.65, "desc": "Industrial logistics REIT owning warehouse and distribution center properties"},
    {"symbol": "CCI", "name": "Crown Castle Inc.", "sector": "Real Estate", "exchange": "NYSE", "price": 105.0, "mcap": 46e9, "pe": 35.8, "div": 5.85, "desc": "Wireless infrastructure REIT with cell towers and small cell networks across the US"},
    {"symbol": "EQIX", "name": "Equinix Inc.", "sector": "Real Estate", "exchange": "NASDAQ", "price": 825.0, "mcap": 78e9, "pe": 85.2, "div": 1.85, "desc": "Data center REIT providing colocation and interconnection services globally"},
    {"symbol": "SPG", "name": "Simon Property Group", "sector": "Real Estate", "exchange": "NYSE", "price": 148.0, "mcap": 48e9, "pe": 18.5, "div": 5.15, "desc": "Largest US mall REIT owning premium shopping centers and outlet malls"},
    {"symbol": "O", "name": "Realty Income Corp.", "sector": "Real Estate", "exchange": "NYSE", "price": 55.0, "mcap": 42e9, "pe": 42.5, "div": 5.45, "desc": "Monthly dividend REIT with net-lease retail and industrial properties"},

    # Utilities
    {"symbol": "SO", "name": "Southern Co.", "sector": "Utilities", "exchange": "NYSE", "price": 78.0, "mcap": 85e9, "pe": 20.5, "div": 3.60, "desc": "Electric utility serving the southeastern United States with nuclear and gas generation"},
    {"symbol": "DUK", "name": "Duke Energy Corp.", "sector": "Utilities", "exchange": "NYSE", "price": 100.0, "mcap": 77e9, "pe": 18.2, "div": 4.05, "desc": "Regulated electric utility providing power to customers in the Carolinas and Midwest"},
    {"symbol": "AEP", "name": "American Electric Power", "sector": "Utilities", "exchange": "NASDAQ", "price": 88.0, "mcap": 45e9, "pe": 16.8, "div": 3.85, "desc": "Electric utility delivering power across 11 states with coal and renewable generation"},
    {"symbol": "SRE", "name": "Sempra Energy", "sector": "Utilities", "exchange": "NYSE", "price": 76.0, "mcap": 48e9, "pe": 15.5, "div": 3.10, "desc": "Energy infrastructure company with California utilities and LNG export terminals"},
    {"symbol": "D", "name": "Dominion Energy", "sector": "Utilities", "exchange": "NYSE", "price": 50.0, "mcap": 42e9, "pe": 22.5, "div": 5.30, "desc": "Regulated utility providing electricity and natural gas to customers in the eastern US"},
]

# ---------------------------------------------------------------------------
# 2. Fetch crypto from CoinGecko
# ---------------------------------------------------------------------------

COINGECKO_URL = "https://api.coingecko.com/api/v3/coins/markets"

def fetch_crypto_data(count=50):
    """Fetch top cryptocurrencies from CoinGecko free API."""
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": count,
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "7d,30d",
    }
    try:
        print(f"Fetching top {count} cryptocurrencies from CoinGecko...")
        resp = requests.get(COINGECKO_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        print(f"  -> Got {len(data)} coins")
        return data
    except Exception as e:
        print(f"  -> CoinGecko fetch failed: {e}")
        print("  -> Using fallback crypto data")
        return None


FALLBACK_CRYPTO = [
    {"symbol": "BTC", "name": "Bitcoin", "mcap": 1320e9, "price": 67500.0, "change24": 2.1, "change7d": 5.4, "change30d": 12.3, "vol": 28e9, "high": 73750.0, "low": 15500.0, "desc": "First and largest decentralized cryptocurrency based on proof-of-work blockchain"},
    {"symbol": "ETH", "name": "Ethereum", "mcap": 420e9, "price": 3520.0, "change24": 1.8, "change7d": 4.2, "change30d": 8.5, "vol": 15e9, "high": 4878.0, "low": 80.0, "desc": "Smart contract platform powering decentralized applications and DeFi protocols"},
    {"symbol": "BNB", "name": "BNB", "mcap": 90e9, "price": 595.0, "change24": 0.9, "change7d": 2.1, "change30d": 5.8, "vol": 1.5e9, "high": 690.0, "low": 5.0, "desc": "Native token of Binance exchange and BNB Chain smart contract platform"},
    {"symbol": "SOL", "name": "Solana", "mcap": 80e9, "price": 185.0, "change24": 3.2, "change7d": 8.5, "change30d": 15.2, "vol": 3.2e9, "high": 260.0, "low": 0.5, "desc": "High-performance blockchain optimized for speed and low transaction costs"},
    {"symbol": "XRP", "name": "XRP", "mcap": 68e9, "price": 1.25, "change24": -0.5, "change7d": 1.8, "change30d": -2.1, "vol": 2.8e9, "high": 3.84, "low": 0.003, "desc": "Digital payment protocol for fast and low-cost cross-border transactions"},
    {"symbol": "USDC", "name": "USD Coin", "mcap": 33e9, "price": 1.00, "change24": 0.01, "change7d": 0.0, "change30d": 0.0, "vol": 5e9, "high": 1.0, "low": 0.99, "desc": "Fully backed stablecoin pegged to the US dollar issued by Circle"},
    {"symbol": "ADA", "name": "Cardano", "mcap": 22e9, "price": 0.62, "change24": 1.5, "change7d": 3.8, "change30d": -5.2, "vol": 800e6, "high": 3.10, "low": 0.02, "desc": "Research-driven blockchain platform with proof-of-stake consensus and smart contracts"},
    {"symbol": "AVAX", "name": "Avalanche", "mcap": 15e9, "price": 38.0, "change24": 2.8, "change7d": 6.2, "change30d": 10.5, "vol": 650e6, "high": 146.0, "low": 2.8, "desc": "Fast smart contract platform with subnet architecture for custom blockchain deployments"},
    {"symbol": "DOGE", "name": "Dogecoin", "mcap": 22e9, "price": 0.16, "change24": 4.5, "change7d": 8.2, "change30d": 18.5, "vol": 1.8e9, "high": 0.74, "low": 0.0001, "desc": "Meme cryptocurrency originally created as a joke that gained mainstream adoption"},
    {"symbol": "DOT", "name": "Polkadot", "mcap": 10e9, "price": 7.50, "change24": 1.2, "change7d": 4.5, "change30d": -3.8, "vol": 350e6, "high": 55.0, "low": 2.7, "desc": "Multi-chain protocol enabling cross-blockchain interoperability and shared security"},
    {"symbol": "TRX", "name": "TRON", "mcap": 12e9, "price": 0.14, "change24": 0.8, "change7d": 2.1, "change30d": 5.2, "vol": 450e6, "high": 0.18, "low": 0.001, "desc": "Blockchain platform focused on entertainment content sharing and decentralized apps"},
    {"symbol": "LINK", "name": "Chainlink", "mcap": 10e9, "price": 17.50, "change24": 2.5, "change7d": 5.8, "change30d": 8.2, "vol": 680e6, "high": 52.88, "low": 0.15, "desc": "Decentralized oracle network connecting smart contracts to real-world data feeds"},
    {"symbol": "MATIC", "name": "Polygon", "mcap": 8e9, "price": 0.85, "change24": 1.8, "change7d": 3.2, "change30d": -4.5, "vol": 520e6, "high": 2.92, "low": 0.003, "desc": "Ethereum layer-2 scaling solution with low-cost and fast transactions"},
    {"symbol": "SHIB", "name": "Shiba Inu", "mcap": 6e9, "price": 0.000010, "change24": 5.2, "change7d": 12.5, "change30d": 25.8, "vol": 450e6, "high": 0.000088, "low": 0.0000000001, "desc": "Meme token ecosystem with decentralized exchange and NFT marketplace"},
    {"symbol": "UNI", "name": "Uniswap", "mcap": 7.5e9, "price": 12.50, "change24": 1.9, "change7d": 4.8, "change30d": 6.5, "vol": 280e6, "high": 44.97, "low": 0.42, "desc": "Largest decentralized exchange protocol for automated token trading on Ethereum"},
    {"symbol": "LTC", "name": "Litecoin", "mcap": 6.5e9, "price": 88.0, "change24": 0.5, "change7d": 1.2, "change30d": -2.8, "vol": 380e6, "high": 412.96, "low": 1.15, "desc": "Peer-to-peer cryptocurrency with faster block times than Bitcoin for everyday payments"},
    {"symbol": "ATOM", "name": "Cosmos", "mcap": 4e9, "price": 10.50, "change24": 2.1, "change7d": 5.5, "change30d": 8.8, "vol": 220e6, "high": 44.70, "low": 1.13, "desc": "Interoperability-focused blockchain ecosystem connecting independent networks"},
    {"symbol": "XLM", "name": "Stellar", "mcap": 3.5e9, "price": 0.12, "change24": 0.8, "change7d": 2.5, "change30d": -1.5, "vol": 180e6, "high": 0.94, "low": 0.001, "desc": "Open-source payment network for fast cross-border transfers and financial inclusion"},
    {"symbol": "APT", "name": "Aptos", "mcap": 4.5e9, "price": 9.80, "change24": 3.5, "change7d": 7.2, "change30d": 12.5, "vol": 250e6, "high": 19.92, "low": 3.08, "desc": "Layer-1 blockchain built by former Meta engineers with Move programming language"},
    {"symbol": "FIL", "name": "Filecoin", "mcap": 3e9, "price": 5.80, "change24": 1.5, "change7d": 3.8, "change30d": -6.2, "vol": 200e6, "high": 237.24, "low": 2.64, "desc": "Decentralized storage network incentivizing users to share spare hard drive capacity"},
    {"symbol": "NEAR", "name": "NEAR Protocol", "mcap": 5e9, "price": 5.20, "change24": 2.8, "change7d": 6.5, "change30d": 10.2, "vol": 310e6, "high": 20.44, "low": 0.52, "desc": "Sharded proof-of-stake blockchain with developer-friendly tools and fast finality"},
    {"symbol": "ARB", "name": "Arbitrum", "mcap": 3.2e9, "price": 1.25, "change24": 2.2, "change7d": 4.8, "change30d": -3.5, "vol": 280e6, "high": 2.40, "low": 0.74, "desc": "Ethereum layer-2 rollup providing cheaper and faster transactions for DeFi apps"},
    {"symbol": "OP", "name": "Optimism", "mcap": 2.8e9, "price": 2.85, "change24": 1.8, "change7d": 3.5, "change30d": 5.8, "vol": 180e6, "high": 4.85, "low": 0.40, "desc": "Optimistic rollup scaling solution for Ethereum with retroactive public goods funding"},
    {"symbol": "ALGO", "name": "Algorand", "mcap": 1.8e9, "price": 0.22, "change24": 1.2, "change7d": 2.8, "change30d": -4.2, "vol": 85e6, "high": 3.56, "low": 0.09, "desc": "Pure proof-of-stake blockchain with instant finality and low carbon footprint"},
    {"symbol": "ICP", "name": "Internet Computer", "mcap": 4.8e9, "price": 10.20, "change24": 3.2, "change7d": 7.8, "change30d": 14.5, "vol": 120e6, "high": 750.73, "low": 3.40, "desc": "Decentralized cloud computing platform running smart contracts at web speed"},
    {"symbol": "INJ", "name": "Injective", "mcap": 3.5e9, "price": 38.00, "change24": 4.5, "change7d": 10.2, "change30d": 22.5, "vol": 250e6, "high": 52.62, "low": 0.65, "desc": "Decentralized finance blockchain with cross-chain derivatives trading protocol"},
    {"symbol": "AAVE", "name": "Aave", "mcap": 1.5e9, "price": 102.0, "change24": 2.5, "change7d": 5.2, "change30d": 8.5, "vol": 180e6, "high": 666.86, "low": 26.02, "desc": "Decentralized lending and borrowing protocol allowing flash loans and yield farming"},
    {"symbol": "MKR", "name": "Maker", "mcap": 2.8e9, "price": 3050.0, "change24": 1.8, "change7d": 4.2, "change30d": 6.8, "vol": 120e6, "high": 6292.31, "low": 168.36, "desc": "Decentralized governance token backing the DAI stablecoin on Ethereum"},
    {"symbol": "RENDER", "name": "Render Token", "mcap": 3.2e9, "price": 8.50, "change24": 5.8, "change7d": 12.5, "change30d": 28.2, "vol": 320e6, "high": 13.60, "low": 0.04, "desc": "Decentralized GPU rendering network connecting artists with computing power"},
    {"symbol": "FET", "name": "Fetch.ai", "mcap": 2.2e9, "price": 2.35, "change24": 4.2, "change7d": 9.8, "change30d": 18.5, "vol": 280e6, "high": 3.48, "low": 0.008, "desc": "AI-focused blockchain platform with autonomous economic agents for Web3"},
    {"symbol": "PEPE", "name": "Pepe", "mcap": 4.2e9, "price": 0.000010, "change24": 8.5, "change7d": 15.2, "change30d": 35.8, "vol": 1.2e9, "high": 0.000017, "low": 0.0000001, "desc": "Meme cryptocurrency inspired by the Pepe the Frog internet meme with viral community"},
    {"symbol": "SUI", "name": "Sui", "mcap": 3.8e9, "price": 1.52, "change24": 3.8, "change7d": 8.5, "change30d": 15.2, "vol": 420e6, "high": 2.18, "low": 0.36, "desc": "Layer-1 blockchain with parallel transaction processing built by former Meta engineers"},
    {"symbol": "SEI", "name": "Sei", "mcap": 1.8e9, "price": 0.65, "change24": 2.5, "change7d": 5.8, "change30d": 10.5, "vol": 180e6, "high": 1.04, "low": 0.01, "desc": "Trading-optimized layer-1 blockchain with built-in order matching engine"},
    {"symbol": "TIA", "name": "Celestia", "mcap": 2.5e9, "price": 15.80, "change24": 3.2, "change7d": 7.5, "change30d": 12.8, "vol": 220e6, "high": 21.0, "low": 2.08, "desc": "Modular blockchain network enabling anyone to deploy their own data availability layer"},
    {"symbol": "WLD", "name": "Worldcoin", "mcap": 1.2e9, "price": 3.20, "change24": 4.8, "change7d": 10.5, "change30d": 20.2, "vol": 150e6, "high": 11.75, "low": 1.00, "desc": "Digital identity and cryptocurrency project using iris scanning for universal basic income"},
    {"symbol": "TON", "name": "Toncoin", "mcap": 18e9, "price": 5.25, "change24": 1.5, "change7d": 3.8, "change30d": 8.5, "vol": 180e6, "high": 8.25, "low": 0.51, "desc": "Layer-1 blockchain integrated with Telegram messenger for payments and mini-apps"},
    {"symbol": "HBAR", "name": "Hedera", "mcap": 3.5e9, "price": 0.098, "change24": 1.8, "change7d": 4.2, "change30d": 6.5, "vol": 120e6, "high": 0.57, "low": 0.01, "desc": "Enterprise-grade distributed ledger with hashgraph consensus for real-time transactions"},
    {"symbol": "VET", "name": "VeChain", "mcap": 2.5e9, "price": 0.035, "change24": 2.2, "change7d": 5.5, "change30d": 9.8, "vol": 95e6, "high": 0.28, "low": 0.002, "desc": "Supply chain focused blockchain platform for product tracking and business process management"},
    {"symbol": "SAND", "name": "The Sandbox", "mcap": 1.2e9, "price": 0.55, "change24": 3.5, "change7d": 7.8, "change30d": 12.5, "vol": 150e6, "high": 8.40, "low": 0.03, "desc": "Virtual world gaming platform where players create, own, and monetize digital experiences"},
    {"symbol": "MANA", "name": "Decentraland", "mcap": 1.0e9, "price": 0.52, "change24": 2.8, "change7d": 6.2, "change30d": 10.8, "vol": 120e6, "high": 5.90, "low": 0.008, "desc": "Virtual reality platform powered by Ethereum where users purchase and develop virtual land"},
    {"symbol": "AXS", "name": "Axie Infinity", "mcap": 1.1e9, "price": 8.20, "change24": 3.2, "change7d": 7.5, "change30d": 14.2, "vol": 85e6, "high": 164.90, "low": 0.12, "desc": "Play-to-earn blockchain game where players breed, battle, and trade digital creatures"},
    {"symbol": "CRV", "name": "Curve DAO Token", "mcap": 0.8e9, "price": 0.62, "change24": 2.5, "change7d": 5.8, "change30d": 8.5, "vol": 95e6, "high": 60.50, "low": 0.17, "desc": "Decentralized exchange protocol optimized for efficient stablecoin and pegged asset swaps"},
    {"symbol": "RUNE", "name": "THORChain", "mcap": 2.0e9, "price": 6.50, "change24": 3.8, "change7d": 8.2, "change30d": 15.5, "vol": 180e6, "high": 21.26, "low": 0.01, "desc": "Cross-chain decentralized exchange enabling native asset swaps across blockchains"},
    {"symbol": "GRT", "name": "The Graph", "mcap": 1.5e9, "price": 0.16, "change24": 2.0, "change7d": 4.5, "change30d": 7.2, "vol": 110e6, "high": 2.88, "low": 0.05, "desc": "Indexing protocol for querying blockchain data enabling efficient decentralized applications"},
    {"symbol": "STX", "name": "Stacks", "mcap": 2.8e9, "price": 1.95, "change24": 3.5, "change7d": 7.8, "change30d": 12.5, "vol": 140e6, "high": 3.85, "low": 0.045, "desc": "Layer-1 blockchain bringing smart contracts and DeFi to Bitcoin through proof of transfer"},
    {"symbol": "BONK", "name": "Bonk", "mcap": 1.5e9, "price": 0.000022, "change24": 6.5, "change7d": 14.2, "change30d": 32.5, "vol": 350e6, "high": 0.000046, "low": 0.0000001, "desc": "Solana-based meme cryptocurrency with community-driven distribution and viral adoption"},
    {"symbol": "JUP", "name": "Jupiter", "mcap": 1.8e9, "price": 1.32, "change24": 3.2, "change7d": 7.5, "change30d": 14.8, "vol": 200e6, "high": 2.05, "low": 0.45, "desc": "Leading Solana DEX aggregator routing trades across multiple liquidity sources"},
    {"symbol": "PENDLE", "name": "Pendle", "mcap": 1.0e9, "price": 6.80, "change24": 4.5, "change7d": 10.2, "change30d": 18.5, "vol": 120e6, "high": 7.52, "low": 0.03, "desc": "DeFi yield trading protocol allowing tokenization and trading of future yield streams"},
    {"symbol": "W", "name": "Wormhole", "mcap": 1.2e9, "price": 0.68, "change24": 2.8, "change7d": 5.5, "change30d": 9.2, "vol": 150e6, "high": 1.85, "low": 0.32, "desc": "Cross-chain messaging protocol enabling token transfers between major blockchains"},
    {"symbol": "ENA", "name": "Ethena", "mcap": 1.5e9, "price": 0.95, "change24": 3.5, "change7d": 8.2, "change30d": 15.5, "vol": 180e6, "high": 1.52, "low": 0.20, "desc": "Synthetic dollar protocol providing crypto-native yield through delta-hedging strategies"},
]


# ---------------------------------------------------------------------------
# 3. Build assets
# ---------------------------------------------------------------------------

def add_noise(val, pct=0.03):
    """Add small random noise to a value."""
    return round(val * (1 + random.uniform(-pct, pct)), 2)


def build_stock_asset(idx, sdef):
    """Build an asset dict from a stock definition."""
    price = add_noise(sdef["price"], 0.02)
    open_price = add_noise(price, 0.01)
    high = round(price * random.uniform(1.005, 1.025), 2)
    low = round(price * random.uniform(0.975, 0.995), 2)
    volume = int(sdef["mcap"] / sdef["price"] * random.uniform(0.005, 0.03))
    change_24h = round(random.uniform(-3.5, 4.5), 2)
    change_7d = round(random.uniform(-6.0, 8.0), 2)
    change_30d = round(random.uniform(-12.0, 15.0), 2)
    ath = round(price * random.uniform(1.05, 1.60), 2)
    atl = round(price * random.uniform(0.001, 0.15), 2)

    return {
        "id": idx,
        "symbol": sdef["symbol"],
        "name": sdef["name"],
        "type": "stock",
        "sector": sdef["sector"],
        "market_cap": int(sdef["mcap"]),
        "current_price": price,
        "open_price": open_price,
        "high_24h": high,
        "low_24h": low,
        "volume_24h": volume,
        "change_pct_24h": change_24h,
        "change_pct_7d": change_7d,
        "change_pct_30d": change_30d,
        "all_time_high": ath,
        "all_time_low": atl,
        "pe_ratio": sdef["pe"],
        "dividend_yield": sdef["div"],
        "exchange": sdef["exchange"],
        "currency": "USD",
        "description": sdef["desc"],
    }


def build_crypto_asset_from_api(idx, coin):
    """Build asset from CoinGecko API response."""
    price = coin.get("current_price", 0)
    return {
        "id": idx,
        "symbol": coin["symbol"].upper(),
        "name": coin["name"],
        "type": "crypto",
        "sector": "Cryptocurrency",
        "market_cap": int(coin.get("market_cap") or 0),
        "current_price": round(price, 6) if price < 1 else round(price, 2),
        "open_price": round(price * random.uniform(0.98, 1.02), 6 if price < 1 else 2),
        "high_24h": round(coin.get("high_24h") or price * 1.02, 6 if price < 1 else 2),
        "low_24h": round(coin.get("low_24h") or price * 0.98, 6 if price < 1 else 2),
        "volume_24h": int(coin.get("total_volume") or 0),
        "change_pct_24h": round(coin.get("price_change_percentage_24h") or 0, 2),
        "change_pct_7d": round(coin.get("price_change_percentage_7d_in_currency") or random.uniform(-5, 8), 2),
        "change_pct_30d": round(coin.get("price_change_percentage_30d_in_currency") or random.uniform(-10, 15), 2),
        "all_time_high": round(coin.get("ath") or price * 2, 2),
        "all_time_low": round(coin.get("atl") or price * 0.01, 6 if price < 1 else 2),
        "pe_ratio": 0.0,
        "dividend_yield": 0.0,
        "exchange": "CoinGecko",
        "currency": "USD",
        "description": "",  # will be filled from fallback or left generic
    }


def build_crypto_asset_from_fallback(idx, fb):
    """Build asset from fallback crypto definition."""
    price = fb["price"]
    return {
        "id": idx,
        "symbol": fb["symbol"],
        "name": fb["name"],
        "type": "crypto",
        "sector": "Cryptocurrency",
        "market_cap": int(fb["mcap"]),
        "current_price": round(price, 6) if price < 1 else round(price, 2),
        "open_price": round(price * random.uniform(0.98, 1.02), 6 if price < 1 else 2),
        "high_24h": round(price * random.uniform(1.01, 1.04), 6 if price < 1 else 2),
        "low_24h": round(price * random.uniform(0.96, 0.99), 6 if price < 1 else 2),
        "volume_24h": int(fb["vol"]),
        "change_pct_24h": fb["change24"],
        "change_pct_7d": fb["change7d"],
        "change_pct_30d": fb["change30d"],
        "all_time_high": round(fb["high"], 2),
        "all_time_low": round(fb["low"], 6 if fb["low"] < 1 else 2),
        "pe_ratio": 0.0,
        "dividend_yield": 0.0,
        "exchange": "CoinGecko",
        "currency": "USD",
        "description": fb["desc"],
    }


# ---------------------------------------------------------------------------
# 4. Build price history
# ---------------------------------------------------------------------------

def generate_price_history(assets, days=15):
    """Generate realistic daily price history for each asset over the last N trading days."""
    history = []
    hist_id = 1
    base_date = datetime(2025, 1, 2)  # Start from Jan 2, 2025

    for asset in assets:
        price = asset["current_price"]
        # Walk backward to create a plausible path ending at current_price
        # Generate daily returns, then adjust so final day matches current_price
        daily_returns = [random.gauss(0.001, 0.015) for _ in range(days)]
        # Build price path forward from an inferred starting price
        start_price = price
        for r in reversed(daily_returns):
            start_price = start_price / (1 + r)

        p = start_price
        trading_day = base_date
        for i in range(days):
            p = p * (1 + daily_returns[i])
            o = round(p * random.uniform(0.995, 1.005), 6 if p < 1 else 2)
            h = round(p * random.uniform(1.005, 1.03), 6 if p < 1 else 2)
            l = round(p * random.uniform(0.97, 0.995), 6 if p < 1 else 2)
            c = round(p, 6 if p < 1 else 2)
            vol_base = asset["volume_24h"] if asset["volume_24h"] > 0 else 1000000
            vol = int(vol_base * random.uniform(0.7, 1.4))

            history.append({
                "id": hist_id,
                "asset_id": asset["id"],
                "date": trading_day.strftime("%Y-%m-%d"),
                "open": o,
                "high": h,
                "low": l,
                "close": c,
                "volume": vol,
            })
            hist_id += 1

            # Advance to next trading day (skip weekends)
            trading_day += timedelta(days=1)
            while trading_day.weekday() >= 5:
                trading_day += timedelta(days=1)

    return history


# ---------------------------------------------------------------------------
# 5. Build sectors
# ---------------------------------------------------------------------------

def build_sectors(assets):
    """Aggregate sector info from assets."""
    sector_map = {}
    for a in assets:
        s = a["sector"]
        if s not in sector_map:
            sector_map[s] = {"count": 0, "changes": []}
        sector_map[s]["count"] += 1
        sector_map[s]["changes"].append(a["change_pct_24h"])

    SECTOR_DESCS = {
        "Technology": "Software, hardware, semiconductors, and IT services companies",
        "Healthcare": "Pharmaceuticals, biotechnology, medical devices, and health services",
        "Finance": "Banks, insurance, asset management, and financial technology",
        "Energy": "Oil, gas, renewable energy, and energy infrastructure companies",
        "Consumer": "Retail, consumer goods, food and beverage, and automotive",
        "Communication": "Telecom, media, entertainment, and social media companies",
        "Industrial": "Manufacturing, aerospace, defense, and logistics companies",
        "Real Estate": "REITs, property management, and real estate development",
        "Utilities": "Electric, water, gas utilities, and regulated energy providers",
        "Cryptocurrency": "Digital currencies, blockchain tokens, and DeFi protocols",
    }

    sectors = []
    for i, (name, info) in enumerate(sorted(sector_map.items()), 1):
        avg = round(sum(info["changes"]) / len(info["changes"]), 2)
        sectors.append({
            "id": i,
            "name": name,
            "description": SECTOR_DESCS.get(name, f"Assets in the {name} sector"),
            "asset_count": info["count"],
            "avg_change_pct": avg,
        })
    return sectors


# ---------------------------------------------------------------------------
# 6. Build users
# ---------------------------------------------------------------------------

USER_PROFILES = [
    {"username": "trader_mike", "name": "Mike Thompson", "email": "mike.t@example.com",
     "strategy": "momentum", "pref_types": ["stock", "crypto"]},
    {"username": "crypto_queen", "name": "Sarah Chen", "email": "sarah.c@example.com",
     "strategy": "crypto_heavy", "pref_types": ["crypto"]},
    {"username": "value_investor", "name": "Robert Williams", "email": "robert.w@example.com",
     "strategy": "value", "pref_types": ["stock"]},
    {"username": "tech_bull", "name": "Emily Rodriguez", "email": "emily.r@example.com",
     "strategy": "growth", "pref_types": ["stock"]},
    {"username": "div_hunter", "name": "James Park", "email": "james.p@example.com",
     "strategy": "dividend", "pref_types": ["stock"]},
    {"username": "balanced_beth", "name": "Beth Morrison", "email": "beth.m@example.com",
     "strategy": "balanced", "pref_types": ["stock", "crypto"]},
    {"username": "defi_dave", "name": "Dave Nguyen", "email": "dave.n@example.com",
     "strategy": "defi", "pref_types": ["crypto"]},
    {"username": "index_irene", "name": "Irene Foster", "email": "irene.f@example.com",
     "strategy": "index", "pref_types": ["stock"]},
]


def build_users(assets):
    """Generate users with watchlists, portfolios, and alerts."""
    stocks = [a for a in assets if a["type"] == "stock"]
    cryptos = [a for a in assets if a["type"] == "crypto"]

    users = []
    for i, profile in enumerate(USER_PROFILES, 1):
        # Select assets for portfolio based on strategy
        if profile["strategy"] == "crypto_heavy":
            pool = cryptos
        elif profile["strategy"] == "defi":
            pool = [c for c in cryptos if c["current_price"] < 50]
        elif profile["strategy"] == "dividend":
            pool = [s for s in stocks if s["dividend_yield"] > 2.0]
        elif profile["strategy"] == "growth":
            pool = [s for s in stocks if s["sector"] == "Technology"]
        elif profile["strategy"] == "value":
            pool = [s for s in stocks if s["pe_ratio"] > 0 and s["pe_ratio"] < 20]
        elif profile["strategy"] == "index":
            pool = [s for s in stocks if s["market_cap"] > 200e9]
        else:
            pool = stocks + cryptos

        random.shuffle(pool)
        port_assets = pool[:random.randint(4, 8)]
        watch_pool = [a for a in (stocks + cryptos) if a not in port_assets]
        random.shuffle(watch_pool)
        watch_assets = watch_pool[:random.randint(3, 7)]

        portfolio = []
        for pa in port_assets:
            if pa["type"] == "crypto" and pa["current_price"] > 5000:
                shares = round(random.uniform(0.1, 2.0), 4)
            elif pa["type"] == "crypto" and pa["current_price"] < 0.01:
                shares = round(random.uniform(10000, 500000), 0)
            elif pa["type"] == "crypto":
                shares = round(random.uniform(5, 500), 2)
            else:
                shares = random.randint(5, 200)
            avg_cost = round(pa["current_price"] * random.uniform(0.7, 1.1), 2)
            portfolio.append({
                "asset_id": pa["id"],
                "shares": shares,
                "avg_cost": avg_cost,
            })

        # Price alerts
        alert_pool = port_assets + watch_assets
        random.shuffle(alert_pool)
        alerts = []
        for aa in alert_pool[:random.randint(1, 3)]:
            direction = random.choice(["above", "below"])
            if direction == "above":
                threshold = round(aa["current_price"] * random.uniform(1.05, 1.30), 2)
            else:
                threshold = round(aa["current_price"] * random.uniform(0.70, 0.95), 2)
            alerts.append({
                "asset_id": aa["id"],
                "threshold": threshold,
                "direction": direction,
            })

        # Saved assets
        saved_pool = [a for a in (stocks + cryptos) if a not in port_assets and a not in watch_assets]
        random.shuffle(saved_pool)
        saved = [a["id"] for a in saved_pool[:random.randint(2, 5)]]

        users.append({
            "id": i,
            "username": profile["username"],
            "name": profile["name"],
            "email": profile["email"],
            "watchlist": [a["id"] for a in watch_assets],
            "price_alerts": alerts,
            "portfolio": portfolio,
            "saved_assets": saved,
        })

    return users


# ---------------------------------------------------------------------------
# 7. Build watchlists
# ---------------------------------------------------------------------------

def build_watchlists(assets, users):
    """Create named watchlists referencing asset IDs."""
    stocks = [a for a in assets if a["type"] == "stock"]
    cryptos = [a for a in assets if a["type"] == "crypto"]
    tech = [a for a in stocks if a["sector"] == "Technology"]
    div_stocks = sorted([a for a in stocks if a["dividend_yield"] > 2.0],
                        key=lambda x: x["dividend_yield"], reverse=True)
    defi = [a for a in cryptos if a["current_price"] < 50 and a["current_price"] > 0.1]
    energy = [a for a in stocks if a["sector"] == "Energy"]
    large_cap = sorted(stocks, key=lambda x: x["market_cap"], reverse=True)

    watchlists = [
        {"id": 1, "name": "FAANG+ Tech Giants", "user_id": users[3]["id"],
         "asset_ids": [a["id"] for a in tech[:8]],
         "created": "2024-11-15"},
        {"id": 2, "name": "Top Cryptos by Market Cap", "user_id": users[1]["id"],
         "asset_ids": [a["id"] for a in sorted(cryptos, key=lambda x: x["market_cap"], reverse=True)[:8]],
         "created": "2024-12-01"},
        {"id": 3, "name": "Dividend Aristocrats", "user_id": users[4]["id"],
         "asset_ids": [a["id"] for a in div_stocks[:8]],
         "created": "2024-10-20"},
        {"id": 4, "name": "AI & Semiconductor Leaders", "user_id": users[0]["id"],
         "asset_ids": [a["id"] for a in stocks if a["symbol"] in ("NVDA", "AMD", "TSM", "AVGO", "INTC", "MU", "AMAT", "QCOM")],
         "created": "2025-01-05"},
        {"id": 5, "name": "DeFi & Web3 Tokens", "user_id": users[6]["id"],
         "asset_ids": [a["id"] for a in defi[:8]],
         "created": "2025-01-10"},
        {"id": 6, "name": "Energy Sector", "user_id": users[2]["id"],
         "asset_ids": [a["id"] for a in energy[:6]],
         "created": "2024-09-15"},
        {"id": 7, "name": "Mega Cap Portfolio", "user_id": users[7]["id"],
         "asset_ids": [a["id"] for a in large_cap[:10]],
         "created": "2024-08-20"},
        {"id": 8, "name": "Meme Coins", "user_id": users[1]["id"],
         "asset_ids": [a["id"] for a in cryptos if a["symbol"] in ("DOGE", "SHIB", "PEPE", "BONK", "WLD")],
         "created": "2025-01-12"},
    ]
    return watchlists


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    random.seed(42)

    # ---- Build stock assets ----
    assets = []
    for i, sdef in enumerate(STOCK_DEFS, 1):
        assets.append(build_stock_asset(i, sdef))

    stock_count = len(assets)
    print(f"Built {stock_count} stock assets")

    # ---- Fetch / build crypto assets ----
    crypto_data = fetch_crypto_data(50)

    if crypto_data:
        # Build descriptions lookup from fallback
        desc_map = {fb["symbol"]: fb["desc"] for fb in FALLBACK_CRYPTO}
        # Also map some CoinGecko IDs to symbols
        for coin in crypto_data:
            idx = stock_count + 1 + len([a for a in assets if a["type"] == "crypto"])
            asset = build_crypto_asset_from_api(idx, coin)
            # Try to find a matching description
            sym = asset["symbol"]
            if sym in desc_map:
                asset["description"] = desc_map[sym]
            else:
                asset["description"] = f"{coin['name']} cryptocurrency ranked by market capitalization"
            assets.append(asset)
    else:
        # Use all fallback crypto
        for fb in FALLBACK_CRYPTO:
            idx = stock_count + 1 + len([a for a in assets if a["type"] == "crypto"])
            assets.append(build_crypto_asset_from_fallback(idx, fb))

    crypto_count = len(assets) - stock_count
    print(f"Built {crypto_count} crypto assets")
    print(f"Total: {len(assets)} assets")

    # ---- Build price history ----
    print("Generating price history (15 days per asset)...")
    history = generate_price_history(assets, days=15)
    print(f"Generated {len(history)} price history records")

    # ---- Build sectors ----
    sectors = build_sectors(assets)
    print(f"Built {len(sectors)} sectors")

    # ---- Build users ----
    users = build_users(assets)
    print(f"Built {len(users)} users")

    # ---- Build watchlists ----
    watchlists = build_watchlists(assets, users)
    print(f"Built {len(watchlists)} watchlists")

    # ---- Write output files ----
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    files = {
        "assets.json": assets,
        "price_history.json": history,
        "sectors.json": sectors,
        "users.json": users,
        "watchlists.json": watchlists,
    }

    for fname, data in files.items():
        path = DATA_DIR / fname
        path.write_text(json.dumps(data, indent=4))
        print(f"Wrote {path} ({len(data)} records)")

    # ---- Also write pristine copies ----
    pristine_dir = DATA_DIR / ".pristine"
    pristine_dir.mkdir(parents=True, exist_ok=True)
    for fname, data in files.items():
        path = pristine_dir / fname
        path.write_text(json.dumps(data, indent=4))
    print(f"Wrote pristine copies to {pristine_dir}")

    print("\nDone! Summary:")
    print(f"  Stocks: {stock_count}")
    print(f"  Crypto: {crypto_count}")
    print(f"  Total assets: {len(assets)}")
    print(f"  Price history records: {len(history)}")
    print(f"  Sectors: {len(sectors)}")
    print(f"  Users: {len(users)}")
    print(f"  Watchlists: {len(watchlists)}")


if __name__ == "__main__":
    main()
