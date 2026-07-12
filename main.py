from datetime import date, datetime

import pandas as pd
import plotly.express as px
import streamlit as st

from app_data import (append_record, delete_by_key, delete_record, export_json, load_data,
                      migrate_missing_ids, replace_record, upsert_by_key)
from market import get_exchange_rate, get_stock_data
from portfolio import build_portfolio, clamp_goal_controls, goal_projection, history_change, monthly_brief

st.set_page_config(page_title="504호 자산관리", page_icon="🏡", layout="wide")
st.markdown("""<style>
.block-container{max-width:1180px;padding-top:1.5rem;padding-bottom:4rem}
[data-testid="stAppViewContainer"]{background:#f5f7fa}
div[data-testid="stMetric"]{background:white;border:1px solid #e8ebef;padding:16px;border-radius:16px}
</style>""", unsafe_allow_html=True)


def money(value, usd=False, rate=1):
    return f"${value / rate:,.0f}" if usd else f"{value:,.0f}원"


def colored_metric(label, value, sub_value=None):
    color = "#f04452" if value > 0 else "#3182f6" if value < 0 else "#191f28"
    st.markdown(
        f"<div style='background:white;border:1px solid #e8ebef;border-radius:16px;padding:16px'>"
        f"<div style='color:#8b95a1;font-size:13px'>{label}</div>"
        f"<div style='color:{color};font-size:22px;font-weight:800;margin-top:5px'>{money(value, usd, rate)}</div>"
        + (f"<div style='color:{color};font-size:13px;font-weight:700'>{sub_value}</div>" if sub_value else "")
        + "</div>",
        unsafe_allow_html=True,
    )


def act(callback, message):
    try:
        callback()
        st.toast(message)
        st.rerun()
    except Exception as exc:
        st.error(str(exc))


data = load_data()
try:
    if migrate_missing_ids(data):
        st.toast("기존 데이터에 안전한 편집 ID를 추가했어요.")
except Exception as exc:
    st.warning(f"데이터 ID 변환을 완료하지 못했습니다: {exc}")

rate = get_exchange_rate()
custom = tuple((str(x.get("ticker", "")), str(x.get("name", ""))) for x in data["custom_dict"])
portfolio = build_portfolio(data, rate, custom)

# 버튼 없이 하루 한 번 스냅샷을 남긴다.
today = date.today().isoformat()
if today not in {str(x.get("date", ""))[:10] for x in data["history"]} and portfolio["total"] > 0:
    snapshot = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total": int(portfolio["total"]), "stock": int(portfolio["stock"]), "cash": int(portfolio["cash"]),
        **{owner: int(portfolio["owner_totals"].get(owner, 0)) for owner in ("성우", "지영", "공동")},
    }
    try:
        append_record("history", snapshot)
        data["history"].append(snapshot)
    except Exception as exc:
        st.caption(f"오늘의 자동 기록을 저장하지 못했습니다: {exc}")

st.title("🏡 504호 자산관리")
st.caption(f"우리 집 돈과 미래를 한눈에 · 1달러 {rate:,.0f}원")
scope = st.segmented_control("보기", ["우리 집", "성우", "지영"], default="우리 집")
currency = st.segmented_control("통화", ["원화", "달러"], default="원화")
usd = currency == "달러"


def owned(rows):
    return rows if scope == "우리 집" else [x for x in rows if x.get("owner") in {scope, "공동"}]


cash_total = sum(
    float(x.get("amount") or 0) * (rate if "USD" in str(x.get("currency")) else 1)
    for x in owned(data["cash_list"])
)
stocks = owned(portfolio["stocks"])
stock_total = sum(x["eval_krw"] for x in stocks)
total = cash_total + stock_total
delta = history_change(data["history"], portfolio["total"]) if scope == "우리 집" else None

home, assets, future, brief, manage = st.tabs(
    ["🏠 우리 집 오늘", "💰 자산", "🔭 목표 타임머신", "📝 월간 브리핑", "⚙️ 관리"]
)

with home:
    cols = st.columns(4)
    cols[0].metric("총자산", money(total, usd, rate), money(delta, usd, rate) if delta is not None else None)
    cols[1].metric("현금", money(cash_total, usd, rate), f"{cash_total/total*100:.1f}%" if total else None)
    cols[2].metric("투자", money(stock_total, usd, rate), f"{stock_total/total*100:.1f}%" if total else None)
    day_change = sum(x["day_change_krw"] for x in stocks)
    cols[3].metric("오늘의 투자 변화", money(day_change, usd, rate))

    left, right = st.columns([1.2, 1])
    with left, st.container(border=True):
        st.subheader("우리 둘의 자산")
        owner_df = pd.DataFrame([
            {"소유": owner, "금액": portfolio["owner_totals"].get(owner, 0)}
            for owner in ("성우", "지영", "공동") if portfolio["owner_totals"].get(owner, 0) > 0
        ])
        if not owner_df.empty:
            fig = px.bar(owner_df, x="소유", y="금액", text_auto=".2s", color="소유")
            fig.update_layout(showlegend=False, height=300, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    with right, st.container(border=True):
        st.subheader("오늘의 한 가지 행동")
        ratio = portfolio["cash"]/portfolio["total"]*100 if portfolio["total"] else 0
        if not data["goals"]:
            st.info("두 분이 함께 이루고 싶은 목표를 하나 등록해 보세요.")
        elif ratio >= 35:
            st.info(f"현금 비중이 {ratio:.1f}%예요. 비상금과 목표자금을 나눠 이름 붙여보세요.")
        elif portfolio["stocks"]:
            largest = max(portfolio["stocks"], key=lambda x: x["eval_krw"])
            weight = largest["eval_krw"]/portfolio["total"]*100 if portfolio["total"] else 0
            st.info(f"가장 큰 자산은 {largest['name']}이고 우리 집 자산의 {weight:.1f}%예요.")
        st.subheader("이번 달 한 문장")
        st.write(monthly_brief(data["history"], portfolio))

    st.subheader(f"✅ {date.today().month}월 우리 집 할 일")
    this_month = date.today().strftime("%Y-%m")
    monthly_tasks = [task for task in data["tasks"] if str(task.get("month")) == this_month]
    if not monthly_tasks:
        st.caption("이번 달 체크리스트가 비어 있어요. 아래에서 첫 할 일을 추가해 보세요.")
    for task in monthly_tasks:
        task_id = task.get("id")
        checked = str(task.get("done", "")).upper() in {"TRUE", "1", "YES"}
        c1, c2 = st.columns([10, 1])
        new_checked = c1.checkbox(
            f"[{task.get('owner') or '공동'}] {task.get('text')}",
            value=checked,
            key=f"task_{task_id}",
        )
        if new_checked != checked:
            act(lambda tid=task_id, done=new_checked: replace_record("tasks", tid, {"done":done}), "체크리스트를 업데이트했어요.")
        if c2.button("삭제", key=f"task_del_{task_id}"):
            act(lambda tid=task_id: delete_record("tasks", tid), "할 일을 삭제했어요.")
    with st.form("monthly_task", clear_on_submit=True):
        tc1, tc2 = st.columns([4, 1])
        task_text = tc1.text_input("이번 달 할 일", placeholder="예: 주택청약 잔액 확인")
        task_owner = tc2.selectbox("담당", ["공동", "성우", "지영"])
        if st.form_submit_button("체크리스트에 추가", use_container_width=True) and task_text.strip():
            act(lambda: append_record("tasks", {"month":this_month, "text":task_text.strip(), "done":False, "owner":task_owner}), "이번 달 할 일을 추가했어요.")

    if data["history"]:
        st.subheader("자산 추이")
        df = pd.DataFrame(data["history"])
        for key in ("total", "stock", "cash"):
            df[key] = pd.to_numeric(df[key], errors="coerce")
        fig = px.line(df.rename(columns={"total":"총자산","stock":"주식","cash":"현금"}),
                      x="date", y=["총자산","주식","현금"], markers=True)
        fig.update_layout(height=360, legend_title="", yaxis_title="원")
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

with assets:
    st.subheader(f"{scope} 자산 상세")
    total_buy = sum(row["buy_krw"] for row in stocks)
    total_profit = stock_total - total_buy
    total_return = total_profit / total_buy * 100 if total_buy else 0
    total_day_change = sum(row["day_change_krw"] for row in stocks)
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("총 매입금액", money(total_buy, usd, rate))
    with s2:
        colored_metric("총 평가손익", total_profit, f"{total_return:+.2f}%")
    s3.metric("총 평가금액", money(stock_total, usd, rate))
    with s4:
        colored_metric("전일대비", total_day_change)

    rows = []
    for row in stocks:
        profit = row["eval_krw"] - row["buy_krw"]
        # 해외주식도 화면 기준 통화로 변환한다.
        current_krw = row["current_native"] * (rate if row["is_overseas"] else 1)
        rows.append({
            "소유": row["owner"], "종목": row["name"], "코드": row["ticker"],
            "수량": f"{row['qty']:,.6f}".rstrip("0").rstrip("."),
            "현재가": money(current_krw, usd, rate), "평가금액": money(row["eval_krw"], usd, rate),
            "평가손익": money(profit, usd, rate),
            "수익률": f"{profit/row['buy_krw']*100:+.2f}%" if row["buy_krw"] else "-",
            "전일": f"{row['day_pct']:+.2f}%", "계좌": row["remarks"],
        })
    if rows:
        # 사용자 입력을 HTML로 조립하지 않아 스크립트/마크업 삽입을 막는다.
        result_df = pd.DataFrame(rows)
        def profit_color(value):
            text = str(value).replace("원", "").replace("$", "").replace(",", "").replace("%", "")
            try:
                number = float(text)
            except ValueError:
                return ""
            return "color:#f04452;font-weight:700" if number > 0 else "color:#3182f6;font-weight:700" if number < 0 else "color:#191f28"
        styled = result_df.style.map(profit_color, subset=["평가손익", "수익률", "전일"])
        st.dataframe(styled, hide_index=True, use_container_width=True)

        pie_rows = [{"항목": row["name"], "평가금액": row["eval_krw"]} for row in stocks]
        if cash_total:
            pie_rows.append({"항목": "현금", "평가금액": cash_total})
        st.subheader("포트폴리오 비중")
        pie = px.pie(pd.DataFrame(pie_rows), values="평가금액", names="항목", hole=.45)
        pie.update_layout(height=420, legend_title="", margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(pie, use_container_width=True, config={"displayModeBar": False})
    else:
        st.info("등록된 투자 자산이 없습니다.")
    cash_rows = []
    for x in owned(data["cash_list"]):
        amount = float(x.get("amount") or 0)
        symbol = "$" if "USD" in str(x.get("currency")) else "₩"
        cash_rows.append({"소유":x.get("owner"), "항목":x.get("label"),
                          "금액":f"{symbol}{amount:,.2f}" if symbol == "$" else f"{symbol}{amount:,.0f}",
                          "통화":x.get("currency")})
    if cash_rows:
        st.subheader("현금·예금")
        st.dataframe(pd.DataFrame(cash_rows), hide_index=True, use_container_width=True)

with future:
    st.subheader("목표 타임머신")
    st.caption("매월 저축액과 기대수익률을 움직여 목표에 도착하는 모습을 미리 확인하세요.")
    if not data["goals"]:
        st.info("관리 탭에서 첫 가족 목표를 등록해 주세요.")
    for goal in data["goals"]:
        with st.container(border=True):
            st.markdown(f"### {goal.get('icon') or '🎯'} {goal.get('name')}")
            c1, c2 = st.columns(2)
            safe_monthly, safe_expected = clamp_goal_controls(
                goal.get("monthly_contribution"), goal.get("expected_return")
            )
            monthly = c1.slider("매월 모을 금액", 0, 10_000_000,
                                safe_monthly, 100_000,
                                key=f"gm{goal.get('id')}")
            expected = c2.slider("기대 연 수익률", 0.0, 12.0,
                                 safe_expected, .5,
                                 key=f"gr{goal.get('id')}")
            c1.caption(f"월 저축액: **{monthly:,.0f}원**")
            c2.caption(f"기대수익률: **{expected:,.1f}%**")
            result = goal_projection(dict(goal, monthly_contribution=monthly, expected_return=expected))
            st.progress(result["progress"]/100, text=f"현재 {result['progress']:.1f}%")
            a, b, c = st.columns(3)
            a.metric("목표", money(float(goal.get("target_amount") or 0)))
            b.metric("목표일 예상", money(result["future"]))
            c.metric("부족 예상", money(result["gap"]))
            if result["gap"] <= 0:
                st.success("지금 계획이면 목표일 안에 도착할 수 있어요!")
            else:
                st.warning(f"월 {result['gap']/max(1,result['months']):,.0f}원을 더 모으면 가능성이 높아져요.")

with brief:
    st.subheader("부부 월간 브리핑")
    st.success(monthly_brief(data["history"], portfolio))
    month = date.today().strftime("%Y-%m")
    tx = [x for x in data["transactions"] if str(x.get("date","")).startswith(month)]
    if tx:
        df = pd.DataFrame(tx)
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
        summary = df.groupby(["owner","type"], as_index=False)["amount"].sum()
        summary["amount"] = summary["amount"].map(lambda value: f"{value:,.0f}원")
        st.dataframe(summary.rename(columns={"owner":"소유","type":"구분","amount":"금액"}),
                     hide_index=True, use_container_width=True)
    else:
        st.caption("이번 달 입출금을 기록하면 저축과 투자수익을 더 정확히 구분할 수 있어요.")

    st.divider()
    st.subheader("AI 프라이빗 뱅커 분석용 데이터")
    prompt = (
        "당신은 부부의 자산을 관리하는 프라이빗 뱅커입니다. 아래 포트폴리오를 분석해 주세요.\n"
        f"총자산 {portfolio['total']:,.0f}원, 현금 {portfolio['cash']:,.0f}원, "
        f"주식 {portfolio['stock']:,.0f}원.\n"
    )
    for row in portfolio["stocks"]:
        profit = row["eval_krw"] - row["buy_krw"]
        return_rate = profit / row["buy_krw"] * 100 if row["buy_krw"] else 0
        prompt += f"- [{row['owner']}] {row['name']}({row['ticker']}): 평가액 {row['eval_krw']:,.0f}원, 수익률 {return_rate:+.2f}%\n"
    prompt += "자산배분, 집중위험, 리밸런싱, 부부가 함께 실행할 행동 3가지를 제안해 주세요."
    st.code(prompt, language="markdown")

with manage:
    cash_tab, stock_tab, goal_tab, tx_tab, watch_tab, dict_tab, history_tab, edit_tab, backup_tab = st.tabs(
        ["현금 추가","주식 추가","목표","입출금","관심종목","종목 사전","기록 관리","수정·삭제","백업"]
    )
    with cash_tab, st.form("cash", clear_on_submit=True):
        owner = st.selectbox("소유", ["성우","지영","공동"])
        label = st.text_input("항목", "현금")
        amount = st.number_input("금액", min_value=0.0)
        st.caption(f"입력 금액: **{amount:,.0f}**")
        curr = st.selectbox("통화", ["KRW(원)","USD(달러)"])
        if st.form_submit_button("추가", use_container_width=True):
            act(lambda: append_record("cash_list", {"owner":owner,"label":label,"amount":amount,"currency":curr}), "추가했어요.")

    with stock_tab, st.form("stock", clear_on_submit=True):
        c1, c2 = st.columns(2)
        owner = c1.selectbox("소유", ["성우","지영","공동"], key="so")
        ticker = c2.text_input("종목코드").strip().upper()
        broker = c1.selectbox("증권사", ["미래에셋","나무","토스","키움","삼성","기타"])
        overseas = c2.checkbox("해외주식")
        qty = c1.number_input("수량", min_value=0.0, format="%.6f")
        avg = c2.number_input("평균단가", min_value=0.0)
        c1.caption(f"수량: **{qty:,.6f}**".rstrip("0").rstrip("."))
        c2.caption(f"평균단가: **{avg:,.2f}**")
        curr = st.selectbox("평단가 통화", ["USD(달러)","KRW(원)"] if overseas else ["KRW(원)","USD(달러)"])
        note = st.text_input("계좌·비고")
        if st.form_submit_button("추가", use_container_width=True) and ticker:
            act(lambda: append_record("stocks", {"owner":owner,"broker":broker,"ticker":ticker,
                "is_overseas":overseas,"qty":qty,"avg_price":avg,"input_currency":curr,"name":"","note":note}), "추가했어요.")

    with goal_tab, st.form("goal", clear_on_submit=True):
        name = st.text_input("목표 이름", placeholder="예: 내 집 마련")
        c1, c2 = st.columns(2)
        target = c1.number_input("목표 금액", min_value=0.0, step=1_000_000.0)
        target_date = c2.date_input("목표일")
        current = c1.number_input("이미 모은 금액", min_value=0.0, step=1_000_000.0)
        monthly = c2.number_input("월 저축액", min_value=0.0, step=100_000.0)
        c1.caption(f"목표: **{target:,.0f}원** · 현재: **{current:,.0f}원**")
        c2.caption(f"월 저축: **{monthly:,.0f}원**")
        expected = c1.number_input("기대 연 수익률(%)", 0.0, 30.0, 3.0)
        owner = c2.selectbox("소유", ["공동","성우","지영"], key="go")
        icon = st.text_input("아이콘", "🎯", max_chars=2)
        if st.form_submit_button("목표 추가", use_container_width=True) and name:
            act(lambda: append_record("goals", {"name":name,"target_amount":target,
                "target_date":target_date.isoformat(),"current_amount":current,
                "monthly_contribution":monthly,"expected_return":expected,"owner":owner,"icon":icon}), "목표를 추가했어요.")

    with tx_tab, st.form("tx", clear_on_submit=True):
        tx_date = st.date_input("날짜", key="td")
        c1, c2 = st.columns(2)
        owner = c1.selectbox("소유", ["성우","지영","공동"], key="to")
        kind = c2.selectbox("구분", ["입금","출금","매수","매도","배당"])
        account = c1.text_input("계좌")
        category = c2.text_input("분류")
        amount = st.number_input("금액", min_value=0.0, key="ta")
        st.caption(f"입력 금액: **{amount:,.0f}원**")
        memo = st.text_input("메모")
        if st.form_submit_button("기록", use_container_width=True):
            act(lambda: append_record("transactions", {"date":tx_date.isoformat(),"owner":owner,
                "account":account,"category":category,"type":kind,"amount":amount,"currency":"KRW","memo":memo}), "기록했어요.")

    with watch_tab:
        with st.form("watch", clear_on_submit=True):
            ticker = st.text_input("관심종목 코드").strip().upper()
            if st.form_submit_button("관심종목 추가") and ticker:
                act(lambda: append_record("watchlist", {"ticker":ticker}), "관심종목을 추가했어요.")
        for row in data["watchlist"]:
            price, change, pct, name = get_stock_data(row.get("ticker"), custom)
            c1, c2, c3 = st.columns([3, 2, 1])
            c1.write(f"⭐ **{name}** ({row.get('ticker')})")
            color = "🔴" if change > 0 else "🔵" if change < 0 else "⚪"
            c2.write(f"{price:,.2f} · {color} {pct:+.2f}%")
            if c3.button("삭제", key=f"wd{row.get('id')}"):
                act(lambda rid=row.get("id"): delete_record("watchlist", rid), "삭제했어요.")

    with dict_tab:
        st.info("자동 이름이 이상한 종목을 한 번 등록하면 계속 적용됩니다.")
        with st.form("dictionary", clear_on_submit=True):
            ticker = st.text_input("종목코드", key="dt").strip().upper()
            name = st.text_input("표시할 한글 이름")
            if st.form_submit_button("저장") and ticker and name:
                act(lambda: upsert_by_key("custom_dict", "ticker", ticker, {"name":name}), "종목 이름을 저장했어요.")
        for row in data["custom_dict"]:
            c1, c2 = st.columns([5, 1])
            c1.write(f"**{row.get('ticker')}** · {row.get('name')}")
            if c2.button("삭제", key=f"dd{row.get('ticker')}"):
                act(lambda ticker=row.get("ticker"): delete_by_key("custom_dict", "ticker", ticker), "삭제했어요.")

    with history_tab:
        if st.button("현재 자산 지금 기록하기", use_container_width=True):
            snapshot = {"date":datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "total":int(portfolio["total"]), "stock":int(portfolio["stock"]), "cash":int(portfolio["cash"]),
                        **{owner:int(portfolio["owner_totals"].get(owner, 0)) for owner in ("성우","지영","공동")}}
            act(lambda: append_record("history", snapshot), "현재 자산을 기록했어요.")
        history_rows = list(reversed(data["history"][-30:]))
        if history_rows:
            history_display = pd.DataFrame(history_rows).copy()
            for column in ["total", "stock", "cash", "성우", "지영", "공동"]:
                if column in history_display.columns:
                    history_display[column] = pd.to_numeric(history_display[column], errors="coerce").fillna(0).map(lambda value: f"{value:,.0f}원")
            st.dataframe(history_display, hide_index=True, use_container_width=True)
            selected_history = st.selectbox(
                "삭제할 기록",
                history_rows,
                format_func=lambda row: f"{row.get('date')} · {float(row.get('total') or 0):,.0f}원",
            )
            if st.button("선택 기록 삭제"):
                act(lambda: delete_record("history", selected_history.get("id")), "기록을 삭제했어요.")

    with edit_tab:
        kind = st.radio("편집할 자산", ["현금","주식"], horizontal=True)
        sheet = "cash_list" if kind == "현금" else "stocks"
        for row in data[sheet]:
            rid = row.get("id")
            with st.expander(f"[{row.get('owner')}] {row.get('label') or row.get('ticker')}"):
                if kind == "현금":
                    value = st.number_input("금액", value=float(row.get("amount") or 0), key=f"a{rid}")
                    if st.button("저장", key=f"s{rid}"):
                        act(lambda rid=rid, value=value: replace_record(sheet, rid, {"amount":value}), "수정했어요.")
                else:
                    qty = st.number_input("수량", value=float(row.get("qty") or 0), format="%.6f", key=f"q{rid}")
                    avg = st.number_input("평균단가", value=float(row.get("avg_price") or 0), key=f"p{rid}")
                    if st.button("저장", key=f"s{rid}"):
                        act(lambda rid=rid, q=qty, a=avg: replace_record(sheet, rid, {"qty":q,"avg_price":a}), "수정했어요.")
                if st.button("삭제", key=f"d{rid}"):
                    act(lambda rid=rid: delete_record(sheet, rid), "삭제했어요.")

    with backup_tab:
        st.download_button("JSON 백업 내려받기", export_json(data), f"504-assets-{today}.json",
                           "application/json", use_container_width=True)
        st.caption("전체 시트를 덮어쓰는 복구 기능은 데이터 손상 위험 때문에 제거했습니다.")
