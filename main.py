import streamlit as st
import yfinance as yf
import pandas as pd
import json
import os
import plotly.express as px
from datetime import datetime

# 📱 토스증권 스타일을 위한 와이드 모드 유지
st.set_page_config(page_title="성우 & 지영 자산관리 V5.1", layout="wide")

# 🎨 UI 스타일 적용
st.markdown("""
<style>
    .stApp { background-color: #f2f4f6; font-family: 'Pretendard', -apple-system, sans-serif; }
    div[data-testid="metric-container"] {
        background-color: white;
        padding: 20px;
        border-radius: 16px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.04);
        border: none;
    }
    .st-expander {
        background-color: white;
        border-radius: 12px;
        border: none;
        box-shadow: 0 2px 10px rgba(0,0,0,0.02);
    }
</style>
""", unsafe_allow_html=True)

# ---------------- 보안 및 데이터 설정 ----------------
FAMILY_PIN = "1234" 

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    st.markdown("## 🔒 성우 & 지영 자산관리")
    user_input = st.text_input("가족 비밀번호 입력", type="password")
    if st.button("앱 열기"):
        if user_input == FAMILY_PIN: st.session_state["logged_in"] = True; st.rerun()
        else: st.error("비밀번호가 틀렸습니다.")
else:
    DATA_FILE = "family_finance_data_v2.json"

    def load_data():
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
                if "cash" in d and "cash_list" not in d:
                    d["cash_list"] = [{"owner": k, "label": "현금", "amount": v, "currency": "KRW(원)"} for k, v in d["cash"].items()]
                    del d["cash"]
                for c in d.get("cash_list", []):
                    if "currency" not in c: c["currency"] = "KRW(원)"
                if "history" not in d: d["history"] = []
                for s in d.get("stocks", []):
                    if "name" not in s: s["name"] = ""
                    if "note" not in s: s["note"] = "" 
                return d
        return {"cash_list": [], "stocks": [], "history": []}

    def save_data(data):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    @st.cache_data(ttl=600)
    def get_exchange_rate():
        try: return yf.Ticker("KRW=X").history(period="1d")["Close"].iloc[-1]
        except: return 1350.0

    @st.cache_data(ttl=3600)
    def get_stock_data(ticker):
        t_to_try = [ticker.upper()]
        if ticker.isdigit() and len(ticker) == 6:
            t_to_try = [ticker + ".KS", ticker + ".KQ"]
        for t in t_to_try:
            try:
                stock = yf.Ticker(t)
                hist = stock.history(period="5d")
                if not hist.empty:
                    info = stock.info
                    real_name = info.get('shortName') or info.get('longName') or ticker.split('.')[0]
                    curr = hist["Close"].iloc[-1]
                    prev = hist["Close"].iloc[-2] if len(hist) >= 2 else curr
                    return curr, curr - prev, (curr - prev) / prev * 100, real_name
            except: continue
        return 0.0, 0.0, 0.0, ticker

    data = load_data()
    ex_rate = get_exchange_rate()

    st.markdown("## 📊 성우 & 지영 자산 포트폴리오")
    col_rate, col_logout = st.columns([5, 1])
    with col_rate: st.caption(f"💱 실시간 환율: **1$ = {ex_rate:,.2f}원**")
    with col_logout:
        if st.button("🔒 로그아웃"): st.session_state["logged_in"] = False; st.rerun()

    # 정보 입력 메뉴
    with st.expander("✏️ 자산 데이터 관리 (입력/수정)"):
        tab1, tab2, tab3, tab4 = st.tabs(["💵 현금", "📈 주식 등록", "⚙️ 보유주식 수정", "📜 기록 관리"])
        
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
                with st.expander(f"{c['owner']} - {c['label']} ({c['amount']:,}{unit_label})"):
                    new_amt = st.number_input("수정액", value=float(c['amount']), key=f"ce_{i}")
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
                s_note = st.text_input("비고 (메모사항)")
                
                if st.form_submit_button("주식 추가"):
                    data["stocks"].append({
                        "owner": s_owner, "broker": s_broker, "ticker": s_ticker, "name": "",
                        "is_overseas": s_is_ovs, "qty": s_qty, "avg_price": s_val, "input_currency": s_cur, "note": s_note
                    })
                    save_data(data); st.rerun()
                    
        with tab3:
            for i, s in enumerate(data["stocks"]):
                with st.expander(f"[{s['owner']}] {s.get('name', s['ticker'])} ({s['broker']})"):
                    new_n = st.text_input("종목명 강제지정", value=s.get('name', ''), key=f"en_{i}")
                    new_q = st.number_input("수량 수정", value=float(s['qty']), key=f"eq_{i}")
                    new_a = st.number_input("평단가 수정", value=float(s['avg_price']), key=f"ea_{i}")
                    new_note = st.text_input("비고 수정", value=s.get('note', ''), key=f"nt_{i}")
                    if st.button("저장", key=f"es_{i}"):
                        data["stocks"][i].update({"name": new_n, "qty": new_q, "avg_price": new_a, "note": new_note})
                        save_data(data); st.rerun()
                    if st.button("이 종목 삭제", key=f"ed_{i}"): data["stocks"].pop(i); save_data(data); st.rerun()
                        
        with tab4:
            st.write("기록을 삭제하시려면 버튼을 누르세요.")
            for i, h in enumerate(data["history"]):
                col_h1, col_h2 = st.columns([4, 1])
                col_h1.write(f"📅 {h['date']} | {h['total']:,}원")
                if col_h2.button("삭제", key=f"hdel_{i}"): data["history"].pop(i); save_data(data); st.rerun()

    st.divider()
    
    view_currency = st.radio("💰 통화 기준", ["원화(KRW)", "달러(USD)"], horizontal=True)
    is_usd_view = view_currency == "달러(USD)"
    unit, div = ("$", ex_rate) if is_usd_view else ("원", 1)

    # 데이터 통합
    processed_stocks = {}
    for s in data["stocks"]:
        key = (s['ticker'], s['owner'])
        is_usd_in = "USD" in s.get("input_currency", "KRW")
        price_krw = s['avg_price'] * ex_rate if is_usd_in else s['avg_price']
        
        if key not in processed_stocks:
            processed_stocks[key] = {
                "owner": s['owner'], "ticker": s['ticker'], "name_override": s.get('name', ''),
                "is_overseas": s['is_overseas'], "qty": s['qty'], "total_buy_krw": price_krw * s['qty'],
                "notes": [f"{s['broker']}" + (f"({s['note']})" if s.get('note') else "")]
            }
        else:
            processed_stocks[key]['qty'] += s['qty']
            processed_stocks[key]['total_buy_krw'] += price_krw * s['qty']
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

    # 요약 카드
    c1, c2, c3 = st.columns(3)
    c1.metric("내 총 자산", f"{total_asset_krw/div:,.0f}{unit}")
    c2.metric("주식 평가금액", f"{total_stock_krw/div:,.0f}{unit}")
    c3.metric("보유 현금", f"{total_cash_krw/div:,.0f}{unit}")
    
    st.divider()
    st.subheader("📈 자산 변동 추이")
    if st.button("현재 자산 상태 누적 기록하기"):
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data["history"].append({"date": now_str, "total": int(total_asset_krw), "stock": int(total_stock_krw), "cash": int(total_cash_krw)})
        save_data(data); st.rerun()

    if data.get("history"):
        h_df = pd.DataFrame(data["history"])
        if not is_usd_view:
            h_df["총자산"], h_df["주식"], h_df["현금"] = h_df["total"]/10000, h_df["stock"]/10000, h_df["cash"]/10000
            fig = px.line(h_df, x="date", y=["총자산", "주식", "현금"], markers=True)
            fig.update_layout(yaxis_title="금액 (단위: 만원)", legend_title="")
        else:
            h_df["총자산"], h_df["주식"], h_df["현금"] = h_df["total"]/ex_rate, h_df["stock"]/ex_rate, h_df["cash"]/ex_rate
            fig = px.line(h_df, x="date", y=["총자산", "주식", "현금"], markers=True)
            fig.update_layout(yaxis_title="금액 (단위: USD)", legend_title="")
        st.plotly_chart(fig, use_container_width=True)

    st.divider()
    if chart_data:
        st.subheader("🍩 포트폴리오 비중")
        st.plotly_chart(px.pie(pd.DataFrame(chart_data), values="평가금액", names="항목", hole=0.45), use_container_width=True)

    def draw_toss_table(df_list):
        if not df_list: st.caption("보유 주식이 없습니다."); return
        html = '<div style="overflow-x: auto; background-color: white; border-radius: 16px; padding: 10px; box-shadow: 0 4px 20px rgba(0,0,0,0.03); margin-bottom: 20px;">'
        html += '<table style="border-collapse: collapse; width: 100%; font-size: 14px; font-family: inherit;">'
        html += '<thead><tr style="border-bottom: 1px solid #e5e8eb;">'
        cols = ["소유", "종목명", "수량", "현재가<br>(평단가)", "평가금액<br>(매입금액)", "평가손익<br>(수익률)", "전일대비", "비고(증권사)"]
        for c in cols: 
            align = "center" if c in ['소유', '수량'] else "left" if c in ['종목명', '비고(증권사)'] else "right"
            html += f'<th style="padding: 12px 8px; text-align: {align}; color: #8b95a1; font-weight: 500; font-size: 13px;">{c}</th>'
        html += '</tr></thead><tbody>'
        
        for r in df_list:
            profit = r['eval_krw'] - r['buy_krw']
            p_pct = (profit / r['buy_krw'] * 100) if r['buy_krw'] > 0 else 0
            p_clr = '#f04452' if profit > 0 else '#3182f6' if profit < 0 else '#333d4b'
            c_clr = '#f04452' if r['d_chg'] > 0 else '#3182f6' if r['d_chg'] < 0 else '#333d4b'
            
            html += f'''<tr style="border-bottom: 1px solid #f2f4f6;">
                <td style="padding: 14px 8px; text-align: center; font-weight: 600; color: #333d4b;">{r['owner']}</td>
                <td style="padding: 14px 8px; text-align: left; font-weight: 600; color: #333d4b;">{r['name']}<br><span style="font-size:12px; color: #8b95a1; font-weight:400;">{r['ticker']}</span></td>
                <td style="padding: 14px 8px; text-align: center; font-weight: 500;">{int(r['qty'])}</td>
                <td style="padding: 14px 8px; text-align: right; font-weight: 500;">{r['curr_p']:,.1f}<br><span style="font-size:12px; color: #8b95a1;">({r['avg_p']:,.1f})</span></td>
                <td style="padding: 14px 8px; text-align: right; font-weight: 500;">{r['eval_krw']/div:,.1f}{unit}<br><span style="font-size:12px; color: #8b95a1;">({r['buy_krw']/div:,.1f}{unit})</span></td>
                <td style="padding: 14px 8px; text-align: right; color: {p_clr}; font-weight: 600;">{profit/div:,.1f}{unit}<br><span style="font-size:12px;">({p_pct:+.2f}%)</span></td>
                <td style="padding: 14px 8px; text-align: right; color: {c_clr}; font-weight: 600;">{r['d_chg']:,.1f}{unit}<br><span style="font-size:12px;">({r['d_pct']:+.2f}%)</span></td>
                <td style="padding: 14px 8px; text-align: left; font-size: 12px; color: #8b95a1;">{r['remarks']}</td>
            </tr>'''
        html += '</tbody></table></div>'
        st.markdown(html, unsafe_allow_html=True)

    st.subheader("🇰🇷 국내 주식")
    draw_toss_table([x for x in final_stock_list if not x['ticker'].isalpha()])
    st.subheader("🇺🇸 해외 주식")
    draw_toss_table([x for x in final_stock_list if x['ticker'].isalpha()])

    # 💡 1,2,3번 반영: 숨김 처리(expanded=False), 직관적 안내문구, 고도화된 프롬프트
    st.divider()
    with st.expander("🤖 AI 프라이빗 뱅커에게 분석 요청하기 (클릭하여 열기)", expanded=False):
        st.markdown("👇 **아래 회색 상자의 우측 상단 모서리를 터치(또는 마우스 오버)하여 나타나는 복사(📋) 버튼**을 누르고, 저에게 붙여넣기 해주세요!")
        
        gemini_prompt = f"""당신은 VVIP 고객의 자산을 관리하는 '최고의 프라이빗 뱅커(PB)'이자 '투자 전략가'입니다.
현재 '성우'와 '지영' 부부의 통합 자산 포트폴리오 데이터를 전달해 드립니다.
아래 데이터를 바탕으로 전문가적인 시각에서 심층 분석과 조언을 제공해 주세요.

---
### 📊 [포트폴리오 요약]
* 기준일시: {datetime.now().strftime("%Y년 %m월 %d일 %H:%M")}
* 총 자산 규모: {total_asset_krw:,.0f} 원
* 현금성 자산: {total_cash_krw:,.0f} 원 (비중: {(total_cash_krw/total_asset_krw*100) if total_asset_krw else 0:.1f}%)
* 주식형 자산: {total_stock_krw:,.0f} 원 (비중: {(total_stock_krw/total_asset_krw*100) if total_asset_krw else 0:.1f}%)

### 📈 [보유 종목 상세 현황] (수익률 순)
"""
        sorted_stocks = sorted(final_stock_list, key=lambda x: (x['eval_krw']-x['buy_krw'])/x['buy_krw'] if x['buy_krw']>0 else 0, reverse=True)
        for s in sorted_stocks:
            p_pct = ((s['eval_krw']-s['buy_krw'])/s['buy_krw']*100) if s['buy_krw']>0 else 0
            wgt = (s['eval_krw']/total_asset_krw*100) if total_asset_krw>0 else 0
            gemini_prompt += f"- [{s['owner']}] {s['name']} ({s['ticker']}): 비중 {wgt:.1f}%, 수익률 {p_pct:+.2f}%, 매입액 {s['buy_krw']:,.0f}원, 평가액 {s['eval_krw']:,.0f}원\n"

        gemini_prompt += """
---
### 📝 [요청 사항]
1. **자산 배분 평가:** 현금과 주식의 비율, 특정 종목(또는 국가)에 대한 쏠림 현상이 없는지 평가해 주세요.
2. **리스크 진단:** 현재 포트폴리오에서 예상되는 위험 요소(환율, 금리, 개별 기업 리스크 등)는 무엇인지 짚어주세요.
3. **맞춤형 리밸런싱 전략:** 수익을 극대화하고 리스크를 방어하기 위해 어떤 종목의 비중을 조절(매수/매도)하는 것이 좋을지, 또는 현금 비중을 어떻게 가져가야 할지 구체적으로 제안해 주세요.
4. **부부 맞춤형 조언:** 부부가 함께 자산을 불려나가는 과정에서 필요한 따뜻하고 동기부여가 되는 조언을 마지막에 덧붙여 주세요. (전문적이지만 친절하고 이해하기 쉬운 톤 앤 매너를 유지해 주세요.)
"""
        st.code(gemini_prompt, language="markdown")
