from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import yaml

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
COMPETITOR_FILE = BASE_DIR / "competitors.yaml"

MOSAIC_PORTFOLIO = {
    "Man Matters": "Men's wellness: hair, performance, skin, hygiene, and science-backed confidence.",
    "Be Bodywise": "Women's wellness: hair, skin, nutrition, body care, and hormonal-health language.",
    "Little Joys": "Kids wellness: parent-trust, emotional reassurance, and nutrition-led routines.",
    "Root Labs": "Ayurveda-led unisex wellness brand in Mosaic's portfolio.",
}

EXPECTED_THEMES_BY_CATEGORY = {
    "Men's wellness": ["hair loss", "testosterone", "doctor authority", "ugc testimonial", "discount / offer", "sleep / stress"],
    "Women's wellness": ["hormonal health", "acne treatment", "doctor authority", "emotional storytelling", "discount / offer"],
    "Baby care": ["parenting pain point", "doctor authority", "emotional storytelling", "ugc testimonial", "discount / offer"],
}

THEME_KEYWORDS = {
    "hair loss": [
        "hair loss", "hairfall", "hair fall", "bald", "balding", "thinning", "regrow", "regrowth", "minoxidil", "alopecia", "dht"
    ],
    "hormonal health": [
        "pcos", "pcod", "period", "hormonal", "hormone", "cycle", "menstrual", "ovulation", "fertility", "bloating"
    ],
    "testosterone": [
        "testosterone", "low t", "stamina", "performance", "vitality", "energy levels", "men's health", "mens health", "drive"
    ],
    "acne treatment": [
        "acne", "pimple", "breakout", "blemish", "clear skin", "oil control", "spots"
    ],
    "doctor authority": [
        "doctor", "dermatologist", "gynaecologist", "gynecologist", "clinically proven", "science-backed", "lab tested", "expert", "recommended by doctors"
    ],
    "ugc testimonial": [
        "review", "testimonial", "my experience", "before and after", "transformation", "worked for me", "real results", "customer story"
    ],
    "discount / offer": [
        "off", "% off", "discount", "sale", "offer", "limited time", "buy 1 get 1", "bogo", "save", "coupon", "deal"
    ],
    "parenting pain point": [
        "new mom", "newborn", "diaper rash", "sensitive skin", "fussy", "picky eater", "teething", "immunity", "colic", "baby"
    ],
    "emotional storytelling": [
        "confidence", "journey", "motherhood", "feel like yourself", "self-care", "feel seen", "feel heard", "story", "because you deserve"
    ],
    "sleep / stress": [
        "sleep", "stress", "tired", "fatigue", "rest", "calm", "recovery", "anxiety"
    ],
}

FORMAT_HINTS = {
    "video": ["video", "reel", "story_video", "motion", "shorts"],
    "carousel": ["carousel", "multi", "collection", "catalog"],
    "static image": ["image", "photo", "single image", "static"],
}


def load_competitors() -> List[Dict[str, Any]]:
    with COMPETITOR_FILE.open("r", encoding="utf-8") as f:
        payload = yaml.safe_load(f) or {}
    return payload.get("brands", [])
