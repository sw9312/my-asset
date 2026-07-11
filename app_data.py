import json
from datetime import datetime
from uuid import uuid4

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials


SHEETS = {
    "cash_list": ["id", "owner", "label", "amount", "currency", "updated_at"],
    "stocks": ["id", "owner", "broker", "ticker", "is_overseas", "qty", "avg_price", "input_currency", "name", "note", "updated_at"],
    "history": ["date", "total", "stock", "cash", "성우", "지영", "공동"],
    "watchlist": ["id", "ticker"],
    "custom_dict": ["ticker", "name"],
    "goals": ["id", "name", "target_amount", "target_date", "current_amount", "monthly_contribution", "expected_return", "owner", "icon"],
    "transactions": ["id", "date", "owner", "account", "category", "type", "amount", "currency", "memo"],
}


def _client():
    credentials = Credentials.from_service_account_info(
        json.loads(st.secrets["gcp_service_account"]),
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    return gspread.authorize(credentials)


def _book():
    return _client().open_by_url(st.secrets["sheet_url"])


def init_sheets(book):
    existing = {ws.title for ws in book.worksheets()}
    for name, headers in SHEETS.items():
        if name not in existing:
            ws = book.add_worksheet(title=name, rows=500, cols=max(20, len(headers)))
            ws.update("A1", [headers])


def load_data():
    try:
        book = _book()
        init_sheets(book)
        data = {name: book.worksheet(name).get_all_records() for name in SHEETS}
        for row in data["stocks"]:
            row["ticker"] = str(row.get("ticker", "")).strip().upper()
            row["is_overseas"] = str(row.get("is_overseas", "")).upper() in {"TRUE", "1"}
            row.setdefault("name", "")
            row.setdefault("note", "")
        for row in data["watchlist"]:
            row["ticker"] = str(row.get("ticker", "")).strip().upper()
        return data
    except Exception as exc:
        st.error(f"구글 시트 연동 실패: {exc}")
        return {name: [] for name in SHEETS}


def _ensure_id(record):
    record = dict(record)
    record.setdefault("id", uuid4().hex[:12])
    if "updated_at" in record or "updated_at" in SHEETS.get(record.get("_sheet", ""), []):
        record["updated_at"] = datetime.now().isoformat(timespec="seconds")
    record.pop("_sheet", None)
    return record


def append_record(sheet_name, record):
    """Append one row without clearing any worksheet."""
    headers = SHEETS[sheet_name]
    record = dict(record, _sheet=sheet_name)
    record = _ensure_id(record)
    ws = _book().worksheet(sheet_name)
    ws.append_row([record.get(key, "") for key in headers], value_input_option="USER_ENTERED")
    return record


def replace_record(sheet_name, record_id, updates):
    """Replace one matching row; concurrent edits in other rows are preserved."""
    ws = _book().worksheet(sheet_name)
    values = ws.get_all_values()
    if not values:
        raise ValueError(f"{sheet_name} 시트에 헤더가 없습니다.")
    headers = values[0]
    if "id" not in headers:
        raise ValueError("기존 데이터에 ID가 없습니다. 앱을 새로고침한 뒤 다시 시도해 주세요.")
    id_col = headers.index("id")
    for row_no, row in enumerate(values[1:], start=2):
        if id_col < len(row) and row[id_col] == record_id:
            current = {key: row[i] if i < len(row) else "" for i, key in enumerate(headers)}
            current.update(updates)
            if "updated_at" in headers:
                current["updated_at"] = datetime.now().isoformat(timespec="seconds")
            ws.update(f"A{row_no}", [[current.get(key, "") for key in headers]])
            return
    raise ValueError("수정할 항목을 찾지 못했습니다.")


def delete_record(sheet_name, record_id):
    ws = _book().worksheet(sheet_name)
    values = ws.get_all_values()
    if not values or "id" not in values[0]:
        raise ValueError("삭제할 항목의 ID를 찾지 못했습니다.")
    id_col = values[0].index("id")
    for row_no, row in enumerate(values[1:], start=2):
        if id_col < len(row) and row[id_col] == record_id:
            ws.delete_rows(row_no)
            return
    raise ValueError("삭제할 항목을 찾지 못했습니다.")


def migrate_missing_ids(data):
    """One-time migration for legacy rows, done sheet-by-sheet before row edits."""
    book = _book()
    changed = False
    for sheet_name in ("cash_list", "stocks", "watchlist"):
        rows = data.get(sheet_name, [])
        if rows and any(not row.get("id") for row in rows):
            normalized = []
            for row in rows:
                item = dict(row, _sheet=sheet_name)
                normalized.append(_ensure_id(item))
            headers = SHEETS[sheet_name]
            ws = book.worksheet(sheet_name)
            ws.clear()
            ws.update("A1", [headers] + [[row.get(key, "") for key in headers] for row in normalized])
            data[sheet_name] = normalized
            changed = True
    return changed


def export_json(data):
    return json.dumps(data, ensure_ascii=False, indent=2)

