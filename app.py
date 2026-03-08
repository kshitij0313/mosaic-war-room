
from __future__ import annotations

import ast
import base64
import difflib
import json
import os
import random
import re
import time
from pathlib import Path
from typing import Dict, List

import altair as alt
import pandas as pd
import streamlit as st
import yaml

from config import MOSAIC_PORTFOLIO

DATA_PATH = "data/processed/structured_ads.csv"
INSIGHTS_PATH = "data/processed/insights_summary.json"
TOP_ADS_PATH = "data/processed/top_ads.csv"
BRIEF_PATH = "data/processed/weekly_brief.txt"
COMPETITORS_PATH = Path(__file__).resolve().parent / "competitors.yaml"
ASSETS_DIR = Path(__file__).resolve().parent / "assets"
TEAM_BANNER_PATH = ASSETS_DIR / "mosaic_team_banner.png"

st.set_page_config(
    page_title="Competitor Ad War Room",
    page_icon="⚔️",
    layout="wide",
    initial_sidebar_state="expanded",
)

HERO_LINES = [
    "Mosaic can see who is repeating, who is surviving, and where the next angle is still open.",
    "Less ad dump. More signal.",
    "The point is not who is running ads. The point is what they keep paying to repeat.",
]

THEME_TAUNTS = {
    "discount / offer": "Price-led messaging is crowded. Proof and clearer value stories matter more here.",
    "doctor authority": "Authority still works, but a lot of brands are using the same clinic-coded language.",
    "ugc testimonial": "UGC is common. Distinctive UGC is not.",
    "hair loss": "Hair-loss creative still earns attention, but the scripts are beginning to look interchangeable.",
    "hormonal health": "Hormonal-health messaging is active, credible, and often repetitive.",
    "sleep / stress": "Sleep and stress still look less crowded than the category's default playbook.",
    "parenting pain point": "Parents are being sold reassurance more than education.",
    "emotional storytelling": "Warmth is easy to write and harder to make memorable.",
}

AWARD_TITLES = {
    "aggressive": "Most Aggressive Advertiser",
    "survivor": "Best Survival Rate",
    "video": "Format Leader",
    "repetitive": "Most Repetitive Messaging",
    "whitespace": "Whitespace Hunter",
}


GLOSSARY_TERMS = {
    "War Score": "A blended score that rewards ad volume, format diversity, staying power, and a less repetitive message mix.",
    "Opportunity Meter": "A whitespace score. Higher means more expected themes still look lightly used or missing.",
    "Message Repetition": "How concentrated a brand is in one dominant theme. Higher repetition can mean stronger recall but less distinctiveness.",
    "Avg. Live Days": "The average number of days active ads have remained live in the current filtered view.",
    "Tracked Ads": "The active competitor ads currently visible after your filters are applied.",
    "Brands in Play": "The number of unique competitor brands in the current view.",
    "Creative Mix": "The split of video, carousel, and static image ads by category or brand.",
    "Whitespace": "A message or format lane that competitors are not using heavily yet.",
    "Longest-running ads": "The ads that have stayed live the longest. They are a useful proxy for what brands keep funding.",
    "Dominant theme": "The most frequently repeated message angle in the current view.",
    "Battlefield": "The part of the app focused on who is advertising hardest, longest, and most repeatedly.",
    "Explorer": "The detailed ad table where you can inspect links, themes, start dates, and platforms.",
}

SUGGESTED_QUESTIONS = [
    "What should Mosaic test next week?",
    "Which competitor has the highest War Score?",
    "What themes are getting crowded?",
    "What is the cleanest whitespace opportunity?",
    "How many brands and ads are in view?",
    "Which category looks busiest right now?",
]


def parse_theme_list(value):
    if isinstance(value, list):
        return [str(x) for x in value if str(x).strip()]
    if pd.isna(value):
        return []
    text = str(value).strip()
    if not text:
        return []
    try:
        parsed = ast.literal_eval(text)
        if isinstance(parsed, list):
            return [str(x) for x in parsed if str(x).strip()]
    except Exception:
        pass
    return [text]


@st.cache_data
def load_ads() -> pd.DataFrame:
    if not os.path.exists(DATA_PATH):
        return pd.DataFrame()
    df = pd.read_csv(DATA_PATH)
    if "start_date" in df.columns:
        df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
    for col in ["ad_age_days", "theme_count", "text_length"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    df["theme_list"] = df.get("theme_list", "").apply(parse_theme_list)
    df["primary_theme"] = df.get("primary_theme", "other / unclassified").fillna("other / unclassified")
    df["format"] = df.get("format", "unknown").fillna("unknown").astype(str).str.lower()
    df["brand"] = df.get("brand", "Unknown").fillna("Unknown").astype(str)
    df["category"] = df.get("category", "Other").fillna("Other").astype(str)
    df["platform"] = df.get("platform", "Unknown").fillna("Unknown").astype(str)
    df["url"] = df.get("url", "").fillna("").astype(str)
    df["ad_text"] = df.get("ad_text", "").fillna("").astype(str)
    return df


@st.cache_data
def load_json(path: str):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def load_text(path: str) -> str:
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


@st.cache_data
def load_top_ads() -> pd.DataFrame:
    if not os.path.exists(TOP_ADS_PATH):
        return pd.DataFrame()
    df = pd.read_csv(TOP_ADS_PATH)
    for col in ["ad_age_days", "performance_proxy_score"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


@st.cache_data
def load_competitors() -> List[dict]:
    if not COMPETITORS_PATH.exists():
        return []
    with open(COMPETITORS_PATH, "r", encoding="utf-8") as f:
        payload = yaml.safe_load(f) or {}
    return payload.get("brands", [])


def apply_custom_css():
    st.markdown(
        """
        <style>
        .stApp {background: radial-gradient(circle at top left, rgba(66, 57, 161, 0.16), transparent 25%), #07101d;}
        .block-container {padding-top: 1rem; padding-bottom: 2rem; max-width: 1420px;}
        h1, h2, h3 {letter-spacing: -0.03em;}
        .hero {
            background: linear-gradient(135deg, rgba(64,49,152,0.88), rgba(5,58,86,0.84));
            border: 1px solid rgba(182, 179, 255, 0.20);
            border-radius: 28px;
            padding: 28px 30px 22px 30px;
            box-shadow: 0 18px 60px rgba(0,0,0,0.22);
            margin-bottom: 18px;
        }
        .eyebrow {font-size: 0.82rem; color: #b7c3ff; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em;}
        .hero-title {font-size: 3rem; font-weight: 800; line-height: 1.02; margin-top: 8px; margin-bottom: 6px;}
        .hero-sub {font-size: 1.05rem; color: #d4dcff; max-width: 920px; margin-top: 6px;}
        .chip-row {display:flex; gap:10px; flex-wrap:wrap; margin-top:14px;}
        .chip {background: rgba(163, 177, 255, 0.12); border: 1px solid rgba(163, 177, 255, 0.18); padding: 8px 12px; border-radius: 999px; font-size: 0.84rem;}
        .section-label {font-size:0.84rem; text-transform: uppercase; letter-spacing: 0.08em; color:#9fb1ff; margin-bottom: 6px; font-weight:700;}
        .glass-card {
            background: linear-gradient(180deg, rgba(18,24,40,0.96), rgba(12,18,30,0.96));
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 24px;
            padding: 18px 18px 14px 18px;
            box-shadow: 0 14px 40px rgba(0,0,0,0.16);
            height: 100%;
        }
        .metric-value {font-size: 2.25rem; font-weight: 800; line-height:1; margin-top:8px;}
        .metric-note {font-size: 0.92rem; color: #9eadd8; margin-top: 8px;}
        .battle-card {padding:16px 18px; border-radius:20px; border:1px solid rgba(255,255,255,0.08); background: rgba(14,22,37,0.95); margin-bottom:12px;}
        .battle-kicker {display:inline-block; padding:4px 9px; border-radius:999px; background: rgba(120,102,255,0.14); color:#d1c8ff; font-size:0.76rem; font-weight:700; margin-bottom:8px;}
        .battle-title {font-size:1.18rem; font-weight:800; margin-bottom:6px;}
        .battle-copy {color:#c2cbe3; font-size:0.98rem; line-height:1.5;}
        .award {border-radius:18px; padding:16px; border:1px solid rgba(255,255,255,0.08); background: linear-gradient(180deg, rgba(16,24,39,1), rgba(13,19,31,1));}
        .award h4 {margin: 0 0 6px 0; font-size: 1rem;}
        .award .winner {font-size: 1.3rem; font-weight: 800;}
        .award .reason {color:#b6c2e6; font-size:0.93rem;}
        .stTabs [data-baseweb="tab-list"] {gap: 10px;}
        .stTabs [data-baseweb="tab"] {height: 46px; border-radius: 999px; padding-left: 18px; padding-right: 18px; background: rgba(255,255,255,0.03);}
        .stTabs [aria-selected="true"] {background: linear-gradient(135deg, rgba(100,89,255,0.25), rgba(67,191,255,0.18));}
        .sidebar-copy {font-size: 0.9rem; color: #b9c2dd; line-height: 1.5;}
        .small-muted {font-size:.86rem; color:#97a5cf;}
        .mosaic-banner {
            background: linear-gradient(135deg, rgba(9,18,33,.98), rgba(14,31,55,.96));
            border:1px solid rgba(168, 194, 255, .14);
            border-radius: 26px;
            overflow:hidden;
            box-shadow: 0 16px 48px rgba(0,0,0,.18);
            margin-bottom: 16px;
        }
        .mosaic-banner-grid {display:grid; grid-template-columns: 1.15fr .85fr; align-items:stretch; gap: 0;}
        .mosaic-copy {padding: 26px 28px 24px 28px;}
        .mosaic-kicker {font-size: .82rem; text-transform: uppercase; letter-spacing: .12em; color:#9fd8ff; font-weight:700;}
        .mosaic-headline {font-size: 2.05rem; line-height: 1.04; font-weight: 800; margin-top: 10px; max-width: 760px;}
        .mosaic-sub {font-size: 1rem; color:#c5d1ee; max-width: 720px; margin-top: 10px;}
        .mosaic-pill-row {display:flex; gap:10px; flex-wrap:wrap; margin-top: 16px;}
        .mosaic-pill {padding: 8px 12px; border-radius: 999px; background: rgba(136, 163, 255, .10); border: 1px solid rgba(136, 163, 255, .18); color:#e7ebff; font-size: .83rem; font-weight:600;}
        .mosaic-image {min-height: 100%; background-size: cover; background-position: center; position: relative;}
        .mosaic-image::after {content: ''; position:absolute; inset:0; background: linear-gradient(90deg, rgba(9,18,33,0.05), rgba(9,18,33,0.18));}
        .know-box {border-radius: 18px; border:1px solid rgba(255,255,255,.08); background: rgba(10,17,29,.95); padding: 14px 16px;}
        .know-kicker {font-size:.78rem; letter-spacing:.08em; text-transform:uppercase; color:#8ec9ff; font-weight:700; margin-bottom:8px;}
        .brief-box {white-space: pre-wrap; line-height: 1.58; color:#dce4ff; background: rgba(12,18,30,.92); border:1px solid rgba(255,255,255,.08); border-radius:20px; padding:18px;}
        .brief-grid {display:grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap:14px; margin-top:10px;}
        .brief-card {background: linear-gradient(180deg, rgba(14,20,34,.96), rgba(10,16,28,.96)); border:1px solid rgba(255,255,255,.08); border-radius:20px; padding:18px;}
        .brief-title {font-size:1.02rem; font-weight:800; margin-bottom:10px;}
        .brief-item {display:flex; gap:10px; align-items:flex-start; color:#d9e2ff; line-height:1.55; margin-bottom:10px;}
        .brief-num {min-width:26px; height:26px; display:flex; align-items:center; justify-content:center; border-radius:999px; background: rgba(100,89,255,.18); border:1px solid rgba(255,255,255,.08); font-size:.8rem; font-weight:800; color:#eef2ff;}
        .brief-lead {font-size:.92rem; color:#9fb1dd; margin-bottom:10px;}
        .glossary-grid {display:grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap:10px; margin-top:6px;}
        .glossary-item {padding:12px 14px; border-radius:16px; background: rgba(12,18,30,.92); border:1px solid rgba(255,255,255,.08);}
        .glossary-term {font-size:.92rem; font-weight:800; margin-bottom:6px;}
        .glossary-def {font-size:.9rem; color:#c2cbe3; line-height:1.5;}
        @media (max-width: 980px) {.brief-grid, .glossary-grid {grid-template-columns: 1fr;}}
        .rain-wrap {position:fixed; inset:0; overflow:hidden; pointer-events:none; z-index:9999;}
        .rain-token {position:fixed; top:-40px; color: rgba(255,255,255,.86); background: rgba(100,89,255,.18); border:1px solid rgba(255,255,255,.18); border-radius:999px; padding:6px 10px; font-size:.82rem; font-weight:700; backdrop-filter: blur(8px); animation-name: brandRain; animation-timing-function: linear; animation-iteration-count: 1;}
        @keyframes brandRain {0% {transform: translateY(-30px) rotate(0deg); opacity:0;} 12% {opacity:1;} 100% {transform: translateY(120vh) rotate(9deg); opacity:0;}}
        @media (max-width: 980px) {.mosaic-banner-grid {grid-template-columns: 1fr;} .mosaic-image {min-height: 260px;}}
        </style>
        """,
        unsafe_allow_html=True,
    )


def image_to_data_uri(path: Path) -> str:
    if not path.exists():
        return ""
    ext = path.suffix.lower().lstrip(".") or "png"
    data = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:image/{ext};base64,{data}"


def render_mosaic_banner():
    image_uri = image_to_data_uri(TEAM_BANNER_PATH)
    image_style = f"background-image:url('{image_uri}');" if image_uri else "background: linear-gradient(135deg, rgba(62,76,143,.5), rgba(17,77,109,.5));"
    brand_pills = "".join([f"<span class='mosaic-pill'>{brand}</span>" for brand in MOSAIC_PORTFOLIO.keys()])
    st.markdown(
        f"""
        <div class='mosaic-banner'>
            <div class='mosaic-banner-grid'>
                <div class='mosaic-copy'>
                    <div class='mosaic-kicker'>Mosaic Wellness portfolio</div>
                    <div class='mosaic-headline'>One command center for Man Matters, Be Bodywise, Little Joys, and Root Labs.</div>
                    <div class='mosaic-sub'>Track who is scaling, who is repeating themselves, and where Mosaic can move with a sharper angle.</div>
                    <div class='mosaic-pill-row'>{brand_pills}</div>
                </div>
                <div class='mosaic-image' style="{image_style}"></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def trigger_brand_rain():
    tokens = ["Man Matters", "Be Bodywise", "Little Joys", "Root Labs"] * 4
    random.shuffle(tokens)
    chips = []
    for idx, token in enumerate(tokens):
        left = random.randint(3, 94)
        dur = round(random.uniform(2.8, 5.4), 2)
        delay = round(random.uniform(0.0, 1.2), 2)
        chips.append(
            f"<span class='rain-token' style='left:{left}%; animation-duration:{dur}s; animation-delay:{delay}s'>{token}</span>"
        )
    ph = st.empty()
    ph.markdown(f"<div class='rain-wrap'>{''.join(chips)}</div>", unsafe_allow_html=True)
    time.sleep(2.6)
    ph.empty()


def top_line(df: pd.DataFrame) -> str:
    if df.empty:
        return HERO_LINES[1]
    fmt = df[~df["format"].eq("unknown")]["format"].mode()
    theme = df["primary_theme"].mode()
    if not fmt.empty and not theme.empty:
        return f"{fmt.iloc[0].title()} is leading the market, while '{theme.iloc[0]}' keeps showing up across competitors."
    return HERO_LINES[0]


def metric_card(label: str, value: str, note: str = ""):
    st.markdown(
        f"""
        <div class='glass-card'>
            <div class='section-label'>{label}</div>
            <div class='metric-value'>{value}</div>
            <div class='metric-note'>{note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def award_card(title: str, winner: str, reason: str):
    st.markdown(
        f"""
        <div class='award'>
            <h4>{title}</h4>
            <div class='winner'>{winner}</div>
            <div class='reason'>{reason}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def explode_themes(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["theme_list"] = out["theme_list"].apply(lambda x: x if x else ["other / unclassified"])
    out = out.explode("theme_list").rename(columns={"theme_list": "theme"})
    return out


def compute_brand_scores(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["brand", "war_score", "activity", "diversity", "survival", "repetition", "opportunity"])
    ex = explode_themes(df)
    g = df.groupby("brand")
    fmt_div = g["format"].nunique()
    activity = g.size()
    survival = g["ad_age_days"].mean().fillna(0)
    theme_entropy = ex.groupby("brand")["theme"].nunique()
    primary_share = ex.groupby(["brand", "theme"]).size().groupby(level=0).max() / ex.groupby("brand").size()
    repetition = (primary_share * 100).fillna(0)
    opportunity = (100 - repetition).clip(lower=0)

    score_df = pd.DataFrame({
        "brand": activity.index,
        "activity": activity.values,
        "diversity": fmt_div.reindex(activity.index).fillna(1).values,
        "survival": survival.reindex(activity.index).values,
        "theme_diversity": theme_entropy.reindex(activity.index).fillna(1).values,
        "repetition": repetition.reindex(activity.index).fillna(0).values,
        "opportunity": opportunity.reindex(activity.index).fillna(0).values,
    })

    def norm(s: pd.Series):
        if s.max() == s.min():
            return pd.Series([50] * len(s), index=s.index)
        return (s - s.min()) / (s.max() - s.min()) * 100

    score_df["war_score"] = (
        0.30 * norm(score_df["activity"]) +
        0.25 * norm(score_df["survival"]) +
        0.20 * norm(score_df["diversity"]) +
        0.15 * norm(score_df["theme_diversity"]) +
        0.10 * (100 - score_df["repetition"]).clip(lower=0)
    ).round(1)
    return score_df.sort_values("war_score", ascending=False)


def opportunity_meter(df: pd.DataFrame) -> tuple[float, List[str]]:
    expected = {
        "Men's wellness": ["hair loss", "testosterone", "doctor authority", "sleep / stress", "ugc testimonial"],
        "Women's wellness": ["hormonal health", "acne treatment", "doctor authority", "emotional storytelling"],
        "Baby care": ["parenting pain point", "doctor authority", "emotional storytelling", "ugc testimonial"],
    }
    ex = explode_themes(df)
    misses = []
    total = 0
    missing = 0
    for category, themes in expected.items():
        cat_themes = set(ex[ex["category"] == category]["theme"].astype(str).str.lower())
        for t in themes:
            total += 1
            if t.lower() not in cat_themes:
                missing += 1
                misses.append(f"{category}: '{t}' is still lightly owned or missing.")
    score = round((missing / total) * 100, 1) if total else 0.0
    return score, misses[:8]


def create_action_queue(df: pd.DataFrame, score_df: pd.DataFrame) -> List[dict]:
    ex = explode_themes(df)
    actions = []
    if not ex.empty:
        theme_counts = ex["theme"].value_counts()
        if theme_counts.get("discount / offer", 0) >= max(3, len(ex) * 0.08):
            actions.append({
                "priority": "P1",
                "title": "Move beyond discount-first creative",
                "copy": "Offer-led messaging is visible across the category. Mosaic can stand out by making the value story sharper than the price cue."
            })
        if theme_counts.get("doctor authority", 0) < max(2, len(ex) * 0.04):
            actions.append({
                "priority": "P1",
                "title": "Use authority-led explainers more deliberately",
                "copy": "Expert-led creative still looks underused in this view. There is room for dermatologist, doctor, or nutrition-backed ads that feel specific and credible."
            })
        if theme_counts.get("sleep / stress", 0) <= 1:
            actions.append({
                "priority": "P2",
                "title": "Test the sleep / stress angle",
                "copy": "Competitors are still clustering around the obvious benefit claims. Sleep and stress remain a cleaner wedge for wellness adjacencies."
            })
    if not score_df.empty:
        leader = score_df.iloc[0]
        actions.append({
            "priority": "P2",
            "title": f"Reverse-engineer {leader['brand']}",
            "copy": f"This brand currently leads the War Score. Study its format mix, message concentration, and longest-running ads before your next planning cycle."
        })
    return actions[:4]


def build_theme_chart(df: pd.DataFrame):
    ex = explode_themes(df)
    chart_df = ex[ex["theme"].ne("other / unclassified")].groupby("theme").size().reset_index(name="count").sort_values("count", ascending=False).head(8)
    if chart_df.empty:
        return None
    return alt.Chart(chart_df).mark_bar(cornerRadiusTopRight=6, cornerRadiusBottomRight=6).encode(
        x=alt.X("count:Q", title="Mentions"),
        y=alt.Y("theme:N", sort="-x", title=None),
        tooltip=["theme", "count"],
    )


def build_format_chart(df: pd.DataFrame):
    chart_df = df[df["format"].ne("unknown")].groupby(["category", "format"]).size().reset_index(name="count")
    if chart_df.empty:
        return None
    return alt.Chart(chart_df).mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6).encode(
        x=alt.X("category:N", title=None, axis=alt.Axis(labelAngle=0, labelLimit=180)),
        xOffset=alt.XOffset("format:N"),
        y=alt.Y("count:Q", title="Ads"),
        color=alt.Color("format:N", title="Format"),
        tooltip=["category", "format", "count"],
    ).properties(height=320)


def filter_ads(df: pd.DataFrame):
    st.sidebar.markdown("## Control Tower")
    st.sidebar.markdown("<div class='sidebar-copy'>Filter by the levers that matter: brand, category, format, theme, and recency.</div>", unsafe_allow_html=True)

    brand_options = sorted(df["brand"].dropna().unique().tolist())
    category_options = sorted(df["category"].dropna().unique().tolist())
    format_options = [x for x in sorted(df["format"].dropna().unique().tolist()) if x != "unknown"]
    theme_options = sorted({t for lst in df["theme_list"].tolist() for t in lst if t and t != "other / unclassified"})

    selected_brands = st.sidebar.multiselect("Brand", brand_options, default=brand_options)
    selected_categories = st.sidebar.multiselect("Category", category_options, default=category_options)
    selected_formats = st.sidebar.multiselect("Format", format_options, default=format_options)
    selected_themes = st.sidebar.multiselect("Theme", theme_options, default=theme_options)
    recency = st.sidebar.selectbox("Recency", ["All dates", "Last 30 days", "Last 60 days", "Last 90 days"], index=0)

    date_vals = df["start_date"].dropna()
    date_range = None
    if not date_vals.empty:
        min_d, max_d = date_vals.min().date(), date_vals.max().date()
        date_range = st.sidebar.date_input("Date range", value=(min_d, max_d), min_value=min_d, max_value=max_d)

    if st.sidebar.button("Drop the Mosaic confetti"):
        st.session_state["trigger_brand_rain"] = True

    out = df.copy()
    if selected_brands:
        out = out[out["brand"].isin(selected_brands)]
    if selected_categories:
        out = out[out["category"].isin(selected_categories)]
    if selected_formats:
        out = out[out["format"].isin(selected_formats)]
    if selected_themes:
        out = out[out["theme_list"].apply(lambda lst: any(t in lst for t in selected_themes))]
    if date_range and isinstance(date_range, tuple) and len(date_range) == 2:
        start, end = date_range
        out = out[(out["start_date"].dt.date >= start) & (out["start_date"].dt.date <= end)]
    if recency != "All dates" and not out["start_date"].dropna().empty:
        days = int(recency.split()[1])
        cutoff = pd.Timestamp.utcnow().tz_localize(None).normalize() - pd.Timedelta(days=days)
        out = out[out["start_date"] >= cutoff]
    return out


def render_battle_card(title: str, copy: str, kicker: str = "Signal"):
    st.markdown(
        f"""
        <div class='battle-card'>
            <div class='battle-kicker'>{kicker}</div>
            <div class='battle-title'>{title}</div>
            <div class='battle-copy'>{copy}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def parse_weekly_brief(brief_text: str) -> Dict[str, List[str]]:
    sections: Dict[str, List[str]] = {}
    current = None
    for raw_line in (brief_text or '').splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.lower().startswith('competitor ad war room'):
            continue
        if re.match(r"^\d+\s+(creative trends|winning formats|strategic insights|opportunity gaps)$", line.lower()):
            current = re.sub(r"^\d+\s+", "", line).strip()
            sections[current] = []
            continue
        cleaned = re.sub(r"^\d+\.\s*", "", line).strip()
        if current and cleaned:
            sections[current].append(cleaned)
    return sections


def render_weekly_brief(brief_text: str):
    sections = parse_weekly_brief(brief_text)
    if not sections:
        st.markdown("<div class='brief-box'>No weekly brief file found yet. Run insights.py to generate one.</div>", unsafe_allow_html=True)
        return

    labels = [
        ("Creative Trends", "What is rising, repeating, or settling into the category"),
        ("Winning Formats", "The formats that look strongest on survival and repeat usage"),
        ("Strategic Insights", "What the numbers suggest Mosaic should actually care about"),
        ("Opportunity Gaps", "The cleanest gaps competitors still have not closed"),
    ]
    html_cards = []
    for title, subtitle in labels:
        items = sections.get(title, [])
        items_html = ''.join([f"<div class='brief-item'><div class='brief-num'>{i}</div><div>{item}</div></div>" for i, item in enumerate(items, start=1)]) or "<div class='small-muted'>No lines generated for this section yet.</div>"
        html_cards.append(f"<div class='brief-card'><div class='brief-title'>{title}</div><div class='brief-lead'>{subtitle}</div>{items_html}</div>")
    st.markdown(f"<div class='brief-grid'>{''.join(html_cards)}</div>", unsafe_allow_html=True)


def build_data_snapshot(df: pd.DataFrame, score_df: pd.DataFrame, misses: List[str]) -> Dict[str, object]:
    ex = explode_themes(df) if not df.empty else pd.DataFrame()
    known = df[df['format'] != 'unknown'] if not df.empty else pd.DataFrame()
    snapshot: Dict[str, object] = {}
    snapshot['brand_count'] = int(df['brand'].nunique()) if not df.empty else 0
    snapshot['total_ads'] = int(len(df))
    snapshot['avg_live_days'] = round(float(df['ad_age_days'].mean()), 1) if 'ad_age_days' in df.columns and len(df) else 0
    snapshot['top_brand'] = score_df.iloc[0]['brand'] if not score_df.empty else None
    snapshot['top_war_score'] = round(float(score_df.iloc[0]['war_score']), 1) if not score_df.empty else None
    snapshot['top_format'] = known['format'].mode().iloc[0] if not known.empty else None
    snapshot['top_category'] = df['category'].mode().iloc[0] if not df.empty else None
    snapshot['top_theme'] = ex[ex['theme'] != 'other / unclassified']['theme'].mode().iloc[0] if not ex[ex['theme'] != 'other / unclassified'].empty else None
    snapshot['format_counts'] = known['format'].value_counts().to_dict() if not known.empty else {}
    snapshot['theme_counts'] = ex[ex['theme'] != 'other / unclassified']['theme'].value_counts().to_dict() if not ex.empty else {}
    snapshot['category_counts'] = df['category'].value_counts().to_dict() if not df.empty else {}
    snapshot['misses'] = misses[:5]
    if not df.empty:
        longest = df.groupby('brand')['ad_age_days'].mean().sort_values(ascending=False)
        if not longest.empty:
            snapshot['longest_brand'] = longest.index[0]
            snapshot['longest_days'] = round(float(longest.iloc[0]), 1)
    return snapshot


def render_glossary():
    items = ''.join([f"<div class='glossary-item'><div class='glossary-term'>{term}</div><div class='glossary-def'>{desc}</div></div>" for term, desc in GLOSSARY_TERMS.items()])
    with st.expander('📚 Glossary', expanded=False):
        st.markdown(f"<div class='glossary-grid'>{items}</div>", unsafe_allow_html=True)


def concise_summary(df: pd.DataFrame) -> str:
    if df.empty:
        return "No live data in view yet. Run the pipeline and come back."
    ex = explode_themes(df)
    top_theme = ex["theme"].mode().iloc[0] if not ex.empty else "the default category script"
    top_fmt = df[df["format"].ne("unknown")]["format"].mode().iloc[0] if not df[df["format"].ne("unknown")].empty else "creative"
    return THEME_TAUNTS.get(top_theme, f"{top_fmt.title()} is carrying most of the load, and the message mix is becoming easier to predict.")


def assistant_answer(question: str, df: pd.DataFrame, insights: Dict, score_df: pd.DataFrame, misses: List[str], actions: List[Dict]) -> str:
    query = (question or '').strip()
    if not query:
        return "Type a competitor name to see its summary in the current filtered view."

    if df.empty:
        return "No live competitor data is loaded yet. Run the pipeline first."

    brands = sorted(df["brand"].dropna().unique().tolist())
    brand_map = {brand.lower(): brand for brand in brands}
    q = query.lower()

    matched_brand = None
    if q in brand_map:
        matched_brand = brand_map[q]
    else:
        contains_matches = [brand for brand in brands if q in brand.lower() or brand.lower() in q]
        if contains_matches:
            matched_brand = contains_matches[0]
        else:
            close = difflib.get_close_matches(query, brands, n=1, cutoff=0.6)
            if close:
                matched_brand = close[0]

    if not matched_brand:
        suggestions = difflib.get_close_matches(query, brands, n=4, cutoff=0.3)
        if suggestions:
            return "I couldn't match that competitor exactly. Try one of these names: " + ", ".join(suggestions)
        return "I couldn't find that competitor in the current filtered view. Type one of the visible competitor names exactly."

    brand_df = df[df["brand"] == matched_brand].copy()
    brand_ex = explode_themes(brand_df) if not brand_df.empty else pd.DataFrame()
    war_row = score_df[score_df["brand"] == matched_brand]

    ad_count = len(brand_df)
    category = brand_df["category"].mode().iloc[0] if not brand_df.empty else "Unknown"
    avg_days = round(float(brand_df["ad_age_days"].mean()), 1) if not brand_df.empty else 0
    longest_days = int(brand_df["ad_age_days"].max()) if not brand_df.empty else 0
    platform_counts = brand_df["platform"].value_counts()
    format_counts = brand_df[brand_df["format"] != "unknown"]["format"].value_counts()
    theme_counts = brand_ex[brand_ex["theme"] != "other / unclassified"]["theme"].value_counts() if not brand_ex.empty else pd.Series(dtype=int)

    top_format = format_counts.index[0] if not format_counts.empty else "No classified format yet"
    top_format_count = int(format_counts.iloc[0]) if not format_counts.empty else 0
    top_theme = theme_counts.index[0] if not theme_counts.empty else "No classified theme yet"
    top_theme_count = int(theme_counts.iloc[0]) if not theme_counts.empty else 0
    war_score_text = f"{float(war_row.iloc[0]['war_score']):.1f}" if not war_row.empty else "N/A"
    platforms = ", ".join(platform_counts.index[:3].tolist()) if not platform_counts.empty else "Unknown"

    interpretation_parts = []
    if war_score_text != "N/A":
        try:
            war_score_value = float(war_score_text)
            if war_score_value >= 70:
                interpretation_parts.append("This competitor looks strong in the current view, with a healthy mix of activity and staying power.")
            elif war_score_value >= 45:
                interpretation_parts.append("This competitor is active and credible, but not clearly dominating the battlefield.")
            else:
                interpretation_parts.append("This competitor is present, but it is not yet punching above the category average on the current War Score.")
        except Exception:
            pass

    if top_format_count and ad_count:
        format_share = round((top_format_count / ad_count) * 100, 1)
        interpretation_parts.append(f"{top_format.title()} is doing most of the work here, accounting for {format_share}% of this brand's visible ads.")
    if top_theme_count:
        interpretation_parts.append(f"The clearest repeated angle is '{top_theme}', which shows up {top_theme_count} time(s) in the filtered view.")

    interpretation = " ".join(interpretation_parts) if interpretation_parts else "This is a directional read based on the current filtered ads in view."

    return f"""### {matched_brand} overview
- **Category:** {category}
- **Tracked ads:** {ad_count}
- **War Score:** {war_score_text}
- **Average live days:** {avg_days}
- **Longest-running ad:** {longest_days} days
- **Leading format:** {top_format} ({top_format_count} ads)
- **Leading theme:** {top_theme} ({top_theme_count} mentions)
- **Main platforms:** {platforms}

**Interpretation:** {interpretation}"""



def render_assistant_tab(filtered: pd.DataFrame, insights: Dict, score_df: pd.DataFrame, misses: List[str], actions: List[Dict]):
    st.markdown("## Ask the War Room")
    st.markdown("<div class='small-muted'>Type a competitor name only. The War Room will return a grounded overview for that competitor from the current filtered view.</div>", unsafe_allow_html=True)

    if "warroom_chat" not in st.session_state:
        st.session_state.warroom_chat = [
            {"role": "assistant", "content": "Type a competitor name like Traya, Power Gummies, or Mother Sparsh to get a live summary."}
        ]

    for msg in st.session_state.warroom_chat:
        with st.chat_message(msg["role"]):
            if msg["role"] == "assistant":
                st.markdown(msg["content"])
            else:
                st.write(msg["content"])

    user_q = st.chat_input("Type a competitor name", key="competitor_lookup_input")
    if user_q:
        st.session_state.warroom_chat = [{"role": "assistant", "content": "Type a competitor name like Traya, Power Gummies, or Mother Sparsh to get a live summary."}]
        st.session_state.warroom_chat.append({"role": "user", "content": user_q})
        answer = assistant_answer(user_q, filtered, insights, score_df, misses, actions)
        st.session_state.warroom_chat.append({"role": "assistant", "content": answer})
        st.rerun()



def build_fun_fact(df: pd.DataFrame, score_df: pd.DataFrame, competitors: List[dict]) -> str:
    facts = []
    if competitors:
        sample = random.choice(competitors)
        facts.append(f"{sample['brand']} is in the watchlist because {sample['why']}")
    if not score_df.empty:
        leader = score_df.iloc[0]
        facts.append(f"{leader['brand']} currently leads the War Score at {leader['war_score']}")
        repeater = score_df.sort_values('repetition', ascending=False).iloc[0]
        facts.append(f"{repeater['brand']} has the highest message repetition score right now at {repeater['repetition']:.1f}%")
    if not df.empty:
        oldest = df.groupby('brand')['ad_age_days'].mean().sort_values(ascending=False)
        if not oldest.empty:
            facts.append(f"{oldest.index[0]} has the oldest average live ads in the current view at {oldest.iloc[0]:.1f} days")
        ex = explode_themes(df)
        if not ex.empty:
            top_theme = ex['theme'].value_counts().idxmax()
            facts.append(f"'{top_theme}' is the most repeated theme in the current filtered battlefield")
        categories = df['category'].value_counts()
        if not categories.empty:
            facts.append(f"{categories.index[0]} is currently the densest category in the dashboard")
    return random.choice(facts) if facts else "Refresh the page once you have live data and this section will start dropping competitor facts."


def render_rotating_fact(df: pd.DataFrame, score_df: pd.DataFrame, competitors: List[dict]):
    fun_fact = build_fun_fact(df, score_df, competitors)
    with st.expander("📘 Know your competitors", expanded=False):
        st.markdown(
            f"""
            <div class='know-box'>
                <div class='know-kicker'>Fresh fact</div>
                <div style='font-size:1.03rem; font-weight:700; margin-bottom:8px;'>One useful thing to know right now</div>
                <div style='color:#dbe4ff; line-height:1.55;'>{fun_fact}.</div>
                <div class='small-muted' style='margin-top:10px;'>Use 'Drop the Mosaic confetti' in the sidebar and this box rotates to a new competitor fact on rerun.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_competitor_cheat_sheet(df: pd.DataFrame, score_df: pd.DataFrame, competitors: List[dict]):
    render_rotating_fact(df, score_df, competitors)
    render_glossary()


def main():
    apply_custom_css()
    df = load_ads()
    insights = load_json(INSIGHTS_PATH)
    top_ads = load_top_ads()
    brief = load_text(BRIEF_PATH)
    competitors = load_competitors()

    if df.empty:
        st.error("No structured ad data found. Run scraper.py, processor.py, and insights.py first.")
        st.stop()

    filtered = filter_ads(df)
    if st.session_state.get("trigger_brand_rain"):
        trigger_brand_rain()
        st.session_state["trigger_brand_rain"] = False

    score_df = compute_brand_scores(filtered)
    opp_score, misses = opportunity_meter(filtered)
    actions = insights.get("monday_actions") or create_action_queue(filtered, score_df)

    total_ads = len(filtered)
    brands_count = filtered["brand"].nunique()
    avg_days = round(filtered["ad_age_days"].mean(), 1) if total_ads else 0
    top_format = filtered[filtered["format"].ne("unknown")]["format"].mode().iloc[0].title() if not filtered[filtered["format"].ne("unknown")].empty else "N/A"
    coverage = round((brands_count / max(df["brand"].nunique(), 10)) * 100, 1)

    if brands_count < 10:
        st.warning(f"Only {brands_count} brands are currently in scope. The assignment target is at least 10 live competitors, so keep the full scrape running until the brand count holds.")

    render_mosaic_banner()

    st.markdown(
        f"""
        <div class='hero'>
            <div class='eyebrow'>Mosaic Wellness portfolio command centre</div>
            <div class='hero-title'>Competitor Ad War Room</div>
            <div class='hero-sub'>{top_line(filtered)}</div>
            <div class='chip-row'>
                <div class='chip'>⚡ {brands_count} competitor brands live</div>
                <div class='chip'>🎯 {total_ads} tracked active ads</div>
                <div class='chip'>🧭 {filtered['category'].nunique()} categories in view</div>
                <div class='chip'>📌 {top_format} currently leads the format mix</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    render_competitor_cheat_sheet(filtered, score_df, competitors)

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        metric_card("Tracked ads", f"{total_ads}", "Live ads in the current filtered view.")
    with m2:
        metric_card("Brands in play", f"{brands_count}", "Assignment target: at least 10.")
    with m3:
        metric_card("Avg. live days", f"{avg_days}", "Longer survival is a useful performance signal.")
    with m4:
        metric_card("Opportunity Meter", f"{opp_score}", "Higher means more whitespace is still available.")

    st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)

    overview_tab, battlefield_tab, whitespace_tab, explorer_tab, ask_tab = st.tabs(["Overview", "Battlefield", "Whitespace", "Explorer", "Ask Mosaic"])

    with overview_tab:
        left, right = st.columns([1.25, 1])
        with left:
            st.markdown("## What the market is doing")
            render_battle_card("Category read", concise_summary(filtered), "Signal")
            st.markdown("### Weekly Intelligence Brief")
            brief_to_show = brief if brief else ""
            render_weekly_brief(brief_to_show)
        with right:
            st.markdown("## Monday Morning Action Queue")
            for item in actions:
                render_battle_card(item["title"], item["copy"], item["priority"])

        st.markdown("## Category coverage")
        st.progress(min(max(coverage / 100, 0.0), 1.0), text=f"Coverage: {coverage}% of the live competitor target mapped")
        st.caption("The app should comfortably hold 10+ brands before you submit. This keeps the weekly read more comparable and defensible.")

        roasts = (insights.get('category_roasts') or {})
        if roasts:
            st.markdown("## Quick category reads")
            roast_cols = st.columns(max(1, len(roasts)))
            for col, (cat, roast) in zip(roast_cols, roasts.items()):
                with col:
                    render_battle_card(cat, roast, 'Category note')

        st.markdown("## Category awards")
        a1, a2, a3 = st.columns(3)
        if not score_df.empty:
            leader = score_df.iloc[0]
            repetitive = score_df.sort_values("repetition", ascending=False).iloc[0]
            survivor = filtered.groupby("brand")["ad_age_days"].mean().sort_values(ascending=False).reset_index().iloc[0]
            with a1:
                award_card(AWARD_TITLES["aggressive"], leader["brand"], f"War Score {leader['war_score']}. Strong activity with above-average staying power.")
            with a2:
                award_card(AWARD_TITLES["repetitive"], repetitive["brand"], f"Message concentration is {repetitive['repetition']:.1f}%. Good recall, but repetition risk is real.")
            with a3:
                award_card(AWARD_TITLES["survivor"], survivor["brand"], f"Average live age: {survivor['ad_age_days']:.1f} days.")

    with battlefield_tab:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("## Creative mix by category")
            fmt_chart = build_format_chart(filtered)
            if fmt_chart is not None:
                st.altair_chart(fmt_chart.properties(height=300), use_container_width=True)
            st.caption("This view hides the 'unknown' bucket unless you are debugging input quality.")
        with c2:
            st.markdown("## Dominant message themes")
            theme_chart = build_theme_chart(filtered)
            if theme_chart is not None:
                st.altair_chart(theme_chart.properties(height=300), use_container_width=True)
            st.caption("The point is not the count alone. It is whether too many brands are beginning to sound interchangeable.")

        st.markdown("## Creative Dominance Leaderboard")
        if not score_df.empty:
            leaderboard = score_df[["brand", "war_score", "activity", "survival", "repetition", "opportunity"]].copy()
            leaderboard.columns = ["Brand", "War Score", "Ad Volume", "Avg. Live Days", "Message Repetition %", "Whitespace Potential"]
            st.dataframe(leaderboard, use_container_width=True, hide_index=True)

        st.markdown("## Longest-running ads")
        long_ads = filtered.sort_values(["ad_age_days", "start_date"], ascending=[False, False]).head(12)
        if not long_ads.empty:
            st.dataframe(
                long_ads[["brand", "category", "format", "primary_theme", "ad_age_days", "platform", "url"]],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "url": st.column_config.LinkColumn("Ad link", display_text="Open ad"),
                    "ad_age_days": st.column_config.NumberColumn("Live days", format="%.0f")
                }
            )

    with whitespace_tab:
        st.markdown("## What still looks open")
        if misses:
            for miss in misses[:5]:
                render_battle_card("Whitespace unlock", miss, "Opportunity")
        else:
            render_battle_card("Whitespace is tighter than expected", "The category is covering more than usual. You may need sharper execution rather than a new angle.", "Heads-up")

        st.markdown("## Opportunity Meter")
        st.progress(min(max(opp_score / 100, 0.0), 1.0), text=f"Opportunity Meter: {opp_score}/100")
        st.caption("Higher score = more open message territory. Lower score = the obvious lanes are already crowded.")

        st.markdown("## Mosaic strategy cues")
        lines = [
            "If everyone is selling the fix, Mosaic can own the feeling after the fix.",
            "Authority still matters, but it needs sharper proof and clearer relevance.",
            "In baby and kids, trust plus education still looks stronger than trust alone.",
            "If men’s wellness ads sound similar, format craft becomes the edge.",
        ]
        for line in lines:
            render_battle_card("A line worth testing", line, "Strategy cue")

    with explorer_tab:
        st.markdown("## Ad explorer")
        display_df = filtered.copy()
        if display_df.empty:
            st.info("No ads match the current filters.")
        else:
            display_df = display_df[(display_df["format"].ne("unknown")) | (display_df["primary_theme"].ne("other / unclassified"))]
            display_df = display_df.sort_values(["start_date", "ad_age_days"], ascending=[False, False])
            st.dataframe(
                display_df[["brand", "category", "format", "primary_theme", "start_date", "ad_age_days", "platform", "ad_text", "url"]],
                use_container_width=True,
                height=520,
                hide_index=True,
                column_config={
                    "url": st.column_config.LinkColumn("Ad link", display_text="Open ad"),
                    "start_date": st.column_config.DateColumn("Start date", format="YYYY-MM-DD"),
                    "ad_age_days": st.column_config.NumberColumn("Live days", format="%.0f")
                }
            )
            st.download_button("Download current battlefield", display_df.to_csv(index=False).encode("utf-8"), "war_room_filtered_ads.csv", "text/csv")

            if not top_ads.empty:
                st.markdown("## Likely winners")
                st.dataframe(
                    top_ads.head(12),
                    use_container_width=True,
                    hide_index=True,
                    column_config={"url": st.column_config.LinkColumn("Ad link", display_text="Open ad")},
                )

    with ask_tab:
        render_assistant_tab(filtered, insights, score_df, misses, actions)


if __name__ == "__main__":
    main()
