from collections import defaultdict
from datetime import date, datetime
from math import pow

from market import get_stock_data


OWNERS = ("성우", "지영", "공동")


def build_portfolio(data, exchange_rate, custom_tuple=()):
    grouped = {}
    for stock in data.get("stocks", []):
        ticker = str(stock.get("ticker", "")).upper()
        owner = stock.get("owner", "공동") or "공동"
        key = (ticker, owner)
        qty = float(stock.get("qty") or 0)
        average = float(stock.get("avg_price") or 0)
        overseas = bool(stock.get("is_overseas"))
        buy_krw = qty * average * (exchange_rate if "USD" in str(stock.get("input_currency")) else 1)
        if key not in grouped:
            grouped[key] = {
                "ticker": ticker, "owner": owner, "qty": 0.0, "buy_krw": 0.0,
                "is_overseas": overseas, "name_override": stock.get("name", ""), "notes": [],
            }
        grouped[key]["qty"] += qty
        grouped[key]["buy_krw"] += buy_krw
        note = stock.get("broker", "") + (f" ({stock.get('note')})" if stock.get("note") else "")
        if note and note not in grouped[key]["notes"]:
            grouped[key]["notes"].append(note)

    stocks = []
    owner_totals = defaultdict(float)
    for item in grouped.values():
        current, day_change, day_pct, web_name = get_stock_data(item["ticker"], custom_tuple)
        multiplier = exchange_rate if item["is_overseas"] else 1
        evaluation = item["qty"] * current * multiplier
        row = dict(item)
        row.update({
            "name": item["name_override"] or web_name,
            "current_native": current,
            "day_change_native": day_change,
            "day_pct": day_pct,
            "eval_krw": evaluation,
            "day_change_krw": item["qty"] * day_change * multiplier,
            "remarks": ", ".join(item["notes"]),
        })
        stocks.append(row)
        owner_totals[item["owner"]] += evaluation

    cash_total = 0.0
    for cash in data.get("cash_list", []):
        value = float(cash.get("amount") or 0)
        if "USD" in str(cash.get("currency")):
            value *= exchange_rate
        cash_total += value
        owner_totals[cash.get("owner", "공동") or "공동"] += value

    stock_total = sum(row["eval_krw"] for row in stocks)
    return {
        "stocks": stocks,
        "cash": cash_total,
        "stock": stock_total,
        "total": cash_total + stock_total,
        "owner_totals": dict(owner_totals),
    }


def history_change(history, current_total):
    if not history:
        return None
    try:
        previous = float(history[-1].get("total") or 0)
    except (TypeError, ValueError):
        return None
    return current_total - previous


def monthly_brief(history, portfolio):
    if not history:
        return "첫 자산 기록을 남기면 다음 달부터 우리 집 월간 브리핑이 만들어져요."
    latest = history[-1]
    previous = history[-2] if len(history) > 1 else None
    lines = []
    if previous:
        delta = float(latest.get("total") or 0) - float(previous.get("total") or 0)
        direction = "늘었어요" if delta >= 0 else "줄었어요"
        lines.append(f"최근 기록 사이 우리 집 자산은 {abs(delta):,.0f}원 {direction}.")
    cash_ratio = portfolio["cash"] / portfolio["total"] * 100 if portfolio["total"] else 0
    lines.append(f"현재 현금 비중은 {cash_ratio:.1f}%예요.")
    if portfolio["stocks"]:
        top = max(portfolio["stocks"], key=lambda row: row["eval_krw"])
        weight = top["eval_krw"] / portfolio["total"] * 100 if portfolio["total"] else 0
        if weight >= 25:
            lines.append(f"{top['name']} 비중이 {weight:.1f}%로 커서 변동성을 함께 확인해 보세요.")
    return " ".join(lines)


def goal_projection(goal, allocated_amount=0):
    target = float(goal.get("target_amount") or 0)
    current = float(goal.get("current_amount") or 0) + float(allocated_amount or 0)
    monthly = float(goal.get("monthly_contribution") or 0)
    annual = float(goal.get("expected_return") or 0) / 100
    try:
        target_date = datetime.strptime(str(goal.get("target_date")), "%Y-%m-%d").date()
        months_left = max(0, (target_date.year - date.today().year) * 12 + target_date.month - date.today().month)
    except ValueError:
        months_left = 0
    monthly_rate = pow(1 + annual, 1 / 12) - 1 if annual > -1 else 0
    future = current
    for _ in range(months_left):
        future = future * (1 + monthly_rate) + monthly
    progress = min(100.0, current / target * 100) if target else 0
    return {"future": future, "gap": max(0, target - future), "progress": progress, "months": months_left}

