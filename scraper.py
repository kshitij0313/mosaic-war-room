from __future__ import annotations

import argparse
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
from dotenv import load_dotenv

from config import RAW_DIR, load_competitors
from utils import safe_write_json, slugify

load_dotenv()

BASE_URL = "https://www.searchapi.io/api/v1/search"
PAGE_CACHE_PATH = RAW_DIR / "page_cache.json"


class SearchAPIClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = BASE_URL

    def get(self, params: Dict[str, Any], retries: int = 6) -> Dict[str, Any]:
        for attempt in range(retries):
            response = requests.get(self.base_url, params={**params, "api_key": self.api_key}, timeout=60)
            if response.status_code == 429:
                wait = min(30 * (attempt + 1), 180)
                print(f"429 rate limit hit. Waiting {wait}s and retrying...")
                time.sleep(wait)
                continue
            response.raise_for_status()
            return response.json()
        raise RuntimeError("SearchAPI rate limit kept firing. Wait a little, then run again.")


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def load_page_cache() -> Dict[str, Any]:
    if PAGE_CACHE_PATH.exists():
        try:
            return pd.read_json(PAGE_CACHE_PATH, typ="series").to_dict()
        except Exception:
            import json
            with PAGE_CACHE_PATH.open("r", encoding="utf-8") as f:
                return json.load(f)
    return {}


def save_page_cache(cache: Dict[str, Any]) -> None:
    safe_write_json(PAGE_CACHE_PATH, cache)


def query_variants(entry: Dict[str, Any]) -> List[str]:
    variants = [entry.get("query", ""), entry.get("brand", "")]
    variants.extend(entry.get("aliases", []) or [])
    out: List[str] = []
    seen = set()
    for item in variants:
        item = str(item or "").strip()
        if item and item.lower() not in seen:
            seen.add(item.lower())
            out.append(item)
    return out


def search_page(client: SearchAPIClient, query: str) -> Dict[str, Any]:
    return client.get({
        "engine": "meta_ad_library_page_search",
        "q": query,
        "country": "ALL",
        "ad_type": "all",
    })


def fetch_ads(client: SearchAPIClient, page_id: str, max_pages: int = 1) -> List[Dict[str, Any]]:
    all_ads: List[Dict[str, Any]] = []
    next_page_token: Optional[str] = None

    for _ in range(max_pages):
        params: Dict[str, Any] = {
            "engine": "meta_ad_library",
            "page_id": page_id,
            "country": "ALL",
            "active_status": "active",
            "ad_type": "all",
        }
        if next_page_token:
            params["next_page_token"] = next_page_token
        payload = client.get(params)
        batch = payload.get("ads", []) or []
        all_ads.extend(batch)
        next_page_token = ((payload.get("pagination") or {}).get("next_page_token"))
        if not next_page_token:
            break
        time.sleep(2)
    return all_ads


def choose_best_page(brand_name: str, page_results: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not page_results:
        return None
    target = normalize(brand_name)
    best = None
    best_score = -1
    for page in page_results:
        name = page.get("name", "")
        alias = page.get("page_alias", "")
        ig = page.get("ig_username", "")
        entity_type = str(page.get("entity_type", "")).upper()
        score = 0
        for candidate in [name, alias, ig]:
            normed = normalize(candidate)
            if target and normed == target:
                score += 110
            elif target and target in normed:
                score += 60
        if page.get("verification") == "VERIFIED":
            score += 10
        if entity_type in {"PAGE", "FB_PAGE"}:
            score += 8
        likes = page.get("likes") or 0
        try:
            score += min(int(likes) // 50000, 10)
        except Exception:
            pass
        if score > best_score:
            best_score = score
            best = page
    return best


def resolve_page(client: SearchAPIClient, entry: Dict[str, Any], page_cache: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    brand = entry["brand"]
    cache_key = brand.lower().strip()
    if cache_key in page_cache and page_cache[cache_key].get("page_id"):
        return page_cache[cache_key]

    all_results: List[Dict[str, Any]] = []
    for query in query_variants(entry):
        payload = search_page(client, query)
        safe_write_json(RAW_DIR / f"page-search-{slugify(brand)}-{slugify(query)}.json", payload)
        for page in payload.get("page_results") or []:
            pid = str(page.get("page_id", ""))
            if pid and pid not in {str(p.get("page_id", "")) for p in all_results}:
                all_results.append(page)
        if len(all_results) >= 6:
            break
        time.sleep(1)

    best = choose_best_page(brand, all_results)
    if best:
        page_cache[cache_key] = best
        save_page_cache(page_cache)
    return best


def build_snapshot_url(ad_archive_id: Any) -> str:
    if not ad_archive_id:
        return ""
    return f"https://www.facebook.com/ads/library/?id={ad_archive_id}"


def _snapshot(ad: Dict[str, Any]) -> Dict[str, Any]:
    return ad.get("snapshot") or {}


def _body_text(snapshot: Dict[str, Any]) -> str:
    body = snapshot.get("body") or {}
    if isinstance(body, dict):
        return body.get("text", "") or ""
    return ""


def _media_counts(snapshot: Dict[str, Any]) -> tuple[int, int]:
    images = snapshot.get("images") or []
    videos = snapshot.get("videos") or []
    cards = snapshot.get("cards") or []
    image_count = max(len(images), len(cards))
    video_count = len(videos)
    return image_count, video_count


def flatten_ad(brand_entry: Dict[str, Any], matched_page: Dict[str, Any], ad: Dict[str, Any]) -> Dict[str, Any]:
    snapshot = _snapshot(ad)
    image_count, video_count = _media_counts(snapshot)
    platforms = ad.get("publisher_platform") or snapshot.get("publisher_platform") or []
    platforms = ", ".join(platforms) if isinstance(platforms, list) else str(platforms or "")
    cta = snapshot.get("link_cta_text") or snapshot.get("cta_text") or ""
    link_caption = snapshot.get("link_caption") or ""
    return {
        "brand_name": brand_entry["brand"],
        "brand_category": brand_entry["category"],
        "competitor_why": brand_entry["why"],
        "brand_query": brand_entry.get("query", brand_entry["brand"]),
        "matched_page_name": ad.get("page_name") or matched_page.get("name", ""),
        "page_id": ad.get("page_id") or matched_page.get("page_id", ""),
        "page_verification": matched_page.get("verification", ""),
        "page_likes": matched_page.get("likes", ""),
        "ad_archive_id": ad.get("ad_archive_id", ""),
        "ad_text": _body_text(snapshot),
        "ad_start_date": ad.get("start_date", ""),
        "ad_end_date": ad.get("end_date", ""),
        "ad_creative_type": snapshot.get("display_format", "") or ad.get("ad_creative_type", ""),
        "raw_display_format": snapshot.get("display_format", ""),
        "platform": platforms,
        "cta_text": cta,
        "link_caption": link_caption,
        "ad_snapshot_url": build_snapshot_url(ad.get("ad_archive_id")),
        "image_count": image_count,
        "video_count": video_count,
        "has_text": bool(_body_text(snapshot).strip()),
    }


def run(max_pages: int = 1, limit_brands: int | None = None, only: List[str] | None = None) -> None:
    api_key = os.getenv("SEARCHAPI_KEY")
    if not api_key:
        raise RuntimeError("SEARCHAPI_KEY not found. Put it in your .env file first.")

    competitors = load_competitors()
    if only:
        wanted = {name.lower().strip() for name in only}
        competitors = [c for c in competitors if c["brand"].lower() in wanted]
    if limit_brands:
        competitors = competitors[:limit_brands]

    client = SearchAPIClient(api_key)
    page_cache = load_page_cache()
    all_rows: List[Dict[str, Any]] = []
    page_rows: List[Dict[str, Any]] = []

    for idx, entry in enumerate(competitors, start=1):
        brand = entry["brand"]
        print(f"[{idx}/{len(competitors)}] resolving page for {brand}...")
        page = resolve_page(client, entry, page_cache)
        if not page:
            print(f"  ! no good page match found for {brand}")
            continue
        page_rows.append({
            "brand": brand,
            "category": entry["category"],
            "query": entry.get("query", brand),
            "matched_page_name": page.get("name", ""),
            "page_id": page.get("page_id", ""),
            "verification": page.get("verification", ""),
            "likes": page.get("likes", ""),
        })
        print(f"  -> using page '{page.get('name', '')}' ({page.get('page_id', '')})")
        ads = fetch_ads(client, str(page.get("page_id")), max_pages=max_pages)
        safe_write_json(RAW_DIR / f"ads-{slugify(brand)}.json", ads)
        print(f"  -> fetched {len(ads)} ads")
        for ad in ads:
            all_rows.append(flatten_ad(entry, page, ad))
        time.sleep(3)

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(page_rows).to_csv(RAW_DIR / "page_matches.csv", index=False)
    pd.DataFrame(all_rows).to_csv(RAW_DIR / "raw_ads.csv", index=False)
    print(f"Saved page matches -> {RAW_DIR / 'page_matches.csv'}")
    print(f"Saved raw ads -> {RAW_DIR / 'raw_ads.csv'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch live Meta Ad Library data via SearchAPI.")
    parser.add_argument("--max-pages", type=int, default=1, help="How many result pages to fetch per brand")
    parser.add_argument("--limit-brands", type=int, default=None, help="Limit the number of brands for quick tests")
    parser.add_argument("--only", nargs="*", help="Run only these brand names")
    args = parser.parse_args()
    run(max_pages=max(1, args.max_pages), limit_brands=args.limit_brands, only=args.only)


if __name__ == "__main__":
    main()
