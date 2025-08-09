
import streamlit as st
import pandas as pd
import numpy as np
import datetime as dt
import re
import io
import yfinance as yf

from report_builder import build_pdf_report, summarize_text_llm, compute_metrics_table, date_range_from_phrase

st.set_page_config(page_title="Stock Report Generator", layout="wide")

st.title("Stock Report Generator")
st.caption("Type a request, get a clean report. No coding required.")

tab1, tab2, tab3 = st.tabs(["Ask in plain English", "Single Ticker Report", "Transcript to Summary"])

@st.cache_data
def load_sector_csv(name: str):
    path = f"data/{name}.csv"
    return pd.read_csv(path)

def parse_query(q: str):
    ql = q.lower()

    # count
    m_count = re.search(r'(\d+)\s+(stocks|companies)', ql)
    count = int(m_count.group(1)) if m_count else 3

    # sector and region presets
    sector_name = None
    sector_csv = None
    benchmark = None

    if "pharma" in ql or "pharmaceutical" in ql:
        sector_name = "India Pharma"
        sector_csv = "sectors_india_pharma"
        benchmark = "^NSEI"
    elif "us tech" in ql or "tech" in ql:
        sector_name = "US Tech"
        sector_csv = "sectors_us_tech"
        benchmark = "^GSPC"
    else:
        sector_name = "India Pharma"
        sector_csv = "sectors_india_pharma"
        benchmark = "^NSEI"

    # period
    period_phrase = "last quarter"
    if "last 3 months" in ql or "last three months" in ql:
        period_phrase = "last 3 months"
    elif "last month" in ql:
        period_phrase = "last month"
    elif "ytd" in ql or "year to date" in ql:
        period_phrase = "ytd"
    elif "last quarter" in ql or "previous quarter" in ql:
        period_phrase = "last quarter"

    # beat benchmark by X percent
    m_by = re.search(r'by\s+(\d+)\s*%?', ql)
    min_outperf = float(m_by.group(1))/100.0 if m_by else None

    return {
        "count": count,
        "sector_name": sector_name,
        "sector_csv": sector_csv,
        "benchmark": benchmark,
        "period_phrase": period_phrase,
        "min_outperf": min_outperf
    }

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

with tab1:
    st.subheader("Ask in plain English")
    example = "List 3 companies in pharma that beat NIFTY in the last quarter"
    q = st.text_input("Your request", value=example)

    if st.button("Generate picks and report"):
        params = parse_query(q)
        start_date, end_date = date_range_from_phrase(params["period_phrase"])

        sector_df = load_sector_csv(params["sector_csv"])
        tickers = sector_df["Ticker"].dropna().unique().tolist()

        bench_ret = nearest_trading_returns(params["benchmark"], start_date, end_date)

        rows = []
        for t in tickers:
            r = nearest_trading_returns(t, start_date, end_date)
            if r is not None:
                rows.append({"Ticker": t, "Return": r})
        if not rows:
            st.error("Could not fetch data. Try again later.")
        else:
            df = pd.DataFrame(rows)
            if bench_ret is not None:
                df["Outperformance"] = df["Return"] - bench_ret
                if params["min_outperf"] is not None:
                    df = df[df["Outperformance"] >= params["min_outperf"]]
            df = df.sort_values("Outperformance", ascending=False if bench_ret is not None else True)
            topn = df.head(params["count"]).reset_index(drop=True)

            st.success(f"Top {len(topn)} in {params['sector_name']} for {params['period_phrase']}")
            st.dataframe(topn)

            buff = io.BytesIO()
            title = f"{params['sector_name']} outperformers vs {params['benchmark']}"
            subtitle = f"Window {start_date} to {end_date}"
            build_pdf_report(buffer=buff, title=title, subtitle=subtitle, tickers=topn["Ticker"].tolist(),
                             benchmark=params["benchmark"], start_date=start_date, end_date=end_date)
            st.download_button("Download PDF report", data=buff.getvalue(), file_name="stock_report.pdf")

with tab2:
    st.subheader("Single Ticker Report")
    tkr = st.text_input("Ticker", value="SUNPHARMA.NS")
    period_choice = st.selectbox("Period", ["last quarter", "last 3 months", "last month", "ytd"])
    benchmark = st.selectbox("Benchmark", ["^NSEI", "^GSPC"])

    if st.button("Generate ticker PDF"):
        start_date, end_date = date_range_from_phrase(period_choice)
        buff = io.BytesIO()
        title = f"Report for {tkr}"
        subtitle = f"Window {start_date} to {end_date} vs {benchmark}"
        build_pdf_report(buffer=buff, title=title, subtitle=subtitle, tickers=[tkr],
                         benchmark=benchmark, start_date=start_date, end_date=end_date)
        st.download_button("Download PDF report", data=buff.getvalue(), file_name=f"{tkr}_report.pdf")

with tab3:
    st.subheader("Transcript to key takeaways")
    st.caption("Paste earnings call text or upload a .txt file. If you add your OpenAI key in Streamlit secrets, I will summarize with an LLM. Otherwise I will produce a simple heuristic summary.")
    text = st.text_area("Paste transcript text", height=200)
    uploaded = st.file_uploader("Or upload a .txt file", type=["txt"])
    if uploaded and not text:
        text = uploaded.read().decode("utf-8", errors="ignore")

    if st.button("Summarize transcript"):
        if not text.strip():
            st.error("Please paste text or upload a file.")
        else:
            summary = summarize_text_llm(text)
            st.text_area("Summary", value=summary, height=200)
            st.download_button("Download summary", data=summary, file_name="transcript_summary.txt")
