@echo off
pip install -r requirements.txt
python scraper.py --max-pages 1 --limit-brands 3
python processor.py
python insights.py
streamlit run app.py
