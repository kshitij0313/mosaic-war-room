from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from config import EXPECTED_THEMES_BY_CATEGORY, FORMAT_HINTS, PROCESSED_DIR, RAW_DIR, THEME_KEYWORDS
from utils import compact_text, parse_theme_list, stable_unique

RAW_PATH = RAW_DIR / "raw_ads.csv"
OUT_PATH = PROCESSED_DIR / "structured_ads.csv"
BRAND_SUMMARY_PATH = PROCESSED_DIR / "brand_summary.csv"


def parse_date(value: Any) -> pd.Timestamp | pd.NaT:
    if value is None or str(value).strip() == "":
        return pd.NaT
    try:
        dt = pd.to_datetime(value, utc=True)
        if hasattr(dt, "tz_localize"):
            dt = dt.tz_localize(None)
        return dt.normalize()
    except Exception:
        return pd.NaT


def normalize_platform(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "Unknown"
    items = [x.strip().title() for x in str(value).split(",") if x.strip()]
    return ", ".join(stable_unique(items)) if items else "Unknown"


def classify_format(row: pd.Series) -> str:
    image_count = int(row.get("image_count", 0) or 0)
    video_count = int(row.get("video_count", 0) or 0)
    hint = f"{row.get('ad_creative_type', '')} {row.get('raw_display_format', '')}".lower()
    if video_count > 0 or any(token in hint for token in FORMAT_HINTS["video"]):
        return "video"
    if image_count > 1 or any(token in hint for token in FORMAT_HINTS["carousel"]):
        return "carousel"
    if image_count >= 1 or any(token in hint for token in FORMAT_HINTS["static image"]):
        return "static image"
    return "unknown"


def classify_themes(text: str) -> List[str]:
    text_l = compact_text(text).lower()
    matched: List[str] = []
    for theme, keywords in THEME_KEYWORDS.items():
        if any(keyword in text_l for keyword in keywords):
            matched.append(theme)
    if not matched:
        matched = ["other / unclassified"]
    return matched


def build_structured(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["brand"] = df["brand_name"].astype(str).str.strip()
    df["category"] = df["brand_category"].astype(str).str.strip()
    df["ad_text"] = df["ad_text"].apply(compact_text)
    df["format"] = df.apply(classify_format, axis=1)
    df["start_date"] = df["ad_start_date"].apply(parse_date)
    df["end_date"] = df.get("ad_end_date", "").apply(parse_date)
    df["platform"] = df["platform"].apply(normalize_platform)
    df["url"] = df["ad_snapshot_url"].fillna("").astype(str)
    df["theme_list"] = df["ad_text"].apply(classify_themes)
    df["primary_theme"] = df["theme_list"].apply(lambda x: x[0] if x else "other / unclassified")
    df["theme_count"] = df["theme_list"].apply(len)
    df["text_length"] = df["ad_text"].str.len()
    df["has_text"] = df["ad_text"].str.len().gt(0).map({True: "yes", False: "no"})
    today = pd.Timestamp.utcnow().tz_localize(None).normalize()
    df["ad_age_days"] = df["start_date"].apply(lambda x: None if pd.isna(x) else int((today - x).days))
    df["expected_theme_slots"] = df["category"].map(lambda c: len(EXPECTED_THEMES_BY_CATEGORY.get(c, []))).fillna(0).astype(int)
    cols = [
        "brand", "category", "ad_text", "format", "start_date", "platform", "url", "primary_theme", "theme_list",
        "theme_count", "ad_age_days", "matched_page_name", "page_id", "ad_archive_id", "raw_display_format",
        "text_length", "has_text", "cta_text", "link_caption", "page_verification", "page_likes", "competitor_why",
        "brand_query", "image_count", "video_count", "expected_theme_slots"
    ]
    for col in cols:
        if col not in df.columns:
            df[col] = None
    out = df[cols].drop_duplicates(subset=["brand", "ad_archive_id", "url", "ad_text"], keep="first")
    out = out.sort_values(["brand", "start_date"], ascending=[True, False])
    return out


def create_brand_summary(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["brand", "category", "ads", "avg_live_days", "leading_format", "leading_theme"])
    ex = df.explode("theme_list").rename(columns={"theme_list": "theme"})
    summary = df.groupby(["brand", "category"]).agg(
        ads=("brand", "size"),
        avg_live_days=("ad_age_days", "mean"),
        leading_format=("format", lambda s: s.mode().iloc[0] if not s.mode().empty else "unknown"),
    ).reset_index()
    lead_theme = ex.groupby("brand")["theme"].agg(lambda s: s.mode().iloc[0] if not s.mode().empty else "other / unclassified").reset_index(name="leading_theme")
    summary = summary.merge(lead_theme, on="brand", how="left")
    summary["avg_live_days"] = summary["avg_live_days"].round(1)
    return summary.sort_values(["category", "ads"], ascending=[True, False])


def main() -> None:
    if not RAW_PATH.exists():
        raise FileNotFoundError(f"{RAW_PATH} not found. Run scraper.py first.")
    df = pd.read_csv(RAW_PATH)
    if df.empty:
        raise ValueError("raw_ads.csv is empty. Rerun scraper.py after your SearchAPI key is working.")
    structured = build_structured(df)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    structured.to_csv(OUT_PATH, index=False)
    brand_summary = create_brand_summary(structured)
    brand_summary.to_csv(BRAND_SUMMARY_PATH, index=False)
    print(f"Saved -> {OUT_PATH}")
    print(f"Saved -> {BRAND_SUMMARY_PATH}")
    print(f"Rows: {len(structured)}")


if __name__ == "__main__":
    main()
