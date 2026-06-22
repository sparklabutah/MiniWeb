#!/usr/bin/env python3
"""
Data preparation script for the MiniWeb search-engine site.

Generates ~200 realistic web page index entries, categories, users with
search history and bookmarks, and translation pairs. Writes JSON files
to sites/search-engine/data/ and snapshots to data/.pristine/.

Data is synthetic but modeled on real-world web content patterns
(Wikipedia, news, tech blogs, government, education, shopping, etc.).
"""

import json
import pathlib
import random
import shutil
from datetime import datetime, timedelta

SITE_DATA_DIR = pathlib.Path(__file__).resolve().parents[2] / "sites" / "search-engine" / "data"
PRISTINE_DIR = SITE_DATA_DIR / ".pristine"

random.seed(42)

# ── Categories ──────────────────────────────────────────────────────────────

CATEGORIES = [
    {"id": 1, "name": "Technology", "description": "Computing, software development, AI, and emerging tech trends", "parent_category": None},
    {"id": 2, "name": "Science", "description": "Natural sciences, research discoveries, and scientific breakthroughs", "parent_category": None},
    {"id": 3, "name": "Health & Fitness", "description": "Medical news, nutrition, exercise, and wellness topics", "parent_category": None},
    {"id": 4, "name": "Finance", "description": "Markets, investing, personal finance, and economic analysis", "parent_category": None},
    {"id": 5, "name": "Travel", "description": "Destinations, travel guides, tips, and cultural experiences", "parent_category": None},
    {"id": 6, "name": "Food & Cooking", "description": "Recipes, culinary techniques, restaurant reviews, and food culture", "parent_category": None},
    {"id": 7, "name": "Arts & Culture", "description": "Visual arts, music, literature, and cultural commentary", "parent_category": None},
    {"id": 8, "name": "History", "description": "Historical events, civilizations, and archaeological discoveries", "parent_category": None},
    {"id": 9, "name": "Education", "description": "Learning resources, academic research, and educational technology", "parent_category": None},
    {"id": 10, "name": "Sports", "description": "Athletic competitions, player profiles, and sports analysis", "parent_category": None},
    {"id": 11, "name": "Government & Politics", "description": "Public policy, legislation, elections, and civic engagement", "parent_category": None},
    {"id": 12, "name": "Shopping", "description": "Product reviews, deals, comparisons, and consumer guides", "parent_category": None},
    {"id": 13, "name": "Entertainment", "description": "Movies, TV shows, gaming, and pop culture news", "parent_category": None},
    {"id": 14, "name": "Environment", "description": "Climate science, sustainability, conservation, and green technology", "parent_category": None},
    {"id": 15, "name": "Business", "description": "Startups, management, entrepreneurship, and corporate strategy", "parent_category": None},
]

# ── Page templates by category ─────────────────────────────────────────────
# Each entry: (title, url_path, snippet, domain, tags, language)

PAGE_TEMPLATES = {
    "Technology": [
        ("Introduction to Machine Learning Algorithms", "ml-algorithms-intro", "A comprehensive guide to the most popular machine learning algorithms including decision trees, neural networks, and support vector machines.", "techblog.example.com", ["machine learning", "AI", "algorithms", "tutorial"], "English"),
        ("Web Development with Python: Flask and Django", "python-web-frameworks", "Learn to build web applications using Python's most popular frameworks, Flask and Django, with step-by-step project examples.", "devtutorials.example.com", ["Python", "web development", "Flask", "Django"], "English"),
        ("Quantum Computing Breakthroughs in 2025", "quantum-computing-2025", "Groundbreaking achievements in quantum error correction and qubit stability bring practical quantum computing closer to reality.", "techblog.example.com", ["quantum computing", "research", "technology", "innovation"], "English"),
        ("The Rise of Edge Computing in IoT Networks", "edge-computing-iot", "How edge computing is transforming IoT deployments by reducing latency and bandwidth costs in industrial applications.", "techblog.example.com", ["edge computing", "IoT", "networking", "infrastructure"], "English"),
        ("Kubernetes Container Orchestration Best Practices", "kubernetes-best-practices", "Production-grade Kubernetes deployment strategies covering scaling, monitoring, security, and resource management.", "devtutorials.example.com", ["Kubernetes", "containers", "DevOps", "cloud"], "English"),
        ("Blockchain Beyond Cryptocurrency: Real-World Applications", "blockchain-applications", "Exploring how blockchain technology is being applied in supply chain, healthcare records, voting systems, and digital identity.", "techblog.example.com", ["blockchain", "applications", "distributed systems", "technology"], "English"),
        ("TypeScript 5.5: Complete Guide to New Features", "typescript-55-features", "Deep dive into TypeScript 5.5's new features including improved type inference, decorators, and const type parameters.", "devtutorials.example.com", ["TypeScript", "JavaScript", "programming", "web development"], "English"),
        ("5G Network Security: Challenges and Solutions", "5g-security-challenges", "Analysis of security vulnerabilities in 5G networks and emerging solutions for protecting next-generation mobile infrastructure.", "cybersec-weekly.example.com", ["5G", "security", "networking", "mobile"], "English"),
        ("Rust Programming Language for Systems Development", "rust-systems-programming", "Why Rust is becoming the preferred choice for systems programming with its memory safety guarantees and zero-cost abstractions.", "devtutorials.example.com", ["Rust", "programming", "systems", "memory safety"], "English"),
        ("Natural Language Processing with Transformer Models", "nlp-transformers", "Understanding the architecture behind GPT, BERT, and other transformer models that revolutionized natural language processing.", "techblog.example.com", ["NLP", "transformers", "AI", "deep learning"], "English"),
        ("Ciberseguridad para Empresas Pequeñas", "ciberseguridad-pymes", "Guía práctica de ciberseguridad para pequeñas y medianas empresas, incluyendo protección contra ransomware y phishing.", "tecnologia.example.com", ["ciberseguridad", "empresas", "ransomware", "protección"], "Spanish"),
        ("Einführung in die Künstliche Intelligenz", "einfuehrung-ki", "Ein einführender Leitfaden zur künstlichen Intelligenz, der maschinelles Lernen, natürliche Sprachverarbeitung und Computer Vision abdeckt.", "tecnologia.example.com", ["KI", "maschinelles Lernen", "technologie", "tutorial"], "German"),
        ("Linux Server Administration Fundamentals", "linux-server-admin", "Essential skills for managing Linux servers including user management, networking, security hardening, and automation with shell scripts.", "devtutorials.example.com", ["Linux", "server", "administration", "sysadmin"], "English"),
        ("Cloud Architecture Patterns for Microservices", "cloud-microservices", "Design patterns for building resilient microservice architectures on AWS, Azure, and Google Cloud Platform.", "techblog.example.com", ["cloud", "microservices", "architecture", "AWS"], "English"),
        ("Développement d'Applications Mobiles avec React Native", "react-native-mobile", "Guide complet pour créer des applications mobiles multiplateformes avec React Native, incluant navigation, état et APIs natives.", "devtutorials-fr.example.com", ["React Native", "mobile", "développement", "JavaScript"], "French"),
        ("GraphQL vs REST: Choosing the Right API Architecture", "graphql-vs-rest", "Comprehensive comparison of GraphQL and REST API architectures with performance benchmarks and use case recommendations.", "techblog.example.com", ["GraphQL", "REST", "API", "web development"], "English"),
        ("WebAssembly: Running Native Code in the Browser", "webassembly-guide", "How WebAssembly enables near-native performance in web applications and its implications for the future of web development.", "devtutorials.example.com", ["WebAssembly", "browser", "performance", "web"], "English"),
        ("Data Engineering with Apache Spark", "apache-spark-guide", "Building scalable data pipelines with Apache Spark, covering batch processing, streaming, and machine learning integration.", "techblog.example.com", ["Spark", "data engineering", "big data", "pipeline"], "English"),
        ("Computer Vision Applications in Manufacturing", "cv-manufacturing", "How computer vision systems are automating quality inspection, defect detection, and inventory tracking in factories.", "techblog.example.com", ["computer vision", "manufacturing", "automation", "AI"], "English"),
        ("Zero Trust Security Architecture", "zero-trust-security", "Implementing zero trust security models in enterprise networks with identity verification, micro-segmentation, and continuous monitoring.", "cybersec-weekly.example.com", ["zero trust", "security", "enterprise", "networking"], "English"),
        ("Progressive Web Apps: The Future of Mobile", "pwa-future-mobile", "Building progressive web apps that deliver native-like experiences with offline support, push notifications, and fast loading.", "devtutorials.example.com", ["PWA", "mobile", "web apps", "offline"], "English"),
        ("API Gateway Design Patterns", "api-gateway-patterns", "Common API gateway patterns for managing microservice traffic including rate limiting, authentication, and request transformation.", "devtutorials.example.com", ["API gateway", "microservices", "design patterns", "backend"], "English"),
    ],
    "Science": [
        ("Climate Change Impact on Arctic Ecosystems", "arctic-climate-impact", "New research reveals accelerating ice loss in the Arctic and its cascading effects on polar bear populations and marine biodiversity.", "sciencedaily.example.com", ["climate change", "Arctic", "ecology", "research"], "English"),
        ("CRISPR Gene Editing: Medical Breakthroughs", "crispr-medical-breakthroughs", "How CRISPR-Cas9 technology is enabling targeted treatments for genetic diseases including sickle cell and certain cancers.", "sciencedaily.example.com", ["CRISPR", "gene editing", "medicine", "genetics"], "English"),
        ("James Webb Space Telescope Discoveries", "jwst-discoveries-2025", "The latest discoveries from the James Webb Space Telescope, including exoplanet atmospheres and early universe observations.", "spacenews.example.com", ["JWST", "astronomy", "space", "telescope"], "English"),
        ("Neuroscience of Sleep and Memory Consolidation", "sleep-memory-neuroscience", "Research into how different sleep stages contribute to memory formation, learning, and cognitive restoration.", "mindscience.example.com", ["neuroscience", "sleep", "memory", "brain"], "English"),
        ("Neue Erkenntnisse in der Teilchenphysik", "teilchenphysik-2025", "Aktuelle Durchbrüche am CERN und ihre Bedeutung für das Verständnis der fundamentalen Kräfte des Universums.", "wissenschaft.example.com", ["Teilchenphysik", "CERN", "Physik", "Forschung"], "German"),
        ("Marine Biology: Deep Sea Ecosystem Discoveries", "deep-sea-ecosystems", "Newly discovered deep-sea hydrothermal vent communities reveal previously unknown chemosynthetic organisms and mineral deposits.", "sciencedaily.example.com", ["marine biology", "deep sea", "ecology", "discovery"], "English"),
        ("Fusion Energy Progress: ITER and Beyond", "fusion-energy-progress", "Status update on the ITER project and private fusion ventures racing to achieve net energy gain from nuclear fusion.", "sciencedaily.example.com", ["fusion", "energy", "ITER", "nuclear"], "English"),
        ("Microbiome Research: Gut-Brain Axis", "gut-brain-microbiome", "How the gut microbiome influences brain function, mood, and behavior through the vagus nerve and immune signaling.", "mindscience.example.com", ["microbiome", "gut-brain", "bacteria", "health"], "English"),
        ("Recherche sur les Vaccins à ARN Messager", "vaccins-arnm-recherche", "Les avancées dans la technologie des vaccins à ARN messager et leurs applications potentielles contre le cancer et les maladies infectieuses.", "sciencedaily-fr.example.com", ["vaccins", "ARN messager", "recherche", "médecine"], "French"),
        ("Gravitational Wave Detection: New Frontiers", "gravitational-waves-new", "Third-generation gravitational wave detectors promise to observe mergers at cosmological distances and test general relativity.", "spacenews.example.com", ["gravitational waves", "LIGO", "physics", "astronomy"], "English"),
        ("Advances in Synthetic Biology", "synthetic-biology-advances", "Engineering biological systems for applications in medicine, agriculture, and sustainable manufacturing.", "sciencedaily.example.com", ["synthetic biology", "bioengineering", "research", "biotechnology"], "English"),
        ("Paleontology: New Dinosaur Species Discovered", "new-dinosaur-species", "Remarkable fossil finds in Patagonia reveal a new titanosaur species that may have been the largest land animal ever.", "sciencedaily.example.com", ["paleontology", "dinosaurs", "fossils", "discovery"], "English"),
        ("Dark Matter Detection Experiments Update", "dark-matter-2025", "Latest results from underground dark matter detectors and new theoretical models for weakly interacting massive particles.", "spacenews.example.com", ["dark matter", "physics", "cosmology", "experiments"], "English"),
        ("Exoplanet Habitability: Water Worlds", "exoplanet-water-worlds", "New discoveries of ocean-covered exoplanets and what they mean for the search for extraterrestrial life.", "spacenews.example.com", ["exoplanets", "habitability", "astrobiology", "space"], "English"),
        ("Epigenetics: How Environment Shapes Gene Expression", "epigenetics-environment", "Understanding how environmental factors modify gene expression without changing DNA sequences and their implications for health.", "sciencedaily.example.com", ["epigenetics", "genetics", "environment", "biology"], "English"),
        ("Quantum Entanglement: Einstein's Spooky Action", "quantum-entanglement", "The physics of quantum entanglement explained, from Einstein's skepticism to modern quantum communication applications.", "sciencedaily.example.com", ["quantum", "entanglement", "physics", "communication"], "English"),
    ],
    "Health & Fitness": [
        ("Guía Completa de Yoga para Principiantes", "yoga-principiantes", "Todo lo que necesitas saber para comenzar tu práctica de yoga, incluyendo posturas básicas, técnicas de respiración y meditación.", "bienestar.example.com", ["yoga", "fitness", "beginners", "wellness"], "Spanish"),
        ("Mediterranean Diet: Science-Backed Benefits", "mediterranean-diet-benefits", "Clinical evidence supporting the Mediterranean diet for heart health, cognitive function, and longevity.", "healthnews.example.com", ["Mediterranean diet", "nutrition", "heart health", "longevity"], "English"),
        ("Krafttraining für Anfänger: Der Komplette Leitfaden", "krafttraining-anfaenger", "Der komplette Leitfaden zum Krafttraining für Anfänger mit Trainingsplänen, Übungsanleitungen und Ernährungstipps.", "fitness-de.example.com", ["Krafttraining", "Anfänger", "Fitness", "Ernährung"], "German"),
        ("Sleep Optimization: Evidence-Based Strategies", "sleep-optimization", "Research-backed strategies for improving sleep quality including circadian rhythm management, sleep hygiene, and supplementation.", "healthnews.example.com", ["sleep", "optimization", "health", "circadian rhythm"], "English"),
        ("Mental Health in the Digital Age", "mental-health-digital", "Understanding the impact of social media, remote work, and screen time on mental health and practical coping strategies.", "mindscience.example.com", ["mental health", "digital wellness", "social media", "psychology"], "English"),
        ("High-Intensity Interval Training: Complete Guide", "hiit-complete-guide", "The science behind HIIT workouts and structured programs for fat loss, cardiovascular fitness, and athletic performance.", "healthnews.example.com", ["HIIT", "exercise", "fitness", "cardio"], "English"),
        ("Plant-Based Nutrition for Athletes", "plant-based-athletes", "How elite athletes are fueling performance with plant-based diets, including meal planning and protein optimization strategies.", "healthnews.example.com", ["plant-based", "nutrition", "athletes", "vegan"], "English"),
        ("Prévention du Diabète par l'Alimentation", "prevention-diabete", "Guide nutritionnel pour la prévention du diabète de type 2, incluant le contrôle glycémique et les recommandations alimentaires.", "sante-fr.example.com", ["diabète", "prévention", "nutrition", "santé"], "French"),
        ("Stretching and Flexibility for Office Workers", "stretching-office-workers", "Desk-friendly stretching routines to combat sedentary lifestyle effects, reduce back pain, and improve posture.", "healthnews.example.com", ["stretching", "flexibility", "office", "posture"], "English"),
        ("Running a Marathon: Training Plan for Beginners", "marathon-training-beginners", "16-week marathon training plan for first-time runners covering mileage buildup, nutrition, injury prevention, and race strategy.", "healthnews.example.com", ["marathon", "running", "training", "endurance"], "English"),
        ("Vitamins and Supplements: What the Research Says", "vitamins-supplements-research", "Evidence-based review of popular dietary supplements including vitamin D, omega-3, magnesium, and probiotics.", "healthnews.example.com", ["vitamins", "supplements", "research", "nutrition"], "English"),
        ("Functional Fitness for Everyday Life", "functional-fitness-guide", "Training programs designed to improve strength and mobility for daily activities like lifting, climbing, and carrying.", "healthnews.example.com", ["functional fitness", "strength", "mobility", "exercise"], "English"),
        ("Mindfulness Meditation: A Scientific Perspective", "mindfulness-science", "Research on how mindfulness meditation affects brain structure, stress hormones, and emotional regulation.", "mindscience.example.com", ["mindfulness", "meditation", "neuroscience", "stress"], "English"),
    ],
    "Finance": [
        ("Global Stock Market Analysis Q1 2025", "stock-market-q1-2025", "Detailed analysis of global stock market performance in the first quarter of 2025, with focus on tech sector growth and emerging markets.", "finreview.example.com", ["stocks", "finance", "market analysis", "investing"], "English"),
        ("Cryptocurrency Regulation: Global Overview", "crypto-regulation-global", "A comprehensive look at how different countries are approaching cryptocurrency regulation in 2025, from the EU's MiCA to Asia's frameworks.", "finreview.example.com", ["cryptocurrency", "regulation", "blockchain", "policy"], "English"),
        ("Personal Finance: Building an Emergency Fund", "emergency-fund-guide", "Step-by-step guide to building and maintaining an emergency fund, including optimal savings vehicles and target calculations.", "moneysmart.example.com", ["personal finance", "savings", "emergency fund", "budgeting"], "English"),
        ("Electric Vehicle Market Investment Analysis", "ev-market-investment", "Investment outlook for the electric vehicle sector covering major manufacturers, battery technology, and charging infrastructure stocks.", "finreview.example.com", ["electric vehicles", "investment", "stocks", "EV market"], "English"),
        ("Inversiones Sostenibles: Guía ESG", "inversiones-esg", "Cómo integrar criterios ambientales, sociales y de gobernanza en tu estrategia de inversión para rendimientos sostenibles.", "finanzas.example.com", ["ESG", "inversiones", "sostenibilidad", "finanzas"], "Spanish"),
        ("Real Estate Market Trends 2025", "real-estate-trends-2025", "Analysis of residential and commercial real estate markets across major metropolitan areas with price forecasts.", "finreview.example.com", ["real estate", "market trends", "housing", "investment"], "English"),
        ("Retirement Planning: 401k and IRA Strategies", "retirement-planning-strategies", "Maximizing retirement savings through optimal 401k contribution strategies, IRA conversions, and Social Security timing.", "moneysmart.example.com", ["retirement", "401k", "IRA", "financial planning"], "English"),
        ("Indexfonds für Einsteiger", "indexfonds-einsteiger", "Wie Sie mit Indexfonds und ETFs ein diversifiziertes Portfolio aufbauen können, mit Vergleich der besten Fonds in Deutschland.", "finanzen-de.example.com", ["Indexfonds", "ETF", "Anlegen", "Portfolio"], "German"),
        ("Federal Reserve Interest Rate Outlook", "fed-interest-rate-2025", "Analysis of Federal Reserve monetary policy and expected interest rate trajectory through 2025 and beyond.", "finreview.example.com", ["Federal Reserve", "interest rates", "monetary policy", "economy"], "English"),
        ("Tax Optimization Strategies for Small Businesses", "tax-strategies-small-biz", "Legal tax reduction strategies for small business owners including deductions, entity structuring, and retirement plan contributions.", "moneysmart.example.com", ["taxes", "small business", "deductions", "strategy"], "English"),
        ("Venture Capital Trends in AI Startups", "vc-trends-ai-startups", "Tracking venture capital investment patterns in artificial intelligence companies, from seed to late stage.", "finreview.example.com", ["venture capital", "AI", "startups", "investment"], "English"),
        ("Inflation Hedging Strategies for 2025", "inflation-hedging-2025", "Portfolio strategies to protect against inflation including TIPS, commodities, real estate, and inflation-linked bonds.", "finreview.example.com", ["inflation", "hedging", "portfolio", "investing"], "English"),
        ("Budgeting Apps Comparison for Millennials", "budgeting-apps-millennials", "Head-to-head review of the top budgeting apps including YNAB, Mint, Copilot, and Monarch for millennial users.", "moneysmart.example.com", ["budgeting", "apps", "personal finance", "millennials"], "English"),
    ],
    "Travel": [
        ("Southeast Asia Budget Travel Guide", "southeast-asia-budget", "How to explore Thailand, Vietnam, Cambodia, and Indonesia on a budget with tips on accommodation, transport, and must-see destinations.", "travelasia.example.com", ["Southeast Asia", "budget travel", "backpacking", "adventure"], "English"),
        ("Japan Cultural Heritage Tours", "japan-cultural-tours", "Explore Japan's UNESCO World Heritage sites from ancient Kyoto temples to Hiroshima's Peace Memorial and Nara's deer park.", "wanderlust.example.com", ["Japan", "cultural tourism", "heritage", "temples"], "English"),
        ("Les Plus Beaux Sentiers de Randonnée en France", "sentiers-randonnee-france", "Guide des meilleurs sentiers de randonnée en France, du GR20 en Corse au Tour du Mont Blanc, avec informations pratiques et niveaux de difficulté.", "voyagefr.example.com", ["randonnée", "France", "sentiers", "nature"], "French"),
        ("Iceland Northern Lights Viewing Guide", "iceland-northern-lights", "Best times, locations, and tips for seeing the aurora borealis in Iceland, including photography settings and tour recommendations.", "wanderlust.example.com", ["Iceland", "Northern Lights", "aurora", "travel guide"], "English"),
        ("Destinos Gastronómicos en América Latina", "destinos-gastronomicos-latam", "Los mejores destinos para turismo gastronómico en América Latina, desde la cocina peruana hasta los asados argentinos.", "viajes.example.com", ["gastronomía", "América Latina", "turismo", "comida"], "Spanish"),
        ("Backpacking Through New Zealand", "backpacking-new-zealand", "Complete guide to backpacking New Zealand's North and South Islands including the Milford Track, Tongariro, and hidden gems.", "wanderlust.example.com", ["New Zealand", "backpacking", "hiking", "adventure"], "English"),
        ("Mediterranean Cruise Planning Guide", "mediterranean-cruise", "Everything you need to plan a Mediterranean cruise including port highlights, excursion tips, and seasonal recommendations.", "wanderlust.example.com", ["cruise", "Mediterranean", "Europe", "travel planning"], "English"),
        ("Safari-Reiseführer für Ostafrika", "safari-ostafrika", "Umfassender Reiseführer für Safari-Abenteuer in Kenia, Tansania und Uganda mit den besten Nationalparks und Reisezeiten.", "reisen-de.example.com", ["Safari", "Afrika", "Wildtiere", "Reise"], "German"),
        ("Digital Nomad Destinations 2025", "digital-nomad-2025", "Top cities for digital nomads in 2025 ranked by cost of living, internet speed, visa policies, and coworking spaces.", "wanderlust.example.com", ["digital nomad", "remote work", "travel", "coworking"], "English"),
        ("Ancient Ruins: World's Most Impressive Archaeological Sites", "ancient-ruins-world", "From Machu Picchu to Angkor Wat, a guide to visiting the world's most spectacular ancient ruins and archaeological sites.", "wanderlust.example.com", ["ruins", "archaeology", "ancient history", "tourism"], "English"),
        ("Road Trip Along the Pacific Coast Highway", "pacific-coast-highway", "Itinerary for the ultimate Pacific Coast Highway road trip from San Francisco to Los Angeles with stops and scenic viewpoints.", "wanderlust.example.com", ["road trip", "California", "Pacific Coast", "scenic drive"], "English"),
        ("Scuba Diving Destinations: Best Coral Reefs", "scuba-diving-reefs", "Guide to the world's best scuba diving destinations from the Great Barrier Reef to Raja Ampat and the Maldives.", "wanderlust.example.com", ["scuba diving", "coral reefs", "ocean", "adventure"], "English"),
        ("Train Travel Across Europe: Eurail Guide", "eurail-train-europe", "How to explore Europe by train using Eurail passes with route suggestions, booking tips, and scenic railway highlights.", "wanderlust.example.com", ["train travel", "Europe", "Eurail", "railway"], "English"),
        ("Voluntourism: Ethical Travel and Giving Back", "voluntourism-ethical", "How to find meaningful volunteer travel opportunities while avoiding programs that do more harm than good.", "wanderlust.example.com", ["voluntourism", "ethical travel", "volunteering", "responsible"], "English"),
    ],
    "Food & Cooking": [
        ("Recettes Traditionnelles de la Cuisine Française", "recettes-traditionnelles", "Découvrez les meilleures recettes traditionnelles françaises, du coq au vin au gratin dauphinois, avec des instructions détaillées.", "cuisine-fr.example.com", ["cooking", "French cuisine", "recipes", "traditional"], "French"),
        ("Farm-to-Table Movement: Sourcing Local Ingredients", "farm-to-table-movement", "The growing farm-to-table movement and its impact on sustainable agriculture, local economies, and culinary innovation.", "foodtrends.example.com", ["farm-to-table", "sustainable food", "local", "organic"], "English"),
        ("Cocina Mexicana: Sabores Auténticos", "cocina-mexicana-autentica", "Descubre los sabores auténticos de la cocina mexicana con recetas de mole, tamales, pozole y otros platos tradicionales.", "cocinamex.example.com", ["Mexican cuisine", "recipes", "traditional", "cooking"], "Spanish"),
        ("Sourdough Bread Baking: From Starter to Loaf", "sourdough-bread-guide", "Complete guide to creating and maintaining a sourdough starter, with recipes for artisan bread, pizza dough, and focaccia.", "foodtrends.example.com", ["sourdough", "bread", "baking", "artisan"], "English"),
        ("Fermentation at Home: Kimchi, Kombucha, and More", "home-fermentation-guide", "How to ferment foods at home including kimchi, kombucha, sauerkraut, and kefir with safety tips and troubleshooting.", "foodtrends.example.com", ["fermentation", "kimchi", "kombucha", "probiotics"], "English"),
        ("Indian Spice Guide: Flavors and Health Benefits", "indian-spice-guide", "Comprehensive guide to Indian spices including turmeric, cumin, cardamom, and their culinary uses and health benefits.", "foodtrends.example.com", ["Indian cuisine", "spices", "cooking", "health"], "English"),
        ("Japanische Sushi-Kunst für Anfänger", "sushi-kunst-anfaenger", "Lernen Sie die Kunst der Sushi-Zubereitung mit Anleitungen zu Nigiri, Maki und Sashimi sowie Tipps zur Auswahl von frischem Fisch.", "kochkunst-de.example.com", ["Sushi", "japanische Küche", "Kochen", "Anfänger"], "German"),
        ("Vegan Desserts: Indulgent Plant-Based Treats", "vegan-desserts-guide", "Decadent vegan dessert recipes from chocolate mousse to ice cream, proving plant-based can be just as indulgent.", "foodtrends.example.com", ["vegan", "desserts", "plant-based", "baking"], "English"),
        ("Wine Pairing Fundamentals", "wine-pairing-guide", "A beginner's guide to pairing wine with food, covering red, white, rosé, and sparkling wines with various cuisines.", "foodtrends.example.com", ["wine", "pairing", "food", "tasting"], "English"),
        ("BBQ and Grilling: Regional Styles Across America", "bbq-regional-styles", "Exploring American BBQ traditions from Texas brisket to Carolina pulled pork, Kansas City ribs, and Memphis dry rub.", "foodtrends.example.com", ["BBQ", "grilling", "American cuisine", "smoking"], "English"),
        ("Thai Street Food: Essential Dishes", "thai-street-food-guide", "A guide to must-try Thai street food from pad thai and som tam to mango sticky rice with tips on finding the best stalls.", "foodtrends.example.com", ["Thai food", "street food", "cooking", "Asia"], "English"),
        ("Chocolate Making: Bean to Bar Process", "chocolate-bean-to-bar", "The complete process of artisan chocolate making from cacao bean sourcing and roasting to tempering and molding.", "foodtrends.example.com", ["chocolate", "artisan", "cacao", "confectionery"], "English"),
        ("Cuisine Libanaise: Mezzé et Traditions", "cuisine-libanaise-mezze", "Découvrez les saveurs de la cuisine libanaise avec des recettes de houmous, taboulé, falafel et autres mezzés traditionnels.", "cuisine-fr.example.com", ["cuisine libanaise", "mezzé", "recettes", "Moyen-Orient"], "French"),
    ],
    "Arts & Culture": [
        ("L'Art Impressionniste au Musée d'Orsay", "impressionnisme-orsay", "Explorez les chefs-d'œuvre impressionnistes du Musée d'Orsay, de Monet à Renoir, et découvrez l'histoire de ce mouvement artistique révolutionnaire.", "artculture-fr.example.com", ["Impressionism", "Orsay", "Monet", "French art"], "French"),
        ("Jazz Improvisation: Theory and Practice", "jazz-improvisation-guide", "Master jazz improvisation techniques including chord extensions, modal playing, and developing your own musical voice.", "musicworld.example.com", ["jazz", "improvisation", "music theory", "performance"], "English"),
        ("Renaissance Art: From Florence to Rome", "renaissance-art-guide", "A guide to the greatest Renaissance masterpieces from Botticelli's Birth of Venus to Michelangelo's Sistine Chapel ceiling.", "artculture-fr.example.com", ["Renaissance", "art", "Florence", "Michelangelo"], "English"),
        ("Digital Photography Composition Techniques", "photography-composition", "Master the rules of composition in digital photography including the rule of thirds, leading lines, and golden ratio.", "cultura.example.com", ["photography", "composition", "digital art", "techniques"], "English"),
        ("Contemporary Street Art Around the World", "street-art-global", "A tour of the world's most vibrant street art scenes from Bushwick to Berlin, Shoreditch to São Paulo.", "artculture-fr.example.com", ["street art", "graffiti", "urban art", "culture"], "English"),
        ("Classical Music for Beginners: A Listening Guide", "classical-music-beginners", "An accessible introduction to classical music from Baroque to Romantic era with curated playlists and historical context.", "musicworld.example.com", ["classical music", "listening guide", "Beethoven", "Mozart"], "English"),
        ("El Muralismo Mexicano: Rivera, Orozco y Siqueiros", "muralismo-mexicano", "Historia y significado del movimiento muralista mexicano y sus tres grandes maestros: Rivera, Orozco y Siqueiros.", "cultura.example.com", ["muralismo", "arte mexicano", "Rivera", "cultura"], "Spanish"),
        ("Modern Architecture: Iconic Buildings of the 21st Century", "modern-architecture-icons", "Exploring groundbreaking architectural designs from the Burj Khalifa to the Sydney Opera House renovation and new sustainable buildings.", "artculture-fr.example.com", ["architecture", "modern design", "buildings", "urban"], "English"),
        ("Film Noir: A Guide to Classic Cinema", "film-noir-classics", "Deep dive into the film noir genre covering essential films, cinematography techniques, and the cultural context of 1940s Hollywood.", "musicworld.example.com", ["film noir", "cinema", "classic movies", "Hollywood"], "English"),
        ("Pottery and Ceramics: Beginner's Workshop Guide", "pottery-beginners-guide", "Learn the fundamentals of pottery including hand-building, wheel throwing, glazing, and kiln firing techniques.", "artculture-fr.example.com", ["pottery", "ceramics", "crafts", "art workshop"], "English"),
        ("Graphic Novel Revolution: Comics as Literature", "graphic-novel-literature", "How graphic novels have evolved from pulp entertainment to recognized literary art with analysis of seminal works.", "musicworld.example.com", ["graphic novels", "comics", "literature", "art"], "English"),
        ("World Music Traditions: African Rhythms", "african-music-traditions", "Exploring the rich musical heritage of West Africa including djembe drumming, highlife, and the roots of modern genres.", "musicworld.example.com", ["world music", "African", "drums", "traditions"], "English"),
    ],
    "History": [
        ("Die Geschichte der Berliner Mauer", "berliner-mauer-geschichte", "Eine umfassende Darstellung der Geschichte der Berliner Mauer, von ihrem Bau 1961 bis zu ihrem Fall 1989 und den politischen Folgen.", "geschichtswelt.example.com", ["Berlin Wall", "history", "Germany", "Cold War"], "German"),
        ("Ancient Roman Engineering Marvels", "roman-engineering-marvels", "How Roman engineers built aqueducts, roads, and the Colosseum using techniques that influence construction to this day.", "historybuff.example.com", ["Rome", "engineering", "ancient history", "architecture"], "English"),
        ("The Silk Road: Trade Routes that Shaped Civilization", "silk-road-history", "How ancient trade routes connecting China, Central Asia, and Europe exchanged goods, ideas, religions, and technologies.", "historybuff.example.com", ["Silk Road", "trade", "ancient history", "civilization"], "English"),
        ("World War II: The Pacific Theater", "wwii-pacific-theater", "A comprehensive account of WWII in the Pacific from Pearl Harbor to the atomic bombings and Japan's surrender.", "historybuff.example.com", ["WWII", "Pacific War", "military history", "Japan"], "English"),
        ("L'Égypte Ancienne: Les Secrets des Pyramides", "secrets-pyramides-egypte", "Nouvelles découvertes archéologiques révélant les méthodes de construction des grandes pyramides de Gizeh.", "histoire-fr.example.com", ["Égypte", "pyramides", "archéologie", "histoire ancienne"], "French"),
        ("The Age of Exploration: European Maritime Discoveries", "age-of-exploration", "Tracing the voyages of Columbus, Magellan, and da Gama and their lasting impact on world history and globalization.", "historybuff.example.com", ["exploration", "maritime", "Columbus", "history"], "English"),
        ("Medieval Castles of Europe", "medieval-castles-europe", "Architectural evolution and strategic significance of medieval castles from motte-and-bailey to concentric fortifications.", "historybuff.example.com", ["castles", "medieval", "Europe", "architecture"], "English"),
        ("Industrial Revolution: How It Changed the World", "industrial-revolution-impact", "The social, economic, and technological transformations of the Industrial Revolution and their lasting consequences.", "historybuff.example.com", ["Industrial Revolution", "history", "technology", "economy"], "English"),
        ("Historia del Imperio Inca", "imperio-inca-historia", "La historia del Tahuantinsuyo, desde su fundación en Cusco hasta la conquista española, incluyendo arquitectura y organización social.", "historia.example.com", ["Inca", "imperio", "historia", "Perú"], "Spanish"),
        ("The Space Race: From Sputnik to Apollo", "space-race-history", "How Cold War rivalry between the US and USSR drove humanity's first steps into space, from satellites to Moon landings.", "historybuff.example.com", ["space race", "Apollo", "Cold War", "NASA"], "English"),
        ("Viking Age: Exploration, Trade, and Settlement", "viking-age-history", "The Viking expansion across the North Atlantic, their sophisticated navigation techniques, and lasting cultural influence.", "historybuff.example.com", ["Vikings", "Norse", "exploration", "medieval"], "English"),
        ("The French Revolution: Causes and Consequences", "french-revolution-causes", "Analysis of the social, economic, and political factors that led to the French Revolution and its lasting impact on democracy.", "historybuff.example.com", ["French Revolution", "history", "democracy", "Europe"], "English"),
        ("Ancient Greek Philosophy: From Socrates to Aristotle", "greek-philosophy-guide", "Survey of ancient Greek philosophy covering Socratic method, Plato's forms, and Aristotle's empiricism.", "historybuff.example.com", ["Greek philosophy", "Socrates", "Plato", "Aristotle"], "English"),
    ],
    "Education": [
        ("Online Learning Platforms Comparison 2025", "online-learning-comparison", "Detailed comparison of major online learning platforms including Coursera, edX, Udemy, and Khan Academy.", "edureview.example.com", ["online learning", "MOOCs", "education", "courses"], "English"),
        ("German Grammar Fundamentals for Beginners", "german-grammar-beginners", "A comprehensive guide to German grammar for beginners with exercises on articles, cases, verbs, and sentence structure.", "sprachschule.example.com", ["German", "grammar", "language learning", "beginners"], "English"),
        ("Teaching Mathematics with Visual Methods", "visual-math-teaching", "How visual and manipulative approaches can improve mathematical understanding from elementary through high school levels.", "edureview.example.com", ["mathematics", "teaching", "visual learning", "education"], "English"),
        ("STEM Education: Bridging the Gender Gap", "stem-gender-gap", "Strategies and programs successfully increasing female participation in science, technology, engineering, and mathematics.", "edureview.example.com", ["STEM", "gender gap", "education", "diversity"], "English"),
        ("Study Techniques Backed by Cognitive Science", "study-techniques-science", "Evidence-based study methods including spaced repetition, retrieval practice, and interleaving for effective learning.", "edureview.example.com", ["study techniques", "cognitive science", "learning", "education"], "English"),
        ("Aprendizaje de Idiomas: Técnicas de Inmersión", "aprendizaje-idiomas-inmersion", "Métodos efectivos de inmersión lingüística para aprender idiomas extranjeros, desde aplicaciones hasta estancias en el extranjero.", "educacion.example.com", ["idiomas", "inmersión", "aprendizaje", "educación"], "Spanish"),
        ("University Rankings Methodology Explained", "university-rankings-explained", "How major ranking systems like QS, THE, and ARWU evaluate universities and what students should actually consider.", "edureview.example.com", ["university rankings", "higher education", "methodology", "students"], "English"),
        ("Coding Bootcamps: Are They Worth It in 2025?", "coding-bootcamps-2025", "Analysis of coding bootcamp outcomes including job placement rates, salary data, and comparison with traditional CS degrees.", "edureview.example.com", ["coding bootcamp", "programming", "career", "education"], "English"),
        ("Special Education: Inclusive Classroom Strategies", "inclusive-education-strategies", "Best practices for creating inclusive classrooms that support students with diverse learning needs and disabilities.", "edureview.example.com", ["special education", "inclusive", "classroom", "teaching"], "English"),
        ("L'Éducation Montessori: Principes et Méthodes", "education-montessori", "Les principes fondamentaux de la pédagogie Montessori et son application dans les écoles modernes du monde entier.", "education-fr.example.com", ["Montessori", "éducation", "pédagogie", "enfants"], "French"),
        ("Academic Writing: Structure and Citation Guide", "academic-writing-guide", "How to write effective academic papers covering thesis development, argument structure, APA/MLA citation, and peer review.", "edureview.example.com", ["academic writing", "citations", "research", "university"], "English"),
        ("Early Childhood Education: Play-Based Learning", "play-based-learning", "Research supporting play-based approaches in early childhood education and practical implementation strategies.", "edureview.example.com", ["early childhood", "play-based", "education", "development"], "English"),
    ],
    "Sports": [
        ("Olympic Records: History of Athletic Achievement", "olympic-records-history", "A comprehensive look at Olympic record progressions across major disciplines and the athletes who pushed human limits.", "sportscenter.example.com", ["Olympics", "records", "athletics", "history"], "English"),
        ("Soccer Tactics: Modern Formations Explained", "soccer-tactics-formations", "Analysis of contemporary soccer formations from 4-3-3 to 3-5-2 with tactical breakdowns of top European clubs.", "sportscenter.example.com", ["soccer", "tactics", "formations", "analysis"], "English"),
        ("Tennis Grand Slam Statistics and Analysis", "tennis-grand-slam-stats", "Statistical deep dive into Grand Slam tennis including surface preferences, head-to-head records, and performance trends.", "sportscenter.example.com", ["tennis", "Grand Slam", "statistics", "analysis"], "English"),
        ("Fútbol Sudamericano: Las Mejores Ligas", "futbol-sudamericano-ligas", "Análisis de las principales ligas de fútbol en Sudamérica, incluyendo la Libertadores y los clubes más exitosos.", "deportes.example.com", ["fútbol", "Sudamérica", "ligas", "deportes"], "Spanish"),
        ("Formula 1: Engineering Behind the Speed", "f1-engineering-speed", "The aerodynamic innovations, power unit technology, and tire strategies that determine success in Formula 1 racing.", "sportscenter.example.com", ["Formula 1", "engineering", "racing", "motorsport"], "English"),
        ("Basketball Analytics: The NBA's Data Revolution", "nba-analytics-revolution", "How advanced statistics and machine learning are transforming player evaluation, game strategy, and draft decisions in the NBA.", "sportscenter.example.com", ["basketball", "NBA", "analytics", "sports data"], "English"),
        ("Marathon World Records: Breaking the Barrier", "marathon-records-evolution", "The history of marathon world record progression and the physiological breakthroughs enabling sub-2-hour performances.", "sportscenter.example.com", ["marathon", "world records", "running", "endurance"], "English"),
        ("Cricket: Understanding Test Match Strategy", "cricket-test-strategy", "A guide to the tactical complexities of Test cricket including field placements, bowling plans, and batting declarations.", "sportscenter.example.com", ["cricket", "Test match", "strategy", "analysis"], "English"),
        ("Swimming Technique: Freestyle Stroke Analysis", "freestyle-swimming-technique", "Biomechanical analysis of freestyle swimming technique with drills to improve efficiency, speed, and breathing.", "sportscenter.example.com", ["swimming", "freestyle", "technique", "training"], "English"),
        ("Rock Climbing: Indoor to Outdoor Transition", "rock-climbing-transition", "Guide for indoor climbers transitioning to outdoor rock climbing covering gear, safety, route reading, and ethics.", "sportscenter.example.com", ["rock climbing", "outdoor", "bouldering", "adventure"], "English"),
        ("Golf Course Strategy for Mid-Handicap Players", "golf-strategy-mid-handicap", "Course management strategies for golfers in the 10-20 handicap range including club selection and risk assessment.", "sportscenter.example.com", ["golf", "strategy", "handicap", "course management"], "English"),
    ],
    "Government & Politics": [
        ("Understanding the US Electoral College System", "us-electoral-college", "How the Electoral College works, its historical origins, and ongoing debates about reform and alternatives.", "govwatch.example.com", ["Electoral College", "elections", "US politics", "democracy"], "English"),
        ("European Union Climate Legislation 2025", "eu-climate-legislation", "Analysis of the EU's latest climate policy framework including emissions targets, carbon border adjustments, and green subsidies.", "govwatch.example.com", ["EU", "climate policy", "legislation", "environment"], "English"),
        ("Digital Privacy Laws: GDPR and Beyond", "digital-privacy-laws", "Comparison of data privacy regulations worldwide including GDPR, CCPA, and emerging frameworks in Asia and Africa.", "govwatch.example.com", ["privacy", "GDPR", "data protection", "regulation"], "English"),
        ("La Politique Énergétique de la France", "politique-energetique-france", "Analyse de la stratégie énergétique française incluant le nucléaire, les énergies renouvelables et les objectifs climatiques.", "politique-fr.example.com", ["énergie", "politique", "France", "nucléaire"], "French"),
        ("Public Health Policy Lessons from Pandemics", "pandemic-policy-lessons", "What governments learned from COVID-19 and how pandemic preparedness policies are being reformed worldwide.", "govwatch.example.com", ["public health", "pandemic", "policy", "government"], "English"),
        ("Immigration Policy Comparison: US, EU, and Australia", "immigration-policy-comparison", "Side-by-side comparison of immigration policies including visa categories, refugee processing, and citizenship pathways.", "govwatch.example.com", ["immigration", "policy", "visa", "comparison"], "English"),
        ("Cybersecurity Policy for Critical Infrastructure", "cybersecurity-critical-infra", "Government frameworks for protecting power grids, water systems, and financial networks from cyber threats.", "govwatch.example.com", ["cybersecurity", "critical infrastructure", "policy", "national security"], "English"),
        ("Universal Basic Income: Global Pilot Results", "ubi-pilot-results", "Results from universal basic income pilot programs in Finland, Kenya, and California and their policy implications.", "govwatch.example.com", ["UBI", "universal basic income", "policy", "economics"], "English"),
        ("Política de Vivienda en España", "politica-vivienda-espana", "Análisis de las políticas de vivienda en España, incluyendo regulación de alquileres y programas de vivienda social.", "politica-es.example.com", ["vivienda", "política", "España", "alquiler"], "Spanish"),
        ("Open Government Data: Transparency Initiatives", "open-government-data", "How governments worldwide are publishing open data to increase transparency, accountability, and civic participation.", "govwatch.example.com", ["open data", "transparency", "government", "civic tech"], "English"),
    ],
    "Shopping": [
        ("Best Laptops for Programmers 2025", "best-laptops-programmers", "In-depth comparison of top laptops for software development including specs, benchmarks, and value analysis.", "techdeals.example.com", ["laptops", "programming", "reviews", "comparison"], "English"),
        ("Sustainable Fashion Brands Guide", "sustainable-fashion-brands", "Curated list of ethical and sustainable fashion brands offering quality clothing with transparent supply chains.", "shopgreen.example.com", ["sustainable fashion", "ethical", "brands", "clothing"], "English"),
        ("Smart Home Devices: Complete Buyer's Guide", "smart-home-buyers-guide", "Comprehensive comparison of smart speakers, thermostats, cameras, and lighting systems for home automation.", "techdeals.example.com", ["smart home", "IoT", "automation", "reviews"], "English"),
        ("Mejores Auriculares Inalámbricos 2025", "auriculares-inalambricos-2025", "Comparativa de los mejores auriculares inalámbricos con cancelación de ruido, calidad de audio y duración de batería.", "techdeals-es.example.com", ["auriculares", "inalámbricos", "tecnología", "comparativa"], "Spanish"),
        ("Electric Bike Comparison: Commuter Models", "electric-bikes-comparison", "Head-to-head comparison of the best electric bikes for urban commuting including range, comfort, and price analysis.", "shopgreen.example.com", ["electric bikes", "commuter", "comparison", "sustainable transport"], "English"),
        ("Kitchen Appliance Reviews: Stand Mixers", "stand-mixer-reviews", "Detailed comparison of stand mixers from KitchenAid, Cuisinart, Bosch, and others with baking performance tests.", "shopgreen.example.com", ["kitchen appliances", "stand mixer", "reviews", "baking"], "English"),
        ("Best Running Shoes by Foot Type", "running-shoes-guide", "Expert guide to choosing running shoes based on foot type, gait analysis, and intended use from road to trail.", "shopgreen.example.com", ["running shoes", "reviews", "fitness", "gear"], "English"),
        ("Vergleich der Besten E-Book-Reader", "ebook-reader-vergleich", "Ausführlicher Vergleich der aktuellen E-Book-Reader von Kindle, Tolino und Kobo mit Displayqualität und Funktionsumfang.", "techdeals-de.example.com", ["E-Book-Reader", "Vergleich", "Kindle", "Tolino"], "German"),
        ("Noise-Canceling Headphones: Studio Quality Test", "noise-canceling-headphones-test", "Professional audio testing of premium noise-canceling headphones from Sony, Bose, Apple, and Sennheiser.", "techdeals.example.com", ["headphones", "noise-canceling", "audio", "reviews"], "English"),
        ("Home Office Ergonomic Setup Guide", "home-office-ergonomic", "Complete guide to creating an ergonomic home office with desk, chair, monitor, and keyboard recommendations.", "shopgreen.example.com", ["ergonomic", "home office", "desk", "health"], "English"),
        ("Camping Gear Essentials: Buyer's Guide", "camping-gear-essentials", "Must-have camping gear from tents and sleeping bags to cooking equipment and navigation tools for wilderness adventures.", "shopgreen.example.com", ["camping", "gear", "outdoor", "equipment"], "English"),
    ],
    "Entertainment": [
        ("Best Sci-Fi TV Series of 2025", "best-scifi-tv-2025", "Ranked list of the year's top science fiction television series with reviews, ratings, and streaming availability.", "entertain-hub.example.com", ["sci-fi", "TV series", "streaming", "reviews"], "English"),
        ("Video Game Design: From Concept to Release", "game-design-process", "Behind the scenes look at modern video game development covering concept art, programming, testing, and launch strategies.", "entertain-hub.example.com", ["video games", "game design", "development", "indie"], "English"),
        ("Podcast Recommendations: True Crime", "true-crime-podcasts", "Curated list of the best true crime podcasts with episode guides and content warnings for sensitive listeners.", "entertain-hub.example.com", ["podcasts", "true crime", "audio", "recommendations"], "English"),
        ("Streaming Wars: Platform Comparison 2025", "streaming-platform-comparison", "Feature-by-feature comparison of Netflix, Disney+, HBO Max, Apple TV+, and Amazon Prime Video content libraries.", "entertain-hub.example.com", ["streaming", "Netflix", "comparison", "entertainment"], "English"),
        ("Les Meilleurs Films du Festival de Cannes", "films-cannes-palmares", "Rétrospective des films les plus marquants du Festival de Cannes, des Palmes d'Or historiques aux découvertes récentes.", "cinema-fr.example.com", ["Cannes", "cinéma", "films", "festival"], "French"),
        ("Board Games Renaissance: Modern Tabletop Gaming", "board-games-renaissance", "How board games have evolved from simple family games to complex strategy experiences driving a tabletop gaming renaissance.", "entertain-hub.example.com", ["board games", "tabletop", "strategy", "hobby"], "English"),
        ("K-Pop Global Phenomenon: Industry Analysis", "kpop-global-analysis", "How K-Pop became a global cultural force and the business model behind major entertainment companies.", "entertain-hub.example.com", ["K-Pop", "music industry", "culture", "global"], "English"),
        ("Anime Guide: Essential Series for Newcomers", "anime-essential-guide", "Curated guide to the best anime series for beginners spanning action, drama, sci-fi, and slice-of-life genres.", "entertain-hub.example.com", ["anime", "guide", "series", "Japanese culture"], "English"),
        ("Virtual Reality Gaming: Headset Comparison 2025", "vr-gaming-headsets-2025", "Comparing the latest VR headsets including Meta Quest 3S, PlayStation VR2, and Apple Vision Pro for gaming performance.", "entertain-hub.example.com", ["VR", "virtual reality", "gaming", "headsets"], "English"),
        ("Escape Rooms: Design and Psychology", "escape-room-psychology", "The psychology behind escape room design including puzzle theory, flow states, and group dynamics.", "entertain-hub.example.com", ["escape rooms", "psychology", "puzzles", "entertainment"], "English"),
    ],
    "Environment": [
        ("Solar Energy: Costs and Efficiency in 2025", "solar-energy-2025", "How solar panel costs have plummeted while efficiency has soared, making solar competitive with fossil fuels globally.", "greentech.example.com", ["solar energy", "renewable", "costs", "efficiency"], "English"),
        ("Ocean Plastic Pollution: Solutions and Innovation", "ocean-plastic-solutions", "Technologies and initiatives tackling ocean plastic pollution from cleanup systems to biodegradable alternatives.", "greentech.example.com", ["ocean plastic", "pollution", "environment", "innovation"], "English"),
        ("Sustainable Agriculture: Regenerative Farming", "regenerative-farming-guide", "How regenerative agriculture practices restore soil health, sequester carbon, and improve farm profitability.", "greentech.example.com", ["agriculture", "regenerative", "sustainable", "farming"], "English"),
        ("Energías Renovables en América Latina", "energias-renovables-latam", "El crecimiento de la energía solar, eólica e hidroeléctrica en América Latina y su impacto económico y ambiental.", "medioambiente.example.com", ["energías renovables", "América Latina", "solar", "eólica"], "Spanish"),
        ("Electric Vehicle Battery Recycling", "ev-battery-recycling", "The growing challenge of recycling lithium-ion batteries from electric vehicles and emerging solutions for a circular economy.", "greentech.example.com", ["battery recycling", "EV", "lithium", "circular economy"], "English"),
        ("Biodiversity Loss: The Sixth Mass Extinction", "biodiversity-sixth-extinction", "Scientific evidence for the current biodiversity crisis and conservation strategies to protect endangered species and ecosystems.", "greentech.example.com", ["biodiversity", "extinction", "conservation", "ecology"], "English"),
        ("Carbon Capture Technology: Current State", "carbon-capture-technology", "Overview of direct air capture and point-source carbon capture technologies, costs, and deployment timelines.", "greentech.example.com", ["carbon capture", "climate tech", "emissions", "technology"], "English"),
        ("Nachhaltige Stadtplanung in Europa", "nachhaltige-stadtplanung", "Wie europäische Städte nachhaltige Stadtplanung umsetzen, von Fahrradinfrastruktur bis zu grünen Gebäuden.", "umwelt-de.example.com", ["Stadtplanung", "Nachhaltigkeit", "Europa", "Städte"], "German"),
        ("Water Conservation Technologies for Agriculture", "water-conservation-agriculture", "Innovative irrigation and water conservation technologies helping farmers reduce water usage while maintaining crop yields.", "greentech.example.com", ["water conservation", "agriculture", "irrigation", "sustainability"], "English"),
        ("Deforestation Monitoring with Satellite Data", "deforestation-satellite-monitoring", "How satellite imagery and AI are enabling real-time monitoring of deforestation in the Amazon and Southeast Asian rainforests.", "greentech.example.com", ["deforestation", "satellite", "monitoring", "rainforest"], "English"),
        ("Green Building Certification: LEED and BREEAM", "green-building-certification", "Guide to green building certification standards including LEED and BREEAM requirements, costs, and benefits.", "greentech.example.com", ["green building", "LEED", "certification", "sustainable"], "English"),
    ],
    "Business": [
        ("Startup Funding: Seed to Series A Guide", "startup-funding-guide", "Navigating early-stage startup funding from bootstrapping through angel investment to Series A venture capital.", "bizinsider.example.com", ["startups", "funding", "venture capital", "entrepreneurship"], "English"),
        ("Remote Work Culture: Building Distributed Teams", "remote-work-distributed", "Best practices for building productive remote teams including communication tools, async workflows, and culture building.", "bizinsider.example.com", ["remote work", "distributed teams", "management", "culture"], "English"),
        ("Supply Chain Resilience After Global Disruptions", "supply-chain-resilience", "How companies are restructuring supply chains for resilience using nearshoring, diversification, and digital twins.", "bizinsider.example.com", ["supply chain", "resilience", "logistics", "strategy"], "English"),
        ("Emprendimiento Social en España", "emprendimiento-social-espana", "Guía de emprendimiento social en España con casos de éxito, fuentes de financiación y marcos legales.", "negocios-es.example.com", ["emprendimiento", "social", "España", "negocios"], "Spanish"),
        ("AI in Business: Practical Implementation Guide", "ai-business-implementation", "How mid-size businesses are successfully implementing AI for customer service, operations, and decision-making.", "bizinsider.example.com", ["AI", "business", "implementation", "automation"], "English"),
        ("The Four-Day Work Week: Evidence and Outcomes", "four-day-work-week", "Results from global four-day work week trials showing impacts on productivity, employee wellbeing, and company revenue.", "bizinsider.example.com", ["work week", "productivity", "wellbeing", "employment"], "English"),
        ("Franchise Opportunities: What to Know Before Investing", "franchise-opportunities-guide", "Complete guide to evaluating franchise opportunities including FDD analysis, territory research, and financial projections.", "bizinsider.example.com", ["franchise", "investment", "business", "entrepreneurship"], "English"),
        ("E-Commerce Trends: Direct-to-Consumer Brands", "dtc-ecommerce-trends", "How direct-to-consumer brands are disrupting retail with data-driven marketing, subscription models, and community building.", "bizinsider.example.com", ["e-commerce", "DTC", "retail", "brands"], "English"),
        ("Intellectual Property Basics for Entrepreneurs", "ip-basics-entrepreneurs", "Understanding patents, trademarks, copyrights, and trade secrets and how to protect your business innovations.", "bizinsider.example.com", ["intellectual property", "patents", "trademarks", "legal"], "English"),
        ("Corporate Social Responsibility: Beyond Greenwashing", "csr-beyond-greenwashing", "How companies are implementing genuine CSR programs with measurable impact on communities and the environment.", "bizinsider.example.com", ["CSR", "corporate responsibility", "sustainability", "ethics"], "English"),
        ("Gründung eines Unternehmens in Deutschland", "unternehmensgruendung-de", "Leitfaden für die Unternehmensgründung in Deutschland mit Rechtsformen, Finanzierung und behördlichen Anforderungen.", "business-de.example.com", ["Gründung", "Unternehmen", "Deutschland", "Startup"], "German"),
    ],
}


def generate_pages():
    """Generate ~200 realistic web page index entries."""
    pages = []
    page_id = 1

    # Date range for indexed dates
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2025, 5, 30)
    date_range_days = (end_date - start_date).days

    for category_name, templates in PAGE_TEMPLATES.items():
        for title, url_path, snippet, domain, tags, language in templates:
            # Generate realistic metrics
            relevance_score = round(random.uniform(5.0, 9.9), 1)
            click_count = random.randint(200, 25000)
            days_offset = random.randint(0, date_range_days)
            date_indexed = (start_date + timedelta(days=days_offset)).strftime("%Y-%m-%d")

            url = f"https://{domain}/{url_path}"

            pages.append({
                "id": page_id,
                "title": title,
                "url": url,
                "snippet": snippet,
                "category": category_name,
                "language": language,
                "date_indexed": date_indexed,
                "relevance_score": relevance_score,
                "click_count": click_count,
                "domain": domain,
                "tags": tags,
            })
            page_id += 1

    # Shuffle to mix categories, then re-assign sequential IDs
    random.shuffle(pages)
    for i, page in enumerate(pages):
        page["id"] = i + 1

    return pages


def generate_categories(pages):
    """Generate categories with accurate page counts."""
    category_counts = {}
    for p in pages:
        cat = p["category"]
        category_counts[cat] = category_counts.get(cat, 0) + 1

    categories = []
    for cat_def in CATEGORIES:
        cat_def_copy = dict(cat_def)
        cat_def_copy["page_count"] = category_counts.get(cat_def_copy["name"], 0)
        categories.append(cat_def_copy)

    return categories


def generate_users(pages):
    """Generate 7 users with search history and bookmarks."""
    page_ids = [p["id"] for p in pages]

    users = [
        {
            "id": 1,
            "username": "alex_researcher",
            "name": "Alex Thompson",
            "email": "alex.thompson@example.com",
            "search_history": [
                {"query": "machine learning algorithms", "date": "2025-05-20"},
                {"query": "quantum computing breakthroughs", "date": "2025-05-18"},
                {"query": "CRISPR gene editing", "date": "2025-05-15"},
                {"query": "deep learning neural networks", "date": "2025-05-10"},
                {"query": "climate change Arctic", "date": "2025-05-08"},
                {"query": "fusion energy ITER", "date": "2025-05-03"},
                {"query": "dark matter detection", "date": "2025-04-28"},
            ],
            "saved_results": random.sample(page_ids, 6),
            "preferred_language": "English",
            "preferences": {"safe_search": True, "results_per_page": 10},
        },
        {
            "id": 2,
            "username": "maria_globetrotter",
            "name": "Maria Garcia",
            "email": "maria.garcia@example.com",
            "search_history": [
                {"query": "yoga para principiantes", "date": "2025-05-22"},
                {"query": "Southeast Asia budget travel", "date": "2025-05-19"},
                {"query": "recettes françaises traditionnelles", "date": "2025-05-14"},
                {"query": "Japanese gardens tour", "date": "2025-05-11"},
                {"query": "Mediterranean cruise planning", "date": "2025-05-06"},
                {"query": "cocina mexicana auténtica", "date": "2025-05-01"},
            ],
            "saved_results": random.sample(page_ids, 5),
            "preferred_language": "Spanish",
            "preferences": {"safe_search": True, "results_per_page": 20},
        },
        {
            "id": 3,
            "username": "finance_guru",
            "name": "David Chen",
            "email": "david.chen@example.com",
            "search_history": [
                {"query": "stock market analysis 2025", "date": "2025-05-21"},
                {"query": "cryptocurrency regulation", "date": "2025-05-17"},
                {"query": "electric vehicle market investment", "date": "2025-05-13"},
                {"query": "personal finance emergency fund", "date": "2025-05-09"},
                {"query": "blockchain applications", "date": "2025-05-05"},
                {"query": "venture capital AI startups", "date": "2025-05-01"},
                {"query": "Federal Reserve interest rates", "date": "2025-04-25"},
                {"query": "retirement planning 401k", "date": "2025-04-20"},
            ],
            "saved_results": random.sample(page_ids, 7),
            "preferred_language": "English",
            "preferences": {"safe_search": False, "results_per_page": 15},
        },
        {
            "id": 4,
            "username": "health_enthusiast",
            "name": "Sophie Mueller",
            "email": "sophie.mueller@example.com",
            "search_history": [
                {"query": "Mediterranean diet benefits", "date": "2025-05-23"},
                {"query": "sleep optimization strategies", "date": "2025-05-16"},
                {"query": "Krafttraining Anfänger", "date": "2025-05-12"},
                {"query": "plant-based nutrition athletes", "date": "2025-05-07"},
                {"query": "marathon training plan", "date": "2025-05-02"},
            ],
            "saved_results": random.sample(page_ids, 4),
            "preferred_language": "German",
            "preferences": {"safe_search": True, "results_per_page": 10},
        },
        {
            "id": 5,
            "username": "culture_buff",
            "name": "Jean-Pierre Lefevre",
            "email": "jp.lefevre@example.com",
            "search_history": [
                {"query": "impressionnisme Orsay", "date": "2025-05-24"},
                {"query": "jazz improvisation techniques", "date": "2025-05-20"},
                {"query": "Berlin Wall history", "date": "2025-05-15"},
                {"query": "Renaissance art history", "date": "2025-05-10"},
                {"query": "Olympic records athletics", "date": "2025-05-06"},
                {"query": "film noir classic cinema", "date": "2025-04-30"},
                {"query": "street art global tour", "date": "2025-04-25"},
            ],
            "saved_results": random.sample(page_ids, 6),
            "preferred_language": "French",
            "preferences": {"safe_search": True, "results_per_page": 10},
        },
        {
            "id": 6,
            "username": "eco_advocate",
            "name": "Priya Sharma",
            "email": "priya.sharma@example.com",
            "search_history": [
                {"query": "solar energy efficiency 2025", "date": "2025-05-25"},
                {"query": "ocean plastic pollution solutions", "date": "2025-05-21"},
                {"query": "regenerative farming practices", "date": "2025-05-17"},
                {"query": "biodiversity extinction crisis", "date": "2025-05-12"},
                {"query": "carbon capture technology", "date": "2025-05-08"},
                {"query": "sustainable fashion brands", "date": "2025-05-03"},
                {"query": "electric vehicle battery recycling", "date": "2025-04-29"},
                {"query": "EU climate legislation", "date": "2025-04-24"},
            ],
            "saved_results": random.sample(page_ids, 8),
            "preferred_language": "English",
            "preferences": {"safe_search": True, "results_per_page": 25},
        },
        {
            "id": 7,
            "username": "tech_shopper",
            "name": "Marcus Johnson",
            "email": "marcus.johnson@example.com",
            "search_history": [
                {"query": "best laptops programmers 2025", "date": "2025-05-23"},
                {"query": "smart home devices comparison", "date": "2025-05-18"},
                {"query": "electric bikes commuter", "date": "2025-05-14"},
                {"query": "running shoes foot type", "date": "2025-05-09"},
                {"query": "streaming platform comparison", "date": "2025-05-04"},
                {"query": "stand mixer reviews", "date": "2025-04-30"},
            ],
            "saved_results": random.sample(page_ids, 5),
            "preferred_language": "English",
            "preferences": {"safe_search": False, "results_per_page": 20},
        },
    ]

    return users


def generate_translations(pages):
    """Generate translation pairs for a subset of pages in non-English languages + some English pages translated."""
    translations = []
    trans_id = 1

    language_pairs = {
        "English": ["Spanish", "French", "German"],
        "French": ["English", "Spanish"],
        "Spanish": ["English", "German"],
        "German": ["English", "French"],
    }

    # Translation templates for common phrases
    title_translations = {
        # English -> Spanish
        ("Introduction to Machine Learning Algorithms", "Spanish"): "Introducción a los Algoritmos de Aprendizaje Automático",
        ("Climate Change Impact on Arctic Ecosystems", "Spanish"): "Impacto del Cambio Climático en los Ecosistemas Árticos",
        ("Mediterranean Diet: Science-Backed Benefits", "Spanish"): "Dieta Mediterránea: Beneficios Respaldados por la Ciencia",
        ("Global Stock Market Analysis Q1 2025", "Spanish"): "Análisis del Mercado Bursátil Global Q1 2025",
        ("Southeast Asia Budget Travel Guide", "Spanish"): "Guía de Viaje Económico por el Sudeste Asiático",
        ("Online Learning Platforms Comparison 2025", "Spanish"): "Comparación de Plataformas de Aprendizaje en Línea 2025",
        ("Olympic Records: History of Athletic Achievement", "Spanish"): "Récords Olímpicos: Historia del Logro Atlético",
        ("Solar Energy: Costs and Efficiency in 2025", "Spanish"): "Energía Solar: Costos y Eficiencia en 2025",
        ("Best Laptops for Programmers 2025", "Spanish"): "Mejores Portátiles para Programadores 2025",
        # English -> French
        ("Introduction to Machine Learning Algorithms", "French"): "Introduction aux Algorithmes d'Apprentissage Automatique",
        ("Quantum Computing Breakthroughs in 2025", "French"): "Avancées en Informatique Quantique en 2025",
        ("CRISPR Gene Editing: Medical Breakthroughs", "French"): "Édition Génétique CRISPR: Percées Médicales",
        ("Jazz Improvisation: Theory and Practice", "French"): "Improvisation Jazz: Théorie et Pratique",
        ("Startup Funding: Seed to Series A Guide", "French"): "Financement de Startups: Du Seed au Series A",
        ("Sleep Optimization: Evidence-Based Strategies", "French"): "Optimisation du Sommeil: Stratégies Basées sur les Preuves",
        # English -> German
        ("Climate Change Impact on Arctic Ecosystems", "German"): "Auswirkungen des Klimawandels auf arktische Ökosysteme",
        ("Web Development with Python: Flask and Django", "German"): "Webentwicklung mit Python: Flask und Django",
        ("Ancient Roman Engineering Marvels", "German"): "Antike Römische Ingenieurskunst",
        ("Blockchain Beyond Cryptocurrency: Real-World Applications", "German"): "Blockchain Jenseits von Kryptowährung: Reale Anwendungen",
        ("Ocean Plastic Pollution: Solutions and Innovation", "German"): "Ozean-Plastikverschmutzung: Lösungen und Innovation",
        # French -> English
        ("Recettes Traditionnelles de la Cuisine Française", "English"): "Traditional French Cuisine Recipes",
        ("L'Art Impressionniste au Musée d'Orsay", "English"): "Impressionist Art at the Musée d'Orsay",
        ("Les Plus Beaux Sentiers de Randonnée en France", "English"): "The Most Beautiful Hiking Trails in France",
        ("Recherche sur les Vaccins à ARN Messager", "English"): "Research on mRNA Vaccines",
        ("L'Éducation Montessori: Principes et Méthodes", "English"): "Montessori Education: Principles and Methods",
        ("La Politique Énergétique de la France", "English"): "France's Energy Policy",
        ("Les Meilleurs Films du Festival de Cannes", "English"): "The Best Films from the Cannes Festival",
        # French -> Spanish
        ("L'Art Impressionniste au Musée d'Orsay", "Spanish"): "El Arte Impresionista en el Museo de Orsay",
        ("Prévention du Diabète par l'Alimentation", "Spanish"): "Prevención de la Diabetes a través de la Alimentación",
        # Spanish -> English
        ("Guía Completa de Yoga para Principiantes", "English"): "Complete Yoga Guide for Beginners",
        ("Cocina Mexicana: Sabores Auténticos", "English"): "Mexican Cuisine: Authentic Flavors",
        ("Inversiones Sostenibles: Guía ESG", "English"): "Sustainable Investments: ESG Guide",
        ("Destinos Gastronómicos en América Latina", "English"): "Gastronomic Destinations in Latin America",
        ("Ciberseguridad para Empresas Pequeñas", "English"): "Cybersecurity for Small Businesses",
        ("El Muralismo Mexicano: Rivera, Orozco y Siqueiros", "English"): "Mexican Muralism: Rivera, Orozco and Siqueiros",
        ("Fútbol Sudamericano: Las Mejores Ligas", "English"): "South American Football: The Best Leagues",
        ("Aprendizaje de Idiomas: Técnicas de Inmersión", "English"): "Language Learning: Immersion Techniques",
        ("Energías Renovables en América Latina", "English"): "Renewable Energy in Latin America",
        ("Historia del Imperio Inca", "English"): "History of the Inca Empire",
        ("Emprendimiento Social en España", "English"): "Social Entrepreneurship in Spain",
        ("Mejores Auriculares Inalámbricos 2025", "English"): "Best Wireless Headphones 2025",
        # Spanish -> German
        ("Cocina Mexicana: Sabores Auténticos", "German"): "Mexikanische Küche: Authentische Aromen",
        ("Guía Completa de Yoga para Principiantes", "German"): "Vollständiger Yoga-Leitfaden für Anfänger",
        # German -> English
        ("Die Geschichte der Berliner Mauer", "English"): "The History of the Berlin Wall",
        ("Krafttraining für Anfänger: Der Komplette Leitfaden", "English"): "Strength Training for Beginners: The Complete Guide",
        ("Einführung in die Künstliche Intelligenz", "English"): "Introduction to Artificial Intelligence",
        ("Neue Erkenntnisse in der Teilchenphysik", "English"): "New Findings in Particle Physics",
        ("Japanische Sushi-Kunst für Anfänger", "English"): "Japanese Sushi Art for Beginners",
        ("Indexfonds für Einsteiger", "English"): "Index Funds for Beginners",
        ("Safari-Reiseführer für Ostafrika", "English"): "Safari Travel Guide for East Africa",
        ("Vergleich der Besten E-Book-Reader", "English"): "Comparison of the Best E-Book Readers",
        ("Nachhaltige Stadtplanung in Europa", "English"): "Sustainable Urban Planning in Europe",
        # German -> French
        ("Die Geschichte der Berliner Mauer", "French"): "L'Histoire du Mur de Berlin",
        ("Krafttraining für Anfänger: Der Komplette Leitfaden", "French"): "Musculation pour Débutants: Le Guide Complet",
    }

    snippet_translations = {
        ("Introduction to Machine Learning Algorithms", "Spanish"): "Una guía completa de los algoritmos de aprendizaje automático más populares, incluyendo árboles de decisión, redes neuronales y máquinas de vectores de soporte.",
        ("Introduction to Machine Learning Algorithms", "French"): "Un guide complet des algorithmes d'apprentissage automatique les plus populaires, y compris les arbres de décision, les réseaux neuronaux et les machines à vecteurs de support.",
        ("Climate Change Impact on Arctic Ecosystems", "German"): "Neue Forschungsergebnisse zeigen einen beschleunigten Eisverlust in der Arktis und seine kaskadenartigen Auswirkungen auf Eisbärenpopulationen und die marine Biodiversität.",
        ("Climate Change Impact on Arctic Ecosystems", "Spanish"): "Nuevas investigaciones revelan una pérdida acelerada de hielo en el Ártico y sus efectos en cascada sobre las poblaciones de osos polares y la biodiversidad marina.",
        ("Guía Completa de Yoga para Principiantes", "English"): "Everything you need to know to start your yoga practice, including basic postures, breathing techniques and meditation.",
        ("Die Geschichte der Berliner Mauer", "English"): "A comprehensive account of the history of the Berlin Wall, from its construction in 1961 to its fall in 1989 and the political consequences.",
        ("Die Geschichte der Berliner Mauer", "French"): "Un récit complet de l'histoire du Mur de Berlin, de sa construction en 1961 à sa chute en 1989 et les conséquences politiques.",
        ("Recettes Traditionnelles de la Cuisine Française", "English"): "Discover the best traditional French recipes, from coq au vin to gratin dauphinois, with detailed instructions.",
        ("L'Art Impressionniste au Musée d'Orsay", "English"): "Explore the Impressionist masterpieces of the Musée d'Orsay, from Monet to Renoir, and discover the history of this revolutionary art movement.",
        ("L'Art Impressionniste au Musée d'Orsay", "Spanish"): "Explore las obras maestras impresionistas del Museo de Orsay, de Monet a Renoir, y descubra la historia de este movimiento artístico revolucionario.",
        ("Cocina Mexicana: Sabores Auténticos", "English"): "Discover the authentic flavors of Mexican cuisine with recipes for mole, tamales, pozole and other traditional dishes.",
        ("Cocina Mexicana: Sabores Auténticos", "German"): "Entdecken Sie die authentischen Aromen der mexikanischen Küche mit Rezepten für Mole, Tamales, Pozole und andere traditionelle Gerichte.",
        ("Krafttraining für Anfänger: Der Komplette Leitfaden", "English"): "The complete guide to strength training for beginners with training plans, exercise instructions and nutrition tips.",
        ("Krafttraining für Anfänger: Der Komplette Leitfaden", "French"): "Le guide complet de la musculation pour débutants avec des plans d'entraînement, des instructions d'exercices et des conseils nutritionnels.",
        ("Einführung in die Künstliche Intelligenz", "English"): "An introductory guide to artificial intelligence covering machine learning, natural language processing and computer vision.",
        ("Les Plus Beaux Sentiers de Randonnée en France", "English"): "Guide to the best hiking trails in France, from the GR20 in Corsica to the Tour du Mont Blanc, with practical information and difficulty levels.",
        ("Inversiones Sostenibles: Guía ESG", "English"): "How to integrate environmental, social and governance criteria into your investment strategy for sustainable returns.",
        ("Quantum Computing Breakthroughs in 2025", "French"): "Des réalisations révolutionnaires en correction d'erreurs quantiques et stabilité des qubits rapprochent l'informatique quantique pratique de la réalité.",
        ("Recherche sur les Vaccins à ARN Messager", "English"): "Advances in mRNA vaccine technology and their potential applications against cancer and infectious diseases.",
        ("Ciberseguridad para Empresas Pequeñas", "English"): "Practical cybersecurity guide for small and medium enterprises, including ransomware and phishing protection.",
        ("Neue Erkenntnisse in der Teilchenphysik", "English"): "Current breakthroughs at CERN and their significance for understanding the fundamental forces of the universe.",
    }

    # Build page lookup
    page_by_title = {p["title"]: p for p in pages}

    for (title, target_lang), translated_title in title_translations.items():
        if title not in page_by_title:
            continue
        page = page_by_title[title]
        translated_snippet = snippet_translations.get(
            (title, target_lang),
            f"[Translation of: {page['snippet'][:80]}...]"
        )
        translations.append({
            "id": trans_id,
            "page_id": page["id"],
            "source_language": page["language"],
            "target_language": target_lang,
            "translated_title": translated_title,
            "translated_snippet": translated_snippet,
        })
        trans_id += 1

    return translations


def main():
    print("Generating search engine data...")

    # Generate pages (~200)
    pages = generate_pages()
    print(f"  Generated {len(pages)} pages")

    # Generate categories with accurate counts
    categories = generate_categories(pages)
    print(f"  Generated {len(categories)} categories")

    # Generate users
    users = generate_users(pages)
    print(f"  Generated {len(users)} users")

    # Generate translations
    translations = generate_translations(pages)
    print(f"  Generated {len(translations)} translations")

    # Write data files
    SITE_DATA_DIR.mkdir(parents=True, exist_ok=True)

    for filename, data in [
        ("pages.json", pages),
        ("categories.json", categories),
        ("users.json", users),
        ("translations.json", translations),
    ]:
        filepath = SITE_DATA_DIR / filename
        filepath.write_text(json.dumps(data, indent=4, ensure_ascii=False))
        print(f"  Wrote {filepath}")

    # Snapshot to .pristine
    PRISTINE_DIR.mkdir(parents=True, exist_ok=True)
    for filename in ["pages.json", "categories.json", "users.json", "translations.json"]:
        src = SITE_DATA_DIR / filename
        dst = PRISTINE_DIR / filename
        shutil.copy2(src, dst)
        print(f"  Snapshot {dst}")

    # Summary stats
    lang_counts = {}
    cat_counts = {}
    domain_counts = {}
    for p in pages:
        lang_counts[p["language"]] = lang_counts.get(p["language"], 0) + 1
        cat_counts[p["category"]] = cat_counts.get(p["category"], 0) + 1
        domain_counts[p["domain"]] = domain_counts.get(p["domain"], 0) + 1

    print("\n=== Summary ===")
    print(f"Total pages: {len(pages)}")
    print(f"Total categories: {len(categories)}")
    print(f"Total users: {len(users)}")
    print(f"Total translations: {len(translations)}")
    print(f"\nPages by language:")
    for lang, count in sorted(lang_counts.items()):
        print(f"  {lang}: {count}")
    print(f"\nPages by category:")
    for cat, count in sorted(cat_counts.items()):
        print(f"  {cat}: {count}")
    print(f"\nUnique domains: {len(domain_counts)}")


if __name__ == "__main__":
    main()
