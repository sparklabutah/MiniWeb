#!/usr/bin/env python3
"""Generate realistic phone/laptop/tablet product comparison data for the
comparison-aggregator MiniWeb site.

Outputs JSON files to sites/comparison-aggregator/data/ and .pristine/.
"""

import json
import pathlib
import random
from datetime import datetime, timedelta

random.seed(42)

SITE_DATA = pathlib.Path("/scratch/general/vast/u1653932/data_sources/comparison-aggregators")
PRISTINE = SITE_DATA / ".pristine"

# ---------------------------------------------------------------------------
# Retailers
# ---------------------------------------------------------------------------
RETAILERS = [
    {"id": 1, "name": "TechHaven", "url": "https://techhaven.example.com", "rating": 4.7},
    {"id": 2, "name": "MegaMart", "url": "https://megamart.example.com", "rating": 4.3},
    {"id": 3, "name": "GadgetWorld", "url": "https://gadgetworld.example.com", "rating": 4.5},
    {"id": 4, "name": "ElectroPrime", "url": "https://electroprime.example.com", "rating": 4.1},
    {"id": 5, "name": "DigitalDen", "url": "https://digitalden.example.com", "rating": 4.6},
    {"id": 6, "name": "BuyBetter", "url": "https://buybetter.example.com", "rating": 4.4},
]

# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------
CATEGORIES = [
    {"id": 1, "name": "Smartphones", "description": "Mobile phones with advanced features and connectivity", "parent_id": None},
    {"id": 2, "name": "Laptops", "description": "Portable computers for work, gaming, and everyday use", "parent_id": None},
    {"id": 3, "name": "Tablets", "description": "Touchscreen devices for media consumption and productivity", "parent_id": None},
    {"id": 4, "name": "Smartwatches", "description": "Wearable devices with fitness tracking and notifications", "parent_id": None},
    {"id": 5, "name": "Headphones", "description": "Audio devices including over-ear, in-ear, and wireless options", "parent_id": None},
    {"id": 6, "name": "Monitors", "description": "External displays for desktop computing and gaming", "parent_id": None},
]

# ---------------------------------------------------------------------------
# Product catalog — realistic models with specs
# ---------------------------------------------------------------------------

def _date(months_ago):
    d = datetime(2025, 6, 1) - timedelta(days=30 * months_ago)
    return d.strftime("%Y-%m-%d")


def _price_history(original, current, steps=4):
    """Generate a descending price history from original to current."""
    if steps <= 1:
        return [current]
    hist = [original]
    drop = (original - current) / (steps - 1)
    for i in range(1, steps - 1):
        hist.append(round(original - drop * i, 2))
    hist.append(current)
    return hist


# -- Smartphones ---------------------------------------------------------------

PHONES = [
    # Apple
    {"name": "iPhone 16 Pro Max", "brand": "Apple", "sub": "Flagship", "price": 1199.99, "orig": 1199.99,
     "specs": {"screen_size": "6.9\"", "battery": "4685 mAh", "ram": "8GB", "storage": "256GB", "processor": "A18 Pro", "camera": "48MP + 12MP + 12MP"},
     "features": ["Titanium frame", "Action button", "USB-C", "5G"], "tags": ["flagship", "premium", "5g"]},
    {"name": "iPhone 16 Pro", "brand": "Apple", "sub": "Flagship", "price": 999.99, "orig": 999.99,
     "specs": {"screen_size": "6.3\"", "battery": "3582 mAh", "ram": "8GB", "storage": "128GB", "processor": "A18 Pro", "camera": "48MP + 12MP + 12MP"},
     "features": ["Titanium frame", "ProMotion 120Hz", "USB-C"], "tags": ["flagship", "compact", "5g"]},
    {"name": "iPhone 16", "brand": "Apple", "sub": "Mid-range", "price": 799.99, "orig": 829.99,
     "specs": {"screen_size": "6.1\"", "battery": "3561 mAh", "ram": "8GB", "storage": "128GB", "processor": "A18", "camera": "48MP + 12MP"},
     "features": ["Dynamic Island", "USB-C", "MagSafe"], "tags": ["mainstream", "reliable"]},
    {"name": "iPhone SE 4", "brand": "Apple", "sub": "Budget", "price": 429.99, "orig": 429.99,
     "specs": {"screen_size": "6.1\"", "battery": "3279 mAh", "ram": "8GB", "storage": "128GB", "processor": "A18", "camera": "48MP"},
     "features": ["Face ID", "USB-C", "5G"], "tags": ["budget", "compact", "value"]},

    # Samsung
    {"name": "Galaxy S25 Ultra", "brand": "Samsung", "sub": "Flagship", "price": 1299.99, "orig": 1319.99,
     "specs": {"screen_size": "6.9\"", "battery": "5000 mAh", "ram": "12GB", "storage": "256GB", "processor": "Snapdragon 8 Elite", "camera": "200MP + 50MP + 10MP + 12MP"},
     "features": ["S Pen", "Titanium frame", "Galaxy AI", "100x Space Zoom"], "tags": ["flagship", "premium", "stylus"]},
    {"name": "Galaxy S25+", "brand": "Samsung", "sub": "Flagship", "price": 999.99, "orig": 1049.99,
     "specs": {"screen_size": "6.7\"", "battery": "4900 mAh", "ram": "12GB", "storage": "256GB", "processor": "Snapdragon 8 Elite", "camera": "50MP + 10MP + 12MP"},
     "features": ["Galaxy AI", "Wireless charging", "IP68"], "tags": ["flagship", "large-screen"]},
    {"name": "Galaxy S25", "brand": "Samsung", "sub": "Mid-range", "price": 799.99, "orig": 849.99,
     "specs": {"screen_size": "6.2\"", "battery": "4000 mAh", "ram": "12GB", "storage": "128GB", "processor": "Snapdragon 8 Elite", "camera": "50MP + 10MP + 12MP"},
     "features": ["Galaxy AI", "Dynamic AMOLED 2X", "IP68"], "tags": ["mainstream", "compact"]},
    {"name": "Galaxy A55", "brand": "Samsung", "sub": "Budget", "price": 429.99, "orig": 449.99,
     "specs": {"screen_size": "6.6\"", "battery": "5000 mAh", "ram": "8GB", "storage": "128GB", "processor": "Exynos 1480", "camera": "50MP + 12MP + 5MP"},
     "features": ["Super AMOLED", "Water resistant", "NFC"], "tags": ["budget", "value", "durable"]},
    {"name": "Galaxy Z Fold 6", "brand": "Samsung", "sub": "Flagship", "price": 1799.99, "orig": 1899.99,
     "specs": {"screen_size": "7.6\" (inner) / 6.3\" (outer)", "battery": "4400 mAh", "ram": "12GB", "storage": "256GB", "processor": "Snapdragon 8 Gen 3", "camera": "50MP + 10MP + 12MP"},
     "features": ["Foldable display", "Flex Mode", "Galaxy AI", "S Pen support"], "tags": ["foldable", "premium", "innovative"]},
    {"name": "Galaxy Z Flip 6", "brand": "Samsung", "sub": "Mid-range", "price": 1099.99, "orig": 1099.99,
     "specs": {"screen_size": "6.7\" (inner) / 3.4\" (outer)", "battery": "4000 mAh", "ram": "12GB", "storage": "256GB", "processor": "Snapdragon 8 Gen 3", "camera": "50MP + 12MP"},
     "features": ["Foldable clamshell", "Flex Window", "Galaxy AI"], "tags": ["foldable", "compact", "stylish"]},

    # Google
    {"name": "Pixel 9 Pro XL", "brand": "Google", "sub": "Flagship", "price": 1079.99, "orig": 1099.99,
     "specs": {"screen_size": "6.8\"", "battery": "5060 mAh", "ram": "16GB", "storage": "128GB", "processor": "Tensor G4", "camera": "50MP + 48MP + 48MP"},
     "features": ["AI photo editing", "7 years updates", "Gemini Nano"], "tags": ["flagship", "camera", "ai"]},
    {"name": "Pixel 9 Pro", "brand": "Google", "sub": "Flagship", "price": 999.99, "orig": 999.99,
     "specs": {"screen_size": "6.3\"", "battery": "4700 mAh", "ram": "16GB", "storage": "128GB", "processor": "Tensor G4", "camera": "50MP + 48MP + 48MP"},
     "features": ["AI photo editing", "Gemini Nano", "Temperature sensor"], "tags": ["flagship", "camera", "compact"]},
    {"name": "Pixel 9", "brand": "Google", "sub": "Mid-range", "price": 799.99, "orig": 799.99,
     "specs": {"screen_size": "6.3\"", "battery": "4700 mAh", "ram": "12GB", "storage": "128GB", "processor": "Tensor G4", "camera": "50MP + 48MP"},
     "features": ["AI features", "7 years updates", "USB-C"], "tags": ["mainstream", "camera", "value"]},
    {"name": "Pixel 9a", "brand": "Google", "sub": "Budget", "price": 499.99, "orig": 499.99,
     "specs": {"screen_size": "6.1\"", "battery": "4492 mAh", "ram": "8GB", "storage": "128GB", "processor": "Tensor G4", "camera": "48MP + 13MP"},
     "features": ["Google AI", "Night Sight", "5 years updates"], "tags": ["budget", "camera", "value"]},

    # OnePlus
    {"name": "OnePlus 13", "brand": "OnePlus", "sub": "Flagship", "price": 899.99, "orig": 899.99,
     "specs": {"screen_size": "6.82\"", "battery": "6000 mAh", "ram": "12GB", "storage": "256GB", "processor": "Snapdragon 8 Elite", "camera": "50MP + 50MP + 50MP"},
     "features": ["Hasselblad camera", "100W fast charging", "IP69"], "tags": ["flagship", "fast-charging", "camera"]},
    {"name": "OnePlus 13R", "brand": "OnePlus", "sub": "Mid-range", "price": 599.99, "orig": 599.99,
     "specs": {"screen_size": "6.78\"", "battery": "6000 mAh", "ram": "12GB", "storage": "256GB", "processor": "Snapdragon 8 Gen 3", "camera": "50MP + 8MP + 50MP"},
     "features": ["80W fast charging", "120Hz AMOLED", "Alert slider"], "tags": ["value", "fast-charging", "performance"]},
    {"name": "OnePlus Nord 4", "brand": "OnePlus", "sub": "Budget", "price": 349.99, "orig": 399.99,
     "specs": {"screen_size": "6.74\"", "battery": "5500 mAh", "ram": "8GB", "storage": "128GB", "processor": "Snapdragon 7+ Gen 3", "camera": "50MP + 8MP"},
     "features": ["Metal unibody", "67W charging", "AMOLED 120Hz"], "tags": ["budget", "metal", "value"]},

    # Xiaomi
    {"name": "Xiaomi 15 Ultra", "brand": "Xiaomi", "sub": "Flagship", "price": 1099.99, "orig": 1199.99,
     "specs": {"screen_size": "6.73\"", "battery": "5500 mAh", "ram": "16GB", "storage": "256GB", "processor": "Snapdragon 8 Elite", "camera": "50MP + 50MP + 50MP + 200MP"},
     "features": ["Leica optics", "90W wireless charging", "Satellite connectivity"], "tags": ["flagship", "camera", "premium"]},
    {"name": "Xiaomi 15", "brand": "Xiaomi", "sub": "Mid-range", "price": 749.99, "orig": 799.99,
     "specs": {"screen_size": "6.36\"", "battery": "5400 mAh", "ram": "12GB", "storage": "256GB", "processor": "Snapdragon 8 Elite", "camera": "50MP + 50MP + 50MP"},
     "features": ["Leica optics", "90W wired charging", "HyperOS"], "tags": ["value", "camera", "compact"]},
    {"name": "Redmi Note 14 Pro+", "brand": "Xiaomi", "sub": "Budget", "price": 329.99, "orig": 349.99,
     "specs": {"screen_size": "6.67\"", "battery": "5110 mAh", "ram": "8GB", "storage": "256GB", "processor": "Dimensity 7300 Ultra", "camera": "200MP + 8MP + 2MP"},
     "features": ["200MP camera", "120W charging", "IP68"], "tags": ["budget", "camera", "fast-charging"]},

    # Sony
    {"name": "Xperia 1 VI", "brand": "Sony", "sub": "Flagship", "price": 1399.99, "orig": 1399.99,
     "specs": {"screen_size": "6.5\"", "battery": "5000 mAh", "ram": "12GB", "storage": "256GB", "processor": "Snapdragon 8 Gen 3", "camera": "52MP + 12MP + 12MP"},
     "features": ["4K HDR display", "3.5mm jack", "Dedicated camera button", "Creator mode"], "tags": ["flagship", "media", "camera", "audio"]},
    {"name": "Xperia 5 V", "brand": "Sony", "sub": "Mid-range", "price": 949.99, "orig": 999.99,
     "specs": {"screen_size": "6.1\"", "battery": "5000 mAh", "ram": "8GB", "storage": "128GB", "processor": "Snapdragon 8 Gen 2", "camera": "48MP + 12MP"},
     "features": ["Compact flagship", "3.5mm jack", "LDAC audio"], "tags": ["compact", "audio", "camera"]},

    # Motorola
    {"name": "Motorola Edge 50 Ultra", "brand": "Motorola", "sub": "Flagship", "price": 799.99, "orig": 899.99,
     "specs": {"screen_size": "6.7\"", "battery": "4500 mAh", "ram": "16GB", "storage": "1TB", "processor": "Snapdragon 8s Gen 3", "camera": "50MP + 64MP + 50MP"},
     "features": ["Wood/vegan leather back", "125W charging", "Wireless charging"], "tags": ["premium", "design", "fast-charging"]},
    {"name": "Moto G Power 5G 2025", "brand": "Motorola", "sub": "Budget", "price": 249.99, "orig": 299.99,
     "specs": {"screen_size": "6.7\"", "battery": "5000 mAh", "ram": "6GB", "storage": "128GB", "processor": "Dimensity 7025", "camera": "50MP + 2MP"},
     "features": ["3-day battery", "Water repellent", "NFC"], "tags": ["budget", "battery", "value"]},

    # Nothing
    {"name": "Nothing Phone (3)", "brand": "Nothing", "sub": "Mid-range", "price": 649.99, "orig": 699.99,
     "specs": {"screen_size": "6.5\"", "battery": "5000 mAh", "ram": "12GB", "storage": "256GB", "processor": "Snapdragon 8s Gen 3", "camera": "50MP + 50MP"},
     "features": ["Glyph Interface", "Transparent back", "Nothing OS"], "tags": ["design", "unique", "transparent"]},
    {"name": "Nothing Phone (2a) Plus", "brand": "Nothing", "sub": "Budget", "price": 399.99, "orig": 399.99,
     "specs": {"screen_size": "6.7\"", "battery": "5000 mAh", "ram": "12GB", "storage": "256GB", "processor": "Dimensity 7350 Pro", "camera": "50MP + 50MP"},
     "features": ["Glyph Interface", "50W fast charging", "Nothing OS 2.6"], "tags": ["budget", "design", "transparent"]},

    # Samsung prev-gen
    {"name": "Galaxy S24 Ultra", "brand": "Samsung", "sub": "Flagship", "price": 1099.99, "orig": 1319.99,
     "specs": {"screen_size": "6.8\"", "battery": "5000 mAh", "ram": "12GB", "storage": "256GB", "processor": "Snapdragon 8 Gen 3", "camera": "200MP + 50MP + 10MP + 12MP"},
     "features": ["S Pen", "Titanium frame", "Galaxy AI", "100x Space Zoom"], "tags": ["flagship", "previous-gen", "stylus", "deal"]},
    {"name": "Galaxy S24", "brand": "Samsung", "sub": "Mid-range", "price": 649.99, "orig": 799.99,
     "specs": {"screen_size": "6.2\"", "battery": "4000 mAh", "ram": "8GB", "storage": "128GB", "processor": "Exynos 2400", "camera": "50MP + 12MP + 10MP"},
     "features": ["Galaxy AI", "Dynamic AMOLED 2X", "IP68"], "tags": ["previous-gen", "compact", "deal"]},
    {"name": "Galaxy A35", "brand": "Samsung", "sub": "Budget", "price": 329.99, "orig": 399.99,
     "specs": {"screen_size": "6.6\"", "battery": "5000 mAh", "ram": "6GB", "storage": "128GB", "processor": "Exynos 1380", "camera": "50MP + 8MP + 5MP"},
     "features": ["Super AMOLED", "Water resistant", "NFC", "Expandable storage"], "tags": ["budget", "value", "durable"]},
    {"name": "Galaxy A16", "brand": "Samsung", "sub": "Budget", "price": 199.99, "orig": 199.99,
     "specs": {"screen_size": "6.7\"", "battery": "5000 mAh", "ram": "4GB", "storage": "128GB", "processor": "Exynos 1330", "camera": "50MP + 5MP + 2MP"},
     "features": ["6 years updates", "Super AMOLED", "Side fingerprint"], "tags": ["budget", "entry-level", "value"]},

    # Apple prev-gen
    {"name": "iPhone 15 Pro Max", "brand": "Apple", "sub": "Flagship", "price": 999.99, "orig": 1199.99,
     "specs": {"screen_size": "6.7\"", "battery": "4441 mAh", "ram": "8GB", "storage": "256GB", "processor": "A17 Pro", "camera": "48MP + 12MP + 12MP"},
     "features": ["Titanium frame", "Action button", "USB-C", "5G"], "tags": ["previous-gen", "premium", "deal"]},
    {"name": "iPhone 15", "brand": "Apple", "sub": "Mid-range", "price": 699.99, "orig": 799.99,
     "specs": {"screen_size": "6.1\"", "battery": "3349 mAh", "ram": "6GB", "storage": "128GB", "processor": "A16 Bionic", "camera": "48MP + 12MP"},
     "features": ["Dynamic Island", "USB-C", "MagSafe"], "tags": ["previous-gen", "mainstream", "deal"]},

    # Google prev-gen
    {"name": "Pixel 8 Pro", "brand": "Google", "sub": "Flagship", "price": 749.99, "orig": 999.99,
     "specs": {"screen_size": "6.7\"", "battery": "5050 mAh", "ram": "12GB", "storage": "128GB", "processor": "Tensor G3", "camera": "50MP + 48MP + 48MP"},
     "features": ["AI photo editing", "7 years updates", "Temperature sensor"], "tags": ["previous-gen", "camera", "deal"]},
    {"name": "Pixel 8a", "brand": "Google", "sub": "Budget", "price": 399.99, "orig": 499.99,
     "specs": {"screen_size": "6.1\"", "battery": "4492 mAh", "ram": "8GB", "storage": "128GB", "processor": "Tensor G3", "camera": "64MP + 13MP"},
     "features": ["Google AI", "Night Sight", "7 years updates"], "tags": ["previous-gen", "budget", "deal"]},

    # OPPO
    {"name": "OPPO Find X8 Pro", "brand": "OPPO", "sub": "Flagship", "price": 1099.99, "orig": 1199.99,
     "specs": {"screen_size": "6.78\"", "battery": "5910 mAh", "ram": "16GB", "storage": "256GB", "processor": "Dimensity 9400", "camera": "50MP + 50MP + 50MP + 50MP"},
     "features": ["Hasselblad camera", "80W fast charging", "IP69"], "tags": ["flagship", "camera", "premium"]},
    {"name": "OPPO Find X8", "brand": "OPPO", "sub": "Mid-range", "price": 799.99, "orig": 849.99,
     "specs": {"screen_size": "6.59\"", "battery": "5630 mAh", "ram": "12GB", "storage": "256GB", "processor": "Dimensity 9400", "camera": "50MP + 50MP + 50MP"},
     "features": ["Hasselblad camera", "80W charging", "Alert slider"], "tags": ["camera", "value", "performance"]},
    {"name": "OPPO Reno 12 Pro", "brand": "OPPO", "sub": "Mid-range", "price": 499.99, "orig": 549.99,
     "specs": {"screen_size": "6.7\"", "battery": "5000 mAh", "ram": "12GB", "storage": "256GB", "processor": "Dimensity 7300", "camera": "50MP + 8MP + 50MP"},
     "features": ["AI features", "67W charging", "AMOLED 120Hz"], "tags": ["mid-range", "ai", "stylish"]},

    # Realme
    {"name": "Realme GT 7 Pro", "brand": "Realme", "sub": "Flagship", "price": 699.99, "orig": 749.99,
     "specs": {"screen_size": "6.78\"", "battery": "6500 mAh", "ram": "12GB", "storage": "256GB", "processor": "Snapdragon 8 Elite", "camera": "50MP + 8MP + 50MP"},
     "features": ["Ultrasonic fingerprint", "120W charging", "IP69"], "tags": ["flagship", "value", "fast-charging"]},
    {"name": "Realme 13 Pro+", "brand": "Realme", "sub": "Mid-range", "price": 379.99, "orig": 399.99,
     "specs": {"screen_size": "6.7\"", "battery": "5200 mAh", "ram": "8GB", "storage": "256GB", "processor": "Snapdragon 7s Gen 2", "camera": "50MP + 8MP + 50MP"},
     "features": ["AI camera", "80W charging", "AMOLED 120Hz"], "tags": ["mid-range", "camera", "value"]},

    # Vivo
    {"name": "Vivo X200 Pro", "brand": "Vivo", "sub": "Flagship", "price": 999.99, "orig": 1049.99,
     "specs": {"screen_size": "6.78\"", "battery": "6000 mAh", "ram": "16GB", "storage": "256GB", "processor": "Dimensity 9400", "camera": "50MP + 50MP + 200MP"},
     "features": ["ZEISS optics", "90W charging", "IP69"], "tags": ["flagship", "camera", "premium"]},
    {"name": "Vivo V40", "brand": "Vivo", "sub": "Mid-range", "price": 449.99, "orig": 499.99,
     "specs": {"screen_size": "6.78\"", "battery": "5500 mAh", "ram": "8GB", "storage": "256GB", "processor": "Snapdragon 7 Gen 3", "camera": "50MP + 50MP"},
     "features": ["ZEISS optics", "80W charging", "AMOLED"], "tags": ["mid-range", "camera", "stylish"]},

    # HONOR
    {"name": "HONOR Magic7 Pro", "brand": "HONOR", "sub": "Flagship", "price": 899.99, "orig": 999.99,
     "specs": {"screen_size": "6.8\"", "battery": "5850 mAh", "ram": "12GB", "storage": "256GB", "processor": "Snapdragon 8 Elite", "camera": "50MP + 50MP + 200MP"},
     "features": ["AI defocus", "100W charging", "IP68+IP69"], "tags": ["flagship", "camera", "ai"]},

    # Asus phone
    {"name": "ASUS ROG Phone 9 Pro", "brand": "ASUS", "sub": "Gaming", "price": 1199.99, "orig": 1299.99,
     "specs": {"screen_size": "6.78\"", "battery": "5800 mAh", "ram": "24GB", "storage": "1TB", "processor": "Snapdragon 8 Elite", "camera": "50MP + 13MP + 5MP"},
     "features": ["AirTrigger 9", "165Hz AMOLED", "65W charging", "RGB rear"], "tags": ["gaming", "performance", "rgb"]},
    {"name": "ASUS Zenfone 11 Ultra", "brand": "ASUS", "sub": "Flagship", "price": 899.99, "orig": 899.99,
     "specs": {"screen_size": "6.78\"", "battery": "5500 mAh", "ram": "12GB", "storage": "256GB", "processor": "Snapdragon 8 Gen 3", "camera": "50MP + 13MP + 32MP"},
     "features": ["Gimbal stabilization", "65W charging", "Zen UI"], "tags": ["flagship", "camera", "versatile"]},

    # Huawei phone
    {"name": "Huawei Pura 70 Ultra", "brand": "Huawei", "sub": "Flagship", "price": 1499.99, "orig": 1499.99,
     "specs": {"screen_size": "6.8\"", "battery": "5200 mAh", "ram": "16GB", "storage": "512GB", "processor": "Kirin 9010", "camera": "50MP + 40MP + 12.5MP"},
     "features": ["Retractable camera", "Satellite calls", "100W charging"], "tags": ["flagship", "camera", "innovative"]},
    {"name": "Huawei Mate 60 Pro", "brand": "Huawei", "sub": "Flagship", "price": 1199.99, "orig": 1299.99,
     "specs": {"screen_size": "6.82\"", "battery": "5000 mAh", "ram": "12GB", "storage": "256GB", "processor": "Kirin 9000s", "camera": "48MP + 12MP + 48MP"},
     "features": ["Satellite messaging", "HarmonyOS", "88W charging"], "tags": ["flagship", "premium", "satellite"]},

    # Tecno
    {"name": "Tecno Phantom V Fold 2", "brand": "Tecno", "sub": "Flagship", "price": 999.99, "orig": 1099.99,
     "specs": {"screen_size": "7.85\" (inner) / 6.42\" (outer)", "battery": "5750 mAh", "ram": "12GB", "storage": "512GB", "processor": "Dimensity 9200+", "camera": "50MP + 50MP + 50MP"},
     "features": ["Foldable display", "70W charging", "Hi-Res audio"], "tags": ["foldable", "value", "premium"]},
    {"name": "Tecno Camon 30 Pro", "brand": "Tecno", "sub": "Mid-range", "price": 349.99, "orig": 399.99,
     "specs": {"screen_size": "6.78\"", "battery": "5000 mAh", "ram": "12GB", "storage": "512GB", "processor": "Dimensity 8200", "camera": "50MP + 50MP + 2MP"},
     "features": ["Sony IMX890", "Universal flash", "AMOLED 120Hz"], "tags": ["mid-range", "camera", "value"]},

    # ZTE / Nubia
    {"name": "Nubia Z70 Ultra", "brand": "ZTE", "sub": "Flagship", "price": 749.99, "orig": 799.99,
     "specs": {"screen_size": "6.85\"", "battery": "6150 mAh", "ram": "12GB", "storage": "256GB", "processor": "Snapdragon 8 Elite", "camera": "50MP + 50MP + 64MP"},
     "features": ["Under-display camera", "80W charging", "No notch display"], "tags": ["flagship", "innovative", "full-screen"]},

    # Samsung prev-gen extras
    {"name": "Galaxy S24 FE", "brand": "Samsung", "sub": "Mid-range", "price": 549.99, "orig": 649.99,
     "specs": {"screen_size": "6.7\"", "battery": "4700 mAh", "ram": "8GB", "storage": "128GB", "processor": "Exynos 2400e", "camera": "50MP + 8MP + 12MP"},
     "features": ["Galaxy AI", "Dynamic AMOLED 2X", "IP68"], "tags": ["value", "fan-edition", "deal"]},

    # Pixel prev-gen
    {"name": "Pixel 7a", "brand": "Google", "sub": "Budget", "price": 349.99, "orig": 499.99,
     "specs": {"screen_size": "6.1\"", "battery": "4385 mAh", "ram": "8GB", "storage": "128GB", "processor": "Tensor G2", "camera": "64MP + 13MP"},
     "features": ["Google AI", "Night Sight", "5 years updates"], "tags": ["previous-gen", "budget", "clearance"]},

    # Motorola extra
    {"name": "Motorola Razr Plus 2024", "brand": "Motorola", "sub": "Flagship", "price": 999.99, "orig": 999.99,
     "specs": {"screen_size": "6.9\" (inner) / 4\" (outer)", "battery": "4000 mAh", "ram": "12GB", "storage": "256GB", "processor": "Snapdragon 8s Gen 3", "camera": "50MP + 50MP"},
     "features": ["Foldable clamshell", "4\" cover display", "68W charging"], "tags": ["foldable", "stylish", "compact"]},
    {"name": "Moto G Stylus 5G 2025", "brand": "Motorola", "sub": "Budget", "price": 299.99, "orig": 299.99,
     "specs": {"screen_size": "6.7\"", "battery": "5000 mAh", "ram": "6GB", "storage": "128GB", "processor": "Snapdragon 6 Gen 3", "camera": "50MP + 8MP + 2MP"},
     "features": ["Built-in stylus", "Water repellent", "NFC"], "tags": ["budget", "stylus", "productivity"]},

    # Xiaomi extras
    {"name": "Xiaomi 14 Ultra", "brand": "Xiaomi", "sub": "Flagship", "price": 899.99, "orig": 1199.99,
     "specs": {"screen_size": "6.73\"", "battery": "5300 mAh", "ram": "16GB", "storage": "512GB", "processor": "Snapdragon 8 Gen 3", "camera": "50MP + 50MP + 50MP + 50MP"},
     "features": ["Leica optics", "Photography kit", "90W charging"], "tags": ["previous-gen", "camera", "deal"]},
    {"name": "POCO F6 Pro", "brand": "Xiaomi", "sub": "Mid-range", "price": 499.99, "orig": 549.99,
     "specs": {"screen_size": "6.67\"", "battery": "5000 mAh", "ram": "12GB", "storage": "256GB", "processor": "Snapdragon 8 Gen 2", "camera": "50MP + 8MP + 2MP"},
     "features": ["120W HyperCharge", "AMOLED 120Hz", "Vapor chamber cooling"], "tags": ["value", "performance", "fast-charging"]},
    {"name": "Redmi Note 13 Pro", "brand": "Xiaomi", "sub": "Budget", "price": 279.99, "orig": 299.99,
     "specs": {"screen_size": "6.67\"", "battery": "5100 mAh", "ram": "8GB", "storage": "256GB", "processor": "Snapdragon 7s Gen 2", "camera": "200MP + 8MP + 2MP"},
     "features": ["200MP camera", "67W charging", "IP54"], "tags": ["budget", "camera", "value"]},

    # Nokia
    {"name": "Nokia X50", "brand": "Nokia", "sub": "Mid-range", "price": 449.99, "orig": 499.99,
     "specs": {"screen_size": "6.5\"", "battery": "4900 mAh", "ram": "8GB", "storage": "128GB", "processor": "Snapdragon 778G", "camera": "108MP + 8MP + 2MP"},
     "features": ["PureView camera", "3 years updates", "IP52", "OZO audio"], "tags": ["mid-range", "durable", "camera"]},

    # TCL
    {"name": "TCL 50 XL 5G", "brand": "TCL", "sub": "Budget", "price": 199.99, "orig": 219.99,
     "specs": {"screen_size": "6.78\"", "battery": "5010 mAh", "ram": "4GB", "storage": "128GB", "processor": "Dimensity 6100+", "camera": "50MP + 2MP"},
     "features": ["NXTVISION display", "5G", "Side fingerprint", "Face unlock"], "tags": ["budget", "entry-level", "5g"]},

    # iPhone storage variants at different retailers
    {"name": "iPhone 16 Pro Max 512GB", "brand": "Apple", "sub": "Flagship", "price": 1399.99, "orig": 1399.99,
     "specs": {"screen_size": "6.9\"", "battery": "4685 mAh", "ram": "8GB", "storage": "512GB", "processor": "A18 Pro", "camera": "48MP + 12MP + 12MP"},
     "features": ["Titanium frame", "Action button", "USB-C", "5G"], "tags": ["flagship", "premium", "high-storage"]},
    {"name": "iPhone 16 Pro Max 1TB", "brand": "Apple", "sub": "Flagship", "price": 1799.99, "orig": 1799.99,
     "specs": {"screen_size": "6.9\"", "battery": "4685 mAh", "ram": "8GB", "storage": "1TB", "processor": "A18 Pro", "camera": "48MP + 12MP + 12MP"},
     "features": ["Titanium frame", "Action button", "USB-C", "ProRes recording"], "tags": ["flagship", "premium", "max-storage"]},

    # Samsung storage variant
    {"name": "Galaxy S25 Ultra 512GB", "brand": "Samsung", "sub": "Flagship", "price": 1419.99, "orig": 1419.99,
     "specs": {"screen_size": "6.9\"", "battery": "5000 mAh", "ram": "12GB", "storage": "512GB", "processor": "Snapdragon 8 Elite", "camera": "200MP + 50MP + 10MP + 12MP"},
     "features": ["S Pen", "Titanium frame", "Galaxy AI", "8K video"], "tags": ["flagship", "premium", "high-storage"]},

    # OnePlus prev-gen
    {"name": "OnePlus 12", "brand": "OnePlus", "sub": "Flagship", "price": 699.99, "orig": 899.99,
     "specs": {"screen_size": "6.82\"", "battery": "5400 mAh", "ram": "12GB", "storage": "256GB", "processor": "Snapdragon 8 Gen 3", "camera": "50MP + 48MP + 64MP"},
     "features": ["Hasselblad camera", "100W charging", "IP65"], "tags": ["previous-gen", "value", "fast-charging"]},

    # Sony prev-gen
    {"name": "Xperia 5 IV", "brand": "Sony", "sub": "Mid-range", "price": 699.99, "orig": 999.99,
     "specs": {"screen_size": "6.1\"", "battery": "5000 mAh", "ram": "8GB", "storage": "128GB", "processor": "Snapdragon 8 Gen 1", "camera": "12MP + 12MP + 12MP"},
     "features": ["Compact flagship", "3.5mm jack", "LDAC audio", "IP68"], "tags": ["previous-gen", "compact", "clearance"]},

    # Fairphone
    {"name": "Fairphone 5", "brand": "Fairphone", "sub": "Mid-range", "price": 699.99, "orig": 699.99,
     "specs": {"screen_size": "6.46\"", "battery": "4200 mAh", "ram": "8GB", "storage": "256GB", "processor": "Snapdragon QCM6490", "camera": "50MP + 50MP"},
     "features": ["Modular repair", "Fair trade materials", "8 years updates", "Removable battery"], "tags": ["sustainable", "modular", "ethical"]},

    # Cat phone
    {"name": "Cat S75", "brand": "Cat", "sub": "Rugged", "price": 599.99, "orig": 599.99,
     "specs": {"screen_size": "6.58\"", "battery": "5000 mAh", "ram": "6GB", "storage": "128GB", "processor": "Dimensity 900", "camera": "50MP + 8MP"},
     "features": ["Satellite SOS", "MIL-STD-810H", "IP68/IP69K", "Underwater camera"], "tags": ["rugged", "outdoor", "satellite"]},

    # Samsung budget
    {"name": "Galaxy A15 5G", "brand": "Samsung", "sub": "Budget", "price": 159.99, "orig": 199.99,
     "specs": {"screen_size": "6.5\"", "battery": "5000 mAh", "ram": "4GB", "storage": "128GB", "processor": "Dimensity 6100+", "camera": "50MP + 5MP + 2MP"},
     "features": ["Super AMOLED", "5G", "Side fingerprint", "Knox security"], "tags": ["budget", "entry-level", "5g"]},

    # Motorola budget
    {"name": "Moto G 5G 2025", "brand": "Motorola", "sub": "Budget", "price": 179.99, "orig": 199.99,
     "specs": {"screen_size": "6.6\"", "battery": "5000 mAh", "ram": "4GB", "storage": "64GB", "processor": "Dimensity 6100+", "camera": "48MP + 2MP"},
     "features": ["5G", "Water repellent", "FM radio", "NFC"], "tags": ["budget", "entry-level", "5g"]},
]

# -- Laptops -------------------------------------------------------------------

LAPTOPS = [
    # Apple
    {"name": "MacBook Pro 16 M4 Max", "brand": "Apple", "sub": "Workstation", "price": 3499.99, "orig": 3499.99,
     "specs": {"screen_size": "16.2\"", "battery": "100 Wh", "ram": "36GB", "storage": "1TB SSD", "processor": "Apple M4 Max", "camera": "1080p FaceTime"},
     "features": ["Liquid Retina XDR", "MagSafe", "HDMI", "SD card slot"], "tags": ["workstation", "creative", "premium"]},
    {"name": "MacBook Pro 14 M4 Pro", "brand": "Apple", "sub": "Professional", "price": 1999.99, "orig": 1999.99,
     "specs": {"screen_size": "14.2\"", "battery": "72.4 Wh", "ram": "24GB", "storage": "512GB SSD", "processor": "Apple M4 Pro", "camera": "1080p FaceTime"},
     "features": ["Liquid Retina XDR", "ProMotion 120Hz", "Thunderbolt 5"], "tags": ["professional", "portable", "creative"]},
    {"name": "MacBook Air 15 M4", "brand": "Apple", "sub": "Ultrabook", "price": 1299.99, "orig": 1299.99,
     "specs": {"screen_size": "15.3\"", "battery": "66.5 Wh", "ram": "16GB", "storage": "256GB SSD", "processor": "Apple M4", "camera": "1080p FaceTime"},
     "features": ["Fanless design", "MagSafe", "18-hour battery"], "tags": ["ultrabook", "silent", "portable"]},
    {"name": "MacBook Air 13 M4", "brand": "Apple", "sub": "Ultrabook", "price": 1099.99, "orig": 1099.99,
     "specs": {"screen_size": "13.6\"", "battery": "52.6 Wh", "ram": "16GB", "storage": "256GB SSD", "processor": "Apple M4", "camera": "1080p FaceTime"},
     "features": ["Fanless design", "Under 3 lbs", "MagSafe"], "tags": ["ultrabook", "compact", "lightweight"]},

    # Dell
    {"name": "Dell XPS 16 9640", "brand": "Dell", "sub": "Professional", "price": 1899.99, "orig": 2099.99,
     "specs": {"screen_size": "16.3\"", "battery": "99.5 Wh", "ram": "32GB", "storage": "1TB SSD", "processor": "Intel Core Ultra 9 185H", "camera": "1080p IR"},
     "features": ["OLED display", "Edge-to-edge keyboard", "Thunderbolt 4"], "tags": ["professional", "creative", "oled"]},
    {"name": "Dell XPS 14 9440", "brand": "Dell", "sub": "Ultrabook", "price": 1499.99, "orig": 1599.99,
     "specs": {"screen_size": "14.5\"", "battery": "69.5 Wh", "ram": "16GB", "storage": "512GB SSD", "processor": "Intel Core Ultra 7 155H", "camera": "1080p IR"},
     "features": ["Haptic touchpad", "InfinityEdge display", "Wi-Fi 7"], "tags": ["ultrabook", "premium", "portable"]},
    {"name": "Dell Inspiron 16 Plus", "brand": "Dell", "sub": "Mid-range", "price": 899.99, "orig": 999.99,
     "specs": {"screen_size": "16\"", "battery": "86 Wh", "ram": "16GB", "storage": "512GB SSD", "processor": "Intel Core Ultra 7 155H", "camera": "1080p"},
     "features": ["ComfortView Plus", "NVIDIA RTX 3050", "Numeric keypad"], "tags": ["mainstream", "productivity", "value"]},
    {"name": "Dell Latitude 7450", "brand": "Dell", "sub": "Business", "price": 1699.99, "orig": 1799.99,
     "specs": {"screen_size": "14\"", "battery": "57 Wh", "ram": "16GB", "storage": "512GB SSD", "processor": "Snapdragon X Elite", "camera": "5MP IR"},
     "features": ["AI-powered features", "5G optional", "Smart card reader"], "tags": ["business", "enterprise", "ai"]},

    # Lenovo
    {"name": "ThinkPad X1 Carbon Gen 12", "brand": "Lenovo", "sub": "Business", "price": 1649.99, "orig": 1849.99,
     "specs": {"screen_size": "14\"", "battery": "57 Wh", "ram": "32GB", "storage": "512GB SSD", "processor": "Intel Core Ultra 7 155U", "camera": "1080p IR"},
     "features": ["TrackPoint", "MIL-STD-810H", "Fingerprint reader"], "tags": ["business", "durable", "enterprise"]},
    {"name": "Yoga Pro 9i 16", "brand": "Lenovo", "sub": "Creative", "price": 2199.99, "orig": 2399.99,
     "specs": {"screen_size": "16\"", "battery": "99.5 Wh", "ram": "32GB", "storage": "1TB SSD", "processor": "Intel Core Ultra 9 185H", "camera": "1080p IR"},
     "features": ["Mini LED display", "NVIDIA RTX 4060", "Harman Kardon speakers"], "tags": ["creative", "content-creation", "premium"]},
    {"name": "IdeaPad Slim 5 14", "brand": "Lenovo", "sub": "Budget", "price": 599.99, "orig": 699.99,
     "specs": {"screen_size": "14\"", "battery": "56.6 Wh", "ram": "16GB", "storage": "512GB SSD", "processor": "AMD Ryzen 5 7530U", "camera": "1080p"},
     "features": ["Rapid Charge", "Dolby Atmos", "Smart noise cancellation"], "tags": ["budget", "student", "portable"]},

    # HP
    {"name": "HP Spectre x360 16", "brand": "HP", "sub": "2-in-1", "price": 1699.99, "orig": 1899.99,
     "specs": {"screen_size": "16\"", "battery": "83 Wh", "ram": "32GB", "storage": "1TB SSD", "processor": "Intel Core Ultra 7 155H", "camera": "5MP IR"},
     "features": ["OLED display", "360-degree hinge", "Pen included", "Thunderbolt 4"], "tags": ["2-in-1", "creative", "premium"]},
    {"name": "HP Pavilion Plus 14", "brand": "HP", "sub": "Mid-range", "price": 849.99, "orig": 899.99,
     "specs": {"screen_size": "14\"", "battery": "51 Wh", "ram": "16GB", "storage": "512GB SSD", "processor": "Intel Core Ultra 5 125H", "camera": "5MP"},
     "features": ["2.8K OLED", "Wi-Fi 7", "Bang & Olufsen audio"], "tags": ["mainstream", "multimedia", "value"]},

    # ASUS
    {"name": "ASUS ROG Strix G18", "brand": "ASUS", "sub": "Gaming", "price": 2299.99, "orig": 2499.99,
     "specs": {"screen_size": "18\"", "battery": "90 Wh", "ram": "32GB", "storage": "1TB SSD", "processor": "Intel Core i9-14900HX", "camera": "720p"},
     "features": ["RTX 4080", "240Hz QHD+", "MUX switch", "Per-key RGB"], "tags": ["gaming", "high-performance", "esports"]},
    {"name": "ASUS Zenbook 14 OLED", "brand": "ASUS", "sub": "Ultrabook", "price": 1099.99, "orig": 1199.99,
     "specs": {"screen_size": "14\"", "battery": "75 Wh", "ram": "16GB", "storage": "512GB SSD", "processor": "Intel Core Ultra 7 155H", "camera": "1080p IR"},
     "features": ["OLED display", "NumberPad 2.0", "Harman Kardon audio"], "tags": ["ultrabook", "oled", "portable"]},
    {"name": "ASUS TUF Gaming A15", "brand": "ASUS", "sub": "Gaming", "price": 1099.99, "orig": 1299.99,
     "specs": {"screen_size": "15.6\"", "battery": "90 Wh", "ram": "16GB", "storage": "512GB SSD", "processor": "AMD Ryzen 7 8845HS", "camera": "720p"},
     "features": ["RTX 4060", "144Hz FHD", "MIL-STD-810H", "Two-way AI noise cancelation"], "tags": ["gaming", "durable", "value"]},

    # Acer
    {"name": "Acer Swift Go 14", "brand": "Acer", "sub": "Ultrabook", "price": 799.99, "orig": 899.99,
     "specs": {"screen_size": "14\"", "battery": "65 Wh", "ram": "16GB", "storage": "512GB SSD", "processor": "Intel Core Ultra 7 155H", "camera": "1440p"},
     "features": ["OLED display", "AI-powered features", "Fingerprint reader"], "tags": ["ultrabook", "ai", "portable"]},
    {"name": "Acer Nitro V 16", "brand": "Acer", "sub": "Gaming", "price": 1199.99, "orig": 1349.99,
     "specs": {"screen_size": "16\"", "battery": "76 Wh", "ram": "16GB", "storage": "1TB SSD", "processor": "Intel Core i7-14650HX", "camera": "1080p"},
     "features": ["RTX 4060", "165Hz WQXGA", "NitroSense controls"], "tags": ["gaming", "value", "performance"]},

    # Microsoft
    {"name": "Surface Laptop 7", "brand": "Microsoft", "sub": "Ultrabook", "price": 1299.99, "orig": 1299.99,
     "specs": {"screen_size": "15\"", "battery": "58 Wh", "ram": "16GB", "storage": "512GB SSD", "processor": "Snapdragon X Elite", "camera": "1080p"},
     "features": ["Copilot+ PC", "PixelSense display", "Haptic touchpad"], "tags": ["ultrabook", "ai", "copilot"]},

    # Framework
    {"name": "Framework Laptop 16", "brand": "Framework", "sub": "Modular", "price": 1399.99, "orig": 1399.99,
     "specs": {"screen_size": "16\"", "battery": "85 Wh", "ram": "32GB", "storage": "1TB SSD", "processor": "AMD Ryzen 7 7840HS", "camera": "1080p"},
     "features": ["Modular design", "Swappable GPU", "User upgradeable", "Open source"], "tags": ["modular", "repairable", "sustainable"]},
    {"name": "Framework Laptop 13", "brand": "Framework", "sub": "Modular", "price": 1049.99, "orig": 1049.99,
     "specs": {"screen_size": "13.5\"", "battery": "61 Wh", "ram": "16GB", "storage": "512GB SSD", "processor": "Intel Core Ultra 7 155U", "camera": "1080p"},
     "features": ["Modular ports", "User upgradeable", "3:2 aspect ratio"], "tags": ["modular", "compact", "repairable"]},

    # Razer
    {"name": "Razer Blade 16", "brand": "Razer", "sub": "Gaming", "price": 2799.99, "orig": 2999.99,
     "specs": {"screen_size": "16\"", "battery": "95.2 Wh", "ram": "32GB", "storage": "1TB SSD", "processor": "Intel Core i9-14900HX", "camera": "1080p IR"},
     "features": ["RTX 4080", "Dual-mode display", "CNC aluminum", "Chroma RGB"], "tags": ["gaming", "premium", "thin"]},
    {"name": "Razer Blade 14", "brand": "Razer", "sub": "Gaming", "price": 2199.99, "orig": 2399.99,
     "specs": {"screen_size": "14\"", "battery": "68.1 Wh", "ram": "16GB", "storage": "1TB SSD", "processor": "AMD Ryzen 9 8945HS", "camera": "1080p IR"},
     "features": ["RTX 4070", "240Hz QHD+", "Under 4 lbs"], "tags": ["gaming", "portable", "premium"]},

    # Samsung laptop
    {"name": "Samsung Galaxy Book4 Ultra", "brand": "Samsung", "sub": "Creative", "price": 2399.99, "orig": 2699.99,
     "specs": {"screen_size": "16\"", "battery": "100 Wh", "ram": "32GB", "storage": "1TB SSD", "processor": "Intel Core Ultra 9 185H", "camera": "1080p"},
     "features": ["RTX 4070", "3K AMOLED", "Galaxy AI", "Samsung ecosystem"], "tags": ["creative", "premium", "ai"]},
    {"name": "Samsung Galaxy Book4 Pro", "brand": "Samsung", "sub": "Ultrabook", "price": 1449.99, "orig": 1549.99,
     "specs": {"screen_size": "16\"", "battery": "76 Wh", "ram": "16GB", "storage": "512GB SSD", "processor": "Intel Core Ultra 7 155H", "camera": "1080p"},
     "features": ["Dynamic AMOLED 2X", "Under 3.5 lbs", "Galaxy AI"], "tags": ["ultrabook", "lightweight", "ai"]},

    # LG laptop
    {"name": "LG Gram 17 2024", "brand": "LG", "sub": "Ultrabook", "price": 1599.99, "orig": 1699.99,
     "specs": {"screen_size": "17\"", "battery": "80 Wh", "ram": "16GB", "storage": "1TB SSD", "processor": "Intel Core Ultra 7 155H", "camera": "1080p IR"},
     "features": ["Under 3 lbs", "MIL-STD-810H", "Thunderbolt 4"], "tags": ["ultrabook", "lightweight", "large-screen"]},
    {"name": "LG Gram Pro 16 2-in-1", "brand": "LG", "sub": "2-in-1", "price": 1799.99, "orig": 1899.99,
     "specs": {"screen_size": "16\"", "battery": "77 Wh", "ram": "32GB", "storage": "1TB SSD", "processor": "Intel Core Ultra 7 155H", "camera": "1080p IR"},
     "features": ["OLED display", "360-degree hinge", "Under 3.1 lbs", "Stylus support"], "tags": ["2-in-1", "lightweight", "oled"]},

    # MSI laptop
    {"name": "MSI Titan 18 HX", "brand": "MSI", "sub": "Gaming", "price": 4299.99, "orig": 4499.99,
     "specs": {"screen_size": "18\"", "battery": "99.9 Wh", "ram": "64GB", "storage": "2TB SSD", "processor": "Intel Core i9-14900HX", "camera": "1080p"},
     "features": ["RTX 4090", "Mini LED 4K 120Hz", "Cherry MX keyboard"], "tags": ["gaming", "desktop-replacement", "premium"]},
    {"name": "MSI Stealth 16 AI Studio", "brand": "MSI", "sub": "Creative", "price": 2199.99, "orig": 2399.99,
     "specs": {"screen_size": "16\"", "battery": "82 Wh", "ram": "32GB", "storage": "1TB SSD", "processor": "Intel Core Ultra 9 185H", "camera": "1080p IR"},
     "features": ["RTX 4070", "OLED 3.2K", "Thin and light", "AI Engine"], "tags": ["creative", "gaming", "portable"]},
    {"name": "MSI Modern 15", "brand": "MSI", "sub": "Budget", "price": 649.99, "orig": 749.99,
     "specs": {"screen_size": "15.6\"", "battery": "53.5 Wh", "ram": "16GB", "storage": "512GB SSD", "processor": "Intel Core Ultra 5 125H", "camera": "720p"},
     "features": ["Business & Productivity", "Nahimic audio", "Anti-flicker"], "tags": ["budget", "business", "value"]},

    # Huawei laptop
    {"name": "Huawei MateBook X Pro 2024", "brand": "Huawei", "sub": "Ultrabook", "price": 1799.99, "orig": 1899.99,
     "specs": {"screen_size": "14.2\"", "battery": "70 Wh", "ram": "32GB", "storage": "1TB SSD", "processor": "Intel Core Ultra 9 185H", "camera": "1080p"},
     "features": ["OLED 3.1K", "Under 2.2 lbs", "Full metal body", "Super Device"], "tags": ["ultrabook", "premium", "lightweight"]},

    # HP additional
    {"name": "HP EliteBook 860 G11", "brand": "HP", "sub": "Business", "price": 1549.99, "orig": 1699.99,
     "specs": {"screen_size": "16\"", "battery": "68 Wh", "ram": "32GB", "storage": "512GB SSD", "processor": "Intel Core Ultra 7 165H", "camera": "5MP IR"},
     "features": ["Sure View privacy", "Smart card reader", "MIL-STD-810H"], "tags": ["business", "enterprise", "secure"]},
    {"name": "HP Omen 16", "brand": "HP", "sub": "Gaming", "price": 1499.99, "orig": 1699.99,
     "specs": {"screen_size": "16.1\"", "battery": "83 Wh", "ram": "16GB", "storage": "1TB SSD", "processor": "AMD Ryzen 9 8945HS", "camera": "1080p"},
     "features": ["RTX 4070", "165Hz QHD", "Omen Gaming Hub", "Tempest Cooling"], "tags": ["gaming", "performance", "value"]},

    # Lenovo additional
    {"name": "Legion Pro 7i 16", "brand": "Lenovo", "sub": "Gaming", "price": 2499.99, "orig": 2699.99,
     "specs": {"screen_size": "16\"", "battery": "99.5 Wh", "ram": "32GB", "storage": "1TB SSD", "processor": "Intel Core i9-14900HX", "camera": "1080p"},
     "features": ["RTX 4080", "240Hz WQXGA", "Coldfront Hyper", "Nahimic audio"], "tags": ["gaming", "high-performance", "esports"]},
    {"name": "ThinkPad T14s Gen 6", "brand": "Lenovo", "sub": "Business", "price": 1399.99, "orig": 1499.99,
     "specs": {"screen_size": "14\"", "battery": "58 Wh", "ram": "32GB", "storage": "512GB SSD", "processor": "Snapdragon X Elite", "camera": "5MP IR"},
     "features": ["Copilot+ PC", "TrackPoint", "MIL-STD-810H", "Smart card"], "tags": ["business", "ai", "enterprise"]},

    # Gigabyte laptop
    {"name": "Gigabyte AORUS 17X", "brand": "Gigabyte", "sub": "Gaming", "price": 2599.99, "orig": 2899.99,
     "specs": {"screen_size": "17.3\"", "battery": "99 Wh", "ram": "32GB", "storage": "2TB SSD", "processor": "Intel Core i9-14900HX", "camera": "1080p"},
     "features": ["RTX 4080", "240Hz QHD", "Per-key RGB", "Windforce cooling"], "tags": ["gaming", "desktop-replacement", "premium"]},

    # ASUS additional
    {"name": "ASUS Vivobook S 15 OLED", "brand": "ASUS", "sub": "Mid-range", "price": 1099.99, "orig": 1199.99,
     "specs": {"screen_size": "15.6\"", "battery": "75 Wh", "ram": "16GB", "storage": "1TB SSD", "processor": "Snapdragon X Elite", "camera": "1080p IR"},
     "features": ["3K OLED", "Copilot+ PC", "Under 3.1 lbs", "Military grade"], "tags": ["mainstream", "oled", "ai"]},
    {"name": "ASUS Chromebook Plus CX34", "brand": "ASUS", "sub": "Chromebook", "price": 399.99, "orig": 449.99,
     "specs": {"screen_size": "14\"", "battery": "63 Wh", "ram": "8GB", "storage": "256GB SSD", "processor": "Intel Core i3-1315U", "camera": "1080p"},
     "features": ["ChromeOS Plus", "Google AI features", "Fanless", "All-day battery"], "tags": ["chromebook", "budget", "student"]},

    # HP additional
    {"name": "HP Dragonfly Pro", "brand": "HP", "sub": "Ultrabook", "price": 1499.99, "orig": 1599.99,
     "specs": {"screen_size": "14\"", "battery": "58 Wh", "ram": "16GB", "storage": "512GB SSD", "processor": "AMD Ryzen 7 7736U", "camera": "8MP"},
     "features": ["8MP camera", "Haptic touchpad", "Bang & Olufsen quad speakers"], "tags": ["ultrabook", "premium", "webcam"]},

    # Dell additional
    {"name": "Dell G16 7630", "brand": "Dell", "sub": "Gaming", "price": 1299.99, "orig": 1499.99,
     "specs": {"screen_size": "16\"", "battery": "86 Wh", "ram": "16GB", "storage": "1TB SSD", "processor": "Intel Core i7-13650HX", "camera": "720p"},
     "features": ["RTX 4060", "165Hz QHD+", "Alienware-inspired thermals"], "tags": ["gaming", "value", "performance"]},

    # Acer additional
    {"name": "Acer Aspire 5 15", "brand": "Acer", "sub": "Budget", "price": 549.99, "orig": 649.99,
     "specs": {"screen_size": "15.6\"", "battery": "50 Wh", "ram": "16GB", "storage": "512GB SSD", "processor": "Intel Core i5-1335U", "camera": "1080p"},
     "features": ["FHD IPS", "Wi-Fi 6", "Numeric keypad", "USB-C"], "tags": ["budget", "student", "mainstream"]},

    # Samsung additional
    {"name": "Samsung Galaxy Book4 360", "brand": "Samsung", "sub": "2-in-1", "price": 1099.99, "orig": 1199.99,
     "specs": {"screen_size": "15.6\"", "battery": "68 Wh", "ram": "16GB", "storage": "512GB SSD", "processor": "Intel Core Ultra 7 155U", "camera": "1080p"},
     "features": ["Super AMOLED", "360-degree hinge", "S Pen included", "Galaxy AI"], "tags": ["2-in-1", "amoled", "ai"]},

    # Lenovo ChromeBook
    {"name": "Lenovo IdeaPad Duet 5 Chromebook", "brand": "Lenovo", "sub": "Chromebook", "price": 449.99, "orig": 499.99,
     "specs": {"screen_size": "13.3\"", "battery": "42 Wh", "ram": "8GB", "storage": "128GB eMMC", "processor": "Snapdragon 7c Gen 2", "camera": "5MP"},
     "features": ["OLED display", "Detachable keyboard", "USI pen support"], "tags": ["chromebook", "detachable", "oled"]},
]

# -- Tablets -------------------------------------------------------------------

TABLETS = [
    # Apple
    {"name": "iPad Pro 13 M4", "brand": "Apple", "sub": "Professional", "price": 1299.99, "orig": 1299.99,
     "specs": {"screen_size": "13\"", "battery": "38.99 Wh", "ram": "8GB", "storage": "256GB", "processor": "Apple M4", "camera": "12MP + LiDAR"},
     "features": ["Ultra Retina XDR OLED", "Apple Pencil Pro", "Thunderbolt / USB 4"], "tags": ["professional", "creative", "premium"]},
    {"name": "iPad Pro 11 M4", "brand": "Apple", "sub": "Professional", "price": 999.99, "orig": 999.99,
     "specs": {"screen_size": "11\"", "battery": "31.29 Wh", "ram": "8GB", "storage": "256GB", "processor": "Apple M4", "camera": "12MP + LiDAR"},
     "features": ["OLED display", "ProMotion 120Hz", "Face ID"], "tags": ["professional", "portable", "creative"]},
    {"name": "iPad Air 13 M3", "brand": "Apple", "sub": "Mid-range", "price": 799.99, "orig": 799.99,
     "specs": {"screen_size": "13\"", "battery": "36.59 Wh", "ram": "8GB", "storage": "128GB", "processor": "Apple M3", "camera": "12MP"},
     "features": ["Liquid Retina display", "Apple Pencil Pro support", "Wi-Fi 6E"], "tags": ["mainstream", "productivity", "portable"]},
    {"name": "iPad Air 11 M3", "brand": "Apple", "sub": "Mid-range", "price": 599.99, "orig": 599.99,
     "specs": {"screen_size": "11\"", "battery": "28.93 Wh", "ram": "8GB", "storage": "128GB", "processor": "Apple M3", "camera": "12MP"},
     "features": ["Touch ID", "Apple Pencil Pro support", "USB-C"], "tags": ["mainstream", "compact", "value"]},
    {"name": "iPad 10th Gen", "brand": "Apple", "sub": "Budget", "price": 349.99, "orig": 449.99,
     "specs": {"screen_size": "10.9\"", "battery": "28.6 Wh", "ram": "4GB", "storage": "64GB", "processor": "A14 Bionic", "camera": "12MP"},
     "features": ["USB-C", "5G optional", "Landscape FaceTime camera"], "tags": ["budget", "student", "entry-level"]},
    {"name": "iPad Mini 7", "brand": "Apple", "sub": "Compact", "price": 499.99, "orig": 499.99,
     "specs": {"screen_size": "8.3\"", "battery": "19.3 Wh", "ram": "8GB", "storage": "128GB", "processor": "A17 Pro", "camera": "12MP"},
     "features": ["Apple Pencil Pro", "USB-C", "Wi-Fi 6E"], "tags": ["compact", "portable", "reading"]},

    # Samsung
    {"name": "Galaxy Tab S10 Ultra", "brand": "Samsung", "sub": "Professional", "price": 1199.99, "orig": 1279.99,
     "specs": {"screen_size": "14.6\"", "battery": "11200 mAh", "ram": "12GB", "storage": "256GB", "processor": "Dimensity 9300+", "camera": "13MP + 8MP"},
     "features": ["S Pen included", "Galaxy AI", "DeX mode", "Super AMOLED"], "tags": ["professional", "large-screen", "productivity"]},
    {"name": "Galaxy Tab S10+", "brand": "Samsung", "sub": "Mid-range", "price": 999.99, "orig": 999.99,
     "specs": {"screen_size": "12.4\"", "battery": "10090 mAh", "ram": "12GB", "storage": "256GB", "processor": "Dimensity 9300+", "camera": "13MP + 8MP"},
     "features": ["S Pen included", "Galaxy AI", "AMOLED 120Hz"], "tags": ["mainstream", "productivity", "large-screen"]},
    {"name": "Galaxy Tab S10 FE", "brand": "Samsung", "sub": "Budget", "price": 449.99, "orig": 449.99,
     "specs": {"screen_size": "10.9\"", "battery": "8000 mAh", "ram": "6GB", "storage": "128GB", "processor": "Exynos 1480", "camera": "8MP"},
     "features": ["S Pen included", "One UI", "Samsung DeX"], "tags": ["budget", "value", "versatile"]},

    # Lenovo
    {"name": "Lenovo Tab P12 Pro", "brand": "Lenovo", "sub": "Mid-range", "price": 599.99, "orig": 699.99,
     "specs": {"screen_size": "12.7\"", "battery": "10200 mAh", "ram": "8GB", "storage": "256GB", "processor": "Dimensity 9000", "camera": "13MP + 5MP"},
     "features": ["AMOLED display", "JBL speakers", "Precision Pen 3"], "tags": ["multimedia", "entertainment", "value"]},

    # Microsoft
    {"name": "Surface Pro 11", "brand": "Microsoft", "sub": "Professional", "price": 1199.99, "orig": 1199.99,
     "specs": {"screen_size": "13\"", "battery": "53.5 Wh", "ram": "16GB", "storage": "256GB", "processor": "Snapdragon X Elite", "camera": "10MP + 1440p front"},
     "features": ["Copilot+ PC", "PixelSense Flow", "Kickstand", "Surface Pen"], "tags": ["professional", "2-in-1", "ai"]},

    # Amazon
    {"name": "Fire Max 11", "brand": "Amazon", "sub": "Budget", "price": 229.99, "orig": 279.99,
     "specs": {"screen_size": "11\"", "battery": "7500 mAh", "ram": "4GB", "storage": "64GB", "processor": "MediaTek MT8188J", "camera": "8MP"},
     "features": ["Alexa built-in", "Stylus support", "Split-screen"], "tags": ["budget", "entertainment", "alexa"]},
    {"name": "Fire HD 10 2024", "brand": "Amazon", "sub": "Budget", "price": 139.99, "orig": 149.99,
     "specs": {"screen_size": "10.1\"", "battery": "6300 mAh", "ram": "3GB", "storage": "32GB", "processor": "Octa-core 2.0 GHz", "camera": "5MP"},
     "features": ["Alexa hands-free", "USB-C", "Show Mode"], "tags": ["budget", "entry-level", "alexa"]},

    # OnePlus tablet
    {"name": "OnePlus Pad 2", "brand": "OnePlus", "sub": "Mid-range", "price": 549.99, "orig": 549.99,
     "specs": {"screen_size": "12.1\"", "battery": "9510 mAh", "ram": "8GB", "storage": "256GB", "processor": "Snapdragon 8 Gen 3", "camera": "13MP"},
     "features": ["2.8K display", "Dolby Vision", "Stylus support", "Smart keyboard"], "tags": ["mainstream", "productivity", "value"]},

    # Xiaomi tablet
    {"name": "Xiaomi Pad 7 Pro", "brand": "Xiaomi", "sub": "Mid-range", "price": 499.99, "orig": 549.99,
     "specs": {"screen_size": "12.4\"", "battery": "10000 mAh", "ram": "8GB", "storage": "256GB", "processor": "Snapdragon 8s Gen 3", "camera": "13MP + 8MP"},
     "features": ["3K display", "Dolby Atmos", "Stylus Pro support", "68W charging"], "tags": ["mainstream", "multimedia", "value"]},

    # Huawei tablet
    {"name": "Huawei MatePad Pro 13.2", "brand": "Huawei", "sub": "Professional", "price": 899.99, "orig": 999.99,
     "specs": {"screen_size": "13.2\"", "battery": "10100 mAh", "ram": "12GB", "storage": "256GB", "processor": "Kirin 9000s", "camera": "13MP"},
     "features": ["OLED display", "M-Pencil 3", "HarmonyOS", "Smart Magnetic Keyboard"], "tags": ["professional", "creative", "premium"]},

    # Google tablet
    {"name": "Pixel Tablet 2", "brand": "Google", "sub": "Mid-range", "price": 499.99, "orig": 499.99,
     "specs": {"screen_size": "10.5\"", "battery": "7020 mAh", "ram": "8GB", "storage": "128GB", "processor": "Tensor G4", "camera": "8MP"},
     "features": ["Speaker dock included", "Hub Mode", "Google AI", "USI 2.0 stylus"], "tags": ["smart-home", "versatile", "google"]},

    # Nokia tablet
    {"name": "Nokia T21", "brand": "Nokia", "sub": "Budget", "price": 249.99, "orig": 269.99,
     "specs": {"screen_size": "10.4\"", "battery": "8200 mAh", "ram": "4GB", "storage": "64GB", "processor": "Unisoc T612", "camera": "8MP"},
     "features": ["2K display", "Stereo speakers", "3 years updates"], "tags": ["budget", "durable", "value"]},

    # Samsung prev-gen tablet
    {"name": "Galaxy Tab S9 Ultra", "brand": "Samsung", "sub": "Professional", "price": 999.99, "orig": 1199.99,
     "specs": {"screen_size": "14.6\"", "battery": "11200 mAh", "ram": "12GB", "storage": "256GB", "processor": "Snapdragon 8 Gen 2", "camera": "13MP + 8MP"},
     "features": ["S Pen included", "IP68", "DeX mode", "Super AMOLED"], "tags": ["previous-gen", "professional", "deal"]},
    {"name": "Galaxy Tab A9+", "brand": "Samsung", "sub": "Budget", "price": 219.99, "orig": 269.99,
     "specs": {"screen_size": "11\"", "battery": "7040 mAh", "ram": "4GB", "storage": "64GB", "processor": "Snapdragon 695", "camera": "8MP"},
     "features": ["TFT display", "Quad speakers", "Samsung Kids"], "tags": ["budget", "family", "entry-level"]},

    # Lenovo additional tablet
    {"name": "Lenovo Tab P11 Pro Gen 2", "brand": "Lenovo", "sub": "Mid-range", "price": 399.99, "orig": 449.99,
     "specs": {"screen_size": "11.2\"", "battery": "8000 mAh", "ram": "6GB", "storage": "128GB", "processor": "Kompanio 1300T", "camera": "13MP + 5MP"},
     "features": ["OLED display", "JBL quad speakers", "Precision Pen 3"], "tags": ["multimedia", "entertainment", "value"]},

    # ReMarkable
    {"name": "reMarkable 2", "brand": "reMarkable", "sub": "E-ink", "price": 449.99, "orig": 449.99,
     "specs": {"screen_size": "10.3\"", "battery": "3000 mAh", "ram": "1GB", "storage": "8GB", "processor": "Dual-core 1.2 GHz", "camera": "N/A"},
     "features": ["E-ink display", "Paper-like writing", "Marker Plus stylus", "No distractions"], "tags": ["e-ink", "writing", "productivity"]},

    # Boox
    {"name": "BOOX Tab Ultra C Pro", "brand": "BOOX", "sub": "E-ink", "price": 599.99, "orig": 649.99,
     "specs": {"screen_size": "10.3\"", "battery": "6300 mAh", "ram": "6GB", "storage": "128GB", "processor": "Snapdragon 662", "camera": "16MP"},
     "features": ["Color Kaleido 3 e-ink", "Android 12", "Stylus included", "GPS"], "tags": ["e-ink", "color", "reading"]},
]

# -- Smartwatches --------------------------------------------------------------

WATCHES = [
    {"name": "Apple Watch Ultra 2", "brand": "Apple", "sub": "Premium", "price": 799.99, "orig": 799.99,
     "specs": {"screen_size": "1.93\"", "battery": "564 mAh", "ram": "1GB", "storage": "64GB", "processor": "S9 SiP", "camera": "N/A"},
     "features": ["Titanium case", "86dB siren", "Depth gauge", "Precision GPS"], "tags": ["premium", "outdoor", "diving"]},
    {"name": "Apple Watch Series 10", "brand": "Apple", "sub": "Mid-range", "price": 399.99, "orig": 399.99,
     "specs": {"screen_size": "1.78\"", "battery": "326 mAh", "ram": "1GB", "storage": "64GB", "processor": "S10 SiP", "camera": "N/A"},
     "features": ["Sleep apnea detection", "Water temp sensor", "Always-On display"], "tags": ["fitness", "health", "mainstream"]},
    {"name": "Samsung Galaxy Watch Ultra", "brand": "Samsung", "sub": "Premium", "price": 649.99, "orig": 649.99,
     "specs": {"screen_size": "1.47\"", "battery": "590 mAh", "ram": "2GB", "storage": "32GB", "processor": "Exynos W1000", "camera": "N/A"},
     "features": ["Titanium Grade 4", "10ATM + IP68", "Dual-frequency GPS"], "tags": ["premium", "outdoor", "durable"]},
    {"name": "Samsung Galaxy Watch 7", "brand": "Samsung", "sub": "Mid-range", "price": 299.99, "orig": 299.99,
     "specs": {"screen_size": "1.47\"", "battery": "425 mAh", "ram": "2GB", "storage": "32GB", "processor": "Exynos W1000", "camera": "N/A"},
     "features": ["BioActive sensor", "Wear OS 5", "Galaxy AI"], "tags": ["fitness", "health", "value"]},
    {"name": "Google Pixel Watch 3", "brand": "Google", "sub": "Mid-range", "price": 349.99, "orig": 349.99,
     "specs": {"screen_size": "1.40\"", "battery": "307 mAh", "ram": "2GB", "storage": "32GB", "processor": "Qualcomm SW5100", "camera": "N/A"},
     "features": ["Fitbit integration", "UWB support", "Wear OS"], "tags": ["fitness", "google", "smart"]},
    {"name": "Garmin Fenix 8", "brand": "Garmin", "sub": "Premium", "price": 999.99, "orig": 999.99,
     "specs": {"screen_size": "1.4\"", "battery": "Up to 48 days", "ram": "N/A", "storage": "32GB", "processor": "Custom Garmin", "camera": "N/A"},
     "features": ["AMOLED display", "Solar charging", "Multi-band GPS", "Dive mode"], "tags": ["outdoor", "endurance", "premium"]},
    {"name": "Garmin Venu 3", "brand": "Garmin", "sub": "Mid-range", "price": 449.99, "orig": 449.99,
     "specs": {"screen_size": "1.4\"", "battery": "Up to 14 days", "ram": "N/A", "storage": "8GB", "processor": "Custom Garmin", "camera": "N/A"},
     "features": ["AMOLED display", "Body Battery", "Wheelchair mode", "Nap detection"], "tags": ["fitness", "health", "lifestyle"]},
    {"name": "Garmin Forerunner 965", "brand": "Garmin", "sub": "Sports", "price": 599.99, "orig": 599.99,
     "specs": {"screen_size": "1.4\"", "battery": "Up to 23 days", "ram": "N/A", "storage": "32GB", "processor": "Custom Garmin", "camera": "N/A"},
     "features": ["AMOLED display", "Training Readiness", "Race Predictor", "Multi-band GPS"], "tags": ["running", "triathlon", "sports"]},
    {"name": "Apple Watch SE 3", "brand": "Apple", "sub": "Budget", "price": 249.99, "orig": 249.99,
     "specs": {"screen_size": "1.57\"", "battery": "245 mAh", "ram": "1GB", "storage": "32GB", "processor": "S9 SiP", "camera": "N/A"},
     "features": ["Crash Detection", "Fall Detection", "Workout tracking", "Family Setup"], "tags": ["budget", "fitness", "value"]},
    {"name": "Fitbit Sense 3", "brand": "Fitbit", "sub": "Mid-range", "price": 299.99, "orig": 329.99,
     "specs": {"screen_size": "1.58\"", "battery": "Up to 6 days", "ram": "N/A", "storage": "4GB", "processor": "Custom Fitbit", "camera": "N/A"},
     "features": ["EDA sensor", "Skin temperature", "SpO2", "6-month Premium trial"], "tags": ["health", "fitness", "wellness"]},
    {"name": "Fitbit Charge 6", "brand": "Fitbit", "sub": "Budget", "price": 159.99, "orig": 159.99,
     "specs": {"screen_size": "0.86\"", "battery": "Up to 7 days", "ram": "N/A", "storage": "N/A", "processor": "Custom Fitbit", "camera": "N/A"},
     "features": ["Google Maps", "YouTube Music", "ECG", "SpO2"], "tags": ["budget", "fitness", "tracker"]},
    {"name": "Amazfit T-Rex Ultra", "brand": "Amazfit", "sub": "Premium", "price": 399.99, "orig": 399.99,
     "specs": {"screen_size": "1.39\"", "battery": "Up to 20 days", "ram": "N/A", "storage": "N/A", "processor": "Custom Amazfit", "camera": "N/A"},
     "features": ["Freediving to 30m", "Dual-band GPS", "MIL-STD-810G", "Mud-resistant"], "tags": ["outdoor", "extreme", "durable"]},
    {"name": "Amazfit GTR 4", "brand": "Amazfit", "sub": "Mid-range", "price": 199.99, "orig": 229.99,
     "specs": {"screen_size": "1.43\"", "battery": "Up to 14 days", "ram": "N/A", "storage": "N/A", "processor": "Custom Amazfit", "camera": "N/A"},
     "features": ["AMOLED display", "150+ sport modes", "Alexa built-in", "Bluetooth calling"], "tags": ["fitness", "value", "versatile"]},
    {"name": "Withings ScanWatch 2", "brand": "Withings", "sub": "Health", "price": 349.99, "orig": 349.99,
     "specs": {"screen_size": "1.0\"", "battery": "Up to 30 days", "ram": "N/A", "storage": "N/A", "processor": "Custom Withings", "camera": "N/A"},
     "features": ["ECG", "SpO2", "Temperature sensor", "Hybrid analog/digital"], "tags": ["health", "elegant", "medical"]},
    {"name": "COROS PACE 3", "brand": "COROS", "sub": "Sports", "price": 229.99, "orig": 229.99,
     "specs": {"screen_size": "1.2\"", "battery": "Up to 38 days", "ram": "N/A", "storage": "4GB", "processor": "Custom COROS", "camera": "N/A"},
     "features": ["Dual-frequency GPS", "Music storage", "Under 39g", "EvoLab training"], "tags": ["running", "ultralight", "endurance"]},
    {"name": "Suunto Race", "brand": "Suunto", "sub": "Sports", "price": 449.99, "orig": 449.99,
     "specs": {"screen_size": "1.43\"", "battery": "Up to 26 days", "ram": "N/A", "storage": "32GB", "processor": "Custom Suunto", "camera": "N/A"},
     "features": ["AMOLED display", "Dual-band GPS", "Turn-by-turn nav", "SuuntoPlus"], "tags": ["sports", "outdoor", "navigation"]},
    {"name": "Polar Vantage V3", "brand": "Polar", "sub": "Sports", "price": 599.99, "orig": 599.99,
     "specs": {"screen_size": "1.39\"", "battery": "Up to 8 days", "ram": "N/A", "storage": "32GB", "processor": "Custom Polar", "camera": "N/A"},
     "features": ["AMOLED display", "Biosense sensor", "Dual-band GPS", "Training Load Pro"], "tags": ["sports", "training", "premium"]},
    {"name": "TicWatch Pro 5 Enduro", "brand": "Mobvoi", "sub": "Mid-range", "price": 349.99, "orig": 349.99,
     "specs": {"screen_size": "1.43\"", "battery": "Up to 45 days", "ram": "2GB", "storage": "32GB", "processor": "Snapdragon W5+ Gen 1", "camera": "N/A"},
     "features": ["Dual-layer display", "Wear OS", "MIL-STD-810H", "Compass"], "tags": ["outdoor", "battery", "wear-os"]},
    {"name": "OnePlus Watch 2", "brand": "OnePlus", "sub": "Mid-range", "price": 299.99, "orig": 299.99,
     "specs": {"screen_size": "1.43\"", "battery": "Up to 4 days", "ram": "2GB", "storage": "32GB", "processor": "Snapdragon W5 Gen 1", "camera": "N/A"},
     "features": ["AMOLED display", "Wear OS", "100+ sport modes", "Dual engine"], "tags": ["fitness", "wear-os", "value"]},
    {"name": "Xiaomi Watch 2 Pro", "brand": "Xiaomi", "sub": "Mid-range", "price": 269.99, "orig": 299.99,
     "specs": {"screen_size": "1.43\"", "battery": "Up to 3 days", "ram": "2GB", "storage": "32GB", "processor": "Snapdragon W5+ Gen 1", "camera": "N/A"},
     "features": ["AMOLED display", "Wear OS", "eSIM support", "150+ sport modes"], "tags": ["fitness", "wear-os", "esim"]},
    {"name": "Huawei Watch GT 5 Pro", "brand": "Huawei", "sub": "Premium", "price": 449.99, "orig": 449.99,
     "specs": {"screen_size": "1.43\"", "battery": "Up to 14 days", "ram": "N/A", "storage": "4GB", "processor": "Custom Huawei", "camera": "N/A"},
     "features": ["Sapphire crystal", "Titanium body", "Free diving", "ECG"], "tags": ["premium", "health", "elegant"]},
]

# -- Headphones ----------------------------------------------------------------

HEADPHONES = [
    {"name": "AirPods Pro 3", "brand": "Apple", "sub": "True Wireless", "price": 249.99, "orig": 249.99,
     "specs": {"screen_size": "N/A", "battery": "6h (30h with case)", "ram": "N/A", "storage": "N/A", "processor": "H3 chip", "camera": "N/A"},
     "features": ["Active Noise Cancellation", "Adaptive Audio", "USB-C case", "Hearing aid mode"], "tags": ["anc", "wireless", "premium"]},
    {"name": "AirPods Max 2", "brand": "Apple", "sub": "Over-ear", "price": 549.99, "orig": 549.99,
     "specs": {"screen_size": "N/A", "battery": "20h", "ram": "N/A", "storage": "N/A", "processor": "H2 chip", "camera": "N/A"},
     "features": ["Digital Crown", "Spatial Audio", "USB-C", "Aluminum design"], "tags": ["over-ear", "premium", "audiophile"]},
    {"name": "Sony WH-1000XM6", "brand": "Sony", "sub": "Over-ear", "price": 399.99, "orig": 399.99,
     "specs": {"screen_size": "N/A", "battery": "40h", "ram": "N/A", "storage": "N/A", "processor": "V2 Processor", "camera": "N/A"},
     "features": ["Industry-leading ANC", "LDAC", "Multipoint", "Speak-to-Chat"], "tags": ["anc", "over-ear", "audiophile"]},
    {"name": "Sony WF-1000XM6", "brand": "Sony", "sub": "True Wireless", "price": 279.99, "orig": 299.99,
     "specs": {"screen_size": "N/A", "battery": "8h (24h with case)", "ram": "N/A", "storage": "N/A", "processor": "V2 Processor", "camera": "N/A"},
     "features": ["ANC", "Hi-Res Audio", "LDAC", "IPX4"], "tags": ["anc", "wireless", "compact"]},
    {"name": "Samsung Galaxy Buds 3 Pro", "brand": "Samsung", "sub": "True Wireless", "price": 249.99, "orig": 249.99,
     "specs": {"screen_size": "N/A", "battery": "7h (30h with case)", "ram": "N/A", "storage": "N/A", "processor": "Custom Samsung", "camera": "N/A"},
     "features": ["ANC", "360 Audio", "Blade design", "Galaxy AI interpreter"], "tags": ["anc", "wireless", "ai"]},
    {"name": "Bose QuietComfort Ultra", "brand": "Bose", "sub": "Over-ear", "price": 429.99, "orig": 429.99,
     "specs": {"screen_size": "N/A", "battery": "24h", "ram": "N/A", "storage": "N/A", "processor": "Custom Bose", "camera": "N/A"},
     "features": ["Immersive Audio", "CustomTune ANC", "Multipoint", "Plush comfort"], "tags": ["anc", "over-ear", "comfort"]},
    {"name": "Bose QuietComfort Ultra Earbuds", "brand": "Bose", "sub": "True Wireless", "price": 299.99, "orig": 299.99,
     "specs": {"screen_size": "N/A", "battery": "6h (24h with case)", "ram": "N/A", "storage": "N/A", "processor": "Custom Bose", "camera": "N/A"},
     "features": ["Immersive Audio", "CustomTune ANC", "IPX4", "Fit tips"], "tags": ["anc", "wireless", "premium"]},
    {"name": "Sennheiser Momentum 4", "brand": "Sennheiser", "sub": "Over-ear", "price": 349.99, "orig": 379.99,
     "specs": {"screen_size": "N/A", "battery": "60h", "ram": "N/A", "storage": "N/A", "processor": "Custom Sennheiser", "camera": "N/A"},
     "features": ["Adaptive ANC", "aptX Adaptive", "Sound Personalization", "Foldable"], "tags": ["over-ear", "audiophile", "battery"]},
    {"name": "Google Pixel Buds Pro 2", "brand": "Google", "sub": "True Wireless", "price": 229.99, "orig": 229.99,
     "specs": {"screen_size": "N/A", "battery": "8h (30h with case)", "ram": "N/A", "storage": "N/A", "processor": "Tensor A1", "camera": "N/A"},
     "features": ["ANC", "Gemini assistant", "Conversation Detection", "IPX4"], "tags": ["anc", "wireless", "ai"]},
    {"name": "Jabra Elite 10 Gen 2", "brand": "Jabra", "sub": "True Wireless", "price": 279.99, "orig": 279.99,
     "specs": {"screen_size": "N/A", "battery": "8h (36h with case)", "ram": "N/A", "storage": "N/A", "processor": "Custom Jabra", "camera": "N/A"},
     "features": ["Dolby Atmos", "Spatial Sound", "IP57", "Multipoint"], "tags": ["anc", "wireless", "spatial"]},
    {"name": "JBL Tour Pro 3", "brand": "JBL", "sub": "True Wireless", "price": 299.99, "orig": 299.99,
     "specs": {"screen_size": "N/A", "battery": "8h (32h with case)", "ram": "N/A", "storage": "N/A", "processor": "Custom JBL", "camera": "N/A"},
     "features": ["Smart charging case display", "True Adaptive ANC", "LDAC", "Auracast"], "tags": ["anc", "wireless", "premium"]},
    {"name": "JBL Tune 770NC", "brand": "JBL", "sub": "Over-ear", "price": 99.99, "orig": 129.99,
     "specs": {"screen_size": "N/A", "battery": "44h", "ram": "N/A", "storage": "N/A", "processor": "Custom JBL", "camera": "N/A"},
     "features": ["Adaptive ANC", "Multipoint", "JBL Pure Bass", "Foldable"], "tags": ["budget", "over-ear", "bass"]},
    {"name": "Beyerdynamic DT 900 Pro X", "brand": "Beyerdynamic", "sub": "Studio", "price": 269.99, "orig": 299.99,
     "specs": {"screen_size": "N/A", "battery": "N/A (wired)", "ram": "N/A", "storage": "N/A", "processor": "N/A", "camera": "N/A"},
     "features": ["Open-back", "STELLAR.45 driver", "Detachable cable", "Made in Germany"], "tags": ["studio", "audiophile", "wired"]},
    {"name": "Audio-Technica ATH-M50xBT2", "brand": "Audio-Technica", "sub": "Over-ear", "price": 199.99, "orig": 199.99,
     "specs": {"screen_size": "N/A", "battery": "50h", "ram": "N/A", "storage": "N/A", "processor": "N/A", "camera": "N/A"},
     "features": ["45mm drivers", "LDAC", "Multipoint", "Foldable"], "tags": ["over-ear", "studio", "wireless"]},
    {"name": "Shure AONIC 50 Gen 2", "brand": "Shure", "sub": "Over-ear", "price": 399.99, "orig": 399.99,
     "specs": {"screen_size": "N/A", "battery": "45h", "ram": "N/A", "storage": "N/A", "processor": "Custom Shure", "camera": "N/A"},
     "features": ["Studio-quality ANC", "Snapdragon Sound", "CustomTune", "USB-C DAC"], "tags": ["audiophile", "anc", "premium"]},
    {"name": "Nothing Ear (3)", "brand": "Nothing", "sub": "True Wireless", "price": 149.99, "orig": 149.99,
     "specs": {"screen_size": "N/A", "battery": "7h (30h with case)", "ram": "N/A", "storage": "N/A", "processor": "Custom Nothing", "camera": "N/A"},
     "features": ["Smart ANC", "ChatGPT integration", "Transparent design", "LDAC"], "tags": ["design", "anc", "value"]},
    {"name": "Samsung Galaxy Buds FE", "brand": "Samsung", "sub": "True Wireless", "price": 99.99, "orig": 99.99,
     "specs": {"screen_size": "N/A", "battery": "6h (21h with case)", "ram": "N/A", "storage": "N/A", "processor": "Custom Samsung", "camera": "N/A"},
     "features": ["ANC", "IPX2", "Wing-tip design", "SmartThings Find"], "tags": ["budget", "wireless", "value"]},
    {"name": "Beats Studio Pro", "brand": "Beats", "sub": "Over-ear", "price": 349.99, "orig": 349.99,
     "specs": {"screen_size": "N/A", "battery": "40h", "ram": "N/A", "storage": "N/A", "processor": "Custom Apple", "camera": "N/A"},
     "features": ["ANC", "Spatial Audio", "USB-C", "Works with Android and Apple"], "tags": ["over-ear", "bass", "lifestyle"]},
    {"name": "Beats Fit Pro", "brand": "Beats", "sub": "True Wireless", "price": 199.99, "orig": 199.99,
     "specs": {"screen_size": "N/A", "battery": "6h (24h with case)", "ram": "N/A", "storage": "N/A", "processor": "H1 chip", "camera": "N/A"},
     "features": ["ANC", "Secure-fit wingtips", "IPX4", "Spatial Audio"], "tags": ["sports", "wireless", "active"]},
    {"name": "Technics EAH-A800", "brand": "Technics", "sub": "Over-ear", "price": 349.99, "orig": 349.99,
     "specs": {"screen_size": "N/A", "battery": "50h", "ram": "N/A", "storage": "N/A", "processor": "Custom Technics", "camera": "N/A"},
     "features": ["LDAC", "Multipoint", "ANC", "Premium sound"], "tags": ["audiophile", "over-ear", "premium"]},
    {"name": "Anker Soundcore Space Q45", "brand": "Anker", "sub": "Over-ear", "price": 99.99, "orig": 149.99,
     "specs": {"screen_size": "N/A", "battery": "50h", "ram": "N/A", "storage": "N/A", "processor": "Custom Anker", "camera": "N/A"},
     "features": ["Adaptive ANC", "LDAC", "Multipoint", "Foldable"], "tags": ["budget", "over-ear", "value"]},
    {"name": "Anker Soundcore Liberty 4 NC", "brand": "Anker", "sub": "True Wireless", "price": 79.99, "orig": 99.99,
     "specs": {"screen_size": "N/A", "battery": "8h (28h with case)", "ram": "N/A", "storage": "N/A", "processor": "Custom Anker", "camera": "N/A"},
     "features": ["Adaptive ANC", "LDAC", "IPX4", "Wireless charging case"], "tags": ["budget", "wireless", "value"]},
    {"name": "Sony LinkBuds Open", "brand": "Sony", "sub": "Open-ear", "price": 179.99, "orig": 199.99,
     "specs": {"screen_size": "N/A", "battery": "8h (22h with case)", "ram": "N/A", "storage": "N/A", "processor": "V1 Processor", "camera": "N/A"},
     "features": ["Open-ear design", "360 Reality Audio", "IPX4", "Multipoint"], "tags": ["open-ear", "ambient", "wireless"]},
    {"name": "Skullcandy Crusher ANC 2", "brand": "Skullcandy", "sub": "Over-ear", "price": 179.99, "orig": 199.99,
     "specs": {"screen_size": "N/A", "battery": "50h", "ram": "N/A", "storage": "N/A", "processor": "Custom Skullcandy", "camera": "N/A"},
     "features": ["Adjustable bass haptics", "ANC", "Personal Sound", "Tile built-in"], "tags": ["bass", "over-ear", "fun"]},
]

# -- Monitors ------------------------------------------------------------------

MONITORS = [
    {"name": "LG UltraGear 32GS95UE", "brand": "LG", "sub": "Gaming", "price": 1299.99, "orig": 1399.99,
     "specs": {"screen_size": "32\"", "battery": "N/A", "ram": "N/A", "storage": "N/A", "processor": "N/A", "camera": "N/A"},
     "features": ["4K OLED", "240Hz", "0.03ms response", "G-Sync / FreeSync"], "tags": ["gaming", "oled", "4k"]},
    {"name": "Samsung Odyssey G9 G95C", "brand": "Samsung", "sub": "Ultrawide", "price": 1099.99, "orig": 1299.99,
     "specs": {"screen_size": "49\"", "battery": "N/A", "ram": "N/A", "storage": "N/A", "processor": "N/A", "camera": "N/A"},
     "features": ["Dual QHD (5120x1440)", "240Hz", "1ms response", "1000R curve"], "tags": ["ultrawide", "gaming", "immersive"]},
    {"name": "Dell UltraSharp U2724D", "brand": "Dell", "sub": "Professional", "price": 619.99, "orig": 619.99,
     "specs": {"screen_size": "27\"", "battery": "N/A", "ram": "N/A", "storage": "N/A", "processor": "N/A", "camera": "N/A"},
     "features": ["QHD IPS Black", "USB-C 90W", "KVM switch", "100% sRGB"], "tags": ["professional", "color-accurate", "usb-c"]},
    {"name": "ASUS ProArt PA32UCXR", "brand": "ASUS", "sub": "Creative", "price": 3499.99, "orig": 3499.99,
     "specs": {"screen_size": "32\"", "battery": "N/A", "ram": "N/A", "storage": "N/A", "processor": "N/A", "camera": "N/A"},
     "features": ["Mini LED", "4K HDR 1600", "Calman Verified", "Thunderbolt 4"], "tags": ["creative", "hdr", "color-accurate"]},
    {"name": "BenQ MOBIUZ EX2710U", "brand": "BenQ", "sub": "Gaming", "price": 599.99, "orig": 699.99,
     "specs": {"screen_size": "27\"", "battery": "N/A", "ram": "N/A", "storage": "N/A", "processor": "N/A", "camera": "N/A"},
     "features": ["4K 144Hz", "IPS", "HDRi", "treVolo speakers"], "tags": ["gaming", "4k", "speakers"]},
    {"name": "LG DualUp 28MQ780", "brand": "LG", "sub": "Productivity", "price": 699.99, "orig": 749.99,
     "specs": {"screen_size": "27.6\"", "battery": "N/A", "ram": "N/A", "storage": "N/A", "processor": "N/A", "camera": "N/A"},
     "features": ["16:18 aspect ratio", "Nano IPS", "USB-C 90W", "Ergo stand"], "tags": ["productivity", "unique", "usb-c"]},
    {"name": "Apple Studio Display", "brand": "Apple", "sub": "Professional", "price": 1599.99, "orig": 1599.99,
     "specs": {"screen_size": "27\"", "battery": "N/A", "ram": "N/A", "storage": "N/A", "processor": "A13 Bionic", "camera": "12MP Center Stage"},
     "features": ["5K Retina", "P3 wide color", "Spatial Audio", "Thunderbolt 3"], "tags": ["professional", "5k", "apple"]},
    {"name": "Gigabyte M28U", "brand": "Gigabyte", "sub": "Gaming", "price": 449.99, "orig": 549.99,
     "specs": {"screen_size": "28\"", "battery": "N/A", "ram": "N/A", "storage": "N/A", "processor": "N/A", "camera": "N/A"},
     "features": ["4K 144Hz", "KVM switch", "USB-C", "SS IPS"], "tags": ["gaming", "4k", "value"]},
    {"name": "MSI MAG 341CQP", "brand": "MSI", "sub": "Ultrawide", "price": 799.99, "orig": 899.99,
     "specs": {"screen_size": "34\"", "battery": "N/A", "ram": "N/A", "storage": "N/A", "processor": "N/A", "camera": "N/A"},
     "features": ["QD-OLED", "175Hz", "0.03ms", "FreeSync Premium Pro"], "tags": ["ultrawide", "oled", "gaming"]},
    {"name": "ASUS ROG Swift PG32UCDM", "brand": "ASUS", "sub": "Gaming", "price": 1299.99, "orig": 1399.99,
     "specs": {"screen_size": "32\"", "battery": "N/A", "ram": "N/A", "storage": "N/A", "processor": "N/A", "camera": "N/A"},
     "features": ["4K QD-OLED", "240Hz", "0.03ms", "G-Sync Compatible"], "tags": ["gaming", "oled", "4k"]},
    {"name": "Dell S2722QC", "brand": "Dell", "sub": "Productivity", "price": 299.99, "orig": 349.99,
     "specs": {"screen_size": "27\"", "battery": "N/A", "ram": "N/A", "storage": "N/A", "processor": "N/A", "camera": "N/A"},
     "features": ["4K IPS", "USB-C 65W", "Built-in speakers", "AMD FreeSync"], "tags": ["productivity", "4k", "value"]},
    {"name": "LG 27UP850N", "brand": "LG", "sub": "Productivity", "price": 349.99, "orig": 399.99,
     "specs": {"screen_size": "27\"", "battery": "N/A", "ram": "N/A", "storage": "N/A", "processor": "N/A", "camera": "N/A"},
     "features": ["4K IPS", "USB-C 96W", "DCI-P3 95%", "VESA DisplayHDR 400"], "tags": ["productivity", "4k", "color-accurate"]},
    {"name": "Samsung ViewFinity S9", "brand": "Samsung", "sub": "Creative", "price": 1299.99, "orig": 1599.99,
     "specs": {"screen_size": "27\"", "battery": "N/A", "ram": "N/A", "storage": "N/A", "processor": "N/A", "camera": "N/A"},
     "features": ["5K IPS", "Matte display", "SlimFit Camera", "Tizen Smart TV"], "tags": ["creative", "5k", "mac-alternative"]},
    {"name": "BenQ PD2706UA", "brand": "BenQ", "sub": "Professional", "price": 549.99, "orig": 599.99,
     "specs": {"screen_size": "27\"", "battery": "N/A", "ram": "N/A", "storage": "N/A", "processor": "N/A", "camera": "N/A"},
     "features": ["4K IPS", "USB-C 90W", "M-Book mode", "Calman Verified"], "tags": ["professional", "design", "color-accurate"]},
    {"name": "Alienware AW3225QF", "brand": "Dell", "sub": "Gaming", "price": 1099.99, "orig": 1199.99,
     "specs": {"screen_size": "32\"", "battery": "N/A", "ram": "N/A", "storage": "N/A", "processor": "N/A", "camera": "N/A"},
     "features": ["4K QD-OLED", "240Hz", "0.03ms", "AlienVision", "G-Sync"], "tags": ["gaming", "oled", "premium"]},
    {"name": "HP Z27k G3", "brand": "HP", "sub": "Professional", "price": 539.99, "orig": 599.99,
     "specs": {"screen_size": "27\"", "battery": "N/A", "ram": "N/A", "storage": "N/A", "processor": "N/A", "camera": "N/A"},
     "features": ["4K IPS", "USB-C 100W", "Factory calibrated", "Daisy chain"], "tags": ["professional", "4k", "enterprise"]},
    {"name": "AOC U28G2XU2", "brand": "AOC", "sub": "Gaming", "price": 349.99, "orig": 399.99,
     "specs": {"screen_size": "28\"", "battery": "N/A", "ram": "N/A", "storage": "N/A", "processor": "N/A", "camera": "N/A"},
     "features": ["4K 144Hz", "IPS", "1ms GTG", "FreeSync Premium Pro"], "tags": ["gaming", "4k", "budget"]},
    {"name": "Acer Predator X34V", "brand": "Acer", "sub": "Ultrawide", "price": 899.99, "orig": 999.99,
     "specs": {"screen_size": "34\"", "battery": "N/A", "ram": "N/A", "storage": "N/A", "processor": "N/A", "camera": "N/A"},
     "features": ["WQHD OLED", "175Hz", "0.01ms", "G-Sync Compatible"], "tags": ["ultrawide", "oled", "gaming"]},
    {"name": "ViewSonic VP2786-4K", "brand": "ViewSonic", "sub": "Creative", "price": 999.99, "orig": 1099.99,
     "specs": {"screen_size": "27\"", "battery": "N/A", "ram": "N/A", "storage": "N/A", "processor": "N/A", "camera": "N/A"},
     "features": ["4K IPS", "Pantone Validated", "Thunderbolt 4", "ColorPro Wheel"], "tags": ["creative", "color-accurate", "photography"]},
    {"name": "Philips Evnia 34M2C7600MV", "brand": "Philips", "sub": "Ultrawide", "price": 1199.99, "orig": 1299.99,
     "specs": {"screen_size": "34\"", "battery": "N/A", "ram": "N/A", "storage": "N/A", "processor": "N/A", "camera": "N/A"},
     "features": ["QD-OLED", "175Hz", "0.1ms", "Ambiglow", "USB-C 90W"], "tags": ["ultrawide", "oled", "immersive"]},
    {"name": "ASUS ProArt PA279CRV", "brand": "ASUS", "sub": "Creative", "price": 499.99, "orig": 549.99,
     "specs": {"screen_size": "27\"", "battery": "N/A", "ram": "N/A", "storage": "N/A", "processor": "N/A", "camera": "N/A"},
     "features": ["4K IPS", "USB-C 96W", "Calman Verified", "ProArt Preset"], "tags": ["creative", "4k", "value"]},
    {"name": "Samsung Smart Monitor M8", "brand": "Samsung", "sub": "Smart", "price": 699.99, "orig": 729.99,
     "specs": {"screen_size": "32\"", "battery": "N/A", "ram": "N/A", "storage": "N/A", "processor": "N/A", "camera": "SlimFit Cam"},
     "features": ["4K Smart TV", "Tizen OS", "SlimFit Camera", "Wireless DeX"], "tags": ["smart", "4k", "lifestyle"]},
]


def build_products():
    """Combine all product lists, assign sequential integer IDs, retailers, etc."""
    all_raw = []
    category_map = {
        "phone": "Smartphones",
        "laptop": "Laptops",
        "tablet": "Tablets",
        "watch": "Smartwatches",
        "headphone": "Headphones",
        "monitor": "Monitors",
    }

    for kind, items in [("phone", PHONES), ("laptop", LAPTOPS), ("tablet", TABLETS),
                        ("watch", WATCHES), ("headphone", HEADPHONES), ("monitor", MONITORS)]:
        for item in items:
            all_raw.append({**item, "_kind": kind})

    random.shuffle(all_raw)
    retailer_names = [r["name"] for r in RETAILERS]

    products = []
    for idx, raw in enumerate(all_raw, start=1):
        orig = raw["orig"]
        price = raw["price"]
        discount = round((1 - price / orig) * 100) if orig > price else 0

        # Assign retailer round-robin with some randomness
        retailer = random.choice(retailer_names)

        # Generate added_date spread over ~18 months
        months_ago = random.uniform(0.5, 18)

        # Rating with some variance
        base_rating = random.choice([3.5, 3.7, 3.8, 3.9, 4.0, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8])
        num_reviews = random.randint(42, 2800)

        # In-stock: ~85% in stock
        in_stock = random.random() < 0.85

        product = {
            "id": idx,
            "name": raw["name"],
            "brand": raw["brand"],
            "category": category_map[raw["_kind"]],
            "subcategory": raw["sub"],
            "description": _generate_description(raw),
            "price": price,
            "original_price": orig,
            "discount_pct": discount,
            "retailer": retailer,
            "rating": base_rating,
            "num_reviews": num_reviews,
            "in_stock": in_stock,
            "specs": raw["specs"],
            "features": raw["features"],
            "tags": raw["tags"],
            "price_history": _price_history(orig, price),
            "added_date": _date(months_ago),
        }
        products.append(product)

    # Sort by id for stable output
    products.sort(key=lambda p: p["id"])
    return products


def _generate_description(raw):
    """Generate a short product description from the name and specs."""
    brand = raw["brand"]
    name = raw["name"]
    specs = raw["specs"]
    parts = [f"{brand} {name}"]
    if specs.get("processor") and specs["processor"] != "N/A":
        parts.append(f"powered by {specs['processor']}")
    if specs.get("screen_size") and specs["screen_size"] != "N/A":
        parts.append(f"with a {specs['screen_size']} display")
    if specs.get("ram") and specs["ram"] != "N/A":
        parts.append(f"and {specs['ram']} RAM")
    return ", ".join(parts)


def build_categories(products):
    """Build categories with accurate product counts."""
    cat_counts = {}
    for p in products:
        cat_counts[p["category"]] = cat_counts.get(p["category"], 0) + 1
    result = []
    for cat in CATEGORIES:
        cat["product_count"] = cat_counts.get(cat["name"], 0)
        result.append(cat)
    return result


def build_retailers(products):
    """Build retailers with accurate product counts."""
    ret_counts = {}
    for p in products:
        ret_counts[p["retailer"]] = ret_counts.get(p["retailer"], 0) + 1
    result = []
    for r in RETAILERS:
        r["product_count"] = ret_counts.get(r["name"], 0)
        result.append(r)
    return result


def build_users(products):
    """Generate 8 users with saved products and subscribed categories."""
    cat_names = [c["name"] for c in CATEGORIES]
    product_ids = [p["id"] for p in products]

    users_raw = [
        {"username": "techsavvy_mike", "name": "Mike Thompson", "email": "mike.t@example.com"},
        {"username": "gadget_guru", "name": "Sarah Chen", "email": "sarah.c@example.com"},
        {"username": "budget_hunter", "name": "Alex Rivera", "email": "alex.r@example.com"},
        {"username": "pro_photog", "name": "Diana Kovalenko", "email": "diana.k@example.com"},
        {"username": "gamer_zed", "name": "Zed Martinez", "email": "zed.m@example.com"},
        {"username": "audiophile_kim", "name": "Kim Nguyen", "email": "kim.n@example.com"},
        {"username": "dev_priya", "name": "Priya Sharma", "email": "priya.s@example.com"},
        {"username": "fitness_jay", "name": "Jay Okonkwo", "email": "jay.o@example.com"},
    ]

    users = []
    for i, u in enumerate(users_raw, start=1):
        saved = sorted(random.sample(product_ids, k=random.randint(2, 6)))
        subs = random.sample(cat_names, k=random.randint(1, 3))
        users.append({
            "id": i,
            "username": u["username"],
            "name": u["name"],
            "email": u["email"],
            "saved_products": saved,
            "subscribed_categories": subs,
        })
    return users


def main():
    products = build_products()
    categories = build_categories(products)
    retailers = build_retailers(products)
    users = build_users(products)

    print(f"Generated {len(products)} products across {len(categories)} categories")
    for cat in categories:
        print(f"  {cat['name']}: {cat['product_count']} products")
    print(f"Generated {len(retailers)} retailers")
    print(f"Generated {len(users)} users")

    # Write to data dir and pristine
    for target_dir in [SITE_DATA, PRISTINE]:
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "products.json").write_text(json.dumps(products, indent=4))
        (target_dir / "categories.json").write_text(json.dumps(categories, indent=4))
        (target_dir / "retailers.json").write_text(json.dumps(retailers, indent=4))
        (target_dir / "users.json").write_text(json.dumps(users, indent=4))
        print(f"Wrote data to {target_dir}")


if __name__ == "__main__":
    main()
