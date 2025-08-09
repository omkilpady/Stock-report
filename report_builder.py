
import datetime as dt
import pandas as pd
import numpy as np
import yfinance as yf
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib.utils import simpleSplit
import io

def date_range_from_phrase(phrase: str):
    today = dt.date.today()

    def quarter_start_end(day: dt.date):
        q_end_months = [3,6,9,12]
        last_end = None
        for m in reversed(q_end_months):
            year = day.year if day.month > m else day.year - 1
            if m == 12:
                last_day = 31
            else:
                tmp = dt.date(year, m, 28) + dt.timedelta(days=4)
                last_day = (tmp - dt.timedelta(days=tmp.day)).day
            cand = dt.date(year, m, last_day)
            if cand < day:
                last_end = cand
                break
        prev_m = {3:12, 6:3, 9:6, 12:9}[last_end.month]
        prev_y = last_end.year - 1 if prev_m == 12 else last_end.year
        if prev_m == 12:
            prev_last_day = 31
        else:
            tmp = dt.date(prev_y, prev_m, 28) + dt.timedelta(days=4)
            prev_last_day = (tmp - dt.timedelta(days=tmp.day)).day
        prev_end = dt.date(prev_y, prev_m, prev_last_day)
        start = prev_end + dt.timedelta(days=1)
        return start, last_end

    pl = phrase.lower()
    if "last quarter" in pl:
        return quarter_start_end(today)
    if "last 3 months" in pl or "last three months" in pl:
        return today - dt.timedelta(days=90), today
    if "last month" in pl:
        return today - dt.timedelta(days=30), today
    if "ytd" in pl or "year to date" in pl:
        start = dt.date(today.year, 1, 1)
        return start, today
    return quarter_start_end(today)

def nearest_trading_returns(ticker: str, start_date: dt.date, end_date: dt.date):
    df = yf.download(ticker, start=start_date - dt.timedelta(days=7), end=end_date + dt.timedelta(days=7), progress=False)
    if df.empty:
        return None
    try:
        sidx = df.index.get_loc(pd.Timestamp(start_date), method="nearest")
        eidx = df.index.get_loc(pd.Timestamp(end_date), method="nearest")
    except Exception:
        return None
    ret = float(df.iloc[eidx]["Adj Close"] / df.iloc[sidx]["Adj Close"] - 1.0)
    return ret

def compute_metrics_table(ticker: str, benchmark: str, start_date: dt.date, end_date: dt.date):
    data = {"Metric": [], "Value": []}

    r = nearest_trading_returns(ticker, start_date, end_date)
    data["Metric"].append("Period return")
    data["Value"].append(f"{r:.2%}" if r is not None else "N/A")

    br = nearest_trading_returns(benchmark, start_date, end_date)
    data["Metric"].append("Benchmark return")
    data["Value"].append(f"{br:.2%}" if br is not None else "N/A")

    if r is not None and br is not None:
        data["Metric"].append("Outperformance vs benchmark")
        data["Value"].append(f"{(r-br):.2%}")
    else:
        data["Metric"].append("Outperformance vs benchmark")
        data["Value"].append("N/A")

    try:
        tk = yf.Ticker(ticker)
        info = tk.get_info()
    except Exception:
        info = {}

    def safe(k, fmt=None):
        v = info.get(k)
        if v is None:
            return "N/A"
        if fmt == "pct":
            try:
                return f"{float(v):.2%}"
            except Exception:
                return "N/A"
        if fmt == "num":
            try:
                return f"{float(v):,.0f}"
            except Exception:
                return "N/A"
        if isinstance(v, float):
            return f"{v:.2f}"
        return str(v)

    data["Metric"].append("Market cap")
    data["Value"].append(safe("marketCap", "num"))
    data["Metric"].append("Trailing P/E")
    data["Value"].append(safe("trailingPE"))
    data["Metric"].append("Forward P/E")
    data["Value"].append(safe("forwardPE"))
    data["Metric"].append("PEG ratio")
    data["Value"].append(safe("pegRatio"))
    data["Metric"].append("Price to book")
    data["Value"].append(safe("priceToBook"))
    data["Metric"].append("Dividend yield")
    data["Value"].append(safe("dividendYield", "pct"))
    data["Metric"].append("52w range")
    low = safe("fiftyTwoWeekLow")
    high = safe("fiftyTwoWeekHigh")
    data["Value"].append(f"{low} to {high}")

    df = pd.DataFrame(data)
    return df

def summarize_text_llm(text: str) -> str:
    try:
        import streamlit as st
        from openai import OpenAI
        if "openai_api_key" in st.secrets and st.secrets["openai_api_key"]:
            client = OpenAI(api_key=st.secrets["openai_api_key"])
            rsp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role":"system","content":"You are a finance analyst assistant. Be factual and concise."},
                    {"role":"user","content":"Summarize the earnings call into 5 concise bullets: results, guidance, demand, margins, risks.\n\n" + text[:12000]}
                ],
                temperature=0.2,
                max_tokens=400
            )
            return rsp.choices[0].message.content.strip()
    except Exception:
        pass
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    top = lines[:10]
    return "Heuristic summary:\n" + "\n".join(f"- {ln}" for ln in top)

def wrap_text(c, text, x, y, max_width, leading=14):
    from reportlab.lib.utils import simpleSplit
    lines = simpleSplit(text, c._fontname, c._fontsize, max_width)
    for line in lines:
        c.drawString(x, y, line)
        y -= leading
    return y

def build_pdf_report(buffer, title: str, subtitle: str, tickers: list, benchmark: str, start_date: dt.date, end_date: dt.date):
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.units import inch

    c = canvas.Canvas(buffer, pagesize=LETTER)
    width, height = LETTER
    margin = 0.7*inch
    y = height - margin

    c.setFont("Helvetica-Bold", 18)
    y = wrap_text(c, title, margin, y, width - 2*margin, leading=22)
    c.setFont("Helvetica", 12)
    y = wrap_text(c, subtitle, margin, y-6, width - 2*margin, leading=16)
    c.setFont("Helvetica", 10)
    y = wrap_text(c, f"Benchmark {benchmark}   Period {start_date} to {end_date}", margin, y-6, width - 2*margin, leading=14)
    c.showPage()

    for t in tickers:
        c.setFont("Helvetica-Bold", 14)
        y = height - margin
        y = wrap_text(c, f"Ticker {t}", margin, y, width - 2*margin, leading=18)

        c.setFont("Helvetica", 10)
        df = compute_metrics_table(t, benchmark, start_date, end_date)
        col1_x = margin
        col2_x = margin + 2.6*inch
        row_y = y - 10
        for _, row in df.iterrows():
            c.drawString(col1_x, row_y, str(row["Metric"]))
            c.drawString(col2_x, row_y, str(row["Value"]))
            row_y -= 14

        row_y -= 10
        c.setFont("Helvetica-Oblique", 10)
        row_y = wrap_text(c, "Notes: add transcript summary and quarterly highlights here.", margin, row_y, width - 2*margin, leading=14)

        c.showPage()

    c.save()
    buffer.seek(0)
