import re
import urllib.request

import streamlit as st
import yfinance as yf


KOR_NAMES = {
    "005930": "삼성전자", "000660": "SK하이닉스", "133690": "TIGER 미국다우존스30",
    "360750": "TIGER 미국S&P500", "069500": "KODEX 200",
}
USA_NAMES = {
    "AAPL": "애플", "MSFT": "마이크로소프트", "NVDA": "엔비디아", "TSLA": "테슬라",
    "AMZN": "아마존", "META": "메타 플랫폼스", "GOOG": "알파벳", "PLTR": "팔란티어",
    "CPNG": "쿠팡", "ORCL": "오라클", "OXY": "옥시덴탈", "PFE": "화이자",
    "SPY": "SPY ETF", "BIL": "BIL ETF", "ASML": "ASML",
}


@st.cache_data(ttl=600)
def get_exchange_rate():
    for ticker in ("USDKRW=X", "KRW=X"):
        try:
            price = float(yf.Ticker(ticker).history(period="5d")["Close"].dropna().iloc[-1])
            if price > 1000:
                return price
        except Exception:
            continue
    return 1380.0


@st.cache_data(ttl=1800)
def get_stock_data(ticker, custom_dict_tuple=()):
    code = str(ticker).strip().upper().split(".")[0]
    names = dict(custom_dict_tuple)
    name = names.get(code) or KOR_NAMES.get(code) or USA_NAMES.get(code)
    candidates = [code]
    if code.isdigit() and len(code) == 6:
        candidates = [f"{code}.KS", f"{code}.KQ"]
    for candidate in candidates:
        try:
            history = yf.Ticker(candidate).history(period="1mo")["Close"].dropna()
            if not history.empty:
                current = float(history.iloc[-1])
                previous = float(history.iloc[-2]) if len(history) > 1 else current
                if not name:
                    name = code
                change = current - previous
                return current, change, (change / previous * 100 if previous else 0), name
        except Exception:
            continue
    return 0.0, 0.0, 0.0, name or code

