import app_data
from app_data import SHEETS, migrate_missing_ids, normalize_sheet_values


class FakeWorksheet:
    def __init__(self, title, values):
        self.title = title
        self.values = values

    def get_all_values(self):
        return self.values

    def clear(self):
        self.values = []

    def update(self, _range, values):
        self.values = values


class FakeBook:
    def __init__(self, sheets):
        self.sheets = {sheet.title: sheet for sheet in sheets}
        self.batch_calls = 0

    def worksheets(self):
        return list(self.sheets.values())

    def add_worksheet(self, title, rows, cols):
        sheet = FakeWorksheet(title, [])
        self.sheets[title] = sheet
        return sheet

    def values_batch_get(self, ranges):
        self.batch_calls += 1
        return {"valueRanges": [{"values": self.sheets[name].values} for name in SHEETS]}


def test_normalize_migrates_legacy_cash_without_losing_values():
    values, changed = normalize_sheet_values(
        "cash_list",
        [["owner", "label", "amount", "currency"], ["지영", "현금", "100", "KRW(원)"]],
    )
    assert changed is True
    assert values[0] == SHEETS["cash_list"]
    migrated = dict(zip(values[0], values[1]))
    assert migrated["owner"] == "지영"
    assert migrated["amount"] == "100"
    assert migrated["id"]


def test_normalize_repairs_blank_duplicate_headers():
    values, changed = normalize_sheet_values(
        "history",
        [["date", "total", "stock", "cash", "", ""], ["2026-01-01", "100", "80", "20", "50", "50"]],
    )
    assert changed is True
    assert values[0] == SHEETS["history"]
    assert values[1][2:5] == ["100", "80", "20"]


def test_migration_with_existing_ids_does_not_read_google_sheets(monkeypatch):
    def fail_if_called():
        raise AssertionError("Google Sheets should not be opened during a slider rerun")

    monkeypatch.setattr(app_data, "_initialized_book", fail_if_called)
    data = {
        "cash_list": [{"id": "cash-1"}],
        "stocks": [{"id": "stock-1"}],
        "watchlist": [{"id": "watch-1"}],
    }
    assert migrate_missing_ids(data) is False


def test_cached_loader_uses_one_batch_read_across_reruns(monkeypatch):
    book = FakeBook([FakeWorksheet(name, [headers]) for name, headers in SHEETS.items()])
    monkeypatch.setattr(app_data, "_initialized_book", lambda: book)
    app_data._load_data_cached.clear()
    app_data._load_data_cached()
    app_data._load_data_cached()
    assert book.batch_calls == 1
    app_data._load_data_cached.clear()
