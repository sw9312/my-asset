import json
from datetime import datetime
from uuid import uuid4

import gspread
import streamlit as st
from google.oauth2.service_account import Credentials


SHEETS = {
    "cash_list": ["id", "owner", "label", "amount", "currency", "updated_at"],
    "stocks": ["id", "owner", "broker", "ticker", "is_overseas", "qty", "avg_price", "input_currency", "name", "note", "updated_at"],
    "history": ["id", "date", "total", "stock", "cash", "성우", "지영", "공동"],
    "watchlist": ["id", "ticker"],
    "custom_dict": ["ticker", "name"],
    "goals": ["id", "name", "target_amount", "target_date", "current_amount", "monthly_contribution", "expected_return", "owner", "icon"],
    "transactions": ["id", "date", "owner", "account", "category", "type", "amount", "currency", "memo"],
    "tasks": ["id", "month", "text", "done", "owner", "updated_at"],
}


@st.cache_resource(show_spinner=False)
def _client():
    credentials = Credentials.from_service_account_info(
        json.loads(st.secrets["gcp_service_account"]),
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    return gspread.authorize(credentials)


@st.cache_resource(show_spinner=False)
def _book():
    return _client().open_by_url(st.secrets["sheet_url"])


def ensure_sheet_tabs(book):
    worksheets = {ws.title: ws for ws in book.worksheets()}
    for name, headers in SHEETS.items():
        if name not in worksheets:
            ws = book.add_worksheet(title=name, rows=500, cols=max(20, len(headers)))
            ws.update("A1", [headers])
            worksheets[name] = ws
    return worksheets


def normalize_sheet_values(name, values):
    """Return canonical values and whether the worksheet needs one rewrite."""
    headers = SHEETS[name]
    if not values:
        return [headers], True
    current_headers = [str(value).strip() for value in values[0]]
    if current_headers == headers:
        return values, False

    normalized = []
    for source_row in values[1:]:
        record = {
            header: source_row[index] if index < len(source_row) else ""
            for index, header in enumerate(current_headers)
            if header
        }
        if "id" in headers and not record.get("id"):
            record["id"] = uuid4().hex[:12]
        if "updated_at" in headers and not record.get("updated_at"):
            record["updated_at"] = datetime.now().isoformat(timespec="seconds")
        if any(str(record.get(key, "")).strip() for key in headers if key not in {"id", "updated_at"}):
            normalized.append([record.get(key, "") for key in headers])
    return [headers] + normalized, True


def values_to_records(name, values):
    headers = SHEETS[name]
    return [
        {header: row[index] if index < len(row) else "" for index, header in enumerate(headers)}
        for row in values[1:]
        if any(str(cell).strip() for cell in row)
    ]


@st.cache_resource(show_spinner=False)
def _initialized_book():
    return _book()


@st.cache_data(ttl=300, show_spinner=False)
def _load_data_cached():
    book = _initialized_book()
    worksheets = ensure_sheet_tabs(book)
    names = list(SHEETS)
    # One batch API call replaces one get_all_values/get_all_records call per tab.
    response = book.values_batch_get([f"'{name}'!A1:Z500" for name in names])
    value_ranges = response.get("valueRanges", [])
    data = {}
    for index, name in enumerate(names):
        values = value_ranges[index].get("values", []) if index < len(value_ranges) else []
        canonical, changed = normalize_sheet_values(name, values)
        if changed:
            worksheets[name].clear()
            worksheets[name].update("A1", canonical)
        data[name] = values_to_records(name, canonical)
    for row in data["stocks"]:
        row["ticker"] = str(row.get("ticker", "")).strip().upper()
        row["is_overseas"] = str(row.get("is_overseas", "")).upper() in {"TRUE", "1"}
        row.setdefault("name", "")
        row.setdefault("note", "")
    for row in data["watchlist"]:
        row["ticker"] = str(row.get("ticker", "")).strip().upper()
    return data


def load_data():
    try:
        data = _load_data_cached()
        st.session_state["last_good_sheet_data"] = data
        return data
    except Exception as exc:
        fallback = st.session_state.get("last_good_sheet_data")
        if fallback:
            st.warning("Google Sheets 요청이 잠시 많아 마지막 정상 데이터를 표시합니다. 잠시 후 자동으로 갱신됩니다.")
            return fallback
        st.error(f"구글 시트 연동 실패: {exc}")
        return {name: [] for name in SHEETS}


def invalidate_data_cache():
    _load_data_cached.clear()


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
    ws = _initialized_book().worksheet(sheet_name)
    ws.append_row([record.get(key, "") for key in headers], value_input_option="USER_ENTERED")
    invalidate_data_cache()
    return record


def replace_record(sheet_name, record_id, updates):
    """Replace one matching row; concurrent edits in other rows are preserved."""
    ws = _initialized_book().worksheet(sheet_name)
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
            invalidate_data_cache()
            return
    raise ValueError("수정할 항목을 찾지 못했습니다.")


def delete_record(sheet_name, record_id):
    ws = _initialized_book().worksheet(sheet_name)
    values = ws.get_all_values()
    if not values or "id" not in values[0]:
        raise ValueError("삭제할 항목의 ID를 찾지 못했습니다.")
    id_col = values[0].index("id")
    for row_no, row in enumerate(values[1:], start=2):
        if id_col < len(row) and row[id_col] == record_id:
            ws.delete_rows(row_no)
            invalidate_data_cache()
            return
    raise ValueError("삭제할 항목을 찾지 못했습니다.")


def upsert_by_key(sheet_name, key, value, updates):
    ws = _initialized_book().worksheet(sheet_name)
    values = ws.get_all_values()
    headers = values[0] if values else SHEETS[sheet_name]
    key_col = headers.index(key)
    for row_no, row in enumerate(values[1:], start=2):
        if key_col < len(row) and str(row[key_col]).upper() == str(value).upper():
            current = {header: row[i] if i < len(row) else "" for i, header in enumerate(headers)}
            current.update(updates)
            ws.update(f"A{row_no}", [[current.get(header, "") for header in headers]])
            invalidate_data_cache()
            return
    append_record(sheet_name, dict(updates, **{key: value}))


def delete_by_key(sheet_name, key, value):
    ws = _initialized_book().worksheet(sheet_name)
    values = ws.get_all_values()
    if not values or key not in values[0]:
        raise ValueError("삭제할 항목을 찾지 못했습니다.")
    key_col = values[0].index(key)
    for row_no, row in enumerate(values[1:], start=2):
        if key_col < len(row) and str(row[key_col]).upper() == str(value).upper():
            ws.delete_rows(row_no)
            invalidate_data_cache()
            return
    raise ValueError("삭제할 항목을 찾지 못했습니다.")


def migrate_missing_ids(data):
    """One-time migration for legacy rows, done sheet-by-sheet before row edits."""
    targets = [
        sheet_name for sheet_name in ("cash_list", "stocks", "watchlist")
        if data.get(sheet_name) and any(not row.get("id") for row in data[sheet_name])
    ]
    if not targets:
        return False
    book = _initialized_book()
    changed = False
    for sheet_name in targets:
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
    if changed:
        invalidate_data_cache()
    return changed


def export_json(data):
    return json.dumps(data, ensure_ascii=False, indent=2)

