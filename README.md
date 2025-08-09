# Stock Report Generator — MVP

Ask in plain English and get a 2 page PDF per ticker. Example:
"List 3 companies in pharma that beat NIFTY in the last quarter"

What you get
1) Picks that outperformed a benchmark for a time window
2) Single ticker PDF report with default metrics like period return, benchmark return, outperformance, market cap, valuation ratios, dividend yield, 52 week range
3) Paste earnings call text and get a bullet summary
4) Download PDF

Data sources
- Prices and basic stats from Yahoo Finance via yfinance
- Transcript summary uses OpenAI if you add your key in Streamlit secrets. Otherwise a simple fallback.

No code deploy on Streamlit Cloud
1) Create a new public GitHub repo and upload all files in this folder
2) In Streamlit Community Cloud, click New app and select your repo
3) Set the app file to app.py
4) Optional for AI summaries, add a secrets file with your OpenAI key

File .streamlit/secrets_template.toml:
openai_api_key = "sk-..."

Roadmap
- Add more sectors CSVs
- Pull transcripts from allowed sources
- Add company fundamentals per region with official APIs
- Save reports and user history with Supabase
- Email PDF

Legal and access
- Respect each website's terms. This MVP avoids scraping restricted sources.