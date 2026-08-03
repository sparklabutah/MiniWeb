# Auto-maintained mapping of macros to verified site UI locations.
# Audited against site templates/routes on 2026-07-08 (full site-by-site pass);
# missing UIs were then built and their macro entries restored the same day.
# Singleton verb-synonym macros merged into canonical names on 2026-07-08.

MACRO_LOCATIONS = {
    "academic-paper-db": {
        "navigate_by_route": [
            "'Scholar Search' page -> click paper title to view paper details",
            "'Scholar Search' page -> click category badge to filter by category",
            "Paper detail page -> click author name to view author page"
        ],
        "search_by_query": [
            "'Scholar Search' page -> 'Search papers...' text field at top"
        ],
        "search_by_semantic": [
            "'Scholar Search' page -> 'Search papers...' field with relevance ranking"
        ],
        "search_by_route": [
            "Category page -> category links in sidebar navigation"
        ],
        "filter_by_semantic": [
            "'Scholar Search' page -> relevance scoring in search results"
        ],
        "filter_by_dropdown": [
            "'Scholar Search' page -> 'Sort' dropdown (Date, Title, Relevance)",
            "'Scholar Search' page -> 'Year' dropdown for date filtering"
        ],
        "sort_by_ranking": [
            "'Scholar Search' page -> 'Sort' dropdown (Date, Title, Relevance)"
        ],
        "extract_by_query": [
            "'Scholar Search' page -> search results showing paper cards with title, authors, abstract"
        ],
        "extract_by_dropdown": [
            "'Scholar Search' page -> 'Year' dropdown filters paper results"
        ],
        "extract_from_table": [
            "Compare page -> side-by-side paper comparison table",
            "Paper detail page -> metadata section with categories and dates"
        ],
        "extract_by_route": [
            "Paper detail page -> full abstract, metadata, author list",
            "Author page -> list of author's papers"
        ],
        "compare_from_table": [
            "Compare page -> two paper selection dropdowns and side-by-side table"
        ],
        "export_by_route": [
            "Paper detail page -> export link with format options"
        ],
        "follow_by_toggle": [
            "Author page -> 'Follow'/'Unfollow' button",
            "Paper detail page -> 'Follow Author' button"
        ],
        "save_by_toggle": [
            "Paper detail page -> 'Save'/'Unsave' button",
            "'My Library' page -> 'Unsave' button on saved papers"
        ],
        "authenticate_by_form": [
            "Login page -> username and password fields"
        ],
        "compute_by_dropdown": [
            "Category page -> 'Compute paper count' category dropdown showing the computed paper count on selection"
        ]
    },
    "agency-portals": {
        "navigate_by_semantic": [
            "'City of Lakeport' page -> 'Search services...' field above Quick Access"
        ],
        "navigate_by_route": [
            "'Services' page -> click service card to view details",
            "'Departments' page -> click department name to view details",
            "'Permits' page -> click permit to view details"
        ],
        "search_by_query": [
            "'City of Lakeport' page -> 'Search services (e.g., building permit, utility bill)...' field"
        ],
        "search_by_semantic": [
            "'City of Lakeport' page -> search field with keyword matching"
        ],
        "filter_by_query": [
            "'Permits' page -> status and type filter dropdowns"
        ],
        "filter_by_dropdown": [
            "'Services' page -> category and department dropdowns",
            "'Permits' page -> status and type dropdowns",
            "'Public Records' page -> record type dropdown"
        ],
        "filter_by_date_range": [
            "'Public Records' page -> date filter fields"
        ],
        "extract_by_query": [
            "Search results showing matching service cards"
        ],
        "extract_by_dropdown": [
            "'Public Records' page -> type dropdown filters the records table"
        ],
        "extract_from_table": [
            "'My Account' dashboard -> recent activity table",
            "'Permits' page -> permits table with status, type, dates",
            "'Public Records' page -> records table",
            "Department detail -> department info section"
        ],
        "extract_by_route": [
            "Service detail page -> full service information",
            "Permit detail page -> permit details",
            "Department detail page -> department info"
        ],
        "verify_by_toggle": [
            "Verify identity page -> code verification form"
        ],
        "submit_by_form": [
            "'Services' page -> search and apply for a service"
        ],
        "apply_by_form": [
            "Apply page -> application form with service fields"
        ],
        "upload_by_upload": [
            "Upload page -> document type dropdown and file input"
        ],
        "select_by_dropdown": [
            "'Schedule Appointment' page -> appointment type and time dropdowns",
            "'Pay Online' page -> payment type dropdown"
        ],
        "book_by_form": [
            "'Schedule Appointment' page -> appointment form with type, date, time"
        ],
        "pay_by_query": [
            "'Pay Online' page -> payment form with type and amount"
        ],
        "authenticate_by_form": [
            "Login page -> username and password fields"
        ],
        "register_by_form": [
            "Register page -> name, email, phone, password fields"
        ],
        "verify_identity_by_code": [
            "Verify Identity page -> 6-digit code input"
        ]
    },
    "ai-chatbots": {
        "navigate_by_route": [
            "Left sidebar -> click conversation title to open chat",
            "Top nav -> 'Chat', 'FAQ', 'Settings' links"
        ],
        "search_by_query": [
            "'FAQ' page -> search bar at top",
            "Knowledge Base page -> search bar",
            "Prompts Library page -> search bar"
        ],
        "search_by_semantic": [
            "Knowledge Base page -> search with category dropdown"
        ],
        "extract_from_table": [
            "'AI Chatbots Hub' home -> 'Recent Conversations' list",
            "Knowledge Base page -> entries table"
        ],
        "extract_by_route": [
            "Chat page -> conversation messages display"
        ],
        "create_by_form": [
            "'+ New Chat' button in sidebar starts a new conversation"
        ],
        "submit_by_form": [
            "Chat page -> message input field and send"
        ],
        "edit_by_query": [
            "Chat page -> inline edit conversation title"
        ],
        "edit_by_form": [
            "Chat page -> edit title form with save button"
        ],
        "delete_from_table": [
            "Chat page -> 'Delete' button per conversation",
            "Sidebar -> 'x' button on each conversation"
        ],
        "configure_by_dropdown": [
            "'Settings' page -> default bot, theme, font size dropdowns"
        ],
        "export_by_dropdown": [
            "'Settings' page -> export type and format dropdowns"
        ],
        "share_by_toggle": [
            "Chat page -> 'Share' button for conversation"
        ],
        "save_by_toggle": [
            "Prompts Library -> 'Save' button on each prompt"
        ],
        "subscribe_by_toggle": [
            "'Settings' page -> subscription radio buttons (free/pro/enterprise)"
        ],
        "authenticate_by_form": [
            "Login page -> username and password fields"
        ],
        "register_by_form": [
            "Register page -> email, password, and confirm fields"
        ],
        "upload_by_upload": [
            "'Settings' page -> 'Import File to Knowledge Base' file input (.txt/.md/.csv/.json) with topic/category fields"
        ]
    },
    "auctions-p2p-marketplaces": {
        "navigate_by_route": [
            "'BidMarket' page -> click listing card to view details",
            "Listing detail -> click seller name to view profile",
            "Category page -> click listing to view details"
        ],
        "search_by_query": [
            "'BidMarket' page -> 'Search for anything...' field at top"
        ],
        "search_by_semantic": [
            "'BidMarket' page -> search field with category/status/sort filters"
        ],
        "filter_by_query": [
            "'BidMarket' page -> search filters listings by keyword"
        ],
        "filter_by_dropdown": [
            "'BidMarket' page -> 'Category' and 'Status' dropdowns"
        ],
        "filter_by_radio": [
            "'BidMarket' page -> condition radio buttons (New, Like New, Good, etc.)"
        ],
        "filter_by_slider": [
            "'BidMarket' page -> 'Max Price' slider below the sort dropdown"
        ],
        "sort_by_ranking": [
            "'BidMarket' page -> 'Sort' dropdown (Ending Soon, Newest, Price, Most Bids)"
        ],
        "extract_by_dropdown": [
            "'BidMarket' page -> filtered results after selecting category/status"
        ],
        "extract_by_route": [
            "Listing detail page -> full listing info, bids, seller info"
        ],
        "compare_from_table": [
            "'Compare' page -> comparison table of selected listings"
        ],
        "create_by_form": [
            "'Sell' page -> listing form (title, description, price, category)"
        ],
        "submit_by_form": [
            "Listing detail -> bid amount input and submit button"
        ],
        "edit_by_form": [
            "Edit listing page -> form with title, description, price, category"
        ],
        "delete_from_table": [
            "Dashboard -> 'Delete' button on each listing",
            "Dashboard -> 'Delete' button on each message"
        ],
        "upload_by_upload": [
            "'Sell' page -> file upload for listing images"
        ],
        "configure_by_slider": [
            "'BidMarket' page -> 'Max Price' slider, 0 to $999"
        ],
        "follow_by_toggle": [
            "Listing detail -> 'Follow Seller' button"
        ],
        "save_by_toggle": [
            "Listing detail -> 'Save'/'Unsave' listing button"
        ],
        "report_by_form": [
            "Listing detail -> 'Report' listing form"
        ],
        "message_from_free_text": [
            "Listing detail -> 'Send Message' form with subject and textarea"
        ],
        "add_by_button": [
            "Listing detail -> 'Add to Watchlist' button"
        ],
        "checkout_by_form": [
            "Listing detail -> 'Buy It Now' button and bid form"
        ],
        "authenticate_by_form": [
            "Login page -> username and password fields"
        ],
        "register_by_form": [
            "Login page -> register form with email, username, password"
        ]
    },
    "banking": {
        "navigate_by_route": [
            "'Welcome, Alex Rivera' dashboard -> click account card for details",
            "'Transactions' page -> click transaction row for details"
        ],
        "search_by_query": [
            "'Transaction History' page -> 'Search transactions by description, category, or reference...' field",
            "Credit Card Transactions -> search bar"
        ],
        "search_by_semantic": [
            "'Transaction History' page -> search with keyword matching"
        ],
        "filter_by_dropdown": [
            "'Transaction History' page -> 'Category' dropdown (Deposit, Dining, Groceries, etc.)",
            "'Transaction History' page -> 'Type' dropdown (Debit, Credit)",
            "'Transaction History' page -> 'Sort' dropdown (Date, Amount, Description)",
            "Credit Card Transactions -> category and status dropdowns"
        ],
        "filter_by_date_range": [
            "'Transaction History' page -> 'From' and 'To' date fields above the table",
            "Credit Card Transactions -> date filters"
        ],
        "sort_by_ranking": [
            "'Transaction History' page -> 'Sort' dropdown (Date, Amount, Description)"
        ],
        "extract_by_query": [
            "'Transaction History' page -> search returns filtered transactions"
        ],
        "extract_from_table": [
            "'Accounts' page -> accounts table (name, type, balance, status)",
            "Account detail -> transactions table",
            "'Transaction History' page -> transactions table",
            "'Pay Bills' page -> bills table",
            "'Payees' page -> payees table",
            "Credit Card pages -> transactions, payments, rewards tables"
        ],
        "extract_by_route": [
            "Account detail page -> account info and transactions"
        ],
        "compute_by_extremum": [
            "'Transaction History' page -> 'Sort' dropdown with amount column"
        ],
        "compute_by_slider": [
            "'Transfer Funds' page -> 'Or use slider' amount slider"
        ],
        "compare_by_date_range": [
            "'Transaction History' page -> 'From' and 'To' date fields for date range filtering"
        ],
        "verify_by_slider": [
            "'Transfer Funds' page -> amount slider synced with amount input"
        ],
        "create_by_form": [
            "'Payees' page -> Add Payee form (name, account, routing fields)"
        ],
        "submit_by_form": [
            "'Transfer Funds' page -> transfer form with from/to account dropdowns, amount, and submit"
        ],
        "edit_by_form": [
            "'Settings' page -> user settings form (email, phone, notifications)",
            "Credit Card Settings -> autopay and payment method forms"
        ],
        "delete_from_table": [
            "'Transaction History' page -> 'Delete' button per transaction row",
            "'Payees' page -> 'Delete' button per payee"
        ],
        "select_from_table": [
            "'Transaction History' page -> flag/select transaction for review"
        ],
        "configure_by_date_range": [
            "'Pay Bills' page -> due date field and auto-pay dropdown"
        ],
        "pay_by_query": [
            "'Pay Bills' page -> select account, enter amount, and submit"
        ],
        "pay_by_form": [
            "'Pay Bills' page -> pay form with account dropdown and amount",
            "'Loans' page -> pay loan form with amount input",
            "Credit Card Payments -> make payment form"
        ],
        "authenticate_by_form": [
            "Login page -> username and password fields"
        ],
        "verify_identity_by_code": [
            "'Verify ID' page -> 6-digit code input form"
        ],
        "export_by_dropdown": [
            "'Transactions' page -> export format dropdown (CSV/JSON) with Export button"
        ]
    },
    "blogs": {
        "navigate_by_route": [
            "'TumblrVibe' page -> click post title to view post",
            "Top nav -> 'Compose', 'Dashboard' links"
        ],
        "search_by_query": [
            "'TumblrVibe' page -> 'Search posts...' field at top"
        ],
        "filter_by_dropdown": [
            "'TumblrVibe' page -> 'Category' dropdown filter",
            "'TumblrVibe' page -> 'Sort' dropdown (Newest, Oldest, Popular)"
        ],
        "filter_by_date_range": [
            "'TumblrVibe' page -> 'From' and 'To' date fields"
        ],
        "sort_by_date_range": [
            "'TumblrVibe' page -> 'Sort' dropdown (Newest, Oldest)"
        ],
        "extract_by_query": [
            "'TumblrVibe' page -> search returns matching post cards"
        ],
        "extract_by_dropdown": [
            "'TumblrVibe' page -> 'Category' dropdown returns filtered posts"
        ],
        "extract_by_route": [
            "Post detail page -> full post content, author, comments"
        ],
        "create_by_form": [
            "'Compose' page -> create post form (title, body, category)"
        ],
        "post_from_free_text": [
            "Post detail page -> comment textarea below article"
        ],
        "follow_by_toggle": [
            "Post detail page -> 'Follow Author' button"
        ],
        "subscribe_by_toggle": [
            "Post detail page -> 'Subscribe to Tag' button"
        ],
        "share_by_dropdown": [
            "Post detail page -> 'Share' button"
        ],
        "save_by_toggle": [
            "Post detail page -> 'Save'/'Unsave' post button"
        ],
        "report_by_form": [
            "Report page -> reason dropdown (spam, harassment, etc.) and details textarea"
        ]
    },
    "books-comics": {
        "navigate_by_route": [
            "'BookVerse' page -> click book card to view details",
            "Category page -> click book to view details",
            "Reader page -> chapter navigation links"
        ],
        "search_by_query": [
            "'BookVerse' page -> 'Search books by title, author, or genre...' field"
        ],
        "search_by_semantic": [
            "'BookVerse' page -> search field with autosuggest"
        ],
        "filter_by_dropdown": [
            "'BookVerse' page -> 'Category', 'Min Rating', and 'Price' dropdowns"
        ],
        "filter_by_slider": [
            "Book detail -> progress slider in reader view"
        ],
        "sort_by_ranking": [
            "'BookVerse' page -> 'Sort' dropdown (Newest, Title A-Z, Top Rated, Price)"
        ],
        "extract_by_route": [
            "Book detail page -> full book info, reviews, chapters"
        ],
        "select_by_dropdown": [
            "Reader page -> chapter dropdown to jump to a specific chapter"
        ],
        "post_from_free_text": [
            "Book detail page -> write review textarea"
        ],
        "rate_by_slider": [
            "Book detail page -> rating slider (1-5 stars)"
        ],
        "follow_by_toggle": [
            "Book detail page -> 'Follow Author' button"
        ],
        "subscribe_by_toggle": [
            "Book detail page -> 'Subscribe to Category' button"
        ],
        "save_by_toggle": [
            "Book detail page -> 'Save'/'Unsave' book button",
            "'My Library' page -> 'Unsave' button on saved books"
        ],
        "add_by_button": [
            "Book detail page -> 'Add to Cart' button"
        ],
        "checkout_by_form": [
            "Checkout page -> account type dropdown, email, and submit"
        ]
    },
    "brokerage": {
        "navigate_by_route": [
            "'All Securities' section -> click ticker row to view details",
            "'Portfolio' page -> click holding to view ticker details"
        ],
        "search_by_query": [
            "'TradeVista' page -> 'Search' field in the top bar"
        ],
        "search_by_semantic": [
            "Search with keyword matching across ticker names"
        ],
        "filter_by_dropdown": [
            "'All Securities' -> 'All Sectors' dropdown (Technology, Healthcare, etc.)",
            "'All Securities' -> 'All Types' dropdown (stock, crypto, futures, etc.)",
            "Options page -> underlying and type dropdowns",
            "'History' page -> status dropdown (open, filled, cancelled)"
        ],
        "filter_by_slider": [
            "'All Securities' section -> 'Max Price' slider, below the sort dropdown"
        ],
        "filter_by_date_range": [
            "'History' page -> 'From' and 'To' date fields above the orders table"
        ],
        "sort_by_ranking": [
            "'All Securities' -> sort dropdown (Market Cap, Price, Top Gainers, Name A-Z)"
        ],
        "extract_from_table": [
            "'All Securities' section -> tickers table (symbol, price, change, volume)",
            "'Portfolio' page -> holdings table (symbol, shares, value, P&L)",
            "'Lists' page -> watchlist table",
            "'History' page -> orders table",
            "Options page -> options chain table",
            "Compare page -> comparison table"
        ],
        "extract_by_route": [
            "Ticker detail page -> price chart, fundamentals, news"
        ],
        "extract_by_extremum": [
            "'Portfolio' page -> positions list with price and P&L columns"
        ],
        "compute_by_extremum": [
            "Ticker detail page -> price chart with period buttons (1D, 1W, 1M, 3M, 1Y)"
        ],
        "submit_by_form": [
            "'Trade' page -> trade form with symbol, shares, order type, and submit"
        ],
        "select_by_dropdown": [
            "'Trade' page -> 'Symbol' dropdown, 'Order Type' dropdown (Market, Limit, Stop Loss), 'Pay With' dropdown"
        ],
        "follow_by_toggle": [
            "Ticker detail page -> 'Add to Watchlist'/'Remove' button"
        ],
        "save_by_toggle": [
            "'Lists' page -> toggle watchlist inclusion"
        ],
        "pay_by_query": [
            "'Trade' page -> 'Pay With' dropdown (Checking Account, Credit Card)"
        ],
        "cancel_by_form": [
            "'History' page -> 'Cancel' button on each open order"
        ],
        "authenticate_by_form": [
            "Login page -> username and password fields"
        ],
        "compute_by_dropdown": [
            "'All Securities' section -> sector and type filter dropdowns"
        ],
        "verify_identity_by_code": [
            "'Login' page -> 2FA verification code input step shown after credentials"
        ],
        "select_by_radio": [
            "'Trade' page -> 'Time in Force' radio buttons (Day / Good till canceled)"
        ]
    },
    "business-company": {
        "navigate_by_semantic": [
            "Search page -> full-text search across all 'Apex Dynamics' content"
        ],
        "navigate_by_route": [
            "'Featured Products' section -> click product for details (MeridianFlow, MeridianVault, etc.)",
            "'Latest Insights' section -> click blog post for details",
            "'Meet Our Team' section -> click member for details",
            "'Careers' page -> click job listing for details"
        ],
        "search_by_query": [
            "Header -> 'Search...' field at top of every page"
        ],
        "search_by_semantic": [
            "Search page -> 'Search products, blog posts, team members...' field"
        ],
        "extract_by_dropdown": [
            "'Products' page -> category dropdown filters products",
            "'Careers' page -> department dropdown filters jobs"
        ],
        "extract_from_table": [
            "'Meet Our Team' section -> team members grid; 'Featured Products' -> products grid"
        ],
        "extract_by_route": [
            "Product detail page -> product information",
            "Job detail page -> description and requirements",
            "Team member page -> bio, role, contact"
        ],
        "submit_by_form": [
            "'Contact' page -> contact form with subject dropdown, name, email, message"
        ],
        "subscribe_by_toggle": [
            "'Subscribe to Our Newsletter' section -> email input and 'Subscribe' button"
        ]
    },
    "calendar-todo": {
        "navigate_by_route": [
            "Calendar grid -> click event to view details",
            "Top bar -> 'Day' and 'Week' view links",
            "Top bar -> user name links to Dashboard"
        ],
        "search_by_query": [
            "Top bar -> 'Search events...' field"
        ],
        "filter_by_dropdown": [
            "Left panel -> 'Category' dropdown (Work, Personal, Health)",
            "Left panel -> priority dropdown (High, Medium, Low)",
            "Left panel -> 'User' dropdown (Alex Rivera, Priya Sharma, etc.)",
            "Left panel -> sort dropdown (Date, Title, Priority)"
        ],
        "filter_by_date_range": [
            "Left panel -> 'From' and 'To' date fields + 'Apply Date Range' button"
        ],
        "sort_by_ranking": [
            "Left panel -> sort dropdown (Date, Title, Priority)"
        ],
        "extract_by_query": [
            "Search returns matching events in the calendar"
        ],
        "extract_by_dropdown": [
            "Category/priority filters return matching events"
        ],
        "extract_by_route": [
            "Event detail page -> full event info with attendees"
        ],
        "extract_by_date_range": [
            "Day/Week view -> events filtered by the selected date window"
        ],
        "create_by_form": [
            "'New Event' form -> 'Add title', start/end times, Category, Calendar, Priority, Location"
        ],
        "create_by_dropdown": [
            "'New Event' form -> 'Category' dropdown, 'Calendar' dropdown, 'Priority' dropdown"
        ],
        "submit_by_form": [
            "'New Event' form -> title input at top of the form"
        ],
        "submit_by_date_range": [
            "'New Event' form -> 'Start' and 'End' date/time inputs"
        ],
        "edit_by_form": [
            "Edit event page -> form with title, description, date, time, category, status"
        ],
        "edit_by_date_range": [
            "Edit event page -> date and time inputs for rescheduling"
        ],
        "delete_from_table": [
            "Event detail page -> 'Delete Event' button"
        ],
        "export_by_dropdown": [
            "Calendar header -> 'CSV', 'ICS', 'JSON' export links"
        ],
        "share_by_toggle": [
            "Event detail page -> 'Share' button (copies link)"
        ],
        "invite_by_form": [
            "Event detail page -> invite form with email input"
        ]
    },
    "cloud-dev-consoles": {
        "navigate_by_route": [
            "'Instances' page -> click instance row to view details",
            "'Services' page -> click service to view details"
        ],
        "search_by_query": [
            "'Instances' page -> 'Search instances...' field",
            "'Services' page -> search input",
            "'Logs' page -> search input"
        ],
        "search_by_semantic": [
            "'Console Home' page -> global search field -> grouped results page across services, instances, databases, functions, buckets, IAM, endpoints, alerts, logs"
        ],
        "filter_by_query": [
            "All list pages -> search text input filters items by name"
        ],
        "filter_by_dropdown": [
            "'Instances' page -> 'Status' dropdown (Running, Stopped), 'Region' dropdown, 'Sort' dropdown",
            "'Services' page -> status and sort dropdowns",
            "'Databases' page -> engine, status, sort dropdowns",
            "'Functions' page -> runtime, status, sort dropdowns",
            "'IAM' page -> role, status, sort dropdowns",
            "'Alerts' page -> status, severity, category dropdowns",
            "'API Gateway' -> method, status, sort dropdowns",
            "'Billing' page -> month and category dropdowns",
            "'Logs' page -> level and category dropdowns"
        ],
        "filter_by_checkbox": [
            "'Instances' page -> 'Environment' checkboxes (Production, Staging, Development)"
        ],
        "filter_by_date_range": [
            "'Logs' page -> date range filters"
        ],
        "sort_by_ranking": [
            "All list pages -> sort dropdown (Name, Cost, Type, etc.)"
        ],
        "extract_by_query": [
            "Search across any service list returns filtered results"
        ],
        "extract_by_dropdown": [
            "'Billing' page -> month/category dropdown returns filtered billing data"
        ],
        "extract_from_table": [
            "'Instances' page -> instances table (name, type, status, region, cost)",
            "'Services' page -> services table",
            "'Databases' page -> databases table",
            "'Functions' page -> functions table",
            "'IAM' page -> users table",
            "'Alerts' page -> alerts table",
            "'API Gateway' -> endpoints table",
            "'Billing' page -> billing table",
            "'Metrics' page -> metrics table",
            "'Logs' page -> logs table",
            "Storage page -> buckets table"
        ],
        "extract_by_route": [
            "Instance detail page -> full instance info table",
            "Service detail page -> service info and endpoints"
        ],
        "compute_by_extremum": [
            "'Billing' page -> billing table with month and category filters"
        ],
        "compute_by_slider": [
            "'Metrics' page -> CPU threshold slider for filtering"
        ],
        "verify_by_dropdown": [
            "'Services' page -> 'Status' filter dropdown (All/Active/Warning/Stopped) + 'Apply' to verify which services are in a given state"
        ],
        "submit_by_form": [
            "'Services' page -> search field with filter dropdowns and 'Apply' button"
        ],
        "delete_from_table": [
            "'Instances' page -> 'Delete' button per instance row"
        ],
        "select_by_dropdown": [
            "Filter dropdowns serve as selection for specific resources"
        ],
        "select_from_table": [
            "Instance/Service tables -> click row to view details"
        ],
        "authenticate_by_form": [
            "Login page -> username and password fields"
        ],
        "create_by_form": [
            "'Instances' page -> 'Launch instance' form (name, type, region, OS, environment)",
            "'Functions' page -> 'Create function' form (name, runtime, handler, memory, timeout)"
        ],
        "edit_by_form": [
            "Instance detail page -> 'Edit Configuration' section with name/type/vCPUs/memory/OS fields"
        ],
        "edit_by_query": [
            "'Metrics' page -> CPU threshold slider with instance filter dropdown"
        ]
    },
    "cloud-storage-file-transfer": {
        "navigate_from_table": [
            "'MeridianCloud' page -> click file name in file list to view details",
            "Folder page -> click file in folder listing"
        ],
        "navigate_by_route": [
            "Left sidebar -> 'Projects', 'Personal', 'Shared', 'Archives' folder links",
            "'MeridianCloud' page -> click folder to open it"
        ],
        "search_by_query": [
            "'MeridianCloud' page -> 'Search in Drive' field at top"
        ],
        "search_by_semantic": [
            "'MeridianCloud' page -> 'Search in Drive' field with file results"
        ],
        "filter_by_dropdown": [
            "'MeridianCloud' page -> 'Type' dropdown (Documents, Spreadsheets, Images, Code, etc.)",
            "'MeridianCloud' page -> sort dropdown (Last modified, Name, File size, Date created)"
        ],
        "filter_by_date_range": [
            "'MeridianCloud' page -> 'From' and 'To' date fields above file list"
        ],
        "sort_by_ranking": [
            "'MeridianCloud' page -> sort dropdown (Last modified, Name, File size, Date created)"
        ],
        "extract_by_semantic": [
            "'MeridianCloud' page -> search returns matching files with type and sort options"
        ],
        "extract_by_dropdown": [
            "'MeridianCloud' page -> 'Type' dropdown returns filtered files"
        ],
        "extract_by_route": [
            "File detail page -> file metadata, sharing info, transfer records"
        ],
        "create_by_form": [
            "'New folder' button -> folder name input ('Untitled folder' placeholder)"
        ],
        "edit_by_dropdown": [
            "Upload modal -> file type dropdown; main view -> type filter dropdown"
        ],
        "edit_by_form": [
            "File detail page -> sharing form ('Enter email to invite')"
        ],
        "delete_from_table": [
            "File rows -> delete action (moves to trash)",
            "Trash page -> permanent delete buttons"
        ],
        "configure_by_toggle": [
            "File detail page -> 'Share' button and star toggle (filled/empty star)"
        ],
        "export_by_dropdown": [
            "File detail page -> 'Download' button at top of detail view"
        ],
        "share_by_toggle": [
            "File detail page -> 'Share' button with permission controls"
        ],
        "save_by_toggle": [
            "File rows -> star/unstar toggle button (filled/empty star icon)",
            "Starred page -> unstar button"
        ],
        "invite_by_form": [
            "File detail page -> 'Enter email to invite' input and 'Invite' button",
            "File detail page -> 'Share' button for sharing with other users"
        ],
        "authenticate_by_form": [
            "Login page -> username and password fields"
        ],
        "upload_by_upload": [
            "'File upload' button -> file name, type dropdown, size, and upload"
        ]
    },
    "code-editor-execution": {
        "navigate_from_table": [
            "'CodeRunner' gallery -> click snippet card (Hello World, Fibonacci, etc.)",
            "Dashboard -> click saved snippet to view"
        ],
        "navigate_by_route": [
            "Top nav -> 'Gallery', 'Editor' links; user name -> Dashboard",
            "'CodeRunner' gallery -> 'Run in Editor' or 'View' links per snippet"
        ],
        "search_by_query": [
            "'CodeRunner' gallery -> 'Search snippets by title, description, or category...' field"
        ],
        "extract_from_table": [
            "Dashboard -> saved snippets table (title, language, difficulty)"
        ],
        "create_by_code": [
            "'Editor' page -> code editor textarea with syntax highlighting"
        ],
        "edit_by_form": [
            "'Editor' page -> code content textarea with run/save buttons"
        ],
        "configure_by_slider": [
            "'Editor' page -> font size slider in editor settings"
        ],
        "share_by_route": [
            "'Editor' page -> 'Share Snippet' button; Snippet page -> 'Share' button"
        ]
    },
    "comparison-aggregators": {
        "navigate_by_route": [
            "'PhoneCompare' page -> click phone card to view specs",
            "Phone detail page -> click brand name in breadcrumb to browse brand's phones"
        ],
        "search_by_query": [
            "'PhoneCompare' page -> 'Search phones...' field at top"
        ],
        "search_by_semantic": [
            "'PhoneCompare' page -> search with brand/OS/sort filter dropdowns"
        ],
        "filter_by_dropdown": [
            "'PhoneCompare' page -> brand and OS dropdowns in the filter bar"
        ],
        "filter_by_toggle": [
            "Phone detail page -> 'Favorite'/'Unfavorite' and 'Add/Remove from Compare' toggles"
        ],
        "filter_by_slider": [
            "'PhoneCompare' page -> 'Max Price' slider, in the filter bar",
            "'PhoneCompare' page -> 'Min Battery' slider, below the price slider"
        ],
        "sort_by_ranking": [
            "'PhoneCompare' page -> sort dropdown (Newest, Name A-Z, Price, Battery)"
        ],
        "extract_by_dropdown": [
            "'PhoneCompare' page -> brand/OS dropdown returns filtered phone list"
        ],
        "extract_from_table": [
            "'PhoneCompare' page -> phone specs cards",
            "Phone detail page -> specifications table",
            "'Compare' page -> side-by-side comparison table",
            "Brand page -> brand's phones list"
        ],
        "extract_by_route": [
            "Phone detail page -> full specifications, reviews, pricing"
        ],
        "extract_by_ranking": [
            "'PhoneCompare' page -> phone cards with rating/price, sortable via sort dropdown"
        ],
        "extract_by_extremum": [
            "'PhoneCompare' page -> sort by price/rating to find extremes"
        ],
        "compute_from_table": [
            "'Compare' page -> side-by-side comparison of two selected phones"
        ],
        "compare_by_dropdown": [
            "'Compare' page -> phone1 and phone2 dropdowns, then side-by-side table"
        ],
        "compare_from_table": [
            "'Compare' page -> comparison table of selected phones"
        ],
        "select_from_table": [
            "Phone detail page -> 'Add to Compare' button"
        ],
        "select_by_extremum": [
            "'PhoneCompare' page -> checkbox on each phone card; 'Compare' page -> phone selection dropdowns"
        ],
        "subscribe_by_toggle": [
            "Phone detail page -> 'Favorite'/'Unfavorite' toggle button"
        ],
        "save_by_toggle": [
            "Phone detail page -> 'Add to Favorites' button",
            "'Dashboard' page -> 'Remove from Favorites' button"
        ],
        "filter_by_checkbox": [
            "'PhoneCompare' page -> 'Features:' checkboxes (NFC, GPS, Dual SIM, Fingerprint) in the filter toolbar"
        ]
    },
    "conference-review-submission": {
        "navigate_by_route": [
            "'PeerPortal' page -> click venue name to view papers",
            "Venue page -> click paper title to view details"
        ],
        "search_by_query": [
            "Venue page -> 'Search by title or keyword...' field at top of paper list"
        ],
        "search_by_semantic": [
            "Venue page -> search with keyword matching across paper titles"
        ],
        "extract_by_query": [
            "Search returns matching papers with titles and scores"
        ],
        "extract_from_table": [
            "Stats page -> statistics tables (acceptance rates, score distributions)"
        ],
        "extract_by_route": [
            "Paper detail page -> full paper info, reviews, scores"
        ],
        "create_by_form": [
            "Review page -> title input, recommendation/confidence dropdowns, comments textarea"
        ],
        "submit_by_form": [
            "Paper detail page -> 'Bid'/'Unbid' button to declare review interest"
        ],
        "edit_by_query": [
            "Paper detail page -> 'Bid'/'Unbid' toggle button"
        ],
        "select_by_dropdown": [
            "Review form -> recommendation dropdown (accept, weak_accept, etc.)",
            "Review form -> confidence dropdown (high, medium, low)"
        ],
        "upload_by_upload": [
            "Console page -> paper upload form accepting .pdf, .doc, .docx, .tex files"
        ],
        "post_from_free_text": [
            "Review form -> review text textarea, strengths/weaknesses fields"
        ],
        "authenticate_by_form": [
            "Login page -> username and password fields"
        ],
        "register_by_form": [
            "Login page -> username and password form for authentication"
        ],
        "delete_from_table": [
            "Paper detail page -> 'Withdraw Submission' button in the Submission Details metadata grid"
        ]
    },
    "converters-calculators": {
        "navigate_by_route": [
            "'CalcTools' page -> click tool card (Length, Weight, Temperature, BMI, Mortgage, Tip)"
        ],
        "search_by_query": [
            "'CalcTools' page -> converter category links for navigation"
        ],
        "search_by_semantic": [
            "'CalcTools' page -> category navigation with direct links"
        ],
        "extract_from_table": [
            "Converter page -> conversion result display with from/to dropdowns"
        ],
        "compare_from_table": [
            "Dashboard page -> saved conversions list for comparison"
        ],
        "compute_by_query": [
            "Calculator page -> expression input for computation"
        ],
        "submit_by_form": [
            "Converter/Calculator -> save conversion result form"
        ],
        "compute_by_dropdown": [
            "Converter page -> from-unit and to-unit dropdowns (Length, Weight, Temperature, etc.)",
            "Base Converter -> from-base and to-base dropdowns (2-36)"
        ]
    },
    "course-sites-classrooms": {
        "navigate_by_semantic": [
            "'EduPortal LMS' page -> course listings with navigation links"
        ],
        "navigate_by_route": [
            "'Welcome back, Alex!' page -> click course card to view course",
            "Course page -> click assignment to view details"
        ],
        "extract_by_query": [
            "Course page -> assignments, discussions, and gradebook links"
        ],
        "extract_by_semantic": [
            "Course page -> course content sections with materials"
        ],
        "extract_by_route": [
            "Course detail page -> course info, assignments, materials",
            "Assignment detail page -> assignment instructions and submission form"
        ],
        "create_by_form": [
            "Discussions page -> new discussion form (title and body textarea)"
        ],
        "submit_by_form": [
            "Assignment page -> submit assignment form (text content)",
            "Assignment page -> grade submission form (score input)"
        ],
        "submit_by_route": [
            "Assignment page -> form submit to turn in assignment"
        ],
        "upload_by_upload": [
            "Assignment page -> file upload for assignment submission"
        ],
        "post_from_free_text": [
            "Discussions page -> reply form textarea"
        ],
        "post_by_route": [
            "Discussions page -> post new discussion thread"
        ],
        "search_by_query": [
            "'EduPortal LMS' dashboard -> search input with 'Search' button filtering the course catalog by title, code, or department"
        ],
        "extract_by_date_range": [
            "Assignment page -> 'From'/'To' date inputs with 'Filter by date' button filtering the submissions table"
        ],
        "play_by_route": [
            "Course page -> lecture lesson title links that load the chosen lecture into the Lecture Player section"
        ],
        "play_by_playback": [
            "Course page -> 'Lecture Player' section with Play/Pause toggle and elapsed-time counter"
        ],
        "follow_by_toggle": [
            "Course page -> enrollment toggle button ('Enroll in Course' / 'Enrolled — Leave Course') in the course header",
            "'EduPortal LMS' page -> 'View & Enroll' link on course cards"
        ],
        "join_by_toggle": [
            "Course page -> enroll/unenroll toggle button in the course header"
        ]
    },
    "crm": {
        "navigate_from_table": [
            "'Contacts' page -> click contact row to view details",
            "'Companies' page -> click company row to view details",
            "'Deals' page -> click deal row to view details"
        ],
        "navigate_by_route": [
            "'Pipeline Overview' dashboard -> click section card to navigate"
        ],
        "search_by_query": [
            "'Contacts' page -> search input field",
            "'Companies' page -> search input field",
            "'Deals' page -> 'Search deals...' text input + Filter button in the pipeline toolbar"
        ],
        "search_by_semantic": [
            "'Contacts' page -> 'Search contacts by name, email, or title...' field with company filter"
        ],
        "filter_by_semantic": [
            "'Contacts' page -> search filters by name, email, or title"
        ],
        "filter_by_dropdown": [
            "'Contacts' page -> company dropdown filter",
            "'Companies' page -> industry dropdown filter",
            "'Deals' page -> stage dropdown (prospecting, qualification, proposal, etc.), owner dropdown",
            "'Activities' page -> type dropdown (call, meeting, email, note, task)"
        ],
        "sort_by_ranking": [
            "'Pipeline Overview' -> 'Sort Deals' dropdown (Amount High-Low, Low-High, Close Date, Name A-Z)"
        ],
        "extract_by_semantic": [
            "'Companies' page -> 'Search companies...' field with industry filter"
        ],
        "extract_by_dropdown": [
            "'Deals' page -> stage dropdown returns filtered deals"
        ],
        "extract_from_table": [
            "'Contacts' page -> contacts table (name, company, email, phone)",
            "'Companies' page -> companies table (name, industry, size)",
            "Company detail -> contacts and deals tables",
            "Contact detail -> deals and activities",
            "'Activities' page -> activities table"
        ],
        "extract_by_route": [
            "Contact detail page -> contact info, deals, activities",
            "Company detail page -> company info, contacts, deals",
            "Deal detail page -> deal info, history, activities"
        ],
        "compute_by_dropdown": [
            "'Deals' page -> stage filter dropdown for viewing deals by pipeline stage"
        ],
        "create_by_form": [
            "'Activities' page -> create activity form (type dropdown, description, date)"
        ],
        "create_by_dropdown": [
            "'Activities' page -> activity type dropdown (call, meeting, email, note, task)"
        ],
        "submit_by_form": [
            "'Activities' page -> create activity form with contact, deal, type, date, and description"
        ],
        "edit_by_form": [
            "Deal detail page -> update stage form (stage dropdown, submit)",
            "Deal detail page -> log activity form (type dropdown, notes, submit)"
        ],
        "delete_from_table": [
            "'Contacts' page -> 'Delete' button per contact row"
        ],
        "select_by_dropdown": [
            "'Activities' page -> type dropdown for new activity"
        ],
        "select_from_table": [
            "Tables -> click row to select and view details"
        ],
        "export_by_dropdown": [
            "'Pipeline Overview' dashboard -> 'Export CSV' link in Deals section header"
        ],
        "filter_by_date_range": [
            "'Activities' page -> From/To date inputs + Filter button in the toolbar"
        ]
    },
    "crowdfunding-donations": {
        "navigate_by_semantic": [
            "'FundSpark' page -> 'Search campaigns...' field with status/sort dropdowns"
        ],
        "navigate_by_route": [
            "'FundSpark' page -> click campaign card to view details",
            "Category tab -> click campaign for details"
        ],
        "search_by_query": [
            "'FundSpark' page -> 'Search campaigns...' field above campaign grid"
        ],
        "search_by_semantic": [
            "'Fund what matters to you' page -> search field at top"
        ],
        "filter_by_query": [
            "'FundSpark' page -> search filters campaigns by keyword"
        ],
        "filter_by_dropdown": [
            "'FundSpark' page -> 'All Statuses' dropdown (Active, Funded, Expired, Cancelled)",
            "'FundSpark' page -> sort dropdown (Trending, Newest, Most Funded, Most Backed, Ending Soon)"
        ],
        "sort_by_dropdown": [
            "'FundSpark' page -> sort dropdown (Trending, Newest, Most Funded, Most Backed, Ending Soon)"
        ],
        "sort_by_date_range": [
            "'FundSpark' page -> sort dropdown for ordering campaigns"
        ],
        "extract_by_query": [
            "Search returns matching campaign cards"
        ],
        "extract_by_dropdown": [
            "'FundSpark' page -> status/sort dropdown returns filtered campaigns"
        ],
        "extract_by_route": [
            "Campaign detail page -> funding progress, updates, backers"
        ],
        "compute_by_dropdown": [
            "'FundSpark' page -> status/sort dropdown with campaign funding progress bars"
        ],
        "create_by_form": [
            "'Start a Project' page -> campaign form (title, description, goal, category, dates)"
        ],
        "submit_by_form": [
            "Campaign detail -> 'Select this reward' -> checkout form (name, email, shipping for physical tiers, anonymous + consent checkboxes)"
        ],
        "post_from_free_text": [
            "Campaign detail page -> post update form textarea"
        ],
        "react_by_toggle": [
            "Campaign detail page -> 'Share' button"
        ],
        "subscribe_by_toggle": [
            "Campaign detail page -> 'Subscribe to Updates' button"
        ],
        "share_by_dropdown": [
            "Campaign detail page -> 'Share' button for sharing via link"
        ],
        "save_by_toggle": [
            "'FundSpark' page -> campaign card star/bookmark toggle"
        ],
        "add_by_button": [
            "Campaign detail page -> 'Select this reward' button on each tier"
        ],
        "checkout_by_form": [
            "Checkout page ('Select this reward' / 'Pledge without a reward') -> backer info, conditional shipping address for physical rewards, payment radios, consent checkbox"
        ],
        "pay_by_form": [
            "Checkout page -> 'Complete pledge' -> 2FA payment verification"
        ],
        "select_by_radio": [
            "Checkout page -> 'Payment method' radio cards (Checking account / Credit card)"
        ],
        "authenticate_by_form": [
            "Login page -> username and password fields"
        ],
        "register_by_form": [
            "Login page -> authentication form"
        ]
    },
    "dating": {
        "navigate_by_route": [
            "'Spark' page -> view profile cards",
            "'Matches' page -> click match to open conversation",
            "Top nav -> 'Discover', 'Matches', 'Profile' links"
        ],
        "search_by_query": [
            "Profiles page -> 'Search' bar (matches name, username, bio, location, interests)"
        ],
        "search_by_proximity": [
            "Profiles page -> 'Within (miles)' distance filter (requires login; distances shown per profile)"
        ],
        "filter_by_dropdown": [
            "'Spark' page -> 'Looking for' dropdown in the Discovery Filters bar",
            "Profiles page -> filter form with gender and looking_for dropdowns"
        ],
        "filter_by_checkbox": [
            "Profiles page -> interest checkboxes (hiking, cooking, reading, etc.) — any-match"
        ],
        "filter_by_date_range": [
            "'Spark' page -> 'Joined From' and 'To' date fields in filter bar"
        ],
        "sort_by_ranking": [
            "'Spark' page -> sort dropdown (Age Low-High, Age High-Low, Name A-Z, Newest)",
            "Profiles page -> 'Sort by' dropdown (Name, Age, Newest members)"
        ],
        "sort_by_proximity": [
            "Profiles page -> 'Sort by' dropdown -> 'Nearest' (requires login)"
        ],
        "extract_by_query": [
            "Profiles page -> search returns matching profiles"
        ],
        "extract_by_semantic": [
            "Profile detail page -> full bio with interests and preferences"
        ],
        "extract_by_dropdown": [
            "Profiles page -> filter dropdown returns filtered profiles"
        ],
        "compare_from_table": [
            "Profiles page -> browse all profiles with filter controls"
        ],
        "create_by_form": [
            "'Edit Profile' page -> 'Bio' textarea"
        ],
        "submit_by_route": [
            "'Edit Profile' page -> form submit to update profile"
        ],
        "edit_by_query": [
            "'Edit Profile' page -> 'Location', 'Interests', 'Bio' fields, 'Looking for' and 'Gender Preference' dropdowns"
        ],
        "configure_by_dropdown": [
            "'Edit Profile' page -> 'Looking for' dropdown, 'Gender Preference' dropdown"
        ],
        "upload_by_upload": [
            "Conversation page -> paperclip photo attach in message compose (filename stored on message, rendered as attachment chip)"
        ],
        "react_by_toggle": [
            "'Spark' page -> heart button on profile cards",
            "'Likes You' page -> 'Like back' / 'Pass' buttons on pending likes"
        ],
        "react_by_gesture": [
            "'Spark' page -> heart (like) and X (pass) buttons on profile cards"
        ],
        "follow_by_toggle": [
            "'Spark' page -> heart button on profile cards"
        ],
        "save_by_toggle": [
            "Profile detail page -> Like/Pass buttons for saving interest"
        ],
        "message_from_free_text": [
            "Conversation page -> message textarea and send button"
        ],
        "authenticate_by_form": [
            "Login page -> username and password fields"
        ],
        "report_by_form": [
            "Profile detail page -> report form (reason input + 'Report' button) under Like/Pass"
        ],
        "block_by_toggle": [
            "Profile detail page -> Block/Blocked toggle button in the safety-actions row"
        ],
        "register_by_form": [
            "Register page (/register, linked from login) -> signup form: username, password, name, age, gender, location, bio, interests, looking_for, gender preference"
        ]
    },
    "design-creative": {
        "navigate_by_route": [
            "'My Projects' page -> click project card to view details",
            "'DesignFlow' home -> click template to view details"
        ],
        "search_by_query": [
            "'DesignFlow' page -> 'Search templates... (e.g. instagram, logo, poster)' field",
            "'Assets' page -> search bar"
        ],
        "search_by_semantic": [
            "'DesignFlow' page -> search with category links (Social Media, Poster, Logo, etc.)"
        ],
        "filter_by_dropdown": [
            "'My Projects' page -> sort dropdown (newest, oldest, name, modified)"
        ],
        "filter_by_chip": [
            "'DesignFlow' page -> category links: 'Social Media', 'Presentation', 'Poster', 'Logo', etc.",
            "'DesignFlow' page -> category links for selecting template types"
        ],
        "sort_by_ranking": [
            "'DesignFlow' page -> 'Sort' dropdown (Most Popular, Name A-Z, Newest)"
        ],
        "extract_by_image": [
            "Editor page -> canvas area with 'Search assets...' input"
        ],
        "create_by_form": [
            "'My Projects' page -> 'Create Project' form with name input"
        ],
        "create_from_table": [
            "Template page -> 'Use This Template' button"
        ],
        "edit_by_form": [
            "Project detail -> update form with name and status dropdown"
        ],
        "delete_from_table": [
            "Editor page -> canvas elements with Remove/Delete actions"
        ],
        "select_by_dropdown": [
            "'Project' page -> status dropdown (Draft, Completed)"
        ],
        "configure_by_dropdown": [
            "Project page -> status dropdown for project configuration"
        ],
        "select_by_radio": [
            "Editor page -> tool buttons (Select, Text, Shape, Image) in toolbar"
        ],
        "play_by_playback": [
            "Editor page -> canvas preview area with design elements"
        ],
        "upload_by_upload": [
            "'Assets' page -> 'Upload Asset' file input"
        ],
        "post_from_free_text": [
            "Project page -> 'Save Changes' button and update form"
        ],
        "react_by_toggle": [
            "Template page -> 'Favorite'/'Unfavorite' toggle button"
        ],
        "follow_by_toggle": [
            "Template page -> 'Favorite' toggle for tracking designs"
        ],
        "save_by_toggle": [
            "Template page -> 'Favorite' button toggle"
        ],
        "invite_by_form": [
            "Project page -> 'Enter email to invite' input and 'Invite' button"
        ]
    },
    "dictionaries-language-tools": {
        "navigate_by_route": [
            "'WordRef Dictionary' page -> click word to view definition",
            "Top nav -> 'Home', 'Browse A-Z' links"
        ],
        "search_by_query": [
            "'WordRef Dictionary' page -> 'Search for a word...' field at center"
        ],
        "search_by_semantic": [
            "'WordRef Dictionary' page -> search field with autofocus"
        ],
        "extract_from_free_text": [
            "Search returns word definitions and related information"
        ],
        "extract_by_semantic": [
            "Search results display definitions, synonyms, and usage examples"
        ],
        "extract_by_route": [
            "Word detail page -> definition, pronunciation, examples, etymology"
        ],
        "play_by_route": [
            "Word detail page -> pronunciation information display"
        ],
        "save_by_toggle": [
            "Word detail page -> 'Save to Vocabulary' button",
            "Dashboard -> saved words with unsave option"
        ],
        "translate_by_query": [
            "'WordRef Dictionary' page -> 'Search for a word...' field for lookups"
        ]
    },
    "documentation-api-docs": {
        "navigate_by_query": [
            "'Search' page -> search form navigates to matching doc page"
        ],
        "navigate_by_semantic": [
            "'MeridianFlow Docs' page -> 'Search documentation...' field in header"
        ],
        "navigate_by_route": [
            "'All Pages' list -> click page title to view documentation",
            "Top nav -> 'API Reference', 'Changelog' links"
        ],
        "search_by_query": [
            "Header -> 'Search documentation...' field at top",
            "'Search' page -> search form"
        ],
        "search_by_semantic": [
            "'Search' page -> 'Search by keyword, topic, or API endpoint...' field"
        ],
        "extract_by_query": [
            "Search returns matching doc sections with highlights"
        ],
        "extract_from_table": [
            "Page detail -> API parameter tables and code examples"
        ],
        "extract_by_route": [
            "Page detail -> full documentation content",
            "'API Reference' page -> endpoint documentation",
            "'Changelog' page -> version history"
        ],
        "copy_by_route": [
            "Page detail -> code block copy buttons"
        ]
    },
    "documents": {
        "navigate_by_route": [
            "'DocEdit' page -> click document name to view",
            "Left sidebar -> folders (Engineering, Product, Meeting Notes, etc.), 'Starred', 'Trash' links"
        ],
        "search_by_query": [
            "'DocEdit' page -> 'Search documents...' field at top of file list"
        ],
        "search_by_semantic": [
            "'DocEdit' page -> search field with sort dropdown"
        ],
        "filter_by_date_range": [
            "'DocEdit' page -> 'From' and 'To' date fields above the document list"
        ],
        "sort_by_ranking": [
            "'DocEdit' page -> 'Sort' dropdown (Last modified, Date created, Title A-Z)"
        ],
        "create_by_query": [
            "'+ New Document' page -> title, content, owner dropdown, folder dropdown"
        ],
        "create_from_table": [
            "'+ New Document' page -> form with title, owner, folder, and content textarea"
        ],
        "edit_by_query": [
            "Editor page -> edit document title and body textarea"
        ],
        "delete_from_table": [
            "'Trash' page -> permanent delete button per document",
            "Document view -> Delete button in the toolbar (owner only) moving the document to trash"
        ],
        "upload_by_upload": [
            "'DocEdit' page -> 'Upload File' button in sidebar"
        ],
        "save_by_toggle": [
            "Editor page -> 'Star'/'Unstar' toggle button in header",
            "'Starred' page -> unstar button"
        ],
        "translate_by_query": [
            "Editor page -> document content textarea for editing text"
        ],
        "invite_by_form": [
            "Editor page -> share form with user and permission dropdowns"
        ]
    },
    "e-commerce": {
        "pay_by_form": [
            "'Checkout' page -> shipping address fields (full name, street, city, state, ZIP), shipping method radios (Standard/Express/Overnight), 'Pay with' dropdown, and 'Place Your Order' button"
        ],
        "navigate_by_route": [
            "'ShopHub' page -> click product card to view details"
        ],
        "search_by_query": [
            "'ShopHub' page -> 'Search products...' field at top"
        ],
        "search_by_semantic": [
            "'ShopHub' page -> 'Search products...' field with results"
        ],
        "filter_by_dropdown": [
            "'ShopHub' page -> 'All Categories', 'All Brands', 'Any Rating' dropdowns in sidebar"
        ],
        "filter_by_checkbox": [
            "'ShopHub' page -> category checkboxes in left sidebar filter panel"
        ],
        "filter_by_slider": [
            "'ShopHub' page -> 'Max Price' slider in left sidebar filter panel"
        ],
        "sort_by_ranking": [
            "'ShopHub' page -> 'Sort by' dropdown (Relevance, Price Low-High, Price High-Low, Avg. Rating, Most Reviews)"
        ],
        "extract_by_dropdown": [
            "'ShopHub' page -> category/brand dropdown returns filtered products"
        ],
        "extract_by_route": [
            "Product detail page -> full product info, reviews, pricing"
        ],
        "extract_by_ranking": [
            "'ShopHub' page -> sort dropdown for ranking products by rating or price"
        ],
        "extract_by_extremum": [
            "'ShopHub' page -> sort dropdown allows price sorting to find extremes"
        ],
        "compare_by_dropdown": [
            "Product detail page -> specs display with 'Add to Cart' and 'Wishlist' buttons"
        ],
        "verify_by_dropdown": [
            "Product detail page -> product info with category, rating, and specs"
        ],
        "select_by_dropdown": [
            "Product detail -> quantity dropdown, size/variant dropdown"
        ],
        "configure_by_slider": [
            "'ShopHub' page -> 'Min $' input and 'Max Price' slider for price range"
        ],
        "save_by_toggle": [
            "Product detail -> 'Add to Wishlist' button",
            "'Wishlist' page -> 'Remove from Wishlist' button"
        ],
        "add_by_button": [
            "Product detail and listing pages -> 'Add to Cart' button"
        ],
        "checkout_by_form": [
            "'Checkout' page -> checkout form with shipping address, shipping method, and payment fields"
        ],
        "redeem_by_code": [
            "'Cart' page -> promo code entry input with 'Apply' button in the order summary showing applied discount"
        ],
        "cancel_by_form": [
            "'Orders' page -> 'Cancel Order' button on each non-shipped order"
        ]
    },
    "email": {
        "navigate_by_semantic": [
            "'WebMail' page -> 'Search mail...' field linked to search page"
        ],
        "navigate_from_table": [
            "'WebMail' page -> click email row to read message"
        ],
        "navigate_by_route": [
            "Left sidebar -> 'Inbox', 'Sent', 'Drafts', 'Trash', 'Spam' folder links",
            "Top nav -> 'Compose', 'Contacts' links"
        ],
        "search_by_query": [
            "'WebMail' page -> 'Search mail...' field at top",
            "Search page -> search form"
        ],
        "filter_by_dropdown": [
            "Message detail -> move to folder dropdown"
        ],
        "filter_by_radio": [
            "Message detail -> 'Mark read'/'Mark unread' toggle button"
        ],
        "filter_by_date_range": [
            "'WebMail' page -> 'From' and 'To' date fields in toolbar above email list"
        ],
        "sort_by_ranking": [
            "'WebMail' page -> sort dropdown (Sort: Date, Sort: Subject, Sort: From) in toolbar"
        ],
        "extract_by_semantic": [
            "Search page -> search results with email matches"
        ],
        "extract_by_dropdown": [
            "Folder navigation returns emails in selected folder"
        ],
        "extract_from_table": [
            "'WebMail' page -> email list (sender, subject, date, star icon)"
        ],
        "extract_by_route": [
            "Message detail page -> full email body, headers, attachments"
        ],
        "create_by_form": [
            "'Compose' page -> 'To', 'Cc', 'Subject' fields and body textarea"
        ],
        "submit_by_form": [
            "'Compose' page -> 'Recipients (e.g. user@example.com)' field"
        ],
        "edit_by_form": [
            "Message detail -> label form, move form"
        ],
        "delete_from_table": [
            "'WebMail' page -> trash icon per email row",
            "Message detail -> 'Delete' button"
        ],
        "select_from_table": [
            "'WebMail' page -> checkbox per email row for bulk actions"
        ],
        "configure_by_dropdown": [
            "Message detail -> move to folder form and label management"
        ],
        "upload_by_upload": [
            "'Compose' page -> 'Attach' file input"
        ],
        "save_by_toggle": [
            "'WebMail' page -> star button per email row",
            "Message detail -> star button"
        ],
        "report_by_form": [
            "Message detail -> report form at bottom (reason dropdown: Spam/Phishing/Other, optional details, 'Report' button); moves message to Spam"
        ],
        "block_by_dropdown": [
            "Message detail -> 'More' dropdown in toolbar -> 'Block sender' (adds sender to blocked list, moves message to Spam)"
        ],
        "authenticate_by_form": [
            "Login page -> username and password fields"
        ],
        "search_by_dropdown": [
            "'Search' page -> folder dropdown (All folders/Inbox/Sent/Drafts/Trash/Spam) scoping search results"
        ]
    },
    "flights-hotels": {
        "navigate_by_route": [
            "Flights page -> click flight row to view details",
            "Hotels page -> click hotel to view details",
            "Bookings page -> click booking to view details"
        ],
        "search_by_query": [
            "'Where do you want to go?' page -> 'From' and 'To' origin/destination dropdowns and search button"
        ],
        "search_by_route": [
            "'SkyLodge' home -> flight search directs to results page",
            "'SkyLodge' home -> search form submits to flights or hotels results"
        ],
        "filter_by_dropdown": [
            "Flights tab -> 'Airline', 'Cabin Class' (Economy, Business, First), 'Travelers' dropdowns",
            "Hotels tab -> city, min_stars, min_rating, amenity dropdowns"
        ],
        "filter_by_checkbox": [
            "Flights tab -> 'Stops' checkboxes (Nonstop, 1 Stop)"
        ],
        "filter_by_slider": [
            "Flights tab -> 'Max Price' slider, below the search fields",
            "Hotels tab -> 'Max Price' slider, below hotel filters",
            "Flights page -> max price input for filtering by maximum price"
        ],
        "filter_by_date_range": [
            "Flights tab -> 'Departure Date' input",
            "Hotels tab -> check-in date input",
            "Hotels tab -> check-in/check-out date inputs"
        ],
        "sort_by_ranking": [
            "Flights page -> sort dropdown (price, duration, departure, airline)",
            "Hotels page -> sort dropdown (price, rating, stars, name)"
        ],
        "extract_by_dropdown": [
            "Filter dropdowns return filtered flights/hotels lists"
        ],
        "extract_by_ranking": [
            "Flights page -> sort dropdown for ranking by price/time"
        ],
        "extract_by_extremum": [
            "Flights page -> sort to find cheapest; Hotels page -> sort and rating filters"
        ],
        "compare_by_dropdown": [
            "Flights page -> flight list for comparison; Hotels page -> hotel list with ratings"
        ],
        "compare_from_table": [
            "Flights page -> flights table with price, duration, airline columns"
        ],
        "verify_from_free_text": [
            "Flight/Hotel detail -> booking form with 'Travelers' and account type"
        ],
        "submit_by_form": [
            "Flight/Hotel detail -> 'Book Now' button with travelers and account selection"
        ],
        "select_by_ranking": [
            "Flights page -> sortable flight list for price-based selection"
        ],
        "checkout_by_form": [
            "Flight/Hotel detail -> booking form with travelers, account type, submit"
        ],
        "book_by_form": [
            "Flight detail -> Book Flight form (travelers, payment, submit)",
            "Hotel detail -> Book Hotel form (nights, travelers, submit)"
        ],
        "pay_by_form": [
            "Flight/Hotel detail -> booking form with account type payment selection"
        ],
        "cancel_by_form": [
            "Booking detail -> 'Cancel Booking' button with confirmation"
        ],
        "select_by_dropdown": [
            "Flight/Hotel detail -> 'Travelers'/nights dropdowns in booking form"
        ]
    },
    "forms-surveys": {
        "navigate_by_semantic": [
            "'FormFlow' page -> 'Search forms' field with tab filtering"
        ],
        "navigate_by_route": [
            "'FormFlow' page -> click form card to view form",
            "'FormFlow' page -> 'Blank form' and 'From template' quick-start cards"
        ],
        "extract_by_query": [
            "'FormFlow' page -> search filters forms showing title, response count, status"
        ],
        "extract_by_semantic": [
            "'FormFlow' page -> search with tab filters (All, Active, Drafts, Closed)"
        ],
        "extract_by_dropdown": [
            "'FormFlow' page -> status tabs (All, Active, Drafts, Closed) filter forms"
        ],
        "extract_by_route": [
            "Form detail page -> form fields and responses count",
            "Results page -> per-field statistics table (Summary and Individual tabs)"
        ],
        "create_by_form": [
            "'Blank form' page -> form builder (title, description, dynamic field rows)"
        ],
        "submit_by_form": [
            "Respond page -> dynamic form fields (text, radio, checkbox, select, textarea) and 'Submit' button",
            "Respond page -> dropdown field type in form responses"
        ],
        "submit_by_route": [
            "Respond page -> fill out and submit form response"
        ],
        "edit_by_query": [
            "'Blank form' page -> form builder with title, description, field types, options"
        ],
        "delete_from_table": [
            "'FormFlow' page -> form card management actions"
        ],
        "select_by_dropdown": [
            "Form builder -> field type dropdown (text, textarea, rating, radio, checkbox, etc.)"
        ],
        "share_by_toggle": [
            "'FormFlow' page -> 'Share' button on each form card (copies URL, shows 'Copied!')"
        ],
        "submit_by_ranking": [
            "Respond page -> ranking field with up/down reorder buttons per item and live rank numbers"
        ],
        "upload_by_upload": [
            "Form detail page -> 'Attachments' file input with 'Upload File' button"
        ]
    },
    "forums": {
        "navigate_by_semantic": [
            "'ForumHub' page -> 'Search ForumHub' field in header"
        ],
        "navigate_by_route": [
            "'ForumHub' page -> click post title to view post and comments",
            "'ForumHub' page -> click subreddit link (r/memes, r/aww, etc.) to view community",
            "Top nav -> 'Messages' link; post form -> 'Submit' link"
        ],
        "search_by_query": [
            "'ForumHub' page -> 'Search ForumHub' field at top",
            "Search page -> search form"
        ],
        "search_by_semantic": [
            "'Search' page -> 'Search ForumHub' field"
        ],
        "filter_by_dropdown": [
            "'ForumHub' page -> 'Subreddit' dropdown"
        ],
        "filter_by_date_range": [
            "'ForumHub' page -> 'From' and 'To' date fields below sort controls"
        ],
        "sort_by_ranking": [
            "'ForumHub' page -> 'Hot', 'New', 'Top' sort tabs above posts"
        ],
        "extract_by_semantic": [
            "'Search' page -> search results list"
        ],
        "extract_by_dropdown": [
            "'ForumHub' page -> 'Subreddit' dropdown returns filtered posts"
        ],
        "extract_by_route": [
            "Post detail page -> full post content and comments thread",
            "User profile page -> user posts, karma, activity"
        ],
        "create_by_form": [
            "'Create a post' page -> 'Community' dropdown, 'Title' input, 'Body' textarea"
        ],
        "submit_by_form": [
            "'Create a post' page -> post creation form and submit"
        ],
        "submit_by_route": [
            "'Create a post' page -> form submit to create new post"
        ],
        "edit_by_form": [
            "Post detail page -> inline edit textarea for post body"
        ],
        "delete_from_table": [
            "Post detail page -> Delete action on post"
        ],
        "react_by_toggle": [
            "Post detail -> upvote/downvote arrow buttons",
            "Comments -> upvote/downvote arrow buttons"
        ],
        "follow_by_toggle": [
            "User profile page -> 'Follow' button"
        ],
        "join_by_toggle": [
            "Subreddit page -> 'Join' button for joining/leaving community"
        ],
        "share_by_dropdown": [
            "Post detail page -> 'Share' button with 'Copy Link' and 'Crosspost' options"
        ],
        "save_by_toggle": [
            "'ForumHub' page -> 'Save' button on each post"
        ],
        "report_by_form": [
            "Post detail page -> 'Report' action"
        ],
        "block_by_toggle": [
            "User profile page -> 'Block' button"
        ],
        "message_from_free_text": [
            "'Messages' page -> compose message form (recipient, subject, body)"
        ],
        "authenticate_by_form": [
            "Login page -> username and password fields"
        ],
        "register_by_form": [
            "Register page -> username and password fields"
        ]
    },
    "handwritten-notes-whiteboards": {
        "configure_by_slider": [
            "Note editor -> brush size slider in the drawing toolbar (1-10)"
        ],
        "navigate_by_route": [
            "'All Notes' list -> click note to open it",
            "Top nav -> '+ New Note' button; sidebar -> tag links (work, personal, ideas, etc.)"
        ],
        "search_by_query": [
            "'NoteCanvas' page -> 'Search notes...' field at top"
        ],
        "search_by_semantic": [
            "'NoteCanvas' page -> search field with tag and sort filters"
        ],
        "create_by_form": [
            "New note page -> title input and text editor textarea"
        ],
        "create_by_toggle": [
            "Note page -> mode toggle buttons in toolbar (Text, Draw, Both)"
        ],
        "create_by_drag": [
            "Note page -> drawing canvas with pen/eraser tools and brush size slider"
        ],
        "submit_by_form": [
            "Note page -> title input and content textarea for composing notes"
        ],
        "edit_by_form": [
            "Edit note page -> form with title, content, tags, color, notebook"
        ],
        "edit_by_ranking": [
            "'All Notes' list -> sort and tag filter controls"
        ],
        "edit_by_drag": [
            "Note page -> drawing canvas with pen and eraser tools"
        ],
        "edit_by_image": [
            "Note page -> drawing canvas area for visual content"
        ],
        "delete_from_table": [
            "Note detail page -> 'Delete Note' button"
        ],
        "upload_by_upload": [
            "'NoteCanvas' page -> 'Upload Image' button in sidebar"
        ],
        "save_by_toggle": [
            "Note page -> pinned checkbox for pinning/unpinning notes"
        ],
        "invite_by_form": [
            "Note page -> 'Invite by email' input and 'Invite' button in toolbar"
        ],
        "navigate_by_pan_zoom": [
            "Note editor (whiteboard canvas) -> zoom in/out with % readout, four pan arrows, and Reset View in the toolbar"
        ],
        "select_by_radio": [
            "Note page -> mode buttons: Text, Draw, Text+Draw"
        ]
    },
    "health-fitness-tracking": {
        "navigate_by_route": [
            "'Exercise' page -> click workout to view details"
        ],
        "search_by_query": [
            "'Exercise' page -> 'Type' dropdown, 'From'/'To' date fields, and 'Filter' button"
        ],
        "search_by_semantic": [
            "'Exercise' page -> type filter and date range for searching workouts"
        ],
        "filter_by_dropdown": [
            "'Exercise' page -> 'Type' dropdown (All Types, Basketball, Hiking, Running, etc.)"
        ],
        "filter_by_date_range": [
            "'Reports' page -> 'From' and 'To' date fields in filter form",
            "'Exercise' page -> 'From' and 'To' date fields"
        ],
        "sort_by_ranking": [
            "Dashboard -> sort dropdown (Sort: Date, Sort: Calories, Sort: Duration, Sort: Type, Sort: Heart Rate)"
        ],
        "extract_by_dropdown": [
            "'Exercise' page -> type dropdown returns filtered workouts"
        ],
        "extract_from_table": [
            "'Exercise' page -> workouts table (date, type, duration, calories, heart rate)",
            "'Reports' page -> daily stats table"
        ],
        "extract_by_route": [
            "Workout detail page -> full workout info, exercises, metrics"
        ],
        "extract_by_date_range": [
            "'Exercise' page -> 'From' and 'To' date fields filter workout history"
        ],
        "compute_by_dropdown": [
            "'Exercise' page -> 'Type' dropdown for viewing stats by workout type"
        ],
        "compute_by_extremum": [
            "'Reports' page -> workout statistics summary cards (averages, totals)"
        ],
        "compute_by_slider": [
            "'Goals' page -> 'Days Above Threshold' panel: metric dropdown + threshold slider + 'Compute' button"
        ],
        "verify_by_slider": [
            "'Goals' page -> 'Tolerance' slider + 'Verify Goals' button showing on/off-track verdict per goal"
        ],
        "create_by_form": [
            "'+ Add Exercise' page -> log workout form with date, type, duration, calories, notes"
        ],
        "submit_by_form": [
            "'Food Diary' page -> 'Search foods...' input with 'Servings' field and 'Log Food' button"
        ],
        "delete_from_table": [
            "'Food Diary' page -> 'x' button on each food entry; Dashboard -> logged items"
        ],
        "select_from_table": [
            "'Exercise' page -> workout list with type and date filters"
        ],
        "configure_by_slider": [
            "'Goals' page -> 'Daily Targets' panel: steps/calories/water/sleep/heart-rate sliders + 'Save Targets' button"
        ]
    },
    "health-portals": {
        "navigate_by_route": [
            "'Appointments' page -> click appointment to view details",
            "'Records' page -> click record to view details",
            "'Messages' page -> click message to view thread"
        ],
        "filter_by_date_range": [
            "'Appointments' page -> date range filter inputs"
        ],
        "extract_by_query": [
            "Record detail page -> full medical record display"
        ],
        "extract_by_dropdown": [
            "'Schedule Appointment' page -> provider/department dropdown filters"
        ],
        "extract_from_table": [
            "'Appointments' page -> appointments table (date, provider, status)",
            "'Billing' page -> billing table (date, amount, status)",
            "Record detail -> vitals and lab results table"
        ],
        "extract_by_route": [
            "Record detail page -> vitals, lab results, diagnoses",
            "Appointment detail page -> appointment info"
        ],
        "compare_by_date_range": [
            "'Appointments' page -> 'From' and 'To' date fields for date range filtering"
        ],
        "submit_by_form": [
            "'Schedule Appointment' page -> appointment form with provider, type, date, time"
        ],
        "submit_by_route": [
            "'Prescriptions' page -> 'Request Refill' button on each prescription"
        ],
        "edit_by_form": [
            "'Schedule Appointment' page -> editable form fields; Register page -> profile form"
        ],
        "message_from_free_text": [
            "'Send Message' page -> recipient dropdown, subject field, body textarea"
        ],
        "book_by_form": [
            "'Schedule Appointment' page -> book appointment with provider, date, time"
        ],
        "book_by_date_range": [
            "'Schedule Appointment' page -> date and time inputs"
        ],
        "pay_by_form": [
            "Pay page -> pay bill form with amount, card, submit"
        ],
        "cancel_by_form": [
            "Cancel page -> reason textarea and submit"
        ],
        "authenticate_by_form": [
            "Login page -> username and password fields"
        ],
        "register_by_form": [
            "Register page -> first/last name, username, email, date of birth, gender, phone fields"
        ],
        "verify_identity_by_code": [
            "Verify page -> 6-digit verification code input"
        ],
        "search_by_query": [
            "'Medical Records' page -> keyword search input + 'Search' button above the records list"
        ],
        "search_by_semantic": [
            "'Medical Records' page -> natural-language 'Smart Search' input returning relevance-ranked records"
        ],
        "export_by_dropdown": [
            "'Billing' page -> 'Export billing records' format dropdown (CSV/JSON) + Export button"
        ],
        "upload_by_upload": [
            "'Send Message' page -> 'Attach a Document for Your Care Team' file input with description and Upload button"
        ]
    },
    "instant-messaging": {
        "navigate_by_semantic": [
            "'QuickChat' page -> 'Search or start new chat' field at top of conversation list"
        ],
        "navigate_by_route": [
            "'QuickChat' page -> click conversation in sidebar to open chat",
            "Top nav -> 'Contacts' link"
        ],
        "search_by_query": [
            "'QuickChat' page -> 'Search or start new chat' field filters conversations"
        ],
        "search_by_dropdown": [
            "Chat sidebar -> search field for finding specific chats"
        ],
        "filter_by_date_range": [
            "'QuickChat' page -> 'From' and 'To' date fields below search"
        ],
        "sort_by_ranking": [
            "'QuickChat' page -> sort dropdown (Sort: Recent, Sort: Name, Sort: Unread)"
        ],
        "extract_by_query": [
            "Search returns matching conversations with preview text"
        ],
        "extract_by_route": [
            "Chat view -> messages for selected conversation"
        ],
        "create_by_form": [
            "Chat panel -> 'Type a message' input with 'Send' button"
        ],
        "delete_from_table": [
            "Chat panel -> 'x' delete button per message"
        ],
        "post_from_free_text": [
            "Chat panel -> message input box and send"
        ],
        "share_by_toggle": [
            "Chat panel -> 'Share' button in header (copies link, shows 'Copied!')"
        ],
        "invite_by_form": [
            "'Contacts' page -> 'Add contact by email or username' input and 'Invite' button"
        ],
        "message_from_free_text": [
            "Chat panel -> message text input and send"
        ],
        "authenticate_by_form": [
            "Login page -> username and password fields"
        ],
        "edit_by_form": [
            "Conversation page -> pencil button on sent messages opens inline edit form (text input + Save/Cancel)"
        ],
        "upload_by_upload": [
            "Conversation page -> paperclip file input in the message input area"
        ],
        "follow_by_toggle": [
            "'QuickChat' page -> pin toggle button (pushpin icon) on each conversation row"
        ],
        "join_by_route": [
            "Conversation page -> 'Join Group' link in the group chat header that adds you to the group"
        ],
        "save_by_toggle": [
            "Conversation page -> star toggle (hollow/filled) in each message's meta row"
        ],
        "report_by_form": [
            "Conversation page -> flag button on each message opens inline report form (reason + Report)"
        ],
        "block_by_toggle": [
            "'Contacts' page -> Block/Blocked toggle button on each contact card"
        ]
    },
    "insurance-loans": {
        "navigate_by_route": [
            "'Your Policies' page -> click policy ID to view details",
            "'Claims' page -> click claim to view details",
            "'Loans' page -> click loan to view details"
        ],
        "search_by_query": [
            "'Claims' page -> date range and status/type dropdowns; 'Policies' page -> type/status filters"
        ],
        "search_by_semantic": [
            "'Claims' page -> search/filter controls for finding claims"
        ],
        "filter_by_dropdown": [
            "'Your Policies' page -> 'Policy Type' and 'Status' dropdowns",
            "'Claims' page -> status and type dropdowns",
            "'Loans' page -> type and status dropdowns",
            "'Payments' page -> type dropdown"
        ],
        "filter_by_date_range": [
            "'Welcome back, Alex' dashboard -> 'From' and 'To' date fields in transactions section",
            "'Claims' page -> date range fields",
            "'Payments' page -> date range fields"
        ],
        "sort_by_ranking": [
            "Dashboard -> 'Sort Loans' dropdown (Balance High-Low, Balance Low-High, Interest Rate)"
        ],
        "extract_by_toggle": [
            "Policy detail page -> full policy information with coverage details"
        ],
        "extract_from_table": [
            "'Your Policies' page -> policies table (type, status, premium, coverage)",
            "'Claims' page -> claims table (status, amount, date)",
            "'Loans' page -> loans table (type, balance, rate, payment)",
            "Loan detail -> amortization table",
            "'Payments' page -> payments table (date, amount, status)",
            "Policy detail -> coverage details table"
        ],
        "extract_by_route": [
            "Policy detail page -> coverage, premium, beneficiaries",
            "Claim detail page -> claim info, timeline, documents",
            "Loan detail page -> balance, rate, payment schedule"
        ],
        "extract_by_ranking": [
            "'Your Policies' page -> policy list with type and status filters"
        ],
        "extract_by_extremum": [
            "'Your Policies' page -> policies with type/status filters for coverage levels"
        ],
        "compare_by_dropdown": [
            "'Your Policies' page -> filtered policy list for comparison"
        ],
        "compare_from_table": [
            "'Your Policies' page -> policy cards with type, status, coverage for comparison"
        ],
        "verify_by_toggle": [
            "Policy Document page -> 'Print / Save as PDF' button"
        ],
        "edit_by_query": [
            "Policy detail page -> management controls"
        ],
        "select_by_dropdown": [
            "'File Claim' page -> policy number dropdown to select which policy"
        ],
        "select_by_ranking": [
            "'Your Policies' page -> policy list sortable by type and status"
        ],
        "select_by_extremum": [
            "'Your Policies' page -> type and status dropdowns for narrowing selection"
        ],
        "export_by_dropdown": [
            "Dashboard -> 'Export CSV' link in policies section"
        ],
        "upload_by_upload": [
            "'File Claim' page -> file upload accepting .pdf, .jpg, .png, .doc files"
        ],
        "pay_by_form": [
            "'Payments' page -> payment records with date range and type filters"
        ],
        "submit_by_form": [
            "'File Claim' page -> claim form (policy, type, description, amount, date, submit)"
        ],
        "compute_from_table": [
            "'Your Policies' page -> policy list with coverage amounts for computing totals"
        ],
        "compute_by_extremum": [
            "'Payments' page -> payment records with date range filters"
        ],
        "configure_by_toggle": [
            "Policy detail page -> 'Policy Settings & Notifications' card with Autopay/Paperless/Email/SMS toggle switches"
        ],
        "create_by_query": [
            "'File Claim' page -> claim form with policy dropdown, date, location, type, description"
        ],
        "sign_by_signature": [
            "Policy Document page -> 'Print / Save as PDF' button"
        ]
    },
    "job-sites": {
        "navigate_by_route": [
            "'All Jobs' page -> click job card to view details",
            "Top nav -> 'Saved Jobs', 'Applications', 'Job Alerts' links"
        ],
        "search_by_query": [
            "'JobQuest' page -> 'Job title, keywords, or company' field",
            "'JobQuest' page -> 'City, state, or remote' location field"
        ],
        "search_by_semantic": [
            "'All Jobs' page -> keyword and location inputs with filter sidebar"
        ],
        "filter_by_query": [
            "'All Jobs' page -> search filters jobs by keyword"
        ],
        "filter_by_semantic": [
            "'All Jobs' page -> keyword search filters by title, keywords, or company"
        ],
        "filter_by_dropdown": [
            "'All Jobs' page -> 'All Companies' dropdown"
        ],
        "filter_by_radio": [
            "'All Jobs' page -> job type radio buttons: 'Full-time', 'Part-time', 'Contract', 'Internship'"
        ],
        "filter_by_slider": [
            "'All Jobs' page -> 'Minimum Salary' and 'Maximum Salary' sliders in sidebar"
        ],
        "filter_by_date_range": [
            "'All Jobs' page -> 'From' and 'To' posted date fields"
        ],
        "sort_by_ranking": [
            "'All Jobs' page -> 'Sort by' dropdown (Date Newest, Salary, Company, Title)"
        ],
        "extract_by_query": [
            "Search returns matching job cards with title, company, salary"
        ],
        "extract_by_semantic": [
            "Search results showing job cards with title, company, location, salary"
        ],
        "extract_by_dropdown": [
            "'All Jobs' page -> company dropdown returns filtered job list"
        ],
        "extract_by_route": [
            "Job detail page -> full description, requirements, salary, company info"
        ],
        "create_by_form": [
            "'Job Alerts' page -> create alert form with name, query, location, salary inputs"
        ],
        "submit_by_form": [
            "Apply page -> application form with resume upload and cover letter textarea"
        ],
        "upload_by_upload": [
            "Apply page -> resume upload accepting .pdf, .doc, .docx, .txt files",
            "Profile page -> resume upload form"
        ],
        "follow_by_toggle": [
            "Job detail page -> 'Follow' button for company"
        ],
        "subscribe_by_toggle": [
            "'Job Alerts' page -> alert subscribe/unsubscribe toggle"
        ],
        "save_by_toggle": [
            "Job detail page -> 'Save Job' button"
        ],
        "apply_by_form": [
            "Apply page -> application form with name, email, resume, cover letter, submit"
        ]
    },
    "live": {
        "navigate_by_semantic": [
            "'StreamHub' page -> 'Search streams...' field with category/status/streamer/sort dropdowns"
        ],
        "navigate_by_route": [
            "'All Streams' section -> click stream card to view",
            "Top nav -> 'Clips' link",
            "'StreamHub' page -> click streamer name to view channel"
        ],
        "search_by_query": [
            "'StreamHub' page -> 'Search streams...' field; Clips page -> channel dropdown"
        ],
        "filter_by_dropdown": [
            "'StreamHub' page -> 'Category', 'Status', 'Streamer', 'Sort By' dropdowns",
            "'Clips' page -> channel dropdown"
        ],
        "sort_by_dropdown": [
            "'StreamHub' page -> 'Sort By' dropdown (Default, Most Viewed, Newest, Oldest, Longest)"
        ],
        "play_by_timestamp": [
            "Stream page -> seek bar and 'Jump to' mm:ss input below the player (plays from the chosen timestamp)"
        ],
        "play_by_playback": [
            "Stream page -> video player with click-to-play, elapsed counter, and seek bar"
        ],
        "post_from_free_text": [
            "Stream page -> 'Send a message...' chat input"
        ],
        "follow_by_toggle": [
            "Channel page -> 'Follow'/'Unfollow' button"
        ],
        "share_by_toggle": [
            "Stream page -> 'Share' button below player (copies link, shows 'Copied!')"
        ],
        "subscribe_by_toggle": [
            "Channel page -> 'Subscribe'/'Unsubscribe' button"
        ],
        "join_by_toggle": [
            "Stream page -> chat area with message input and 'Chat' submit button"
        ],
        "pay_by_dropdown": [
            "Stream page -> 'Cheer' amount dropdown + 'Cheer' button under the chat input (pays channel points, posts a highlighted chat message)"
        ],
        "redeem_by_dropdown": [
            "Channel page -> 'Channel Point Rewards' cards with 'Redeem' buttons"
        ],
        "authenticate_by_form": [
            "Login page -> username and password fields"
        ],
        "register_by_form": [
            "Register page -> email, username, password fields"
        ],
        "report_by_form": [
            "Stream page -> 'Report Stream' form below the stream tags (reason dropdown + description + Report button)"
        ]
    },
    "map-services": {
        "navigate_by_route": [
            "'CascadiaMaps' page -> click place marker to view details",
            "Search results -> click place to view details"
        ],
        "search_by_query": [
            "'CascadiaMaps' page -> 'Search CascadiaMaps' field at top",
            "'CascadiaMaps' page -> search results with clickable place entries"
        ],
        "search_by_semantic": [
            "'CascadiaMaps' page -> 'Search CascadiaMaps' field with map view"
        ],
        "search_by_pan_zoom": [
            "'CascadiaMaps' page -> map view with search overlay"
        ],
        "search_by_proximity": [
            "'CascadiaMaps' page -> search returns nearby places"
        ],
        "filter_by_dropdown": [
            "'CascadiaMaps' page -> sort dropdown (Default, Rating, Name A-Z)"
        ],
        "filter_by_slider": [
            "'CascadiaMaps' page -> 'Min Rating' slider in filter bar (0 to 5 stars)"
        ],
        "sort_by_ranking": [
            "'CascadiaMaps' page -> sort dropdown (Default, Rating, Name A-Z) next to category"
        ],
        "extract_by_query": [
            "Search returns matching places with name, category, rating"
        ],
        "extract_by_route": [
            "Place detail page -> address, hours, rating, reviews, photos"
        ],
        "compute_by_route": [
            "'Get Directions' page -> 'From' and 'To' inputs with mode buttons (Driving, Cycling, Walking, Transit)"
        ],
        "compare_by_route": [
            "Compare page -> select two places via form, then comparison table"
        ],
        "create_by_form": [
            "Place detail page -> review form with rating dropdown and text textarea"
        ],
        "submit_by_form": [
            "Place detail page -> review form with rating and text fields"
        ],
        "post_from_free_text": [
            "Place detail page -> write review form (rating dropdown, comment textarea)"
        ],
        "configure_by_dropdown": [
            "'Settings' page -> 'Default Travel Mode' dropdown (Driving, Cycling, Walking, Transit) and 'Distance Units' dropdown"
        ],
        "export_by_route": [
            "Route detail page -> route info with distance and duration"
        ],
        "save_by_query": [
            "'Saved' page -> saved places list",
            "Place detail page -> 'Save Place' button"
        ],
        "route_by_query": [
            "'Get Directions' page -> 'Starting point or address' and 'Destination or address' inputs with 'Get Directions' button"
        ],
        "route_by_route": [
            "'Get Directions' page -> route display with waypoints"
        ],
        "filter_by_toggle": [
            "'CascadiaMaps' page -> 'Open now' toggle pill in the filter bar (green when active)"
        ],
        "select_by_radio": [
            "'Get Directions' page -> 'Mode' buttons: Driving, Cycling, Walking, Transit"
        ]
    },
    "multimedia-posting": {
        "navigate_by_route": [
            "'Feed' -> click post to view details",
            "'Feed' -> click username to view profile"
        ],
        "search_by_query": [
            "'Explore' page -> 'Search posts by caption, tags, or location...' field"
        ],
        "search_by_semantic": [
            "'Explore' page -> search with sort dropdown"
        ],
        "sort_by_dropdown": [
            "'Explore' page -> sort dropdown (newest, popular, oldest)"
        ],
        "extract_by_semantic": [
            "'Explore' page -> search results showing posts with captions and tags"
        ],
        "extract_by_dropdown": [
            "'Explore' page -> type filtering for posts"
        ],
        "extract_by_route": [
            "Post detail page -> caption, comments, likes, media"
        ],
        "create_by_form": [
            "'+ Create' page -> type dropdown, caption textarea, tags, location, file upload"
        ],
        "edit_by_form": [
            "'+ Create' page -> caption textarea, location, tags, type dropdown"
        ],
        "post_from_free_text": [
            "Post detail page -> comment textarea",
            "'+ Create' page -> post creation with file upload, caption, location, tags"
        ],
        "select_by_dropdown": [
            "'+ Create' page -> post type dropdown (photo, video, carousel)"
        ],
        "configure_by_toggle": [
            "'Settings' page -> dark mode, notifications, privacy toggles"
        ],
        "play_by_dropdown": [
            "'Stories' page -> story display with playback controls"
        ],
        "play_by_playback": [
            "'Stories' page -> story playback with prev/next navigation"
        ],
        "upload_by_upload": [
            "'+ Create' page -> file upload area (click to select images/videos)"
        ],
        "react_by_toggle": [
            "Post detail -> heart (like) toggle button"
        ],
        "follow_by_dropdown": [
            "Profile page -> 'Follow' button on user profiles"
        ],
        "follow_by_toggle": [
            "Profile page -> 'Follow'/'Unfollow' button"
        ],
        "subscribe_by_toggle": [
            "'Settings' page -> notifications toggle"
        ],
        "share_by_dropdown": [
            "Post detail page -> 'Share' button with 'Copy Link' and 'Send as DM' options"
        ],
        "save_by_toggle": [
            "Post detail -> 'Save'/'Unsave' bookmark button"
        ],
        "report_by_form": [
            "Post detail page -> 'Report' action"
        ],
        "block_by_toggle": [
            "Post detail page -> block/unblock user action"
        ],
        "delete_from_table": [
            "Post detail page -> 'Delete Post' entry in the more (...) actions menu (author only)"
        ],
        "export_by_dropdown": [
            "'Settings' page -> 'Export Your Data' format dropdown (JSON/CSV) with download"
        ],
        "filter_by_chip": [
            "'Explore' page -> post type filter chips (Photos, Videos, Carousels)"
        ]
    },
    "music": {
        "navigate_by_route": [
            "'SoundWave' home -> click artist card to view profile",
            "'Browse' page -> click album to view details",
            "Search results -> click track to view details",
            "Top nav -> 'Library', 'Playlists', 'Browse' links"
        ],
        "search_by_query": [
            "Header -> 'Search artists, albums, tracks...' field"
        ],
        "search_by_semantic": [
            "'SoundWave' home -> search with full search form"
        ],
        "search_by_route": [
            "Search page -> results split by type (artists, albums, tracks)"
        ],
        "filter_by_dropdown": [
            "'Browse' page -> 'Genre' dropdown for filtering"
        ],
        "sort_by_ranking": [
            "'Browse' page -> sort dropdown (name, listeners, newest)"
        ],
        "extract_by_query": [
            "Search returns matching artists, albums, and tracks"
        ],
        "create_by_form": [
            "Create Playlist page -> name, description, visibility checkbox"
        ],
        "select_by_dropdown": [
            "Track detail page -> 'Add to Playlist' dropdown to select playlist"
        ],
        "add_by_button": [
            "Album/Track pages -> 'Add to Playlist' button"
        ],
        "play_by_playback": [
            "Track page -> 'Play' button for audio playback"
        ],
        "play_by_route": [
            "Track page -> navigate to a track from browse/album and press 'Play'"
        ],
        "follow_by_dropdown": [
            "Artist page -> 'More' dropdown with 'Follow' and 'Share Artist' options"
        ],
        "follow_by_toggle": [
            "Artist page -> 'Follow'/'Following' button"
        ],
        "share_by_dropdown": [
            "Track page -> 'Share' dropdown with 'Copy Link' and 'Share on Twitter'; Artist page -> 'Share Artist'"
        ],
        "save_by_toggle": [
            "Track page -> 'Like'/'Unlike' heart button"
        ],
        "subscribe_by_toggle": [
            "Artist page -> 'Subscribe' button for release notifications"
        ],
        "play_by_date_range": [
            "'Browse' page -> 'Play a release period' bar with two date inputs + Play button showing now-playing queue"
        ]
    },
    "news": {
        "navigate_by_route": [
            "'Featured Stories' section -> click article card to read",
            "Category page -> click article to read"
        ],
        "search_by_query": [
            "'Lakeport Tribune' header -> 'Search articles...' field",
            "Search page -> search form"
        ],
        "search_by_semantic": [
            "Search page -> 'Search articles...' field with results"
        ],
        "extract_by_query": [
            "Search returns matching articles with titles and snippets"
        ],
        "extract_by_route": [
            "Article detail page -> full text, author, date, tags, comments"
        ],
        "play_by_playback": [
            "Article page -> 'Listen to Article' button"
        ],
        "post_from_free_text": [
            "Article detail -> comment textarea and submit"
        ],
        "follow_by_dropdown": [
            "Article page -> category links and author attribution"
        ],
        "share_by_dropdown": [
            "Article page -> 'Share' action link in toolbar"
        ],
        "save_by_toggle": [
            "Article detail -> 'Bookmark'/'Unbookmark' button",
            "'Bookmarks' page -> bookmarked articles list"
        ],
        "report_by_form": [
            "Report page -> reason dropdown (spam, harassment, etc.) and details textarea"
        ],
        "authenticate_by_form": [
            "Login page -> username and password fields"
        ],
        "register_by_form": [
            "Register page -> display name, email, username, password fields"
        ],
        "filter_by_date_range": [
            "Search page -> From/To date inputs + 'Filter by Date' button",
            "Category page -> From/To date inputs + 'Filter by Date' button in the category header"
        ],
        "extract_by_semantic": [
            "Search page -> 'Smart Search' natural-language input + 'Find Stories' button with relevance scores"
        ],
        "subscribe_by_toggle": [
            "Register page -> newsletter toggle buttons (Daily Digest, Breaking News Alerts, Weekly Roundup)"
        ]
    },
    "password-managers": {
        "configure_by_slider": [
            "'Generator' page -> password 'Length' slider (8-64) with live value display"
        ],
        "navigate_by_semantic": [
            "Vault page -> 'Search entries...' field with 'Category' and 'Strength' filter dropdowns"
        ],
        "navigate_by_route": [
            "'VaultGuard' home -> click vault card (Personal, Work, Side Project)",
            "Vault page -> click entry to view details",
            "Top nav -> 'Generator', 'Security', 'Audit Log' links"
        ],
        "search_by_query": [
            "Vault page -> 'Search entries...' field in vault view"
        ],
        "filter_by_dropdown": [
            "Vault page -> 'Category' dropdown (All, Credit Card, Login), 'Strength' dropdown (All, Excellent, Strong, Fair, Weak)",
            "'Audit Log' -> action and vault dropdowns",
            "New/Edit Entry -> category, vault, strength dropdowns"
        ],
        "extract_by_semantic": [
            "Vault page -> search results showing matching entries with title and category"
        ],
        "extract_by_code": [
            "Entry detail page -> 'Reveal' button with PIN code input for password reveal"
        ],
        "extract_by_dropdown": [
            "Vault page -> category/strength dropdown returns filtered entries"
        ],
        "extract_from_table": [
            "'Audit Log' page -> audit trail table (timestamp, action, entry, vault, device, IP)",
            "Entry detail -> metadata (created, updated, last_used, strength)"
        ],
        "extract_by_route": [
            "Entry detail page -> credentials, notes, tags, audit history"
        ],
        "create_by_form": [
            "New Entry page -> form with title, username, password, URL, notes, tags"
        ],
        "create_by_dropdown": [
            "New Entry page -> vault dropdown and category dropdown"
        ],
        "submit_by_form": [
            "New Entry page -> form with all credential fields and dropdowns"
        ],
        "edit_by_form": [
            "Edit Entry page -> form with title, username, password, URL, notes, tags"
        ],
        "delete_from_table": [
            "Entry detail page -> 'Delete' button with confirm dialog"
        ],
        "select_by_dropdown": [
            "Filter dropdowns -> select vault, category, or strength level"
        ],
        "configure_by_dropdown": [
            "'Settings' page -> auto-lock, clipboard clear, password length, theme dropdowns"
        ],
        "export_by_dropdown": [
            "Vault page -> entries list with category and strength filters"
        ],
        "upload_by_upload": [
            "'VaultGuard' home -> 'Import' button accepting .csv, .json files",
            "'New Entry' page -> Icon Image file input on the entry creation form"
        ],
        "verify_identity_by_code": [
            "'Login' page -> Two-Factor Verification panel (6-digit or backup code input) shown after unlock",
            "'Unlock Your Vault' page -> 'Email Address' and 'Master Password' fields"
        ]
    },
    "personal-portfolio": {
        "navigate_by_semantic": [
            "Search page -> 'Search across portfolio...' field with results"
        ],
        "navigate_by_route": [
            "Top nav -> 'Projects', 'Resume', 'Blog' links",
            "'Projects' page -> click project card (TrailSync, ScoreKeep, etc.) for details"
        ],
        "extract_by_query": [
            "'Projects' page -> filter form with search input and category/tech/status dropdowns"
        ],
        "extract_by_semantic": [
            "Search page -> results matching projects, resume, and blog content"
        ],
        "extract_from_table": [
            "Skills page -> skills table (name, level, years, category)"
        ],
        "extract_by_route": [
            "Project detail page -> project info, tech stack, collaborators",
            "'AlexDev' home -> portfolio sections (Projects, Skills, Resume, Blog, Contact)"
        ],
        "submit_by_form": [
            "'Alex Rivera' page -> contact form with 'Name', 'Email', 'Subject', 'Message' and 'Send Message' button"
        ],
        "sort_by_ranking": [
            "'AlexDev' home -> sort dropdown (Newest, Title A-Z, Status) in projects section"
        ],
        "export_by_dropdown": [
            "'AlexDev' home -> 'Export CSV' link in projects section header"
        ],
        "subscribe_by_toggle": [
            "'Alex Rivera' page -> contact form with name, email, subject, message fields"
        ]
    },
    "petitions-voting-info": {
        "navigate_by_route": [
            "'Petitions' page -> click petition to view details",
            "'Elections' page -> click election to view details"
        ],
        "search_by_query": [
            "'Petitions' page -> 'Search petitions...' field with status/category/sort dropdowns"
        ],
        "search_by_semantic": [
            "'Petitions' page -> keyword search across petition titles and descriptions"
        ],
        "filter_by_query": [
            "'Petitions' page -> 'Search petitions...' field filters petitions by keyword"
        ],
        "filter_by_dropdown": [
            "'Petitions' page -> category dropdown (community, infrastructure, etc.)",
            "'Petitions' page -> status dropdown (active, won, closed)",
            "'Petitions' page -> sort dropdown (date, signatures, title)",
            "'Petitions' page -> order toggle (asc/desc)"
        ],
        "sort_by_toggle": [
            "'Petitions' page -> sort dropdown with asc/desc order select"
        ],
        "extract_by_query": [
            "Search returns petitions with titles and signature counts"
        ],
        "extract_by_dropdown": [
            "'Petitions' page -> category dropdown returns filtered petitions"
        ],
        "extract_by_route": [
            "Petition detail page -> description, signatures, comments, progress bar",
            "Election detail page -> races, candidates, results"
        ],
        "verify_by_dropdown": [
            "'Voter Info' page -> precinct dropdown to check registration status"
        ],
        "create_by_form": [
            "'Start a Petition' page -> title, description, goal, category dropdown"
        ],
        "submit_by_form": [
            "Petition detail page -> signature input and comment textarea, 'Sign Petition' button"
        ],
        "sign_by_signature": [
            "Petition detail page -> legal name input and optional comment"
        ],
        "subscribe_by_toggle": [
            "Petition detail page -> 'Subscribe' button for petition updates"
        ],
        "share_by_dropdown": [
            "Petition detail page -> share method dropdown (email, twitter, facebook, link)"
        ],
        "save_by_toggle": [
            "Petition detail page -> 'Save' button for bookmarking"
        ],
        "authenticate_by_form": [
            "Login page -> username and password fields"
        ],
        "register_by_form": [
            "Register Voter page -> name, email, phone, address, precinct, party dropdown"
        ]
    },
    "podcasts-audiobooks": {
        "navigate_by_route": [
            "'Trending Podcasts' section -> click podcast to view details",
            "'Top Audiobooks' section -> click audiobook to view details",
            "Podcast detail -> click episode to view details"
        ],
        "search_by_query": [
            "'SoundShelf' page -> 'Search podcasts, audiobooks...' field"
        ],
        "search_by_semantic": [
            "'SoundShelf' page -> search field with keyword matching"
        ],
        "filter_by_dropdown": [
            "'Podcasts' page -> category dropdown (News, Technology, True Crime, etc.)",
            "'Audiobooks' page -> genre dropdown (Fiction, Self-Help, etc.)"
        ],
        "filter_by_slider": [
            "'Audiobooks' page -> min rating slider (1-5)",
            "'Audiobooks' page -> max duration slider (1-25 hours)"
        ],
        "sort_by_ranking": [
            "'Audiobooks' page -> min-rating and max-duration sliders for filtering/sorting"
        ],
        "extract_by_query": [
            "Search returns matching podcasts, episodes, and audiobooks"
        ],
        "submit_by_form": [
            "Podcast/Audiobook detail -> review form with rating slider and review textarea"
        ],
        "select_by_dropdown": [
            "Episode detail -> playback speed dropdown (0.5x to 3.0x)"
        ],
        "play_by_dropdown": [
            "Episode detail -> play button with speed select dropdown"
        ],
        "post_from_free_text": [
            "Audiobook detail -> review form (rating slider and review textarea)"
        ],
        "react_by_toggle": [
            "Episode detail -> 'Like'/'Unlike' button; Audiobook detail -> 'Like' button"
        ],
        "rate_by_slider": [
            "Audiobook detail -> rating slider (1-5 stars)"
        ],
        "follow_by_dropdown": [
            "Podcast detail -> 'Follow' button"
        ],
        "follow_by_toggle": [
            "Podcast detail -> 'Follow'/'Unfollow' button"
        ],
        "subscribe_by_toggle": [
            "Podcast detail -> 'Subscribe'/'Unsubscribe' button"
        ],
        "save_by_toggle": [
            "Episode detail -> 'Save'/'Unsave' button for bookmarking episodes"
        ]
    },
    "project-homepages": {
        "navigate_by_query": [
            "'FlowNet' homepage -> section navigation via query param"
        ],
        "navigate_by_semantic": [
            "Search page -> 'Search project content...' field with results"
        ],
        "navigate_by_route": [
            "Top nav -> 'Paper', 'Team', 'Resources', 'Updates', 'Stats' links"
        ],
        "search_by_query": [
            "'FlowNet' page -> 'Search project content...' field at top"
        ],
        "extract_by_semantic": [
            "Search page -> results with matching project content scored by relevance"
        ],
        "extract_by_dropdown": [
            "'Resources' page -> resource type dropdown"
        ],
        "extract_from_table": [
            "'Stats' page -> overview, metrics, team, and resources tables"
        ],
        "extract_by_route": [
            "Section pages -> section content; 'FlowNet' home -> section navigation dropdown"
        ],
        "export_by_dropdown": [
            "Export page -> format dropdown (bibtex, apa, json, csv) for download"
        ]
    },
    "project-mgmt-issue-tracking": {
        "navigate_by_semantic": [
            "Project page -> 'Search issues...' field with sprint/assignee/type/priority filters"
        ],
        "navigate_by_route": [
            "'Meridian Tracker' dashboard -> click project card (MeridianFlow, MeridianVault, etc.)",
            "Project page -> click issue card to view details",
            "Top nav -> 'Sprints', 'Backlog', '+ New Issue' links"
        ],
        "search_by_query": [
            "'Backlog' page -> 'Search backlog...' field with project/type/priority dropdowns"
        ],
        "filter_by_dropdown": [
            "'Backlog' page -> project, type, priority dropdowns",
            "Project page -> assignee, type, priority dropdowns"
        ],
        "sort_by_ranking": [
            "Project page -> issue list with type and priority filters"
        ],
        "extract_by_query": [
            "Search returns matching issues"
        ],
        "extract_by_semantic": [
            "Project page -> search returns matching issues with title and description"
        ],
        "extract_by_dropdown": [
            "'Backlog' page -> project/priority dropdown returns filtered issues"
        ],
        "extract_from_table": [
            "'Backlog' page -> issues table (key, title, type, status, priority, assignee, points)"
        ],
        "extract_by_route": [
            "Issue detail page -> description, metadata, comments, status history"
        ],
        "create_by_form": [
            "'+ New Issue' page -> project dropdown, title input, description textarea, type, priority, assignee, sprint, story points"
        ],
        "submit_by_form": [
            "'+ New Issue' page -> form with title, project/type/priority/assignee dropdowns, description, labels"
        ],
        "edit_by_query": [
            "Issue detail page -> edit form with title, type, priority, assignee, description, story points"
        ],
        "edit_by_dropdown": [
            "Issue detail -> status transition dropdown (open, in_progress, review, done, closed)"
        ],
        "edit_by_form": [
            "Issue detail -> edit form (title, description, type, priority, assignee, sprint, points, labels)"
        ],
        "delete_from_table": [
            "Issue detail -> 'Delete Issue' button"
        ],
        "post_from_free_text": [
            "Issue detail -> add comment textarea"
        ],
        "filter_by_date_range": [
            "Project board page -> 'Created from'/'to' date inputs in the filter form"
        ],
        "export_by_dropdown": [
            "Project board page -> 'Export issues as' format dropdown (CSV/JSON) + Export button"
        ],
        "follow_by_toggle": [
            "Issue detail page -> 'Watch'/'Watching' toggle button in the actions row"
        ]
    },
    "qa-knowledge": {
        "navigate_by_route": [
            "'All Questions' page -> click question title to view thread",
            "Top nav -> 'Tags', 'Users', 'Ask Question' links",
            "'Tags' page -> click tag to view questions"
        ],
        "search_by_query": [
            "'KnowledgeHub' page -> 'Search questions...' field at top",
            "Search page -> search form"
        ],
        "search_by_semantic": [
            "'KnowledgeHub' page -> search field with keyword matching"
        ],
        "filter_by_dropdown": [
            "'All Questions' page -> 'All Tags' dropdown filter"
        ],
        "sort_by_ranking": [
            "'All Questions' page -> sort tabs: 'Newest', 'Votes', 'Active', 'Unanswered'"
        ],
        "extract_by_query": [
            "Search returns matching questions with vote counts and answers"
        ],
        "extract_by_route": [
            "Question detail page -> full question, answers, votes, comments",
            "User profile page -> reputation, activity, tags"
        ],
        "create_by_form": [
            "'Ask Question' page -> title input, body textarea, tag input"
        ],
        "submit_by_form": [
            "Question detail -> answer textarea ('Write your answer here...') and post button"
        ],
        "edit_by_form": [
            "Edit Question page -> title, body, tags form"
        ],
        "post_from_free_text": [
            "Question detail -> answer body textarea"
        ],
        "post_by_route": [
            "Question detail -> post new answer"
        ],
        "react_by_toggle": [
            "Question detail -> upvote/downvote buttons on questions",
            "Question detail -> upvote/downvote buttons on answers"
        ],
        "follow_by_dropdown": [
            "'All Questions' page -> follow tag from dropdown"
        ],
        "follow_by_toggle": [
            "Tag questions page ('Questions tagged') -> 'Follow Tag' button"
        ],
        "share_by_dropdown": [
            "Question detail -> share platform dropdown (email, twitter, linkedin, copy_link)"
        ],
        "save_by_toggle": [
            "Question detail -> 'Save'/'Bookmark' question button"
        ],
        "report_by_form": [
            "Question detail -> 'Report' question form (reason dropdown)",
            "Answer -> 'Report' answer form (reason dropdown)"
        ],
        "authenticate_by_form": [
            "Login page -> username and password fields"
        ],
        "register_by_form": [
            "Register page -> username, email, password fields"
        ]
    },
    "rating-review": {
        "navigate_by_route": [
            "'All Businesses' page -> click business card to view details",
            "Top nav -> 'My Reviews', 'Photos' links"
        ],
        "search_by_query": [
            "'LakeReview' page -> 'Search businesses, restaurants, services...' field",
            "'All Businesses' page -> 'Business name, cuisine...' field"
        ],
        "search_by_semantic": [
            "'Find the Best Local Businesses' hero -> search bar at top"
        ],
        "filter_by_query": [
            "Search filters businesses by keyword"
        ],
        "filter_by_dropdown": [
            "'All Businesses' page -> 'All Categories' and 'Any Rating' dropdowns"
        ],
        "extract_by_query": [
            "Search returns matching businesses with name, category, rating"
        ],
        "extract_by_route": [
            "Business detail page -> address, hours, rating, reviews, photos"
        ],
        "extract_by_ranking": [
            "'All Businesses' page -> businesses list with star ratings, sortable by rating"
        ],
        "compute_by_dropdown": [
            "'All Businesses' page -> 'All Categories' dropdown for viewing ratings by category"
        ],
        "edit_by_form": [
            "'My Reviews' page -> 'Edit' button on each review"
        ],
        "delete_from_table": [
            "'My Reviews' page -> 'Delete' button on each review"
        ],
        "post_from_free_text": [
            "Write Review page -> star rating radio buttons and review textarea"
        ],
        "react_by_toggle": [
            "Business detail page -> 'Useful', 'Funny', 'Cool' vote buttons on each review"
        ],
        "follow_by_toggle": [
            "Business detail page -> '+ Follow'/'Following' toggle button in each review's action row"
        ],
        "save_by_toggle": [
            "'All Businesses' page -> 'Save'/'Saved' bookmark toggle on each business card"
        ],
        "report_by_form": [
            "Write Review page -> 'Report a Problem' card (reason dropdown + details + Submit Report button)"
        ]
    },
    "real-estate-buy-rent": {
        "navigate_by_route": [
            "Listings page -> click listing card to view property details",
            "Top nav -> 'All Listings', 'Buy', 'Rent', 'Agents', 'Saved', 'Inquiries' links"
        ],
        "search_by_query": [
            "'Find Your Next Home' hero -> 'Search by address, feature, or keyword...' field",
            "Listings page -> 'Search listings...' field"
        ],
        "search_by_semantic": [
            "'Lakeport Real Estate' page -> search field with 'Buy or Rent' dropdown"
        ],
        "filter_by_query": [
            "Search bar filters listings by keyword"
        ],
        "filter_by_dropdown": [
            "Listings page -> Status, Type, Beds, Baths dropdowns in filter bar"
        ],
        "filter_by_checkbox": [
            "Listings page -> 'Garage', 'Pool', 'Basement' checkboxes in filter row"
        ],
        "filter_by_slider": [
            "Listings page -> 'Max $' price slider in filter row"
        ],
        "sort_by_ranking": [
            "Listings page -> sort dropdown (Newest, Price, Largest, Most Bedrooms)"
        ],
        "extract_by_dropdown": [
            "Filter dropdowns return filtered listing results"
        ],
        "extract_from_table": [
            "Listing detail -> property details (beds, baths, sqft, year, features)"
        ],
        "extract_by_route": [
            "Listing detail page -> full property info, photos, agent, map",
            "Agent detail page -> agent info and their listings"
        ],
        "extract_by_ranking": [
            "Listings page -> sort dropdown for ranking by price"
        ],
        "extract_by_extremum": [
            "Listings page -> sort by price to find cheapest/most expensive"
        ],
        "compare_by_dropdown": [
            "Listings page -> filtered listing cards for property comparison"
        ],
        "submit_by_form": [
            "Listing detail page -> inquiry form (name, email, phone, message textarea)"
        ],
        "select_by_ranking": [
            "Listings page -> sort dropdown for ordering by price/date"
        ],
        "select_by_extremum": [
            "Listings page -> sort and sqft_min filter for selecting by size/price"
        ],
        "save_by_toggle": [
            "Listing detail -> 'Save'/'Unsave' listing button",
            "'Saved' page -> saved listings list"
        ],
        "book_by_form": [
            "Listing detail page -> inquiry form with message textarea and 'Send Inquiry' button"
        ],
        "follow_by_toggle": [
            "Agent detail page -> 'Follow Agent'/'Following' toggle button on the agent profile card"
        ]
    },
    "remote-calls": {
        "navigate_by_route": [
            "Top nav -> 'Dashboard', 'Meetings', 'Recordings', 'Call Log', 'Schedule', 'Join', 'Settings' links"
        ],
        "search_by_query": [
            "'Meetings' page -> 'Meeting title...' search input",
            "'Recordings' page -> search input"
        ],
        "search_by_semantic": [
            "'Meetings' page -> search with date/status/type/participant filters"
        ],
        "filter_by_dropdown": [
            "'Call Log' page -> type (audio, video), status (completed, missed), contact dropdowns",
            "'Meetings' page -> 'Status', 'Type', 'Participant' dropdowns"
        ],
        "filter_by_date_range": [
            "'Call Log' page -> 'From' and 'To' date fields",
            "'Meetings' page -> 'From' and 'To' date fields"
        ],
        "extract_by_query": [
            "Search returns matching meetings/recordings"
        ],
        "extract_from_table": [
            "'Meetings' page -> meetings table (title, date, duration, status, type)",
            "'Call Log' page -> call log table (caller, callee, type, duration, status)"
        ],
        "extract_by_route": [
            "Meeting detail page -> participants, recording, chat, share link",
            "Recording detail page -> playback, duration, views, transcript"
        ],
        "submit_by_form": [
            "'Schedule a Meeting' page -> 'Meeting Title' input, datetime, participant checkboxes, duration/type dropdowns"
        ],
        "select_by_dropdown": [
            "'Schedule a Meeting' page -> 'Duration' dropdown, 'Meeting Type' dropdown (Work/Personal)",
            "'Settings' page -> notification_sound, background, language dropdowns"
        ],
        "configure_by_dropdown": [
            "'Settings' page -> notification_sound, background, language dropdowns"
        ],
        "play_by_playback": [
            "Recording detail page -> play button; playing reveals exact runtime, resolution, and chapters (POST /recording/<id>/play)"
        ],
        "export_by_dropdown": [
            "'Call Log' page -> filtered call history with search and filter controls"
        ],
        "upload_by_upload": [
            "'Schedule a Meeting' page -> file attachment input"
        ],
        "share_by_toggle": [
            "Meeting detail page -> 'Share' button (copies link, shows 'Link Copied!')"
        ],
        "invite_by_form": [
            "Meeting detail page -> 'Invite by email' input and 'Invite' button"
        ],
        "message_from_free_text": [
            "'Join' page -> meeting code input (e.g. mtg-005) and 'Join Meeting' button"
        ],
        "book_by_form": [
            "'Schedule a Meeting' page -> form with title, date, time, duration, type, participants"
        ],
        "cancel_by_form": [
            "Meeting detail page -> 'Cancel Meeting' button"
        ],
        "join_by_code": [
            "'Join' page -> meeting code text field and submit"
        ]
    },
    "software-marketplace": {
        "configure_by_slider": [
            "'Settings' page -> 'Notification Frequency' slider (0-10, Off to Max) with live value display"
        ],
        "navigate_by_route": [
            "'AppVault' home -> click app card to view details"
        ],
        "search_by_query": [
            "'AppVault' page -> 'Search for apps & games' field at top"
        ],
        "search_by_semantic": [
            "'AppVault' page -> search with category/rating/price/sort filters"
        ],
        "filter_by_dropdown": [
            "'Browse' page -> category, genre, min_rating, price dropdowns"
        ],
        "filter_by_slider": [
            "'Browse' page -> 'Max Price' slider in filter sidebar"
        ],
        "sort_by_ranking": [
            "'Browse' page -> sort dropdown (rating, reviews, name, newest, price)"
        ],
        "sort_by_extremum": [
            "'Browse' page -> sort and min_rating dropdowns for finding top-rated apps"
        ],
        "extract_from_table": [
            "'Compare' page -> side-by-side comparison table of two apps"
        ],
        "extract_by_route": [
            "App detail page -> description, reviews, rating, developer info"
        ],
        "compare_from_table": [
            "'Compare' page -> select two apps via dropdowns then comparison table"
        ],
        "select_by_dropdown": [
            "'Compare' page -> app1 and app2 dropdowns for comparison"
        ],
        "configure_by_dropdown": [
            "'Settings' page -> theme (light/dark), language, content filter dropdowns"
        ],
        "save_by_toggle": [
            "App detail -> 'Add to Wishlist'/'Remove from Wishlist' button"
        ],
        "add_by_button": [
            "App detail -> 'Install'/'Add to Cart' button"
        ],
        "redeem_by_code": [
            "Checkout page -> promo code input (WELCOME20, SUMMER50, FREEAPP, VIP30)"
        ]
    },
    "sports-esports": {
        "navigate_by_route": [
            "'Scoreboard' page -> click match card to view details",
            "'Standings' page -> click team to view details",
            "'Players' page -> click player to view details"
        ],
        "search_by_query": [
            "'Players' page -> search input for filtering player names"
        ],
        "filter_by_dropdown": [
            "'Players' page -> league and team dropdowns"
        ],
        "filter_by_slider": [
            "'Standings' page -> 'Min Wins' slider (0-50) that filters the standings table"
        ],
        "extract_by_query": [
            "Player search returns matching players"
        ],
        "extract_from_table": [
            "'Standings' page -> standings table (Rank, Team, W, L, Win%)",
            "League page -> standings table per league",
            "Team page -> roster table, match history",
            "Match page -> player roster tables per team",
            "'Compare Teams' page -> comparison table"
        ],
        "extract_by_route": [
            "Team detail page -> roster, record, match history",
            "Match detail page -> score, status, players, comments",
            "Player detail page -> stats, team, matches"
        ],
        "extract_by_extremum": [
            "'Compare Teams' page -> side-by-side team comparison with statistics"
        ],
        "compute_from_table": [
            "'Compare Teams' page -> comparison table showing team records and stats"
        ],
        "compare_by_dropdown": [
            "'Compare Teams' page -> 'Team A' and 'Team B' dropdowns, then side-by-side table"
        ],
        "play_by_playback": [
            "Highlights page -> match highlight player with play button"
        ],
        "post_from_free_text": [
            "Match detail page -> comment textarea"
        ],
        "react_by_toggle": [
            "'Favorites' page -> 'Add'/'Remove' toggle forms for teams and players"
        ],
        "follow_by_toggle": [
            "'Favorites' page -> add/remove team/player favorites toggle",
            "Team/Player detail -> favorite toggle"
        ],
        "subscribe_by_toggle": [
            "League page -> subscribe to league notifications toggle"
        ],
        "save_by_toggle": [
            "'Favorites' page -> toggle favorite teams/players"
        ],
        "search_by_semantic": [
            "'Favorites' page -> 'Search Teams & Players' natural-language search input with 'Add to Favorites' buttons on results"
        ],
        "filter_by_date_range": [
            "'Favorites' page -> From/To date inputs filtering favorited teams' matches by date"
        ]
    },
    "spreadsheets-slides": {
        "navigate_by_semantic": [
            "'SheetDeck' page -> spreadsheet/presentation listings"
        ],
        "navigate_by_route": [
            "'SheetDeck' page -> click spreadsheet or presentation to open it",
            "Left sidebar -> 'All Files', 'Spreadsheets', 'Presentations', 'Shared with Me', 'Templates' links"
        ],
        "extract_from_table": [
            "Spreadsheet page -> cell grid table (A1 notation, rows x cols)"
        ],
        "compute_by_query": [
            "Spreadsheet view -> cell data with formula capabilities"
        ],
        "compute_by_extremum": [
            "Spreadsheet view -> data table with sortable columns"
        ],
        "create_by_form": [
            "'+ New' -> Create Spreadsheet or Create Presentation form with title input"
        ],
        "edit_by_query": [
            "Spreadsheet view -> editable cells with A1-reference addressing"
        ],
        "edit_by_form": [
            "Spreadsheet page -> cell edit form (per-cell inputs, bulk submit)"
        ],
        "export_by_dropdown": [
            "Spreadsheet/presentation view -> data export controls"
        ],
        "share_by_toggle": [
            "Spreadsheet page -> 'Share' button in toolbar (copies link, shows 'Copied!')",
            "Spreadsheet page -> 'Share' button in toolbar"
        ],
        "delete_from_table": [
            "'SheetDeck' page -> Delete button on each file card with confirm dialog"
        ]
    },
    "tax-filing-dmv-permits": {
        "navigate_by_route": [
            "'File & Pay' page -> click filing to view details",
            "'Motor Vehicles' page -> click vehicle to view details",
            "'Permits' page -> click permit to view details"
        ],
        "search_by_query": [
            "'Search' page -> search bar with text input"
        ],
        "search_by_semantic": [
            "'City of Lakeport' home -> navigation with tax filing and permit sections"
        ],
        "filter_by_dropdown": [
            "'File & Pay' page -> tax_year, type, status dropdowns",
            "'Motor Vehicles' page -> body_type, renewal_status dropdowns",
            "'Permits' page -> type, status dropdowns",
            "'Payments' page -> type dropdown",
            "'Forms' page -> category dropdown"
        ],
        "filter_by_date_range": [
            "'Permits' page -> 'From'/'To' date range filter"
        ],
        "extract_by_query": [
            "Search returns matching documents and filings"
        ],
        "extract_by_semantic": [
            "'City of Lakeport' home -> filing and permit records"
        ],
        "extract_by_dropdown": [
            "Filter dropdowns return filtered lists"
        ],
        "extract_from_table": [
            "'City of Lakeport' dashboard -> stats table",
            "'File & Pay' -> filings table (year, type, status, amount)",
            "'Motor Vehicles' -> vehicles table (make, model, year, VIN)",
            "'Permits' -> permits table (type, status, dates)",
            "'Payments' -> payments table (type, amount, date, status)"
        ],
        "extract_by_route": [
            "Tax filing detail page -> filing info table",
            "Vehicle detail page -> vehicle info table",
            "Permit detail page -> permit info table"
        ],
        "compute_from_table": [
            "'City of Lakeport' home -> tax filing data with amounts"
        ],
        "compute_by_extremum": [
            "'City of Lakeport' home -> payment records for finding extremes"
        ],
        "verify_by_toggle": [
            "Vehicle detail page -> 'Insurance Verified' toggle button"
        ],
        "submit_by_form": [
            "'Make Payment' page -> payment form with type, method, account type, amount"
        ],
        "apply_by_form": [
            "Apply Permit page -> permit form with type dropdown, description"
        ],
        "sign_by_signature": [
            "Sign Document page -> legal name text input for signature"
        ],
        "select_by_dropdown": [
            "'Make Payment' -> pay type, method dropdowns",
            "'Appointments' -> service, time_slot, location dropdowns"
        ],
        "select_by_date_range": [
            "'Appointments' page -> date input for scheduling"
        ],
        "upload_by_upload": [
            "Apply Permit page -> file upload for supporting documents"
        ],
        "book_by_date_range": [
            "'Appointments' page -> booking form with service, date, time_slot, location"
        ],
        "pay_by_form": [
            "'Make Payment' page -> payment submission form"
        ],
        "authenticate_by_form": [
            "Login page -> username and password fields"
        ],
        "verify_identity_by_code": [
            "Verify Identity page -> code input form"
        ],
        "edit_by_query": [
            "'City of Lakeport' home -> Notes column in Recent Tax Filings table with per-filing text input + Save button"
        ],
        "export_by_dropdown": [
            "'City of Lakeport' home -> 'Export Your Data' bar with data-type dropdown (filings/vehicles/permits/payments) and format dropdown (CSV/JSON)"
        ]
    },
    "team-chat-workspace": {
        "navigate_by_route": [
            "Left sidebar -> click channel name (# general, # engineering, # product, etc.)",
            "Top sidebar -> 'All Channels', 'Threads', 'Members', 'Search' links"
        ],
        "search_by_query": [
            "'Search' page -> 'Search messages...' field",
            "Channel page -> search within channel"
        ],
        "search_by_dropdown": [
            "'Search' page -> channel dropdown to search within specific channel"
        ],
        "filter_by_dropdown": [
            "'Members' page -> department dropdown",
            "'Threads' page -> channel dropdown"
        ],
        "sort_by_ranking": [
            "'Meridian Chat' page -> sort dropdown (Sort: Recent, Sort: Name, Sort: Activity)"
        ],
        "filter_by_date_range": [
            "Channel page -> date filter inputs",
            "'Threads' page -> From/To date inputs in the filter bar"
        ],
        "extract_by_query": [
            "Search returns matching messages across channels"
        ],
        "extract_by_semantic": [
            "'Meridian Chat' page -> workspace channels and messages with search"
        ],
        "extract_by_dropdown": [
            "'Members' page -> department dropdown returns filtered members"
        ],
        "extract_by_route": [
            "Thread detail page -> full thread with replies"
        ],
        "submit_by_form": [
            "'Meridian Chat' page -> message input area for composing messages"
        ],
        "delete_from_table": [
            "Channel page -> 'x delete' button per message"
        ],
        "upload_by_upload": [
            "Channel page -> file upload form in message area"
        ],
        "post_from_free_text": [
            "Channel page -> message input box at bottom and 'Send' button"
        ],
        "share_by_toggle": [
            "Channel page -> 'Share' button in header (copies link, shows 'Copied!')"
        ],
        "invite_by_form": [
            "Channel page -> 'Invite member' input and 'Invite' button in header"
        ],
        "message_from_free_text": [
            "Channel page -> message text input and 'Send' button",
            "Thread detail -> reply input and send"
        ],
        "authenticate_by_form": [
            "Login page -> username and password fields"
        ],
        "create_by_form": [
            "'Meridian Chat' page -> sidebar 'Create Channel' form (name + description + Create Channel button)"
        ],
        "edit_by_form": [
            "Channel page -> 'edit' button on own messages revealing inline edit form (Save/Cancel)"
        ],
        "follow_by_dropdown": [
            "'Meridian Chat' page -> sidebar 'Follow Member' member dropdown + Follow button"
        ],
        "follow_by_toggle": [
            "Channel page -> 'Follow'/'Following' toggle button in the channel header"
        ],
        "join_by_toggle": [
            "Channel page -> 'Join Channel'/'Leave Channel' toggle button in the channel header"
        ],
        "save_by_toggle": [
            "Channel page -> per-message 'save'/'saved' bookmark toggle"
        ],
        "block_by_toggle": [
            "'Members' page -> 'Block'/'Blocked' toggle button on each member card"
        ]
    },
    "ticketing-events": {
        "navigate_by_route": [
            "'Discover Events' section -> click event card to view details",
            "Top nav -> 'My Tickets' link"
        ],
        "search_by_query": [
            "'LakeportEvents' page -> 'Search events, venues, organizers...' field at top"
        ],
        "search_by_semantic": [
            "'LakeportEvents' page -> search with category-based filtering"
        ],
        "filter_by_query": [
            "'LakeportEvents' page -> search filters events by keyword"
        ],
        "filter_by_dropdown": [
            "'LakeportEvents' page -> 'Category' and 'Status' dropdowns",
            "Event detail -> ticket_type dropdown"
        ],
        "filter_by_checkbox": [
            "Settings page -> notification checkboxes"
        ],
        "filter_by_slider": [
            "'LakeportEvents' page -> 'Max Price' slider in filter panel"
        ],
        "filter_by_date_range": [
            "'LakeportEvents' page -> 'Date From' and 'Date To' fields"
        ],
        "sort_by_ranking": [
            "'LakeportEvents' page -> 'Sort by' dropdown (Date Soonest, Date Latest, Price, Name A-Z)"
        ],
        "extract_by_query": [
            "Search returns matching events with dates and prices"
        ],
        "extract_from_table": [
            "Compare page -> side-by-side event comparison table"
        ],
        "compare_from_table": [
            "Compare page -> compare two events with side-by-side table"
        ],
        "submit_by_form": [
            "Event detail page -> ticket booking form with ticket type/quantity and purchase button"
        ],
        "select_by_date_range": [
            "'LakeportEvents' page -> event date selection"
        ],
        "configure_by_dropdown": [
            "'Settings' page -> location dropdown"
        ],
        "add_by_button": [
            "Event detail -> 'Add to Cart' / purchase button with ticket_type and quantity dropdowns"
        ],
        "checkout_by_form": [
            "Checkout page -> name, email, payment, and submit"
        ],
        "book_by_form": [
            "Event detail -> book ticket form with type, quantity, submit"
        ],
        "redeem_by_code": [
            "'Checkout' page -> promotional code entry"
        ],
        "cancel_by_form": [
            "Cancel page -> reason textarea and submit"
        ],
        "authenticate_by_form": [
            "Login page -> username and password fields"
        ],
        "register_by_form": [
            "Register page -> name, email, password fields"
        ],
        "save_by_toggle": [
            "'LakeportEvents' page -> heart save/bookmark toggle on each event card"
        ]
    },
    "transit-directions": {
        "search_by_query": [
            "'Find a Stop' page -> 'Search by stop name or address...' field"
        ],
        "search_by_proximity": [
            "'Lakeport Transit Authority' page -> transit route search with stop finding"
        ],
        "sort_by_dropdown": [
            "'All Routes' page -> sort dropdown (route_number, name, frequency, travel_time)",
            "'Find a Stop' page -> sort dropdown (Name A-Z, Zone, Routes Served, Amenities)"
        ],
        "extract_by_query": [
            "Stop search returns matching stops"
        ],
        "extract_by_dropdown": [
            "'Fares & Passes' page -> zone, rider, pass_type dropdowns show fare prices"
        ],
        "extract_from_table": [
            "'Route Overview' section -> routes overview table",
            "Route detail -> schedule timetable (per-stop departure times)",
            "'Fares & Passes' page -> fare comparison table",
            "'Compare Routes' page -> route comparison table"
        ],
        "compute_by_dropdown": [
            "'Fares & Passes' page -> zone + rider + pass_type dropdowns compute fare amount"
        ],
        "compute_by_extremum": [
            "'Fares at a Glance' section -> fare comparison across routes"
        ],
        "compare_from_table": [
            "'Compare Routes' page -> 'Route 1' and 'Route 2' dropdowns, then side-by-side table"
        ],
        "select_by_dropdown": [
            "'Fares & Passes' page -> 'All Zones', 'All Riders', 'All Pass Types' dropdowns",
            "'Compare Routes' page -> 'Route 1' and 'Route 2' dropdowns",
            "'Find a Stop' page -> zone and route dropdowns"
        ],
        "select_by_ranking": [
            "'Route Overview' -> route options ranked by price and travel time"
        ],
        "select_by_extremum": [
            "'Route Overview' -> route selection with time-based optimization"
        ],
        "export_by_dropdown": [
            "'Routes' page -> export control with data-type dropdown (routes/stops/fares) and format dropdown (CSV/JSON)",
            "'Fares' page -> 'Export fare data' dropdown + Export button"
        ],
        "share_by_toggle": [
            "'Trip Planner' page -> per-saved-trip 'Sharing: On/Off' toggle button displaying the generated share link"
        ]
    },
    "translation": {
        "navigate_by_route": [
            "Top nav -> 'Translate', 'History', 'Saved' links"
        ],
        "extract_by_query": [
            "'LinguaBridge' page -> translation text input area"
        ],
        "extract_by_semantic": [
            "'LinguaBridge' page -> saved translations with search capabilities"
        ],
        "configure_by_toggle": [
            "'Settings' page -> toggle checkboxes for auto_detect, formal_mode, auto_pronounce"
        ],
        "export_by_dropdown": [
            "'Settings' page -> export format dropdown (json, csv, txt) for download"
        ],
        "translate_by_query": [
            "'LinguaBridge' page -> source text input with source language dropdown (Detect, English, Spanish, etc.) and target language dropdown, then translate"
        ]
    },
    "university-academic": {
        "navigate_by_semantic": [
            "'Faculty & Staff' page -> search input (name or area)"
        ],
        "navigate_by_route": [
            "'Academics' page -> click course to view details",
            "'Faculty & Staff' page -> click faculty member to view profile",
            "'Events' page -> click event to view details"
        ],
        "search_by_query": [
            "'Academics' page -> search input for courses",
            "'Faculty & Staff' page -> search input",
            "'Alumni' page -> search input"
        ],
        "search_by_semantic": [
            "'Faculty & Staff' page -> search input (name or area)"
        ],
        "filter_by_dropdown": [
            "'Academics' page -> department and level dropdowns",
            "'Events' page -> type dropdown",
            "'Alumni' page -> year dropdown",
            "'Faculty & Staff' page -> area dropdown"
        ],
        "extract_by_query": [
            "Search returns matching courses/faculty with details"
        ],
        "extract_from_table": [
            "'Academics' page -> courses table (code, title, credits, level, instructor)",
            "Compare page -> side-by-side course comparison table"
        ],
        "extract_by_route": [
            "Course detail page -> full course info, prerequisites, instructor",
            "Faculty detail page -> bio, research areas, publications",
            "Event detail page -> event info, time, location"
        ],
        "extract_by_date_range": [
            "'Events' page -> date fields filter events by date range"
        ],
        "compare_from_table": [
            "Compare page -> select two courses via dropdowns, then side-by-side table"
        ],
        "submit_by_form": [
            "'Contact' page -> contact form (subject, message textarea)"
        ],
        "apply_by_form": [
            "'Apply Now' page -> application form (name, email, program dropdown, statement textarea)"
        ],
        "export_by_dropdown": [
            "'Resources' page -> format selection (csv, json) and type (courses, faculty) for download"
        ],
        "subscribe_by_toggle": [
            "'Campus Life' page -> Subscribe/Unsubscribe toggle per research area"
        ]
    },
    "url-shorteners-qr": {
        "navigate_by_query": [
            "'My Links' page -> 'Search links...' field"
        ],
        "navigate_by_route": [
            "'Recent Links' section -> click link title to view details",
            "Top nav -> 'Create', 'My Links' links"
        ],
        "search_by_query": [
            "'My Links' page -> 'Search links...' field"
        ],
        "filter_by_date_range": [
            "'My Links' page -> date filter inputs"
        ],
        "extract_by_query": [
            "'My Links' page -> search results showing per-link click counts"
        ],
        "extract_from_table": [
            "Link detail page -> click statistics table (countries, devices, referrers)"
        ],
        "delete_from_table": [
            "Link detail page -> 'Delete' button"
        ],
        "configure_by_dropdown": [
            "'Shorten a URL' form -> redirect type dropdown (301 Permanent, 302 Temporary, 307 Strict)",
            "'My Links' page -> status filter and sort dropdowns"
        ],
        "create_by_query": [
            "'Shorten a URL' form -> 'Paste your long URL here...' input, 'Title', 'Custom short code', 'Expiry', 'Tags' fields, 'Generate QR Code' checkbox, and 'Shorten URL' button"
        ],
        "create_by_form": [
            "'Shorten a URL' form -> URL input and optional custom code, then create short link"
        ],
        "edit_by_query": [
            "Link detail page -> 'Edit Link' card with title, destination-URL, and tags inputs + Save button"
        ],
        "export_by_dropdown": [
            "'My Links' page -> export control with CSV/JSON format dropdown and Export button"
        ],
        "share_by_toggle": [
            "Link detail page -> 'Sharing: On/Off' toggle button revealing the short share URL and QR share link"
        ]
    },
    "version-control": {
        "navigate_by_route": [
            "'MeridianGit' page -> click repo name to view details",
            "Repo detail -> 'Issues', 'Merge Requests' links",
            "Top nav -> 'Dashboard', 'Repositories', 'Projects', 'Issues', 'Merge Requests', 'Members' links"
        ],
        "search_by_query": [
            "'MeridianGit' page -> 'Search or jump to...' field at top",
            "'MeridianGit' page -> code search across repository contents"
        ],
        "search_by_semantic": [
            "'MeridianGit' page -> repository search with keyword matching"
        ],
        "filter_by_dropdown": [
            "'Issues' page -> state dropdown (open, closed), project dropdown",
            "'Merge Requests' page -> state and project dropdowns",
            "'Repositories' page -> sort dropdown"
        ],
        "sort_by_ranking": [
            "'Dashboard' page -> sort dropdown (Sort: Updated, Sort: Stars, Sort: Name)"
        ],
        "extract_by_query": [
            "Code search returns matching files and snippets"
        ],
        "extract_by_semantic": [
            "'MeridianGit' page -> repository cards with descriptions"
        ],
        "extract_from_table": [
            "Repo detail -> file tree table, commit history table"
        ],
        "extract_by_route": [
            "Repo detail page -> README, file tree, commits, issues, merge requests",
            "Issue detail -> description, comments",
            "Merge request detail -> info, changes, reviews"
        ],
        "create_by_form": [
            "'New repository' page -> name, description, owner dropdown, default_branch dropdown"
        ],
        "select_by_dropdown": [
            "'New repository' page -> owner dropdown, default_branch dropdown"
        ],
        "follow_by_toggle": [
            "Repo detail -> 'Star'/'Unstar' button"
        ],
        "compare_from_table": [
            "Repository detail (Commits tab) -> per-commit base/compare radio selectors + 'Compare commits' button showing additions/deletions/files-changed delta"
        ],
        "submit_by_form": [
            "Repository detail (Issues tab) -> 'New issue' form (title, labels)",
            "Repository detail (Commits tab) -> 'Open a merge request' form (title, source/target branch, description)"
        ],
        "edit_by_form": [
            "Repository detail (Issues tab) -> per-issue 'Edit' button revealing inline form (title, open/closed state)"
        ],
        "upload_by_upload": [
            "Repository detail (Code tab) -> 'Upload file to repository' form with file input, destination path, and commit message"
        ],
        "export_by_route": [
            "Repository detail header -> 'Export CSV' and 'Export JSON' download links"
        ],
        "post_from_free_text": [
            "Repository detail (Issues tab) -> per-issue 'Comment' button revealing a free-text textarea"
        ]
    },
    "video": {
        "play_by_route": [
            "'StreamHub' page -> click video thumbnail to open the watch page with player"
        ],
        "navigate_by_route": [
            "'StreamHub' page -> click video thumbnail to watch",
            "Channel page -> click video to watch",
            "'Playlists' page -> click playlist to view"
        ],
        "search_by_query": [
            "'StreamHub' header -> 'Search' field at top"
        ],
        "search_by_semantic": [
            "'StreamHub' page -> video search across titles, descriptions, tags"
        ],
        "filter_by_dropdown": [
            "'+ Upload' page -> category dropdown (Education, Entertainment, Gaming, etc.)",
            "'+ Upload' page -> visibility/status dropdown"
        ],
        "sort_by_ranking": [
            "'StreamHub' page -> sort tabs: 'Trending', 'Latest', 'Popular', 'Most Liked'"
        ],
        "extract_by_query": [
            "Search returns matching videos with titles and view counts"
        ],
        "submit_by_route": [
            "'+ Upload' page -> video upload and metadata forms"
        ],
        "upload_by_upload": [
            "'+ Upload' page -> title, description, category dropdown, visibility, file input"
        ],
        "select_by_dropdown": [
            "'+ Upload' page -> category and visibility dropdowns"
        ],
        "play_by_playback": [
            "Watch page -> play button; playing reveals exact duration, stream quality, and chapters (POST /api/videos/<id>/play)"
        ],
        "post_from_free_text": [
            "Watch page -> comment textarea and submit"
        ],
        "react_by_toggle": [
            "Watch page -> 'Like' toggle button"
        ],
        "follow_by_toggle": [
            "Channel page -> 'Follow' button"
        ],
        "subscribe_by_toggle": [
            "Watch/Channel page -> 'Subscribe' button"
        ],
        "share_by_dropdown": [
            "Watch page -> 'Share' button with platform options (link, twitter, facebook, reddit, email, embed)"
        ],
        "save_by_toggle": [
            "Watch page -> 'Save to playlist' button"
        ],
        "report_by_form": [
            "Watch page -> 'Report' form with reason dropdown"
        ],
        "authenticate_by_form": [
            "Login page -> username and password fields"
        ],
        "filter_by_date_range": [
            "'StreamHub' page -> 'Uploaded from/to' date inputs in the filter bar with Clear Dates chip"
        ],
        "play_by_date_range": [
            "'StreamHub' page -> 'Play Newest in Range' button linking to the watch page of the most recent upload in the date-filtered list"
        ],
        "configure_by_toggle": [
            "'Settings' page -> default quality, playback speed, autoplay/notifications options"
        ]
    },
    "visual-how-to-guides": {
        "navigate_by_route": [
            "'StepVista' home -> click guide card in 'Featured Guides' or 'Most Popular' sections",
            "Category page -> click guide to view details",
            "Author page -> click guide to view details"
        ],
        "search_by_query": [
            "'StepVista' page -> 'Search guides...' field at top",
            "Search page -> search form"
        ],
        "search_by_semantic": [
            "'StepVista' page -> search across titles, descriptions, step content"
        ],
        "filter_by_dropdown": [
            "'Browse' page -> category and difficulty dropdowns"
        ],
        "filter_by_slider": [
            "'Browse' page -> difficulty slider (easy/medium/hard)"
        ],
        "sort_by_ranking": [
            "'Browse' page -> sort dropdown (rating, views, newest, duration)"
        ],
        "extract_from_table": [
            "'Compare' page -> side-by-side guide comparison table with two dropdowns"
        ],
        "extract_by_route": [
            "Guide detail page -> steps, author, rating, comments"
        ],
        "play_by_playback": [
            "Step Playback page -> individual step with prev/next navigation"
        ],
        "post_from_free_text": [
            "Guide detail page -> comment textarea and submit"
        ],
        "react_by_toggle": [
            "Guide detail page -> helpful/unhelpful toggle on comments"
        ],
        "rate_by_slider": [
            "Guide detail page -> rating slider (1-5 stars)"
        ],
        "save_by_toggle": [
            "Guide detail page -> 'Bookmark'/'Unbookmark' button",
            "'Bookmarks' page -> bookmarked guides list"
        ],
        "play_by_date_range": [
            "'StepVista' home -> 'Browse Guides by Date' created-from/created-to date inputs + 'Show Guides' button with 'Play steps' links"
        ]
    },
    "weather": {
        "extract_from_table": [
            "'7-Day Forecast' page -> forecast table",
            "'History' page -> 30-day historical weather table",
            "'Hourly' page -> 24-hour forecast cards"
        ],
        "subscribe_by_toggle": [
            "'Locations' page -> manage saved locations (login required)",
            "'Alerts' page -> per-alert 'Subscribe to alerts' switch (logged-in users)"
        ],
        "save_by_query": [
            "'Locations' page -> add location form and submit",
            "'Locations' page -> 'Quick Save by Name' text input + 'Save Location' button"
        ],
        "navigate_by_query": [
            "'Current' page -> location search bar (text input + 'Go' button) resolving a named weather station"
        ],
        "navigate_by_pan_zoom": [
            "'Locations' page -> SVG station map with zoom in/out, arrow-pan, reset buttons and drag-to-pan"
        ],
        "search_by_query": [
            "'Locations' page -> 'Search Weather Stations' text input + Search button listing matching stations"
        ],
        "search_by_proximity": [
            "'Locations' page -> 'Find Nearby Stations' lat/lng/radius inputs + 'Find Nearby' button listing stations by distance"
        ],
        "filter_by_toggle": [
            "'Current' page -> F/C unit switch on the current-conditions card",
            "'Alerts' page -> Severe/Moderate/Minor severity toggle buttons with live shown-count"
        ],
        "extract_by_toggle": [
            "'7-Day Forecast' page -> 'Show extended details' switch adding Dew Point, UV, Sunrise, Sunset columns"
        ],
        "extract_by_date_range": [
            "'Current' page -> 'Past Weather Lookup' From/To date inputs + 'Get Data' button rendering matching days"
        ],
        "compare_by_query": [
            "'Current' page -> 'Compare Locations' two-location form + Compare button with side-by-side table"
        ],
        "filter_by_date_range": [
            "'History' page -> From/To date inputs + 'View Range' button filtering the history table"
        ]
    },
    "wikis": {
        "navigate_by_query": [
            "'LakeportWiki' page -> article navigation with search"
        ],
        "navigate_by_route": [
            "'LakeportWiki' page -> click article title to read",
            "Category page -> click article to read",
            "Recent Changes -> click edit to view article"
        ],
        "search_by_query": [
            "'LakeportWiki' page -> 'Search wiki...' field at top",
            "Search page -> search form"
        ],
        "search_by_semantic": [
            "'LakeportWiki' page -> search with semantic keyword matching"
        ],
        "extract_by_query": [
            "Search returns matching articles with titles and snippets"
        ],
        "extract_by_dropdown": [
            "'LakeportWiki' page -> category navigation with page listings"
        ],
        "extract_from_table": [
            "Article page -> infobox/data tables within article content",
            "Compare page -> side-by-side article comparison table",
            "Recent Changes -> revision history table (editor, timestamp, summary)"
        ],
        "extract_by_route": [
            "Article page -> full article content, revision history, categories"
        ],
        "compare_by_dropdown": [
            "Compare page -> page1 and page2 dropdowns, then side-by-side comparison"
        ],
        "verify_from_free_text": [
            "'LakeportWiki' page -> article content for fact verification"
        ],
        "create_by_form": [
            "Create page -> title, content textarea, category dropdown"
        ],
        "edit_by_dropdown": [
            "Edit page -> category dropdown, content textarea, edit summary"
        ]
    },
}
