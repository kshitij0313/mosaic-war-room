# Competitor Ad War Room — Mosaic Edition

A premium Streamlit-based competitive intelligence cockpit for Mosaic Wellness.

## What is new in this polished build
- **Mosaic portfolio banner** using the supplied team image, so the app opens with an on-brand portfolio view instead of a generic graphic.
- **Drop the Mosaic confetti** button that rains `Man Matters`, `Be Bodywise`, `Little Joys`, and `Root Labs` across the screen for a quick demo moment.
- **Know your competitors** dropdown that rotates to a different competitor fact on refresh.
- **Ask Mosaic** assistant for natural language questions about competitors, formats, themes, whitespace, and next actions.
- **Cleaner intelligence view** with no raw JSON panel and no code-looking brief block in the main experience.

## Core product features
- Pulls **live active competitor ads** from the public Meta Ad Library using SearchAPI's documented Meta Ad Library endpoints.
- Structures those ads into clean CSVs.
- Classifies creative format and messaging themes.
- Turns raw ad records into a sharper intelligence layer: War Score, Opportunity Meter, Whitespace Unlocks, Monday Morning Action Queue, and a weekly brief.
- Presents everything in a dark, more product-like dashboard instead of a basic report.

## Project structure
- `scraper.py` — fetches live page IDs and ad results via SearchAPI.
- `processor.py` — cleans and enriches the raw records.
- `insights.py` — generates scores, briefs, and strategic outputs.
- `app.py` — the premium dashboard UI.
- `competitors.yaml` — real competitor seed list for Mosaic's categories.
- `.streamlit/config.toml` — visual theme.
- `assets/mosaic_team_banner.png` — on-brand portfolio banner image.

## Before you run
1. Create a SearchAPI account.
2. Copy your API key.
3. Copy `.env.example` to `.env`.
4. Paste your key into `.env`:

```env
SEARCHAPI_KEY=your_real_key_here
```

## Install
```bash
pip install -r requirements.txt
```

## Run the pipeline
Start small first if you are testing your key:

```bash
python scraper.py --max-pages 1 --limit-brands 3
python processor.py
python insights.py
streamlit run app.py
```

When that works, run the full competitor set:

```bash
python scraper.py --max-pages 1
python processor.py
python insights.py
streamlit run app.py
```

## What gets created
- `data/raw/page_matches.csv`
- `data/raw/raw_ads.csv`
- `data/processed/structured_ads.csv`
- `data/processed/brand_summary.csv`
- `data/processed/insights_summary.json`
- `data/processed/top_ads.csv`
- `data/processed/weekly_brief.txt`

## Deploy to Streamlit Community Cloud
1. Push the folder to GitHub.
2. Go to Streamlit Community Cloud.
3. Create a new app from your repo.
4. Select `app.py`.
5. Add this secret in the deploy settings:

```toml
SEARCHAPI_KEY="your_real_key_here"
```

6. Deploy.

## Notes
- The app is designed for **10+ real competitor brands**. It warns you if your live dataset is below that threshold.
- The UI hides `unknown` formats from front-stage charts and filters so the dashboard feels intentional rather than half-debugged.
- If SearchAPI returns HTTP 429, wait a bit and rerun. The scraper has retry logic, but free plans can still throttle bursty runs.
- `--limit-brands 3` is only a smoke test. Omit it for the real scrape.
