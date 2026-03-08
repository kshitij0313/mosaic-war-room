from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from config import EXPECTED_THEMES_BY_CATEGORY, PROCESSED_DIR
from utils import parse_theme_list, stable_unique

INPUT_PATH = PROCESSED_DIR / "structured_ads.csv"
OUTPUT_JSON = PROCESSED_DIR / "insights_summary.json"
OUTPUT_TOP_ADS = PROCESSED_DIR / "top_ads.csv"
OUTPUT_BRIEF = PROCESSED_DIR / "weekly_brief.txt"


TAUNT_BY_THEME = {
    "discount / offer": "The category is leaning on price like it forgot how persuasion works.",
    "doctor authority": "Everybody is borrowing credibility. Very few are making it memorable.",
    "ugc testimonial": "UGC is everywhere. Distinctiveness is on annual leave.",
    "hair loss": "Hair-loss creatives still get attention, but the scripts are getting suspiciously copy-paste.",
    "hormonal health": "Hormonal-health messaging is crowded and emotionally predictable.",
    "sleep / stress": "Sleep and stress still feel fresher than the category deserves.",
    "parenting pain point": "Parents are being sold reassurance more than education — still an open lane.",
    "emotional storytelling": "Everybody wants warmth. Not everybody earns it.",
}


def load_data() -> pd.DataFrame:
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"{INPUT_PATH} not found. Run processor.py first.")
    df = pd.read_csv(INPUT_PATH)
    if df.empty:
        raise ValueError("structured_ads.csv is empty.")
    df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
    df["ad_age_days"] = pd.to_numeric(df.get("ad_age_days"), errors="coerce").fillna(0)
    df["text_length"] = pd.to_numeric(df.get("text_length"), errors="coerce").fillna(0)
    df["theme_count"] = pd.to_numeric(df.get("theme_count"), errors="coerce").fillna(0)
    df["theme_list"] = df["theme_list"].apply(parse_theme_list)
    df["primary_theme"] = df["primary_theme"].fillna("other / unclassified")
    df["format"] = df["format"].fillna("unknown").astype(str).str.lower()
    return df


def explode_themes(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["theme_list"] = out["theme_list"].apply(lambda x: x or ["other / unclassified"])
    return out.explode("theme_list").rename(columns={"theme_list": "theme"})


def pct(part: float, whole: float) -> float:
    return round((part / whole) * 100, 1) if whole else 0.0


def norm(series: pd.Series) -> pd.Series:
    if series.max() == series.min():
        return pd.Series([50.0] * len(series), index=series.index)
    return (series - series.min()) / (series.max() - series.min()) * 100


def compute_brand_scores(df: pd.DataFrame) -> pd.DataFrame:
    ex = explode_themes(df)
    g = df.groupby("brand")
    activity = g.size().rename("activity")
    diversity = g["format"].nunique().rename("diversity")
    survival = g["ad_age_days"].mean().rename("survival")
    theme_diversity = ex.groupby("brand")["theme"].nunique().rename("theme_diversity")
    dominant_share = ex.groupby(["brand", "theme"]).size().groupby(level=0).max() / ex.groupby("brand").size()
    repetition = (dominant_share * 100).rename("repetition")

    score_df = pd.concat([activity, diversity, survival, theme_diversity, repetition], axis=1).fillna(0).reset_index()
    score_df["opportunity"] = (100 - score_df["repetition"]).clip(lower=0)
    score_df["war_score"] = (
        0.30 * norm(score_df["activity"]) +
        0.25 * norm(score_df["survival"]) +
        0.20 * norm(score_df["diversity"]) +
        0.15 * norm(score_df["theme_diversity"]) +
        0.10 * score_df["opportunity"]
    ).round(1)
    return score_df.sort_values("war_score", ascending=False)


def compute_top_ads(df: pd.DataFrame) -> pd.DataFrame:
    def score_row(row: pd.Series) -> float:
        age = min(float(row.get("ad_age_days", 0) or 0), 120)
        fmt = str(row.get("format", "unknown")).lower()
        theme_count = float(row.get("theme_count", 0) or 0)
        text_len = float(row.get("text_length", 0) or 0)
        score = 0.0
        score += (age / 120) * 45
        score += {"video": 20, "carousel": 14, "static image": 10}.get(fmt, 6)
        score += min(theme_count * 3, 12)
        if 40 <= text_len <= 260:
            score += 8
        elif text_len > 0:
            score += 4
        text = str(row.get("ad_text", "")).lower()
        if any(k in text for k in ["doctor", "science-backed", "dermatologist", "gynaecologist", "gynecologist"]):
            score += 4
        if any(k in text for k in ["review", "before and after", "worked for me", "real results"]):
            score += 4
        return round(min(score, 100), 1)

    out = df.copy()
    out["performance_proxy_score"] = out.apply(score_row, axis=1)
    out = out.sort_values(["performance_proxy_score", "ad_age_days"], ascending=[False, False])
    return out


def opportunity_meter(df: pd.DataFrame) -> tuple[float, List[str]]:
    ex = explode_themes(df)
    misses: List[str] = []
    total = 0
    missing = 0
    for category, expected in EXPECTED_THEMES_BY_CATEGORY.items():
        cat_themes = set(ex[ex["category"] == category]["theme"].astype(str).str.lower())
        for theme in expected:
            total += 1
            if theme.lower() not in cat_themes:
                missing += 1
                misses.append(f"{category}: nobody is really owning '{theme}'.")
    return round((missing / total) * 100, 1) if total else 0.0, misses[:8]


def creative_trends(df: pd.DataFrame, ex: pd.DataFrame) -> List[str]:
    total = len(df)
    fmt_counts = df[df["format"] != "unknown"]["format"].value_counts()
    trends: List[str] = []
    if not fmt_counts.empty:
        lead_fmt = fmt_counts.index[0]
        trends.append(f"{lead_fmt.title()} is carrying the category, accounting for {pct(fmt_counts.iloc[0], fmt_counts.sum())}% of known-format ads.")
    by_cat = df[df["format"] != "unknown"].groupby(["category", "format"]).size().reset_index(name="count")
    for category in df["category"].dropna().unique():
        sub = by_cat[by_cat["category"] == category].sort_values("count", ascending=False)
        if not sub.empty:
            lead = sub.iloc[0]
            trends.append(f"In {category}, {lead['format']} leads with {pct(lead['count'], sub['count'].sum())}% share.")
    tf = ex.groupby(["theme", "format"]).size().reset_index(name="count").sort_values("count", ascending=False)
    if not tf.empty:
        top = tf.iloc[0]
        trends.append(f"The market's favourite combo is '{top['theme']}' delivered through {top['format']} creatives.")
    return trends[:5]


def longevity_signals(df: pd.DataFrame, ex: pd.DataFrame) -> List[str]:
    total = len(df)
    long_30 = df[df["ad_age_days"] >= 30]
    long_60 = df[df["ad_age_days"] >= 60]
    signals = [
        f"{pct(len(long_30), total)}% of tracked ads have survived 30+ days; {pct(len(long_60), total)}% have made it past 60 days."
    ]
    if not long_60.empty:
        fmt = long_60[long_60["format"] != "unknown"]["format"].value_counts()
        if not fmt.empty:
            signals.append(f"Among 60+ day holdouts, {fmt.index[0]} is the keeper format — useful if you care about survival, not novelty theatre.")
        long_themes = ex[ex["url"].isin(long_60["url"])]["theme"].value_counts()
        if not long_themes.empty:
            signals.append(f"The longest-running message cluster is '{long_themes.index[0]}', which suggests budget is sticking to that story.")
    return signals[:4]


def message_saturation(ex: pd.DataFrame) -> List[str]:
    counts = ex["theme"].value_counts()
    lines = []
    for theme, count in counts.head(3).items():
        if theme == "other / unclassified":
            continue
        lines.append(f"'{theme}' is overcrowded, showing up in {pct(count, len(ex))}% of theme mentions. {TAUNT_BY_THEME.get(theme, '')}".strip())
    return lines[:4]


def format_shifts(df: pd.DataFrame) -> List[str]:
    valid = df.dropna(subset=["start_date"]).copy()
    if len(valid) < 8:
        return ["Not enough dated ads yet to call a meaningful format shift. Get more brands in before pretending we discovered a trend."]
    latest = valid["start_date"].max()
    recent = valid[valid["start_date"] >= latest - pd.Timedelta(days=21)]
    older = valid[valid["start_date"] < latest - pd.Timedelta(days=21)]
    if len(recent) < 4 or len(older) < 4:
        return ["The new-vs-old split is still too thin for a confident format-shift read."]
    recent_share = recent[recent["format"] != "unknown"]["format"].value_counts(normalize=True)
    older_share = older[older["format"] != "unknown"]["format"].value_counts(normalize=True)
    deltas = []
    for fmt in sorted(set(recent_share.index).union(set(older_share.index))):
        delta = round((recent_share.get(fmt, 0) - older_share.get(fmt, 0)) * 100, 1)
        deltas.append((fmt, delta))
    deltas.sort(key=lambda x: abs(x[1]), reverse=True)
    lines = []
    for fmt, delta in deltas[:3]:
        if abs(delta) < 6:
            continue
        direction = "up" if delta > 0 else "down"
        lines.append(f"{fmt.title()} usage is {direction} {abs(delta)} percentage points in newer ads versus older survivors.")
    return lines or ["Format mix is fairly stable. The category may be tweaking scripts more than changing containers."]


def strategic_insights(df: pd.DataFrame, ex: pd.DataFrame, score_df: pd.DataFrame) -> List[str]:
    lines = []
    if not score_df.empty:
        leader = score_df.iloc[0]
        lines.append(f"{leader['brand']} is currently the category bully with a War Score of {leader['war_score']}. Audit it before your next brief acts surprised.")
        repetitive = score_df.sort_values("repetition", ascending=False).iloc[0]
        lines.append(f"{repetitive['brand']} is leaning hardest on one message pillar, which is great for recall and dangerous for boredom.")
    sleep_count = ex[ex["theme"] == "sleep / stress"].shape[0]
    if sleep_count <= 1:
        lines.append("Sleep / stress remains strangely underused. That lane still looks cleaner than another generic science-backed monologue.")
    baby = ex[ex["category"] == "Baby care"]
    if not baby.empty and baby[baby["theme"] == "doctor authority"].shape[0] <= 1:
        lines.append("Baby care is selling reassurance more than expert education. Mosaic can take that lane without sounding cold.")
    return lines[:5]


def monday_actions(df: pd.DataFrame, ex: pd.DataFrame, score_df: pd.DataFrame, opp: float, misses: List[str]) -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    counts = ex["theme"].value_counts()
    if counts.get("discount / offer", 0) >= max(3, len(ex) * 0.08):
        items.append({
            "priority": "P1",
            "title": "Stop playing discount karaoke",
            "copy": "Too much of the market is flirting with coupons. Win with story and proof, not another sale sticker."
        })
    if counts.get("doctor authority", 0) <= 2:
        items.append({
            "priority": "P1",
            "title": "Ship an authority-led explainer",
            "copy": "The expert lane is still less crowded than it should be. Use it before the category wakes up."
        })
    if opp >= 35 and misses:
        items.append({
            "priority": "P1",
            "title": "Attack whitespace, not your own reflection",
            "copy": misses[0]
        })
    if not score_df.empty:
        leader = score_df.iloc[0]
        items.append({
            "priority": "P2",
            "title": f"Reverse-engineer {leader['brand']}",
            "copy": f"It leads on War Score today. Steal the pattern, not the headline."
        })
    return items[:4]


def category_roasts(df: pd.DataFrame, ex: pd.DataFrame) -> Dict[str, str]:
    roasts: Dict[str, str] = {}
    for category in df["category"].dropna().unique():
        cat = ex[ex["category"] == category]
        lead_theme = cat["theme"].mode().iloc[0] if not cat.empty else "other / unclassified"
        lead_fmt = df[df["category"] == category]["format"].mode().iloc[0]
        if category == "Men's wellness":
            roasts[category] = f"{lead_fmt.title()} heavy, proof hungry, and still over-indexing on '{lead_theme}'. Half clinic, half insecurity, not enough originality."
        elif category == "Women's wellness":
            roasts[category] = f"Polished and credible, but '{lead_theme}' is showing up so often the category is starting to sound harmonised by committee."
        else:
            roasts[category] = f"Warm, safe, trustworthy — and often visually interchangeable. '{lead_theme}' is doing more of the work than it should."
    return roasts


def build_weekly_brief(creative: List[str], longevity: List[str], strategy: List[str], gaps: List[str]) -> str:
    lines = ["Competitor Ad War Room — Weekly Brief", ""]
    lines.append("3 Creative Trends")
    for i, line in enumerate(creative[:3], start=1):
        lines.append(f"{i}. {line}")
    lines.append("")
    lines.append("2 Winning Formats")
    for i, line in enumerate(longevity[:2], start=1):
        lines.append(f"{i}. {line}")
    lines.append("")
    lines.append("2 Strategic Insights")
    for i, line in enumerate(strategy[:2], start=1):
        lines.append(f"{i}. {line}")
    lines.append("")
    lines.append("2 Opportunity Gaps")
    for i, line in enumerate(gaps[:2], start=1):
        lines.append(f"{i}. {line}")
    return "\n".join(lines)


def main() -> None:
    df = load_data()
    ex = explode_themes(df)
    score_df = compute_brand_scores(df)
    top_ads = compute_top_ads(df)
    opp_score, gaps = opportunity_meter(df)

    creative = creative_trends(df, ex)
    longevity = longevity_signals(df, ex)
    shifts = format_shifts(df)
    saturation = message_saturation(ex)
    strategy = strategic_insights(df, ex, score_df)
    roasts = category_roasts(df, ex)
    actions = monday_actions(df, ex, score_df, opp_score, gaps)

    overview = {
        "total_ads": int(len(df)),
        "brands_tracked": int(df["brand"].nunique()),
        "categories_tracked": int(df["category"].nunique()),
        "avg_ad_age_days": round(float(df["ad_age_days"].mean()), 1),
        "top_format": (df[df["format"] != "unknown"]["format"].mode().iloc[0] if not df[df["format"] != "unknown"].empty else "unknown"),
        "top_theme": (ex[ex["theme"] != "other / unclassified"]["theme"].mode().iloc[0] if not ex[ex["theme"] != "other / unclassified"].empty else "other / unclassified"),
        "opportunity_meter": opp_score,
    }

    awards = []
    if not score_df.empty:
        leader = score_df.iloc[0]
        repetitive = score_df.sort_values("repetition", ascending=False).iloc[0]
        survivor = df.groupby("brand")["ad_age_days"].mean().sort_values(ascending=False).reset_index().iloc[0]
        awards = [
            {"label": "Most Aggressive Advertiser", "winner": leader["brand"], "why": f"War Score {leader['war_score']}"},
            {"label": "Most Repetitive Messaging", "winner": repetitive["brand"], "why": f"{repetitive['repetition']:.1f}% concentration"},
            {"label": "Best Survival Rate", "winner": survivor["brand"], "why": f"{survivor['ad_age_days']:.1f} average live days"},
        ]

    payload = {
        "overview": overview,
        "creative_trends": creative,
        "longevity_signals": longevity,
        "format_shifts": shifts,
        "message_saturation": saturation,
        "strategic_insights": strategy,
        "gap_detection": gaps,
        "category_roasts": roasts,
        "monday_actions": actions,
        "brand_scores": score_df.to_dict(orient="records"),
        "awards": awards,
    }

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    with OUTPUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    top_ads[["brand", "category", "format", "primary_theme", "ad_age_days", "performance_proxy_score", "platform", "url", "ad_text"]].head(40).to_csv(OUTPUT_TOP_ADS, index=False)
    OUTPUT_BRIEF.write_text(build_weekly_brief(creative, longevity, strategy, gaps), encoding="utf-8")

    print(f"Saved -> {OUTPUT_JSON}")
    print(f"Saved -> {OUTPUT_TOP_ADS}")
    print(f"Saved -> {OUTPUT_BRIEF}")


if __name__ == "__main__":
    main()
