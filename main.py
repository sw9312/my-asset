import streamlit as st
import yfinance as yf
import pandas as pd
import json
import os
import plotly.express as px
from datetime import datetime
import urllib.request
import re
import gspread
from google.oauth2.service_account import Credentials

# 📱 앱 설정
st.set_page_config(page_title="성우 & 지영 자산관리 V6.1", layout="wide")

# 🎨 디자인 스타일
st.markdown("""
<style>
    .block-container { max-width: 1100px !important; padding-top: 2rem !important; }
    .stApp { background-color: #f2f4f6 !important; }
    
    p, span, div, h1, h2, h3, h4, h5, h6, label, li { color: #191f28 !important; }
    .toss-red { color: #f04452 !important; }
    .toss-blue { color: #3182f6 !important; }
    .toss-black { color: #191f28 !important; }

    .stTextInput input, .stNumberInput input {
        background-color: #ffffff !important; border: 1px solid #c8d0d8 !important;
        border-radius: 8px !important; color: #191f28 !important;
        padding: 10px 12px !important; box-shadow: inset 0 1px 2px rgba(0,0,0,0.02);
    }
    .stTextInput input:focus, .stNumberInput input:focus {
        border-color: #3182f6 !important; box-shadow: 0 0 0 2px rgba(49,130,246,0.2) !important;
    }
    div[data-baseweb="select"] > div {
        background-color: #ffffff !important; border: 1px solid #c8d0d8 !important; border-radius: 8px !important;
    }
    
    .st-expander {
        background-color: white !important; border-radius: 12px !important;
        border: 1px solid #e5e8eb !important; box-shadow: 0 2px 10px rgba(0,0,0,0.02) !important;
    }
    .login-box {
        background-color: white; padding: 30px; border-radius: 20px; border: 1px solid #e5e8eb;
        box-shadow: 0 10px 30px rgba(0,0,0,0.05); max-width: 400px; margin: 0 auto;
    }

    @media (max-width: 768px) {
        .desktop-view { display: none !important; }
        .mobile-view { display: block !important; }
    }
    @media (min-width: 769px) {
        .desktop-view { display: block !important; }
        .mobile-view { display: none !important; }
    }
    
    .sticky-th {
        position: sticky; left: 0; background-color: #f9fafb !important; 
        z-index: 2; border-right: 1px solid #e5e8eb;
    }
    .sticky-col {
        position: sticky; left: 0; background-color: #ffffff !important; 
        z-index: 1; border-right: 1px solid #e5e8eb;
    }
    .sticky-col-tot {
        position: sticky; left: 0; background-color: #f9fafb !important; 
        z-index: 1; border-right: 1px solid #e5e8eb;
    }
</style>
""", unsafe_allow_html=True)

# ---------------- 보안 및 데이터 설정 ----------------
FAMILY_PIN = "1204" 

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    st.markdown("<div class='login-box'>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center; color: #191f28;'>🔒 성우 & 지영 자산관리</h3>", unsafe_allow_html=True)
    user_input = st.text_input("가족 비밀번호", type="password", placeholder="비밀번호를 입력하세요")
    if st.button("앱 열기", use_container_width=True):
        if user_input == FAMILY_PIN: st.session_state["logged_in"] = True; st.rerun()
        else: st.error("비밀번호가 틀렸습니다.")
    st.markdown("</div>", unsafe_allow_html=True)
else:
    def get_gspread_client():
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        secret_info = json.loads(st.secrets["gcp_service_account"])
        credentials = Credentials.from_service_account_info(secret_info, scopes=scopes)
        return gspread.authorize(credentials)

    def init_sheets(sh):
        existing = [w.title for w in sh.worksheets()]
        for name in ["cash_list", "stocks", "history", "watchlist"]:
            if name not in existing:
                sh.add_worksheet(title=name, rows="500", cols="20")

    def load_data():
        try:
            gc = get_gspread_client()
            sh = gc.open_by_url(st.secrets["sheet_url"])
            init_sheets(sh)
            
            data = {}
            for name in ["cash_list", "stocks", "history", "watchlist"]:
                wks = sh.worksheet(name)
                records = wks.get_all_records()
                data[name] = records if records else []
                
            for s in data.get("stocks", []):
                if "name" not in s: s["name"] = ""
                if "note" not in s: s["note"] = ""
                if "is_overseas" in s:
                    if str(s["is_overseas"]).upper() in ["TRUE", "1"]: s["is_overseas"] = True
                    elif str(s["is_overseas"]).upper() in ["FALSE", "0"]: s["is_overseas"] = False
            return data
        except Exception as e:
            st.error(f"구글 시트 연동 실패: {e}")
            return {"cash_list": [], "stocks": [], "history": [], "watchlist": []}

    def save_data(data):
        try:
            gc = get_gspread_client()
            sh = gc.open_by_url(st.secrets["sheet_url"])
            for name in ["cash_list", "stocks", "history", "watchlist"]:
                wks = sh.worksheet(name)
                wks.clear()
                if data.get(name):
                    df = pd.DataFrame(data[name])
                    df = df.fillna("")
                    wks.update('A1', [df.columns.values.tolist()] + df.values.tolist())
        except Exception as e:
            st.error(f"구글 시트 저장 실패: {e}")

    KOR_NAMES = {
        "005930": "삼성전자", "000660": "SK하이닉스", "373220": "LG에너지솔루션", 
        "207940": "삼성바이오로직스", "005380": "현대차", "000270": "기아", "068270": "셀트리온", 
        "005490": "POSCO홀딩스", "035420": "NAVER", "035720": "카카오", "005935": "삼성전자우",
        "133690": "TIGER 미국다우존스30", "360750": "TIGER 미국S&P500", "069500": "KODEX 200"
    }
    USA_NAMES = {
        "AAPL": "애플", "MSFT": "마이크로소프트", "NVDA": "엔비디아", "TSLA": "테슬라",
        "AMZN": "아마존", "META": "메타 플랫폼스", "GOOGL": "알파벳 A", "MU": "마이크론",
        "PLTR": "팔란티어", "CPNG": "쿠팡", "ORCL": "오라클", "OXY": "옥시덴탈", "AMR": "알파 메탈러지컬", "BKSY": "블랙스카이"
    }

    @st.cache_data(ttl=600)
    def get_exchange_rate():
        for ticker in ["USDKRW=X", "KRW=X"]:
            try:
                rate = yf.Ticker(ticker).history(period="1d")["Close"].iloc[-1]
                if rate > 1000: return rate
            except: continue
        return 1380.0

    @st.cache_data(ttl=3600)
    def get_stock_data(ticker):
        clean_ticker = str(ticker).upper().split('.')[0]
        real_name = KOR_NAMES.get(clean_ticker) or USA_NAMES.get(clean_ticker)
        
        if not real_name:
            real_name = clean_ticker
            if clean_ticker.isdigit() and len(clean_ticker) == 6:
                try:
                    url = f"https://finance.naver.com/item/main.naver?code={clean_ticker}"
                    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                    html = urllib.request.urlopen(req, timeout=3).read().decode('euc-kr', errors='ignore')
                    match = re.search(r'<title>(.*?) : 네이버', html)
                    if match: real_name = match.group(1)
                except: pass
            else:
                try:
                    info = yf.Ticker(ticker.upper()).info
                    if info: real_name = info.get('shortName') or info.get('longName') or clean_ticker
                except: pass

        t_to_try = [ticker.upper()]
        if clean_ticker.isdigit() and len(clean_ticker) == 6:
            if "." not in ticker: t_to_try = [ticker + ".KS", ticker + ".KQ"]

        for t in t_to_try:
            try:
                stock = yf.Ticker(t)
                hist = stock.history(period="1mo") 
                if not hist.empty: hist = hist.dropna(subset=["Close"])
                if not hist.empty:
                    curr = float(hist["Close"].iloc[-1])
                    prev = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else curr
                    return curr, curr - prev, (curr - prev) / prev * 100, real_name
            except: continue
        return 0.0, 0.0, 0.0, real_name

    data = load_data()
    ex_rate = get_exchange_rate()

    st.markdown("<h2 style='font-weight: 700;'>📊 통합 자산 포트폴리오</h2>", unsafe_allow_html=True)
    col_rate, col_logout = st.columns([5, 1])
    with col_rate: st.markdown(f"<span style='color: #8b95a1 !important;'>💱 실시간 환율: <b>1$ = {ex_rate:,.2f}원</b></span>", unsafe_allow_html=True)
    with col_logout:
        if st.button("🔒 로그아웃", use_container_width=True): st.session_state["logged_in"] = False; st.rerun()

    # 💡 탭 6개 (백업 탭) 정상 부활!
    with st.expander("✏️ 자산 데이터 관리 (입력/수정)"):
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["💵 현금", "📈 주식 등록", "⚙️ 보유주식 수정", "⭐ 관심종목", "📜 기록 관리", "💾 백업"])
        
        with tab1:
            with st.form("cash_form", clear_on_submit=True):
                col_c1, col_c2 = st.columns(2)
                c_owner = col_c1.radio("소유자", ["성우", "지영"], horizontal=True)
                c_label = col_c2.text_input("항목 이름", value="현금")
                col_c3, col_c4 = st.columns(2)
                c_amt = col_c3.number_input("잔액 입력", min_value=0.0)
                c_curr = col_c4.selectbox("통화", ["KRW(원)", "USD(달러)"])
                if st.form_submit_button("현금 추가"):
                    data["cash_list"].append({"owner": c_owner, "label": c_label, "amount": c_amt, "currency": c_curr})
                    save_data(data); st.rerun()
            st.write("---")
            for i, c in enumerate(data.get("cash_list", [])):
                unit_label = "$" if "USD" in c['currency'] else "원"
                with st.expander(f"[{c['owner']}] {c['label']} ({c['amount']:,}{unit_label})"):
                    new_amt = st.number_input("금액 수정", value=float(c['amount']), key=f"ce_{i}")
                    c_btn1, c_btn2 = st.columns(2)
                    if c_btn1.button("수정", key=f"cb_{i}"): data["cash_list"][i]['amount'] = new_amt; save_data(data); st.rerun()
                    if c_btn2.button("삭제", key=f"cd_{i}"): data["cash_list"].pop(i); save_data(data); st.rerun()

        with tab2:
            with st.form("stock_form", clear_on_submit=True):
                col1, col2 = st.columns(2)
                s_owner = col1.selectbox("소유자", ["성우", "지영"])
                s_ticker = col2.text_input("종목코드 (예: 005930, AAPL)").upper()
                s_broker = st.selectbox("증권사", ["미래에셋", "나무", "토스", "키움", "삼성", "기타"])
                s_cur = st.selectbox("평단가 통화", ["KRW(원)", "USD(달러)"])
                s_is_ovs = st.checkbox("해외 주식인가요?")
                col3, col4 = st.columns(2)
                s_qty = col3.number_input("수량", min_value=0.0)
                s_val = col4.number_input("평균단가", min_value=0.0)
                s_note = st.text_input("비고 (계좌종류 등)")
                if s_is_ovs: s_is_ovs_bool = True
                else: s_is_ovs_bool = False
                if st.form_submit_button("주식 추가"):
                    data["stocks"].append({"owner": s_owner, "broker": s_broker, "ticker": s_ticker, "name": "", "is_overseas": s_is_ovs_bool, "qty": s_qty, "avg_price": s_val, "input_currency": s_cur, "note": s_note})
                    save_data(data); st.rerun()
                    
        with tab3:
            for i, s in enumerate(data["stocks"]):
                display_name = s.get('name') if s.get('name') else s['ticker']
                with st.expander(f"[{s['owner']}] {display_name} ({s['broker']})"):
                    new_n = st.text_input("종목명 강제지정", value=s.get('name', ''), key=f"en_{i}", placeholder="비워두면 자동 검색됩니다")
                    new_q = st.number_input("수량", value=float(s['qty']), key=f"eq_{i}")
                    new_a = st.number_input("평단가", value=float(s['avg_price']), key=f"ea_{i}")
                    new_note = st.text_input("비고", value=s.get('note', ''), key=f"nt_{i}")
                    if st.button("저장", key=f"es_{i}"):
                        data["stocks"][i].update({"name": new_n, "qty": new_q, "avg_price": new_a, "note": new_note})
                        save_data(data); st.rerun()
                    if st.button("삭제", key=f"ed_{i}"): data["stocks"].pop(i); save_data(data); st.rerun()

        with tab4:
            with st.form("watchlist_form", clear_on_submit=True):
                wl_ticker = st.text_input("관심종목 코드 (예: TSLA, 005930)").upper()
                if st.form_submit_button("관심종목 추가"):
                    if wl_ticker:
                        data["watchlist"].append({"ticker": wl_ticker})
                        save_data(data); st.rerun()
            st.write("---")
            for i, w in enumerate(data.get("watchlist", [])):
                col_w1, col_w2 = st.columns([4, 1])
                col_w1.write(f"⭐ {w['ticker']}")
                if col_w2.button("삭제", key=f"wdel_{i}"):
                    data["watchlist"].pop(i); save_data(data); st.rerun()
                        
        with tab5:
            for i, h in enumerate(data["history"]):
                col_h1, col_h2 = st.columns([4, 1])
                col_h1.write(f"📅 {h['date']} | {h['total']:,}원")
                if col_h2.button("삭제", key=f"hdel_{i}"): data["history"].pop(i); save_data(data); st.rerun()
                
        # 💡 여기가 빠져있던 백업 탭입니다!
        with tab6:
            st.warning("예전에 쓰던 데이터를 아래 상자에 넣고 복구를 누르시면 구글 시트로 한 번에 넘어갑니다.")
            st.text_area("현재 내 데이터 (복사 보관용)", value=json.dumps(data, ensure_ascii=False), height=100)
            restore_json = st.text_input("복구용 데이터 붙여넣기")
            if st.button("데이터 복구 실행"):
                try:
                    new_data = json.loads(restore_json)
                    save_data(new_data)
                    st.success("데이터가 구글 시트로 완벽하게 복구되었습니다! 잠시 후 화면이 새로고침됩니다.")
                    st.rerun()
                except Exception as e:
                    st.error(f"올바른 형식이 아닙니다: {e}")

    st.divider()
    
    view_currency = st.radio("💰 통화 기준", ["원화(KRW)", "달러(USD)"], horizontal=True)
    is_usd_view = view_currency == "달러(USD)"
    unit, div = ("$", ex_rate) if is_usd_view else ("원", 1)

    processed_stocks = {}
    for s in data.get("stocks", []):
        key = (s['ticker'], s['owner'])
        is_usd_in = "USD" in s.get("input_currency", "KRW")
        try: price_krw = float(s['avg_price']) * ex_rate if is_usd_in else float(s['avg_price'])
        except: price_krw = 0.0
        try: qty = float(s['qty'])
        except: qty = 0.0
        
        if key not in processed_stocks:
            processed_stocks[key] = {
                "owner": s['owner'], "ticker": s['ticker'], "name_override": s.get('name', ''),
                "is_overseas": s['is_overseas'], "qty": qty, "total_buy_krw": price_krw * qty,
                "notes": [f"{s['broker']}" + (f"({s['note']})" if s.get('note') else "")]
            }
        else:
            processed_stocks[key]['qty'] += qty
            processed_stocks[key]['total_buy_krw'] += price_krw * qty
            note_str = f"{s['broker']}" + (f"({s['note']})" if s.get('note') else "")
            if note_str not in processed_stocks[key]['notes']: processed_stocks[key]['notes'].append(note_str)

    total_stock_krw = 0
    final_stock_list = []
    chart_data = []

    for key, p in processed_stocks.items():
        curr_p, d_chg, d_pct, web_name = get_stock_data(p['ticker'])
        final_name = p['name_override'] if p['name_override'] else web_name
        eval_krw = p['qty'] * curr_p * (ex_rate if p['is_overseas'] else 1)
        total_stock_krw += eval_krw
        
        avg_p_view = (p['total_buy_krw'] / p['qty']) / (ex_rate if is_usd_view else 1) if p['qty'] > 0 else 0
        curr_p_view = curr_p if p['is_overseas'] else curr_p / (ex_rate if is_usd_view else 1)
        d_chg_view = (d_chg * p['qty'] * (ex_rate if p['is_overseas'] else 1)) / div

        final_stock_list.append({
            "owner": p['owner'], "name": final_name, "ticker": p['ticker'],
            "qty": p['qty'], "buy_krw": p['total_buy_krw'], "eval_krw": eval_krw,
            "curr_p": curr_p_view, "avg_p": avg_p_view, "d_chg": d_chg_view, "d_pct": d_pct,
            "remarks": ", ".join(p['notes'])
        })
        chart_data.append({"항목": final_name, "평가금액": eval_krw})

    total_cash_krw = sum([float(c['amount']) * (ex_rate if "USD" in c['currency'] else 1) for c in data.get("cash_list", [])])
    total_asset_krw = total_cash_krw + total_stock_krw
    if total_cash_krw > 0: chart_data.append({"항목": "현금", "평가금액": total_cash_krw})

    custom_metric_html = f"""
    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 20px;">
        <div style="background-color: white; padding: 15px 10px; border-radius: 16px; box-shadow: 0 4px 15px rgba(0,0,0,0.03); text-align: center; border: 1px solid #f2f4f6;">
            <div style="color: #8b95a1; font-size: 13px; font-weight: 600; margin-bottom: 5px;">총 자산</div>
            <div style="color: #191f28; font-size: 18px; font-weight: 800;">{total_asset_krw/div:,.0f}<span style="font-size:14px; margin-left:2px;">{unit}</span></div>
        </div>
        <div style="background-color: white; padding: 15px 10px; border-radius: 16px; box-shadow: 0 4px 15px rgba(0,0,0,0.03); text-align: center; border: 1px solid #f2f4f6;">
            <div style="color: #8b95a1; font-size: 13px; font-weight: 600; margin-bottom: 5px;">주식</div>
            <div style="color: #191f28; font-size: 18px; font-weight: 800;">{total_stock_krw/div:,.0f}<span style="font-size:14px; margin-left:2px;">{unit}</span></div>
        </div>
        <div style="background-color: white; padding: 15px 10px; border-radius: 16px; box-shadow: 0 4px 15px rgba(0,0,0,0.03); text-align: center; border: 1px solid #f2f4f6;">
            <div style="color: #8b95a1; font-size: 13px; font-weight: 600; margin-bottom: 5px;">현금</div>
            <div style="color: #191f28; font-size: 18px; font-weight: 800;">{total_cash_krw/div:,.0f}<span style="font-size:14px; margin-left:2px;">{unit}</span></div>
        </div>
    </div>
    """
    st.markdown(custom_metric_html, unsafe_allow_html=True)
    
    st.divider()
    st.markdown("<h3 style='color: #191f28;'>📈 자산 추이</h3>", unsafe_allow_html=True)
    if st.button("현재 자산 누적 기록하기", use_container_width=True):
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data["history"].append({"date": now_str, "total": int(total_asset_krw), "stock": int(total_stock_krw), "cash": int(total_cash_krw)})
        save_data(data); st.rerun()

    if data.get("history"):
        h_df = pd.DataFrame(data["history"])
        val_div = 10000 if not is_usd_view else ex_rate
        h_df["총자산"], h_df["주식"], h_df["현금"] = h_df["total"]/val_div, h_df["stock"]/val_div, h_df["cash"]/val_div
        fig = px.line(h_df, x="date", y=["총자산", "주식", "현금"], markers=True)
        fig.update_layout(yaxis_title="만원" if not is_usd_view else "USD", legend_title="", plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font=dict(color="#191f28"), dragmode=False)
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    if chart_data:
        st.divider()
        st.markdown("<h3 style='color: #191f28;'>🍩 포트폴리오 비중</h3>", unsafe_allow_html=True)
        fig_pie = px.pie(pd.DataFrame(chart_data), values="평가금액", names="항목", hole=0.45)
        fig_pie.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font=dict(color="#191f28"), dragmode=False)
        st.plotly_chart(fig_pie, use_container_width=True, config={'displayModeBar': False})

    def draw_responsive_table(df_list):
        if not df_list: 
            st.markdown("<p style='color:#8b95a1;'>보유 주식이 없습니다.</p>", unsafe_allow_html=True)
            return
        
        total_buy = sum(r['buy_krw'] for r in df_list)
        total_eval = sum(r['eval_krw'] for r in df_list)
        total_profit = total_eval - total_buy
        total_p_pct = (total_profit / total_buy * 100) if total_buy > 0 else 0
        total_d_chg = sum(r['d_chg'] for r in df_list)
        
        tp_clr = 'toss-red' if total_profit > 0 else 'toss-blue' if total_profit < 0 else 'toss-black'
        tc_clr = 'toss-red' if total_d_chg > 0 else 'toss-blue' if total_d_chg < 0 else 'toss-black'

        desk_html = '<div class="desktop-view" style="overflow-x: auto; background-color: white; border-radius: 16px; padding: 10px 15px; box-shadow: 0 4px 20px rgba(0,0,0,0.03); margin-bottom: 25px;">'
        desk_html += '<table style="border-collapse: collapse; font-size: 14px; color: #191f28; white-space: nowrap; width: 100%;">'
        desk_html += '<thead><tr style="border-bottom: 1px solid #e5e8eb;">'
        cols = ["소유", "종목명", "수량", "현재가<br>(평단가)", "평가금액<br>(매입금액)", "평가손익<br>(수익률)", "전일대비", "비고"]
        for c in cols: 
            align = "center" if c in ['소유', '수량'] else "left" if c in ['종목명', '비고'] else "right"
            style_add = " max-width: 150px; white-space: normal; word-break: keep-all;" if c == "종목명" else ""
            desk_html += f'<th style="padding: 10px 15px; text-align: {align}; color: #8b95a1; font-weight: 500; font-size: 13px;{style_add}">{c}</th>'
        desk_html += '</tr></thead><tbody>'
        
        desk_html += f'<tr style="background-color: #f9fafb; border-bottom: 2px solid #e5e8eb;">'
        desk_html += f'<td colspan="4" style="padding: 12px 15px; text-align: center; font-weight: 800; color: #191f28;">합 계</td>'
        desk_html += f'<td style="padding: 12px 15px; text-align: right; font-weight: 800; color: #191f28;">{total_eval/div:,.1f}{unit}<br><span style="font-size:12px; color: #8b95a1; font-weight:600;">({total_buy/div:,.1f}{unit})</span></td>'
        desk_html += f'<td style="padding: 12px 15px; text-align: right; font-weight: 800;" class="{tp_clr}">{total_profit/div:,.1f}{unit}<br><span style="font-size:12px;">({total_p_pct:+.2f}%)</span></td>'
        desk_html += f'<td style="padding: 12px 15px; text-align: right; font-weight: 800;" class="{tc_clr}">{total_d_chg:,.1f}{unit}</td>'
        desk_html += f'<td style="padding: 12px 15px;"></td></tr>'
        
        for r in df_list:
            profit = r['eval_krw'] - r['buy_krw']
            p_pct = (profit / r['buy_krw'] * 100) if r['buy_krw'] > 0 else 0
            p_clr = 'toss-red' if profit > 0 else 'toss-blue' if profit < 0 else 'toss-black'
            c_clr = 'toss-red' if r['d_chg'] > 0 else 'toss-blue' if r['d_chg'] < 0 else 'toss-black'
            
            desk_html += f'<tr style="border-bottom: 1px solid #f2f4f6;">'
            desk_html += f'<td style="padding: 12px 15px; text-align: center; font-weight: 600; color: #191f28;">{r["owner"]}</td>'
            desk_html += f'<td style="padding: 12px 15px; text-align: left; font-weight: 600; color: #191f28; max-width: 150px; white-space: normal; word-break: keep-all;">{r["name"]}<br><span style="font-size:12px; color: #8b95a1; font-weight:400;">{r["ticker"]}</span></td>'
            desk_html += f'<td style="padding: 12px 15px; text-align: center; font-weight: 500; color: #191f28;">{int(r["qty"])}</td>'
            desk_html += f'<td style="padding: 12px 15px; text-align: right; font-weight: 500; color: #191f28;">{r["curr_p"]:,.1f}<br><span style="font-size:12px; color: #8b95a1;">({r["avg_p"]:,.1f})</span></td>'
            desk_html += f'<td style="padding: 12px 15px; text-align: right; font-weight: 500; color: #191f28;">{r["eval_krw"]/div:,.1f}{unit}<br><span style="font-size:12px; color: #8b95a1;">({r["buy_krw"]/div:,.1f}{unit})</span></td>'
            desk_html += f'<td style="padding: 12px 15px; text-align: right; font-weight: 700;" class="{p_clr}">{profit/div:,.1f}{unit}<br><span style="font-size:12px;">({p_pct:+.2f}%)</span></td>'
            desk_html += f'<td style="padding: 12px 15px; text-align: right; font-weight: 700;" class="{c_clr}">{r["d_chg"]:,.1f}{unit}<br><span style="font-size:12px;">({r["d_pct"]:+.2f}%)</span></td>'
            desk_html += f'<td style="padding: 12px 15px; text-align: left; font-size: 13px; color: #8b95a1;">{r["remarks"]}</td></tr>'
        desk_html += '</tbody></table></div>'

        mob_html = '<div class="mobile-view" style="overflow-x: auto; background-color: white; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.03); margin-bottom: 20px;">'
        mob_html += '<table style="border-collapse: collapse; font-size: 13px; color: #191f28; white-space: nowrap; width: 100%; min-width: 600px;">'
        
        mob_html += '<thead><tr style="border-bottom: 1px solid #e5e8eb; background-color: #f9fafb;">'
        mob_html += '<th class="sticky-th" style="padding: 12px 10px; text-align: left; color: #8b95a1; font-weight: 600; max-width: 120px; white-space: normal; word-break: keep-all;">[소유] 종목명<br><span style="font-size: 11px;">보유수량</span></th>'
        mob_html += '<th style="padding: 12px 10px; text-align: right; color: #8b95a1; font-weight: 500;">현재가<br><span style="font-size: 11px;">(평단가)</span></th>'
        mob_html += '<th style="padding: 12px 10px; text-align: right; color: #8b95a1; font-weight: 500;">평가손익<br><span style="font-size: 11px;">(수익률)</span></th>'
        mob_html += '<th style="padding: 12px 10px; text-align: right; color: #8b95a1; font-weight: 500;">평가금액<br><span style="font-size: 11px;">(매입금액)</span></th>'
        mob_html += '<th style="padding: 12px 10px; text-align: right; color: #8b95a1; font-weight: 500;">전일대비</th>'
        mob_html += '</tr></thead><tbody>'
        
        mob_html += f'<tr style="background-color: #f2f4f6; border-bottom: 2px solid #e5e8eb;">'
        mob_html += f'<td class="sticky-col-tot" style="padding: 12px 10px; text-align: left; font-weight: 800; color: #191f28;">합 계</td>'
        mob_html += f'<td style="padding: 12px 10px; text-align: right;"></td>'
        mob_html += f'<td style="padding: 12px 10px; text-align: right; font-weight: 800;" class="{tp_clr}">{total_profit/div:,.1f}{unit}<br><span style="font-size:11px;">({total_p_pct:+.2f}%)</span></td>'
        mob_html += f'<td style="padding: 12px 10px; text-align: right; font-weight: 800; color: #191f28;">{total_eval/div:,.1f}{unit}<br><span style="font-size:11px; color: #8b95a1; font-weight:normal;">({total_buy/div:,.1f}{unit})</span></td>'
        mob_html += f'<td style="padding: 12px 10px; text-align: right; font-weight: 800;" class="{tc_clr}">{total_d_chg:,.1f}{unit}</td></tr>'

        for r in df_list:
            profit = r['eval_krw'] - r['buy_krw']
            p_pct = (profit / r['buy_krw'] * 100) if r['buy_krw'] > 0 else 0
            p_clr = 'toss-red' if profit > 0 else 'toss-blue' if profit < 0 else 'toss-black'
            c_clr = 'toss-red' if r['d_chg'] > 0 else 'toss-blue' if r['d_chg'] < 0 else 'toss-black'
            
            mob_html += f'<tr style="border-bottom: 1px solid #f2f4f6;">'
            mob_html += f'<td class="sticky-col" style="padding: 12px 10px; text-align: left; max-width: 120px; white-space: normal; word-break: keep-all;">'
            mob_html += f'<div style="font-weight: 700; color: #191f28;">[{r["owner"]}] {r["name"]}</div>'
            mob_html += f'<div style="font-size: 12px; color: #8b95a1;">{int(r["qty"])}주</div></td>'
            
            mob_html += f'<td style="padding: 12px 10px; text-align: right; font-weight: 600; color: #191f28;">{r["curr_p"]:,.1f}<br><span style="font-size:11px; color: #8b95a1; font-weight:normal;">({r["avg_p"]:,.1f})</span></td>'
            mob_html += f'<td style="padding: 12px 10px; text-align: right; font-weight: 700;" class="{p_clr}">{profit/div:,.1f}{unit}<br><span style="font-size:11px;">({p_pct:+.2f}%)</span></td>'
            mob_html += f'<td style="padding: 12px 10px; text-align: right; font-weight: 600; color: #191f28;">{r["eval_krw"]/div:,.1f}{unit}<br><span style="font-size:11px; color: #8b95a1; font-weight:normal;">({r["buy_krw"]/div:,.1f}{unit})</span></td>'
            mob_html += f'<td style="padding: 12px 10px; text-align: right; font-weight: 700;" class="{c_clr}">{r["d_chg"]:,.1f}{unit}<br><span style="font-size:11px;">({r["d_pct"]:+.2f}%)</span></td></tr>'
        
        mob_html += '</tbody></table></div>'
        st.markdown(desk_html + mob_html, unsafe_allow_html=True)

    st.markdown("<h3 style='color:#191f28;'>🇰🇷 국내 주식</h3>", unsafe_allow_html=True)
    draw_responsive_table([x for x in final_stock_list if not str(x['ticker']).isalpha()])
    st.markdown("<h3 style='color:#191f28;'>🇺🇸 해외 주식</h3>", unsafe_allow_html=True)
    draw_responsive_table([x for x in final_stock_list if str(x['ticker']).isalpha()])

    if data.get("watchlist"):
        st.divider()
        st.markdown("<h3 style='color:#191f28;'>⭐ 관심 종목</h3>", unsafe_allow_html=True)
        
        desk_wl_html = '<div class="desktop-view" style="overflow-x: auto; background-color: white; border-radius: 16px; padding: 10px 15px; box-shadow: 0 4px 20px rgba(0,0,0,0.03); margin-bottom: 25px;">'
        desk_wl_html += '<table style="border-collapse: collapse; font-size: 14px; color: #191f28; white-space: nowrap; width: 100%;">'
        desk_wl_html += '<thead><tr style="border-bottom: 1px solid #e5e8eb;">'
        desk_wl_html += '<th style="padding: 10px 15px; text-align: left; color: #8b95a1; font-weight: 500; font-size: 13px; max-width: 150px; white-space: normal; word-break: keep-all;">종목명</th>'
        desk_wl_html += '<th style="padding: 10px 15px; text-align: right; color: #8b95a1; font-weight: 500; font-size: 13px;">현재가</th>'
        desk_wl_html += '<th style="padding: 10px 15px; text-align: right; color: #8b95a1; font-weight: 500; font-size: 13px;">전일대비</th>'
        desk_wl_html += '</tr></thead><tbody>'
        
        mob_wl_html = '<div class="mobile-view" style="overflow-x: auto; background-color: white; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.03); margin-bottom: 20px;">'
        mob_wl_html += '<table style="border-collapse: collapse; font-size: 13px; color: #191f28; white-space: nowrap; width: 100%; min-width: 350px;">'
        mob_wl_html += '<thead><tr style="border-bottom: 1px solid #e5e8eb; background-color: #f9fafb;">'
        mob_wl_html += '<th class="sticky-th" style="padding: 12px 10px; text-align: left; color: #8b95a1; font-weight: 600; max-width: 120px; white-space: normal; word-break: keep-all;">종목명</th>'
        mob_wl_html += '<th style="padding: 12px 10px; text-align: right; color: #8b95a1; font-weight: 500;">현재가</th>'
        mob_wl_html += '<th style="padding: 12px 10px; text-align: right; color: #8b95a1; font-weight: 500;">전일대비</th>'
        mob_wl_html += '</tr></thead><tbody>'

        for w in data["watchlist"]:
            c_p, d_chg, d_pct, w_name = get_stock_data(w['ticker'])
            is_us = str(w['ticker']).isalpha()
            u_str = "$" if is_us else "원"
            
            c_p_str = f"{c_p:,.2f}" if is_us else f"{c_p:,.0f}"
            d_chg_str = f"{d_chg:,.2f}" if is_us else f"{d_chg:,.0f}"
            c_clr = 'toss-red' if d_chg > 0 else 'toss-blue' if d_chg < 0 else 'toss-black'
            
            desk_wl_html += f'<tr style="border-bottom: 1px solid #f2f4f6;">'
            desk_wl_html += f'<td style="padding: 12px 15px; text-align: left; font-weight: 600; color: #191f28; max-width: 150px; white-space: normal; word-break: keep-all;">{w_name}<br><span style="font-size:12px; color: #8b95a1; font-weight:400;">{w["ticker"]}</span></td>'
            desk_wl_html += f'<td style="padding: 12px 15px; text-align: right; font-weight: 600; color: #191f28;">{c_p_str}{u_str}</td>'
            desk_wl_html += f'<td style="padding: 12px 15px; text-align: right; font-weight: 700;" class="{c_clr}">{d_chg_str}{u_str}<br><span style="font-size:12px;">({d_pct:+.2f}%)</span></td></tr>'
            
            mob_wl_html += f'<tr style="border-bottom: 1px solid #f2f4f6;">'
            mob_wl_html += f'<td class="sticky-col" style="padding: 12px 10px; text-align: left; font-weight: 700; color: #191f28; max-width: 120px; white-space: normal; word-break: keep-all;">{w_name}<br><span style="font-size: 11px; color: #8b95a1; font-weight:normal;">{w["ticker"]}</span></td>'
            mob_wl_html += f'<td style="padding: 12px 10px; text-align: right; font-weight: 600; color: #191f28;">{c_p_str}{u_str}</td>'
            mob_wl_html += f'<td style="padding: 12px 10px; text-align: right; font-weight: 700;" class="{c_clr}">{d_chg_str}{u_str}<br><span style="font-size:11px;">({d_pct:+.2f}%)</span></td></tr>'
            
        desk_wl_html += '</tbody></table></div>'
        mob_wl_html += '</tbody></table></div>'
        st.markdown(desk_wl_html + mob_wl_html, unsafe_allow_html=True)

    st.divider()
    with st.expander("🤖 AI 프라이빗 뱅커에게 분석 요청하기", expanded=False):
        st.markdown("👇 아래 상자 우측 상단의 **복사(📋) 버튼**을 누르고, 저에게 붙여넣기 해주세요!")
        gemini_prompt = f"""당신은 VVIP 고객의 자산을 관리하는 '최고의 프라이빗 뱅커(PB)'입니다.
아래 데이터를 바탕으로 전문가적인 시각에서 분석과 조언을 제공해 주세요.

---
### 📊 [포트폴리오 요약]
* 기준일시: {datetime.now().strftime("%Y년 %m월 %d일 %H:%M")}
* 총 자산: {total_asset_krw:,.0f} 원
* 현금: {total_cash_krw:,.0f} 원 (비중: {(total_cash_krw/total_asset_krw*100) if total_asset_krw else 0:.1f}%)
* 주식: {total_stock_krw:,.0f} 원 (비중: {(total_stock_krw/total_asset_krw*100) if total_asset_krw else 0:.1f}%)

### 📈 [보유 종목 현황]
"""
        sorted_stocks = sorted(final_stock_list, key=lambda x: (x['eval_krw']-x['buy_krw'])/x['buy_krw'] if x['buy_krw']>0 else 0, reverse=True)
        for s in sorted_stocks:
            p_pct = ((s['eval_krw']-s['buy_krw'])/s['buy_krw']*100) if s['buy_krw']>0 else 0
            wgt = (s['eval_krw']/total_asset_krw*100) if total_asset_krw>0 else 0
            gemini_prompt += f"- {s['name']} ({s['ticker']}): 비중 {wgt:.1f}%, 수익률 {p_pct:+.2f}%, 평가액 {s['eval_krw']:,.0f}원, 비고: {s['remarks']}\n"
        gemini_prompt += """
---
### 📝 [요청 사항]
1. 자산 배분 적절성 평가 및 리스크 진단
2. 수익 극대화를 위한 맞춤형 리밸런싱 전략 제안
3. 부부를 위한 따뜻한 재테크 조언
"""
        st.code(gemini_prompt, language="markdown")
